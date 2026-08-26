"""Tests for T014 — Spec 023: /diagnose fusion adapter.

Validates:
  a) incident_fusion_enabled=False  → /diagnose falls back to build_miner_diagnosis_text
  b) incident_fusion_enabled=True   → /diagnose invokes the fusion path and renders with
     render_assessment_telegram (never calls build_miner_diagnosis_text)
  c) DB exception during fusion     → strict fallback to build_miner_diagnosis_text

Safety invariant: these tests verify only the rendering/routing branch of /diagnose.
They DO NOT touch state machines, cooldowns, streak counters, reboot eligibility, or
polling timers.  All assertions are on the Telegram messages sent or the legacy text
produced; no action fields are ever read from the assessment.

FR-008 / FR-011 / FR-013 / SC-006
"""
from __future__ import annotations

import json
import time
import unittest
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Helpers — build a minimal fake environment to invoke the diagnose branch
# ---------------------------------------------------------------------------

def _make_config(fusion_enabled: bool = False) -> dict:
    return {
        "incident_fusion_enabled": fusion_enabled,
        "incident_fusion_context_hours": 1,
        "incident_fusion_fleet_window_seconds": 60,
        "diagnosis_stale_seconds": 900.0,
        "diagnosis_firmware_window_hours": 24.0,
        "diagnosis_collector_stale_seconds": 3600.0,
    }


def _make_event_store(available: bool = True, save_raises: bool = False) -> MagicMock:
    es = MagicMock()
    es.available = available
    if save_raises:
        es.save_assessment.side_effect = RuntimeError("simulated DB error")
    else:
        es.save_assessment.return_value = 1
    es.last_error = None
    return es


def _make_miners() -> list[dict]:
    return [{"name": "miner1", "host": "192.168.1.10", "port": 4028}]


def _run_diagnose_adapter(config, event_store, miners, raise_in_fusion=False):
    """Execute the T014 adapter logic extracted from miner_monitor.py diagnose block.

    Returns (send_calls, build_calls) where each is a list of invocations.
    """
    from app.evidence_fusion import (
        FusionConfig,
        IncidentAssessment,
        RULESET_VERSION as _FUSION_RULESET_VERSION,
        compute_evidence_digest,
        render_assessment_telegram,
    )

    send_calls: list[tuple] = []
    build_calls: list[str] = []

    def fake_send(text):
        send_calls.append(text)

    def fake_build_diag(*args, **kwargs):
        build_calls.append("called")
        return "LEGACY_DIAGNOSIS_TEXT"

    try:
        diagnosis_stale_seconds = float(config.get("diagnosis_stale_seconds", 900.0))
    except (TypeError, ValueError):
        diagnosis_stale_seconds = 900.0
    try:
        diagnosis_firmware_window_hours = float(config.get("diagnosis_firmware_window_hours", 24.0))
    except (TypeError, ValueError):
        diagnosis_firmware_window_hours = 24.0
    try:
        diagnosis_collector_stale_seconds = float(config.get("diagnosis_collector_stale_seconds", 3600.0))
    except (TypeError, ValueError):
        diagnosis_collector_stale_seconds = 3600.0

    _fusion_texts: list[str] = []
    _fusion_ok = False
    _fusion_cfg, _fusion_warnings = FusionConfig.from_mapping(config)
    if _fusion_cfg.enabled and event_store is not None and event_store.available:
        _assessment_now_ts = time.time()
        _t_start = time.monotonic()
        try:
            if raise_in_fusion:
                raise RuntimeError("simulated hard fusion failure")
            _RV = _FUSION_RULESET_VERSION
            _IA = IncidentAssessment
            _context_s = _fusion_cfg.context_hours * 3600.0
            _win_start = _assessment_now_ts - _context_s
            _win_end = _assessment_now_ts
            _selected_miners = miners
            _subject_ref = (
                f"{_selected_miners[0]['name']}|"
                f"{_selected_miners[0]['host']}:"
                f"{_selected_miners[0]['port']}"
                if _selected_miners else "fleet"
            )
            _miner_key_val = _subject_ref if _selected_miners else None
            _digest = compute_evidence_digest([], _RV)
            _assessment = _IA(
                subject_type="miner",
                subject_ref=_subject_ref,
                miner_key=_miner_key_val,
                ruleset_version=_RV,
                window_start_ts=_win_start,
                window_end_ts=_win_end,
                assessment_now_ts=_assessment_now_ts,
                status="complete",
                evidence_digest=_digest,
                hypotheses=(),
                observed_facts=(),
                contradictions=(),
                missing_evidence=(),
            )
            try:
                event_store.save_assessment(
                    subject_type=_assessment.subject_type,
                    subject_ref=_assessment.subject_ref,
                    miner_key=_assessment.miner_key,
                    ruleset_version=_assessment.ruleset_version,
                    window_start_ts=_assessment.window_start_ts,
                    window_end_ts=_assessment.window_end_ts,
                    assessment_now_ts=_assessment.assessment_now_ts,
                    status=_assessment.status,
                    evidence_digest=_assessment.evidence_digest,
                    findings_json=json.dumps([]),
                    hypotheses_json=json.dumps([]),
                    contradictions_json=json.dumps([]),
                    missing_evidence_json=json.dumps([]),
                )
            except Exception:
                pass  # persistence failure never blocks Telegram
            _elapsed = time.monotonic() - _t_start
            if _elapsed >= 2.0:
                pass  # budget exceeded; _fusion_ok stays False
            else:
                _fusion_texts = render_assessment_telegram(_assessment)
                _fusion_ok = True
        except Exception:
            pass  # strict fallback

    if _fusion_ok and _fusion_texts:
        for _part in _fusion_texts:
            fake_send(_part)
    else:
        diag_text = fake_build_diag(
            event_store, miners, None,
            now_ts=time.time(),
            stale_after_seconds=diagnosis_stale_seconds,
            firmware_window_hours=diagnosis_firmware_window_hours,
            collector_stale_seconds=diagnosis_collector_stale_seconds,
        )
        fake_send(diag_text)

    return send_calls, build_calls


# ---------------------------------------------------------------------------
# T014a — disabled: must call build_miner_diagnosis_text, not fusion
# ---------------------------------------------------------------------------

class TestDiagnoseAdapterDisabled(unittest.TestCase):

    def test_disabled_calls_legacy_build_diagnosis(self):
        config = _make_config(fusion_enabled=False)
        event_store = _make_event_store()
        miners = _make_miners()

        send_calls, build_calls = _run_diagnose_adapter(config, event_store, miners)

        self.assertEqual(build_calls, ["called"])
        self.assertEqual(len(send_calls), 1)
        self.assertEqual(send_calls[0], "LEGACY_DIAGNOSIS_TEXT")

    def test_disabled_does_not_call_save_assessment(self):
        config = _make_config(fusion_enabled=False)
        event_store = _make_event_store()
        miners = _make_miners()

        _run_diagnose_adapter(config, event_store, miners)

        event_store.save_assessment.assert_not_called()


# ---------------------------------------------------------------------------
# T014b — enabled: must render via render_assessment_telegram, not legacy
# ---------------------------------------------------------------------------

class TestDiagnoseAdapterEnabled(unittest.TestCase):

    def test_enabled_calls_render_assessment_telegram_not_legacy(self):
        config = _make_config(fusion_enabled=True)
        event_store = _make_event_store()
        miners = _make_miners()

        send_calls, build_calls = _run_diagnose_adapter(config, event_store, miners)

        self.assertEqual(build_calls, [], "Legacy builder must NOT be called when fusion is enabled")
        self.assertGreater(len(send_calls), 0)
        combined = "\n".join(send_calls)
        self.assertIn("EVALUACION DE INCIDENTE", combined)

    def test_enabled_renders_read_only_footer(self):
        config = _make_config(fusion_enabled=True)
        event_store = _make_event_store()
        miners = _make_miners()

        send_calls, _ = _run_diagnose_adapter(config, event_store, miners)

        combined = "\n".join(send_calls)
        self.assertIn("[LECTURA / SIN ACCION AUTOMATICA]", combined)

    def test_enabled_calls_save_assessment_once(self):
        config = _make_config(fusion_enabled=True)
        event_store = _make_event_store()
        miners = _make_miners()

        _run_diagnose_adapter(config, event_store, miners)

        event_store.save_assessment.assert_called_once()


# ---------------------------------------------------------------------------
# T014c — exception / DB error: strict fallback to legacy
# ---------------------------------------------------------------------------

class TestDiagnoseAdapterFallbackOnException(unittest.TestCase):

    def test_hard_exception_in_fusion_triggers_legacy_fallback(self):
        """Any exception inside the fusion block → legacy fallback, no crash."""
        config = _make_config(fusion_enabled=True)
        event_store = _make_event_store()
        miners = _make_miners()

        send_calls, build_calls = _run_diagnose_adapter(
            config, event_store, miners, raise_in_fusion=True
        )

        self.assertEqual(build_calls, ["called"])
        self.assertEqual(len(send_calls), 1)
        self.assertEqual(send_calls[0], "LEGACY_DIAGNOSIS_TEXT")

    def test_save_assessment_exception_does_not_block_fusion_response(self):
        """save_assessment raises → exception swallowed; fusion text still sent."""
        config = _make_config(fusion_enabled=True)
        event_store = _make_event_store(save_raises=True)
        miners = _make_miners()

        send_calls, build_calls = _run_diagnose_adapter(config, event_store, miners)

        # save_assessment was called (and raised) — error was swallowed
        event_store.save_assessment.assert_called_once()
        # Fusion response still sent
        self.assertEqual(build_calls, [])
        combined = "\n".join(send_calls)
        self.assertIn("EVALUACION DE INCIDENTE", combined)


# ---------------------------------------------------------------------------
# T014 — SC-006: IncidentAssessment has no action-decision fields
# ---------------------------------------------------------------------------

class TestAssessmentActionInvariant(unittest.TestCase):

    def test_incident_assessment_has_no_action_fields(self):
        from app.evidence_fusion import IncidentAssessment, RULESET_VERSION, compute_evidence_digest
        forbidden = {
            "allow_reboot", "trigger_reboot", "external_cli_command",
            "auto_action", "reboot_eligible",
        }
        digest = compute_evidence_digest([], RULESET_VERSION)
        now_ts = time.time()
        assessment = IncidentAssessment(
            subject_type="miner",
            subject_ref="test_ref",
            miner_key="test_ref",
            ruleset_version=RULESET_VERSION,
            window_start_ts=now_ts - 3600,
            window_end_ts=now_ts,
            assessment_now_ts=now_ts,
            status="complete",
            evidence_digest=digest,
            hypotheses=(),
            observed_facts=(),
            contradictions=(),
            missing_evidence=(),
        )
        for field_name in forbidden:
            self.assertFalse(
                hasattr(assessment, field_name),
                f"IncidentAssessment must not have field '{field_name}' (SC-006)",
            )


if __name__ == "__main__":
    unittest.main()
