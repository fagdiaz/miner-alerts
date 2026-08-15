"""Phase 3 — Red contracts for the compact Telegram message format.

These tests define the exact compact format from the sprint prompt.
They should FAIL before the renderer is updated and PASS after.
"""

import unittest

from app.alert_episodes import (
    IrregularEpisodeCoordinator,
    render_episode_notification_batch,
)


def _coord(coalesce: float = 30) -> IrregularEpisodeCoordinator:
    return IrregularEpisodeCoordinator(
        coalesce_seconds=coalesce,
        reminder_schedule_seconds=(300, 600, 900, 1800, 3600, 7200),
        steady_repeat_seconds=3600,
    )


def _observe(
    c: IrregularEpisodeCoordinator,
    *,
    miner: str = "24",
    previous: str = "OK",
    state: str = "OFFLINE",
    now: float = 100.0,
    rate: float | None = None,
    responded: bool = False,
    boards: int | None = None,
    event_id: int | None = 123,
    restart: dict | None = None,
) -> None:
    c.observe(
        miner_key=f"S19JPRO-{miner}|192.168.100.{miner}:4028",
        name_display=miner,
        host=f"192.168.100.{miner}",
        previous_state=previous,
        state=state,
        responded=responded,
        rate_ths=rate,
        threshold_ths=60.0,
        active_boards=boards if boards is not None else (3 if responded else None),
        expected_boards=3,
        now_ts=now,
        transition_event_id=event_id,
        restart=restart,
    )


class CompactAlertFormatTest(unittest.TestCase):
    """Contract A exact format:
    ALERTA MINEROS

    24 OFFLINE · 30s · /e123
    25 LOW · 42.30 TH/s · 18s · /e124
    """

    def test_alert_uses_compact_header(self) -> None:
        c = _coord()
        _observe(c, miner="24", now=100.0, event_id=123)
        batch = c.pop_due(now_ts=130.0)
        msg = render_episode_notification_batch(batch, now_ts=130.0)
        self.assertTrue(
            msg.startswith("ALERTA MINEROS"),
            f"Expected 'ALERTA MINEROS' header, got: {msg[:40]!r}",
        )

    def test_alert_line_contains_dot_separators(self) -> None:
        c = _coord()
        _observe(c, miner="24", now=100.0, event_id=123)
        batch = c.pop_due(now_ts=130.0)
        msg = render_episode_notification_batch(batch, now_ts=130.0)
        # Find the miner line
        miner_lines = [l for l in msg.splitlines() if l.startswith("24")]
        self.assertEqual(1, len(miner_lines), f"Expected one line for miner 24, got: {miner_lines}")
        line = miner_lines[0]
        self.assertIn("OFFLINE", line)
        self.assertIn("/e123", line)
        self.assertIn("\u00b7", line, "Expected middle dot (·) separator")

    def test_low_alert_includes_rate(self) -> None:
        c = _coord()
        _observe(c, miner="25", state="LOW", responded=True,
                 rate=42.3, boards=3, now=100.0, event_id=124)
        batch = c.pop_due(now_ts=130.0)
        msg = render_episode_notification_batch(batch, now_ts=130.0)
        miner_lines = [l for l in msg.splitlines() if l.startswith("25")]
        self.assertEqual(1, len(miner_lines))
        line = miner_lines[0]
        self.assertIn("LOW", line)
        self.assertIn("42.30 TH/s", line)
        self.assertIn("/e124", line)

    def test_grouped_alert_all_on_single_lines(self) -> None:
        c = _coord()
        _observe(c, miner="24", now=100.0, event_id=123)
        _observe(c, miner="25", state="LOW", responded=True,
                 rate=42.3, boards=3, now=103.0, event_id=124)
        batch = c.pop_due(now_ts=130.0)
        msg = render_episode_notification_batch(batch, now_ts=130.0)
        # Each miner should be on one line, not multi-line blocks
        lines_24 = [l for l in msg.splitlines() if "24" in l and "OFFLINE" in l]
        lines_25 = [l for l in msg.splitlines() if "25" in l and "LOW" in l]
        self.assertEqual(1, len(lines_24), "Miner 24 should be on exactly one line")
        self.assertEqual(1, len(lines_25), "Miner 25 should be on exactly one line")


class CompactRecoveryFormatTest(unittest.TestCase):
    """Contract B exact format:
    RECUPERADOS

    24 OK · 98.40 TH/s
    OFFLINE -> LOW -> OK · 4m · /e123
    """

    def test_recovery_uses_compact_header(self) -> None:
        c = _coord()
        _observe(c, miner="24", now=100.0, event_id=123)
        c.pop_due(now_ts=130.0)
        _observe(c, miner="24", previous="OFFLINE", state="OK",
                 responded=True, rate=98.4, boards=3, now=340.0, event_id=125)
        batch = c.pop_due(now_ts=370.0)
        msg = render_episode_notification_batch(batch, now_ts=370.0)
        self.assertIn("RECUPERADOS", msg)

    def test_recovery_includes_sequence_and_duration(self) -> None:
        c = _coord()
        _observe(c, miner="24", now=100.0, event_id=123)
        c.pop_due(now_ts=130.0)
        _observe(c, miner="24", previous="OFFLINE", state="OK",
                 responded=True, rate=98.4, boards=3, now=340.0, event_id=125)
        batch = c.pop_due(now_ts=370.0)
        msg = render_episode_notification_batch(batch, now_ts=370.0)
        self.assertIn("OK -> OFFLINE -> OK", msg)
        self.assertIn("/e", msg)


class CompactPersistenceFormatTest(unittest.TestCase):
    """Contract C exact format:
    SIGUE AFECTADO · 5m

    24 OFFLINE · /e123
    """

    def test_persistence_uses_compact_header(self) -> None:
        c = _coord()
        _observe(c, miner="24", now=100.0, event_id=123)
        c.pop_due(now_ts=130.0)
        batch = c.pop_due(now_ts=400.0)
        self.assertEqual(1, len(batch.persistent))
        msg = render_episode_notification_batch(batch, now_ts=400.0)
        self.assertIn("SIGUE AFECTADO", msg)


class CompactAgeFormatTest(unittest.TestCase):
    """Ages should use shorthand: seconds for <60s, minutes for >=60s."""

    def test_short_age_in_seconds(self) -> None:
        c = _coord()
        _observe(c, miner="24", now=100.0, event_id=123)
        batch = c.pop_due(now_ts=130.0)
        msg = render_episode_notification_batch(batch, now_ts=130.0)
        # Age is 30s; should show in seconds
        self.assertIn("30s", msg)

    def test_longer_age_in_minutes(self) -> None:
        c = _coord()
        _observe(c, miner="24", now=100.0, event_id=123)
        c.pop_due(now_ts=130.0)
        # At t=400, the persistence reminder fires; age = 300s = 5m
        batch = c.pop_due(now_ts=400.0)
        msg = render_episode_notification_batch(batch, now_ts=400.0)
        self.assertIn("5m", msg)


if __name__ == "__main__":
    unittest.main()
