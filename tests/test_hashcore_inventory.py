"""Unit tests for Hashcore Capability Inventory (Spec 026).

Verifies:
- Metadata-only mode starts zero subprocesses.
- Absent, empty, or mismatched allowlists result in BLOCKED status with zero subprocesses.
- Invalid argv (placeholders, IP addresses, credentials) is strictly rejected.
- Fingerprint changes invalidate allowlist approvals.
- Command risk classification rules (read-only, mutating, unknown).
- Subprocess execution constraints (shell=False, stdin=DEVNULL, no-window, 10s timeout, 64 KiB stream bound).
- Sanitization: zero absolute paths, secrets, or IP addresses in exported artifacts.
"""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# The module under test will be in tools.hashcore_inventory
from tools.hashcore_inventory import (
    CommandClassification,
    HashcoreInventory,
    InvocationApproval,
    classify_command,
    sanitize_text,
)


class TestHashcoreInventoryMetadataOnly(unittest.TestCase):
    """Tests for metadata-only mode and zero-process invariants (T004)."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.wrapper_path = Path(self.tmp_dir.name) / "toolkit_cli.bat"
        self.exe_path = Path(self.tmp_dir.name) / "hashcore-toolkit.exe"

        # Create dummy wrapper and executable files
        self.wrapper_content = b"@echo off\nhashcore-toolkit.exe cli %*\n"
        self.exe_content = b"\x4d\x5a" + b"\x00" * 1024  # Minimal MZ header mock

        self.wrapper_path.write_bytes(self.wrapper_content)
        self.exe_path.write_bytes(self.exe_content)

    def tearDown(self):
        self.tmp_dir.cleanup()

    @patch("subprocess.run")
    @patch("subprocess.Popen")
    def test_metadata_only_starts_zero_subprocesses(self, mock_popen, mock_run):
        """Metadata-only mode must never invoke subprocess."""
        inv = HashcoreInventory(
            wrapper_path=str(self.wrapper_path),
            executable_path=str(self.exe_path),
            mode="metadata_only",
        )
        report = inv.run()

        mock_run.assert_not_called()
        mock_popen.assert_not_called()

        self.assertEqual(report["mode"], "metadata_only")
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(len(report["invocations"]), 0)

        # Verify installation fields
        inst = report["installation"]
        self.assertEqual(inst["wrapper_basename"], "toolkit_cli.bat")
        self.assertEqual(inst["executable_basename"], "hashcore-toolkit.exe")
        self.assertEqual(inst["wrapper_size_bytes"], len(self.wrapper_content))
        self.assertEqual(inst["executable_size_bytes"], len(self.exe_content))
        self.assertTrue(len(inst["wrapper_sha256"]) == 64)
        self.assertTrue(len(inst["executable_sha256"]) == 64)
        self.assertEqual(inst["wrapper_shape"], "argv_passthrough")

        # Absolute paths must NOT be present in installation record
        self.assertNotIn(str(self.wrapper_path), json.dumps(inst))
        self.assertNotIn(self.tmp_dir.name, json.dumps(inst))

    @patch("subprocess.run")
    def test_absent_allowlist_starts_zero_subprocesses(self, mock_run):
        """When allowlist is absent or empty, tool returns blocked with 0 subprocesses."""
        inv = HashcoreInventory(
            wrapper_path=str(self.wrapper_path),
            executable_path=str(self.exe_path),
            mode="reviewed_invocation",
            allowlist_path=str(Path(self.tmp_dir.name) / "nonexistent_allowlist.json"),
        )
        report = inv.run()
        mock_run.assert_not_called()
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(len(report["invocations"]), 0)

    @patch("subprocess.run")
    def test_mismatched_fingerprint_starts_zero_subprocesses(self, mock_run):
        """If executable SHA256 does not match allowlist, starts zero subprocesses."""
        allowlist_data = {
            "entries": [
                {
                    "invocation_id": "test_version",
                    "wrapper_sha256": "wrong_wrapper_sha256" + "0" * 44,
                    "executable_sha256": "wrong_exe_sha256" + "0" * 48,
                    "argv": ["version"],
                    "timeout_seconds": 5,
                    "expected_exit_codes": [0],
                    "vendor_evidence_ref": "doc_v1",
                    "evidence_digest": "a" * 64,
                }
            ]
        }
        allowlist_file = Path(self.tmp_dir.name) / "allowlist.json"
        allowlist_file.write_text(json.dumps(allowlist_data), encoding="utf-8")

        inv = HashcoreInventory(
            wrapper_path=str(self.wrapper_path),
            executable_path=str(self.exe_path),
            mode="reviewed_invocation",
            allowlist_path=str(allowlist_file),
        )
        report = inv.run()
        mock_run.assert_not_called()
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(len(report["invocations"]), 0)

    def test_invalid_argv_rejection(self):
        """Allowlist entries with placeholders, miner IPs, or paths must be rejected."""
        invalid_argvs = [
            ["reboot", "{host}-{host}"],
            ["restart", "192.168.100.23"],
            ["config", "-s", "C:\\path\\settings.json"],
            ["login", "admin", "secret123"],
            [],  # empty
            ["status", "--miner-ip", "10.0.0.1"],
        ]
        for argv in invalid_argvs:
            with self.subTest(argv=argv):
                entry = InvocationApproval(
                    invocation_id="invalid_test",
                    wrapper_sha256="a" * 64,
                    executable_sha256="b" * 64,
                    argv=argv,
                    vendor_evidence_ref="ref",
                    evidence_digest="c" * 64,
                    timeout_seconds=5,
                    expected_exit_codes=[0],
                )
                valid, reason = entry.validate()
                self.assertFalse(valid, f"Expected invalid for argv={argv}, got reason={reason}")


class TestHashcoreCommandClassification(unittest.TestCase):
    """Tests for conservative command risk classification (T005)."""

    def test_mutating_commands(self):
        mutating = ["reboot", "restart", "flash", "set", "write", "tune", "config", "pause", "resume"]
        for cmd in mutating:
            with self.subTest(cmd=cmd):
                self.assertEqual(classify_command(cmd), CommandClassification.MUTATING)

    def test_read_only_commands(self):
        read_only = ["version", "help", "--help", "-h", "--version", "-v"]
        for cmd in read_only:
            with self.subTest(cmd=cmd):
                self.assertEqual(classify_command(cmd), CommandClassification.READ_ONLY)

    def test_unknown_commands_fail_closed(self):
        unknowns = ["status", "scan", "discover", "probe", "info", "random_unseen_cmd", ""]
        for cmd in unknowns:
            with self.subTest(cmd=cmd):
                self.assertEqual(classify_command(cmd), CommandClassification.UNKNOWN)


class TestHashcoreExecutionConstraints(unittest.TestCase):
    """Tests for execution bounds: timeout, 64 KiB stream bound, no-window (T005)."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.wrapper_path = Path(self.tmp_dir.name) / "toolkit_cli.bat"
        self.exe_path = Path(self.tmp_dir.name) / "hashcore-toolkit.exe"
        self.wrapper_path.write_bytes(b"@echo off\n")
        self.exe_path.write_bytes(b"dummy")

    def tearDown(self):
        self.tmp_dir.cleanup()

    @patch("subprocess.run")
    def test_execution_parameters(self, mock_run):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = b"Hashcore Toolkit 1.6.0\n"
        mock_proc.stderr = b""
        mock_run.return_value = mock_proc

        wrapper_hash = HashcoreInventory._compute_sha256(self.wrapper_path)
        exe_hash = HashcoreInventory._compute_sha256(self.exe_path)

        allowlist_data = {
            "entries": [
                {
                    "invocation_id": "inv_version",
                    "wrapper_sha256": wrapper_hash,
                    "executable_sha256": exe_hash,
                    "argv": ["version"],
                    "timeout_seconds": 5,
                    "expected_exit_codes": [0],
                    "vendor_evidence_ref": "ref1",
                    "evidence_digest": "d" * 64,
                }
            ]
        }
        allowlist_file = Path(self.tmp_dir.name) / "allowlist.json"
        allowlist_file.write_text(json.dumps(allowlist_data), encoding="utf-8")

        inv = HashcoreInventory(
            wrapper_path=str(self.wrapper_path),
            executable_path=str(self.exe_path),
            mode="reviewed_invocation",
            allowlist_path=str(allowlist_file),
        )
        report = inv.run()

        mock_run.assert_called_once()
        _, kwargs = mock_run.call_args

        self.assertFalse(kwargs.get("shell"), "shell must be False")
        self.assertEqual(kwargs.get("stdin"), subprocess.DEVNULL, "stdin must be DEVNULL")
        self.assertEqual(kwargs.get("timeout"), 5, "timeout must match allowlist")
        if os.name == "nt":
            self.assertTrue(kwargs.get("creationflags", 0) & 0x08000000, "CREATE_NO_WINDOW must be set")

        self.assertEqual(len(report["invocations"]), 1)
        inv_record = report["invocations"][0]
        self.assertEqual(inv_record["exit_code"], 0)
        self.assertFalse(inv_record["timed_out"])
        self.assertFalse(inv_record["stdout_truncated"])

    @patch("subprocess.run")
    def test_stream_truncation_at_64_kib(self, mock_run):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = b"A" * (70 * 1024)  # 70 KiB > 64 KiB
        mock_proc.stderr = b"B" * (65 * 1024)
        mock_run.return_value = mock_proc

        wrapper_hash = HashcoreInventory._compute_sha256(self.wrapper_path)
        exe_hash = HashcoreInventory._compute_sha256(self.exe_path)

        allowlist_data = {
            "entries": [
                {
                    "invocation_id": "inv_large",
                    "wrapper_sha256": wrapper_hash,
                    "executable_sha256": exe_hash,
                    "argv": ["version"],
                    "timeout_seconds": 10,
                    "expected_exit_codes": [0],
                    "vendor_evidence_ref": "ref",
                    "evidence_digest": "e" * 64,
                }
            ]
        }
        allowlist_file = Path(self.tmp_dir.name) / "allowlist.json"
        allowlist_file.write_text(json.dumps(allowlist_data), encoding="utf-8")

        inv = HashcoreInventory(
            wrapper_path=str(self.wrapper_path),
            executable_path=str(self.exe_path),
            mode="reviewed_invocation",
            allowlist_path=str(allowlist_file),
        )
        report = inv.run()

        inv_record = report["invocations"][0]
        self.assertTrue(inv_record["stdout_truncated"])
        self.assertTrue(inv_record["stderr_truncated"])
        self.assertEqual(inv_record["stdout_bytes"], 65536)
        self.assertEqual(inv_record["stderr_bytes"], 65536)


class TestHashcoreSanitization(unittest.TestCase):
    """Tests for artifact sanitization and secret protection (T006)."""

    def test_sanitize_paths_and_ips(self):
        raw = "Error on 192.168.100.25 at C:\\Program Files\\Hashcore\\Toolkit\\config.json with secret token=abc12345"
        sanitized = sanitize_text(raw)
        self.assertNotIn("192.168.100.25", sanitized)
        self.assertNotIn("C:\\Program Files", sanitized)
        self.assertNotIn("abc12345", sanitized)
        self.assertIn("[IP_REDACTED]", sanitized)
        self.assertIn("[PATH_REDACTED]", sanitized)


if __name__ == "__main__":
    unittest.main()
