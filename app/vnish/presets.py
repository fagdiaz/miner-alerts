from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


STATUS_STABLE = "STABLE"
STATUS_AUTOTUNING = "AUTOTUNING"
STATUS_DOWNCLOCKED = "DOWNCLOCKED"
STATUS_UNKNOWN = "UNKNOWN"

STATUS_LABELS: Dict[str, str] = {
    STATUS_STABLE: "🟢 ESTABLE",
    STATUS_AUTOTUNING: "🔄 EN AUTOTUNING",
    STATUS_DOWNCLOCKED: "⚠️ DOWNCLOCKED",
    STATUS_UNKNOWN: "⚪ SIN DATOS",
}


@dataclass(frozen=True)
class PresetAssessment:
    miner_name: str
    status: str
    status_label: str
    frequency_mhz: Optional[float]
    voltage_v: Optional[float]
    power_w: Optional[float]
    rate_ths: Optional[float]
    inferred_profile: str
    recent_events: tuple[str, ...]
    recommendation: str


def infer_operating_profile(
    frequency_mhz: Optional[float],
    power_w: Optional[float],
) -> str:
    """Infer the descriptive power/frequency profile bucket."""
    if frequency_mhz is None and power_w is None:
        return "Desconocido"
    freq_part = f"{frequency_mhz:.0f} MHz" if frequency_mhz is not None else "N/A"
    if power_w is not None and power_w > 0:
        rounded_p = round(power_w / 100.0) * 100
        return f"~{rounded_p:.0f}W ({freq_part})"
    return freq_part


def assess_miner_preset(
    miner_name: str,
    frequency_mhz: Optional[float],
    voltage_mv: Optional[float],
    power_w: Optional[float],
    rate_ths: Optional[float],
    chains_transitioning_count: int = 0,
    baseline_frequency_mhz: Optional[float] = None,
    recent_events: tuple[str, ...] = (),
    frequency_drop_threshold_mhz: float = 25.0,
) -> PresetAssessment:
    """Assess operational frequency, voltage, and dynamic tuning state."""
    if frequency_mhz is None and voltage_mv is None and power_w is None:
        return PresetAssessment(
            miner_name=miner_name,
            status=STATUS_UNKNOWN,
            status_label=STATUS_LABELS[STATUS_UNKNOWN],
            frequency_mhz=None,
            voltage_v=None,
            power_w=None,
            rate_ths=None,
            inferred_profile="Desconocido",
            recent_events=tuple(recent_events),
            recommendation="Sin telemetría de frecuencia o tensión disponible.",
        )

    voltage_v = round(voltage_mv / 1000.0, 2) if voltage_mv is not None else None
    inferred = infer_operating_profile(frequency_mhz, power_w)

    # 1. Autotuning in progress
    has_autotune_event = any("autotune" in e.lower() for e in recent_events)
    if chains_transitioning_count > 0 or has_autotune_event:
        return PresetAssessment(
            miner_name=miner_name,
            status=STATUS_AUTOTUNING,
            status_label=STATUS_LABELS[STATUS_AUTOTUNING],
            frequency_mhz=frequency_mhz,
            voltage_v=voltage_v,
            power_w=power_w,
            rate_ths=rate_ths,
            inferred_profile=inferred,
            recent_events=tuple(recent_events),
            recommendation="Cadenas en proceso de calibración o autotuning dinámico.",
        )

    # 2. Downclocked from baseline
    if (
        baseline_frequency_mhz is not None
        and frequency_mhz is not None
        and (baseline_frequency_mhz - frequency_mhz) >= frequency_drop_threshold_mhz
    ):
        diff = baseline_frequency_mhz - frequency_mhz
        return PresetAssessment(
            miner_name=miner_name,
            status=STATUS_DOWNCLOCKED,
            status_label=STATUS_LABELS[STATUS_DOWNCLOCKED],
            frequency_mhz=frequency_mhz,
            voltage_v=voltage_v,
            power_w=power_w,
            rate_ths=rate_ths,
            inferred_profile=inferred,
            recent_events=tuple(recent_events),
            recommendation=(
                f"El firmware redujo la frecuencia en {diff:.1f} MHz respecto al perfil nominal. "
                "Verificar estabilidad térmica y de alimentación."
            ),
        )

    # 3. Stable
    return PresetAssessment(
        miner_name=miner_name,
        status=STATUS_STABLE,
        status_label=STATUS_LABELS[STATUS_STABLE],
        frequency_mhz=frequency_mhz,
        voltage_v=voltage_v,
        power_w=power_w,
        rate_ths=rate_ths,
        inferred_profile=inferred,
        recent_events=tuple(recent_events),
        recommendation="Frecuencia y tensión en sincronía con el perfil nominal.",
    )


def build_presets_table_text(assessments: List[PresetAssessment]) -> str:
    """Format fleet operating profile overview in mobile-first vertical cards."""
    lines = [
        "⚙️ Perfiles y Autotuning",
        "────────────────────────────",
    ]
    attention_miners = []

    for idx, ass in enumerate(assessments):
        if idx > 0:
            lines.append("")

        freq_str = f"{ass.frequency_mhz:.1f} MHz" if ass.frequency_mhz is not None else "N/A"
        v_str = f"{ass.voltage_v:.1f}V" if ass.voltage_v is not None else "N/A"
        p_str = f"{ass.power_w:,.0f} W" if ass.power_w is not None else "N/A"
        r_str = f"{ass.rate_ths:.1f} TH/s" if ass.rate_ths is not None else "N/A"

        lines.append(f"{ass.miner_name}: {ass.status_label}")
        lines.append(f"• Frec: {freq_str} ({v_str})")
        lines.append(f"• {r_str}  |  {p_str}")

        if ass.inferred_profile and ass.inferred_profile != "Desconocido":
            prof = ass.inferred_profile[:22]
            lines.append(f"• Perfil: {prof}")

        if ass.status in (STATUS_AUTOTUNING, STATUS_DOWNCLOCKED):
            attention_miners.append(ass.miner_name)

    lines.append("────────────────────────────")
    if attention_miners:
        lines.append("⚠️ Atención:")
        for m in attention_miners:
            lines.append(f"  • {m}")
        lines.append("En autotuning o frecuencia baja.")
    else:
        lines.append("✅ Frecuencias y perfiles estables.")
    lines.append("• Uso: /presets <minero>")
    return "\n".join(lines)




def build_miner_preset_detail_text(assessment: PresetAssessment) -> str:
    """Format deep profile diagnostic card for a single miner."""
    freq_str = f"{assessment.frequency_mhz:.1f} MHz" if assessment.frequency_mhz is not None else "N/A"
    v_str = f"{assessment.voltage_v:.2f} V" if assessment.voltage_v is not None else "N/A"
    p_str = f"{assessment.power_w:,.0f} W" if assessment.power_w is not None else "N/A"
    r_str = f"{assessment.rate_ths:.1f} TH/s" if assessment.rate_ths is not None else "N/A"
    events_str = f"[{', '.join(assessment.recent_events)}]" if assessment.recent_events else "[]"

    lines = [
        f"⚙️ Diagnóstico de Perfil y Tuning — {assessment.miner_name}",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"• Estado: {assessment.status_label}",
        f"• Perfil Inferido: {assessment.inferred_profile}",
        f"• Frecuencia Promedio: {freq_str}",
        f"• Tensión de Cadena: {v_str}",
        f"• Potencia de Cadena: {p_str}",
        f"• Hashrate Actual: {r_str}",
        f"• Eventos Recientes: {events_str}",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"💡 Recomendación: {assessment.recommendation}",
    ]
    return "\n".join(lines)


def fetch_latest_preset_assessments(
    db_path: Path | str,
    miners: list,
    states: Optional[dict] = None,
    config: Optional[dict] = None,
) -> List[PresetAssessment]:
    """Extract latest frequency and tuning data for all configured miners."""
    db_file = Path(db_path).expanduser()
    if not db_file.is_absolute() and not db_file.exists():
        repo_root = Path(__file__).resolve().parent.parent.parent
        if (repo_root / db_file).exists():
            db_file = repo_root / db_file
    assessments: List[PresetAssessment] = []
    cfg = config or {}
    freq_drop_thresh = float(cfg.get("preset_frequency_drop_mhz", 25.0))

    db_samples: Dict[str, dict] = {}
    firmware_events_by_miner: Dict[str, list] = {}

    if db_file.exists():
        uri = f"file:{db_file.resolve().as_posix()}?mode=ro"
        conn = None
        try:
            conn = sqlite3.connect(uri, uri=True, timeout=2.0)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Check if firmware_events exists
            has_fw = cursor.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='firmware_events'"
            ).fetchone() is not None

            for miner in miners:
                m_name = miner.get("name")
                m_host = miner.get("host") or miner.get("ip")
                m_port = miner.get("port", 4028)
                m_ident = str(m_name or m_host or "unknown")

                candidate_keys = []
                if m_name and m_host:
                    candidate_keys.append(f"{m_name}|{m_host}:{m_port}")
                if m_host:
                    candidate_keys.append(str(m_host))
                if m_name:
                    candidate_keys.append(str(m_name))

                placeholders = ",".join("?" for _ in candidate_keys)
                try:
                    cursor.execute(
                        f"""
                        SELECT rate_ths, frequency_mhz_avg, chain_voltage_mv_avg, chain_power_w_total, chains_transitioning_count
                        FROM telemetry_samples
                        WHERE miner_key IN ({placeholders}) OR miner_name = ? OR host = ?
                        ORDER BY observed_ts DESC
                        LIMIT 1
                        """,
                        (*candidate_keys, str(m_name or ""), str(m_host or "")),
                    )
                    row = cursor.fetchone()
                    if row:
                        db_samples[m_ident] = {
                            "rate_ths": row["rate_ths"],
                            "frequency_mhz": row["frequency_mhz_avg"],
                            "voltage_mv": row["chain_voltage_mv_avg"],
                            "power_w": row["chain_power_w_total"],
                            "chains_transitioning_count": row["chains_transitioning_count"] or 0,
                        }
                except Exception:
                    pass

                if has_fw:
                    try:
                        cursor.execute(
                            f"""
                            SELECT summary FROM firmware_events
                            WHERE miner_key IN ({placeholders}) OR miner_name = ? OR host = ?
                            ORDER BY id DESC
                            LIMIT 3
                            """,
                            (*candidate_keys, str(m_name or ""), str(m_host or "")),
                        )
                        fw_rows = cursor.fetchall()
                        firmware_events_by_miner[m_ident] = [r["summary"] for r in fw_rows]
                    except Exception:
                        pass
        except Exception:
            pass
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    for miner in miners:
        m_name = miner.get("name") or miner.get("host") or miner.get("ip") or "unknown"
        m_ident = str(miner.get("name") or miner.get("host") or miner.get("ip"))
        sample = db_samples.get(m_ident)
        events = tuple(firmware_events_by_miner.get(m_ident, []))

        base_freq = None
        if states:
            m_host = miner.get("host") or miner.get("ip")
            m_port = miner.get("port", 4028)
            full_key = f"{m_name}|{m_host}:{m_port}"
            for k in (full_key, str(m_host), str(m_name), m_ident):
                if k in states:
                    base_freq = getattr(states[k], "baseline_frequency_mhz", None)
                    break

        if sample:
            ass = assess_miner_preset(
                miner_name=m_name,
                frequency_mhz=sample["frequency_mhz"],
                voltage_mv=sample["voltage_mv"],
                power_w=sample["power_w"],
                rate_ths=sample["rate_ths"],
                chains_transitioning_count=sample["chains_transitioning_count"],
                baseline_frequency_mhz=base_freq,
                recent_events=events,
                frequency_drop_threshold_mhz=freq_drop_thresh,
            )
        else:
            ass = assess_miner_preset(
                miner_name=m_name,
                frequency_mhz=None,
                voltage_mv=None,
                power_w=None,
                rate_ths=None,
                chains_transitioning_count=0,
                baseline_frequency_mhz=base_freq,
                recent_events=events,
                frequency_drop_threshold_mhz=freq_drop_thresh,
            )
        assessments.append(ass)

    return assessments


def evaluate_preset_alerts(
    state: Any,
    assessment: PresetAssessment,
    now_ts: float,
    config: dict,
) -> Optional[str]:
    """Evaluate operating profile adjustments and downclock alerts."""
    preset_alert_enabled = bool(config.get("preset_alert_enabled", True))
    if not preset_alert_enabled:
        return None

    cooldown_seconds = float(config.get("preset_cooldown_seconds", 3600))

    # Initialize baseline frequency when stable
    if (
        getattr(state, "baseline_frequency_mhz", None) is None
        and assessment.status == STATUS_STABLE
        and assessment.frequency_mhz is not None
        and assessment.frequency_mhz > 100.0
    ):
        state.baseline_frequency_mhz = assessment.frequency_mhz

    if assessment.status == STATUS_DOWNCLOCKED:
        last_ts = getattr(state, "last_preset_warning_ts", None)
        if last_ts is None or (now_ts - last_ts) >= cooldown_seconds:
            state.last_preset_warning_ts = now_ts
            base_freq = getattr(state, "baseline_frequency_mhz", None)
            base_str = f"{base_freq:.1f} MHz" if base_freq is not None else "Nominal"
            cur_str = f"{assessment.frequency_mhz:.1f} MHz" if assessment.frequency_mhz is not None else "N/A"
            return (
                f"ℹ️ [PERFIL/AUTOTUNE] {assessment.miner_name} — Ajuste automático de perfil detectado:\n"
                f"Frecuencia reducida: {base_str} -> {cur_str}.\n"
                f"El firmware ajustó el preset por estabilidad o temperatura."
            )

    return None
