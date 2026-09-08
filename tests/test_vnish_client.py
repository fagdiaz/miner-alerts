import unittest
from unittest.mock import MagicMock, patch

import requests

from app.vnish_client import (
    DEFAULT_HTTP_TIMEOUT,
    get_cooling_settings,
    get_summary_cooling,
    lock_miner,
    mask_secret,
    safe_set_fan_duty,
    set_manual_fan_duty,
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

    @patch("app.vnish_client.lock_miner")
    @patch("app.vnish_client.set_manual_fan_duty")
    @patch("app.vnish_client.unlock_miner")
    def test_safe_set_fan_duty_always_locks(self, mock_unlock, mock_set, mock_lock):
        mock_unlock.return_value = (True, "active_token_123", None)
        mock_set.return_value = (True, None)
        mock_lock.return_value = True

        ok, err = safe_set_fan_duty("192.168.100.23", "admin", 85)
        self.assertTrue(ok)
        mock_unlock.assert_called_once_with("192.168.100.23", "admin", timeout=DEFAULT_HTTP_TIMEOUT)
        mock_set.assert_called_once_with("192.168.100.23", "active_token_123", 85, timeout=DEFAULT_HTTP_TIMEOUT)
        mock_lock.assert_called_once_with("192.168.100.23", "active_token_123", timeout=DEFAULT_HTTP_TIMEOUT)

    @patch("app.vnish_client.lock_miner")
    @patch("app.vnish_client.set_manual_fan_duty")
    @patch("app.vnish_client.unlock_miner")
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


if __name__ == "__main__":
    unittest.main()
