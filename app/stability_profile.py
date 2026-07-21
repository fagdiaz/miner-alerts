from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional


STATUS_LEARNING = "learning"
STATUS_STABLE = "stable"
STATUS_WATCH = "watch"
STATUS_CRITICAL = "critical"


@dataclass(frozen=True)
class MetricRule:
    relative_floor: float
    absolute_floor: float


@dataclass(frozen=True)
class MetricBand:
    metric: str
    sample_count: int
    median: float
    mad: float
    lower: float
    upper: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "sample_count": self.sample_count,
            "median": self.median,
            "mad": self.mad,
            "lower": self.lower,
            "upper": self.upper,
        }


@dataclass(frozen=True)
class DiagnosticReason:
    code: str
    severity: str
    message: str
    observed: Optional[float] = None
    lower: Optional[float] = None
    upper: Optional[float] = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "observed": self.observed,
            "lower": self.lower,
            "upper": self.upper,
        }


@dataclass(frozen=True)
class StabilityAssessment:
    status: str
    sample_count: int
    required_samples: int
    confidence: float
    observed_ts: Optional[float]
    age_seconds: Optional[float]
    latest: Mapping[str, Any]
    bands: Mapping[str, MetricBand]
    reasons: tuple[DiagnosticReason, ...]

    @property
    def reason_codes(self) -> tuple[str, ...]:
        return tuple(reason.code for reason in self.reasons)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "sample_count": self.sample_count,
            "required_samples": self.required_samples,
            "confidence": self.confidence,
            "observed_ts": self.observed_ts,
            "age_seconds": self.age_seconds,
            "latest": dict(self.latest),
            "bands": {name: band.as_dict() for name, band in self.bands.items()},
            "reasons": [reason.as_dict() for reason in self.reasons],
            "reason_codes": list(self.reason_codes),
        }


_METRIC_RULES: dict[str, MetricRule] = {
    "rate_ths": MetricRule(relative_floor=0.08, absolute_floor=2.0),
    "max_temp_c": MetricRule(relative_floor=0.05, absolute_floor=4.0),
    "chain_voltage_mv_avg": MetricRule(relative_floor=0.03, absolute_floor=100.0),
    "chain_power_w_total": MetricRule(relative_floor=0.10, absolute_floor=150.0),
    "frequency_mhz_avg": MetricRule(relative_floor=0.05, absolute_floor=20.0),
}


def _finite(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def _baseline_eligible(row: Mapping[str, Any]) -> bool:
    if not _as_bool(row.get("responded")):
        return False
    if str(row.get("state") or "").upper() != "OK":
        return False
    if _finite(row.get("rate_ths")) is None:
        return False
    active = _finite(row.get("active_boards"))
    expected = _finite(row.get("expected_boards"))
    if active is not None and expected is not None and active < expected:
        return False
    return True


def _metric_band(metric: str, rows: Iterable[Mapping[str, Any]]) -> Optional[MetricBand]:
    values = [value for row in rows if (value := _finite(row.get(metric))) is not None]
    if not values:
        return None
    center = float(statistics.median(values))
    mad = float(statistics.median(abs(value - center) for value in values))
    rule = _METRIC_RULES[metric]
    radius = max(
        abs(center) * rule.relative_floor,
        mad * 1.4826 * 3.0,
        rule.absolute_floor,
    )
    return MetricBand(
        metric=metric,
        sample_count=len(values),
        median=round(center, 4),
        mad=round(mad, 4),
        lower=round(center - radius, 4),
        upper=round(center + radius, 4),
    )


def _hard_reasons(
    latest: Mapping[str, Any],
    *,
    age_seconds: Optional[float],
    stale_after_seconds: float,
    high_temperature_c: float,
) -> list[DiagnosticReason]:
    reasons: list[DiagnosticReason] = []
    if age_seconds is None or age_seconds > stale_after_seconds:
        reasons.append(
            DiagnosticReason(
                "stale_sample",
                STATUS_CRITICAL,
                "Muestra historica ausente o vencida.",
                observed=age_seconds,
                upper=stale_after_seconds,
            )
        )

    responded = _as_bool(latest.get("responded"))
    state = str(latest.get("state") or "UNKNOWN").upper()
    if not responded:
        reasons.append(
            DiagnosticReason(
                "no_response",
                STATUS_CRITICAL,
                "El ultimo muestreo no obtuvo respuesta del minero.",
            )
        )
        if state == "OFFLINE":
            reasons.append(
                DiagnosticReason(
                    "state_offline",
                    STATUS_CRITICAL,
                    "Estado OFFLINE consistente con falta de respuesta.",
                )
            )

    rate = _finite(latest.get("rate_ths"))
    threshold = _finite(latest.get("threshold_ths"))
    if (
        state == "LOW"
        and rate is not None
        and threshold is not None
        and rate < threshold
    ):
        reasons.append(
            DiagnosticReason(
                "state_low",
                STATUS_CRITICAL,
                "Estado LOW consistente con el hashrate actual.",
            )
        )
    if responded and rate is None:
        reasons.append(
            DiagnosticReason(
                "invalid_rate",
                STATUS_CRITICAL,
                "El ultimo hashrate no es numerico.",
            )
        )
    elif rate is not None and threshold is not None and rate < threshold:
        reasons.append(
            DiagnosticReason(
                "rate_below_threshold",
                STATUS_CRITICAL,
                f"Hashrate {rate:.1f} TH/s debajo del umbral {threshold:.1f} TH/s.",
                observed=rate,
                lower=threshold,
            )
        )

    active = _finite(latest.get("active_boards"))
    expected = _finite(latest.get("expected_boards"))
    if active is not None and expected is not None and active < expected:
        if state == "HASHBOARD":
            reasons.append(
                DiagnosticReason(
                    "state_hashboard",
                    STATUS_CRITICAL,
                    "Estado HASHBOARD consistente con placas faltantes.",
                )
            )
        reasons.append(
            DiagnosticReason(
                "board_missing",
                STATUS_CRITICAL,
                f"Hashboards activas {int(active)}/{int(expected)}.",
                observed=active,
                lower=expected,
            )
        )

    temperature = _finite(latest.get("max_temp_c"))
    if temperature is not None and temperature >= high_temperature_c:
        reasons.append(
            DiagnosticReason(
                "high_temperature",
                STATUS_CRITICAL,
                f"Temperatura {temperature:.1f}C en o sobre limite {high_temperature_c:.1f}C.",
                observed=temperature,
                upper=high_temperature_c,
            )
        )
    return reasons


def _watch_reasons(
    latest: Mapping[str, Any],
    bands: Mapping[str, MetricBand],
) -> list[DiagnosticReason]:
    reasons: list[DiagnosticReason] = []
    state = str(latest.get("state") or "UNKNOWN").upper()
    if state != "OK":
        reasons.append(
            DiagnosticReason(
                "state_recovery_hysteresis",
                STATUS_WATCH,
                f"Estado persistido {state}, pero la señal actual ya no confirma la falla.",
            )
        )
    rate = _finite(latest.get("rate_ths"))
    rate_band = bands.get("rate_ths")
    if rate is not None and rate_band is not None and rate < rate_band.lower:
        reasons.append(
            DiagnosticReason(
                "rate_below_baseline",
                STATUS_WATCH,
                f"Hashrate {rate:.1f} TH/s debajo de base {rate_band.lower:.1f}-{rate_band.upper:.1f}.",
                observed=rate,
                lower=rate_band.lower,
                upper=rate_band.upper,
            )
        )

    temperature = _finite(latest.get("max_temp_c"))
    temperature_band = bands.get("max_temp_c")
    if (
        temperature is not None
        and temperature_band is not None
        and temperature > temperature_band.upper
    ):
        reasons.append(
            DiagnosticReason(
                "temperature_above_baseline",
                STATUS_WATCH,
                f"Temperatura {temperature:.1f}C sobre base hasta {temperature_band.upper:.1f}C.",
                observed=temperature,
                upper=temperature_band.upper,
            )
        )

    checks = (
        (
            "chain_voltage_mv_avg",
            "chain_voltage_drift",
            "Voltaje de cadena fuera de base (no es voltaje AC de entrada).",
        ),
        ("chain_power_w_total", "power_drift", "Consumo de cadenas fuera de base."),
        ("frequency_mhz_avg", "frequency_drift", "Frecuencia media fuera de base."),
    )
    for metric, code, message in checks:
        observed = _finite(latest.get(metric))
        band = bands.get(metric)
        if observed is None or band is None:
            continue
        if observed < band.lower or observed > band.upper:
            reasons.append(
                DiagnosticReason(
                    code,
                    STATUS_WATCH,
                    message,
                    observed=observed,
                    lower=band.lower,
                    upper=band.upper,
                )
            )
    return reasons


def analyze_stability(
    samples: Iterable[Mapping[str, Any]],
    *,
    now_ts: float,
    stale_after_seconds: float = 900.0,
    min_samples: int = 12,
    high_temperature_c: float = 85.0,
) -> StabilityAssessment:
    """Build an action-free assessment from bounded persisted telemetry rows."""
    safe_min_samples = max(3, min(int(min_samples), 288))
    safe_stale = max(30.0, float(stale_after_seconds))
    safe_high_temperature = max(1.0, float(high_temperature_c))
    rows = [dict(row) for row in samples if isinstance(row, Mapping)]
    rows.sort(key=lambda row: _finite(row.get("observed_ts")) or float("-inf"), reverse=True)

    if not rows:
        reason = DiagnosticReason(
            "no_samples",
            STATUS_LEARNING,
            "Sin muestras historicas para construir el baseline.",
        )
        return StabilityAssessment(
            status=STATUS_LEARNING,
            sample_count=0,
            required_samples=safe_min_samples,
            confidence=0.0,
            observed_ts=None,
            age_seconds=None,
            latest={},
            bands={},
            reasons=(reason,),
        )

    latest = rows[0]
    baseline_rows = [row for row in rows[1:] if _baseline_eligible(row)]
    observed_ts = _finite(latest.get("observed_ts"))
    age_seconds = None if observed_ts is None else max(0.0, float(now_ts) - observed_ts)
    bands: dict[str, MetricBand] = {}
    for metric in _METRIC_RULES:
        band = _metric_band(metric, baseline_rows)
        if band is not None:
            bands[metric] = band

    hard_reasons = _hard_reasons(
        latest,
        age_seconds=age_seconds,
        stale_after_seconds=safe_stale,
        high_temperature_c=safe_high_temperature,
    )
    sample_count = len(baseline_rows)
    confidence = round(min(1.0, sample_count / safe_min_samples), 4)
    if hard_reasons:
        status = STATUS_CRITICAL
        reasons = hard_reasons
    elif sample_count < safe_min_samples:
        status = STATUS_LEARNING
        reasons = [
            DiagnosticReason(
                "baseline_learning",
                STATUS_LEARNING,
                f"Baseline en aprendizaje: {sample_count}/{safe_min_samples} muestras saludables.",
            )
        ]
    else:
        reasons = _watch_reasons(latest, bands)
        status = STATUS_WATCH if reasons else STATUS_STABLE

    return StabilityAssessment(
        status=status,
        sample_count=sample_count,
        required_samples=safe_min_samples,
        confidence=confidence,
        observed_ts=observed_ts,
        age_seconds=age_seconds,
        latest=latest,
        bands=bands,
        reasons=tuple(reasons),
    )


def _display_number(value: Any, suffix: str = "", digits: int = 1) -> str:
    number = _finite(value)
    return "N/A" if number is None else f"{number:.{digits}f}{suffix}"


def render_stability_assessment(
    miner_name: str,
    assessment: StabilityAssessment,
    *,
    max_reasons: int = 3,
) -> str:
    status_label = assessment.status.upper()
    if assessment.status == STATUS_LEARNING:
        status_label = (
            f"LEARNING {assessment.sample_count}/{assessment.required_samples}"
        )
    latest = assessment.latest
    active = _finite(latest.get("active_boards"))
    expected = _finite(latest.get("expected_boards"))
    boards = (
        f"{int(active)}/{int(expected)}"
        if active is not None and expected is not None
        else "N/A"
    )
    age = "N/A" if assessment.age_seconds is None else f"{assessment.age_seconds:.0f}s"
    lines = [
        f"{miner_name}  {status_label}",
        "hash={rate} temp={temp} boards={boards} age={age}".format(
            rate=_display_number(latest.get("rate_ths"), " TH/s"),
            temp=_display_number(latest.get("max_temp_c"), "C"),
            boards=boards,
            age=age,
        ),
    ]
    rate_band = assessment.bands.get("rate_ths")
    if rate_band is not None and assessment.sample_count >= assessment.required_samples:
        lines.append(f"base_hash={rate_band.lower:.1f}-{rate_band.upper:.1f} TH/s")
    safe_reason_limit = max(1, min(int(max_reasons), 5))
    if assessment.reasons:
        lines.extend(f"- {reason.message}" for reason in assessment.reasons[:safe_reason_limit])
        hidden = len(assessment.reasons) - safe_reason_limit
        if hidden > 0:
            lines.append(f"- +{hidden} evidencias")
    else:
        lines.append("- Sin desvios relevantes frente al baseline.")
    return "\n".join(lines)
