"""Unit tests for Scheduled Maintenance Windows & Soft Pre-Ramp Planner (Spec 052)."""

from __future__ import annotations

import time
import unittest

from app.governance.maintenance_scheduler import (
    ScheduledStage,
    ScheduledWindow,
    evaluate_window_stage,
    format_remaining_short,
    parse_duration_seconds,
    parse_schedule_expression,
    render_pre_ramp_card,
    render_schedule_cancelled_card,
    render_schedule_confirmation_card,
    render_scheduled_status_card,
)
from app.telegram.help_center import visible_line_width


class TestMaintenanceScheduler(unittest.TestCase):
    def test_parse_duration_seconds(self) -> None:
        self.assertEqual(parse_duration_seconds("2h"), 7200.0)
        self.assertEqual(parse_duration_seconds("30m"), 1800.0)
        self.assertEqual(parse_duration_seconds("1h30m"), 5400.0)
        self.assertEqual(parse_duration_seconds("1.5h"), 5400.0)
        self.assertEqual(parse_duration_seconds("90m"), 5400.0)
        self.assertIsNone(parse_duration_seconds("invalid"))
        self.assertIsNone(parse_duration_seconds(""))

    def test_parse_schedule_relative_valid(self) -> None:
        now = 10000.0
        ok, window, err = parse_schedule_expression("in 30m", "2h", now_ts=now, user_id="admin")
        self.assertTrue(ok)
        self.assertIsNotNone(window)
        self.assertIsNone(err)
        assert window is not None
        self.assertEqual(window.start_ts, 10000.0 + 1800.0)
        self.assertEqual(window.duration_seconds, 7200.0)
        self.assertEqual(window.stage, ScheduledStage.PENDING)
        self.assertEqual(window.created_by, "admin")

    def test_parse_schedule_relative_plus_syntax(self) -> None:
        now = 10000.0
        ok, window, err = parse_schedule_expression("+1h", "45m", now_ts=now)
        self.assertTrue(ok)
        self.assertIsNotNone(window)
        assert window is not None
        self.assertEqual(window.start_ts, 10000.0 + 3600.0)
        self.assertEqual(window.duration_seconds, 2700.0)

    def test_parse_schedule_absolute_datetime(self) -> None:
        from datetime import datetime, timezone
        now = datetime(2026, 10, 1, 13, 0, tzinfo=timezone.utc).timestamp()
        ok, window, err = parse_schedule_expression("2026-10-15 14:30", "3h", now_ts=now)
        self.assertTrue(ok, f"Error: {err}")
        self.assertIsNotNone(window)
        assert window is not None
        self.assertGreater(window.start_ts, now)
        self.assertEqual(window.duration_seconds, 10800.0)

    def test_parse_schedule_validation_errors(self) -> None:
        now = 10000.0
        # Too soon (< 5 minutes)
        ok, window, err = parse_schedule_expression("in 2m", "2h", now_ts=now)
        self.assertFalse(ok)
        self.assertIn("al menos 5 minutos", str(err))

        # Duration too short (< 15 min)
        ok, window, err = parse_schedule_expression("in 30m", "5m", now_ts=now)
        self.assertFalse(ok)
        self.assertIn("entre 15 minutos y 24 horas", str(err))

        # Duration too long (> 24h)
        ok, window, err = parse_schedule_expression("in 30m", "25h", now_ts=now)
        self.assertFalse(ok)
        self.assertIn("entre 15 minutos y 24 horas", str(err))

        # Invalid format
        ok, window, err = parse_schedule_expression("manana a la tarde", now_ts=now)
        self.assertFalse(ok)
        self.assertIn("No se pudo interpretar", str(err))

    def test_evaluate_window_stage_progression(self) -> None:
        start_ts = 2000.0
        duration = 3600.0  # 1 hour
        window = ScheduledWindow(
            window_id="test_win",
            start_ts=start_ts,
            duration_seconds=duration,
            created_ts=1000.0,
            stage=ScheduledStage.PENDING,
        )

        # 1. Way before start: T-20m (t=800) -> PENDING
        stage, _ = evaluate_window_stage(window, now_ts=800.0)
        self.assertEqual(stage, ScheduledStage.PENDING)

        # 2. T-10m reached (t=1400) -> PRE_RAMP_TIER_1 (2300W)
        stage, reason = evaluate_window_stage(window, now_ts=1400.0)
        self.assertEqual(stage, ScheduledStage.PRE_RAMP_TIER_1)
        self.assertIn("Tier 1", str(reason))
        window.stage = ScheduledStage.PRE_RAMP_TIER_1

        # 3. T-5m reached (t=1700) -> PRE_RAMP_TIER_2 (2100W)
        stage, reason = evaluate_window_stage(window, now_ts=1700.0)
        self.assertEqual(stage, ScheduledStage.PRE_RAMP_TIER_2)
        self.assertIn("Tier 2", str(reason))
        window.stage = ScheduledStage.PRE_RAMP_TIER_2

        # 4. T-0 reached (t=2000) -> EXECUTED
        stage, reason = evaluate_window_stage(window, now_ts=2000.0)
        self.assertEqual(stage, ScheduledStage.EXECUTED)
        self.assertIn("T-0", str(reason))
        window.stage = ScheduledStage.EXECUTED

        # 5. During maintenance (t=3000) -> still EXECUTED
        stage, _ = evaluate_window_stage(window, now_ts=3000.0)
        self.assertEqual(stage, ScheduledStage.EXECUTED)

        # 6. End reached (t=5600 >= 2000 + 3600) -> COMPLETED
        stage, reason = evaluate_window_stage(window, now_ts=5600.0)
        self.assertEqual(stage, ScheduledStage.COMPLETED)
        self.assertIn("finalizada", str(reason))

    def test_serialization_roundtrip(self) -> None:
        window = ScheduledWindow(
            window_id="win_12345",
            start_ts=1700000000.0,
            duration_seconds=7200.0,
            created_ts=1699990000.0,
            created_by="operador",
            stage=ScheduledStage.PRE_RAMP_TIER_1,
            stage_updated_ts=1699999000.0,
        )
        d = window.to_dict()
        restored = ScheduledWindow.from_dict(d)
        self.assertEqual(restored.window_id, window.window_id)
        self.assertEqual(restored.start_ts, window.start_ts)
        self.assertEqual(restored.duration_seconds, window.duration_seconds)
        self.assertEqual(restored.created_ts, window.created_ts)
        self.assertEqual(restored.created_by, window.created_by)
        self.assertEqual(restored.stage, window.stage)
        self.assertEqual(restored.end_ts, window.end_ts)

    def test_render_schedule_confirmation_card_width(self) -> None:
        window = ScheduledWindow(
            window_id="win_sample",
            start_ts=time.time() + 3600.0,
            duration_seconds=7200.0,
            created_ts=time.time(),
        )
        card, reply_markup = render_schedule_confirmation_card(window)
        self.assertIn("MANTENIMIENTO PROGRAMADO", card)
        self.assertIn("inline_keyboard", reply_markup)

        for line in card.split("\n"):
            self.assertLessEqual(
                visible_line_width(line),
                32,
                f"Line exceeds 32 visible columns: {line!r}",
            )

    def test_render_scheduled_status_card_width(self) -> None:
        # 1. None window
        card_none, markup_none = render_scheduled_status_card(None)
        self.assertIn("VENTANA DE MANTENIMIENTO", card_none)
        self.assertIsNone(markup_none)
        for line in card_none.split("\n"):
            self.assertLessEqual(visible_line_width(line), 32)

        # 2. Active window
        window = ScheduledWindow(
            window_id="win_sample",
            start_ts=time.time() + 1800.0,
            duration_seconds=3600.0,
            created_ts=time.time(),
        )
        card_active, markup_active = render_scheduled_status_card(window)
        self.assertIsNotNone(markup_active)
        for line in card_active.split("\n"):
            self.assertLessEqual(visible_line_width(line), 32)

    def test_render_pre_ramp_card_width(self) -> None:
        card = render_pre_ramp_card(tier=1, target_w=2300, mins_to_stop=10)
        self.assertIn("PRE-RAMPA DE DESCARGA", card)
        for line in card.split("\n"):
            self.assertLessEqual(visible_line_width(line), 32)

    def test_render_schedule_cancelled_card_width(self) -> None:
        card = render_schedule_cancelled_card()
        self.assertIn("VENTANA CANCELADA", card)
        for line in card.split("\n"):
            self.assertLessEqual(visible_line_width(line), 32)


if __name__ == "__main__":
    unittest.main()
