"""Unit tests for config audit tool (Spec 073)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.audit_config import audit_config_dicts, audit_config_files


class TestAuditConfig(unittest.TestCase):
    def test_identical_configs_pass(self) -> None:
        ref = {
            "telegram": {"bot_token": "abc", "chat_id": "123"},
            "poll_seconds": 30,
            "threshold_ths": 60.0,
            "miners": [{"name": "M1", "host": "192.168.1.10"}],
        }
        ok, errors, warnings = audit_config_dicts(ref, ref)
        self.assertTrue(ok)
        self.assertEqual(len(errors), 0)

    def test_missing_critical_key_fails(self) -> None:
        ref = {"poll_seconds": 30, "miners": [{"name": "M1", "host": "1.1.1.1"}]}
        tgt = {"poll_seconds": 30}  # missing critical 'miners'
        ok, errors, warnings = audit_config_dicts(ref, tgt)
        self.assertFalse(ok)
        self.assertTrue(any("miners" in e for e in errors))

    def test_missing_optional_key_warns_in_non_strict(self) -> None:
        ref = {
            "poll_seconds": 30,
            "optional_feature_enabled": True,
        }
        tgt = {"poll_seconds": 30}
        ok, errors, warnings = audit_config_dicts(ref, tgt, strict=False)
        self.assertTrue(ok)
        self.assertTrue(any("optional_feature_enabled" in w for w in warnings))

    def test_missing_optional_key_fails_in_strict(self) -> None:
        ref = {
            "poll_seconds": 30,
            "optional_feature_enabled": True,
        }
        tgt = {"poll_seconds": 30}
        ok, errors, warnings = audit_config_dicts(ref, tgt, strict=True)
        self.assertFalse(ok)
        self.assertTrue(any("optional_feature_enabled" in e for e in errors))

    def test_type_mismatch_fails(self) -> None:
        ref = {"poll_seconds": 30}
        tgt = {"poll_seconds": "thirty"}  # string instead of int
        ok, errors, warnings = audit_config_dicts(ref, tgt)
        self.assertFalse(ok)
        self.assertTrue(any("Type mismatch" in e for e in errors))

    def test_int_and_float_are_compatible_numbers(self) -> None:
        ref = {"threshold_ths": 60.0}
        tgt = {"threshold_ths": 60}  # int instead of float
        ok, errors, warnings = audit_config_dicts(ref, tgt)
        self.assertTrue(ok)
        self.assertEqual(len(errors), 0)

    def test_bool_is_not_compatible_with_number(self) -> None:
        ref = {"threshold_ths": 60.0}
        tgt = {"threshold_ths": True}  # True is bool
        ok, errors, warnings = audit_config_dicts(ref, tgt)
        self.assertFalse(ok)
        self.assertTrue(any("Type mismatch" in e for e in errors))

    def test_detects_placeholder_credentials(self) -> None:
        ref = {"telegram": {"bot_token": "PONER_TOKEN"}}
        tgt = {"telegram": {"bot_token": "PONER_TOKEN"}}
        ok, errors, warnings = audit_config_dicts(ref, tgt)
        self.assertTrue(ok)
        self.assertTrue(any("Placeholder" in w for w in warnings))

    def test_detects_unknown_keys(self) -> None:
        ref = {"poll_seconds": 30}
        tgt = {"poll_seconds": 30, "unsupported_legacy_key": 123}
        ok, errors, warnings = audit_config_dicts(ref, tgt)
        self.assertTrue(ok)
        self.assertTrue(any("unsupported_legacy_key" in w for w in warnings))

    def test_miner_missing_host_or_ip_fails(self) -> None:
        ref = {"miners": []}
        tgt = {"miners": [{"name": "BadMiner"}]}  # no host or ip
        ok, errors, warnings = audit_config_dicts(ref, tgt)
        self.assertFalse(ok)
        self.assertTrue(any("missing 'host' or 'ip'" in e for e in errors))

    def test_miner_with_ip_passes(self) -> None:
        ref = {"miners": []}
        tgt = {"miners": [{"name": "GoodMiner", "ip": "192.168.1.50"}]}
        ok, errors, warnings = audit_config_dicts(ref, tgt)
        self.assertTrue(ok)
        self.assertEqual(len(errors), 0)

    def test_audit_config_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            ref_path = Path(tmp_dir) / "ref.json"
            tgt_path = Path(tmp_dir) / "tgt.json"

            ref_path.write_text(json.dumps({"poll_seconds": 30}), encoding="utf-8")
            tgt_path.write_text(json.dumps({"poll_seconds": 30}), encoding="utf-8")

            ok, errors, warnings = audit_config_files(ref_path, tgt_path)
            self.assertTrue(ok)

    def test_audit_config_main_with_config_alias(self) -> None:
        from unittest import mock
        from tools import audit_config
        with tempfile.TemporaryDirectory() as tmp_dir:
            ref_path = Path(tmp_dir) / "ref.json"
            tgt_path = Path(tmp_dir) / "tgt.json"
            ref_path.write_text(json.dumps({"poll_seconds": 30}), encoding="utf-8")
            tgt_path.write_text(json.dumps({"poll_seconds": 30}), encoding="utf-8")

            argv = ["audit_config.py", "--reference", str(ref_path), "--config", str(tgt_path)]
            with mock.patch.object(audit_config.sys, "argv", argv):
                exit_code = audit_config.main()
                self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
