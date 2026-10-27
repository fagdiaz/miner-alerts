"""Unit & Integration Tests for Spec 093.

Validates:
1. DetectionHook streak persistence (fixing the premature wipe of offline_streak/low_streak).
2. Fast Phase Drop & Elevator Outage cycle wiring and hysteresis bypass.
3. Autonomous Stock Firmware Recovery Handler (Bitmain reboot -> VNish reflash + profile restore).
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from app.core.engine import DetectionHook
from app.core.models import MinerState
from app.core.reboot_safety import STATE_HASHBOARD, STATE_LOW, STATE_OFFLINE, STATE_OK
from app.governance.firmware_recovery import (
    handle_stock_firmware_recovery,
    reboot_stock_bitmain,
    reset_stock_recovery_state,
)
from app.governance.phase_drop_discriminator import (
    PhaseDropAssessment,
    PhaseDropConfig,
    PhaseDropVerdict,
    evaluate_phase_drop,
    process_phase_drop_cycle,
    render_phase_drop_alert,
)


class DummyContext:
    def __init__(self):
        self.miners = [
            {"name": "23", "host": "192.168.100.23", "port": 4028, "electrical_group": "elevator_1"},
            {"name": "24", "host": "192.168.100.24", "port": 4028, "electrical_group": "elevator_1"},
            {"name": "25", "host": "192.168.100.25", "port": 4028, "electrical_group": "elevator_2"},
            {"name": "26", "host": "192.168.100.26", "port": 4028, "electrical_group": "elevator_2"},
        ]
        self.config = {
            "fails_before_alert": 3,
            "recovery_successes": 1,
            "expected_boards": 3,
        }
        self.threshold_ths = 60.0
        self.state_lock = MagicMock()
        self.state_lock.__enter__.return_value = None
        self.state_lock.__exit__.return_value = None
        self.event_store = MagicMock()
        self.bot_token = "test_bot_token"
        self.chat_id = "123456"
        self.qa_mode = False
        self.qa_notify = False


def test_detection_hook_offline_streak_persistence():
    """Verify that offline_streak increments across ticks and triggers OFFLINE on tick 3."""
    ctx = DummyContext()
    hook = DetectionHook()
    state = MinerState(state=STATE_OK, offline_streak=0)
    miner_key = "25|192.168.100.25:4028"
    states = {miner_key: state}

    tick_data = {
        "states": states,
        "miner_results": {
            miner_key: {
                "miner": ctx.miners[2],
                "state": state,
                "responded": False,
                "rate_ths": None,
                "elapsed": None,
                "previous_elapsed": None,
                "reboot_reason": "",
                "active_boards": None,
                "vnish_telemetry": None,
                "quality_telemetry": None,
            }
        },
        "startup_grace_active": False,
    }

    # Tick 1: responded=False -> streak=1, state stays OK
    hook.execute(ctx, 1, 1000.0, tick_data)
    assert state.offline_streak == 1
    assert state.state == STATE_OK

    # Tick 2: responded=False -> streak=2, state stays OK
    hook.execute(ctx, 2, 1030.0, tick_data)
    assert state.offline_streak == 2
    assert state.state == STATE_OK

    # Tick 3: responded=False -> streak=3 (>= fails_before_alert) -> transitions to OFFLINE
    hook.execute(ctx, 3, 1060.0, tick_data)
    assert state.offline_streak == 3
    assert state.state == STATE_OFFLINE

    # Tick 4: responded=False -> streak=4, stays OFFLINE
    hook.execute(ctx, 4, 1090.0, tick_data)
    assert state.offline_streak == 4
    assert state.state == STATE_OFFLINE

    # Tick 5: Miner recovers (responded=True, rate=90 TH/s)
    tick_data["miner_results"][miner_key]["responded"] = True
    tick_data["miner_results"][miner_key]["rate_ths"] = 90.0
    tick_data["miner_results"][miner_key]["active_boards"] = 3
    hook.execute(ctx, 5, 1120.0, tick_data)
    assert state.state == STATE_OK
    assert state.offline_streak == 0


def test_detection_hook_low_streak_persistence():
    """Verify that low_streak increments across ticks without premature wipe and transitions to LOW."""
    ctx = DummyContext()
    hook = DetectionHook()
    state = MinerState(state=STATE_OK, low_streak=0)
    miner_key = "25|192.168.100.25:4028"
    states = {miner_key: state}

    tick_data = {
        "states": states,
        "miner_results": {
            miner_key: {
                "miner": ctx.miners[2],
                "state": state,
                "responded": True,
                "rate_ths": 45.0,  # Below threshold 60.0
                "elapsed": 1000,
                "previous_elapsed": 970,
                "reboot_reason": "",
                "active_boards": 3,
                "vnish_telemetry": None,
                "quality_telemetry": None,
            }
        },
        "startup_grace_active": False,
    }

    # Tick 1: low hashrate -> low_streak=1, state stays OK
    hook.execute(ctx, 1, 1000.0, tick_data)
    assert state.low_streak == 1
    assert state.state == STATE_OK

    # Tick 2: low hashrate -> low_streak=2, state stays OK
    hook.execute(ctx, 2, 1030.0, tick_data)
    assert state.low_streak == 2
    assert state.state == STATE_OK

    # Tick 3: low hashrate -> low_streak=3 -> transitions to LOW
    hook.execute(ctx, 3, 1060.0, tick_data)
    assert state.low_streak == 3
    assert state.state == STATE_LOW


def test_phase_drop_elevator_detection_and_alert():
    """Verify evaluate_phase_drop classifies simultaneous elevator drops correctly."""
    failed_miners = [
        {"name": "25", "host": "192.168.100.25", "port": 4028, "electrical_group": "elevator_2"},
        {"name": "26", "host": "192.168.100.26", "port": 4028, "electrical_group": "elevator_2"},
    ]
    responded_miners = [
        {"name": "23", "host": "192.168.100.23", "port": 4028, "electrical_group": "elevator_1"},
        {"name": "24", "host": "192.168.100.24", "port": 4028, "electrical_group": "elevator_1"},
    ]

    assessment = evaluate_phase_drop(
        failed_miners=failed_miners,
        responded_miners=responded_miners,
        host_network_ok=True,
    )

    assert assessment.verdict == PhaseDropVerdict.PHASE_DROP_ELEVATOR
    assert assessment.affected_groups == ["elevator_2"]
    assert sorted(assessment.failed_miners) == ["25", "26"]
    assert assessment.active_groups == ["elevator_1"]

    card = render_phase_drop_alert(assessment)
    assert "DISPARO DE CIRCUITO" in card
    assert "elevator_2" in card
    assert "Desenergizado" in card


def test_process_phase_drop_cycle_bypasses_hysteresis():
    """Verify that process_phase_drop_cycle marks miners OFFLINE immediately when elevator drops."""
    st25 = MinerState(state=STATE_OK, offline_streak=0)
    st26 = MinerState(state=STATE_OK, offline_streak=0)
    states = {
        "25|192.168.100.25:4028": st25,
        "26|192.168.100.26:4028": st26,
    }
    failed_miners = [
        {"name": "25", "host": "192.168.100.25", "port": 4028, "electrical_group": "elevator_2"},
        {"name": "26", "host": "192.168.100.26", "port": 4028, "electrical_group": "elevator_2"},
    ]
    responded_miners = [
        {"name": "23", "host": "192.168.100.23", "port": 4028, "electrical_group": "elevator_1"},
        {"name": "24", "host": "192.168.100.24", "port": 4028, "electrical_group": "elevator_1"},
    ]

    last_alert_ts = {}
    active_phase_drops = set()
    mock_send_tg = MagicMock()

    assessment = process_phase_drop_cycle(
        miners=failed_miners + responded_miners,
        states=states,
        tick_failed_miners=failed_miners,
        tick_responded_miners=responded_miners,
        maintenance_miner_ids=set(),
        phase_drop_config=PhaseDropConfig(enabled=True),
        last_alert_ts=last_alert_ts,
        active_phase_drops=active_phase_drops,
        now_ts=1000.0,
        fails_before_alert=3,
        send_telegram_fn=mock_send_tg,
        bot_token="test_token",
        chat_id="12345",
        reachability_fn=lambda **kw: True,
    )

    assert assessment.verdict == PhaseDropVerdict.PHASE_DROP_ELEVATOR
    # Immediate hysteresis bypass
    assert st25.state == "OFFLINE"
    assert st26.state == "OFFLINE"
    assert st25.offline_streak >= 3
    assert st26.offline_streak >= 3

    # Telegram alert dispatched
    assert mock_send_tg.called
    assert "elevator_2" in last_alert_ts
    assert "elevator_2" in active_phase_drops


def test_reboot_stock_bitmain_handles_response():
    """Verify reboot_stock_bitmain issues digest auth request properly."""
    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        ok, msg = reboot_stock_bitmain("192.168.100.26")
        assert ok is True
        assert "200" in msg


def test_stock_firmware_recovery_ladder():
    """Verify autonomous recovery steps: attempt 1 -> reboot, attempt 2 -> reflash."""
    reset_stock_recovery_state()
    mock_send_tg = MagicMock()
    config = {"stock_firmware_auto_recovery_enabled": True}

    with patch("app.governance.firmware_recovery.reboot_stock_bitmain") as mock_reboot, \
         patch("app.governance.firmware_recovery.is_stock_bitmain") as mock_is_stock, \
         patch("app.governance.firmware_recovery.flash_bitmain_nand") as mock_flash, \
         patch("app.governance.firmware_recovery.restore_miner_profile") as mock_restore:

        mock_reboot.return_value = (True, "Reboot OK")
        mock_is_stock.return_value = True
        mock_flash.return_value = (True, "Flash OK")
        mock_restore.return_value = (True, "Profile OK")

        # Step 1: Initial detection -> should trigger reboot
        action, msg = handle_stock_firmware_recovery(
            host="192.168.100.26",
            miner_name="S19JPRO-26",
            config=config,
            send_telegram_fn=mock_send_tg,
            now_ts=1000.0,
        )
        assert action is True
        assert "reinicio" in msg.lower()
        time.sleep(0.1)
        assert mock_reboot.called

        # In cooldown:
        action_cd, _ = handle_stock_firmware_recovery(
            host="192.168.100.26",
            miner_name="S19JPRO-26",
            config=config,
            now_ts=1050.0,
        )
        assert action_cd is False

        # Step 2: After cooldown, if still stock -> should trigger reflash
        action_flash, msg_flash = handle_stock_firmware_recovery(
            host="192.168.100.26",
            miner_name="S19JPRO-26",
            config=config,
            send_telegram_fn=mock_send_tg,
            now_ts=1350.0,
        )
        assert action_flash is True
        assert "flasheo" in msg_flash.lower()
        time.sleep(0.1)
        assert mock_flash.called
