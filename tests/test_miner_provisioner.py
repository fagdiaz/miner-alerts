"""Unit tests for Miner Provisioner module (Spec 076)."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.governance.miner_provisioner import (
    find_profile_path,
    provision_miner_from_profile,
)


class TestMinerProvisioner(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.sample_profile = {
            "miner": {
                "pools": [{"url": "stratum+tcp://stratum.binance.com:8888", "user": "fagdiaz.19216810024"}],
                "overclock": {
                    "preset": "2300",
                    "preset_switcher": {"top_preset": "2700"},
                    "chains": [{"chips": [1, 2, 3]}],
                },
            }
        }
        self.profile_path = Path(self.tmp_dir) / "S19JPRO-24.json"
        with open(self.profile_path, "w", encoding="utf-8") as f:
            json.dump(self.sample_profile, f)

    def tearDown(self):
        try:
            if self.profile_path.exists():
                self.profile_path.unlink()
            os.rmdir(self.tmp_dir)
        except Exception:
            pass

    def test_find_profile_path_resolution(self):
        # By canonical name
        p1 = find_profile_path("S19JPRO-24", profiles_dir=self.tmp_dir)
        self.assertIsNotNone(p1)
        self.assertEqual(p1.name, "S19JPRO-24.json")

        # By short numeric name
        p2 = find_profile_path("24", profiles_dir=self.tmp_dir)
        self.assertIsNotNone(p2)
        self.assertEqual(p2.name, "S19JPRO-24.json")

        # Nonexistent miner
        p3 = find_profile_path("99", profiles_dir=self.tmp_dir)
        self.assertIsNone(p3)

    def test_provision_fails_if_profile_missing(self):
        ok, msg = provision_miner_from_profile("192.168.100.99", "99", profiles_dir=self.tmp_dir)
        self.assertFalse(ok)
        self.assertIn("ERROR_PROFILE_NOT_FOUND", msg)

    def test_provision_fails_if_profile_invalid(self):
        bad_path = Path(self.tmp_dir) / "S19JPRO-98.json"
        with open(bad_path, "w", encoding="utf-8") as f:
            f.write("not_valid_json")
        try:
            ok, msg = provision_miner_from_profile("192.168.100.98", "98", profiles_dir=self.tmp_dir)
            self.assertFalse(ok)
            self.assertIn("ERROR_PROFILE_CORRUPT", msg)
        finally:
            if bad_path.exists():
                bad_path.unlink()

    @patch("app.governance.miner_provisioner.unlock_miner", return_value=(False, None, "bad_pw"))
    def test_provision_fails_if_unlock_rejected(self, mock_unlock):
        ok, msg = provision_miner_from_profile("192.168.100.24", "24", profiles_dir=self.tmp_dir)
        self.assertFalse(ok)
        self.assertIn("ERROR_UNLOCK_FAILED", msg)

    @patch("app.governance.miner_provisioner.lock_miner")
    @patch("app.governance.miner_provisioner.restart_mining", return_value=(True, None))
    @patch("requests.post")
    @patch("app.governance.miner_provisioner.unlock_miner", return_value=(True, "token_xyz", None))
    def test_provision_miner_success(self, mock_unlock, mock_post, mock_restart, mock_lock):
        resp = MagicMock()
        resp.status_code = 200
        mock_post.return_value = resp

        ok, msg = provision_miner_from_profile(
            host="192.168.100.24",
            miner_name="24",
            profiles_dir=self.tmp_dir,
            restart_after=True,
        )
        self.assertTrue(ok)
        self.assertIn("PROVISION_SUCCESS", msg)

        # Verify POST payload sent to settings
        mock_post.assert_called_once()
        call_url = mock_post.call_args[0][0]
        self.assertIn("192.168.100.24/api/v1/settings", call_url)
        call_json = mock_post.call_args[1]["json"]
        self.assertIn("miner", call_json)
        self.assertEqual(call_json["miner"]["overclock"]["preset"], "2300")

        # Verify restart and lock
        mock_restart.assert_called_once()
        mock_lock.assert_called_once_with("192.168.100.24", "token_xyz", timeout=2.0)


if __name__ == "__main__":
    unittest.main()
