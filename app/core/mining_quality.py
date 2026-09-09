from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional


STATUS_LEARNING = "learning"
STATUS_STABLE = "stable"
STATUS_WATCH = "watch"
STATUS_CRITICAL = "critical"

_CHAIN_STATE_RE = re.compile(r"^chain_state(\d+)$", re.IGNORECASE)
_CHAIN_FAULT_RE = re.compile(r"^chain_fault(\d+)$", re.IGNORECASE)
_HEALTHY_CHAIN_STATES = frozenset(("mining", "alive", "ok", "working"))
_TRANSITION_MARKERS = ("tune", "tuning", "autotune", "calibrat", "start", "init", "warm")
_EMPTY_FAULT_VALUES = frozenset(("", "0", "none", "ok", "false", "normal", "no", "null", "n/a", "na", "-"))


@dataclass(frozen=True)
class MiningQualityTelemetry:
    accepted_shares_total: Optional[int] = None
    rejected_shares_total: Optional[int] = None
    stale_shares_total: Optional[int] = None
    chain_fault_count: Optional[int] = None
    chains_not_mining_count: Optional[int] = None
    chains_transitioning_count: Optional[int] = None
    quality_flags: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "accepted_shares_total": self.accepted_shares_total,
            "rejected_shares_total": self.rejected_shares_total,
            "stale_shares_total": self.stale_shares_total,
            "chain_fault_count": self.chain_fault_count,
            "chains_not_mining_count": self.chains_not_mining_count,
            "chains_transitioning_count": self.chains_transitioning_count,
            "quality_flags": list(self.quality_flags),
        }


@dataclass(frozen=True)
class QualityDelta:
    interval_seconds: Optional[float] = None
    accepted: Optional[int] = None
    rejected: Optional[int] = None
    stale: Optional[int] = None
    hw_errors: Optional[int] = None
    rejected_percent: Optional[float] = None
    stale_percent: Optional[float] = None
    counter_reset: bool = False

    @property
    def total_shares(self) -> Optional[int]:
        if self.accepted is None or self.rejected is None or self.stale is None:
            return None
        return self.accepted + self.rejected + self.stale

    def as_dict(self) -> dict[str, Any]:
        return {
            "interval_seconds": self.interval_seconds,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "stale": self.stale,
            "hw_errors": self.hw_errors,
            "rejected_percent": self.rejected_percent,
            "stale_percent": self.stale_percent,
            "counter_reset": self.counter_reset,
            "total_shares": self.total_shares,
        }


@dataclass(frozen=True)
class QualityReason:
    code: str
    severity: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
        }


@dataclass(frozen=True)
class QualityAssessment:
    status: str
    sample_count: int
    comparable_intervals: int
    required_intervals: int
    confidence: float
    latest: Mapping[str, Any]
    delta: QualityDelta
    reasons: tuple[QualityReason, ...]

    @property
    def reason_codes(self) -> tuple[str, ...]:
        return tuple(reason.code for reason in self.reasons)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "sample_count": self.sample_count,
            "comparable_intervals": self.comparable_intervals,
            "required_intervals": self.required_intervals,
            "confidence": self.confidence,
            "latest": dict(self.latest),
            "delta": self.delta.as_dict(),
            "reasons": [reason.as_dict() for reason in self.reasons],
            "reason_codes": list(self.reason_codes),
        }


def _finite(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _counter(value: Any) -> Optional[int]:
    number = _finite(value)
    if number is None or number < 0 or not number.is_integer():
        return None
    return int(number)


def _dicts(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            if isinstance(nested, (dict, list, tuple)):
                yield from _dicts(nested)
    elif isinstance(value, (list, tuple)):
        for item in value:
            if isinstance(item, (dict, list, tuple)):
                yield from _dicts(item)


def _summary_entry(summary: Any) -> Mapping[str, Any]:
    if isinstance(summary, dict) and "SUMMARY" in summary:
        entries = summary.get("SUMMARY")
        if isinstance(entries, list):
            return next((entry for entry in entries if isinstance(entry, dict)), {})
        return entries if isinstance(entries, dict) else {}
    return summary if isinstance(summary, Mapping) else {}


def normalize_mining_quality(
    summary: Any,
    stats_response: Any,
    *,
    expected_boards: Optional[int] = None,
) -> MiningQualityTelemetry:
    """Normalize bounded quality evidence from responses already fetched this tick."""
    summary_row = _summary_entry(summary)
    accepted = _counter(summary_row.get("Accepted"))
    rejected = _counter(summary_row.get("Rejected"))
    stale = _counter(summary_row.get("Stale"))

    root = (
        stats_response.get("STATS")
        if isinstance(stats_response, dict) and "STATS" in stats_response
        else stats_response
    )
    states: dict[str, str] = {}
    faults: dict[str, str] = {}
    state_field_ids: set[str] = set()
    fault_field_ids: set[str] = set()
    for item in _dicts(root):
        for raw_key, raw_value in item.items():
            key = str(raw_key).strip().lower()
            state_match = _CHAIN_STATE_RE.fullmatch(key)
            if state_match:
                state_field_ids.add(state_match.group(1))
                value = str(raw_value or "").strip().lower()
                if value:
                    states[state_match.group(1)] = value[:40]
                continue
            fault_match = _CHAIN_FAULT_RE.fullmatch(key)
            if fault_match:
                fault_field_ids.add(fault_match.group(1))
                value = str(raw_value or "").strip().lower()
                if value not in _EMPTY_FAULT_VALUES:
                    faults[fault_match.group(1)] = value[:80]

    transitioning = 0
    not_mining = 0
    for state in states.values():
        if state in _HEALTHY_CHAIN_STATES:
            continue
        if any(marker in state for marker in _TRANSITION_MARKERS):
            transitioning += 1
        else:
            not_mining += 1

    flags: list[str] = []
    if accepted is None or rejected is None or stale is None:
        flags.append("share_counters_missing")
    if not state_field_ids and not fault_field_ids:
        flags.append("chain_signal_missing")
    observed_chain_ids = state_field_ids | fault_field_ids
    if (
        expected_boards is not None
        and expected_boards > 0
        and observed_chain_ids
        and len(observed_chain_ids) < expected_boards
    ):
        flags.append("chain_signal_below_expected")
    if faults:
        flags.append("chain_fault_present")
    if not_mining:
        flags.append("chain_not_mining")
    if transitioning:
        flags.append("firmware_transition")

    return MiningQualityTelemetry(
        accepted_shares_total=accepted,
        rejected_shares_total=rejected,
        stale_shares_total=stale,
        chain_fault_count=len(faults) if fault_field_ids else None,
        chains_not_mining_count=not_mining if state_field_ids else None,
        chains_transitioning_count=transitioning if state_field_ids else None,
        quality_flags=tuple(flags),
    )


def _pair_delta(current: Mapping[str, Any], previous: Mapping[str, Any]) -> QualityDelta:
    current_elapsed = _counter(current.get("elapsed_seconds"))
    previous_elapsed = _counter(previous.get("elapsed_seconds"))
    current_observed = _finite(current.get("observed_ts"))
    previous_observed = _finite(previous.get("observed_ts"))
    fields = (
        "accepted_shares_total",
        "rejected_shares_total",
        "stale_shares_total",
    )
    current_counters = [_counter(current.get(field)) for field in fields]
    previous_counters = [_counter(previous.get(field)) for field in fields]
    current_hw = _counter(current.get("hw_errors_total"))
    previous_hw = _counter(previous.get("hw_errors_total"))

    elapsed_reset = (
        current_elapsed is not None
        and previous_elapsed is not None
        and current_elapsed < previous_elapsed
    )
    counters_reset = any(
        now is not None and before is not None and now < before
        for now, before in zip(current_counters, previous_counters)
    )
    hw_reset = current_hw is not None and previous_hw is not None and current_hw < previous_hw
    if elapsed_reset or counters_reset or hw_reset:
        return QualityDelta(counter_reset=True)
    if any(value is None for value in (*current_counters, *previous_counters)):
        return QualityDelta()

    accepted = int(current_counters[0] or 0) - int(previous_counters[0] or 0)
    rejected = int(current_counters[1] or 0) - int(previous_counters[1] or 0)
    stale = int(current_counters[2] or 0) - int(previous_counters[2] or 0)
    total = accepted + rejected + stale
    interval = None
    if current_elapsed is not None and previous_elapsed is not None:
        interval = float(current_elapsed - previous_elapsed)
    elif current_observed is not None and previous_observed is not None:
        interval = max(0.0, current_observed - previous_observed)
    hw_delta = None
    if current_hw is not None and previous_hw is not None:
        hw_delta = current_hw - previous_hw
    return QualityDelta(
        interval_seconds=interval,
        accepted=accepted,
        rejected=rejected,
        stale=stale,
        hw_errors=hw_delta,
        rejected_percent=round(rejected * 100.0 / total, 4) if total > 0 else None,
        stale_percent=round(stale * 100.0 / total, 4) if total > 0 else None,
    )


def _is_comparable(delta: QualityDelta) -> bool:
    return (
        not delta.counter_reset
        and delta.accepted is not None
        and delta.rejected is not None
        and delta.stale is not None
        and delta.interval_seconds is not None
        and delta.interval_seconds > 0
    )


def analyze_mining_quality(
    samples: Iterable[Mapping[str, Any]],
    *,
    min_intervals: int = 3,
    reject_warning_percent: float = 1.0,
    stale_warning_percent: float = 1.0,
    hw_error_delta_warning: int = 50,
    no_share_warning_seconds: float = 900.0,
) -> QualityAssessment:
    """Assess current mining quality from bounded persisted cumulative counters."""
    safe_min_intervals = max(1, min(int(min_intervals), 48))
    safe_reject = max(0.0, min(float(reject_warning_percent), 100.0))
    safe_stale = max(0.0, min(float(stale_warning_percent), 100.0))
    safe_hw = max(1, int(hw_error_delta_warning))
    safe_no_share = max(60.0, float(no_share_warning_seconds))
    rows = [dict(row) for row in samples if isinstance(row, Mapping)]
    rows.sort(key=lambda row: _finite(row.get("observed_ts")) or float("-inf"), reverse=True)
    rows = rows[:100]

    if not rows:
        reason = QualityReason("no_samples", STATUS_LEARNING, "Sin muestras de calidad.")
        return QualityAssessment(
            status=STATUS_LEARNING,
            sample_count=0,
            comparable_intervals=0,
            required_intervals=safe_min_intervals,
            confidence=0.0,
            latest={},
            delta=QualityDelta(),
            reasons=(reason,),
        )

    latest = rows[0]
    latest_delta = _pair_delta(rows[0], rows[1]) if len(rows) > 1 else QualityDelta()
    comparable_intervals = 0
    for index in range(len(rows) - 1):
        delta = _pair_delta(rows[index], rows[index + 1])
        if delta.counter_reset:
            break
        if not _is_comparable(delta):
            break
        comparable_intervals += 1

    critical_reasons: list[QualityReason] = []
    chain_faults = _counter(latest.get("chain_fault_count"))
    chains_not_mining = _counter(latest.get("chains_not_mining_count"))
    if chain_faults:
        critical_reasons.append(
            QualityReason(
                "chain_fault",
                STATUS_CRITICAL,
                f"Vnish informa fallas actuales en {chain_faults} cadena(s).",
            )
        )
    if chains_not_mining:
        critical_reasons.append(
            QualityReason(
                "chain_not_mining",
                STATUS_CRITICAL,
                f"{chains_not_mining} cadena(s) no estan minando.",
            )
        )
    if critical_reasons:
        return QualityAssessment(
            status=STATUS_CRITICAL,
            sample_count=len(rows),
            comparable_intervals=comparable_intervals,
            required_intervals=safe_min_intervals,
            confidence=round(min(1.0, comparable_intervals / safe_min_intervals), 4),
            latest=latest,
            delta=latest_delta,
            reasons=tuple(critical_reasons),
        )

    watch_reasons: list[QualityReason] = []
    transitions = _counter(latest.get("chains_transitioning_count"))
    if transitions:
        watch_reasons.append(
            QualityReason(
                "firmware_transition",
                STATUS_WATCH,
                f"{transitions} cadena(s) en transicion/autotune; observar antes de intervenir.",
            )
        )
    if latest_delta.rejected_percent is not None and latest_delta.rejected_percent >= safe_reject:
        watch_reasons.append(
            QualityReason(
                "rejected_share_rate",
                STATUS_WATCH,
                f"Shares rechazadas {latest_delta.rejected_percent:.2f}% en el ultimo intervalo.",
            )
        )
    if latest_delta.stale_percent is not None and latest_delta.stale_percent >= safe_stale:
        watch_reasons.append(
            QualityReason(
                "stale_share_rate",
                STATUS_WATCH,
                f"Shares stale {latest_delta.stale_percent:.2f}% en el ultimo intervalo.",
            )
        )
    if latest_delta.hw_errors is not None and latest_delta.hw_errors >= safe_hw:
        watch_reasons.append(
            QualityReason(
                "hardware_error_growth",
                STATUS_WATCH,
                f"Errores HW aumentaron {latest_delta.hw_errors} en el ultimo intervalo.",
            )
        )
    if (
        latest_delta.total_shares == 0
        and latest_delta.interval_seconds is not None
        and latest_delta.interval_seconds >= safe_no_share
    ):
        watch_reasons.append(
            QualityReason(
                "no_share_progress",
                STATUS_WATCH,
                f"Sin progreso de shares durante {latest_delta.interval_seconds:.0f}s.",
            )
        )
    if watch_reasons:
        status = STATUS_WATCH
        reasons = watch_reasons
    elif latest_delta.counter_reset:
        status = STATUS_LEARNING
        reasons = [
            QualityReason(
                "counter_reset",
                STATUS_LEARNING,
                "Uptime o contadores reiniciados; comienza un intervalo nuevo.",
            )
        ]
    elif not _is_comparable(latest_delta):
        status = STATUS_LEARNING
        reasons = [
            QualityReason(
                "quality_data_incomplete",
                STATUS_LEARNING,
                "Faltan dos muestras comparables con contadores de shares.",
            )
        ]
    elif comparable_intervals < safe_min_intervals:
        status = STATUS_LEARNING
        reasons = [
            QualityReason(
                "quality_learning",
                STATUS_LEARNING,
                f"Calidad en aprendizaje: {comparable_intervals}/{safe_min_intervals} intervalos.",
            )
        ]
    else:
        status = STATUS_STABLE
        reasons = []

    return QualityAssessment(
        status=status,
        sample_count=len(rows),
        comparable_intervals=comparable_intervals,
        required_intervals=safe_min_intervals,
        confidence=round(min(1.0, comparable_intervals / safe_min_intervals), 4),
        latest=latest,
        delta=latest_delta,
        reasons=tuple(reasons),
    )


def _display_delta(value: Optional[int]) -> str:
    return "N/A" if value is None else str(value)


def render_mining_quality(
    miner_name: str,
    assessment: QualityAssessment,
    *,
    max_reasons: int = 3,
) -> str:
    label = assessment.status.upper()
    if assessment.status == STATUS_LEARNING:
        label = f"LEARNING {assessment.comparable_intervals}/{assessment.required_intervals}"
    delta = assessment.delta
    interval = "N/A" if delta.interval_seconds is None else f"{delta.interval_seconds:.0f}s"
    lines = [
        f"{miner_name}  {label}",
        "interval={interval} accepted={accepted} rejected={rejected} stale={stale}".format(
            interval=interval,
            accepted=_display_delta(delta.accepted),
            rejected=_display_delta(delta.rejected),
            stale=_display_delta(delta.stale),
        ),
    ]
    if delta.rejected_percent is not None or delta.stale_percent is not None:
        rejected = "N/A" if delta.rejected_percent is None else f"{delta.rejected_percent:.2f}%"
        stale = "N/A" if delta.stale_percent is None else f"{delta.stale_percent:.2f}%"
        lines.append(
            f"reject={rejected} stale={stale} hw_delta={_display_delta(delta.hw_errors)}"
        )
    safe_reason_limit = max(1, min(int(max_reasons), 5))
    if assessment.reasons:
        lines.extend(f"- {reason.message}" for reason in assessment.reasons[:safe_reason_limit])
        hidden = len(assessment.reasons) - safe_reason_limit
        if hidden > 0:
            lines.append(f"- +{hidden} evidencias")
    else:
        lines.append("- Sin degradacion de calidad en el ultimo intervalo.")
    return "\n".join(lines)
