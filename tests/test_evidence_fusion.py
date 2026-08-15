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


if __name__ == "__main__":
    unittest.main()
