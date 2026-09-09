"""Unit and Contract Tests for Fleet Shutdown and Thermal Purge (Spec 048)."""

import unittest
from unittest.mock import MagicMock, patch

from app.governance.fleet_shutdown import (
    execute_parallel_resume,
    execute_parallel_shutdown,
    extract_miner_identifier,
    make_empty_bitmask,
    make_full_bitmask,
    parse_selection_indices,
    render_resume_success_card,
    render_safe_area_card,
    render_shutdown_error_card,
    render_shutdown_in_progress,
    resolve_selected_miners,
    toggle_selection_bitmask,
)
from app.telegram.help_center import visible_line_width
from app.vnish.client import (
    get_miner_status,
    resume_mining,
    safe_resume_mining,
    safe_stop_mining,
    stop_mining,
)


class TestBitmaskHelpers(unittest.TestCase):
    """Test pure deterministic bitmask manipulation."""

    def test_make_masks(self):
        self.assertEqual(make_empty_bitmask(4), "0000")
        self.assertEqual(make_full_bitmask(4), "1111")
        self.assertEqual(make_empty_bitmask(0), "")
        self.assertEqual(make_full_bitmask(0), "")

    def test_toggle_bitmask(self):
        mask = "0000"
        mask = toggle_selection_bitmask(mask, 0)
        self.assertEqual(mask, "1000")
        mask = toggle_selection_bitmask(mask, 2)
        self.assertEqual(mask, "1010")
        mask = toggle_selection_bitmask(mask, 0)
        self.assertEqual(mask, "0010")
        # Out of bounds safe
        self.assertEqual(toggle_selection_bitmask(mask, 99), "0010")
        self.assertEqual(toggle_selection_bitmask("", 0), "")

    def test_parse_and_resolve(self):
        miners = [
            {"name": "S19JPRO-23", "host": "192.168.100.23"},
            {"name": "S19JPRO-24", "host": "192.168.100.24"},
            {"name": "S19JPRO-25", "host": "192.168.100.25"},
            {"name": "S19JPRO-26", "host": "192.168.100.26"},
        ]
        self.assertEqual(parse_selection_indices("0000"), [])
        self.assertEqual(parse_selection_indices("1010"), [0, 2])
        self.assertEqual(parse_selection_indices("1111"), [0, 1, 2, 3])

        resolved = resolve_selected_miners("1010", miners)
        self.assertEqual(len(resolved), 2)
        self.assertEqual(resolved[0]["name"], "S19JPRO-23")
        self.assertEqual(resolved[1]["name"], "S19JPRO-25")

        resolved_all = resolve_selected_miners("1111", miners)
        self.assertEqual(len(resolved_all), 4)

    def test_extract_miner_identifier(self):
        self.assertEqual(extract_miner_identifier({"name": "S19JPRO-23"}), "23")
        self.assertEqual(extract_miner_identifier({"name": "MINER-4"}), "4")
        self.assertEqual(extract_miner_identifier({"host": "192.168.1.100"}), "192.168.1.100")


class TestConcurrentDispatchers(unittest.TestCase):
    """Test parallel execution of shutdown and resume routines."""

    def test_execute_parallel_shutdown_all_success(self):
        miners = [
            {"name": "S19JPRO-23", "host": "192.168.100.23"},
            {"name": "S19JPRO-25", "host": "192.168.100.25"},
        ]

        def dummy_stop(host, pw, timeout=3.0):
            return True, None

        results = execute_parallel_shutdown(miners, "admin", stop_fn=dummy_stop)
        self.assertEqual(len(results), 2)
        self.assertTrue(results["23"].success)
        self.assertTrue(results["25"].success)
        self.assertIsNone(results["23"].error)

    def test_execute_parallel_shutdown_partial_failure(self):
        miners = [
            {"name": "S19JPRO-23", "host": "192.168.100.23"},
            {"name": "S19JPRO-25", "host": "192.168.100.25"},
        ]

        def dummy_stop(host, pw, timeout=3.0):
            if "25" in host:
                return False, "connection_timeout"
            return True, None

        results = execute_parallel_shutdown(miners, "admin", stop_fn=dummy_stop)
        self.assertEqual(len(results), 2)
        self.assertTrue(results["23"].success)
        self.assertFalse(results["25"].success)
        self.assertEqual(results["25"].error, "connection_timeout")

    def test_execute_parallel_resume_all_success(self):
        miners = [
            {"name": "S19JPRO-23", "host": "192.168.100.23"},
            {"name": "S19JPRO-24", "host": "192.168.100.24"},
        ]

        def dummy_resume(host, pw, timeout=3.0):
            return True, None

        results = execute_parallel_resume(miners, "admin", resume_fn=dummy_resume)
        self.assertEqual(len(results), 2)
        self.assertTrue(results["23"].success)
        self.assertTrue(results["24"].success)

    def test_execute_empty_miners_list(self):
        self.assertEqual(execute_parallel_shutdown([], "admin"), {})
        self.assertEqual(execute_parallel_resume([], "admin"), {})


class TestMobileCardRenderers(unittest.TestCase):
    """Test that all rendered mobile cards strictly observe <= 32 visible cols."""

    def _assert_all_lines_mobile_width(self, text: str, max_cols: int = 32):
        for line in text.split("\n"):
            w = visible_line_width(line)
            self.assertLessEqual(
                w,
                max_cols,
                f"Line exceeds {max_cols} visible columns ({w} cols): '{line}'",
            )

    def test_render_shutdown_in_progress(self):
        card = render_shutdown_in_progress(["23", "25"], purge_seconds=45)
        self._assert_all_lines_mobile_width(card)
        self.assertIn("PARADA EN PROGRESO", card)
        self.assertIn("45s", card)

    def test_render_safe_area_card(self):
        card = render_safe_area_card(["23", "25", "26"], snooze_hours=4.0)
        self._assert_all_lines_mobile_width(card)
        self.assertIn("ÁREA ELÉCTRICA SEGURA", card)
        self.assertIn("S19JPRO-23", card)
        self.assertIn("S19JPRO-25", card)
        self.assertIn("S19JPRO-26", card)

    def test_render_resume_success_card(self):
        card = render_resume_success_card(["23", "24", "25", "26"])
        self._assert_all_lines_mobile_width(card)
        self.assertIn("MINADO REANUDADO", card)
        self.assertIn("S19JPRO-23", card)

    def test_render_shutdown_error_card(self):
        errors = {
            "S19JPRO-23": "connection_timeout_reaching_miner",
            "S19JPRO-25": "unauthorized_invalid_token",
        }
        card = render_shutdown_error_card(errors)
        self._assert_all_lines_mobile_width(card)
        self.assertIn("ALERTA EN MANIOBRA", card)


class TestVnishClientShutdownMethods(unittest.TestCase):
    """Test low-level vnish client stop/resume methods with mocks."""

    @patch("requests.post")
    def test_stop_mining_ok(self, mock_post):
        mock_post.return_value.status_code = 200
        ok, err = stop_mining("192.168.1.100", "dummy_tok")
        self.assertTrue(ok)
        self.assertIsNone(err)
        mock_post.assert_called_once()
        self.assertIn("mining/stop", mock_post.call_args[0][0])

    @patch("requests.post")
    def test_stop_mining_http_error(self, mock_post):
        mock_post.return_value.status_code = 500
        ok, err = stop_mining("192.168.1.100", "dummy_tok")
        self.assertFalse(ok)
        self.assertEqual(err, "http_status_500")

    @patch("requests.post")
    def test_resume_mining_fallback(self, mock_post):
        # 1st call to mining/resume fails 404, 2nd call to mining/start succeeds 200
        resp1 = MagicMock(status_code=404)
        resp2 = MagicMock(status_code=200)
        mock_post.side_effect = [resp1, resp2]

        ok, err = resume_mining("192.168.1.100", "dummy_tok")
        self.assertTrue(ok)
        self.assertIsNone(err)
        self.assertEqual(mock_post.call_count, 2)

    @patch("requests.get")
    def test_get_miner_status_ok(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"miner_state": "stopped"}
        ok, data, err = get_miner_status("192.168.1.100")
        self.assertTrue(ok)
        self.assertEqual(data.get("miner_state"), "stopped")
        self.assertIsNone(err)

    @patch("app.vnish.client.unlock_miner")
    @patch("app.vnish.client.lock_miner")
    @patch("app.vnish.client.stop_mining")
    def test_safe_stop_mining_transactional(self, mock_stop, mock_lock, mock_unlock):
        mock_unlock.return_value = (True, "tok123", None)
        mock_stop.return_value = (True, None)

        ok, err = safe_stop_mining("192.168.1.100", "admin")
        self.assertTrue(ok)
        mock_unlock.assert_called_once()
        mock_stop.assert_called_once_with("192.168.1.100", "tok123", timeout=2.5)
        mock_lock.assert_called_once_with("192.168.1.100", "tok123", timeout=2.5)


if __name__ == "__main__":
    unittest.main()

