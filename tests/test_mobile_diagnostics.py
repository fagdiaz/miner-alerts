"""
test_mobile_diagnostics.py — Comprehensive validation of Mobile-First renderers (Spec 047).

Ensures all rendered lines from:
- build_balancer_table_text
- build_miner_balancer_detail_text
- build_elevator_sensitivity_text
- format_daily_digest
- build_snooze_status_text
- render_event_list
- render_event_detail
- render_reboot_decision
strictly adhere to visible_line_width <= 32 columns (RFC C1-C10).
Also verifies callback token byte limits (<= 64 bytes) and keyboard builders.
"""

from __future__ import annotations

import unittest
from typing import Any, Dict, List

from app.core.event_store import (
    render_event_detail,
    render_event_list,
    render_reboot_decision,
)
from app.governance.preset_balancer import (
    ACTION_HOLD_STABLE,
    ACTION_STEP_DOWN_RESTARTS,
    ACTION_STEP_UP_OPTIMIZE,
    BalancerDecision,
    ElevatorSensitivitySummary,
    StabilityMetrics,
    build_balancer_table_text,
    build_elevator_sensitivity_text,
    build_miner_balancer_detail_text,
)
from app.telegram.daily_digest import format_daily_digest
from app.telegram.fleet_cards import (
    DIAG_REF_BALANCER,
    DIAG_REF_DIGEST,
    DIAG_REF_ELEV,
    DIAG_REF_EVENTS,
    MOBILE_LINE_WIDTH_LIMIT,
    SUPPORTED_REPORT_TYPES,
    build_diagnostic_keyboard,
    parse_diagnostic_callback,
)
from app.telegram.help_center import visible_line_width
from app.telegram.snooze import build_snooze_status_text


def _assert_all_lines_mobile_compliant(test_case: unittest.TestCase, text: str, context_label: str = "") -> None:
    """Helper asserting every line in rendered text has visible_line_width <= 32."""
    lines = text.split("\n")
    for idx, line in enumerate(lines, start=1):
        w = visible_line_width(line)
        test_case.assertLessEqual(
            w,
            MOBILE_LINE_WIDTH_LIMIT,
            f"Line {idx} exceeds {MOBILE_LINE_WIDTH_LIMIT} cols in {context_label} (width={w}): {repr(line)}",
        )


class TestMobileDiagnostics(unittest.TestCase):
    def test_callback_constants_and_parser(self) -> None:
        """Verify new diagnostic callbacks are <= 64 bytes and correctly parsed."""
        for cb_const in (DIAG_REF_BALANCER, DIAG_REF_ELEV, DIAG_REF_DIGEST, DIAG_REF_EVENTS):
            self.assertLessEqual(len(cb_const.encode("utf-8")), 64)
            parsed = parse_diagnostic_callback(cb_const)
            self.assertIsNotNone(parsed)
            self.assertEqual(parsed.action, "ref")
            self.assertIn(parsed.report_type, SUPPORTED_REPORT_TYPES)

    def test_build_diagnostic_keyboard_for_spec047(self) -> None:
        """Verify keyboards for new reports have 1-tap refresh and return to menu."""
        for rtype in ("balancer", "elev", "digest", "events"):
            kb = build_diagnostic_keyboard(rtype)
            self.assertIn("inline_keyboard", kb)
            buttons = kb["inline_keyboard"][0]
            self.assertEqual(len(buttons), 2)
            self.assertEqual(buttons[0]["callback_data"], f"diag:ref:{rtype}")
            self.assertIn("Actualizar", buttons[0]["text"])

    def test_balancer_table_text_mobile_width(self) -> None:
        """Verify build_balancer_table_text adheres to <= 32 columns."""
        # Empty
        empty_text = build_balancer_table_text([])
        _assert_all_lines_mobile_compliant(self, empty_text, "empty balancer table")

        # Multi-elevator with long reasons
        m1 = StabilityMetrics(
            miner_name="S19JPRO-23",
            electrical_group="elevator_sensible",
            current_preset="2700W",
            restarts_24h=3,
            restarts_72h=5,
            hours_since_last_restart=1.5,
            avg_hashrate_24h_ths=85.0,
            downtime_minutes_24h=40.0,
            thermal_headroom_c=4.0,
            current_power_w=2710.0,
        )
        d1 = BalancerDecision(
            action=ACTION_STEP_DOWN_RESTARTS,
            miner_name="S19JPRO-23",
            electrical_group="elevator_sensible",
            current_preset="2700W",
            target_preset="2500W",
            reason="Inestabilidad reiterada por caidas de tension y microcortes frecuentes",
            requires_write=True,
            estimated_effective_hashrate=90.0,
        )

        m2 = StabilityMetrics(
            miner_name="S19JPRO-25",
            electrical_group="elevator_estable",
            current_preset="2500W",
            restarts_24h=0,
            restarts_72h=0,
            hours_since_last_restart=120.0,
            avg_hashrate_24h_ths=94.5,
            downtime_minutes_24h=0.0,
            thermal_headroom_c=7.5,
            current_power_w=2490.0,
        )
        d2 = BalancerDecision(
            action=ACTION_STEP_UP_OPTIMIZE,
            miner_name="S19JPRO-25",
            electrical_group="elevator_estable",
            current_preset="2500W",
            target_preset="2700W",
            reason="Margen termico amplio y estabilidad prolongada comprobada",
            requires_write=True,
            estimated_effective_hashrate=98.0,
        )

        text = build_balancer_table_text([(m1, d1), (m2, d2)], is_enabled=True, is_dry_run=False)
        _assert_all_lines_mobile_compliant(self, text, "populated balancer table")

    def test_miner_balancer_detail_text_mobile_width(self) -> None:
        """Verify build_miner_balancer_detail_text adheres to <= 32 columns."""
        m = StabilityMetrics(
            miner_name="S19JPRO-23",
            electrical_group="elevator_sensible",
            current_preset="2700W",
            restarts_24h=2,
            restarts_72h=3,
            hours_since_last_restart=4.5,
            avg_hashrate_24h_ths=89.2,
            downtime_minutes_24h=15.0,
            thermal_headroom_c=5.2,
            current_power_w=2680.0,
        )
        d = BalancerDecision(
            action=ACTION_HOLD_STABLE,
            miner_name="S19JPRO-23",
            electrical_group="elevator_sensible",
            current_preset="2700W",
            target_preset="2700W",
            reason="Operacion estable sin necesidad de intervencion",
            requires_write=False,
            estimated_effective_hashrate=94.0,
        )
        card = build_miner_balancer_detail_text(m, d)
        _assert_all_lines_mobile_compliant(self, card, "miner balancer detail card")

    def test_elevator_sensitivity_text_mobile_width(self) -> None:
        """Verify build_elevator_sensitivity_text adheres to <= 32 columns."""
        empty_card = build_elevator_sensitivity_text({})
        _assert_all_lines_mobile_compliant(self, empty_card, "empty elevator sensitivity card")

        s1 = ElevatorSensitivitySummary(
            group_name="elevator_1",
            miners=["S19JPRO-23", "S19JPRO-24"],
            total_load_w=5393.0,
            total_capacity_w=7000.0,
            restarts_24h=0,
            restarts_72h=1,
            cascade_incidents_7d=0,
            sensitivity_level="ESTABLE",
            diagnostics="Sin correlacion con caidas de tension electrica en la linea.",
            recommendation="Mantener operacion actual sin cambios.",
        )
        s2 = ElevatorSensitivitySummary(
            group_name="elevator_2",
            miners=["S19JPRO-25", "S19JPRO-26"],
            total_load_w=5420.0,
            total_capacity_w=7000.0,
            restarts_24h=4,
            restarts_72h=7,
            cascade_incidents_7d=2,
            sensitivity_level="ALTA_SENSIBILIDAD",
            diagnostics="Caidas de tension reiteradas disparan reinicios simultaneos en cascada.",
            recommendation="Escalar un minero a 2500W para reducir la carga total bajo 5000W.",
        )
        card = build_elevator_sensitivity_text({"elevator_1": s1, "elevator_2": s2})
        _assert_all_lines_mobile_compliant(self, card, "elevator sensitivity card")

    def test_daily_digest_mobile_width(self) -> None:
        """Verify format_daily_digest adheres to <= 32 columns."""
        metrics_full = {
            "fleet_uptime_pct": 99.4,
            "active_miners_count": 4,
            "total_miners_count": 4,
            "avg_hashrate_ths": 382.4,
            "nominal_hashrate_ths": 380.0,
            "avg_efficiency_j_th": 27.8,
            "shares_accepted_pct": 99.82,
            "shares_rejected_pct": 0.18,
            "incidents_24h": 2,
            "reboots_24h": 1,
            "backup_status": {"verified": True, "time_str": "03:15", "size_mb": 14.2},
            "snoozed_miners": ["S19JPRO-23", "S19JPRO-26"],
        }
        card = format_daily_digest(metrics_full, date_str="09/09/2026")
        _assert_all_lines_mobile_compliant(self, card, "daily digest full card")

        metrics_sparse = {
            "fleet_uptime_pct": 100.0,
            "active_miners_count": 0,
            "total_miners_count": 0,
            "avg_hashrate_ths": 0.0,
            "nominal_hashrate_ths": 0.0,
            "avg_efficiency_j_th": None,
            "shares_accepted_pct": 100.0,
            "shares_rejected_pct": 0.0,
            "incidents_24h": 0,
            "reboots_24h": 0,
            "backup_status": {"verified": False},
            "snoozed_miners": [],
        }
        sparse_card = format_daily_digest(metrics_sparse, date_str="09/09/2026")
        _assert_all_lines_mobile_compliant(self, sparse_card, "daily digest sparse card")

    def test_snooze_status_text_mobile_width(self) -> None:
        """Verify build_snooze_status_text adheres to <= 32 columns."""
        class DummyState:
            snooze_until_ts = 0.0

        miners = [
            {"name": "S19JPRO-23", "host": "192.168.1.23", "port": 4028},
            {"name": "S19JPRO-24", "host": "192.168.1.24", "port": 4028},
        ]
        states = {
            "S19JPRO-23|192.168.1.23:4028": DummyState(),
            "S19JPRO-24|192.168.1.24:4028": DummyState(),
        }

        # Empty snoozed
        text_empty = build_snooze_status_text(miners, states, now_ts=1000.0)
        _assert_all_lines_mobile_compliant(self, text_empty, "snooze empty status")

        # Active snoozed
        states["S19JPRO-23|192.168.1.23:4028"].snooze_until_ts = 1000.0 + 3600.0
        text_active = build_snooze_status_text(miners, states, now_ts=1000.0)
        _assert_all_lines_mobile_compliant(self, text_active, "snooze active status")

    def test_event_renderers_mobile_width(self) -> None:
        """Verify event_store renderers adhere to <= 32 columns."""
        # Empty list
        empty_list = render_event_list([])
        _assert_all_lines_mobile_compliant(self, empty_list, "empty event list")

        # Populated list
        events = [
            {
                "id": 101,
                "occurred_ts": 1757430000.0,
                "miner_name": "S19JPRO-23",
                "summary": "Reinicio inesperado por caida de tension",
                "event_type": "restart_detected",
            },
            {
                "id": 102,
                "occurred_ts": 1757430100.0,
                "miner_name": "S19JPRO-24",
                "summary": "OK -> LOW",
                "event_type": "state_transition",
            },
        ]
        list_card = render_event_list(events)
        _assert_all_lines_mobile_compliant(self, list_card, "populated event list")

        # Event detail with related events
        ev = {
            "id": 101,
            "occurred_ts": 1757430000.0,
            "miner_name": "S19JPRO-23",
            "event_type": "restart_detected",
            "classification": "unexpected",
            "previous_elapsed": 85000,
            "current_elapsed": 110,
            "new_state": "OK",
            "rate_ths": 98.4,
            "action_source": "auto_reboot_policy",
            "summary": "Reinicio automatico ejecutado con exito tras recuperacion de voltaje",
        }
        detail_card = render_event_detail(ev, related_events=events)
        _assert_all_lines_mobile_compliant(self, detail_card, "event detail card")

        # Reboot decision (various results)
        base_decision = {
            "evaluated_ts": 1757430000.0,
            "miner_key": "S19JPRO-23|192.168.100.23:4028",
            "miner_name": "S19JPRO-23",
            "result": "fleet_incident",
            "state": "LOW",
            "rate_ths": 52.0,
            "threshold_ths": 65.0,
            "low_elapsed_seconds": 720.0,
            "active_boards": 3,
            "expected_boards": 3,
            "max_temp_c": 76.5,
            "frequency_mhz_avg": 520.0,
            "hw_errors_total": 12,
            "chain_voltage_mv_avg": 12800.0,
            "chain_power_w_total": 2650.0,
            "cooldown_remaining_seconds": 90.0,
            "details_json": (
                '{"affected_count":2,"affected_miners":["S19JPRO-23","S19JPRO-24"],'
                '"fleet_min_affected":2,"fleet_snapshot_age_seconds":25.0}'
            ),
        }
        dec_card = render_reboot_decision(base_decision)
        _assert_all_lines_mobile_compliant(self, dec_card, "reboot decision fleet incident card")

        # Thermal decision
        thermal_decision = dict(base_decision)
        thermal_decision["result"] = "high_temperature"
        thermal_decision["details_json"] = '{"max_temp_c":86.5,"thermal_limit_c":85.0}'
        thermal_card = render_reboot_decision(thermal_decision)
        _assert_all_lines_mobile_compliant(self, thermal_card, "reboot decision thermal card")

        # Firmware transition decision
        fw_decision = dict(base_decision)
        fw_decision["result"] = "firmware_transition"
        fw_decision["details_json"] = '{"chains_transitioning_count":2}'
        fw_card = render_reboot_decision(fw_decision)
        _assert_all_lines_mobile_compliant(self, fw_card, "reboot decision fw transition card")


if __name__ == "__main__":
    unittest.main()
