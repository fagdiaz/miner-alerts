import unittest
from unittest.mock import MagicMock, patch

import requests

from app.vnish.client import (
    DEFAULT_HTTP_TIMEOUT,
    get_available_presets,
    get_cooling_settings,
    get_overclock_settings,
    get_summary_cooling,
    lock_miner,
    mask_secret,
    safe_get_overclock_settings,
    safe_set_fan_duty,
    safe_set_miner_preset,
    set_manual_fan_duty,
    set_miner_preset,
    unlock_miner,
)


class TestVnishClient(unittest.TestCase):
    def test_mask_secret(self):
        self.assertEqual(mask_secret(None), "None")
        self.assertEqual(mask_secret(""), "None")
        self.assertEqual(mask_secret("admin"), "***")
        self.assertEqual(mask_secret("token_123456"), "***")

    @patch("requests.post")
    def test_unlock_miner_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"token": "test_token_xyz"}
        mock_post.return_value = mock_resp

        ok, token, err = unlock_miner("192.168.100.23", "admin")
        self.assertTrue(ok)
        self.assertEqual(token, "test_token_xyz")
        self.assertIsNone(err)
        mock_post.assert_called_once_with(
            "http://192.168.100.23/api/v1/unlock",
            json={"pw": "admin"},
            timeout=DEFAULT_HTTP_TIMEOUT,
        )

    @patch("requests.post")
    def test_unlock_miner_unauthorized(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_post.return_value = mock_resp

        ok, token, err = unlock_miner("192.168.100.23", "wrong_pw")
        self.assertFalse(ok)
        self.assertIsNone(token)
        self.assertEqual(err, "unauthorized_invalid_password")

    @patch("requests.post")
    def test_unlock_miner_timeout(self, mock_post):
        mock_post.side_effect = requests.exceptions.Timeout("Connection timed out")

        ok, token, err = unlock_miner("192.168.100.23", "admin")
        self.assertFalse(ok)
        self.assertIsNone(token)
        self.assertEqual(err, "connection_timeout")

    @patch("requests.post")
    def test_lock_miner_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        res = lock_miner("192.168.100.23", "test_token_xyz")
        self.assertTrue(res)
        mock_post.assert_called_once_with(
            "http://192.168.100.23/api/v1/lock",
            headers={"Authorization": "Bearer test_token_xyz"},
            timeout=DEFAULT_HTTP_TIMEOUT,
        )

    def test_lock_miner_empty_token(self):
        # Empty token is a no-op returning True
        self.assertTrue(lock_miner("192.168.100.23", None))
        self.assertTrue(lock_miner("192.168.100.23", ""))

    @patch("requests.get")
    def test_get_cooling_settings(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "miner": {
                "cooling": {
                    "mode": {"name": "manual", "param": 100},
                    "fan_min_duty": 40,
                }
            }
        }
        mock_get.return_value = mock_resp

        ok, cooling, err = get_cooling_settings("192.168.100.23", "token_123")
        self.assertTrue(ok)
        self.assertIsNone(err)
        self.assertEqual(cooling["mode"]["param"], 100)

    @patch("requests.post")
    def test_set_manual_fan_duty_clamped(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        # Duty clamped to 100
        ok, err = set_manual_fan_duty("192.168.100.23", "token_123", 110)
        self.assertTrue(ok)
        mock_post.assert_called_with(
            "http://192.168.100.23/api/v1/settings",
            headers={
                "Authorization": "Bearer token_123",
                "Content-Type": "application/json",
            },
            json={"miner": {"cooling": {"mode": {"name": "manual", "param": 100}}}},
            timeout=DEFAULT_HTTP_TIMEOUT,
        )

        # Duty clamped to 40
        ok, err = set_manual_fan_duty("192.168.100.23", "token_123", 25)
        self.assertTrue(ok)
        mock_post.assert_called_with(
            "http://192.168.100.23/api/v1/settings",
            headers={
                "Authorization": "Bearer token_123",
                "Content-Type": "application/json",
            },
            json={"miner": {"cooling": {"mode": {"name": "manual", "param": 40}}}},
            timeout=DEFAULT_HTTP_TIMEOUT,
        )

    @patch("app.vnish.client.lock_miner")
    @patch("app.vnish.client.set_manual_fan_duty")
    @patch("app.vnish.client.unlock_miner")
    def test_safe_set_fan_duty_always_locks(self, mock_unlock, mock_set, mock_lock):
        mock_unlock.return_value = (True, "active_token_123", None)
        mock_set.return_value = (True, None)
        mock_lock.return_value = True

        ok, err = safe_set_fan_duty("192.168.100.23", "admin", 85)
        self.assertTrue(ok)
        mock_unlock.assert_called_once_with("192.168.100.23", "admin", timeout=DEFAULT_HTTP_TIMEOUT)
        mock_set.assert_called_once_with("192.168.100.23", "active_token_123", 85, timeout=DEFAULT_HTTP_TIMEOUT)
        mock_lock.assert_called_once_with("192.168.100.23", "active_token_123", timeout=DEFAULT_HTTP_TIMEOUT)

    @patch("app.vnish.client.lock_miner")
    @patch("app.vnish.client.set_manual_fan_duty")
    @patch("app.vnish.client.unlock_miner")
    def test_safe_set_fan_duty_locks_on_exception(self, mock_unlock, mock_set, mock_lock):
        mock_unlock.return_value = (True, "active_token_123", None)
        mock_set.side_effect = RuntimeError("Network partition mid-set")

        with self.assertRaises(RuntimeError):
            safe_set_fan_duty("192.168.100.23", "admin", 85)

        # Guarantee lock_miner was called despite the exception
        mock_lock.assert_called_once_with("192.168.100.23", "active_token_123", timeout=DEFAULT_HTTP_TIMEOUT)

    @patch("requests.get")
    def test_get_summary_cooling(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "miner": {
                "cooling": {
                    "fan_duty": 100,
                    "fan_num": 4,
                    "settings": {"mode": {"name": "manual"}},
                }
            }
        }
        mock_get.return_value = mock_resp

        ok, cooling, err = get_summary_cooling("192.168.100.23")
        self.assertTrue(ok)
        self.assertIsNone(err)
        self.assertEqual(cooling["fan_duty"], 100)

    @patch("requests.get")
    def test_get_available_presets_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {"name": "2300W", "power": 2300},
            {"name": "2500W", "power": 2500},
            {"name": "2700W", "power": 2700},
        ]
        mock_get.return_value = mock_resp

        ok, presets, err = get_available_presets("192.168.100.23", "token_123")
        self.assertTrue(ok)
        self.assertIsNone(err)
        self.assertEqual(len(presets), 3)
        self.assertEqual(presets[1]["name"], "2500W")
        mock_get.assert_called_once_with(
            "http://192.168.100.23/api/v1/presets",
            headers={"Authorization": "Bearer token_123"},
            timeout=DEFAULT_HTTP_TIMEOUT,
        )

    @patch("requests.get")
    def test_get_available_presets_timeout(self, mock_get):
        mock_get.side_effect = requests.exceptions.Timeout("Connection timeout")

        ok, presets, err = get_available_presets("192.168.100.23", "token_123")
        self.assertFalse(ok)
        self.assertIsNone(presets)
        self.assertEqual(err, "connection_timeout")

    @patch("requests.post")
    def test_set_miner_preset_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        ok, err = set_miner_preset("192.168.100.23", "token_123", "2500W")
        self.assertTrue(ok)
        self.assertIsNone(err)
        mock_post.assert_called_once_with(
            "http://192.168.100.23/api/v1/settings",
            headers={
                "Authorization": "Bearer token_123",
                "Content-Type": "application/json",
            },
            json={"miner": {"overclock": {"preset": "2500"}}},
            timeout=DEFAULT_HTTP_TIMEOUT,
        )

    @patch("app.vnish.client.lock_miner")
    @patch("app.vnish.client.set_miner_preset")
    @patch("app.vnish.client.unlock_miner")
    def test_safe_set_miner_preset_always_locks(self, mock_unlock, mock_set, mock_lock):
        mock_unlock.return_value = (True, "token_abc", None)
        mock_set.return_value = (True, None)
        mock_lock.return_value = True

        ok, err = safe_set_miner_preset("192.168.100.23", "admin", "2500W")
        self.assertTrue(ok)
        mock_unlock.assert_called_once_with("192.168.100.23", "admin", timeout=DEFAULT_HTTP_TIMEOUT)
        mock_set.assert_called_once_with("192.168.100.23", "token_abc", "2500W", timeout=DEFAULT_HTTP_TIMEOUT)
        mock_lock.assert_called_once_with("192.168.100.23", "token_abc", timeout=DEFAULT_HTTP_TIMEOUT)

    @patch("requests.get")
    def test_get_overclock_settings_switcher_enabled(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "miner": {
                "overclock": {
                    "preset": "2300",
                    "preset_switcher": {
                        "enabled": True,
                        "top_preset": "2700",
                        "min_preset": "1740",
                        "rise_temp": 79,
                        "decrease_temp": 84,
                        "check_time": 300,
                    },
                }
            }
        }
        mock_get.return_value = mock_resp

        ok, data, err = get_overclock_settings("192.168.100.25", "token_123")
        self.assertTrue(ok)
        self.assertIsNone(err)
        self.assertEqual(data["preset"], "2300")
        self.assertTrue(data["switcher_enabled"])
        self.assertEqual(data["top_preset"], "2700")
        self.assertEqual(data["target_power_w"], 2700.0)
        self.assertEqual(data["rise_temp"], 79)
        self.assertEqual(data["decrease_temp"], 84)

    @patch("requests.get")
    def test_get_overclock_settings_switcher_disabled(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "miner": {
                "overclock": {
                    "preset": "2500",
                    "preset_switcher": {
                        "enabled": False,
                        "top_preset": "2700",
                    },
                }
            }
        }
        mock_get.return_value = mock_resp

        ok, data, err = get_overclock_settings("192.168.100.25", "token_123")
        self.assertTrue(ok)
        self.assertIsNone(err)
        self.assertEqual(data["preset"], "2500")
        self.assertFalse(data["switcher_enabled"])
        self.assertEqual(data["target_power_w"], 2500.0)

    @patch("app.vnish.client.lock_miner")
    @patch("app.vnish.client.get_overclock_settings")
    @patch("app.vnish.client.unlock_miner")
    def test_safe_get_overclock_settings_always_locks(self, mock_unlock, mock_get_oc, mock_lock):
        mock_unlock.return_value = (True, "tok_xyz", None)
        mock_get_oc.return_value = (True, {"target_power_w": 2700.0}, None)
        mock_lock.return_value = True

        ok, data, err = safe_get_overclock_settings("192.168.100.25", "admin")
        self.assertTrue(ok)
        self.assertEqual(data["target_power_w"], 2700.0)
        mock_unlock.assert_called_once_with("192.168.100.25", "admin", timeout=DEFAULT_HTTP_TIMEOUT)
        mock_get_oc.assert_called_once_with("192.168.100.25", "tok_xyz", timeout=DEFAULT_HTTP_TIMEOUT)
        mock_lock.assert_called_once_with("192.168.100.25", "tok_xyz", timeout=DEFAULT_HTTP_TIMEOUT)



if __name__ == "__main__":
    unittest.main()

