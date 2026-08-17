"""
Evidence Fusion — Spec 023 Phase 2 implementation.

Pure domain module: no IO, no wall-clock calls, no miner state mutations.
Every function receives all inputs as arguments and returns immutable values.

Public surface (all exported symbols pass the T002-T007 red contracts):

    FusionConfig          — validated configuration from a flat mapping
    EvidenceFact          — frozen, canonical, normalized evidence unit
    CauseHypothesis       — frozen hypothesis with level, facts and codes
    IncidentAssessment    — frozen top-level assessment; no action fields
    FusionResult          — result envelope (assessment + status)

    classify_freshness        — FR-001: fresh / stale / future_skew / unknown
    map_clock_quality         — FR-002: system / system_local / ... / unknown
    validate_fact_code        — FR-015: fail-closed for unrecognized families
    sort_facts_canonical      — FR-012: stable (effective_ts, source, id, code)
    compute_evidence_digest   — FR-012: deterministic SHA-256, no IDs/ts
    compute_confidence_ceiling— FR-003/FR-010: minimum ceiling governs
    max_cause_level           — FR-004/FR-006: non-causal conditions
    evaluate_hypothesis       — FR-005: supporting/contradicting/missing
    detect_fleet_pattern      — FR-006: >= 2 distinct miners in window
    is_within_attribution_window — FR-007: action attribution

Safety boundary: this module cannot call external CLIs, alter miner state,
modify action policies, or interact with the scheduling subsystem.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
from typing import Any, Mapping, Optional, Sequence

# ---------------------------------------------------------------------------
# Ruleset version — code-owned; increment when normalization semantics change
# ---------------------------------------------------------------------------
RULESET_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Stable code families (FR-015: unknown families fail closed)
# ---------------------------------------------------------------------------
_RECOGNIZED_FAMILIES = frozenset(
    {
        "signal",
        "restart",
        "action",
        "firmware",
        "quality",
        "fleet",
        "collector",
        "acquisition",
        "power",
    }
)

# ---------------------------------------------------------------------------
# Clock quality values (FR-002)
# ---------------------------------------------------------------------------
_VALID_CLOCK_QUALITIES = frozenset(
    {"system", "system_local", "fixed_utc_offset", "unparsed", "unknown"}
)

# ---------------------------------------------------------------------------
# Confidence levels (FR-003)
# ---------------------------------------------------------------------------
_LEVEL_RANK: dict[str, int] = {
    "observed": 0,
    "suspected": 1,
    "confirmed": 2,
}
_RANK_LEVEL = {v: k for k, v in _LEVEL_RANK.items()}

# Ceiling table: condition string -> maximum level (FR-010)
_CEILING_TABLE: dict[str, str] = {
    "stale": "observed",
    "future_skew": "observed",
    "unparsed_clock": "observed",
    "partial_collector": "observed",
    "fresh_symptom": "suspected",
    "temporal_proximity_only": "suspected",
    "direct_cause_fresh_valid": "confirmed",
}

# Non-causal conditions: these conditions alone can never produce "confirmed"
# for any cause (FR-004, FR-006)
_NON_CAUSAL_CONDITIONS = frozenset(
    {
        "temporal_proximity_only",
        "fleet.concurrent_degradation",
        "signal.current_offline",
        "signal.current_low",
        "fresh_symptom",
        "stale",
        "future_skew",
        "unparsed_clock",
        "partial_collector",
    }
)

# Cause codes that require external power-source proof (Spec 024 gate)
_POWER_CONFIRMATION_REQUIRES_EXTERNAL = frozenset({"power.electrical_fault"})


# ---------------------------------------------------------------------------
# FusionConfig
# ---------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class FusionConfig:
    """Validated fusion configuration (FR-013).

    Always construct via :meth:`from_mapping`; never instantiate directly.
    """

    enabled: bool
    context_hours: int
    fleet_window_seconds: int

    # Existing diagnosis keys — read-only copies, not validated here
    diagnosis_stale_seconds: int
    diagnosis_firmware_window_hours: int
    diagnosis_collector_stale_seconds: int
    restart_attribution_window_seconds: int

    @classmethod
    def from_mapping(cls, cfg: Mapping[str, Any]) -> "tuple[FusionConfig, list[str]]":
        """Parse and validate from a flat config mapping.

        Returns ``(FusionConfig, warnings)`` where ``warnings`` is a list of
        human-readable strings for each invalid value that fell back to a safe
        default.  Never raises.
        """
        warnings: list[str] = []

        # --- enabled ---
        raw_enabled = cfg.get("incident_fusion_enabled", False)
        if not isinstance(raw_enabled, bool):
            enabled = False
            warnings.append(
                f"incident_fusion_enabled: expected bool, got "
                f"{type(raw_enabled).__name__!r}; disabling fusion"
            )
        else:
            enabled = raw_enabled

        # --- context_hours ---
        raw_hours = cfg.get("incident_fusion_context_hours", 24)
        context_hours = 24
        try:
            v = float(raw_hours)
            if not math.isfinite(v):
                raise ValueError("non-finite")
            v_int = int(v)
            if 1 <= v_int <= 168:
                context_hours = v_int
            else:
                warnings.append(
                    f"incident_fusion_context_hours: {raw_hours!r} out of range "
                    f"[1, 168]; using default 24"
                )
        except (TypeError, ValueError):
            warnings.append(
                f"incident_fusion_context_hours: invalid value {raw_hours!r}; "
                f"using default 24"
            )

        # --- fleet_window_seconds ---
        raw_fleet = cfg.get("incident_fusion_fleet_window_seconds", 60)
        fleet_window_seconds = 60
        try:
            v = float(raw_fleet)
            if not math.isfinite(v):
                raise ValueError("non-finite")
            v_int = int(v)
            if 30 <= v_int <= 300:
                fleet_window_seconds = v_int
            else:
                warnings.append(
                    f"incident_fusion_fleet_window_seconds: {raw_fleet!r} out of "
                    f"range [30, 300]; using default 60"
                )
        except (TypeError, ValueError):
            warnings.append(
                f"incident_fusion_fleet_window_seconds: invalid value "
                f"{raw_fleet!r}; using default 60"
            )

        # --- existing diagnosis keys (no re-validation; keep current behavior) ---
        def _int_default(key: str, default: int) -> int:
            try:
                return int(cfg.get(key, default))
            except (TypeError, ValueError):
                return default

        return cls(
            enabled=enabled,
            context_hours=context_hours,
            fleet_window_seconds=fleet_window_seconds,
            diagnosis_stale_seconds=_int_default("diagnosis_stale_seconds", 900),
            diagnosis_firmware_window_hours=_int_default(
                "diagnosis_firmware_window_hours", 24
            ),
            diagnosis_collector_stale_seconds=_int_default(
                "diagnosis_collector_stale_seconds", 3600
            ),
            restart_attribution_window_seconds=_int_default(
                "restart_attribution_window_seconds", 900
            ),
        ), warnings


# ---------------------------------------------------------------------------
# EvidenceFact — immutable, canonical evidence unit (FR-001)
# ---------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class EvidenceFact:
    """A single normalized evidence unit from one EventStore source row.

    Immutable by construction (frozen dataclass).
    ``fact_id`` format: ``<source_table>:<source_row_id>:<code>``
    """

    fact_id: str
    subject_type: str          # "miner" | "fleet" | "collector"
    subject_key: str
    source: str                # EventStore table name
    source_row_id: int
    code: str                  # dot-notation family.detail code
    effective_ts: float        # authoritative event time (epoch seconds)
    ingested_ts: Optional[float]
    freshness: str             # "fresh" | "stale" | "future_skew" | "unknown"
    clock_quality: str         # see _VALID_CLOCK_QUALITIES
    authority: Optional[str]   # Spec 022 acquisition_authority
    quality: Optional[str]     # Spec 022 quality category
    reason_code: Optional[str] # Spec 022 acquisition_reason_code
    value: Optional[float]
    units: Optional[str]
    confidence_ceiling: str    # pre-computed per-fact ceiling


# ---------------------------------------------------------------------------
# CauseHypothesis — frozen hypothesis (FR-003)
# ---------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class CauseHypothesis:
    """A candidate causal explanation with evidence traceability."""

    cause_code: str
    level: str                          # "observed" | "suspected" | "confirmed"
    supporting_fact_ids: tuple[str, ...]
    contradicting_fact_ids: tuple[str, ...]
    missing_requirement_codes: tuple[str, ...]
    confidence_ceiling: str
    description: str


# ---------------------------------------------------------------------------
# IncidentAssessment — top-level assessment (no action fields, SC-006)
# ---------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class IncidentAssessment:
    """Read-only incident assessment.

    Contains no fields that could drive an action decision.
    Forbidden fields: allow_reboot, trigger_reboot, external_cli_command,
    auto_action, reboot_eligible.
    """

    subject_type: str
    subject_ref: str
    miner_key: Optional[str]
    ruleset_version: str
    window_start_ts: float
    window_end_ts: float
    assessment_now_ts: float
    status: str                      # "complete" | "incomplete" | "unavailable"
    evidence_digest: str             # SHA-256 hex of canonical fact set
    hypotheses: tuple[CauseHypothesis, ...]
    observed_facts: tuple[EvidenceFact, ...]
    contradictions: tuple[str, ...]  # decisive contradiction codes
    missing_evidence: tuple[str, ...]


# ---------------------------------------------------------------------------
# FR-001: Freshness classification
# ---------------------------------------------------------------------------

_FUTURE_SKEW_TOLERANCE_S = 5.0


def classify_freshness(
    effective_ts: float,
    assessment_now_ts: float,
    stale_threshold_s: float,
) -> str:
    """Return 'fresh', 'stale', 'future_skew', or 'unknown'.

    - future_skew  : effective_ts > assessment_now_ts + 5s
    - fresh        : within stale_threshold_s of assessment_now_ts
    - stale        : older than stale_threshold_s
    - unknown      : non-finite inputs
    """
    try:
        if not (math.isfinite(effective_ts) and math.isfinite(assessment_now_ts)
                and math.isfinite(stale_threshold_s)):
            return "unknown"
    except TypeError:
        return "unknown"

    if effective_ts > assessment_now_ts + _FUTURE_SKEW_TOLERANCE_S:
        return "future_skew"
    age = assessment_now_ts - effective_ts
    if age <= stale_threshold_s:
        return "fresh"
    return "stale"


# ---------------------------------------------------------------------------
# FR-002: Clock quality mapping
# ---------------------------------------------------------------------------

# Source tables that always use the system clock
_SYSTEM_CLOCK_SOURCES = frozenset(
    {"telemetry_samples", "operational_events", "reboot_decisions", "collector_runs"}
)


def map_clock_quality(
    source_table: str,
    source_clock: Optional[str] = None,
) -> str:
    """Return the clock quality string for a given source table + clock field.

    - System-clock sources → 'system'
    - firmware_events with a valid source_clock → as stored
    - firmware_events with None / 'unparsed' → 'unparsed'
    - Unknown source table → 'unknown'
    """
    if source_table in _SYSTEM_CLOCK_SOURCES:
        return "system"
    if source_table == "firmware_events":
        if source_clock and source_clock in _VALID_CLOCK_QUALITIES:
            return source_clock
        return "unparsed"
    return "unknown"


# ---------------------------------------------------------------------------
# FR-015: Fact code validation (fail closed)
# ---------------------------------------------------------------------------


def validate_fact_code(code: str) -> bool:
    """Return True iff ``code`` belongs to a recognized stable family.

    Unknown families fail closed: they cannot support any hypothesis.
    """
    if not isinstance(code, str) or "." not in code:
        return False
    family = code.split(".", 1)[0]
    return family in _RECOGNIZED_FAMILIES


# ---------------------------------------------------------------------------
# FR-012: Canonical ordering and evidence digest
# ---------------------------------------------------------------------------


def sort_facts_canonical(facts: Sequence[EvidenceFact]) -> list[EvidenceFact]:
    """Return facts sorted by (effective_ts, source, source_row_id, code).

    Tie-breaking is total and stable; equal facts remain in original order
    (sort is stable in CPython).
    """
    return sorted(
        facts,
        key=lambda f: (f.effective_ts, f.source, f.source_row_id, f.code),
    )


def _canonical_fact_dict(fact: EvidenceFact) -> dict:
    """Produce a digest-safe dict for one fact (no IDs or ingestion ts)."""
    d: dict = {
        "code": fact.code,
        "confidence_ceiling": fact.confidence_ceiling,
        "source": fact.source,
        "subject_key": fact.subject_key,
        "subject_type": fact.subject_type,
    }
    # Only include numeric value if finite
    if fact.value is not None:
        if math.isfinite(fact.value):
            d["value"] = fact.value
        # Non-finite values are excluded from the digest per contract
    if fact.units is not None:
        d["units"] = fact.units
    if fact.authority is not None:
        d["authority"] = fact.authority
    return d


def compute_evidence_digest(
    facts: Sequence[EvidenceFact],
    ruleset_version: str,
) -> str:
    """Return a deterministic SHA-256 hex digest of the canonical fact set.

    - Facts sorted canonically before hashing.
    - ``fact_id``, ``source_row_id``, ``ingested_ts``, and ``effective_ts``
      are excluded (they contain database IDs and creation metadata).
    - NaN and Infinity values are excluded.
    - The ruleset version is mixed in so version changes produce a new digest.
    """
    sorted_facts = sort_facts_canonical(list(facts))
    payload = {
        "ruleset_version": ruleset_version,
        "facts": [_canonical_fact_dict(f) for f in sorted_facts],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# FR-003/FR-010: Confidence ceilings
# ---------------------------------------------------------------------------


def compute_confidence_ceiling(conditions: list[str]) -> str:
    """Return the maximum achievable confidence level given a list of conditions.

    The final ceiling is the minimum across all applicable ceilings.
    More low-quality conditions never increase confidence.
    Unknown conditions are ignored (they do not raise ceiling, do not lower it).
    """
    min_rank = _LEVEL_RANK["confirmed"]  # start optimistic
    for cond in conditions:
        if cond in _CEILING_TABLE:
            rank = _LEVEL_RANK[_CEILING_TABLE[cond]]
            if rank < min_rank:
                min_rank = rank
    return _RANK_LEVEL[min_rank]


# ---------------------------------------------------------------------------
# FR-004/FR-006: max_cause_level
# ---------------------------------------------------------------------------


def max_cause_level(cause_code: str, evidence_conditions: list[str]) -> str:
    """Return the maximum achievable level for a cause given conditions.

    Enforces mandatory conservative rules from evidence-rules.md:
    - temporal_proximity_only alone → at most 'suspected'
    - fleet.concurrent_degradation → at most 'suspected' for most causes
    - power.* confirmation requires external power source (Spec 024)
    - API OFFLINE / LOW alone → at most 'suspected'

    Returns 'observed', 'suspected', or 'confirmed'.
    """
    # Ceiling from conditions
    ceiling = compute_confidence_ceiling(evidence_conditions)

    # Power confirmation blocked until Spec 024 validates an external source
    if cause_code in _POWER_CONFIRMATION_REQUIRES_EXTERNAL:
        ceiling_rank = min(_LEVEL_RANK[ceiling], _LEVEL_RANK["suspected"])
        ceiling = _RANK_LEVEL[ceiling_rank]

    # If every condition is non-causal, cap at 'suspected'
    cond_set = set(evidence_conditions)
    if cond_set and cond_set.issubset(_NON_CAUSAL_CONDITIONS):
        ceiling_rank = min(_LEVEL_RANK[ceiling], _LEVEL_RANK["suspected"])
        ceiling = _RANK_LEVEL[ceiling_rank]

    return ceiling


# ---------------------------------------------------------------------------
# FR-005: Hypothesis evaluation
# ---------------------------------------------------------------------------


def evaluate_hypothesis(
    supporting: list[str],
    contradicting: list[str],
    missing: list[str],
) -> dict:
    """Evaluate a hypothesis from its supporting conditions and contradiction codes.

    Returns a dict with:
      - level: "observed" | "suspected" | "confirmed"
      - contradicting_fact_ids: list of decisive contradiction codes
      - missing_requirement_codes: list of missing requirement codes
    """
    # Compute ceiling from supporting conditions
    level = compute_confidence_ceiling(supporting) if supporting else "observed"

    # Any decisive contradiction prevents confirmation
    if contradicting:
        # Drop to at most 'suspected'
        rank = min(_LEVEL_RANK[level], _LEVEL_RANK["suspected"])
        level = _RANK_LEVEL[rank]

    # Missing required evidence prevents confirmation
    if missing:
        rank = min(_LEVEL_RANK[level], _LEVEL_RANK["suspected"])
        level = _RANK_LEVEL[rank]

    return {
        "level": level,
        "contradicting_fact_ids": list(contradicting),
        "missing_requirement_codes": list(missing),
    }


# ---------------------------------------------------------------------------
# FR-006: Fleet pattern detection
# ---------------------------------------------------------------------------


def detect_fleet_pattern(
    facts: Sequence[EvidenceFact],
    fleet_window_seconds: float = 60.0,
) -> Optional[dict]:
    """Detect a concurrent degradation fleet pattern.

    Returns a dict with ``code``, ``miner_keys``, ``window_span_s`` and
    ``first_fact_ids`` if at least 2 distinct miners have degradation facts
    within ``fleet_window_seconds`` of each other; otherwise None.

    Degradation codes: signal.current_offline, signal.current_low.
    """
    _DEGRADATION_CODES = frozenset({"signal.current_offline", "signal.current_low"})

    degradation_facts = [f for f in facts if f.code in _DEGRADATION_CODES]
    if len(degradation_facts) < 2:
        return None

    # Sort by effective_ts
    sorted_d = sorted(degradation_facts, key=lambda f: f.effective_ts)

    # Sliding window: find first window where >= 2 distinct miners appear
    for i, anchor in enumerate(sorted_d):
        window_end = anchor.effective_ts + fleet_window_seconds
        in_window = [
            f for f in sorted_d[i:]
            if f.effective_ts <= window_end
        ]
        distinct_miners = {f.subject_key for f in in_window}
        if len(distinct_miners) >= 2:
            span = in_window[-1].effective_ts - anchor.effective_ts
            return {
                "code": "fleet.concurrent_degradation",
                "miner_keys": sorted(distinct_miners),
                "window_span_s": span,
                "first_fact_ids": [f.fact_id for f in in_window],
            }
    return None


# ---------------------------------------------------------------------------
# FR-007: Action attribution window
# ---------------------------------------------------------------------------


def is_within_attribution_window(
    action_ts: float,
    restart_ts: float,
    window_seconds: float = 900.0,
) -> bool:
    """Return True iff ``restart_ts`` is within ``window_seconds`` of ``action_ts``.

    Restart must occur after the action. Restart at exactly the window boundary
    (action_ts + window_seconds) is within range.
    """
    return 0.0 <= (restart_ts - action_ts) <= window_seconds
