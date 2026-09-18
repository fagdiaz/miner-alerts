"""Unit tests for FirmwareFlasher module (Spec 076)."""

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import requests

from app.network.firmware_flasher import (
    DEFAULT_PACKAGE_PATH,
    FirmwareFlasher,
    flash_bitmain_nand,
    is_stock_bitmain,
)


class TestFirmwareFlasher(unittest.TestCase):
    def setUp(self):
        # Create a dummy tarball file for tests
        self.tmp_fd, self.tmp_path = tempfile.mkstemp(suffix=".tar.gz")
        with open(self.tmp_path, "wb") as f:
            f.write(b"dummy_tarball_payload")

    def tearDown(self):
        try:
            os.close(self.tmp_fd)
            if os.path.exists(self.tmp_path):
                os.remove(self.tmp_path)
        except Exception:
            pass

    @patch("requests.get")
    def test_is_stock_bitmain_detected_via_digest_header(self, mock_get):
        resp = MagicMock()
        resp.status_code = 401
        resp.headers = {
            "WWW-Authenticate": 'Digest realm="antMiner Configuration", nonce="12345"',
            "Server": "lighttpd/1.4.32",
        }
        mock_get.return_value = resp

        self.assertTrue(is_stock_bitmain("192.168.100.24"))

    @patch("requests.get")
    def test_is_stock_bitmain_detected_via_lighttpd_server(self, mock_get):
        resp = MagicMock()
        resp.status_code = 200
        resp.headers = {"Server": "lighttpd/1.4.32"}
        mock_get.return_value = resp

        self.assertTrue(is_stock_bitmain("192.168.100.24"))

    @patch("requests.get")
    def test_is_stock_bitmain_returns_false_for_vnish(self, mock_get):
        resp = MagicMock()
        resp.status_code = 200
        resp.headers = {"Server": "nginx"}
        mock_get.return_value = resp

        self.assertFalse(is_stock_bitmain("192.168.100.23"))

    def test_flash_bitmain_nand_fails_if_package_missing(self):
        ok, msg = flash_bitmain_nand("192.168.100.24", package_path="nonexistent_file_path.tar.gz")
        self.assertFalse(ok)
        self.assertIn("ERROR_PACKAGE_NOT_FOUND", msg)

    @patch("app.network.firmware_flasher.is_stock_bitmain", return_value=False)
    def test_flash_bitmain_nand_aborts_if_not_stock_bitmain(self, mock_probe):
        ok, msg = flash_bitmain_nand("192.168.100.24", package_path=self.tmp_path)
        self.assertFalse(ok)
        self.assertIn("ABORTED_NOT_STOCK_BITMAIN", msg)

    @patch("app.network.firmware_flasher.is_stock_bitmain", return_value=True)
    @patch("requests.post")
    def test_flash_bitmain_nand_success(self, mock_post, mock_probe):
        resp = MagicMock()
        resp.status_code = 200
        resp.text = "Update completed successfully"
        mock_post.return_value = resp

        ok, msg = flash_bitmain_nand("192.168.100.24", package_path=self.tmp_path)
        self.assertTrue(ok)
        self.assertIn("Flasheo completado exitosamente", msg)
        mock_post.assert_called_once()
        call_url = mock_post.call_args[0][0]
        self.assertIn("192.168.100.24/cgi-bin/upgrade.cgi", call_url)

    @patch("app.network.firmware_flasher.is_stock_bitmain", return_value=True)
    @patch("requests.post")
    def test_flash_bitmain_nand_auth_failure(self, mock_post, mock_probe):
        resp = MagicMock()
        resp.status_code = 401
        resp.text = "Unauthorized"
        mock_post.return_value = resp

        ok, msg = flash_bitmain_nand("192.168.100.24", package_path=self.tmp_path)
        self.assertFalse(ok)
        self.assertIn("ERROR_AUTH_FAILED", msg)

    @patch("app.network.firmware_flasher.is_stock_bitmain", return_value=True)
    @patch("requests.post", side_effect=requests.exceptions.Timeout("Read timed out"))
    def test_flash_bitmain_nand_handles_timeout_as_reboot(self, mock_post, mock_probe):
        ok, msg = flash_bitmain_nand("192.168.100.24", package_path=self.tmp_path)
        self.assertTrue(ok)
        self.assertIn("TIMEOUT_OR_REBOOT", msg)

    @patch("app.network.firmware_flasher.is_stock_bitmain", return_value=True)
    @patch("requests.post")
    def test_firmware_flasher_class_wrapper(self, mock_post, mock_probe):
        resp = MagicMock()
        resp.status_code = 200
        mock_post.return_value = resp

        flasher = FirmwareFlasher(package_path=self.tmp_path)
        self.assertTrue(flasher.is_target_stock_bitmain("192.168.100.24"))

        ok, msg = flasher.flash_miner("192.168.100.24")
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
