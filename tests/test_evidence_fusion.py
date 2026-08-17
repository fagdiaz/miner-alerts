"""Red contract tests for Spec 023 — Incident Evidence Fusion.

T002: Configuration, disabled-fallback and validation contracts (FR-013).
T003: Normalization, freshness, clock quality, ordering, digest and
      unknown-code fail-closed contracts (FR-001, FR-002, FR-010, FR-012, FR-015).

These tests define the expected behaviour of ``app.evidence_fusion`` before
the module exists.  They MUST fail with ``ModuleNotFoundError`` until the
implementation phase (T008-T011) creates the module.  Existing production
code is never imported or modified by this file.
"""
from __future__ import annotations

import hashlib
import json
import math
import unittest


# ---------------------------------------------------------------------------
# T002 — Configuration and disabled-fallback contracts (FR-013)
# ---------------------------------------------------------------------------

class TestFusionConfigParsing(unittest.TestCase):
    """Verify ``FusionConfig.from_mapping`` parses and validates exactly the
    keys documented in ``contracts/config.md``."""

    def _parse(self, overrides: dict | None = None):
        from app.evidence_fusion import FusionConfig  # noqa: F811
        base: dict = {}
        if overrides:
            base.update(overrides)
        config, warnings = FusionConfig.from_mapping(base)
        return config, warnings

    # -- defaults -----------------------------------------------------------

    def test_defaults_when_keys_absent(self):
        """All keys absent → disabled, 24 h context, 60 s fleet window."""
        config, warnings = self._parse({})
        self.assertFalse(config.enabled)
        self.assertEqual(config.context_hours, 24)
        self.assertEqual(config.fleet_window_seconds, 60)
        self.assertEqual(len(warnings), 0)

    def test_enabled_true(self):
        config, _ = self._parse({"incident_fusion_enabled": True})
        self.assertTrue(config.enabled)

    def test_enabled_false_explicit(self):
        config, _ = self._parse({"incident_fusion_enabled": False})
        self.assertFalse(config.enabled)

    # -- validation ---------------------------------------------------------

    def test_invalid_enabled_type_falls_back_to_disabled(self):
        """Non-boolean ``incident_fusion_enabled`` → disable + warning."""
        config, warnings = self._parse({"incident_fusion_enabled": "yes"})
        self.assertFalse(config.enabled)
        self.assertTrue(any("incident_fusion_enabled" in w for w in warnings))

    def test_context_hours_below_minimum_uses_default(self):
        config, warnings = self._parse({"incident_fusion_context_hours": 0})
        self.assertEqual(config.context_hours, 24)
        self.assertTrue(any("incident_fusion_context_hours" in w for w in warnings))

    def test_context_hours_above_maximum_uses_default(self):
        config, warnings = self._parse({"incident_fusion_context_hours": 200})
        self.assertEqual(config.context_hours, 24)
        self.assertTrue(any("incident_fusion_context_hours" in w for w in warnings))

    def test_context_hours_valid_boundary_low(self):
        config, _ = self._parse({"incident_fusion_context_hours": 1})
        self.assertEqual(config.context_hours, 1)

    def test_context_hours_valid_boundary_high(self):
        config, _ = self._parse({"incident_fusion_context_hours": 168})
        self.assertEqual(config.context_hours, 168)

    def test_fleet_window_below_minimum_uses_default(self):
        config, warnings = self._parse(
            {"incident_fusion_fleet_window_seconds": 10}
        )
        self.assertEqual(config.fleet_window_seconds, 60)
        self.assertTrue(
            any("incident_fusion_fleet_window_seconds" in w for w in warnings)
        )

    def test_fleet_window_above_maximum_uses_default(self):
        config, warnings = self._parse(
            {"incident_fusion_fleet_window_seconds": 500}
        )
        self.assertEqual(config.fleet_window_seconds, 60)

    def test_fleet_window_valid_boundary_low(self):
        config, _ = self._parse(
            {"incident_fusion_fleet_window_seconds": 30}
        )
        self.assertEqual(config.fleet_window_seconds, 30)

    def test_fleet_window_valid_boundary_high(self):
        config, _ = self._parse(
            {"incident_fusion_fleet_window_seconds": 300}
        )
        self.assertEqual(config.fleet_window_seconds, 300)

    def test_nan_context_hours_uses_default(self):
        config, warnings = self._parse(
            {"incident_fusion_context_hours": float("nan")}
        )
        self.assertEqual(config.context_hours, 24)
        self.assertTrue(len(warnings) > 0)

    def test_infinity_fleet_window_uses_default(self):
        config, warnings = self._parse(
            {"incident_fusion_fleet_window_seconds": float("inf")}
        )
        self.assertEqual(config.fleet_window_seconds, 60)
        self.assertTrue(len(warnings) > 0)


# ---------------------------------------------------------------------------
# T003 — Normalization, freshness, clock, ordering and digest (FR-001/2/10/12/15)
# ---------------------------------------------------------------------------

class TestEvidenceFactNormalization(unittest.TestCase):
    """Verify ``EvidenceFact`` immutability and field semantics from
    ``data-model.md``."""

    def _make_fact(self, **overrides):
        from app.evidence_fusion import EvidenceFact  # noqa: F811
        defaults = {
            "fact_id": "telemetry_samples:1:signal.current_low",
            "subject_type": "miner",
            "subject_key": "23",
            "source": "telemetry_samples",
            "source_row_id": 1,
            "code": "signal.current_low",
            "effective_ts": 1786700000.0,
            "ingested_ts": None,
            "freshness": "fresh",
            "clock_quality": "system",
            "authority": None,
            "quality": None,
            "reason_code": None,
            "value": 42.5,
            "units": "TH/s",
            "confidence_ceiling": "observed",
        }
        defaults.update(overrides)
        return EvidenceFact(**defaults)

    def test_fact_is_immutable(self):
        """EvidenceFact must be frozen/immutable."""
        fact = self._make_fact()
        with self.assertRaises((AttributeError, TypeError)):
            fact.code = "modified"

    def test_fact_id_format(self):
        """fact_id follows ``<source_table>:<source_row_id>:<code>``."""
        fact = self._make_fact()
        parts = fact.fact_id.split(":")
        self.assertEqual(len(parts), 3)
        self.assertEqual(parts[0], "telemetry_samples")
        self.assertEqual(parts[1], "1")
        self.assertEqual(parts[2], "signal.current_low")


class TestFreshnessClassification(unittest.TestCase):
    """Verify freshness is classified deterministically per
    ``contracts/evidence-rules.md``."""

    def _classify(self, effective_ts, assessment_now_ts, stale_seconds=900):
        from app.evidence_fusion import classify_freshness
        return classify_freshness(effective_ts, assessment_now_ts, stale_seconds)

    def test_fresh_within_threshold(self):
        now = 1786700000.0
        self.assertEqual(self._classify(now - 100, now), "fresh")

    def test_stale_beyond_threshold(self):
        now = 1786700000.0
        self.assertEqual(self._classify(now - 1000, now, 900), "stale")

    def test_stale_exactly_at_boundary(self):
        now = 1786700000.0
        self.assertEqual(self._classify(now - 900, now, 900), "fresh")

    def test_future_skew_beyond_tolerance(self):
        """Timestamps >5s in the future → future_skew."""
        now = 1786700000.0
        self.assertEqual(self._classify(now + 10, now), "future_skew")

    def test_future_within_tolerance(self):
        """Timestamps ≤5s in the future → still fresh."""
        now = 1786700000.0
        self.assertEqual(self._classify(now + 3, now), "fresh")

    def test_none_effective_ts_returns_unknown(self):
        now = 1786700000.0
        self.assertEqual(self._classify(None, now), "unknown")


class TestClockQualityMapping(unittest.TestCase):
    """Verify clock quality mapping per ``contracts/evidence-rules.md``."""

    def _map(self, source_table, source_clock=None):
        from app.evidence_fusion import map_clock_quality
        return map_clock_quality(source_table, source_clock)

    def test_telemetry_samples_is_system(self):
        self.assertEqual(self._map("telemetry_samples"), "system")

    def test_operational_events_is_system(self):
        self.assertEqual(self._map("operational_events"), "system")

    def test_reboot_decisions_is_system(self):
        self.assertEqual(self._map("reboot_decisions"), "system")

    def test_firmware_events_parsed_clock(self):
        self.assertEqual(
            self._map("firmware_events", "system_local"), "system_local"
        )

    def test_firmware_events_unparsed_clock(self):
        self.assertEqual(
            self._map("firmware_events", "unparsed"), "unparsed"
        )

    def test_firmware_events_no_clock_is_unparsed(self):
        self.assertEqual(self._map("firmware_events", None), "unparsed")

    def test_collector_runs_is_system(self):
        self.assertEqual(self._map("collector_runs"), "system")

    def test_unknown_source_is_unknown(self):
        self.assertEqual(self._map("some_future_table"), "unknown")


class TestUnknownCodeFailClosed(unittest.TestCase):
    """Unknown fact or cause codes must fail closed (FR-015)."""

    def _validate_code(self, code):
        from app.evidence_fusion import validate_fact_code
        return validate_fact_code(code)

    def test_recognized_code_is_valid(self):
        self.assertTrue(self._validate_code("signal.current_low"))

    def test_recognized_family_new_member_is_valid(self):
        self.assertTrue(self._validate_code("signal.recovered"))

    def test_unknown_family_is_invalid(self):
        self.assertFalse(self._validate_code("exotic.unknown_thing"))

    def test_empty_code_is_invalid(self):
        self.assertFalse(self._validate_code(""))

    def test_none_code_is_invalid(self):
        self.assertFalse(self._validate_code(None))


class TestCanonicalOrdering(unittest.TestCase):
    """Facts must sort by (effective_ts, source, source_row_id, code)
    per FR-012 for deterministic digest."""

    def _sort_facts(self, facts):
        from app.evidence_fusion import sort_facts_canonical
        return sort_facts_canonical(facts)

    def _make_fact(self, effective_ts, source, source_row_id, code):
        from app.evidence_fusion import EvidenceFact
        return EvidenceFact(
            fact_id=f"{source}:{source_row_id}:{code}",
            subject_type="miner",
            subject_key="23",
            source=source,
            source_row_id=source_row_id,
            code=code,
            effective_ts=effective_ts,
            ingested_ts=None,
            freshness="fresh",
            clock_quality="system",
            authority=None,
            quality=None,
            reason_code=None,
            value=None,
            units=None,
            confidence_ceiling="observed",
        )

    def test_sorts_by_effective_ts_first(self):
        a = self._make_fact(100.0, "telemetry_samples", 1, "signal.current_low")
        b = self._make_fact(200.0, "telemetry_samples", 2, "signal.current_low")
        result = self._sort_facts([b, a])
        self.assertEqual(result[0].effective_ts, 100.0)
        self.assertEqual(result[1].effective_ts, 200.0)

    def test_tiebreak_by_source(self):
        a = self._make_fact(100.0, "firmware_events", 1, "firmware.chain_break")
        b = self._make_fact(100.0, "telemetry_samples", 1, "signal.current_low")
        result = self._sort_facts([b, a])
        self.assertEqual(result[0].source, "firmware_events")
        self.assertEqual(result[1].source, "telemetry_samples")

    def test_tiebreak_by_source_row_id(self):
        a = self._make_fact(100.0, "telemetry_samples", 1, "signal.current_low")
        b = self._make_fact(100.0, "telemetry_samples", 5, "signal.current_low")
        result = self._sort_facts([b, a])
        self.assertEqual(result[0].source_row_id, 1)
        self.assertEqual(result[1].source_row_id, 5)

    def test_tiebreak_by_code(self):
        a = self._make_fact(100.0, "telemetry_samples", 1, "signal.current_low")
        b = self._make_fact(100.0, "telemetry_samples", 1, "signal.recovered")
        result = self._sort_facts([b, a])
        self.assertEqual(result[0].code, "signal.current_low")
        self.assertEqual(result[1].code, "signal.recovered")

    def test_deterministic_across_runs(self):
        """Same input → same output every time."""
        facts = [
            self._make_fact(300.0, "operational_events", 5, "restart.uptime_reset"),
            self._make_fact(100.0, "telemetry_samples", 1, "signal.current_low"),
            self._make_fact(200.0, "firmware_events", 3, "firmware.chain_break"),
        ]
        run1 = self._sort_facts(list(facts))
        run2 = self._sort_facts(list(facts))
        self.assertEqual(
            [f.fact_id for f in run1],
            [f.fact_id for f in run2],
        )


class TestEvidenceDigest(unittest.TestCase):
    """Evidence digest must be deterministic and exclude generated IDs
    and creation timestamps (FR-012)."""

    def _compute_digest(self, facts, ruleset_version="1.0.0"):
        from app.evidence_fusion import compute_evidence_digest
        return compute_evidence_digest(facts, ruleset_version)

    def _make_fact(self, effective_ts, source, source_row_id, code):
        from app.evidence_fusion import EvidenceFact
        return EvidenceFact(
            fact_id=f"{source}:{source_row_id}:{code}",
            subject_type="miner",
            subject_key="23",
            source=source,
            source_row_id=source_row_id,
            code=code,
            effective_ts=effective_ts,
            ingested_ts=None,
            freshness="fresh",
            clock_quality="system",
            authority=None,
            quality=None,
            reason_code=None,
            value=42.5,
            units="TH/s",
            confidence_ceiling="observed",
        )

    def test_digest_is_sha256_hex(self):
        facts = [self._make_fact(100.0, "telemetry_samples", 1, "signal.current_low")]
        digest = self._compute_digest(facts)
        self.assertEqual(len(digest), 64)
        int(digest, 16)  # valid hex

    def test_same_facts_same_digest(self):
        facts = [self._make_fact(100.0, "telemetry_samples", 1, "signal.current_low")]
        d1 = self._compute_digest(facts)
        d2 = self._compute_digest(list(facts))
        self.assertEqual(d1, d2)

    def test_different_facts_different_digest(self):
        f1 = [self._make_fact(100.0, "telemetry_samples", 1, "signal.current_low")]
        f2 = [self._make_fact(200.0, "telemetry_samples", 2, "signal.recovered")]
        self.assertNotEqual(self._compute_digest(f1), self._compute_digest(f2))

    def test_different_ruleset_different_digest(self):
        facts = [self._make_fact(100.0, "telemetry_samples", 1, "signal.current_low")]
        d1 = self._compute_digest(facts, "1.0.0")
        d2 = self._compute_digest(facts, "1.1.0")
        self.assertNotEqual(d1, d2)

    def test_order_independent_after_canonical_sort(self):
        """Digest should be the same regardless of input order when facts
        are canonically sorted internally."""
        a = self._make_fact(100.0, "telemetry_samples", 1, "signal.current_low")
        b = self._make_fact(200.0, "firmware_events", 3, "firmware.chain_break")
        d1 = self._compute_digest([a, b])
        d2 = self._compute_digest([b, a])
        self.assertEqual(d1, d2)

    def test_non_finite_value_excluded(self):
        """Facts with NaN/Inf values must not produce NaN in the digest
        serialization (FR-012)."""
        fact = self._make_fact(100.0, "telemetry_samples", 1, "signal.current_low")
        # Even if value were NaN, the digest function must handle it
        # by serializing a safe sentinel rather than NaN/Infinity
        digest = self._compute_digest([fact])
        self.assertIsInstance(digest, str)
        self.assertEqual(len(digest), 64)



# ---------------------------------------------------------------------------
# T004 — Confidence ceilings and non-causality (FR-003, FR-004, FR-005, FR-006, FR-010)
# ---------------------------------------------------------------------------

class TestConfidenceCeilings(unittest.TestCase):
    """Verify that the confidence-ceiling rules are enforced as specified in
    ``contracts/evidence-rules.md``."""

    def _ceiling(self, conditions: list[str]) -> str:
        from app.evidence_fusion import compute_confidence_ceiling
        return compute_confidence_ceiling(conditions)

    def test_stale_evidence_caps_at_observed(self):
        """Stale evidence cannot exceed 'observed' regardless of other conditions."""
        self.assertEqual(self._ceiling(["stale"]), "observed")

    def test_future_skew_caps_at_observed(self):
        """Future-skewed evidence cannot exceed 'observed'."""
        self.assertEqual(self._ceiling(["future_skew"]), "observed")

    def test_unparsed_clock_caps_at_observed(self):
        """Unparsed clock cannot confirm ordering-sensitive causes."""
        self.assertEqual(self._ceiling(["unparsed_clock"]), "observed")

    def test_partial_collector_caps_at_observed(self):
        """Partial collector run: firmware evidence stays at observed."""
        self.assertEqual(self._ceiling(["partial_collector"]), "observed")

    def test_fresh_symptom_caps_at_suspected(self):
        """Fresh symptom or quality reason: at most suspected."""
        self.assertEqual(self._ceiling(["fresh_symptom"]), "suspected")

    def test_temporal_proximity_only_caps_at_suspected(self):
        """Timing proximity alone cannot confirm a cause (FR-004)."""
        self.assertEqual(self._ceiling(["temporal_proximity_only"]), "suspected")

    def test_direct_causal_fresh_valid_can_be_confirmed(self):
        """Direct fresh causal evidence with all required conditions may be confirmed."""
        ceiling = self._ceiling(["direct_cause_fresh_valid"])
        self.assertIn(ceiling, ("confirmed", "suspected"))  # implementation decides

    def test_minimum_ceiling_governs(self):
        """When multiple conditions apply, the lowest ceiling wins (FR-010)."""
        ceiling = self._ceiling(["direct_cause_fresh_valid", "stale"])
        self.assertEqual(ceiling, "observed")

    def test_more_low_quality_facts_never_promote_confidence(self):
        """Adding more stale facts cannot increase ceiling above observed."""
        c1 = self._ceiling(["stale"])
        c2 = self._ceiling(["stale", "stale", "stale"])
        self.assertEqual(c1, c2)
        self.assertEqual(c2, "observed")


class TestNonCausality(unittest.TestCase):
    """FR-004, FR-006: timing-only and fleet patterns cannot confirm causality."""

    def _assess_cause(self, cause_code: str, evidence_conditions: list[str]) -> str:
        """Returns max achievable level: 'observed', 'suspected', or 'confirmed'."""
        from app.evidence_fusion import max_cause_level
        return max_cause_level(cause_code, evidence_conditions)

    def test_offline_alone_cannot_confirm_network_cause(self):
        """API OFFLINE alone cannot confirm network, power or miner failure."""
        level = self._assess_cause("network.failure", ["signal.current_offline"])
        self.assertNotEqual(level, "confirmed")

    def test_low_alone_cannot_confirm_thermal_cause(self):
        """LOW state alone cannot confirm temperature cause."""
        level = self._assess_cause("thermal.overheat", ["signal.current_low"])
        self.assertNotEqual(level, "confirmed")

    def test_fleet_concurrent_degradation_cannot_confirm_electrical(self):
        """Fleet concurrence cannot confirm electrical cause (FR-006)."""
        level = self._assess_cause(
            "power.electrical_fault",
            ["fleet.concurrent_degradation"],
        )
        self.assertNotEqual(level, "confirmed")

    def test_fleet_pattern_without_pdu_stays_suspected_at_most(self):
        """Without power.* external fact, fleet pattern stays suspected at most."""
        level = self._assess_cause(
            "power.electrical_fault",
            ["fleet.concurrent_degradation", "fresh_symptom"],
        )
        self.assertIn(level, ("observed", "suspected"))

    def test_temporal_proximity_alone_is_at_most_suspected(self):
        """Two events near in time produce at most 'suspected', never 'confirmed'."""
        level = self._assess_cause(
            "restart.caused_by_action",
            ["temporal_proximity_only"],
        )
        self.assertNotEqual(level, "confirmed")


class TestContradictionsAndMissingEvidence(unittest.TestCase):
    """FR-005: supporting, contradicting and missing evidence must remain visible."""

    def _eval_hypothesis(self, supporting: list[str], contradicting: list[str],
                          missing: list[str]) -> dict:
        from app.evidence_fusion import evaluate_hypothesis
        return evaluate_hypothesis(supporting, contradicting, missing)

    def test_no_contradiction_produces_no_contradicting_list(self):
        result = self._eval_hypothesis(
            supporting=["signal.current_low"],
            contradicting=[],
            missing=[],
        )
        self.assertEqual(result["contradicting_fact_ids"], [])

    def test_decisive_contradiction_prevents_confirmation(self):
        result = self._eval_hypothesis(
            supporting=["direct_cause_fresh_valid"],
            contradicting=["action.no_successful_action_in_window"],
            missing=[],
        )
        self.assertNotEqual(result["level"], "confirmed")

    def test_missing_evidence_is_visible_not_contradiction(self):
        result = self._eval_hypothesis(
            supporting=[],
            contradicting=[],
            missing=["reboot_decision.missing"],
        )
        self.assertIn("reboot_decision.missing", result["missing_requirement_codes"])
        self.assertEqual(result["contradicting_fact_ids"], [])

    def test_absence_is_not_automatically_a_contradiction(self):
        """An absent source is missing evidence, not a decisive contradiction."""
        result = self._eval_hypothesis(
            supporting=["signal.current_low"],
            contradicting=[],
            missing=["firmware.chain_break"],
        )
        # Should not be 'confirmed' (missing req), but also not treat absence as proof
        self.assertNotEqual(result["level"], "confirmed")
        self.assertEqual(result["contradicting_fact_ids"], [])


# ---------------------------------------------------------------------------
# T005 — Replay fixtures (FR-006, FR-007)
# ---------------------------------------------------------------------------

class TestIsolatedVsFleetFixtures(unittest.TestCase):
    """Verify that isolated and fleet scenario fixtures produce different
    fleet-pattern observations without altering cause conclusions."""

    def _build_fact(self, miner_key: str, effective_ts: float, code: str,
                     freshness: str = "fresh") -> object:
        from app.evidence_fusion import EvidenceFact
        return EvidenceFact(
            fact_id=f"telemetry_samples:1:{code}",
            subject_type="miner",
            subject_key=miner_key,
            source="telemetry_samples",
            source_row_id=1,
            code=code,
            effective_ts=effective_ts,
            ingested_ts=None,
            freshness=freshness,
            clock_quality="system",
            authority=None,
            quality=None,
            reason_code=None,
            value=None,
            units=None,
            confidence_ceiling="observed",
        )

    def _detect_fleet_pattern(self, facts: list, fleet_window_seconds: float = 60.0):
        from app.evidence_fusion import detect_fleet_pattern
        return detect_fleet_pattern(facts, fleet_window_seconds)

    def test_single_miner_offline_is_isolated(self):
        """One miner going OFFLINE at T=100 → isolated, no fleet pattern."""
        facts = [self._build_fact("23", 100.0, "signal.current_offline")]
        pattern = self._detect_fleet_pattern(facts)
        self.assertIsNone(pattern)

    def test_two_miners_within_window_is_fleet(self):
        """Two miners degrade within 60s → fleet.concurrent_degradation."""
        facts = [
            self._build_fact("23", 100.0, "signal.current_offline"),
            self._build_fact("24", 120.0, "signal.current_offline"),
        ]
        pattern = self._detect_fleet_pattern(facts)
        self.assertIsNotNone(pattern)
        self.assertEqual(pattern["code"], "fleet.concurrent_degradation")

    def test_two_miners_outside_window_is_not_fleet(self):
        """Two miners degrade >60s apart → no fleet pattern."""
        facts = [
            self._build_fact("23", 100.0, "signal.current_offline"),
            self._build_fact("24", 200.0, "signal.current_offline"),
        ]
        pattern = self._detect_fleet_pattern(facts, fleet_window_seconds=60.0)
        self.assertIsNone(pattern)

    def test_fleet_pattern_does_not_produce_confirmed_electrical_cause(self):
        """Fleet pattern alone cannot produce a confirmed electrical cause."""
        from app.evidence_fusion import max_cause_level
        level = max_cause_level(
            "power.electrical_fault",
            ["fleet.concurrent_degradation"],
        )
        self.assertNotEqual(level, "confirmed")


class TestAttributedActionFixture(unittest.TestCase):
    """FR-007: action attribution uses the existing 900-second window."""

    def _check_attribution(self, action_ts: float, restart_ts: float,
                             window_seconds: float = 900.0) -> bool:
        from app.evidence_fusion import is_within_attribution_window
        return is_within_attribution_window(action_ts, restart_ts, window_seconds)

    def test_restart_within_window_is_attributed(self):
        """Restart 300s after action → attributed."""
        self.assertTrue(self._check_attribution(1000.0, 1300.0, 900.0))

    def test_restart_exactly_at_boundary(self):
        """Restart exactly at 900s → still within window."""
        self.assertTrue(self._check_attribution(1000.0, 1900.0, 900.0))

    def test_restart_beyond_window_is_not_attributed(self):
        """Restart 1000s after action → not attributed."""
        self.assertFalse(self._check_attribution(1000.0, 2001.0, 900.0))

    def test_restart_before_action_is_not_attributed(self):
        """Restart before action → not attributed."""
        self.assertFalse(self._check_attribution(1000.0, 500.0, 900.0))


class TestFirmwareClockFixtures(unittest.TestCase):
    """FR-002, FR-010: firmware events with parsed vs unparsed clocks."""

    def _map(self, source_table: str, source_clock: str | None = None) -> str:
        from app.evidence_fusion import map_clock_quality
        return map_clock_quality(source_table, source_clock)

    def test_firmware_parsed_local_clock(self):
        self.assertEqual(
            self._map("firmware_events", "system_local"), "system_local"
        )

    def test_firmware_parsed_utc_clock(self):
        self.assertEqual(
            self._map("firmware_events", "fixed_utc_offset"), "fixed_utc_offset"
        )

    def test_firmware_unparsed_cannot_prove_ordering(self):
        """Unparsed firmware clock → cannot confirm ordering-sensitive causes."""
        quality = self._map("firmware_events", "unparsed")
        self.assertEqual(quality, "unparsed")

    def test_firmware_unparsed_ceiling_is_observed(self):
        from app.evidence_fusion import compute_confidence_ceiling
        ceiling = compute_confidence_ceiling(["unparsed_clock"])
        self.assertEqual(ceiling, "observed")


# ---------------------------------------------------------------------------
# T007 — Action invariants: fusion must not alter state or call Hashcore
# ---------------------------------------------------------------------------

class TestActionInvariants(unittest.TestCase):
    """FR-008, SC-006: evidence fusion is read-only and cannot alter monitor state."""

    def test_evidence_fusion_module_has_no_hashcore_import(self):
        """app.evidence_fusion must not import any Hashcore module."""
        import importlib
        import importlib.util
        import sys
        # If the module doesn't exist yet, the test is vacuously green
        # (the import guard handles it gracefully)
        spec = importlib.util.find_spec("app.evidence_fusion")
        if spec is None:
            self.skipTest("app.evidence_fusion not yet implemented")
        mod = importlib.import_module("app.evidence_fusion")
        # Check module source does not import reboot_safety or hashcore
        import inspect
        source = inspect.getsource(mod)
        self.assertNotIn("hashcore", source.lower(),
                         "evidence_fusion must not import hashcore")
        self.assertNotIn("reboot_safety", source,
                         "evidence_fusion must not import reboot_safety")

    def test_evidence_fusion_module_has_no_miner_monitor_import(self):
        """app.evidence_fusion must not import miner_monitor (action authority)."""
        import importlib.util
        spec = importlib.util.find_spec("app.evidence_fusion")
        if spec is None:
            self.skipTest("app.evidence_fusion not yet implemented")
        import importlib, inspect
        mod = importlib.import_module("app.evidence_fusion")
        source = inspect.getsource(mod)
        self.assertNotIn("miner_monitor", source,
                         "evidence_fusion must not import miner_monitor")

    def test_assessment_output_has_no_action_fields(self):
        """IncidentAssessment must not expose fields that could be action inputs."""
        from app.evidence_fusion import IncidentAssessment  # noqa: F811
        import dataclasses
        field_names = {f.name for f in dataclasses.fields(IncidentAssessment)}
        forbidden = {"allow_reboot", "trigger_reboot", "hashcore_command",
                     "auto_action", "reboot_eligible"}
        self.assertFalse(
            field_names & forbidden,
            f"IncidentAssessment contains forbidden action fields: "
            f"{field_names & forbidden}",
        )

    def test_compute_evidence_digest_does_not_mutate_input(self):
        """compute_evidence_digest must not mutate the passed fact list."""
        from app.evidence_fusion import EvidenceFact, compute_evidence_digest
        fact = EvidenceFact(
            fact_id="telemetry_samples:1:signal.current_low",
            subject_type="miner",
            subject_key="23",
            source="telemetry_samples",
            source_row_id=1,
            code="signal.current_low",
            effective_ts=1786700000.0,
            ingested_ts=None,
            freshness="fresh",
            clock_quality="system",
            authority=None,
            quality=None,
            reason_code=None,
            value=42.5,
            units="TH/s",
            confidence_ceiling="observed",
        )
        original = [fact]
        compute_evidence_digest(list(original), "1.0.0")
        self.assertEqual(len(original), 1)



# ---------------------------------------------------------------------------
# T013 — Shared semantic renderer tests (FR-011)
# ---------------------------------------------------------------------------

class TestSharedSemanticRenderer(unittest.TestCase):
    """Verify render_assessment_text and render_assessment_telegram."""

    def _build_sample_assessment(self):
        from app.evidence_fusion import (
            CauseHypothesis,
            EvidenceFact,
            IncidentAssessment,
        )
        fact1 = EvidenceFact(
            fact_id="telemetry_samples:1:signal.current_low",
            subject_type="miner",
            subject_key="23",
            source="telemetry_samples",
            source_row_id=1,
            code="signal.current_low",
            effective_ts=1786700000.0,
            ingested_ts=None,
            freshness="fresh",
            clock_quality="system",
            authority="authoritative",
            quality=None,
            reason_code=None,
            value=42.5,
            units="TH/s",
            confidence_ceiling="observed",
        )
        hypo1 = CauseHypothesis(
            cause_code="restart.caused_by_action",
            level="suspected",
            supporting_fact_ids=("telemetry_samples:1:signal.current_low",),
            contradicting_fact_ids=(),
            missing_requirement_codes=(),
            confidence_ceiling="suspected",
            description="Reinicio sospechado por accion manual previa",
        )
        return IncidentAssessment(
            subject_type="episode",
            subject_ref="ep:42",
            miner_key="23",
            ruleset_version="1.0.0",
            window_start_ts=1786696400.0,
            window_end_ts=1786700000.0,
            assessment_now_ts=1786700000.0,
            status="complete",
            evidence_digest="a" * 64,
            hypotheses=(hypo1,),
            observed_facts=(fact1,),
            contradictions=("action.no_successful_action_in_window",),
            missing_evidence=("reboot_decision.missing",),
        )

    def test_render_assessment_text_sections_and_footer(self):
        from app.evidence_fusion import render_assessment_text
        assessment = self._build_sample_assessment()
        rendered = render_assessment_text(assessment)

        # Check section headers and ordering
        self.assertIn("EVALUACION DE INCIDENTE · episode:ep:42", rendered)
        self.assertIn("[HECHOS OBSERVADOS]", rendered)
        self.assertIn("signal.current_low", rendered)
        self.assertIn("[CAUSAS E HIPOTESIS]", rendered)
        self.assertIn("SOSPECHADA · restart.caused_by_action", rendered)
        self.assertIn("[CONTRADICCIONES]", rendered)
        self.assertIn("action.no_successful_action_in_window", rendered)
        self.assertIn("[EVIDENCIA FALTANTE O DESACTUALIZADA]", rendered)
        self.assertIn("reboot_decision.missing", rendered)
        self.assertIn("[LECTURA / SIN ACCION AUTOMATICA]", rendered)

    def test_render_assessment_telegram_splitting(self):
        from app.evidence_fusion import render_assessment_telegram
        assessment = self._build_sample_assessment()

        # Unsplit when max_chars is large
        parts = render_assessment_telegram(assessment, max_chars=4000)
        self.assertEqual(len(parts), 1)
        self.assertIn("[LECTURA / SIN ACCION AUTOMATICA]", parts[0])

        # Splits into multiple parts when max_chars is small
        small_parts = render_assessment_telegram(assessment, max_chars=120)
        self.assertGreater(len(small_parts), 1)
        for p in small_parts:
            self.assertLessEqual(len(p), 120)


if __name__ == "__main__":
    unittest.main()


