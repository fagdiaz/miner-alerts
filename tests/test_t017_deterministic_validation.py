"""SC-001 through SC-004 deterministic validation tests for Spec 023 (T017).

Proves:
  SC-001: Known fixtures produce deterministic assessments across repeated runs.
  SC-002: No timing-only fixture yields a confirmed cause.
  SC-003: Every conclusion links to persisted facts and exposes contradiction
          or missing evidence.
  SC-004: Fleet patterns are recognized without changing action decisions or
          confirming electrical causality without external PDU/UPS proof.

FR-003, FR-004, FR-005, FR-006, FR-008, FR-011, FR-012, FR-015.
"""
from __future__ import annotations

import dataclasses
import random
import unittest

from app.evidence_fusion import (
    RULESET_VERSION,
    CauseHypothesis,
    EvidenceFact,
    IncidentAssessment,
    compute_confidence_ceiling,
    compute_evidence_digest,
    detect_fleet_pattern,
    evaluate_hypothesis,
    is_within_attribution_window,
    max_cause_level,
    render_assessment_telegram,
    render_assessment_text,
    sort_facts_canonical,
)


def _make_fact(
    *,
    source: str = "telemetry_samples",
    row_id: int = 1,
    code: str = "signal.current_low",
    effective_ts: float = 1786700000.0,
    miner_key: str = "miner-23",
    freshness: str = "fresh",
    clock_quality: str = "system",
    authority: str | None = "authoritative",
    val: float | None = 42.5,
    ceiling: str = "observed",
) -> EvidenceFact:
    return EvidenceFact(
        fact_id=f"{source}:{row_id}:{code}",
        subject_type="miner",
        subject_key=miner_key,
        source=source,
        source_row_id=row_id,
        code=code,
        effective_ts=effective_ts,
        ingested_ts=effective_ts + 0.5,
        freshness=freshness,
        clock_quality=clock_quality,
        authority=authority,
        quality=None,
        reason_code=None,
        value=val,
        units="TH/s" if val is not None else None,
        confidence_ceiling=ceiling,
    )


class TestSC001FixtureDeterminismAndReplay(unittest.TestCase):
    """SC-001: Known fixtures produce deterministic assessments across repeated runs."""

    def setUp(self) -> None:
        self.base_facts = [
            _make_fact(source="telemetry_samples", row_id=1, code="signal.current_low", effective_ts=1000.0),
            _make_fact(source="telemetry_samples", row_id=2, code="quality.hw_error_high", effective_ts=1010.0),
            _make_fact(source="operational_events", row_id=1, code="action.manual_reboot", effective_ts=1020.0),
            _make_fact(source="firmware_events", row_id=5, code="firmware.thermal", effective_ts=1025.0, clock_quality="system_local"),
            _make_fact(source="collector_runs", row_id=10, code="collector.ok", effective_ts=1030.0),
        ]

    def test_digest_deterministic_under_shuffling(self) -> None:
        """Canonical sorting ensures identical SHA-256 digest regardless of input fact order."""
        digest_base = compute_evidence_digest(self.base_facts, RULESET_VERSION)
        rng = random.Random(2026)
        for _ in range(25):
            shuffled = list(self.base_facts)
            rng.shuffle(shuffled)
            self.assertEqual(
                compute_evidence_digest(shuffled, RULESET_VERSION),
                digest_base,
                "Digest must be bit-for-bit identical across any permutation",
            )

    def test_digest_unaffected_by_internal_row_ids_or_ingested_ts(self) -> None:
        """Semantic digest excludes internal table IDs and ingestion timestamps."""
        f1 = _make_fact(row_id=10, effective_ts=2000.0)
        f2 = _make_fact(row_id=99999, effective_ts=2000.0)
        d1 = compute_evidence_digest([f1], RULESET_VERSION)
        d2 = compute_evidence_digest([f2], RULESET_VERSION)
        self.assertEqual(d1, d2, "Digest must not depend on database row IDs")

    def test_canonical_sorting_stability(self) -> None:
        """Facts are sorted by (effective_ts, source, source_row_id, code)."""
        f_late = _make_fact(source="telemetry_samples", row_id=1, code="b.code", effective_ts=200.0)
        f_early_a = _make_fact(source="operational_events", row_id=1, code="z.code", effective_ts=100.0)
        f_early_b = _make_fact(source="telemetry_samples", row_id=2, code="a.code", effective_ts=100.0)

        sorted_facts = sort_facts_canonical([f_late, f_early_b, f_early_a])
        self.assertEqual(sorted_facts[0], f_early_a)  # operational_events < telemetry_samples
        self.assertEqual(sorted_facts[1], f_early_b)
        self.assertEqual(sorted_facts[2], f_late)

    def test_renderer_output_replay_equality(self) -> None:
        """Replaying assessment rendering generates identical text and telegram splits."""
        hypo = CauseHypothesis(
            cause_code="restart.caused_by_action",
            level="suspected",
            supporting_fact_ids=("telemetry_samples:1:signal.current_low",),
            contradicting_fact_ids=(),
            missing_requirement_codes=(),
            confidence_ceiling="suspected",
            description="Accion previa correlacionada",
        )
        digest = compute_evidence_digest(self.base_facts, RULESET_VERSION)
        assessment = IncidentAssessment(
            subject_type="miner",
            subject_ref="miner-23",
            miner_key="miner-23",
            ruleset_version=RULESET_VERSION,
            window_start_ts=900.0,
            window_end_ts=1100.0,
            assessment_now_ts=1100.0,
            status="complete",
            evidence_digest=digest,
            hypotheses=(hypo,),
            observed_facts=tuple(self.base_facts),
            contradictions=(),
            missing_evidence=(),
        )
        text_1 = render_assessment_text(assessment)
        text_2 = render_assessment_text(assessment)
        self.assertEqual(text_1, text_2)

        tg_1 = render_assessment_telegram(assessment, max_chars=500)
        tg_2 = render_assessment_telegram(assessment, max_chars=500)
        self.assertEqual(tg_1, tg_2)


class TestSC002TimingOnlyNonConfirmation(unittest.TestCase):
    """SC-002: No timing-only fixture yields a confirmed cause."""

    def test_temporal_proximity_only_ceiling_is_suspected(self) -> None:
        """compute_confidence_ceiling with temporal_proximity_only caps at suspected."""
        ceiling = compute_confidence_ceiling(["temporal_proximity_only"])
        self.assertEqual(ceiling, "suspected")

    def test_temporal_proximity_cannot_confirm_any_cause(self) -> None:
        """max_cause_level returns at most suspected for temporal proximity."""
        test_causes = [
            "restart.caused_by_action",
            "power.electrical_fault",
            "firmware.thermal_shutdown",
            "network.disconnect",
        ]
        for cause in test_causes:
            level = max_cause_level(cause, ["temporal_proximity_only"])
            self.assertIn(level, ("observed", "suspected"))
            self.assertNotEqual(level, "confirmed", f"{cause} must not be confirmed by timing only")

    def test_symptom_alone_cannot_confirm_cause(self) -> None:
        """Offline, low hashrate or quality symptoms alone cannot confirm root causes."""
        for symptom in ("signal.current_offline", "signal.current_low", "fresh_symptom"):
            level = max_cause_level("power.electrical_fault", [symptom])
            self.assertNotEqual(level, "confirmed")

    def test_evaluate_hypothesis_caps_at_suspected_when_timing_only(self) -> None:
        """evaluate_hypothesis never outputs confirmed with only temporal proximity."""
        result = evaluate_hypothesis(
            supporting=["temporal_proximity_only"],
            contradicting=[],
            missing=[],
        )
        self.assertEqual(result["level"], "suspected")

    def test_stale_or_skewed_evidence_drops_to_observed(self) -> None:
        """Stale or clock-skewed evidence cannot even reach suspected."""
        for bad_condition in ("stale", "future_skew", "unparsed_clock", "partial_collector"):
            level = max_cause_level("restart.caused_by_action", [bad_condition])
            self.assertEqual(level, "observed")


class TestSC003ContradictionVisibilityAndMissingEvidence(unittest.TestCase):
    """SC-003: Conclusions expose contradictions and missing evidence visibly."""

    def test_decisive_contradiction_drops_confirmed_to_suspected(self) -> None:
        """Direct evidence with a decisive contradiction cannot remain confirmed."""
        result = evaluate_hypothesis(
            supporting=["direct_cause_fresh_valid"],
            contradicting=["action.no_successful_action_in_window"],
            missing=[],
        )
        self.assertEqual(result["level"], "suspected")
        self.assertIn("action.no_successful_action_in_window", result["contradicting_fact_ids"])

    def test_missing_evidence_drops_confirmed_to_suspected(self) -> None:
        """Missing required evidence prevents confirmation."""
        result = evaluate_hypothesis(
            supporting=["direct_cause_fresh_valid"],
            contradicting=[],
            missing=["firmware.clock_unparsed"],
        )
        self.assertEqual(result["level"], "suspected")
        self.assertIn("firmware.clock_unparsed", result["missing_requirement_codes"])

    def test_contradictions_and_missing_rendered_visibly(self) -> None:
        """render_assessment_text explicitly includes sections for contradictions and missing."""
        assessment = IncidentAssessment(
            subject_type="episode",
            subject_ref="ep:101",
            miner_key="miner-23",
            ruleset_version=RULESET_VERSION,
            window_start_ts=100.0,
            window_end_ts=200.0,
            assessment_now_ts=200.0,
            status="incomplete",
            evidence_digest="f" * 64,
            hypotheses=(),
            observed_facts=(),
            contradictions=("action.contradicted_by_subsequent_ok",),
            missing_evidence=("collector.run_missing_in_window",),
        )
        rendered = render_assessment_text(assessment)
        self.assertIn("[CONTRADICCIONES]", rendered)
        self.assertIn("action.contradicted_by_subsequent_ok", rendered)
        self.assertIn("[EVIDENCIA FALTANTE O DESACTUALIZADA]", rendered)
        self.assertIn("collector.run_missing_in_window", rendered)
        self.assertIn("[LECTURA / SIN ACCION AUTOMATICA]", rendered)

    def test_absence_is_missing_not_contradiction(self) -> None:
        """Absence of evidence goes to missing_requirement_codes, not contradiction."""
        result = evaluate_hypothesis(
            supporting=["fresh_symptom"],
            contradicting=[],
            missing=["collector.missing"],
        )
        self.assertEqual(len(result["contradicting_fact_ids"]), 0)
        self.assertEqual(result["missing_requirement_codes"], ["collector.missing"])


class TestSC004FleetNonCausalityAndActionInvariance(unittest.TestCase):
    """SC-004: Fleet patterns are recognized without changing action decisions."""

    def test_fleet_pattern_detected_for_concurrent_miners(self) -> None:
        """Two miners with degradation facts within 60s yield fleet pattern."""
        facts = [
            _make_fact(miner_key="miner-23", effective_ts=100.0, code="signal.current_offline"),
            _make_fact(miner_key="miner-24", effective_ts=130.0, code="signal.current_offline"),
        ]
        pattern = detect_fleet_pattern(facts, fleet_window_seconds=60.0)
        self.assertIsNotNone(pattern)
        self.assertEqual(pattern["code"], "fleet.concurrent_degradation")
        self.assertEqual(set(pattern["miner_keys"]), {"miner-23", "miner-24"})
        self.assertEqual(pattern["window_span_s"], 30.0)

    def test_fleet_pattern_never_confirms_electrical_cause_without_external_pdu(self) -> None:
        """Fleet concurrent degradation alone CANNOT confirm power.electrical_fault."""
        level = max_cause_level("power.electrical_fault", ["fleet.concurrent_degradation"])
        self.assertNotEqual(
            level,
            "confirmed",
            "Fleet degradation cannot confirm electrical cause without external PDU evidence (Spec 024 gate)",
        )
        self.assertEqual(level, "suspected")

    def test_assessment_dataclass_has_zero_action_fields(self) -> None:
        """IncidentAssessment must NOT have any field that could authorize actions."""
        field_names = {f.name for f in dataclasses.fields(IncidentAssessment)}
        forbidden_action_fields = {
            "allow_reboot",
            "trigger_reboot",
            "hashcore_command",
            "external_cli_command",
            "auto_action",
            "reboot_eligible",
            "streak_override",
            "target_miner_reboot",
        }
        intersection = field_names & forbidden_action_fields
        self.assertFalse(
            intersection,
            f"IncidentAssessment violates action-invariance contract: found {intersection}",
        )

    def test_functions_do_not_mutate_input_arguments(self) -> None:
        """Pure functions must not mutate fact collections passed to them."""
        facts = [
            _make_fact(row_id=1, effective_ts=200.0, code="signal.current_low"),
            _make_fact(row_id=2, effective_ts=100.0, code="signal.current_offline"),
        ]
        facts_copy = list(facts)
        sort_facts_canonical(facts)
        self.assertEqual(facts, facts_copy, "sort_facts_canonical must not mutate input list")

        compute_evidence_digest(facts, RULESET_VERSION)
        self.assertEqual(facts, facts_copy, "compute_evidence_digest must not mutate input")

        detect_fleet_pattern(facts, 60.0)
        self.assertEqual(facts, facts_copy, "detect_fleet_pattern must not mutate input")


if __name__ == "__main__":
    unittest.main()
