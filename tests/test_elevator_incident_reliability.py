import pytest
from unittest.mock import Mock

from app.governance.correlated_restarts import RestartCorrelation
from app.governance import firmware_recovery as recovery


MINERS = [dict(name=str(n), electrical_group='e1' if n < 25 else 'e2')
          for n in range(23, 27)]


def test_shared_restart_in_same_tick_or_adjacent_tick():
    c = RestartCorrelation()
    assert c.observe(MINERS, ['25'], 1000) == []
    assert c.observe(MINERS, ['26'], 1030) == [('e2', ['25', '26'])]
    assert c.observe(MINERS, [], 1060) == []
    assert RestartCorrelation().observe(MINERS, ['25', '26'], 1000) == [('e2', ['25', '26'])]


def test_unrelated_restart_or_other_group_cannot_form_cascade():
    c = RestartCorrelation()
    assert c.observe(MINERS, ['23', '25'], 1000) == []
    assert c.observe(MINERS, ['26'], 1060) == []


def test_each_group_keeps_first_alert_and_has_independent_cooldown():
    c = RestartCorrelation()
    assert c.observe(MINERS, ['25', '26'], 1000)
    assert not c.observe(MINERS, ['25', '26'], 1030)
    assert c.observe(MINERS, ['23', '24'], 1040) == [('e1', ['23', '24'])]
    assert c.observe(MINERS, ['25', '26'], 1900) == [('e2', ['25', '26'])]


def test_disabled_or_removed_miners_do_not_accumulate_state():
    c = RestartCorrelation()
    c.observe(MINERS, ['25', '26', 'unknown'], 1000)
    assert c.observe(MINERS[:2], ['unknown'], 1060) == []
    assert c.recent == {} and c.notified == {}


@pytest.mark.parametrize('boards,flag,expected', [
    (None, False, False), (None, True, True),
    (3, False, False), (2, False, True), (0, False, True), (-1, False, False),
])
def test_missing_telemetry_never_triggers_stock_probe(boards, flag, expected):
    assert recovery.stock_recovery_candidate(boards, flag) is expected


@pytest.mark.parametrize('attempts', [0, 1])
@pytest.mark.parametrize('notify', [False, True])
def test_qa_cannot_launch_reboot_or_flash(monkeypatch, attempts, notify):
    monkeypatch.setattr(recovery, '_RECOVERY_ATTEMPTS', {'test': attempts})
    thread = Mock(side_effect=AssertionError('QA launched actuator'))
    monkeypatch.setattr(recovery.threading, 'Thread', thread)
    taken, reason = recovery.handle_stock_firmware_recovery(
        'test', 'miner', {}, qa_mode=True, qa_notify=notify, now_ts=10000)
    assert not taken and reason == 'blocked_by_qa'
    thread.assert_not_called()


def test_disabled_reflash_cannot_launch_actuator(monkeypatch):
    monkeypatch.setattr(recovery, '_RECOVERY_ATTEMPTS', {'test': 1})
    monkeypatch.setattr(recovery, '_ACTIVE_RECOVERY_HOSTS', set())
    monkeypatch.setattr(recovery, '_LAST_RECOVERY_TS', {})
    thread = Mock(side_effect=AssertionError('Disabled flash launched'))
    monkeypatch.setattr(recovery.threading, 'Thread', thread)
    taken, _ = recovery.handle_stock_firmware_recovery(
        'test', 'miner', {'stock_firmware_reflash_enabled': False}, now_ts=10000)
    assert not taken
    thread.assert_not_called()


def test_balancer_simulation_cannot_forge_applied_state_or_send_success(monkeypatch):
    import threading
    from app import miner_monitor as mm
    from app.core.models import MinerState
    from app.governance.balancer_cycle import execute_balancer_cycle
    from app.governance.preset_balancer import StabilityMetrics
    from app.governance.elevator_budget import FacilityBudgetState
    state = MinerState(balancer_preset='2700W', last_preset_change_ts=123.0)
    miner = dict(name='test', host='test.invalid', port=4028, electrical_group='e1')
    metric = StabilityMetrics('test', 'e1', '2700W', 0, 0, 50,
                              hw_errors_delta_10m=350, hw_error_rate_pct=2.5)
    monkeypatch.setattr(mm, 'extract_miner_stability_metrics', Mock(return_value=[metric]))
    monkeypatch.setattr(mm, 'refresh_vnish_overclock_settings', Mock())
    facility = FacilityBudgetState()
    monkeypatch.setattr(mm, '_FACILITY_BUDGET_STATE', facility)
    actuator, sender = Mock(), Mock()
    monkeypatch.setattr(mm, 'safe_set_miner_preset', actuator)
    decisions = execute_balancer_cycle(
        miners=[miner], states={'test|test.invalid:4028': state},
        state_lock=threading.Lock(), config={'preset_balancer_dry_run': True},
        now_ts=1000000, qa_mode=False, force=True,
        send_telegram_fn=sender, bot_token='fake', chat_id='fake',
    )
    assert decisions[0][1].target_preset == '2500W'
    assert state.balancer_preset == '2700W'
    assert state.last_preset_change_ts == 123.0
    assert state.hw_error_lock_until_ts is None
    assert state.hw_error_locked_preset is None
    assert facility.last_facility_transition_ts == 0
    actuator.assert_not_called()
    sender.assert_not_called()
