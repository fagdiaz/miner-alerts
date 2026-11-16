"""Incident regressions: native power switching must not trigger generic restarts."""

import pytest
from unittest.mock import patch
from types import SimpleNamespace
import threading

from app.core.restart_intelligence import (
    evaluate_auto_restart_candidate, _async_execute_mining_restart,
    _async_execute_preset_restart, evaluate_preset_restart_candidate,
)
from app.core.engine import ActuatorHook
from app.core.models import MinerState


def candidate(**overrides):
    values = dict(
        now_ts=2000.0, responded=True, rate_ths=90.0, threshold_ths=60.0,
        active_boards=3, expected_boards=3, miner_state="mining",
        restart_required=True, reboot_required=False, auto_restart_enabled=True,
        last_auto_restart_ts=None, auto_restart_cooldown_seconds=300.0,
        auto_restart_count=0, max_retries_before_reboot=3, elapsed=5000,
    )
    values.update(overrides)
    return evaluate_auto_restart_candidate(**values)


def test_m24_healthy_pending_flag_defers_to_preset_watchdog():
    assert candidate()[:2] == (False, "handled_by_preset_watchdog")


@pytest.mark.parametrize("state", ["auto-tuning", "auto_tuning", "autotuning", "tuning"])
def test_native_autotune_is_not_a_generic_recovery_trigger(state):
    assert candidate(miner_state=state, rate_ths=0.0, active_boards=0)[:2] == (
        False, "transient_starting",
    )


def test_real_stopped_miner_remains_recoverable():
    assert candidate(miner_state="stopped", rate_ths=0.0, active_boards=0)[0]


def make_hook_case(qa=False, degraded=False, pending=True):
    state = MinerState(
        state="LOW" if degraded else "OK", vnish_restart_required=pending,
        vnish_restart_detected_ts=1000.0, low_since_ts=500.0 if degraded else None,
    )
    lock = threading.RLock()
    ctx = SimpleNamespace(
        config={"startup_guard_seconds": 1, "low_sustained_seconds": 1},
        state_lock=lock, event_store=None, bot_token="", chat_id="",
        qa_mode=qa, qa_allow_actions=False, qa_notify=False,
        threshold_ths=60.0, hashcore_cfg={},
    )
    miner = {"name": "M24", "host": "test.invalid", "port": 4028}
    result = dict(
        miner=miner, state=state, responded=True, rate_ths=0.0 if degraded else 90.0,
        elapsed=5000, active_boards=0 if degraded else 3,
        vnish_telemetry=SimpleNamespace(max_temp_c=70.0), quality_telemetry=None,
    )
    tick = {"miner_results": {"M24|test.invalid:4028": result}, "process_start_ts": 1.0}
    return ctx, state, tick


@pytest.mark.parametrize("state", ["auto-tuning", "initializing"])
def test_hook_uses_real_native_state_and_blocks_both_restart_levels(state):
    ctx, st, tick = make_hook_case(degraded=True)
    with patch("app.vnish.client.get_miner_status", return_value=(True, {
        "miner_state": state, "restart_required": True,
    }, None)), patch("app.core.engine.threading.Thread") as thread, patch(
        "app.core.system.run_hashcore_cli"
    ) as reboot:
        ActuatorHook().execute(ctx, 1, 2000.0, tick)
    thread.assert_not_called()
    reboot.assert_not_called()
    assert st.last_auto_restart_ts is None


def test_hook_clears_stale_pending_flag_without_dispatch():
    ctx, st, tick = make_hook_case()
    with patch("app.vnish.client.get_miner_status", return_value=(True, {
        "miner_state": "mining", "restart_required": False,
    }, None)), patch("app.core.engine.threading.Thread") as thread:
        ActuatorHook().execute(ctx, 1, 2000.0, tick)
    thread.assert_not_called()
    assert not st.vnish_restart_required
    assert st.vnish_restart_detected_ts is None


def test_hook_live_http_is_outside_state_lock():
    ctx, st, tick = make_hook_case()
    def status(*args, **kwargs):
        assert not ctx.state_lock._is_owned()
        return True, {"miner_state": "mining", "restart_required": True}, None
    with patch("app.vnish.client.get_miner_status", side_effect=status), patch(
        "app.core.engine.threading.Thread"
    ) as thread:
        ActuatorHook().execute(ctx, 1, 2000.0, tick)
    # Only the preset path may run; generic L1 cannot create a second thread.
    assert thread.call_count == 1
    assert thread.call_args.kwargs["target"] is _async_execute_preset_restart


def test_failed_status_read_cannot_dispatch_l1():
    ctx, st, tick = make_hook_case()
    with patch("app.vnish.client.get_miner_status", return_value=(False, None, "timeout")), patch(
        "app.core.engine.threading.Thread"
    ) as thread:
        ActuatorHook().execute(ctx, 1, 2000.0, tick)
    thread.assert_not_called()


def test_hook_qa_has_no_restart_thread():
    ctx, st, tick = make_hook_case(qa=True)
    with patch("app.vnish.client.get_miner_status", return_value=(True, {
        "miner_state": "mining", "restart_required": True,
    }, None)), patch("app.core.engine.threading.Thread") as thread:
        ActuatorHook().execute(ctx, 1, 2000.0, tick)
    thread.assert_not_called()


def test_real_l1_dispatch_does_not_also_reboot():
    ctx, st, tick = make_hook_case(degraded=True)
    with patch("app.vnish.client.get_miner_status", return_value=(True, {
        "miner_state": "stopped", "restart_required": False,
    }, None)), patch("app.core.engine.threading.Thread") as thread, patch(
        "app.core.system.run_hashcore_cli"
    ) as reboot:
        ActuatorHook().execute(ctx, 1, 2000.0, tick)
    assert thread.call_count == 1
    assert thread.call_args.kwargs["target"] is _async_execute_mining_restart
    reboot.assert_not_called()


@pytest.mark.parametrize("worker", [_async_execute_mining_restart, _async_execute_preset_restart])
@pytest.mark.parametrize("blocker", ["qa", "governance"])
def test_workers_enforce_qa_and_governance_before_io(worker, blocker):
    from app.governance.intervention_policy import InterventionGovernance
    args = dict(
        host="test.invalid", password="", miner_name="M24", miner_dict={},
        bot_token="", chat_id="", qa_mode=blocker == "qa", qa_notify=False, event_store=None,
    )
    if worker is _async_execute_mining_restart:
        args.update(trigger_reason="zero_hashrate", attempt=1, max_attempts=3)
    else:
        args.update(target_preset="2300")
    with patch("app.governance._orchestrator_state.get_intervention_gov", return_value=(
        InterventionGovernance(reboots_enabled=False) if blocker == "governance" else None
    )), patch("app.vnish.client.safe_restart_mining") as restart, patch(
        "app.miner_monitor.safe_restart_mining"
    ) as mm_restart, patch("app.vnish.client.get_miner_status") as status, patch(
        "app.miner_monitor.safe_set_miner_preset"
    ) as preset:
        worker(**args)
    restart.assert_not_called()
    mm_restart.assert_not_called()
    status.assert_not_called()
    preset.assert_not_called()


def preset_worker():
    _async_execute_preset_restart(
        host="test.invalid", password="", miner_name="M24", miner_dict={},
        target_preset="2300", bot_token="", chat_id="", qa_mode=False,
        qa_notify=False, event_store=None,
    )


@pytest.mark.parametrize("status", [
    {"miner_state": "mining", "restart_required": False},
    {"miner_state": "auto-tuning", "restart_required": True},
    {"miner_state": "mining", "restart_required": True, "reboot_required": True},
])
def test_preset_worker_revalidates_pending_state(status):
    with patch("app.governance._orchestrator_state.get_intervention_gov", return_value=None), patch(
        "app.vnish.client.get_miner_status", return_value=(True, status, None)
    ), patch("app.vnish.client.safe_restart_mining") as restart:
        preset_worker()
    restart.assert_not_called()


@pytest.mark.parametrize("temp", [None, 80, 86, float("nan")])
def test_preset_worker_revalidates_temperature(temp):
    with patch("app.governance._orchestrator_state.get_intervention_gov", return_value=None), patch(
        "app.vnish.client.get_miner_status", return_value=(True, {
            "miner_state": "mining", "restart_required": True,
        }, None)
    ), patch("app.vnish.client.read_miner_status_summary", return_value=(True, {
        "miner_state": "mining", "hr_realtime_ths": 90, "chip_temp": {"max": temp},
    }, None)), patch("app.vnish.client.safe_restart_mining") as restart:
        preset_worker()
    restart.assert_not_called()


def test_recovery_preclamp_preserves_native_ceiling():
    with patch("app.governance._orchestrator_state.get_intervention_gov", return_value=None), patch(
        "app.miner_monitor.safe_set_miner_preset", return_value=(True, None)
    ) as preset, patch("app.miner_monitor.safe_restart_mining", return_value=(True, None)), patch(
        "app.miner_monitor.send_telegram"
    ), patch("app.miner_monitor.record_action_outcome"), patch("time.sleep"):
        _async_execute_mining_restart(
            host="test.invalid", password="", miner_name="M24",
            miner_dict={"max_hardware_preset": "2700W"}, trigger_reason="zero_hashrate",
            attempt=1, max_attempts=3, bot_token="", chat_id="", qa_mode=False,
            qa_notify=False, event_store=None,
        )
    assert preset.call_args.kwargs == {"clamp_top_preset": False}


def test_preset_watchdog_requires_temperature_evidence():
    assert evaluate_preset_restart_candidate(
        now_ts=2000, vnish_restart_required=True, is_hash_degraded=False,
        is_warming_up=False, max_chip_temp_c=None, detected_ts=1000, last_restart_ts=None,
    ) == (False, "temperature_unavailable")


def test_native_tuning_also_blocks_l2_when_l1_disabled():
    ctx, st, tick = make_hook_case(degraded=True)
    ctx.config["auto_restart_mining_enabled"] = False
    with patch("app.vnish.client.get_miner_status", return_value=(True, {
        "miner_state": "auto-tuning", "restart_required": False,
    }, None)), patch("app.core.system.run_hashcore_cli") as reboot:
        ActuatorHook().execute(ctx, 1, 2000.0, tick)
    reboot.assert_not_called()


def test_valid_preset_watchdog_still_applies_pending_settings():
    with patch("app.governance._orchestrator_state.get_intervention_gov", return_value=None), patch(
        "app.vnish.client.get_miner_status", return_value=(True, {
            "miner_state": "mining", "restart_required": True,
        }, None)
    ), patch("app.vnish.client.read_miner_status_summary", return_value=(True, {
        "miner_state": "mining", "hr_realtime_ths": 90, "chip_temp": {"max": 70},
    }, None)), patch("app.vnish.client.safe_restart_mining", return_value=(True, None)) as restart, patch(
        "app.telegram.sender.send_telegram"
    ), patch("app.miner_monitor.record_action_outcome"):
        preset_worker()
    restart.assert_called_once()


def test_governance_change_during_fresh_read_prevents_restart():
    from app.governance.intervention_policy import InterventionGovernance
    with patch("app.governance._orchestrator_state.get_intervention_gov", side_effect=[
        None, InterventionGovernance(reboots_enabled=False),
    ]), patch("app.vnish.client.get_miner_status", return_value=(True, {
        "miner_state": "mining", "restart_required": True,
    }, None)), patch("app.vnish.client.read_miner_status_summary", return_value=(True, {
        "miner_state": "mining", "hr_realtime_ths": 90, "chip_temp": {"max": 70},
    }, None)), patch("app.vnish.client.safe_restart_mining") as restart:
        preset_worker()
    restart.assert_not_called()


@pytest.mark.parametrize("guard", ["is_shutdown_maintenance", "snooze_until_ts", "thermal_pause_until_ts", "last_thermal_downstep_ts"])
def test_hook_does_not_interrupt_maintenance_or_thermal_settling(guard):
    ctx, st, tick = make_hook_case(degraded=True)
    setattr(st, guard, True if guard == "is_shutdown_maintenance" else (
        1999.0 if guard == "last_thermal_downstep_ts" else 2100.0
    ))
    with patch("app.vnish.client.get_miner_status") as status, patch(
        "app.core.engine.threading.Thread"
    ) as thread, patch("app.core.system.run_hashcore_cli") as reboot:
        ActuatorHook().execute(ctx, 1, 2000.0, tick)
    status.assert_not_called()
    thread.assert_not_called()
    reboot.assert_not_called()
