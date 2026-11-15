"""Regression proofs for the November heat incident; no hardware or Telegram I/O."""
import pytest

from tests.test_emergency_thermal_guard import TestProcessEmergencyThermalGuard
from app.governance.thermal_guard import (
    evaluate_emergency_thermal_action, process_emergency_thermal_guard,
    ACTION_PAUSED_COOLING,
)


@pytest.fixture
def rig():
    r = TestProcessEmergencyThermalGuard()
    r.setUp()
    return r


def run(r, temp=86, now=10000, **kwargs):
    return process_emergency_thermal_guard(
        r.miner, r.state, temp, r.config, now, "test-password",
        safe_set_preset_fn=r.mock_set_preset,
        safe_stop_fn=r.mock_stop_mining,
        safe_resume_fn=r.mock_resume_mining,
        safe_set_fan_fn=r.mock_set_fan,
        send_telegram_fn=r.mock_send_tg, log_fn=r.mock_log,
        bot_token="fake", chat_id="fake", **kwargs,
    )


@pytest.mark.parametrize("preset,target", [
    ("2300", "2150"), ("2150W", "2000"), ("2000", "1850"),
    ("1850", "1800"), ("1800", "1740"), ("1740", "1740"),
])
def test_recovery_never_upsteps_or_uses_nonexistent_preset(preset, target):
    for paused, temp in [(None, 86), (1, 70)]:
        decision = evaluate_emergency_thermal_action(
            temp, preset, thermal_pause_until_ts=paused, now_ts=10000)
        assert decision.target_preset == target


def test_failed_downstep_keeps_observed_preset_and_reports_failure(rig):
    rig.mock_set_preset.return_value = (False, "http_status_400")
    run(rig)
    assert rig.state.balancer_preset == "2700"
    assert rig.state.vnish_discovered_preset is None
    assert "falló" in rig.mock_send_tg.call_args.args[2]
    rig.mock_set_fan.assert_called_once()


@pytest.mark.parametrize("failure", ["preset", "resume"])
def test_failed_recovery_remains_paused_and_never_claims_success(rig, failure):
    rig.state.thermal_pause_until_ts = 1
    if failure == "preset":
        rig.mock_set_preset.return_value = (False, "http_status_400")
    else:
        rig.mock_resume_mining.return_value = (False, "timeout")
    assert run(rig, temp=70) == ACTION_PAUSED_COOLING
    assert rig.state.thermal_pause_until_ts > 10000
    assert rig.state.balancer_preset == "2700"
    if failure == "preset":
        rig.mock_resume_mining.assert_not_called()
    assert "falló" in rig.mock_send_tg.call_args.args[2]


def test_failed_stop_is_not_recorded_as_successful_pause(rig):
    rig.mock_stop_mining.return_value = (False, "timeout")
    run(rig, temp=88)
    assert rig.state.thermal_pause_until_ts is None
    assert "falló" in rig.mock_send_tg.call_args.args[2]


def test_notification_cooldown_does_not_suppress_new_critical_event(rig):
    run(rig)
    run(rig, now=10200)
    assert rig.mock_send_tg.call_count == 1
    run(rig, temp=88, now=10230)
    assert rig.mock_send_tg.call_count == 2
    assert "PAUSA FORZADA" in rig.mock_send_tg.call_args.args[2]


def test_qa_recovery_cannot_touch_hardware(rig):
    rig.state.thermal_pause_until_ts = 1
    run(rig, temp=70, qa_mode=True)
    rig.mock_set_preset.assert_not_called()
    rig.mock_resume_mining.assert_not_called()
    rig.mock_set_fan.assert_not_called()


def test_observed_preset_wins_over_dry_balancer_state(rig):
    rig.state.vnish_discovered_preset = "2150"
    rig.state.governor_last_power_w = 2148
    run(rig)
    assert rig.mock_set_preset.call_args.args[2] == "2000"


def test_default_recovery_loads_pending_settings_before_claiming_success(rig, monkeypatch):
    # VNish resume/start leaves newly saved overclock settings pending; a mining
    # process restart is required after the confirmed thermal stop.
    from app.vnish import client
    rig.state.thermal_pause_until_ts = 1
    monkeypatch.setattr(client, "safe_restart_mining", rig.mock_resume_mining)
    plain_resume = rig.mock_stop_mining
    monkeypatch.setattr(client, "safe_resume_mining", plain_resume)
    process_emergency_thermal_guard(
        rig.miner, rig.state, 70, rig.config, 10000, "test-password",
        safe_set_preset_fn=rig.mock_set_preset,
        safe_set_fan_fn=rig.mock_set_fan,
        send_telegram_fn=rig.mock_send_tg, log_fn=rig.mock_log,
    )
    rig.mock_resume_mining.assert_called_once()
    plain_resume.assert_not_called()
    assert rig.state.thermal_pause_until_ts is None


@pytest.mark.parametrize('stored,watts,target', [
    ('2000', 2498, '2300'), ('2500', 2298, '2150'), ('2300', 2148, '2000'),
])
def test_active_watts_take_precedence_over_configured_preset(stored, watts, target):
    decision = evaluate_emergency_thermal_action(86, stored, watts, now_ts=10000)
    assert decision.target_preset == target


def test_resume_retains_measured_tier_across_pause_and_persistence(rig, tmp_path):
    from app.core.state_manager import save_state, load_state
    rig.state.governor_last_power_w = 2498
    rig.state.vnish_discovered_preset = '2000'
    run(rig, temp=88)
    assert rig.state.thermal_resume_preset == '2300'
    path = tmp_path / 'state.json'
    save_state(path, {'test': rig.state}, last_update_id=0)
    restored, _ = load_state(path)
    rig.state = restored['test']
    rig.state.governor_last_power_w = 0
    run(rig, temp=70, now=10100)
    assert rig.mock_set_preset.call_args.args[2] == '2300'
    assert rig.state.thermal_resume_preset is None


@pytest.mark.parametrize('hint,cap,target', [('junk', '2500W', '1740'),
                                          ('2300', '2000W', '2000')])
def test_resume_hint_is_validated_and_bounded_by_configured_ceiling(hint, cap, target):
    decision = evaluate_emergency_thermal_action(
        70, '2000', 0, thermal_pause_until_ts=1, now_ts=10000,
        thermal_resume_preset=hint, max_hardware_preset=cap)
    assert decision.target_preset == target
