"""Incident replay and transport contracts; all network calls are simulated."""

import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests

from app.core.engine import DetectionHook
from app.core.event_store import EventStore
from app.core.models import MinerState
from app.telegram import delivery, sender
from app.telegram.daily_digest import fetch_daily_digest_metrics, format_daily_digest
from app.telegram.fleet_cards import render_fleet_status_card
from app.telegram.transition_notices import TransitionNotices


def response(code=200, **body):
    return SimpleNamespace(status_code=code, json=lambda: body, text="redacted")


@pytest.mark.parametrize("failure", [requests.ConnectionError("SECRET"), requests.Timeout("SECRET"), response(503)])
def test_transient_failure_recovers_with_bounded_retry(monkeypatch, failure):
    sleeps, logs = [], []
    monkeypatch.setattr(delivery.time, "sleep", sleeps.append)
    ok = response(ok=True)
    session = Mock(post=Mock(side_effect=[failure, ok]))
    hb = Mock()
    assert delivery.post_message(session, "https://test.invalid", {}, log=logs.append, heartbeat=hb) is ok
    assert session.post.call_count == 2 and sleeps == [1.0]
    assert "SECRET" not in str(logs)
    assert hb.call_count >= 4


@pytest.mark.parametrize("reply", [response(400), response(403), response(200, ok=False), response(429, parameters={"retry_after": 31})])
def test_permanent_or_long_rate_limit_does_not_loop(monkeypatch, reply):
    sleep = Mock()
    monkeypatch.setattr(delivery.time, "sleep", sleep)
    session = Mock(post=Mock(return_value=reply))
    logs = []
    assert delivery.post_message(session, "url", {}, log=logs.append) is None
    assert session.post.call_count == 1
    sleep.assert_not_called()
    assert "DELIVERY_FAILED" in logs[-1]


def test_rate_limit_honors_delay_and_attempt_budget(monkeypatch):
    sleeps = []
    monkeypatch.setattr(delivery.time, "sleep", sleeps.append)
    session = Mock(post=Mock(return_value=response(429, parameters={"retry_after": 7})))
    assert delivery.post_message(session, "url", {}, log=lambda _: None) is None
    assert session.post.call_count == 3 and sum(sleeps) == 14


class StopWorker(BaseException):
    pass


def test_failed_message_does_not_poison_dedupe_and_commands_bypass_it(monkeypatch):
    item = (1000, "fake", "same", "STATUS", "test", None, None, None,
            False, None, None, "batch", 1, 1, None)
    command = (*item[:8], True, *item[9:])
    q = Mock()
    q.get.side_effect = [item, item, item, command, StopWorker()]
    q.qsize.return_value = 0
    post = Mock(side_effect=[None, response(ok=True), response(ok=True)])
    monkeypatch.setattr(sender, "post_message", post)
    monkeypatch.setattr(sender, "get_telegram_session", Mock())
    monkeypatch.setattr(sender, "_LAST_SENT_HASH", {})
    monkeypatch.setattr(sender, "_LAST_SENT_TS", {})
    monkeypatch.setattr(sender, "_LAST_ENQUEUED", {})
    monkeypatch.setattr(sender, "log", Mock())
    with pytest.raises(StopWorker):
        sender.telegram_sender_worker("fake", q, False)
    assert post.call_count == 3  # failure, successful retry of same content, command


def test_direct_fallback_uses_confirmed_transport(monkeypatch):
    post = Mock(return_value=None)
    monkeypatch.setattr(sender, "post_message", post)
    assert not sender._send_telegram_direct("fake", "fake", ["text"], dbg_update_id=None, dbg_cmd=None)
    assert post.call_count == 1


@pytest.mark.parametrize("until,expected", [(None, False), (999, False), (1000, False), (1001, True)])
def test_status_only_marks_active_snooze(monkeypatch, until, expected):
    monkeypatch.setattr("app.telegram.fleet_cards.time.time", lambda: 1000)
    text, _ = render_fleet_status_card({"test": MinerState(snooze_until_ts=until)})
    assert ("Silenciado" in text) is expected


def test_same_incident_alerts_each_severity_once_and_recovers():
    gate = TransitionNotices()
    states = ["LOW", "HASHBOARD", "LOW", "HASHBOARD", "LOW", "OK"]
    assert [gate.allow(s, 1000 + 30 * i) for i, s in enumerate(states)] == [True, True, False, False, False, True]
    assert gate.allow("LOW", 1200)
    assert gate.allow("OFFLINE", 1201)
    assert TransitionNotices().allow("LOW", 1201)  # another miner independent
    assert gate.allow("LOW", 1500)  # cooldown boundary


@pytest.mark.parametrize("snoozed,qa_mode,expected", [(False, False, 3), (True, False, 0), (False, True, 0)])
def test_detection_replay_keeps_history_but_limits_notifications(monkeypatch, snoozed, qa_mode, expected):
    send = Mock()
    monkeypatch.setattr(sender, "send_telegram", send)
    miner = dict(name="test", host="test.invalid", port=4028)
    state = MinerState(snooze_until_ts=2000 if snoozed else None)
    key = "test|test.invalid:4028"
    store = Mock(available=True)
    ctx = SimpleNamespace(miners=[miner], config={"chain_telemetry_enabled": False},
                          threshold_ths=60, state_lock=threading.Lock(), event_store=store,
                          bot_token="fake", chat_id="fake", qa_mode=qa_mode, qa_notify=False)
    result = dict(miner=miner, state=state, responded=True, rate_ths=0, elapsed=900,
                  previous_elapsed=899, reboot_reason="", active_boards=3, vnish_telemetry=None)
    tick = dict(states={key: state}, miner_results={key: result}, startup_grace_active=False)
    hook = DetectionHook()
    # Force the actual five transitions observed in Telegram, without modifying the FSM.
    transitions = ["LOW", "HASHBOARD", "LOW", "HASHBOARD", "LOW", "OK"]
    classify = Mock(side_effect=transitions)
    monkeypatch.setattr(DetectionHook, "classify_state", classify)
    for i in range(6):
        hook.execute(ctx, i, 1000 + 30 * i, tick)
    assert state.state == "OK"
    assert store.record_event.call_count == 6
    assert send.call_count == expected
    if expected:
        assert [c.args[3] for c in send.call_args_list] == ["LOW_HASHRATE", "HASHBOARD", "STATUS"]


def test_digest_counts_observations_separately_from_actions(tmp_path):
    store = EventStore(tmp_path / "events.db")
    try:
        for kind in ["auto_restart_mining_success", "auto_reboot_success", "restart_detected", "restart_detected"]:
            store.record_event(occurred_ts=990, event_type=kind, severity="info", summary="test")
        metrics = fetch_daily_digest_metrics(store.path, [], now_ts=1000)
        assert metrics["restarts_detected_24h"] == 2
        assert metrics["reboots_24h"] == 1
        text = format_daily_digest(metrics)
        assert "Reinicios detectados: 2" in text and "Reboots ejecutados: 1" in text
    finally:
        store.close()


def test_soft_restart_requires_recent_success_once_and_same_miner(tmp_path):
    store = EventStore(tmp_path / "events.db")
    try:
        def record(kind, ts, miner="a"):
            store.record_event(occurred_ts=ts, miner_key=miner, event_type=kind, severity="info", summary="test")
        record("auto_restart_mining_failed", 990)
        assert store.get_unattributed_mining_restart_ts("a", now_ts=1000, elapsed=5) is None
        record("auto_restart_mining_success", 995)
        assert store.get_unattributed_mining_restart_ts("b", now_ts=1000, elapsed=2) is None
        assert store.get_unattributed_mining_restart_ts("a", now_ts=1000, elapsed=2) == 995
        assert store.get_unattributed_mining_restart_ts("a", now_ts=1000, elapsed=80) is None
        record("restart_detected", 1000)
        assert store.get_unattributed_mining_restart_ts("a", now_ts=1030, elapsed=2) is None
        record("auto_restart_mining_success", 1100)
        assert store.get_unattributed_mining_restart_ts("a", now_ts=1300, elapsed=2) is None
    finally:
        store.close()


def test_hook_uses_confirmed_soft_restart_once(tmp_path, monkeypatch):
    monkeypatch.setattr(sender, "send_telegram", Mock())
    monkeypatch.setattr(DetectionHook, "classify_state", Mock(return_value="OK"))
    miner = dict(name="test", host="test.invalid", port=4028)
    key = "test|test.invalid:4028"
    state = MinerState()
    store = EventStore(tmp_path / "hook.db")
    ctx = SimpleNamespace(miners=[miner], config={"notify_reboot": False, "chain_telemetry_enabled": False},
                          threshold_ths=60, state_lock=threading.Lock(), event_store=store,
                          bot_token="fake", chat_id="fake", qa_mode=True, qa_notify=False)
    result = dict(miner=miner, state=state, responded=True, rate_ths=0, elapsed=2,
                  previous_elapsed=900, reboot_reason="elapsed_drop", active_boards=3, vnish_telemetry=None)
    tick = dict(states={key: state}, miner_results={key: result}, startup_grace_active=False)
    try:
        store.record_event(occurred_ts=99990, miner_key=key, event_type="auto_restart_mining_success", severity="info", summary="test")
        hook = DetectionHook()
        hook.execute(ctx, 1, 100000, tick)
        event = next(e for e in store.list_events(miner_key=key) if e['event_type'] == 'restart_detected')
        assert event['classification'] == 'expected_auto' and event['action_ts'] == 99990
        hook.execute(ctx, 2, 100030, tick)
        event = next(e for e in store.list_events(miner_key=key) if e['event_type'] == 'restart_detected')
        assert event['classification'] == 'unexpected'
    finally:
        store.close()
