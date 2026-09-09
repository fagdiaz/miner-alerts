"""Unit tests for Telegram Interactive Command Center & Rich UI (Spec 043)."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.telegram.command_center import (
    CC_ACT_PREFIX,
    CC_NAV_ALERTS,
    CC_NAV_MAIN,
    CC_NAV_METRICS,
    CC_NAV_PROFILES,
    CC_NAV_REBOOT,
    CC_NAV_SILENT,
    CC_PREFIX,
    CommandCenterAction,
    build_alert_action_buttons,
    build_inline_keyboard,
    make_progress_bar,
    parse_command_center_callback,
    render_alerts_view,
    render_main_dashboard,
    render_metrics_view,
    render_profiles_view,
    render_reboot_confirmation,
    render_reboot_menu,
    render_silent_mode_view,
)
from app.miner_monitor import MinerState


class TestCommandCenterParser(unittest.TestCase):
    def test_parse_valid_nav_actions(self):
        act = parse_command_center_callback("cc:nav:main")
        self.assertIsNotNone(act)
        self.assertEqual(act.kind, "nav")
        self.assertEqual(act.target, "main")

        act = parse_command_center_callback("cc:nav:metrics")
        self.assertIsNotNone(act)
        self.assertEqual(act.kind, "nav")
        self.assertEqual(act.target, "metrics")

        act = parse_command_center_callback("cc:nav:reboot")
        self.assertIsNotNone(act)
        self.assertEqual(act.kind, "nav")
        self.assertEqual(act.target, "reboot")

        act = parse_command_center_callback("cc:nav:profiles")
        self.assertIsNotNone(act)
        self.assertEqual(act.kind, "nav")
        self.assertEqual(act.target, "profiles")

        act = parse_command_center_callback("cc:nav:alerts")
        self.assertIsNotNone(act)
        self.assertEqual(act.kind, "nav")
        self.assertEqual(act.target, "alerts")

    def test_parse_valid_act_actions(self):
        act = parse_command_center_callback("cc:act:refresh")
        self.assertIsNotNone(act)
        self.assertEqual(act.kind, "act")
        self.assertEqual(act.target, "refresh")
        self.assertEqual(act.param, "main")

        act = parse_command_center_callback("cc:act:refresh:metrics")
        self.assertIsNotNone(act)
        self.assertEqual(act.kind, "act")
        self.assertEqual(act.target, "refresh")
        self.assertEqual(act.param, "metrics")

        act = parse_command_center_callback("cc:act:rb_req:23")
        self.assertIsNotNone(act)
        self.assertEqual(act.kind, "act")
        self.assertEqual(act.target, "rb_req")
        self.assertEqual(act.miner_id, "23")

        act = parse_command_center_callback("cc:act:rb_ccl:23")
        self.assertIsNotNone(act)
        self.assertEqual(act.kind, "act")
        self.assertEqual(act.target, "rb_ccl")
        self.assertEqual(act.miner_id, "23")

        act = parse_command_center_callback("cc:act:rb_cfm:tok123:23")
        self.assertIsNotNone(act)
        self.assertEqual(act.kind, "act")
        self.assertEqual(act.target, "rb_cfm")
        self.assertEqual(act.token, "tok123")
        self.assertEqual(act.miner_id, "23")

    def test_parse_invalid_or_malformed(self):
        self.assertIsNone(parse_command_center_callback(""))
        self.assertIsNone(parse_command_center_callback("other:data"))
        self.assertIsNone(parse_command_center_callback("cc:"))
        self.assertIsNone(parse_command_center_callback("cc:nav"))
        self.assertIsNone(parse_command_center_callback("cc:act"))


class TestCommandCenterUI(unittest.TestCase):
    def setUp(self):
        self.miners = [
            {"name": "S19JPRO-23", "host": "192.168.1.23", "port": 4028},
            {"name": "S19JPRO-24", "host": "192.168.1.24", "port": 4028},
            {"name": "S19JPRO-25", "host": "192.168.1.25", "port": 4028},
        ]
        st23 = MinerState()
        st23.state = "OK"
        st23.governor_duty = 65
        st23.governor_last_temp_c = 78.5
        st23.governor_last_power_w = 2700.0
        st23.balancer_preset = "2700W"

        st24 = MinerState()
        st24.state = "LOW"
        st24.governor_duty = 70
        st24.governor_last_temp_c = 81.2
        st24.governor_last_power_w = 2500.0
        st24.balancer_preset = "2500W"

        st25 = MinerState()
        st25.state = "OK"
        st25.governor_duty = 60
        st25.governor_last_temp_c = 75.0
        st25.governor_last_power_w = 2300.0
        st25.balancer_preset = "2300W"

        self.states = {
            "S19JPRO-23": st23,
            "S19JPRO-24": st24,
            "S19JPRO-25": st25,
        }
        self.config = {"miners": self.miners}

    def test_make_progress_bar(self):
        bar_empty = make_progress_bar(0, 85, width=8)
        self.assertEqual(bar_empty, "░░░░░░░░")

        bar_full = make_progress_bar(85, 85, width=8)
        self.assertEqual(bar_full, "████████")

        bar_half = make_progress_bar(42.5, 85, width=8)
        self.assertEqual(bar_half, "████░░░░")

    def test_render_main_dashboard(self):
        text, markup = render_main_dashboard(self.states, self.config, self.miners)
        self.assertIn("COMMAND CENTER", text)
        self.assertIn("ADVERTENCIA", text)  # st24 is LOW
        self.assertIn("7,500 W", text)  # 2700 + 2500 + 2300
        self.assertIn("81.2°C", text)  # max temp

        kb = markup.get("inline_keyboard", [])
        self.assertEqual(len(kb), 4)
        # Check callback data in buttons
        row0_cbs = [b["callback_data"] for b in kb[0]]
        self.assertIn(CC_NAV_METRICS, row0_cbs)
        self.assertIn(CC_NAV_PROFILES, row0_cbs)

        row1_cbs = [b["callback_data"] for b in kb[1]]
        self.assertIn(CC_NAV_SILENT, row1_cbs)
        self.assertIn(CC_NAV_REBOOT, row1_cbs)

        row2_cbs = [b["callback_data"] for b in kb[2]]
        self.assertIn(CC_NAV_ALERTS, row2_cbs)
        self.assertIn(f"{CC_ACT_PREFIX}refresh", row2_cbs)

        row3_cbs = [b["callback_data"] for b in kb[3]]
        self.assertIn("help:nav:home", row3_cbs)

    def test_render_main_dashboard_canonical_keys(self):
        canonical_states = {
            f"{m['name']}|{m['host']}:{m['port']}": self.states[m["name"]]
            for m in self.miners
        }
        text, markup = render_main_dashboard(canonical_states, self.config, self.miners)
        self.assertIn("COMMAND CENTER", text)
        self.assertIn("ADVERTENCIA", text)  # st24 is LOW
        self.assertIn("7,500 W", text)
        self.assertIn("81.2°C", text)

    def test_render_metrics_view(self):
        text, markup = render_metrics_view(self.states, self.miners)
        self.assertIn("MÉTRICAS DETALLADAS", text)
        self.assertIn("S19JPRO-23", text)
        self.assertIn("78.5°C", text)
        self.assertIn("Fans: 65%", text)

        kb = markup.get("inline_keyboard", [])
        self.assertEqual(len(kb), 1)
        row_cbs = [b["callback_data"] for b in kb[0]]
        self.assertIn(CC_NAV_MAIN, row_cbs)
        self.assertIn(f"{CC_ACT_PREFIX}refresh:metrics", row_cbs)

    def test_render_reboot_menu(self):
        text, markup = render_reboot_menu(self.states, self.miners)
        self.assertIn("CONTROL DE REINICIOS", text)
        kb = markup.get("inline_keyboard", [])
        self.assertTrue(len(kb) >= 2)

        # Confirm all miners have reboot buttons
        flattened_cbs = [b["callback_data"] for row in kb for b in row]
        self.assertIn(f"{CC_ACT_PREFIX}rb_req:S19JPRO-23", flattened_cbs)
        self.assertIn(f"{CC_ACT_PREFIX}rb_req:S19JPRO-24", flattened_cbs)
        self.assertIn(f"{CC_ACT_PREFIX}rb_req:S19JPRO-25", flattened_cbs)
        self.assertIn(CC_NAV_MAIN, flattened_cbs)

    def test_render_reboot_confirmation(self):
        text, markup = render_reboot_confirmation("S19JPRO-24", "tok_abc")
        self.assertIn("CONFIRMACIÓN DE REINICIO", text)
        self.assertIn("S19JPRO-24", text)
        self.assertIn("60 segundos", text)

        kb = markup.get("inline_keyboard", [])
        self.assertEqual(len(kb), 2)
        self.assertEqual(kb[0][0]["callback_data"], f"{CC_ACT_PREFIX}rb_cfm:tok_abc:S19JPRO-24")
        self.assertEqual(kb[1][0]["callback_data"], f"{CC_ACT_PREFIX}rb_ccl:S19JPRO-24")

    def test_render_profiles_view(self):
        text, markup = render_profiles_view(self.states, self.miners)
        self.assertIn("PRESETS Y PERFILES", text)
        self.assertIn("2700W", text)
        kb = markup.get("inline_keyboard", [])
        self.assertEqual(kb[0][0]["callback_data"], CC_NAV_MAIN)

    def test_render_alerts_view(self):
        text, markup = render_alerts_view(self.states, self.config, self.miners)
        self.assertIn("ESTADO DE ALERTAS", text)
        self.assertIn("Alertas Activas", text)
        kb = markup.get("inline_keyboard", [])
        self.assertEqual(kb[0][0]["callback_data"], CC_NAV_MAIN)

    def test_build_alert_action_buttons(self):
        markup = build_alert_action_buttons("24")
        kb = markup.get("inline_keyboard", [])
        self.assertEqual(len(kb), 2)
        row0_cbs = [b["callback_data"] for b in kb[0]]
        self.assertIn("diag:24", row0_cbs)
        self.assertIn("chart:24", row0_cbs)

        row1_cbs = [b["callback_data"] for b in kb[1]]
        self.assertIn("rb_req:24", row1_cbs)
        self.assertIn("snz:24:60", row1_cbs)


class TestCommandCenterDispatch(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_path = Path(self.temp_dir.name) / "state.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("app.miner_monitor.edit_message_text")
    @patch("app.miner_monitor.answer_callback_query")
    def test_dispatch_nav_main(self, mock_answer, mock_edit):
        from app.miner_monitor import _handle_command_center_callback
        import threading
        from app.telegram.callbacks import CallbackTokenRegistry

        cb_query = {
            "id": "cb_1",
            "data": "cc:nav:main",
            "message": {"message_id": 1234, "chat": {"id": 100}},
            "from": {"id": 100},
        }
        lock = threading.Lock()
        reg = CallbackTokenRegistry()

        _handle_command_center_callback(
            cb_query=cb_query,
            config={"miners": []},
            bot_token="fake_token",
            chat_id="100",
            cb_chat_id=100,
            message_id=1234,
            cb_id="cb_1",
            miners=[],
            states={},
            state_lock=lock,
            state_path=self.state_path,
            current_last_update_id=1,
            hashcore_cfg={},
            event_store=None,
            qa_mode=True,
            qa_allow_actions=False,
            token_registry=reg,
        )

        # Verify immediate answerCallbackQuery (<500ms ack)
        mock_answer.assert_called_once_with("fake_token", "cb_1")
        # Verify edit_message_text was called with dashboard text
        mock_edit.assert_called_once()
        args, kwargs = mock_edit.call_args
        self.assertEqual(args[0], "fake_token")
        self.assertEqual(args[1], "100")
        self.assertEqual(args[2], 1234)
        self.assertIn("COMMAND CENTER", args[3])

    @patch("app.miner_monitor.edit_message_text")
    @patch("app.miner_monitor.answer_callback_query")
    def test_dispatch_nav_metrics_and_refresh(self, mock_answer, mock_edit):
        from app.miner_monitor import _handle_command_center_callback
        import threading
        from app.telegram.callbacks import CallbackTokenRegistry

        lock = threading.Lock()
        reg = CallbackTokenRegistry()

        # Nav to metrics
        cb_query = {
            "id": "cb_2",
            "data": "cc:nav:metrics",
            "message": {"message_id": 1234, "chat": {"id": 100}},
            "from": {"id": 100},
        }
        _handle_command_center_callback(
            cb_query=cb_query,
            config={"miners": [{"name": "M1"}]},
            bot_token="fake_token",
            chat_id="100",
            cb_chat_id=100,
            message_id=1234,
            cb_id="cb_2",
            miners=[{"name": "M1"}],
            states={"M1": MinerState()},
            state_lock=lock,
            state_path=self.state_path,
            current_last_update_id=1,
            hashcore_cfg={},
            event_store=None,
            qa_mode=True,
            qa_allow_actions=False,
            token_registry=reg,
        )
        mock_answer.assert_called_with("fake_token", "cb_2")
        args, _ = mock_edit.call_args
        self.assertIn("MÉTRICAS DETALLADAS", args[3])

    @patch("app.miner_monitor.edit_message_text")
    @patch("app.miner_monitor.answer_callback_query")
    def test_dispatch_nav_silent(self, mock_answer, mock_edit):
        from app.miner_monitor import _handle_command_center_callback
        import threading
        from app.telegram.callbacks import CallbackTokenRegistry

        lock = threading.Lock()
        reg = CallbackTokenRegistry()

        cb_query = {
            "id": "cb_sil_nav",
            "data": "cc:nav:silent",
            "message": {"message_id": 1234, "chat": {"id": 100}},
            "from": {"id": 100},
        }
        _handle_command_center_callback(
            cb_query=cb_query,
            config={"miners": [{"name": "M1"}]},
            bot_token="fake_token",
            chat_id="100",
            cb_chat_id=100,
            message_id=1234,
            cb_id="cb_sil_nav",
            miners=[{"name": "M1"}],
            states={"M1": MinerState()},
            state_lock=lock,
            state_path=self.state_path,
            current_last_update_id=1,
            hashcore_cfg={},
            event_store=None,
            qa_mode=True,
            qa_allow_actions=False,
            token_registry=reg,
        )
        mock_answer.assert_called_with("fake_token", "cb_sil_nav")
        args, _ = mock_edit.call_args
        self.assertIn("MODO SILENCIO / VISITAS", args[3])

    @patch("app.miner_monitor.edit_message_text")
    @patch("app.miner_monitor.answer_callback_query")
    def test_dispatch_act_silent_30m_and_off(self, mock_answer, mock_edit):
        from app.miner_monitor import _handle_command_center_callback
        import threading
        from app.telegram.callbacks import CallbackTokenRegistry

        lock = threading.Lock()
        reg = CallbackTokenRegistry()
        miner = {"name": "24", "host": "192.168.1.24", "port": 4028}
        m_key = "24|192.168.1.24:4028"
        states = {m_key: MinerState()}

        # 1. Activate 30m via callback
        cb_query_act = {
            "id": "cb_sil_act",
            "data": "cc:act:silent:30m",
            "message": {"message_id": 1234, "chat": {"id": 100}},
            "from": {"id": 100},
        }
        _handle_command_center_callback(
            cb_query=cb_query_act,
            config={"miners": [miner], "silent_mode_target_max_duty": 70},
            bot_token="fake_token",
            chat_id="100",
            cb_chat_id=100,
            message_id=1234,
            cb_id="cb_sil_act",
            miners=[miner],
            states=states,
            state_lock=lock,
            state_path=self.state_path,
            current_last_update_id=1,
            hashcore_cfg={},
            event_store=None,
            qa_mode=True,
            qa_allow_actions=False,
            token_registry=reg,
        )
        self.assertTrue(states[m_key].silent_mode_active)
        self.assertIsNotNone(states[m_key].silent_mode_revert_ts)
        self.assertEqual(states[m_key].silent_mode_target_max_duty, 70)
        self.assertTrue(self.state_path.exists())

        # 2. Deactivate via callback
        cb_query_off = {
            "id": "cb_sil_off",
            "data": "cc:act:silent:off",
            "message": {"message_id": 1234, "chat": {"id": 100}},
            "from": {"id": 100},
        }
        _handle_command_center_callback(
            cb_query=cb_query_off,
            config={"miners": [miner], "silent_mode_target_max_duty": 70},
            bot_token="fake_token",
            chat_id="100",
            cb_chat_id=100,
            message_id=1234,
            cb_id="cb_sil_off",
            miners=[miner],
            states=states,
            state_lock=lock,
            state_path=self.state_path,
            current_last_update_id=1,
            hashcore_cfg={},
            event_store=None,
            qa_mode=True,
            qa_allow_actions=False,
            token_registry=reg,
        )
        self.assertFalse(states[m_key].silent_mode_active)
        self.assertIsNone(states[m_key].silent_mode_revert_ts)

    @patch("app.miner_monitor.run_hashcore_cli", return_value=(True, "ok_qa"))
    @patch("app.miner_monitor.edit_message_text")
    @patch("app.miner_monitor.answer_callback_query")
    def test_reboot_flow_request_and_confirm(self, mock_answer, mock_edit, mock_run):
        from app.miner_monitor import _handle_command_center_callback
        import threading
        from app.telegram.callbacks import CallbackTokenRegistry

        lock = threading.Lock()
        reg = CallbackTokenRegistry()
        miner = {"name": "24", "host": "192.168.1.24", "port": 4028}

        # Step 1: rb_req
        cb_query_req = {
            "id": "cb_req",
            "data": "cc:act:rb_req:24",
            "message": {"message_id": 1234, "chat": {"id": 100}},
            "from": {"id": 100},
        }
        _handle_command_center_callback(
            cb_query=cb_query_req,
            config={"miners": [miner]},
            bot_token="fake_token",
            chat_id="100",
            cb_chat_id=100,
            message_id=1234,
            cb_id="cb_req",
            miners=[miner],
            states={"24|192.168.1.24:4028": MinerState()},
            state_lock=lock,
            state_path=self.state_path,
            current_last_update_id=1,
            hashcore_cfg={},
            event_store=None,
            qa_mode=True,
            qa_allow_actions=True,
            token_registry=reg,
        )
        args, kwargs = mock_edit.call_args
        self.assertIn("CONFIRMACIÓN DE REINICIO", args[3])
        # Extract token from keyboard callback data
        kb = kwargs["reply_markup"]["inline_keyboard"]
        cfm_cb = kb[0][0]["callback_data"]  # cc:act:rb_cfm:<token>:24
        token = cfm_cb.split(":")[3]

        # Step 2: rb_cfm
        cb_query_cfm = {
            "id": "cb_cfm",
            "data": f"cc:act:rb_cfm:{token}:24",
            "message": {"message_id": 1234, "chat": {"id": 100}},
            "from": {"id": 100},
        }
        _handle_command_center_callback(
            cb_query=cb_query_cfm,
            config={"miners": [miner]},
            bot_token="fake_token",
            chat_id="100",
            cb_chat_id=100,
            message_id=1234,
            cb_id="cb_cfm",
            miners=[miner],
            states={"24|192.168.1.24:4028": MinerState()},
            state_lock=lock,
            state_path=self.state_path,
            current_last_update_id=1,
            hashcore_cfg={},
            event_store=None,
            qa_mode=True,
            qa_allow_actions=True,
            token_registry=reg,
        )
        args, _ = mock_edit.call_args
        self.assertIn("Reinicio de 24", args[3])

    @patch("app.miner_monitor.answer_callback_query")
    def test_unauthorized_user_rejection(self, mock_answer):
        from app.miner_monitor import _handle_callback_query
        import threading
        from app.telegram.callbacks import CallbackTokenRegistry

        cb_query = {
            "id": "cb_unauth",
            "data": "cc:nav:main",
            "message": {"message_id": 1234, "chat": {"id": 99999}},
            "from": {"id": 99999},  # Mismatched user!
        }
        lock = threading.Lock()
        reg = CallbackTokenRegistry()

        _handle_callback_query(
            cb_query=cb_query,
            config={},
            bot_token="fake_token",
            chat_id="12345",  # Authorized admin chat ID
            miners=[],
            states={},
            state_lock=lock,
            state_path=self.state_path,
            current_last_update_id=1,
            hashcore_cfg={},
            event_store=None,
            qa_mode=True,
            qa_allow_actions=False,
            token_registry=reg,
        )

        mock_answer.assert_called_once_with(
            "fake_token",
            "cb_unauth",
            text="⛔ Acceso no autorizado",
            show_alert=True,
        )

    def test_parse_shutdown_callbacks(self):
        from app.telegram.command_center import parse_command_center_callback

        # Navigation
        act = parse_command_center_callback("cc:nav:shutdown")
        self.assertIsNotNone(act)
        self.assertEqual(act.kind, "nav")
        self.assertEqual(act.target, "shutdown")

        act = parse_command_center_callback("cc:nav:resume")
        self.assertIsNotNone(act)
        self.assertEqual(act.kind, "nav")
        self.assertEqual(act.target, "resume")

        # Toggles and actions
        act = parse_command_center_callback("cc:act:sd_tog:23:1010")
        self.assertEqual(act.kind, "act")
        self.assertEqual(act.target, "sd_tog")
        self.assertEqual(act.miner_id, "23")
        self.assertEqual(act.param, "1010")

        act = parse_command_center_callback("cc:act:sd_req:1010")
        self.assertEqual(act.target, "sd_req")
        self.assertEqual(act.param, "1010")

        act = parse_command_center_callback("cc:act:sd_cfm:token123:1010")
        self.assertEqual(act.target, "sd_cfm")
        self.assertEqual(act.token, "token123")
        self.assertEqual(act.param, "1010")

        act = parse_command_center_callback("cc:act:sd_ccl:1010")
        self.assertEqual(act.target, "sd_ccl")
        self.assertEqual(act.param, "1010")

        act = parse_command_center_callback("cc:act:sd_all")
        self.assertEqual(act.target, "sd_all")

        act = parse_command_center_callback("cc:act:sd_clr")
        self.assertEqual(act.target, "sd_clr")

        act = parse_command_center_callback("cc:act:resume:23")
        self.assertEqual(act.target, "resume")
        self.assertEqual(act.param, "23")

        act = parse_command_center_callback("cc:act:resume:all")
        self.assertEqual(act.target, "resume")
        self.assertEqual(act.param, "all")

    def test_render_shutdown_menu_mobile_width_and_toggles(self):
        from app.telegram.command_center import render_shutdown_menu
        from app.telegram.help_center import visible_line_width

        miners = [
            {"name": "S19JPRO-23", "host": "192.168.100.23"},
            {"name": "S19JPRO-24", "host": "192.168.100.24"},
            {"name": "S19JPRO-25", "host": "192.168.100.25"},
            {"name": "S19JPRO-26", "host": "192.168.100.26"},
        ]

        for mask in ("0000", "1010", "1111"):
            text, kb = render_shutdown_menu({}, miners=miners, selected_mask=mask)
            for line in text.split("\n"):
                w = visible_line_width(line)
                self.assertLessEqual(w, 32, f"Line exceeds 32 cols in mask={mask}: '{line}'")

            # Check buttons structure
            inline_rows = kb.get("inline_keyboard", [])
            self.assertGreaterEqual(len(inline_rows), 4)

        # Check checkbox icons
        _, kb_none = render_shutdown_menu({}, miners=miners, selected_mask="0000")
        self.assertIn("⬜ S19-23", str(kb_none))
        self.assertIn("🛑 Apagar Seleccionados (0)", str(kb_none))

        _, kb_two = render_shutdown_menu({}, miners=miners, selected_mask="1010")
        self.assertIn("☑️ S19-23", str(kb_two))
        self.assertIn("⬜ S19-24", str(kb_two))
        self.assertIn("☑️ S19-25", str(kb_two))
        self.assertIn("🛑 APAGAR SELECCIONADOS (2) 🛑", str(kb_two))

        _, kb_all = render_shutdown_menu({}, miners=miners, selected_mask="1111")
        self.assertIn("⚡ APAGAR GRANJA (4) ⚡", str(kb_all))

    def test_render_shutdown_confirmation_mobile_width(self):
        from app.telegram.command_center import render_shutdown_confirmation
        from app.telegram.help_center import visible_line_width

        text, kb = render_shutdown_confirmation(["23", "25"], token="tok123", bitmask="1010")
        for line in text.split("\n"):
            w = visible_line_width(line)
            self.assertLessEqual(w, 32, f"Line exceeds 32 cols: '{line}'")
        self.assertIn("CONFIRMAR PARADA SEGURA", text)
        self.assertIn("tok123", str(kb))

    def test_render_resume_menu_mobile_width(self):
        from app.telegram.command_center import render_resume_menu
        from app.telegram.help_center import visible_line_width

        miners = [
            {"name": "S19JPRO-23", "host": "192.168.100.23"},
            {"name": "S19JPRO-24", "host": "192.168.100.24"},
            {"name": "S19JPRO-25", "host": "192.168.100.25"},
            {"name": "S19JPRO-26", "host": "192.168.100.26"},
        ]
        text, kb = render_resume_menu({}, miners=miners)
        for line in text.split("\n"):
            w = visible_line_width(line)
            self.assertLessEqual(w, 32, f"Line exceeds 32 cols: '{line}'")
        self.assertIn("REANUDAR MINADO", text)
        self.assertIn("REANUDAR GRANJA COMPLETA", str(kb))


if __name__ == "__main__":
    unittest.main()
