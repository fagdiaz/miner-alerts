from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


STATUS_OPTIMAL = "OPTIMAL"
STATUS_NORMAL = "NORMAL"
STATUS_ELEVATED = "ELEVATED"
STATUS_DEGRADED = "DEGRADED"
STATUS_UNKNOWN = "UNKNOWN"

STATUS_LABELS: Dict[str, str] = {
    STATUS_OPTIMAL: "🟢 ÓPTIMA",
    STATUS_NORMAL: "🟢 NORMAL",
    STATUS_ELEVATED: "🟡 ELEVADA",
    STATUS_DEGRADED: "🟠 DEGRADADA",
    STATUS_UNKNOWN: "⚪ SIN DATOS",
}


@dataclass(frozen=True)
class EfficiencyAssessment:
    miner_name: str
    status: str
    status_label: str
    rate_ths: Optional[float]
    power_w: Optional[float]
    efficiency_j_th: Optional[float]
    recommendation: str


def calculate_efficiency_j_th(
    power_w: Optional[float],
    rate_ths: Optional[float],
) -> Optional[float]:
    """Calculate Joules per Terahash (Watts / TH/s)."""
    if power_w is None or rate_ths is None:
        return None
    try:
        p = float(power_w)
        r = float(rate_ths)
    except (TypeError, ValueError):
        return None
    if p <= 0.0 or r <= 0.0:
        return None
    return round(p / r, 2)


def assess_miner_efficiency(
    miner_name: str,
    power_w: Optional[float],
    rate_ths: Optional[float],
    target_j_th: float = 30.0,
    degraded_threshold_j_th: float = 35.0,
) -> EfficiencyAssessment:
    """Assess energy efficiency in J/TH against performance baselines."""
    eff = calculate_efficiency_j_th(power_w, rate_ths)
    if eff is None:
        return EfficiencyAssessment(
            miner_name=miner_name,
            status=STATUS_UNKNOWN,
            status_label=STATUS_LABELS[STATUS_UNKNOWN],
            rate_ths=rate_ths,
            power_w=power_w,
            efficiency_j_th=None,
            recommendation="Sin datos suficientes de potencia o hashrate.",
        )

    if eff <= 28.5:
        status = STATUS_OPTIMAL
        rec = "Eficiencia excelente en rango óptimo de consumo."
    elif eff <= 31.5:
        status = STATUS_NORMAL
        rec = "Eficiencia nominal normal de operación."
    elif eff <= degraded_threshold_j_th:
        status = STATUS_ELEVATED
        rec = "Eficiencia ligeramente elevada. Monitorear evolución de temperaturas o autotune."
    else:
        status = STATUS_DEGRADED
        rec = (
            f"Eficiencia severamente degradada ({eff:.1f} J/TH > {degraded_threshold_j_th:.1f}). "
            "El equipo consume potencia normal pero genera hashrate subóptimo. "
            "Inspeccionar chips con errores o caídas de tensión por cadena."
        )

    return EfficiencyAssessment(
        miner_name=miner_name,
        status=status,
        status_label=STATUS_LABELS[status],
        rate_ths=rate_ths,
        power_w=power_w,
        efficiency_j_th=eff,
        recommendation=rec,
    )


def build_efficiency_table_text(assessments: List[EfficiencyAssessment]) -> str:
    """Format fleet energy efficiency summary table."""
    lines = [
        "⚡ Miner Alerts — Eficiencia Energética (J/TH)",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]
    total_power_w = 0.0
    total_rate_ths = 0.0
    degraded_miners = []

    for ass in assessments:
        eff_str = f"{ass.efficiency_j_th:.1f} J/TH" if ass.efficiency_j_th is not None else "N/A"
        p_str = f"{ass.power_w:,.0f} W" if ass.power_w is not None else "N/A"
        r_str = f"{ass.rate_ths:.1f} TH/s" if ass.rate_ths is not None else "N/A"
        lines.append(f"{ass.miner_name}: {ass.status_label} | {eff_str} | {p_str} | {r_str}")
        if ass.power_w is not None and ass.power_w > 0:
            total_power_w += ass.power_w
        if ass.rate_ths is not None and ass.rate_ths > 0:
            total_rate_ths += ass.rate_ths
        if ass.status == STATUS_DEGRADED:
            degraded_miners.append(ass.miner_name)

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    fleet_eff = (total_power_w / total_rate_ths) if total_rate_ths > 0 else 0.0
    kw_str = f"{total_power_w / 1000.0:.1f} kW"
    lines.append(f"⚡ Promedio Flota: {fleet_eff:.1f} J/TH | Total: {total_power_w:,.0f} W ({kw_str})")
    if degraded_miners:
        joined = ", ".join(degraded_miners)
        lines.append(f"⚠️ Atención: {joined} presenta(n) degradación energética.")
    else:
        lines.append("✅ Flota operando en rangos óptimos de eficiencia.")
    lines.append("Para detalle individual: /efficiency <minero>")
    return "\n".join(lines)


def build_miner_efficiency_detail_text(assessment: EfficiencyAssessment) -> str:
    """Format deep efficiency diagnostic card for a single miner."""
    eff_str = f"{assessment.efficiency_j_th:.1f} J/TH" if assessment.efficiency_j_th is not None else "N/A"
    p_str = f"{assessment.power_w:,.0f} W" if assessment.power_w is not None else "N/A"
    kw_str = f" ({assessment.power_w / 1000.0:.2f} kW)" if assessment.power_w is not None else ""
    r_str = f"{assessment.rate_ths:.1f} TH/s" if assessment.rate_ths is not None else "N/A"

    lines = [
        f"⚡ Diagnóstico de Eficiencia — {assessment.miner_name}",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"• Estado: {assessment.status_label}",
        f"• Eficiencia: {eff_str}",
        f"• Hashrate Actual: {r_str}",
        f"• Potencia de Cadenas: {p_str}{kw_str}",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"💡 Recomendación: {assessment.recommendation}",
    ]
    return "\n".join(lines)


def fetch_latest_efficiency_assessments(
    db_path: Path | str,
    miners: list,
    states: Optional[dict] = None,
    config: Optional[dict] = None,
) -> List[EfficiencyAssessment]:
    """Retrieve latest power and hashrate for each miner and assess efficiency."""
    db_file = Path(db_path)
    assessments: List[EfficiencyAssessment] = []
    cfg = config or {}
    target_j_th = float(cfg.get("efficiency_target_j_th", 30.0))
    degraded_thresh = float(cfg.get("efficiency_degraded_threshold_j_th", 35.0))

    db_samples: Dict[str, dict] = {}
    if db_file.exists():
        uri = f"file:{db_file.resolve().as_posix()}?mode=ro"
        conn = None
        try:
            conn = sqlite3.connect(uri, uri=True, timeout=2.0)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            for miner in miners:
                m_key = miner.get("ip") or miner.get("name")
                cursor.execute(
                    """
                    SELECT rate_ths, chain_power_w_total
                    FROM telemetry_samples
                    WHERE miner_key = ?
                    ORDER BY observed_ts DESC
                    LIMIT 1
                    """,
                    (str(m_key),),
                )
                row = cursor.fetchone()
                if row:
                    db_samples[str(m_key)] = {
                        "rate_ths": row["rate_ths"],
                        "power_w": row["chain_power_w_total"],
                    }
        except Exception:
            pass
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    for miner in miners:
        m_key = str(miner.get("ip") or miner.get("name"))
        m_name = miner.get("name") or m_key
        sample = db_samples.get(m_key)
        if sample:
            ass = assess_miner_efficiency(
                miner_name=m_name,
                power_w=sample["power_w"],
                rate_ths=sample["rate_ths"],
                target_j_th=target_j_th,
                degraded_threshold_j_th=degraded_thresh,
            )
        else:
            ass = assess_miner_efficiency(
                miner_name=m_name,
                power_w=None,
                rate_ths=None,
                target_j_th=target_j_th,
                degraded_threshold_j_th=degraded_thresh,
            )
        assessments.append(ass)

    return assessments


def evaluate_efficiency_alerts(
    state: Any,
    assessment: EfficiencyAssessment,
    now_ts: float,
    config: dict,
) -> Optional[str]:
    """Evaluate efficiency assessment against thresholds, streaks and cooldowns."""
    alert_enabled = bool(config.get("efficiency_alert_enabled", True))
    if not alert_enabled:
        return None

    streak_target = int(config.get("efficiency_degraded_streak", 3))
    cooldown_seconds = float(config.get("efficiency_cooldown_seconds", 3600))

    if assessment.status == STATUS_DEGRADED:
        current_streak = getattr(state, "efficiency_streak", 0) + 1
        state.efficiency_streak = current_streak

        if current_streak >= streak_target:
            last_ts = getattr(state, "last_efficiency_warning_ts", None)
            if last_ts is None or (now_ts - last_ts) >= cooldown_seconds:
                state.last_efficiency_warning_ts = now_ts
                p_str = f"{assessment.power_w:,.0f} W" if assessment.power_w is not None else "N/A"
                r_str = f"{assessment.rate_ths:.1f} TH/s" if assessment.rate_ths is not None else "N/A"
                eff_str = (
                    f"{assessment.efficiency_j_th:.1f} J/TH"
                    if assessment.efficiency_j_th is not None
                    else "N/A"
                )
                return (
                    f"⚠️ [EFICIENCIA] {assessment.miner_name} — Degradación energética detectada ({eff_str}).\n"
                    f"Potencia: {p_str} para {r_str}.\n"
                    f"Consumo excesivo por TH generado. Se recomienda inspección de cadenas."
                )
        return None

    # Normalization: reset streak
    state.efficiency_streak = 0
    return None
