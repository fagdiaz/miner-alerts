"""
Unit and Integration Tests for Spec 084: Governance Dashboard (`/directivas`).

Validates:
1. SQLite EventStore DDL, indices, snapshot persistence, querying, and retention pruning.
2. Recovery cooling deadlock detection logic (`evaluate_recovery_deadlock`).
3. Strict Mobile-First card formatting (every line <= 32 columns).
4. DirectivesCommand Telegram routing, aliases, authorization, and dispatch.
"""

import time
from typing import Any, Dict, List
import pytest

from app.core.event_store import EventStore
from app.governance.directives_dashboard import (
    GovernanceSnapshot,
    evaluate_recovery_deadlock,
    build_fleet_directives_card,
    build_miner_directive_card,
    build_deadlock_alert_text,
)
from app.governance.governance_context import MinerGovernanceContext
from app.telegram.commands.directives import DirectivesCommand
from app.telegram.context import TelegramRequestContext
from app.telegram.router import create_default_command_router


def test_event_store_governance_snapshots(tmp_path):
    """Test EventStore DDL, snapshot recording, query filtering, and retention pruning."""
    db_file = tmp_path / "test_miner_alerts.db"
    store = EventStore(db_file)
    assert store.available is True

    now = time.time()
    ok = store.record_governance_snapshot(
        miner_name="S19JPRO-24",
        fan_action="ACTION_HOLD_TARGET",
        fan_duty=92,
        target_power_w=2700,
        current_power_w=2698.5,
        chip_temp_c=68.2,
        fga_cohort="COOL",
        fga_r_th=0.019,
        elevator_group="elevator_1",
        elevator_gate_status="GATE_OK",
        solar_envelope_active=False,
        contingency_mode="VALLE (5400W)",
        restart_required=False,
        is_deadlocked=False,
        details={"test_key": "val1"},
        created_ts=now,
    )
    assert ok is True

    # Record second snapshot for different miner
    store.record_governance_snapshot(
        miner_name="S19JPRO-25",
        fan_action="ACTION_RECOVERY_MAX_COOLING",
        fan_duty=100,
        target_power_w=2700,
        current_power_w=2495.0,
        chip_temp_c=74.5,
        fga_cohort="STANDARD",
        fga_r_th=0.022,
        elevator_group="elevator_2",
        elevator_gate_status="DEADLOCKED",
        solar_envelope_active=True,
        contingency_mode="PICO (5000W)",
        restart_required=True,
        is_deadlocked=True,
        details={"note": "cooling_trap"},
        created_ts=now + 1.0,
    )

    # Query all
    all_snaps = store.get_recent_governance_snapshots(limit=10)
    assert len(all_snaps) == 2
    assert all_snaps[0]["miner_name"] == "S19JPRO-25"
    assert all_snaps[0]["is_deadlocked"] == 1
    assert all_snaps[0]["restart_required"] == 1
    assert all_snaps[1]["miner_name"] == "S19JPRO-24"
    assert all_snaps[1]["is_deadlocked"] == 0

    # Query filtered by miner
    m24_snaps = store.get_recent_governance_snapshots(miner_name="S19JPRO-24", limit=10)
    assert len(m24_snaps) == 1
    assert m24_snaps[0]["miner_name"] == "S19JPRO-24"
    assert m24_snaps[0]["fan_action"] == "ACTION_HOLD_TARGET"

    # Test count_rows
    assert store.count_rows("governance_snapshots") == 2

    # Test prune_governance_snapshots directly
    deleted = store.prune_governance_snapshots(cutoff_ts=now + 100_000)
    assert deleted == 2
    assert store.count_rows("governance_snapshots") == 0

    # Also test store.prune deletes governance snapshots while maintaining 5-key backwards compatibility
    store.record_governance_snapshot(
        miner_name="S19JPRO-24",
        fan_action="ACTION_HOLD_TARGET",
        fan_duty=92,
        target_power_w=2700,
        current_power_w=2698.5,
        chip_temp_c=68.2,
        fga_cohort="COOL",
        fga_r_th=0.019,
        elevator_group="elevator_1",
        elevator_gate_status="GATE_OK",
        solar_envelope_active=False,
        contingency_mode="VALLE (5400W)",
        restart_required=False,
        is_deadlocked=False,
        details={},
        created_ts=now,
    )
    assert store.count_rows("governance_snapshots") == 1
    prune_res = store.prune(
        now_ts=now + 100_000,
        sample_retention_days=1,
        event_retention_days=1,
        decision_retention_days=1,
    )
    assert "samples" in prune_res
    assert store.count_rows("governance_snapshots") == 0


def test_evaluate_recovery_deadlock():
    """Verify deadlock condition detection and warming up exception."""
    now = 1000.0

    # 1. No recovery cooling action
    assert evaluate_recovery_deadlock("ACTION_HOLD_TARGET", now - 400.0, now) is False
    assert evaluate_recovery_deadlock("ACTION_STEP_DOWN", now - 400.0, now) is False

    # 2. Recovery cooling action but under threshold (e.g. 150s <= 300s)
    assert evaluate_recovery_deadlock("ACTION_RECOVERY_MAX_COOLING", now - 150.0, now) is False

    # 3. Recovery cooling action with no timestamp recorded
    assert evaluate_recovery_deadlock("ACTION_RECOVERY_MAX_COOLING", None, now) is False

    # 4. Warming up suppresses deadlock
    assert evaluate_recovery_deadlock("ACTION_RECOVERY_MAX_COOLING", now - 500.0, now, is_warming_up=True) is False

    # 5. Deadlock condition met (>300s continuous recovery cooling)
    assert evaluate_recovery_deadlock("ACTION_RECOVERY_MAX_COOLING", now - 301.0, now, is_warming_up=False) is True
    assert evaluate_recovery_deadlock("ACTION_RECOVERY_MAX_COOLING", now - 600.0, now, is_warming_up=False) is True


def test_fleet_directives_card_formatting_max_32_cols():
    """Verify fleet overview card strictly respects <= 32 cols per line across all states."""
    now = 10_000.0
    contexts = [
        MinerGovernanceContext(
            miner_name="S19JPRO-23",
            current_power_w=2698.0,
            target_power_w=2700,
            fan_duty=92,
            fan_action="ACTION_HOLD_TARGET",
            chip_temp_c=78.5,
            inlet_temp_c=24.0,
            fga_cohort="STANDARD",
            fga_thermal_resistance=0.021,
            electrical_group="elevator_1",
            is_stock_firmware=False,
            restart_required=False,
            recovery_since_ts=None,
            is_warming_up=False,
        ),
        MinerGovernanceContext(
            miner_name="S19JPRO-24",
            current_power_w=2495.0,
            target_power_w=2700,
            fan_duty=100,
            fan_action="ACTION_RECOVERY_MAX_COOLING",
            chip_temp_c=69.0,
            inlet_temp_c=24.0,
            fga_cohort="COOL",
            fga_thermal_resistance=0.019,
            electrical_group="elevator_1",
            is_stock_firmware=False,
            restart_required=True,
            recovery_since_ts=now - 350.0,  # Deadlocked
            is_warming_up=False,
        ),
        MinerGovernanceContext(
            miner_name="S19JPRO-25",
            current_power_w=2699.0,
            target_power_w=2700,
            fan_duty=92,
            fan_action="ACTION_STEP_DOWN",
            chip_temp_c=79.2,
            inlet_temp_c=25.0,
            fga_cohort="STANDARD",
            fga_thermal_resistance=0.022,
            electrical_group="elevator_2",
            is_stock_firmware=False,
            restart_required=False,
            recovery_since_ts=None,
            is_warming_up=False,
        ),
        MinerGovernanceContext(
            miner_name="S19JPRO-26",
            current_power_w=2699.0,
            target_power_w=2700,
            fan_duty=92,
            fan_action="ACTION_HOLD_DWELL",
            chip_temp_c=77.8,
            inlet_temp_c=25.0,
            fga_cohort="STANDARD",
            fga_thermal_resistance=0.021,
            electrical_group="elevator_2",
            is_stock_firmware=False,
            restart_required=False,
            recovery_since_ts=None,
            is_warming_up=True,
        ),
    ]

    card = build_fleet_directives_card(
        contexts,
        elevator_states={"elevator_1": 5193.0, "elevator_2": 5398.0},
        solar_active=True,
        now_ts=now,
    )

    for i, line in enumerate(card.splitlines(), start=1):
        assert len(line) <= 32, f"Line {i} exceeds 32 chars ({len(line)}): '{line}'"

    assert "DIRECTIVAS DE GOBERNANZA" in card
    assert "M23" in card
    assert "M24" in card
    assert "DEADLOCK: ⚠️ M24" in card
    assert "SOLAR: ACTIVO" in card


def test_miner_directive_card_formatting_max_32_cols():
    """Verify detailed miner directive card strictly respects <= 32 cols across all 5 layers."""
    now = 10_000.0
    ctx = MinerGovernanceContext(
        miner_name="S19JPRO-24",
        current_power_w=2698.0,
        target_power_w=2700,
        fan_duty=92,
        fan_action="ACTION_HOLD_TARGET",
        chip_temp_c=68.2,
        inlet_temp_c=24.0,
        fga_cohort="COOL",
        fga_thermal_resistance=0.0195,
        electrical_group="elevator_1",
        configured_preset="2700W",
        is_stock_firmware=False,
        restart_required=False,
        recovery_since_ts=None,
        is_warming_up=False,
    )

    card = build_miner_directive_card(
        ctx,
        elevator_group="elevator_1",
        elevator_gate_status="GATE_OK",
        solar_active=False,
        is_deadlocked=False,
        deadlock_duration_s=0.0,
        contingency_mode="VALLE (5400W)",
        now_ts=now,
    )

    for i, line in enumerate(card.splitlines(), start=1):
        assert len(line) <= 32, f"Line {i} exceeds 32 chars ({len(line)}): '{line}'"

    assert "P0: SEGURIDAD HARDWARE" in card
    assert "P1: FIRMWARE & REINICIO" in card
    assert "P2: ELEVADOR & AMBIENTE" in card
    assert "P3: AGENTE DE PLANTA (FGA)" in card
    assert "P4: ESTADO FIRMWARE" in card
    assert "Estado: ✅ NOMINAL" in card


def test_deadlock_alert_formatting_max_32_cols():
    """Verify proactive deadlock alert message strictly respects <= 32 cols."""
    alert_text = build_deadlock_alert_text(
        miner_name="S19JPRO-24",
        current_power_w=2495.0,
        target_power_w=2700.0,
        duration_seconds=312.0,
    )

    for i, line in enumerate(alert_text.splitlines(), start=1):
        assert len(line) <= 32, f"Alert line {i} exceeds 32 chars ({len(line)}): '{line}'"

    assert "⚠️ ALERTA DE GOBERNANZA" in alert_text
    assert "S19JPRO-24" in alert_text
    assert "312s (>300s)" in alert_text


class DummyState:
    def __init__(self, name: str, host: str, pwr: float = 2700.0, chip_t: float = 75.0, action: str = "ACTION_HOLD_TARGET"):
        self.miner_name = name
        self.host = host
        self.governor_last_power_w = pwr
        self.governor_duty = 92
        self.governor_last_action = action
        self.governor_last_temp_c = chip_t
        self.last_temp_c = chip_t
        self.inlet_temp_c = 24.0
        self.balancer_preset = "2700W"
        self.rate_ths = 100.0
        self.vnish_restart_required = False
        self.governor_recovery_since_ts = None
        self.is_shutdown_maintenance = False
        self.last_elapsed = 1500


def test_directives_command_router_dispatch():
    """Verify DirectivesCommand registration and dispatch via TelegramCommandRouter."""
    router = create_default_command_router()
    handler = router.find_handler("directivas")
    assert handler is not None
    assert isinstance(handler, DirectivesCommand)
    assert router.find_handler("gov_status") is handler
    assert router.find_handler("directives") is handler
    assert router.find_handler("directiva") is handler

    # Setup dummy context
    sent_messages = []

    def fake_send(text, **kwargs):
        sent_messages.append((text, kwargs))
        return True

    miners = [
        {"name": "S19JPRO-23", "host": "192.168.1.23", "port": 4028, "electrical_group": "elevator_1"},
        {"name": "S19JPRO-24", "host": "192.168.1.24", "port": 4028, "electrical_group": "elevator_1"},
    ]
    states = {
        "S19JPRO-23|192.168.1.23:4028": DummyState("S19JPRO-23", "192.168.1.23"),
        "S19JPRO-24|192.168.1.24:4028": DummyState("S19JPRO-24", "192.168.1.24"),
    }

    from pathlib import Path
    import threading
    req_context = TelegramRequestContext(
        bot_token="fake_token",
        chat_id="123456",
        config={},
        miners=miners,
        states=states,
        state_lock=threading.RLock(),
        state_path=Path("state.json"),
        current_last_update_id=1,
        hashcore_cfg={},
        event_store=None,
        qa_mode=True,
        qa_allow_actions=False,
        token_registry={},
    )
    req_context.send_message = fake_send

    # 1. Authorization rejection
    assert handler.check_authorization(req_context, "999999") is False
    unauth = router.dispatch("directivas", [], req_context, from_id="999999")
    assert unauth is True
    assert len(sent_messages) == 0

    # 2. Authorized fleet overview
    ok = router.dispatch("directivas", [], req_context, from_id="123456", update_id=101)
    assert ok is True
    assert len(sent_messages) == 1
    fleet_msg = sent_messages[-1][0]
    assert "DIRECTIVAS DE GOBERNANZA" in fleet_msg
    assert "M23" in fleet_msg
    assert "M24" in fleet_msg

    # 3. Authorized drill-down for miner 24 via alias directives
    ok_m24 = router.dispatch("directives", ["24"], req_context, from_id="123456", update_id=102)
    assert ok_m24 is True
    m24_msg = sent_messages[-1][0]
    assert "DIRECTIVAS: S19JPRO-24" in m24_msg
    assert "P0: SEGURIDAD HARDWARE" in m24_msg

    # 4. Unknown miner query
    ok_unk = router.dispatch("gov_status", ["99"], req_context, from_id="123456", update_id=103)
    assert ok_unk is True
    unk_msg = sent_messages[-1][0]
    assert "no existe" in unk_msg
