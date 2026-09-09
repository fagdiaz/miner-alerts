"""
test_fleet_cards.py — Unit tests for Mobile Fleet Cards & Diagnostic UX (Spec 046).

Verifies strict line width limits (<= 32 visible columns), total character length (< 3,600 chars),
resilience to missing data, callback grammar and payload boundaries (<= 64 bytes).
"""

from __future__ import annotations

import unittest
from typing import Any, Dict, List

from app.governance.energy_efficiency import (
    EfficiencyAssessment,
    STATUS_DEGRADED,
    STATUS_OPTIMAL,
    build_efficiency_table_text,
)
from app.governance.fan_health import (
    CoolingAssessment,
    STATUS_CRITICAL_HEAT,
    STATUS_ELEVATED,
    STATUS_HEALTHY,
    STATUS_SATURATED,
    build_fans_table_text,
)
from app.telegram.fleet_cards import (
    DIAG_PREFIX,
    DIAG_REF_EFF,
    DIAG_REF_FANS,
    DIAG_REF_PRESETS,
    DIAG_REF_STATUS,
    MOBILE_LINE_WIDTH_LIMIT,
    build_diagnostic_keyboard,
    parse_diagnostic_callback,
    render_fleet_status_card,
)
from app.telegram.help_center import visible_line_width
from app.vnish.presets import (
    PresetAssessment,
    STATUS_AUTOTUNING,
    STATUS_DOWNCLOCKED,
    STATUS_STABLE,
    build_presets_table_text,
)


class MockMinerState:
    def __init__(
        self,
        state: str = "OK",
        last_rate_ths: float = 101.5,
        last_active_boards: int = 3,
        last_expected_boards: int = 3,
        last_max_chip_temp: float = 81.0,
        last_fan_duty_percent: float = 94.0,
        last_power_w: float = 2698.0,
        last_efficiency_j_th: float = 26.6,
        silent_mode_active: bool = False,
        snooze_until_ts: float | None = None,
    ):
        self.state = state
        self.last_rate_ths = last_rate_ths
        self.last_active_boards = last_active_boards
        self.last_expected_boards = last_expected_boards
        self.last_max_chip_temp = last_max_chip_temp
        self.last_fan_duty_percent = last_fan_duty_percent
        self.last_power_w = last_power_w
        self.last_efficiency_j_th = last_efficiency_j_th
        self.silent_mode_active = silent_mode_active
        self.snooze_until_ts = snooze_until_ts


class TestFleetCardsLineLimits(unittest.TestCase):
    """Test every rendered data line strictly obeys visible_line_width <= 32."""

    def _assert_all_lines_under_limit(self, text: str, label: str):
        for idx, line in enumerate(text.split("\n"), start=1):
            width = visible_line_width(line)
            self.assertLessEqual(
                width,
                MOBILE_LINE_WIDTH_LIMIT,
                f"Line {idx} in {label} exceeds 32 visible cols ({width} cols): {line!r}",
            )
        # Verify total size is well under 3,600 characters to prevent split_telegram_message breakage
        self.assertLess(
            len(text),
            3600,
            f"Total length of {label} exceeds 3,600 characters ({len(text)} chars)",
        )

    def test_status_card_normal_fleet(self):
        miners = [
            {"name": "S19JPRO-23", "host": "192.168.100.23", "port": 4028},
            {"name": "S19JPRO-24", "host": "192.168.100.24", "port": 4028},
            {"name": "S19JPRO-25", "host": "192.168.100.25", "port": 4028},
            {"name": "S19JPRO-26", "host": "192.168.100.26", "port": 4028},
        ]
        states = {
            "S19JPRO-23|192.168.100.23:4028": MockMinerState(last_rate_ths=101.5, last_power_w=2698.0),
            "S19JPRO-24|192.168.100.24:4028": MockMinerState(last_rate_ths=93.6, last_power_w=2499.0, last_max_chip_temp=82.0),
            "S19JPRO-25|192.168.100.25:4028": MockMinerState(last_rate_ths=96.4, last_power_w=2498.0, silent_mode_active=True),
            "S19JPRO-26|192.168.100.26:4028": MockMinerState(last_rate_ths=100.6, last_power_w=2699.0, snooze_until_ts=9999999999.0),
        }
        text, kb = render_fleet_status_card(states, miners=miners, now_ts_str="15:00 hs")
        self._assert_all_lines_under_limit(text, "render_fleet_status_card:normal")
        self.assertIn("ESTADO DE FLOTA", text)
        self.assertIn("S19JPRO-23", text)
        self.assertIn("Total:", text)

    def test_status_card_missing_data_and_offline(self):
        miners = [
            {"name": "S19JPRO-23", "host": "192.168.100.23", "port": 4028},
            {"name": "S19JPRO-LONG-NAME-TEST", "host": "192.168.100.24", "port": 4028},
        ]
        states = {
            "S19JPRO-23|192.168.100.23:4028": MockMinerState(state="OFFLINE", last_rate_ths=0.0, last_power_w=0.0, last_max_chip_temp=None, last_fan_duty_percent=None),
            # S19JPRO-LONG-NAME-TEST missing in states
        }
        text, kb = render_fleet_status_card(states, miners=miners)
        self._assert_all_lines_under_limit(text, "render_fleet_status_card:missing_data")
        self.assertIn("OFFLINE", text)
        self.assertIn("SIN DATOS", text)

    def test_status_card_empty(self):
        text, kb = render_fleet_status_card({})
        self._assert_all_lines_under_limit(text, "render_fleet_status_card:empty")
        self.assertIn("Sin lecturas", text)

    def test_fans_card_limits(self):
        assessments = [
            CoolingAssessment("S19JPRO-23", STATUS_HEALTHY, "🟢 OK", 71.2, 13.8, 5400, 82.0, (), "OK", "hold_target"),
            CoolingAssessment("S19JPRO-24", STATUS_SATURATED, "🟠 SATURADO", 82.0, 3.0, 6000, 100.0, (), "Limpiar filtros", "recovery_max"),
            CoolingAssessment("S19JPRO-25", STATUS_CRITICAL_HEAT, "🔴 CRÍTICO", 84.8, 0.2, 6200, 100.0, (), "Urgente", "emergency_spike"),
            CoolingAssessment("S19JPRO-26", STATUS_ELEVATED, "🟡 ELEVADO", 76.5, 8.5, 5600, 88.0, (), "Monitorear", None),
        ]
        text = build_fans_table_text(assessments)
        self._assert_all_lines_under_limit(text, "build_fans_table_text")

    def test_efficiency_card_limits(self):
        assessments = [
            EfficiencyAssessment("S19JPRO-23", STATUS_OPTIMAL, "🟢 ÓPTIMA", 101.5, 2698.0, 26.6, "Optimo"),
            EfficiencyAssessment("S19JPRO-24", STATUS_OPTIMAL, "🟢 ÓPTIMA", 93.6, 2499.0, 26.7, "Optimo"),
            EfficiencyAssessment("S19JPRO-25", STATUS_DEGRADED, "🟠 DEGRADADA", 72.0, 3050.0, 42.4, "Degradada"),
            EfficiencyAssessment("S19JPRO-26", STATUS_OPTIMAL, "🟢 ÓPTIMA", 100.6, 2699.0, 26.8, "Optimo"),
        ]
        text = build_efficiency_table_text(assessments)
        self._assert_all_lines_under_limit(text, "build_efficiency_table_text")

    def test_presets_card_limits(self):
        assessments = [
            PresetAssessment("S19JPRO-23", STATUS_STABLE, "🟢 ESTABLE", 516.0, 12.83, 2698.0, 104.2, "~2700W (516 MHz)", (), "OK"),
            PresetAssessment("S19JPRO-24", STATUS_DOWNCLOCKED, "⚠️ DOWNCLOCKED", 484.9, 12.89, 2499.0, 94.8, "~2500W (485 MHz)", (), "Reducido"),
            PresetAssessment("S19JPRO-25", STATUS_AUTOTUNING, "🔄 AUTOTUNING", 487.3, 12.60, 2498.0, 92.8, "~2500W (487 MHz)", (), "Tuning"),
            PresetAssessment("S19JPRO-26", STATUS_STABLE, "🟢 ESTABLE", 514.9, 12.80, 2699.0, 98.6, "~2700W (515 MHz)", (), "OK"),
        ]
        text = build_presets_table_text(assessments)
        self._assert_all_lines_under_limit(text, "build_presets_table_text")


class TestFleetCardsCallbacksAndKeyboards(unittest.TestCase):
    """Test callback parsing, validation, and keyboard construction."""

    def test_parse_valid_callbacks(self):
        action_status = parse_diagnostic_callback("diag:ref:status")
        self.assertIsNotNone(action_status)
        self.assertEqual(action_status.action, "ref")
        self.assertEqual(action_status.report_type, "status")

        action_fans = parse_diagnostic_callback("diag:ref:fans")
        self.assertIsNotNone(action_fans)
        self.assertEqual(action_fans.report_type, "fans")

        action_eff = parse_diagnostic_callback("diag:ref:eff")
        self.assertIsNotNone(action_eff)
        self.assertEqual(action_eff.report_type, "eff")

        action_presets = parse_diagnostic_callback("diag:ref:presets")
        self.assertIsNotNone(action_presets)
        self.assertEqual(action_presets.report_type, "presets")

    def test_parse_invalid_callbacks(self):
        self.assertIsNone(parse_diagnostic_callback(""))
        self.assertIsNone(parse_diagnostic_callback("diag:invalid"))
        self.assertIsNone(parse_diagnostic_callback("diag:act:status"))
        self.assertIsNone(parse_diagnostic_callback("diag:ref:unknown_report"))
        self.assertIsNone(parse_diagnostic_callback("other:ref:status"))
        self.assertIsNone(parse_diagnostic_callback("diag:ref:status:extra"))
        self.assertIsNone(parse_diagnostic_callback("x" * 65))

    def test_keyboards_structure_and_bounds(self):
        for rep in ("status", "fans", "eff", "presets"):
            kb = build_diagnostic_keyboard(rep)
            self.assertIn("inline_keyboard", kb)
            rows = kb["inline_keyboard"]
            self.assertGreaterEqual(len(rows), 1)
            for row in rows:
                for btn in row:
                    cb = btn.get("callback_data", "")
                    self.assertLessEqual(
                        len(cb.encode("utf-8")),
                        64,
                        f"Callback data in {rep} keyboard exceeds 64 bytes: {cb!r}",
                    )
                    self.assertTrue(
                        cb.startswith(DIAG_PREFIX) or cb == "cc:nav:main" or cb == "cc:nav:metrics",
                        f"Unexpected callback {cb!r} in {rep} keyboard",
                    )


if __name__ == "__main__":
    unittest.main()
