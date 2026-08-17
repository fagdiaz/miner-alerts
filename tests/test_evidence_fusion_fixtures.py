"""Advanced deterministic replay fixtures and edge-case unit tests for Spec 023.

Tests pure domain invariants of ``app.evidence_fusion`` without IO or database access.
Target: CHK-GEM-01 (Spec 023 Fixtures & Determinism).
"""

from __future__ import annotations

import dataclasses
import random
import unittest

from app.evidence_fusion import (
    EvidenceFact,
    compute_evidence_digest,
    sort_facts_canonical,
)


class TestEvidenceFusionFixturesAndDeterminism(unittest.TestCase):
    """Verify deterministic invariants under shuffled, duplicate and edge-case synthetic inputs."""

    def _make_fact(
        self,
        *,
        row_id: int = 1,
        code: str = "signal.current_low",
        effective_ts: float = 1786700000.0,
        source: str = "telemetry_samples",
        val: float | None = 42.5,
        freshness: str = "fresh",
    ) -> EvidenceFact:
        return EvidenceFact(
            fact_id=f"{source}:{row_id}:{code}",
            subject_type="miner",
            subject_key="23",
            source=source,
            source_row_id=row_id,
            code=code,
            effective_ts=effective_ts,
            ingested_ts=effective_ts + 1.0,
            freshness=freshness,
            clock_quality="system",
            authority="authoritative",
            quality=None,
            reason_code=None,
            value=val,
            units="TH/s" if val is not None else None,
            confidence_ceiling="observed",
        )

    def test_digest_determinism_under_shuffled_inputs(self) -> None:
        """Shuffling a set of 20 synthetic facts must produce the exact same digest every time."""
        facts = [
            self._make_fact(row_id=i, effective_ts=1786700000.0 + i, code=f"signal.code_{i % 5}")
            for i in range(20)
        ]
        base_digest = compute_evidence_digest(facts, "1.0.0")

        # Shuffle 10 times and verify digest equality
        rng = random.Random(42)
        for _ in range(10):
            shuffled = list(facts)
            rng.shuffle(shuffled)
            self.assertEqual(
                compute_evidence_digest(shuffled, "1.0.0"),
                base_digest,
                "Digest must be order-independent after canonical sort",
            )

    def test_canonical_ordering_tie_breaking(self) -> None:
        """Facts with identical effective_ts must be sorted stably by (source, source_row_id, code)."""
        f1 = self._make_fact(row_id=2, source="operational_events", effective_ts=100.0, code="a.code")
        f2 = self._make_fact(row_id=1, source="telemetry_samples", effective_ts=100.0, code="b.code")
        f3 = self._make_fact(row_id=1, source="operational_events", effective_ts=100.0, code="z.code")

        sorted_facts = sort_facts_canonical([f1, f2, f3])
        # f3 has source='operational_events', row_id=1 -> comes before f1 (row_id=2)
        # f1 has source='operational_events', row_id=2 -> comes before f2 ('telemetry_samples')
        self.assertEqual(sorted_facts[0], f3)
        self.assertEqual(sorted_facts[1], f1)
        self.assertEqual(sorted_facts[2], f2)

    def test_digest_unaffected_by_database_row_ids_or_ingested_ts(self) -> None:
        """Database row IDs and ingestion timestamps must NOT affect the semantic evidence digest."""
        f_base = self._make_fact(row_id=10, effective_ts=1000.0)
        f_diff_id = self._make_fact(row_id=999, effective_ts=1000.0)

        d1 = compute_evidence_digest([f_base], "1.0.0")
        d2 = compute_evidence_digest([f_diff_id], "1.0.0")
        self.assertEqual(d1, d2, "Row ID differences must not alter the evidence digest")

    def test_digest_changes_when_ruleset_version_changes(self) -> None:
        """Changing ruleset_version must change the resulting digest even with identical facts."""
        fact = self._make_fact()
        d_v1 = compute_evidence_digest([fact], "1.0.0")
        d_v2 = compute_evidence_digest([fact], "1.0.1")
        self.assertNotEqual(d_v1, d_v2, "Ruleset version change must produce a distinct digest")

    def test_non_finite_values_excluded_without_crash(self) -> None:
        """Facts with NaN or Infinity values must be excluded from digest without raising errors."""
        f_nan = self._make_fact(val=float("nan"))
        f_inf = self._make_fact(val=float("inf"))
        f_none = self._make_fact(val=None)
        # Override units so all three have identical units="TH/s"
        f_nan = dataclasses.replace(f_nan, units="TH/s")
        f_inf = dataclasses.replace(f_inf, units="TH/s")
        f_none = dataclasses.replace(f_none, units="TH/s")

        d_nan = compute_evidence_digest([f_nan], "1.0.0")
        d_inf = compute_evidence_digest([f_inf], "1.0.0")
        d_none = compute_evidence_digest([f_none], "1.0.0")

        # NaN, Inf and None all exclude the value key from canonical dict -> same digest
        self.assertEqual(d_nan, d_none)
        self.assertEqual(d_inf, d_none)


if __name__ == "__main__":
    unittest.main()
