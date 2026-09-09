from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


STATUS_HEALTHY = "HEALTHY"
STATUS_ELEVATED = "ELEVATED"
STATUS_SATURATED = "SATURATED"
STATUS_CRITICAL_HEAT = "CRITICAL_HEAT"
STATUS_FAN_DEFECT = "FAN_DEFECT"
STATUS_UNKNOWN = "UNKNOWN"

STATUS_LABELS: Dict[str, str] = {
    STATUS_HEALTHY: "🟢 OK",
    STATUS_ELEVATED: "🟡 ELEVADO",
    STATUS_SATURATED: "🟠 SATURADO",
    STATUS_CRITICAL_HEAT: "🔴 CRÍTICO",
    STATUS_FAN_DEFECT: "⚠️ DEFECTO FAN",
    STATUS_UNKNOWN: "⚪ SIN DATOS",
}


@dataclass(frozen=True)
class CoolingAssessment:
    miner_name: str
    status: str
    status_label: str
    max_temp_c: Optional[float]
    thermal_headroom_c: Optional[float]
    fan_rpm_max: Optional[int]
    fan_pwm_percent: Optional[float]
    diagnostic_flags: tuple[str, ...]
    recommendation: str
    fan_mode: Optional[str] = None


def calculate_thermal_headroom(
    max_temp_c: Optional[float],
    thermal_limit_c: float = 85.0,
) -> Optional[float]:
    """Calculate degrees Celsius remaining until emergency thermal trip."""
    if max_temp_c is None:
        return None
    return round(max(0.0, float(thermal_limit_c) - float(max_temp_c)), 2)


def assess_miner_cooling(
    miner_name: str,
    max_temp_c: Optional[float],
    fan_rpm_max: Optional[int],
    fan_pwm_percent: Optional[float],
    diagnostic_flags: tuple[str, ...] = (),
    rate_ths: Optional[float] = None,
    thermal_limit_c: float = 85.0,
    critical_temp_c: float = 84.5,
    saturate_temp_c: float = 78.0,
    saturate_pwm_pct: float = 95.0,
    saturate_rpm: int = 5800,
    fan_mode: Optional[str] = None,
) -> CoolingAssessment:
    """Assess cooling dissipation and mechanical fan health from telemetry."""
    headroom = calculate_thermal_headroom(max_temp_c, thermal_limit_c=thermal_limit_c)

    # 1. Unknown / No telemetry
    if max_temp_c is None and fan_rpm_max is None and fan_pwm_percent is None:
        return CoolingAssessment(
            miner_name=miner_name,
            status=STATUS_UNKNOWN,
            status_label=STATUS_LABELS[STATUS_UNKNOWN],
            max_temp_c=None,
            thermal_headroom_c=None,
            fan_rpm_max=None,
            fan_pwm_percent=None,
            diagnostic_flags=tuple(diagnostic_flags),
            recommendation="Sin datos de telemetría disponibles.",
            fan_mode=fan_mode,
        )

    # 2. Fan defect: missing tachometer or < 2000 RPM while hashing
    has_missing_signal = "fan_signal_missing" in diagnostic_flags
    is_stalled = (
        rate_ths is not None
        and rate_ths > 0.0
        and fan_rpm_max is not None
        and fan_rpm_max < 2000
    )
    if has_missing_signal or is_stalled:
        rec = (
            "Falla mecánica de ventilador o señal ausente. Inspeccionar cooler o cableado inmediatamente."
        )
        return CoolingAssessment(
            miner_name=miner_name,
            status=STATUS_FAN_DEFECT,
            status_label=STATUS_LABELS[STATUS_FAN_DEFECT],
            max_temp_c=max_temp_c,
            thermal_headroom_c=headroom,
            fan_rpm_max=fan_rpm_max,
            fan_pwm_percent=fan_pwm_percent,
            diagnostic_flags=tuple(diagnostic_flags),
            recommendation=rec,
            fan_mode=fan_mode,
        )

    # 3. Critical Heat (>= critical_temp_c)
    if max_temp_c is not None and max_temp_c >= critical_temp_c:
        rec = (
            f"Temperatura crítica ({max_temp_c:.1f}°C) cerca del corte por hardware ({thermal_limit_c:.1f}°C). "
            "Reducir perfil de energía o apagar para mantenimiento urgente."
        )
        return CoolingAssessment(
            miner_name=miner_name,
            status=STATUS_CRITICAL_HEAT,
            status_label=STATUS_LABELS[STATUS_CRITICAL_HEAT],
            max_temp_c=max_temp_c,
            thermal_headroom_c=headroom,
            fan_rpm_max=fan_rpm_max,
            fan_pwm_percent=fan_pwm_percent,
            diagnostic_flags=tuple(diagnostic_flags),
            recommendation=rec,
            fan_mode=fan_mode,
        )

    # 4. Saturated dissipation (>= 78°C and [PWM >= 95% or RPM >= 5800])
    is_pwm_saturated = fan_pwm_percent is not None and fan_pwm_percent >= saturate_pwm_pct
    is_rpm_saturated = fan_rpm_max is not None and fan_rpm_max >= saturate_rpm
    if max_temp_c is not None and max_temp_c >= saturate_temp_c and (is_pwm_saturated or is_rpm_saturated):
        rec = (
            "Disipación saturada con ventiladores al máximo. Inspeccionar y limpiar filtros antipolvo "
            "o verificar temperatura ambiente."
        )
        return CoolingAssessment(
            miner_name=miner_name,
            status=STATUS_SATURATED,
            status_label=STATUS_LABELS[STATUS_SATURATED],
            max_temp_c=max_temp_c,
            thermal_headroom_c=headroom,
            fan_rpm_max=fan_rpm_max,
            fan_pwm_percent=fan_pwm_percent,
            diagnostic_flags=tuple(diagnostic_flags),
            recommendation=rec,
            fan_mode=fan_mode,
        )

    # 5. Elevated regime (75°C <= temp < 78°C or PWM >= 90%)
    is_temp_elevated = max_temp_c is not None and 75.0 <= max_temp_c < saturate_temp_c
    is_pwm_elevated = fan_pwm_percent is not None and fan_pwm_percent >= 90.0
    if is_temp_elevated or is_pwm_elevated:
        rec = "Régimen térmico elevado. Monitorear flujo de aire."
        return CoolingAssessment(
            miner_name=miner_name,
            status=STATUS_ELEVATED,
            status_label=STATUS_LABELS[STATUS_ELEVATED],
            max_temp_c=max_temp_c,
            thermal_headroom_c=headroom,
            fan_rpm_max=fan_rpm_max,
            fan_pwm_percent=fan_pwm_percent,
            diagnostic_flags=tuple(diagnostic_flags),
            recommendation=rec,
            fan_mode=fan_mode,
        )

    # 6. Healthy
    rec = "Flujo de aire y disipación en rango óptimo."
    return CoolingAssessment(
        miner_name=miner_name,
        status=STATUS_HEALTHY,
        status_label=STATUS_LABELS[STATUS_HEALTHY],
        max_temp_c=max_temp_c,
        thermal_headroom_c=headroom,
        fan_rpm_max=fan_rpm_max,
        fan_pwm_percent=fan_pwm_percent,
        diagnostic_flags=tuple(diagnostic_flags),
        recommendation=rec,
        fan_mode=fan_mode,
    )


def build_fans_table_text(assessments: List[CoolingAssessment]) -> str:
    """Format fleet cooling and fan health overview table."""
    lines = [
        "❄️ Miner Alerts — Estado de Enfriamiento",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    warnings = []
    for ass in assessments:
        rpm_str = f"{ass.fan_rpm_max:,} RPM" if ass.fan_rpm_max is not None else "RPM N/A"
        pwm_str = f"{ass.fan_pwm_percent:.0f}%" if ass.fan_pwm_percent is not None else "N/A"
        temp_str = f"{ass.max_temp_c:.1f}°C" if ass.max_temp_c is not None else "N/A"
        headroom_str = f"{ass.thermal_headroom_c:.1f}°C" if ass.thermal_headroom_c is not None else "N/A"
        mode_str = f" [{ass.fan_mode.upper()}]" if ass.fan_mode else ""

        row = (
            f"{ass.miner_name}: {ass.status_label} | "
            f"{rpm_str} ({pwm_str}{mode_str}) | "
            f"{temp_str} (Margen: {headroom_str})"
        )
        lines.append(row)
        if ass.status in (STATUS_SATURATED, STATUS_CRITICAL_HEAT, STATUS_FAN_DEFECT):
            warnings.append(ass.miner_name)

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    if warnings:
        joined = ", ".join(warnings)
        lines.append(f"⚠️ Atención: {joined} requiere(n) inspección de filtros o fans.")
    else:
        lines.append("✅ Flota operando con márgenes térmicos seguros.")

    lines.append("Para detalle individual: /fans <minero>")
    return "\n".join(lines)


def build_miner_fan_detail_text(assessment: CoolingAssessment) -> str:
    """Format deep cooling diagnostic card for a single miner."""
    rpm_str = f"{assessment.fan_rpm_max:,} RPM" if assessment.fan_rpm_max is not None else "N/A"
    pwm_str = f"{assessment.fan_pwm_percent:.1f}%" if assessment.fan_pwm_percent is not None else "N/A"
    temp_str = f"{assessment.max_temp_c:.1f}°C" if assessment.max_temp_c is not None else "N/A"
    headroom_str = f"{assessment.thermal_headroom_c:.1f}°C" if assessment.thermal_headroom_c is not None else "N/A"
    flags_str = f"[{', '.join(assessment.diagnostic_flags)}]" if assessment.diagnostic_flags else "[]"
    mode_str = f" ({assessment.fan_mode.upper()})" if assessment.fan_mode else ""

    lines = [
        f"❄️ Diagnóstico de Enfriamiento — {assessment.miner_name}",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"• Estado: {assessment.status_label}",
        f"• Temp. Máxima: {temp_str} (Límite: 85.0°C)",
        f"• Margen Térmico: {headroom_str}",
        f"• Velocidad Fans: {rpm_str}",
        f"• Potencia PWM: {pwm_str}{mode_str}",
    ]
    if assessment.fan_mode:
        lines.append(f"• Modo Control: {assessment.fan_mode.upper()}")
    lines.extend([
        f"• Flags: {flags_str}",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"💡 Recomendación: {assessment.recommendation}",
    ])
    return "\n".join(lines)


def fetch_latest_cooling_assessments(
    db_path: Path | str,
    miners: list,
    states: Optional[dict] = None,
    config: Optional[dict] = None,
) -> List[CoolingAssessment]:
    """Retrieve the latest telemetry for each miner and assess cooling health."""
    db_file = Path(db_path)
    assessments: List[CoolingAssessment] = []
    cfg = config or {}
    critical_temp = float(cfg.get("cooling_critical_temp_c", 84.5))
    saturate_temp = float(cfg.get("cooling_saturate_temp_c", 78.0))
    saturate_pwm = float(cfg.get("cooling_saturate_pwm_pct", 95.0))
    saturate_rpm = int(cfg.get("cooling_saturate_rpm", 5800))

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
                    SELECT max_temp_c, fan_rpm_max, fan_pwm_percent, diagnostic_flags_json, rate_ths
                    FROM telemetry_samples
                    WHERE miner_key = ?
                    ORDER BY observed_ts DESC
                    LIMIT 1
                    """,
                    (str(m_key),),
                )
                row = cursor.fetchone()
                if row:
                    flags_raw = row["diagnostic_flags_json"]
                    flags = tuple(json.loads(flags_raw)) if flags_raw else ()
                    db_samples[str(m_key)] = {
                        "max_temp_c": row["max_temp_c"],
                        "fan_rpm_max": row["fan_rpm_max"],
                        "fan_pwm_percent": row["fan_pwm_percent"],
                        "diagnostic_flags": flags,
                        "rate_ths": row["rate_ths"],
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
        st = None
        if states:
            for s_k, s_v in states.items():
                if miner.get("name") and miner.get("name") in s_k:
                    st = s_v
                    break
                elif miner.get("host") and miner.get("host") in s_k:
                    st = s_v
                    break
        fan_mode = getattr(st, "last_fan_mode", None) if st else None
        sample = db_samples.get(m_key)
        if sample:
            ass = assess_miner_cooling(
                miner_name=m_name,
                max_temp_c=sample["max_temp_c"],
                fan_rpm_max=sample["fan_rpm_max"],
                fan_pwm_percent=sample["fan_pwm_percent"],
                diagnostic_flags=sample["diagnostic_flags"],
                rate_ths=sample["rate_ths"],
                critical_temp_c=critical_temp,
                saturate_temp_c=saturate_temp,
                saturate_pwm_pct=saturate_pwm,
                saturate_rpm=saturate_rpm,
                fan_mode=fan_mode,
            )
        else:
            ass = assess_miner_cooling(
                miner_name=m_name,
                max_temp_c=None,
                fan_rpm_max=None,
                fan_pwm_percent=None,
                diagnostic_flags=(),
                rate_ths=None,
                fan_mode=fan_mode,
            )
        assessments.append(ass)

    return assessments


def evaluate_cooling_alerts(
    state: Any,
    assessment: CoolingAssessment,
    now_ts: float,
    config: dict,
) -> Optional[str]:
    """Evaluate cooling assessment against thresholds and streak/cooldown rules."""
    cooling_alert_enabled = bool(config.get("cooling_alert_enabled", True))
    if not cooling_alert_enabled:
        return None

    saturate_streak_target = int(config.get("cooling_saturate_streak", 3))
    cooldown_seconds = float(config.get("cooling_cooldown_seconds", 3600))

    # Mechanical Fan Defect: immediate warning
    if assessment.status == STATUS_FAN_DEFECT:
        last_ts = getattr(state, "last_cooling_warning_ts", None)
        if last_ts is None or (now_ts - last_ts) >= cooldown_seconds:
            state.last_cooling_warning_ts = now_ts
            rpm_str = f"{assessment.fan_rpm_max:,} RPM" if assessment.fan_rpm_max is not None else "Tacómetro sin señal"
            return (
                f"🚨 [VENTILADOR] {assessment.miner_name} — Falla mecánica de ventilador detectada ({rpm_str}).\n"
                f"Riesgo de sobrecalentamiento inminente. Revisar cooler o tacómetro."
            )
        return None

    # Thermal Saturation or Critical Heat: streak-based warning
    if assessment.status in (STATUS_SATURATED, STATUS_CRITICAL_HEAT):
        current_streak = getattr(state, "cooling_streak", 0) + 1
        state.cooling_streak = current_streak

        if current_streak >= saturate_streak_target:
            last_ts = getattr(state, "last_cooling_warning_ts", None)
            if last_ts is None or (now_ts - last_ts) >= cooldown_seconds:
                state.last_cooling_warning_ts = now_ts
                rpm_str = f"{assessment.fan_rpm_max:,} RPM" if assessment.fan_rpm_max is not None else "RPM N/A"
                pwm_str = f"{assessment.fan_pwm_percent:.0f}% PWM" if assessment.fan_pwm_percent is not None else ""
                temp_str = f"{assessment.max_temp_c:.1f}°C" if assessment.max_temp_c is not None else "N/A"
                headroom_str = (
                    f"{assessment.thermal_headroom_c:.1f}°C"
                    if assessment.thermal_headroom_c is not None
                    else "N/A"
                )
                specs = ", ".join(s for s in [rpm_str, pwm_str, temp_str] if s)
                return (
                    f"⚠️ [ENFRIAMIENTO] {assessment.miner_name} — Saturación térmica detectada ({specs}).\n"
                    f"Margen crítico hacia corte: {headroom_str}.\n"
                    f"Se recomienda inspección de flujo y limpieza preventiva de filtros antipolvo."
                )
        return None

    # Normalization: reset streak
    state.cooling_streak = 0
    return None
