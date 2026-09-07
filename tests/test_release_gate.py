"""Unit tests for V2 Release Stabilization Gate (Spec 029).

Verifies:
- T001: Terminal disposition audit across Specs 021-028.
- T002: Deterministic runtime-payload digest and exclusion of secrets/runtime files.
- T003: Completeness of regression matrix R001-R025.
- T004: Invariant clock-reset behavior (code changes change digest; doc changes preserve digest).
- T005: Manifest sanitization (zero secrets, credentials, or absolute paths).
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.release_audit import (
    TERMINAL_DISPOSITIONS,
    ReleaseAudit,
    audit_matrix_completeness,
    audit_terminal_dispositions,
    compute_runtime_payload_digest,
    sanitize_manifest,
)


class TestReleaseGateTerminalDispositions(unittest.TestCase):
    """Tests for T001 terminal disposition audit."""

    def test_current_repo_specs_dispositions_all_terminal(self):
        """Current Specs 021-028 in the repository must all be terminal."""
        project_root = Path(__file__).resolve().parents[1]
        dispositions = audit_terminal_dispositions(project_root)

        expected_specs = [
            "021-monitor-liveness-watchdog",
            "022-adaptive-acquisition",
            "023-incident-evidence-fusion",
            "024-electrical-source-discovery",
            "025-prometheus-metrics",
            "026-hashcore-capability-inventory",
            "027-operator-interface-decision",
            "028-backup-retention-restore",
        ]
        for spec_key in expected_specs:
            self.assertIn(spec_key, dispositions, f"Missing disposition for {spec_key}")
            state = dispositions[spec_key]["state"]
            self.assertIn(
                state,
                TERMINAL_DISPOSITIONS,
                f"Spec {spec_key} has non-terminal state '{state}'",
            )

    def test_rejects_non_terminal_disposition(self):
        """If any spec is planned, in_progress, or observation_pending, freeze is rejected."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            specs_dir = tmp_path / "specs"
            specs_dir.mkdir()

            # Create a mock spec that is still observation_pending
            spec_dir = specs_dir / "021-monitor-liveness-watchdog"
            spec_dir.mkdir()
            (spec_dir / "evidence.md").write_text(
                "# Evidence\nStatus: observation_pending\nGate D+3 pending",
                encoding="utf-8",
            )

            with self.assertRaises(ValueError) as ctx:
                audit_terminal_dispositions(tmp_path)
            self.assertIn("non-terminal", str(ctx.exception).lower())

    def test_rejects_missing_evidence_file(self):
        """If a spec directory lacks evidence.md, freeze is rejected."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            specs_dir = tmp_path / "specs"
            specs_dir.mkdir()
            spec_dir = specs_dir / "021-monitor-liveness-watchdog"
            spec_dir.mkdir()

            with self.assertRaises(FileNotFoundError):
                audit_terminal_dispositions(tmp_path)


class TestReleaseGateRuntimePayloadDigest(unittest.TestCase):
    """Tests for T002/T005 deterministic runtime payload digest and clock-reset invariants."""

    def test_digest_deterministic(self):
        """Computing digest twice on the same tree yields identical hash."""
        project_root = Path(__file__).resolve().parents[1]
        digest1, entries1 = compute_runtime_payload_digest(project_root)
        digest2, entries2 = compute_runtime_payload_digest(project_root)

        self.assertEqual(digest1, digest2)
        self.assertEqual(len(entries1), len(entries2))
        self.assertGreater(len(entries1), 5)

    def test_excludes_secrets_runtime_data_and_tests(self):
        """Payload must exclude config.json, state.json, *.db, logs, tests, specs, docs."""
        project_root = Path(__file__).resolve().parents[1]
        _, entries = compute_runtime_payload_digest(project_root)

        paths = [e["path"] for e in entries]
        for p in paths:
            self.assertFalse(p.startswith("tests/"), f"Test file included: {p}")
            self.assertFalse(p.startswith("specs/"), f"Spec file included: {p}")
            self.assertFalse(p.startswith("docs/"), f"Doc file included: {p}")
            self.assertFalse(p.endswith("config.json"), f"Local config included: {p}")
            self.assertFalse(p.endswith("state.json"), f"Local state included: {p}")
            self.assertFalse(p.endswith(".db"), f"Database file included: {p}")
            self.assertFalse(p.endswith(".log"), f"Log file included: {p}")

        # Ensure example config is included
        self.assertIn("app/config.example.json", paths)
        # Ensure main app file is included
        self.assertIn("app/miner_monitor.py", paths)

    def test_code_change_alters_payload_digest(self):
        """Modifying a runtime code file alters the payload digest (clock reset)."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            app_dir = tmp_path / "app"
            app_dir.mkdir()
            file_path = app_dir / "miner_monitor.py"
            file_path.write_text("print('v1')", encoding="utf-8")

            digest1, _ = compute_runtime_payload_digest(tmp_path)

            # Modify file
            file_path.write_text("print('v2')", encoding="utf-8")
            digest2, _ = compute_runtime_payload_digest(tmp_path)

            self.assertNotEqual(digest1, digest2)

    def test_docs_change_preserves_payload_digest(self):
        """Modifying a docs file does NOT alter the payload digest (observation preserved)."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            app_dir = tmp_path / "app"
            app_dir.mkdir()
            (app_dir / "miner_monitor.py").write_text("print('v1')", encoding="utf-8")

            docs_dir = tmp_path / "docs"
            docs_dir.mkdir()
            doc_file = docs_dir / "README.md"
            doc_file.write_text("Doc v1", encoding="utf-8")

            digest1, _ = compute_runtime_payload_digest(tmp_path)

            # Modify doc file
            doc_file.write_text("Doc v2 modified", encoding="utf-8")
            digest2, _ = compute_runtime_payload_digest(tmp_path)

            self.assertEqual(digest1, digest2)


class TestReleaseGateMatrixCompleteness(unittest.TestCase):
    """Tests for T003/T005 regression matrix completeness."""

    def test_matrix_requires_all_25_rows(self):
        """Matrix must have exactly R001 through R025."""
        rows = [
            {"id": f"R{i:03d}", "area": "Test", "check": "Desc", "status": "pass", "evidence_ref": "ref"}
            for i in range(1, 26)
        ]
        result = audit_matrix_completeness(rows)
        self.assertTrue(result["complete"])
        self.assertEqual(len(result["missing_ids"]), 0)

    def test_matrix_detects_missing_rows(self):
        """Missing check IDs are detected and fail completeness."""
        rows = [
            {"id": f"R{i:03d}", "area": "Test", "check": "Desc", "status": "pass", "evidence_ref": "ref"}
            for i in range(1, 24)  # Missing R024 and R025
        ]
        result = audit_matrix_completeness(rows)
        self.assertFalse(result["complete"])
        self.assertIn("R024", result["missing_ids"])
        self.assertIn("R025", result["missing_ids"])

    def test_matrix_validates_row_fields(self):
        """Every row must have id, area, check, status, evidence_ref."""
        rows = [
            {"id": "R001", "area": "Test", "check": "Desc", "status": "pass"}  # Missing evidence_ref
        ]
        result = audit_matrix_completeness(rows)
        self.assertFalse(result["complete"])
        self.assertIn("R001", result["invalid_rows"])

    def test_rejects_invalid_status(self):
        """Status must be pass, fail, blocked, or not_applicable."""
        rows = [
            {"id": "R001", "area": "Test", "check": "Desc", "status": "unknown_status", "evidence_ref": "ref"}
        ]
        result = audit_matrix_completeness(rows)
        self.assertFalse(result["complete"])
        self.assertIn("R001", result["invalid_rows"])


class TestReleaseGateSanitization(unittest.TestCase):
    """Tests for T005 manifest sanitization."""

    def test_sanitize_manifest_redacts_credentials_and_ips(self):
        """Sanitizer redacts bot tokens, sensitive IPs, and full local disk paths."""
        raw_manifest = {
            "token": "123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ",
            "host": "192.168.1.50",
            "path": "F:\\02-ASIC - mineros\\miner-alerts\\secret.key",
            "safe_entry": "app/miner_monitor.py",
        }
        sanitized = sanitize_manifest(raw_manifest)
        sanitized_str = json.dumps(sanitized)

        self.assertNotIn("123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ", sanitized_str)
        self.assertNotIn("192.168.1.50", sanitized_str)
        self.assertNotIn("F:\\02-ASIC - mineros", sanitized_str)
        self.assertIn("app/miner_monitor.py", sanitized_str)


if __name__ == "__main__":
    unittest.main()
