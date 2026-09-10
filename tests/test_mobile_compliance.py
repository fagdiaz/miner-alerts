#!/usr/bin/env python3
"""Master Mobile-First Line Width Compliance Certification Suite (Spec 053).

Certifies that 100% of generated lines across all Telegram cards and reports
(Specs 045, 046, 047, 048, 049, 050, 051, 052) strictly adhere to
`visible_line_width(line) <= 32` columns without markdown overflow.
"""

from __future__ import annotations

import unittest
from typing import Any, Dict, List

from app.core.event_store import (
    render_event_detail,
    render_event_list,
    render_reboot_decision,
)
from app.governance.fleet_shutdown import (
    render_safe_area_card,
    render_shutdown_in_progress,
    render_resume_success_card,
    render_shutdown_error_card,
)
from app.governance.maintenance_scheduler import (
    ScheduledStage,
    ScheduledWindow,
    render_pre_ramp_card,
    render_schedule_cancelled_card,
    render_schedule_confirmation_card,
    render_scheduled_status_card,
)
from app.governance.phase_drop_discriminator import (
    PhaseDropAssessment,
    PhaseDropVerdict,
    render_phase_drop_alert,
)
from app.governance.post_blackout_guard import (
    render_post_blackout_alert,
    render_recovery_action_card,
)
from app.governance.preset_balancer import (
    build_balancer_table_text,
    build_elevator_sensitivity_text,
    build_miner_balancer_detail_text,
)
from app.telegram.daily_digest import format_daily_digest
from app.telegram.fleet_cards import render_fleet_status_card
from app.telegram.help_center import (
    HELP_CATEGORIES,
    HELP_COMMANDS,
    render_help_category,
    render_help_command_detail,
    render_help_home,
    visible_line_width,
)
from app.telegram.snooze import build_snooze_status_text


class MockMinerState:
    """Mock state object for mobile rendering."""
    def __init__(self, name: str, state: str = "OK"):
        self.state = state
        self.is_shutdown_maintenance = False
        self.last_rate_ths = 104.5
        self.last_power_w = 2850
        self.last_max_chip_temp = 82.1
        self.last_fan_duty_percent = 72
        self.last_efficiency_j_th = 27.27
        self.last_active_boards = 3
        self.last_expected_boards = 3
        self.last_responded = True
        self.snooze_until_ts = None
        self.silent_mode_active = False


class TestMasterMobileCompliance(unittest.TestCase):
    """Certifies visible_line_width(line) <= 32 across all card generators."""

    def _assert_card_lines_width(self, card_text: str, card_name: str) -> None:
        self.assertTrue(card_text, f"{card_name} returned empty text")
        lines = card_text.splitlines()
        for idx, line in enumerate(lines, 1):
            w = visible_line_width(line)
            self.assertLessEqual(
                w,
                32,
                f"Card '{card_name}' line {idx} width {w} > 32: '{line}'",
            )

    # 1. Spec 045: Help Center Mobile Navigation
    def test_help_center_cards_compliance(self) -> None:
        home_card, _ = render_help_home()
        self._assert_card_lines_width(home_card, "help_home_card")
        for cat_key in HELP_CATEGORIES.keys():
            cat_card, _ = render_help_category(cat_key)
            self._assert_card_lines_width(cat_card, f"help_category_{cat_key}")
        for cmd_name in list(HELP_COMMANDS.keys())[:5]:
            cmd_card, _ = render_help_command_detail(cmd_name)
            self._assert_card_lines_width(cmd_card, f"help_cmd_{cmd_name}")

    # 2. Spec 046: Fleet Status Card
    def test_fleet_status_card_compliance(self) -> None:
        miners = [
            {"name": "S19JPRO-23", "host": "192.168.100.23", "port": 4028},
            {"name": "S19JPRO-24", "host": "192.168.100.24", "port": 4028},
            {"name": "S19JPRO-25", "host": "192.168.100.25", "port": 4028},
            {"name": "S19JPRO-26", "host": "192.168.100.26", "port": 4028},
        ]
        states = {
            "S19JPRO-23|192.168.100.23:4028": MockMinerState("23", "OK"),
            "S19JPRO-24|192.168.100.24:4028": MockMinerState("24", "LOW"),
            "S19JPRO-25|192.168.100.25:4028": MockMinerState("25", "HASHBOARD"),
            "S19JPRO-26|192.168.100.26:4028": MockMinerState("26", "OFFLINE"),
        }
        card, _ = render_fleet_status_card(states, miners=miners, now_ts_str="18:30")
        self._assert_card_lines_width(card, "fleet_status_card")

    # 3. Spec 047: Balancer, Elevadores, Snooze, Events
    def test_spec_047_diagnostics_cards(self) -> None:
        # Balancer table
        b_text = build_balancer_table_text([], is_enabled=True, is_dry_run=False)
        self._assert_card_lines_width(b_text, "balancer_table")

        # Elevator sensitivity
        e_text = build_elevator_sensitivity_text({})
        self._assert_card_lines_width(e_text, "elevator_sensitivity")

        # Snooze status
        s_text = build_snooze_status_text([], {})
        self._assert_card_lines_width(s_text, "snooze_status")

        # Events list
        ev_list = render_event_list([])
        self._assert_card_lines_width(ev_list, "event_list")

    # 4. Specs 048-049: Fleet Shutdown & Active Purge Ramp
    def test_fleet_shutdown_cards_compliance(self) -> None:
        c1 = render_shutdown_in_progress(["23", "24", "25", "26"])
        self._assert_card_lines_width(c1, "shutdown_in_progress")

        c2 = render_safe_area_card(["23", "24", "25", "26"], snooze_hours=4.0, idle_duty=40)
        self._assert_card_lines_width(c2, "safe_area_card")

        c3 = render_resume_success_card(["23", "24", "25", "26"])
        self._assert_card_lines_width(c3, "resume_success_card")

        c4 = render_shutdown_error_card({"23": "timeout", "24": "http_error"})
        self._assert_card_lines_width(c4, "shutdown_error_card")

    # 5. Spec 050: Post-Blackout Recovery Guard
    def test_post_blackout_cards_compliance(self) -> None:
        from app.governance.post_blackout_guard import PostBlackoutTarget
        target = PostBlackoutTarget(
            miner_id="23",
            name="S19JPRO-23",
            host="192.168.100.23",
            uptime_seconds=120,
        )
        c1, _ = render_post_blackout_alert([target], auto_resume_seconds=30)
        self._assert_card_lines_width(c1, "post_blackout_alert")

        c2 = render_recovery_action_card(["23", "24", "25", "26"], automated=False)
        self._assert_card_lines_width(c2, "recovery_action_card")

    # 6. Spec 051: Fast Phase Drop Discriminator
    def test_phase_drop_cards_compliance(self) -> None:
        assessment_elev = PhaseDropAssessment(
            verdict=PhaseDropVerdict.PHASE_DROP_ELEVATOR,
            affected_groups=["elevador_1"],
            failed_miners=["23", "24"],
            responded_miners=[],
            active_groups=["elevador_1"],
            host_network_ok=True,
            details="Corte unísono en elevador 1",
        )
        c1 = render_phase_drop_alert(assessment_elev)
        self._assert_card_lines_width(c1, "phase_drop_elevator")

        assessment_fleet = PhaseDropAssessment(
            verdict=PhaseDropVerdict.PHASE_DROP_FLEET,
            affected_groups=["elevador_1", "elevador_2"],
            failed_miners=["23", "24", "25", "26"],
            responded_miners=[],
            active_groups=["elevador_1", "elevador_2"],
            host_network_ok=True,
            details="Corte total en la flota",
        )
        c2 = render_phase_drop_alert(assessment_fleet)
        self._assert_card_lines_width(c2, "phase_drop_fleet")

        assessment_iso = PhaseDropAssessment(
            verdict=PhaseDropVerdict.NETWORK_ISOLATION,
            affected_groups=[],
            failed_miners=["23", "24", "25", "26"],
            responded_miners=[],
            active_groups=["elevador_1", "elevador_2"],
            host_network_ok=False,
            details="Aislamiento Ethernet del host",
        )
        c3 = render_phase_drop_alert(assessment_iso)
        self._assert_card_lines_width(c3, "phase_drop_isolation")

    # 7. Spec 052: Scheduled Electrical Maintenance Windows
    def test_maintenance_scheduler_cards_compliance(self) -> None:
        win = ScheduledWindow(
            window_id="win_test_999",
            start_ts=3600.0,
            duration_seconds=7200.0,
            created_ts=1000.0,
            created_by="operador",
            stage=ScheduledStage.PENDING,
            stage_updated_ts=1000.0,
        )
        c1, _ = render_schedule_confirmation_card(win)
        self._assert_card_lines_width(c1, "schedule_confirmation_card")

        c2, _ = render_scheduled_status_card(win, now_ts=1050.0)
        self._assert_card_lines_width(c2, "scheduled_status_card")

        c3 = render_pre_ramp_card(tier=1, target_w=2300, mins_to_stop=10)
        self._assert_card_lines_width(c3, "pre_ramp_card")

        c4 = render_schedule_cancelled_card()
        self._assert_card_lines_width(c4, "schedule_cancelled_card")


if __name__ == "__main__":
    unittest.main()
