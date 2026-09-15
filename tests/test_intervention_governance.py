"""Unit tests for Intervention Governance & Vnish Libre Mode (Spec 057)."""

import unittest
import time
from app.governance.intervention_policy import (
    ACTION_CONTINGENCY,
    ACTION_FAN_GOVERNOR,
    ACTION_PRESET_BALANCER,
    ACTION_REBOOT_L1,
    ACTION_REBOOT_L2,
    InterventionGovernance,
    apply_governance_toggle,
    format_governance_summary,
    should_allow_intervention,
)
from app.telegram.command_center import (
    CC_NAV_INTERVENTIONS,
    parse_command_center_callback,
    render_interventions_menu,
    render_main_dashboard,
)


class TestInterventionGovernancePolicy(unittest.TestCase):
    def test_default_state_all_allowed(self):
        gov = InterventionGovernance()
        now_ts = 1000.0
        for act in (ACTION_REBOOT_L1, ACTION_REBOOT_L2, ACTION_FAN_GOVERNOR, ACTION_PRESET_BALANCER, ACTION_CONTINGENCY):
            allowed, reason = should_allow_intervention(act, gov, now_ts)
            self.assertTrue(allowed, f"Action {act} should be allowed by default")
            self.assertEqual(reason, "allowed")

    def test_master_disable_blocks_all_actuators(self):
        gov = InterventionGovernance(master_enabled=False, disabled_reason="test_freeze")
        now_ts = 1000.0
        for act in (ACTION_REBOOT_L1, ACTION_REBOOT_L2, ACTION_FAN_GOVERNOR, ACTION_PRESET_BALANCER, ACTION_CONTINGENCY):
            allowed, reason = should_allow_intervention(act, gov, now_ts)
            self.assertFalse(allowed, f"Action {act} should be blocked under master disabled")
            self.assertIn("master_interventions_disabled:vnish_libre", reason)

    def test_selective_actuator_toggles(self):
        now_ts = 1000.0
        # Only reboots disabled
        gov = InterventionGovernance(reboots_enabled=False)
        self.assertFalse(should_allow_intervention(ACTION_REBOOT_L1, gov, now_ts)[0])
        self.assertFalse(should_allow_intervention(ACTION_REBOOT_L2, gov, now_ts)[0])
        self.assertTrue(should_allow_intervention(ACTION_FAN_GOVERNOR, gov, now_ts)[0])
        self.assertTrue(should_allow_intervention(ACTION_CONTINGENCY, gov, now_ts)[0])

        # Only governor disabled
        gov_fans = InterventionGovernance(governor_enabled=False)
        self.assertTrue(should_allow_intervention(ACTION_REBOOT_L1, gov_fans, now_ts)[0])
        self.assertFalse(should_allow_intervention(ACTION_FAN_GOVERNOR, gov_fans, now_ts)[0])

        # Only contingency disabled
        gov_cont = InterventionGovernance(contingency_enabled=False)
        self.assertFalse(should_allow_intervention(ACTION_CONTINGENCY, gov_cont, now_ts)[0])
        self.assertTrue(should_allow_intervention(ACTION_FAN_GOVERNOR, gov_cont, now_ts)[0])

    def test_timer_expiration_restores_permissions(self):
        now_ts = 1000.0
        # Disabled with timer until 1050
        gov = InterventionGovernance(master_enabled=False, expires_at_ts=1050.0)
        self.assertFalse(should_allow_intervention(ACTION_REBOOT_L1, gov, 1040.0)[0])
        
        # After 1050, expired -> should be allowed
        allowed, reason = should_allow_intervention(ACTION_REBOOT_L1, gov, 1051.0)
        self.assertTrue(allowed)
        self.assertEqual(reason, "timer_expired_restored")

    def test_apply_governance_toggle_all_off_and_on(self):
        gov = InterventionGovernance()
        now_ts = 1000.0
        # All off with 1h timer
        toggled = apply_governance_toggle(gov, "all_off", now_ts, duration_seconds=3600)
        self.assertFalse(toggled.master_enabled)
        self.assertFalse(toggled.reboots_enabled)
        self.assertFalse(toggled.governor_enabled)
        self.assertEqual(toggled.expires_at_ts, 4600.0)

        # All back on
        restored = apply_governance_toggle(toggled, "all_on", now_ts)
        self.assertTrue(restored.master_enabled)
        self.assertTrue(restored.reboots_enabled)
        self.assertIsNone(restored.expires_at_ts)

    def test_apply_individual_toggles(self):
        gov = InterventionGovernance()
        now_ts = 1000.0
        # Toggle reboots
        g2 = apply_governance_toggle(gov, "toggle_reboots", now_ts)
        self.assertFalse(g2.reboots_enabled)
        self.assertTrue(g2.governor_enabled)

        # Toggle governor
        g3 = apply_governance_toggle(g2, "toggle_governor", now_ts)
        self.assertFalse(g3.governor_enabled)

        # Toggle contingency
        g4 = apply_governance_toggle(g3, "toggle_contingency", now_ts)
        self.assertFalse(g4.contingency_enabled)

        # Toggle presets
        g5 = apply_governance_toggle(g4, "toggle_presets", now_ts)
        self.assertFalse(g5.presets_enabled)

    def test_serialization_roundtrip(self):
        gov = InterventionGovernance(
            master_enabled=False,
            reboots_enabled=False,
            governor_enabled=True,
            expires_at_ts=1700000000.0,
            disabled_reason="testing",
        )
        d = gov.to_dict()
        loaded = InterventionGovernance.from_dict(d)
        self.assertEqual(gov, loaded)


class TestInterventionTelegramUI(unittest.TestCase):
    def test_callback_parsing(self):
        self.assertEqual(parse_command_center_callback("cc:nav:interventions").target, "interventions")
        self.assertEqual(parse_command_center_callback("cc:act:int_all:off").param, "off")
        self.assertEqual(parse_command_center_callback("cc:act:int_all:on").param, "on")
        self.assertEqual(parse_command_center_callback("cc:act:int_tog:reboots").param, "reboots")
        self.assertEqual(parse_command_center_callback("cc:act:int_tog:governor").param, "governor")
        self.assertEqual(parse_command_center_callback("cc:act:int_tim:60m").param, "60m")

    def test_render_interventions_menu(self):
        gov = InterventionGovernance(master_enabled=True)
        text, kb = render_interventions_menu(gov, now_ts=1000.0)
        self.assertIn("GOBERNANZA DE INTERVENCIONES", text)
        self.assertIn("Régimen: 🟢 ACTIVAS", text)
        
        # Check buttons
        flat_buttons = [btn for row in kb["inline_keyboard"] for btn in row]
        button_texts = [b["text"] for b in flat_buttons]
        self.assertTrue(any("Desactivar TODAS" in t for t in button_texts))
        self.assertTrue(any("Reinicios: ON" in t for t in button_texts))
        self.assertTrue(any("Fans Gov: ON" in t for t in button_texts))
        self.assertTrue(any("30m" in t for t in button_texts))
        self.assertTrue(any("Menú Principal" in t for t in button_texts))

    def test_render_main_dashboard_includes_interventions_button(self):
        gov = InterventionGovernance(master_enabled=True)
        text, kb = render_main_dashboard({}, miners=[], gov=gov)
        flat_buttons = [btn for row in kb["inline_keyboard"] for btn in row]
        int_buttons = [b for b in flat_buttons if b.get("callback_data") == CC_NAV_INTERVENTIONS]
        self.assertEqual(len(int_buttons), 1)
        self.assertIn("🛡️ Intervenciones [🟢 ON]", int_buttons[0]["text"])

    def test_render_main_dashboard_reflects_disabled_badge(self):
        gov = InterventionGovernance(master_enabled=False)
        text, kb = render_main_dashboard({}, miners=[], gov=gov)
        flat_buttons = [btn for row in kb["inline_keyboard"] for btn in row]
        int_buttons = [b for b in flat_buttons if b.get("callback_data") == CC_NAV_INTERVENTIONS]
        self.assertIn("[🔴 LIBRE]", int_buttons[0]["text"])


class TestInterventionMonitorIntegration(unittest.TestCase):
    def test_evaluate_auto_restart_blocked_by_governance(self):
        from app.miner_monitor import evaluate_auto_restart_candidate

        now_ts = 1000.0
        # When master is disabled (Vnish Libre)
        gov_libre = InterventionGovernance(master_enabled=False, disabled_reason="user_freeze")
        cand, reason, cd = evaluate_auto_restart_candidate(
            now_ts=now_ts,
            responded=True,
            rate_ths=0.0,
            threshold_ths=60.0,
            active_boards=0,
            expected_boards=3,
            miner_state="stopped",
            restart_required=False,
            reboot_required=False,
            auto_restart_enabled=True,
            last_auto_restart_ts=None,
            auto_restart_cooldown_seconds=300.0,
            auto_restart_count=0,
            max_retries_before_reboot=2,
            gov=gov_libre,
        )
        self.assertFalse(cand)
        self.assertIn("interventions_blocked:master_interventions_disabled", reason)

        # When only reboots are disabled
        gov_no_reboot = InterventionGovernance(master_enabled=True, reboots_enabled=False)
        cand, reason, cd = evaluate_auto_restart_candidate(
            now_ts=now_ts,
            responded=True,
            rate_ths=0.0,
            threshold_ths=60.0,
            active_boards=0,
            expected_boards=3,
            miner_state="stopped",
            restart_required=False,
            reboot_required=False,
            auto_restart_enabled=True,
            last_auto_restart_ts=None,
            auto_restart_cooldown_seconds=300.0,
            auto_restart_count=0,
            max_retries_before_reboot=2,
            gov=gov_no_reboot,
        )
        self.assertFalse(cand)
        self.assertEqual(reason, "interventions_blocked:reboots_disabled")

        # When interventions are enabled, qualifies normally
        gov_active = InterventionGovernance(master_enabled=True, reboots_enabled=True)
        cand, reason, cd = evaluate_auto_restart_candidate(
            now_ts=now_ts,
            responded=True,
            rate_ths=0.0,
            threshold_ths=60.0,
            active_boards=0,
            expected_boards=3,
            miner_state="stopped",
            restart_required=False,
            reboot_required=False,
            auto_restart_enabled=True,
            last_auto_restart_ts=None,
            auto_restart_cooldown_seconds=300.0,
            auto_restart_count=0,
            max_retries_before_reboot=2,
            gov=gov_active,
        )
        self.assertTrue(cand)
        self.assertEqual(reason, "stopped_state")

    def test_auto_restart_allowed_after_timer_expiration(self):
        from app.miner_monitor import evaluate_auto_restart_candidate

        # Expired timer at now_ts=1050 (expiration was 1000)
        gov_expired = InterventionGovernance(
            master_enabled=False,
            expires_at_ts=1000.0,
        )
        cand, reason, cd = evaluate_auto_restart_candidate(
            now_ts=1050.0,
            responded=True,
            rate_ths=0.0,
            threshold_ths=60.0,
            active_boards=0,
            expected_boards=3,
            miner_state="stopped",
            restart_required=False,
            reboot_required=False,
            auto_restart_enabled=True,
            last_auto_restart_ts=None,
            auto_restart_cooldown_seconds=300.0,
            auto_restart_count=0,
            max_retries_before_reboot=2,
            gov=gov_expired,
        )
        self.assertTrue(cand)
        self.assertEqual(reason, "stopped_state")


if __name__ == "__main__":
    unittest.main()
