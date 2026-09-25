"""Predictive Hashboard and Chain Health Assessment Engine (Spec 054).

Analyzes granular telemetry from /api/v1/chains to identify physical sensor
anomalies (I2C bus errors), performance deficits, and impending chain breaks
before catastrophic hardware failures or abrupt miner reboots occur.
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from app.telegram.help_center import visible_line_width, wrap_mobile_lines

MOBILE_CARD_SEPARATOR = "─" * 28
MOBILE_LINE_WIDTH_LIMIT = 32

STATUS_CHAIN_OK = "CHAIN_OK"
STATUS_CHAIN_SENSOR_ERROR = "CHAIN_SENSOR_ERROR"
STATUS_CHAIN_DEFICIT = "CHAIN_DEFICIT"
STATUS_CHAIN_FAULT = "CHAIN_FAULT"
STATUS_CHAIN_UNKNOWN = "CHAIN_UNKNOWN"

STATUS_LABELS: Dict[str, str] = {
    STATUS_CHAIN_OK: "🟢 OK",
    STATUS_CHAIN_SENSOR_ERROR: "⚠️ SENSOR I2C",
    STATUS_CHAIN_DEFICIT: "🟡 DÉFICIT",
    STATUS_CHAIN_FAULT: "🔴 FALLA PLACA",
    STATUS_CHAIN_UNKNOWN: "⚪ SIN DATOS",
}


@dataclass(frozen=True)
class ChainAssessment:
    """Diagnostic health assessment for a single hashboard chain."""
    miner_name: str
    chain_id: int
    status: str
    status_label: str
    state: str
    hr_realtime_mhs: float
    hr_nominal_mhs: float
    hr_deficit_pct: float
    freq_mhz_avg: float
    sensors_error_count: int
    faulty_sensor_locs: tuple[int, ...]
    chips_error_count: int
    chips_throttled_count: int
    max_chip_temp: Optional[float]
    max_board_temp: Optional[float]
    recommendation: str

    @property
    def is_healthy(self) -> bool:
        return self.status == STATUS_CHAIN_OK


@dataclass(frozen=True)
class MinerChainsAssessment:
    """Consolidated assessment for all hashboards on a miner."""
    miner_name: str
    observed_ts: float
    chains: tuple[ChainAssessment, ...]
    overall_status: str
    overall_status_label: str
    faulty_chains: tuple[int, ...]
    has_sensor_error: bool
    summary: str

    @property
    def is_all_healthy(self) -> bool:
        return self.overall_status == STATUS_CHAIN_OK

    @property
    def is_healthy(self) -> bool:
        return self.is_all_healthy


def assess_single_chain(miner_name: str, chain: Any) -> ChainAssessment:
    """Assess the physical and operational health of a single hashboard chain."""
    # Extract attributes whether chain is ChainTelemetry dataclass or SQLite Row/dict
    if hasattr(chain, "chain_id"):
        c_id = int(chain.chain_id)
        c_state = str(chain.state).lower()
        c_hr_real = float(chain.hr_realtime_mhs)
        c_hr_nom = float(chain.hr_nominal_mhs)
        c_deficit = float(chain.hr_deficit_pct)
        c_freq = float(chain.freq_mhz_avg)
        c_sensors_err = int(chain.sensors_error_count)
        c_chips_err = int(getattr(chain, "chips_error_count", 0))
        c_chips_throt = int(getattr(chain, "chips_throttled_count", 0))
        c_max_chip = getattr(chain, "max_chip_temp", None)
        c_max_board = getattr(chain, "max_board_temp", None)

        faulty_locs_list: List[int] = []
        is_chain_mining = c_state in ("mining", "ok")
        for s in getattr(chain, "sensors", []):
            s_state = getattr(s, "state", "") if hasattr(s, "state") else (s.get("state", "") if isinstance(s, dict) else "")
            s_state_str = str(s_state).lower()
            is_sensor_err = False
            if s_state_str in ("error", "err", "fault", "failed", "broken", "offline"):
                is_sensor_err = True
            elif is_chain_mining and s_state_str != "measure":
                is_sensor_err = True
            if is_sensor_err:
                loc_val = getattr(s, "loc", None) if hasattr(s, "loc") else (s.get("loc") if isinstance(s, dict) else None)
                if loc_val is not None:
                    faulty_locs_list.append(int(loc_val))
        faulty_locs = tuple(sorted(faulty_locs_list))

    elif isinstance(chain, dict) or hasattr(chain, "keys"):
        c_id = int(chain.get("chain_id", 0))
        c_state = str(chain.get("state", "unknown")).lower()
        c_hr_real = float(chain.get("hr_realtime", chain.get("hr_realtime_mhs", 0.0)))
        c_hr_nom = float(chain.get("hr_nominal", chain.get("hr_nominal_mhs", 0.0)))
        c_deficit = float(chain.get("hr_deficit_pct", 0.0))
        c_freq = float(chain.get("freq_avg", chain.get("freq_mhz_avg", 0.0)))
        c_sensors_err = int(chain.get("sensors_error_count", 0))
        c_chips_err = int(chain.get("chips_error_count", 0))
        c_chips_throt = int(chain.get("chips_throttled_count", 0))

        sensors_raw = chain.get("sensors_json", "[]")
        faulty_locs_list = []
        c_max_chip = None
        c_max_board = None
        is_chain_mining = c_state in ("mining", "ok")
        if isinstance(sensors_raw, str):
            try:
                sensors_list = json.loads(sensors_raw)
                if isinstance(sensors_list, list):
                    for s in sensors_list:
                        if isinstance(s, dict):
                            s_state_str = str(s.get("state", "")).lower()
                            is_sensor_err = False
                            if s_state_str in ("error", "err", "fault", "failed", "broken", "offline"):
                                is_sensor_err = True
                            elif is_chain_mining and s_state_str != "measure":
                                is_sensor_err = True
                            if is_sensor_err and s.get("loc") is not None:
                                faulty_locs_list.append(int(s["loc"]))
                    chip_temps = [float(s["chip"]) for s in sensors_list if isinstance(s, dict) and isinstance(s.get("chip"), (int, float))]
                    board_temps = [float(s["board"]) for s in sensors_list if isinstance(s, dict) and isinstance(s.get("board"), (int, float))]
                    c_max_chip = max(chip_temps) if chip_temps else None
                    c_max_board = max(board_temps) if board_temps else None
            except Exception:
                pass
        faulty_locs = tuple(sorted(faulty_locs_list))
        if c_max_chip is None and chain.get("max_chip_temp") is not None:
            c_max_chip = float(chain["max_chip_temp"])
        if c_max_board is None and chain.get("max_board_temp") is not None:
            c_max_board = float(chain["max_board_temp"])
    else:
        return ChainAssessment(
            miner_name=miner_name,
            chain_id=0,
            status=STATUS_CHAIN_UNKNOWN,
            status_label=STATUS_LABELS[STATUS_CHAIN_UNKNOWN],
            state="unknown",
            hr_realtime_mhs=0.0,
            hr_nominal_mhs=0.0,
            hr_deficit_pct=0.0,
            freq_mhz_avg=0.0,
            sensors_error_count=0,
            faulty_sensor_locs=(),
            chips_error_count=0,
            chips_throttled_count=0,
            max_chip_temp=None,
            max_board_temp=None,
            recommendation="Datos de cadena no disponibles.",
        )

    # Classification rules
    if c_state not in ("mining", "ok") and c_hr_real <= 0.0:
        status = STATUS_CHAIN_FAULT
        rec = f"Placa fuera de servicio ({c_state}). Posible corte de cadena o desconexión física."
    elif c_sensors_err > 0:
        status = STATUS_CHAIN_SENSOR_ERROR
        loc_str = f"loc {', '.join(map(str, faulty_locs))}" if faulty_locs else "I2C"
        rec = f"Falla en sensor térmico ({loc_str}). Riesgo inminente de aborto por chain_break."
    elif c_deficit >= 10.0:
        status = STATUS_CHAIN_DEFICIT
        rec = f"Déficit sostenido de hashrate ({c_deficit:.1f}%). Verificar chips estrangulados."
    else:
        status = STATUS_CHAIN_OK
        rec = "Placa saludable operando a rendimiento nominal."

    return ChainAssessment(
        miner_name=miner_name,
        chain_id=c_id,
        status=status,
        status_label=STATUS_LABELS[status],
        state=c_state,
        hr_realtime_mhs=c_hr_real,
        hr_nominal_mhs=c_hr_nom,
        hr_deficit_pct=round(c_deficit, 2),
        freq_mhz_avg=round(c_freq, 2),
        sensors_error_count=c_sensors_err,
        faulty_sensor_locs=faulty_locs,
        chips_error_count=c_chips_err,
        chips_throttled_count=c_chips_throt,
        max_chip_temp=c_max_chip,
        max_board_temp=c_max_board,
        recommendation=rec,
    )


def assess_miner_chains(
    miner_name: str,
    chains: Iterable[Any],
    observed_ts: Optional[float] = None,
) -> MinerChainsAssessment:
    """Assess all chains on a miner and determine overall health."""
    ts = observed_ts if observed_ts is not None else time.time()
    assessments: List[ChainAssessment] = [
        assess_single_chain(miner_name, c) for c in chains
    ]
    if not assessments:
        return MinerChainsAssessment(
            miner_name=miner_name,
            observed_ts=ts,
            chains=(),
            overall_status=STATUS_CHAIN_UNKNOWN,
            overall_status_label=STATUS_LABELS[STATUS_CHAIN_UNKNOWN],
            faulty_chains=(),
            has_sensor_error=False,
            summary="Sin datos de telemetría de cadena.",
        )

    faulty_chains = tuple(c.chain_id for c in assessments if not c.is_healthy)
    has_sensor_error = any(c.sensors_error_count > 0 for c in assessments)
    has_fault = any(c.status == STATUS_CHAIN_FAULT for c in assessments)
    has_deficit = any(c.status == STATUS_CHAIN_DEFICIT for c in assessments)

    if has_fault:
        overall = STATUS_CHAIN_FAULT
        summary = f"Falla física en placa(s): Cadena {', '.join(map(str, faulty_chains))}"
    elif has_sensor_error:
        overall = STATUS_CHAIN_SENSOR_ERROR
        sensor_chains = [c.chain_id for c in assessments if c.sensors_error_count > 0]
        summary = f"Falla sensor I2C en placa(s): Cadena {', '.join(map(str, sensor_chains))}"
    elif has_deficit:
        overall = STATUS_CHAIN_DEFICIT
        deficit_chains = [c.chain_id for c in assessments if c.status == STATUS_CHAIN_DEFICIT]
        summary = f"Déficit de hashrate en placa(s): Cadena {', '.join(map(str, deficit_chains))}"
    else:
        overall = STATUS_CHAIN_OK
        summary = "Todas las placas operando nominalmente al 100%."

    return MinerChainsAssessment(
        miner_name=miner_name,
        observed_ts=ts,
        chains=tuple(assessments),
        overall_status=overall,
        overall_status_label=STATUS_LABELS[overall],
        faulty_chains=faulty_chains,
        has_sensor_error=has_sensor_error,
        summary=summary,
    )


def find_culprit_chain_for_restart(chain_samples: Iterable[Any]) -> Optional[Dict[str, Any]]:
    """Identify which hashboard chain was degraded or faulty prior to a restart.

    Returns a dict with culprit info if an anomaly was present, or None if healthy.
    """
    for c in chain_samples:
        assessment = assess_single_chain("culprit_finder", c)
        if assessment.status == STATUS_CHAIN_SENSOR_ERROR:
            loc_str = ", ".join(map(str, assessment.faulty_sensor_locs)) if assessment.faulty_sensor_locs else "desconocida"
            return {
                "chain_id": assessment.chain_id,
                "reason": f"Falla sensor I2C (loc {loc_str})",
                "faulty_locs": list(assessment.faulty_sensor_locs),
                "sensors_error_count": assessment.sensors_error_count,
            }
        elif assessment.status == STATUS_CHAIN_FAULT:
            return {
                "chain_id": assessment.chain_id,
                "reason": f"Corte de cadena o placa detenida ({assessment.state})",
                "faulty_locs": [],
                "sensors_error_count": 0,
            }
        elif assessment.status == STATUS_CHAIN_DEFICIT and assessment.hr_deficit_pct >= 20.0:
            return {
                "chain_id": assessment.chain_id,
                "reason": f"Déficit crítico ({assessment.hr_deficit_pct:.1f}%)",
                "faulty_locs": [],
                "sensors_error_count": 0,
            }
    return None


def evaluate_chain_health_streak(
    streak_data: Dict[str, Any],
    assessment: MinerChainsAssessment,
    min_streak: int = 2,
    cooldown_s: float = 7200.0,
    now_ts: Optional[float] = None,
    alert_on_sensor_error: bool = True,
    is_snoozed: bool = False,
) -> Tuple[bool, Optional[str]]:
    """Evaluate consecutive fault streaks and cooldown to avoid alert spam.

    Returns:
        (should_alert: bool, alert_card_text: Optional[str])
    """
    if is_snoozed:
        return False, None

    now = now_ts if now_ts is not None else time.time()

    if assessment.overall_status in (STATUS_CHAIN_SENSOR_ERROR, STATUS_CHAIN_FAULT):
        current_streak = int(streak_data.get("fault_streak", 0)) + 1
        streak_data["fault_streak"] = current_streak
        last_alert_ts = float(streak_data.get("last_alert_ts", 0.0))

        if assessment.overall_status == STATUS_CHAIN_SENSOR_ERROR and not alert_on_sensor_error:
            return False, None

        if current_streak >= min_streak:
            if last_alert_ts == 0.0 or (now - last_alert_ts) >= cooldown_s:
                streak_data["last_alert_ts"] = now
                card = build_chain_alert_card(assessment.miner_name, assessment)
                return True, card
        return False, None

    # Reset streak if healthy or unknown
    streak_data["fault_streak"] = 0
    return False, None


def build_chain_alert_card(miner_name: str, assessment: MinerChainsAssessment) -> str:
    """Format a Mobile-First alert card (width <= 32 cols) for chain health."""
    lines = [
        "⚠️ *ALERTA SALUD DE CADENA*",
        MOBILE_CARD_SEPARATOR,
        f"• Minero: {miner_name}",
        f"• Estado: {assessment.overall_status_label}",
    ]
    if assessment.faulty_chains:
        lines.append(f"• Placas: Cadena {', '.join(map(str, assessment.faulty_chains))}")

    lines.append(MOBILE_CARD_SEPARATOR)

    for c in assessment.chains:
        if not c.is_healthy:
            lines.append(f"🔌 *Cadena {c.chain_id}* ({c.status_label})")
            if c.faulty_sensor_locs:
                lines.append(f"  Sensor: loc {', '.join(map(str, c.faulty_sensor_locs))} ERROR")
            hr_th = f"{c.hr_realtime_mhs / 1000.0:.2f} TH/s"
            lines.append(f"  Hash: {hr_th}")
            if c.chips_error_count > 0:
                lines.append(f"  HW Errs: {c.chips_error_count} chips")
            lines.append(MOBILE_CARD_SEPARATOR)

    lines.append("💡 *Diagnóstico Preventivo:*")
    if assessment.has_sensor_error:
        lines.append("Falla de bus/sensor en placa.")
        lines.append("Vnish puede abortar cadena")
        lines.append("(chain_break) abruptamente.")
    elif any(c.status == STATUS_CHAIN_FAULT for c in assessment.chains):
        lines.append("Cadena fuera de servicio.")
        lines.append("Posible corte de cadena,")
        lines.append("alimentación o falla de inicio.")
    elif any(c.status == STATUS_CHAIN_DEFICIT for c in assessment.chains):
        lines.append("Déficit sostenido de hashrate.")
        lines.append("Verificar chips estrangulados.")
    else:
        rec_wrapped = wrap_mobile_lines(assessment.summary, width=MOBILE_LINE_WIDTH_LIMIT)
        lines.extend(rec_wrapped)
    lines.append(MOBILE_CARD_SEPARATOR)

    return "\n".join(lines)


def build_chains_card_text(assessment: MinerChainsAssessment) -> str:
    """Format a Mobile-First card (width <= 32 cols) for /chains <miner>."""
    lines = [
        "🔌 *SALUD DE CADENAS*",
        MOBILE_CARD_SEPARATOR,
        f"• Minero: {assessment.miner_name}",
        f"• Estado: {assessment.overall_status_label}",
        MOBILE_CARD_SEPARATOR,
    ]

    if not assessment.chains:
        lines.append("⚠️ Sin datos de cadenas.")
        lines.append("Esperando recolección Vnish.")
        lines.append(MOBILE_CARD_SEPARATOR)
        return "\n".join(lines)

    for c in assessment.chains:
        badge = "🟢" if c.is_healthy else ("⚠️" if c.status == STATUS_CHAIN_SENSOR_ERROR else "🔴")
        lines.append(f"🔌 *Cadena {c.chain_id}* ({c.status_label} {badge})")
        hr_real_th = f"{c.hr_realtime_mhs / 1000.0:.1f} TH/s"
        hr_nom_th = f"{c.hr_nominal_mhs / 1000.0:.1f}"
        lines.append(f"• Hash: {hr_real_th} (nom {hr_nom_th})")

        temp_chip_str = f"{c.max_chip_temp:.0f}°C" if c.max_chip_temp is not None else "--"
        temp_board_str = f"{c.max_board_temp:.0f}°C" if c.max_board_temp is not None else "--"
        lines.append(f"• Temp: {temp_chip_str} chip | {temp_board_str} board")

        freq_str = f"{c.freq_mhz_avg:.0f} MHz" if c.freq_mhz_avg > 0 else "--"
        lines.append(f"• Frec: {freq_str} | Chips: 126")

        if c.sensors_error_count > 0:
            locs = f"loc {', '.join(map(str, c.faulty_sensor_locs))}" if c.faulty_sensor_locs else "I2C"
            lines.append(f"• Sensor: {locs} ERROR ⚠️")
        else:
            lines.append("• Sensores: 4/4 OK")

        if c.chips_error_count > 0 or c.chips_throttled_count > 0:
            lines.append(f"• Errs: {c.chips_error_count} | Throt: {c.chips_throttled_count}")

        lines.append("")

    if lines and lines[-1] == "":
        lines.pop()

    lines.append(MOBILE_CARD_SEPARATOR)
    lines.append("💡 *Diagnóstico:*")
    rec_wrapped = wrap_mobile_lines(assessment.summary, width=MOBILE_LINE_WIDTH_LIMIT)
    lines.extend(rec_wrapped)
    lines.append(MOBILE_CARD_SEPARATOR)

    return "\n".join(lines)


def build_chains_fleet_summary_text(assessments: List[MinerChainsAssessment]) -> str:
    """Format a Mobile-First overview (width <= 32 cols) for /chains (all miners)."""
    lines = [
        "🔌 *CADENAS: FLOTA ASIC*",
        MOBILE_CARD_SEPARATOR,
    ]

    if not assessments:
        lines.append("⚠️ Sin telemetría de cadenas.")
        lines.append("Esperando recolección Vnish.")
        lines.append(MOBILE_CARD_SEPARATOR)
        return "\n".join(lines)

    faulty_total = 0
    for a in assessments:
        m_short = a.miner_name
        if m_short.startswith("S19JPRO-"):
            m_short = f"S19-{m_short[8:]}"
        elif len(m_short) > 10:
            m_short = m_short[:10]

        chain_tags = []
        for c in a.chains:
            if c.is_healthy:
                chain_tags.append(f"C{c.chain_id}:OK")
            elif c.status == STATUS_CHAIN_SENSOR_ERROR:
                chain_tags.append(f"C{c.chain_id}:ERR")
            elif c.status == STATUS_CHAIN_DEFICIT:
                chain_tags.append(f"C{c.chain_id}:DEF")
            else:
                chain_tags.append(f"C{c.chain_id}:FLT")

        tags_str = " ".join(chain_tags) if chain_tags else "Sin datos"
        badge = "🟢" if a.overall_status == STATUS_CHAIN_OK else "⚠️"
        if not a.is_healthy:
            faulty_total += 1

        miner_line = f"• {m_short}: {tags_str} {badge}"
        if visible_line_width(miner_line) > MOBILE_LINE_WIDTH_LIMIT:
            lines.append(f"• {m_short} {badge}:")
            lines.append(f"  {tags_str}")
        else:
            lines.append(miner_line)

        for c in a.chains:
            if c.sensors_error_count > 0 and c.faulty_sensor_locs:
                loc_str = f"loc {', '.join(map(str, c.faulty_sensor_locs))}"
                lines.append(f"  └ C{c.chain_id}: Sensor {loc_str} ERROR")

    lines.append(MOBILE_CARD_SEPARATOR)
    if faulty_total > 0:
        lines.append(f"• Alerta: {faulty_total} equipo(s)")
    else:
        lines.append("• Estado: Flota 100% saludable")
    lines.append("Usa: /chains <id> para detalle.")
    lines.append(MOBILE_CARD_SEPARATOR)

    return "\n".join(lines)


# =============================================================================
# Spec 069: Deep Chain Telemetry & Predictive Chain Break Diagnostics (PROP-008)
# =============================================================================

RISK_TYPE_I2C_PERSISTENT_ERROR = "I2C_PERSISTENT_ERROR"
RISK_TYPE_CHIP_DEGRADATION = "CHIP_DEGRADATION"
RISK_TYPE_POWER_DISTURBANCE = "POWER_DISTURBANCE"
RISK_TYPE_ELECTRICAL_SAG = "ELECTRICAL_SAG"

SEVERITY_WARNING = "WARNING"
SEVERITY_CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class PredictiveChainRisk:
    """Predictive hardware risk assessment for a hashboard chain (Spec 069)."""
    miner_name: str
    chain_id: int
    risk_type: str  # "I2C_PERSISTENT_ERROR", "CHIP_DEGRADATION", "ELECTRICAL_SAG", "POWER_DISTURBANCE"
    severity: str   # "WARNING", "CRITICAL"
    persistence_hours: float
    error_sample_pct: float
    faulty_locs: Tuple[int, ...]
    message: str
    observed_ts: float = 0.0


def _safe_float(val: Any, default: float = 0.0) -> float:
    """Safely convert any value to float, shielding against None and non-finite values."""
    if val is None:
        return default
    try:
        f = float(val)
        return f if math.isfinite(f) else default
    except (ValueError, TypeError):
        return default


def extract_faulty_sensor_locs(sensors_raw: Any, is_mining: bool = True) -> Tuple[int, ...]:
    """Extract faulty I2C sensor locations (loc) from sensors JSON or objects."""
    faulty_locs_list: List[int] = []
    if isinstance(sensors_raw, str):
        try:
            sensors_list = json.loads(sensors_raw)
        except Exception:
            sensors_list = []
    elif isinstance(sensors_raw, list):
        sensors_list = sensors_raw
    elif hasattr(sensors_raw, "__iter__"):
        sensors_list = list(sensors_raw)
    else:
        sensors_list = []

    for s in sensors_list:
        if isinstance(s, dict):
            s_state = str(s.get("state", "")).lower()
            is_err = False
            if s_state in ("error", "err", "fault", "failed", "broken", "offline"):
                is_err = True
            elif is_mining and s_state != "measure":
                is_err = True
            if is_err and s.get("loc") is not None:
                try:
                    faulty_locs_list.append(int(float(s["loc"])))
                except (ValueError, TypeError):
                    pass
        elif hasattr(s, "state"):
            s_state = str(getattr(s, "state", "")).lower()
            is_err = False
            if s_state in ("error", "err", "fault", "failed", "broken", "offline"):
                is_err = True
            elif is_mining and s_state != "measure":
                is_err = True
            if is_err and hasattr(s, "loc") and getattr(s, "loc") is not None:
                try:
                    faulty_locs_list.append(int(float(getattr(s, "loc"))))
                except (ValueError, TypeError):
                    pass
    return tuple(sorted(set(faulty_locs_list)))


class PredictiveChainEngine:
    """Motor de evaluación predictiva de salud de cadenas y placas ASIC (Spec 069)."""

    def evaluate_chain_history(
        self,
        samples: List[Dict[str, Any]],
        now_ts: Optional[float] = None,
        config: Optional[Dict[str, Any]] = None,
        miner_name: Optional[str] = None,
        chain_id: Optional[int] = None,
        sibling_chains_samples: Optional[Dict[int, List[Dict[str, Any]]]] = None,
    ) -> Optional[PredictiveChainRisk]:
        """Evalúa el historial de muestras de una cadena bajo las reglas de la Spec 069."""
        if not samples:
            return None

        cfg = config or {}
        now = float(now_ts) if now_ts is not None else time.time()

        # Derive miner name and chain id if not explicitly passed
        m_name = miner_name or str(samples[0].get("miner_name", samples[0].get("miner_key", "unknown")))
        c_id = chain_id if chain_id is not None else int(samples[0].get("chain_id", 0))

        # -----------------------------------------------------------------
        # Regla 1 — Fallo Persistente de Sensor Térmico I2C (QA-069-01)
        # -----------------------------------------------------------------
        min_samples_i2c = int(cfg.get("chain_sensor_error_min_samples", 24))
        persistence_hours_i2c = float(cfg.get("chain_sensor_error_persistence_hours", 12.0))
        error_pct_threshold = float(cfg.get("chain_sensor_error_sample_pct", 90.0))
        window_seconds_i2c = persistence_hours_i2c * 3600.0

        # Filter samples within the 12h window if timestamps are present
        samples_with_ts = [s for s in samples if s.get("observed_ts") is not None]
        if samples_with_ts:
            window_samples_i2c = [
                s for s in samples if _safe_float(s.get("observed_ts")) >= (now - window_seconds_i2c)
            ]
        else:
            window_samples_i2c = samples

        n_samples_i2c = len(window_samples_i2c)
        if n_samples_i2c >= min_samples_i2c:
            err_samples = []
            loc_counts: Dict[int, int] = {}

            for s in window_samples_i2c:
                c_err = int(_safe_float(s.get("sensors_error_count"), 0))
                s_json = s.get("sensors_json", "[]")
                f_locs = extract_faulty_sensor_locs(s_json)
                if c_err > 0 or f_locs:
                    err_samples.append(s)
                    for loc in f_locs:
                        loc_counts[loc] = loc_counts.get(loc, 0) + 1

            err_pct = (len(err_samples) / n_samples_i2c) * 100.0
            if err_pct >= error_pct_threshold:
                # Check for persistent physical sensor location (>= 80% of error samples)
                common_locs_list = [
                    loc for loc, count in loc_counts.items()
                    if (count / len(err_samples)) >= 0.80
                ]
                if not common_locs_list and loc_counts:
                    top_loc, top_cnt = max(loc_counts.items(), key=lambda x: x[1])
                    if top_cnt / len(err_samples) >= 0.70:
                        common_locs_list = [top_loc]

                common_locs = tuple(sorted(common_locs_list))
                loc_str = f"loc {', '.join(map(str, common_locs))}" if common_locs else "I2C"

                # Calculate actual observed persistence duration
                if samples_with_ts and len(err_samples) >= 2:
                    t_min = min(_safe_float(s.get("observed_ts")) for s in err_samples)
                    t_max = max(_safe_float(s.get("observed_ts")) for s in err_samples)
                    duration_h = max(round((t_max - t_min) / 3600.0, 1), round(persistence_hours_i2c, 1))
                else:
                    duration_h = round(persistence_hours_i2c, 1)

                msg = (
                    f"Sensor térmico I2C ({loc_str}) en fallo continuo por "
                    f">{persistence_hours_i2c:.0f}h ({len(err_samples)}/{n_samples_i2c} muestras)."
                )
                return PredictiveChainRisk(
                    miner_name=m_name,
                    chain_id=c_id,
                    risk_type=RISK_TYPE_I2C_PERSISTENT_ERROR,
                    severity=SEVERITY_WARNING,
                    persistence_hours=duration_h,
                    error_sample_pct=round(err_pct, 1),
                    faulty_locs=common_locs,
                    message=msg,
                    observed_ts=now,
                )

        # -----------------------------------------------------------------
        # Regla 2 — Detección de Déficit de Hashrate Localizado
        # -----------------------------------------------------------------
        deficit_threshold_pct = float(cfg.get("chain_deficit_threshold_pct", 10.0))
        deficit_duration_hours = float(cfg.get("chain_deficit_duration_hours", 3.0))
        deficit_window_seconds = deficit_duration_hours * 3600.0
        min_samples_deficit = int(cfg.get("chain_deficit_min_samples", 4))

        if samples_with_ts:
            window_samples_def = [
                s for s in samples if _safe_float(s.get("observed_ts")) >= (now - deficit_window_seconds)
            ]
        else:
            window_samples_def = samples

        n_def = len(window_samples_def)
        if n_def >= min_samples_deficit:
            deficit_hits = [
                s for s in window_samples_def
                if _safe_float(s.get("hr_deficit_pct")) >= deficit_threshold_pct
            ]
            deficit_sample_pct = (len(deficit_hits) / n_def) * 100.0
            if deficit_sample_pct >= 80.0:
                # Verify sibling chains nominal (hr_deficit_pct <= 2.0%)
                sibling_nominal = True
                if sibling_chains_samples:
                    for sib_id, sib_samples in sibling_chains_samples.items():
                        if sib_id == c_id or not sib_samples:
                            continue
                        recent_sib = [
                            s for s in sib_samples
                            if _safe_float(s.get("observed_ts")) >= (now - deficit_window_seconds)
                        ] or sib_samples[-n_def:]
                        if recent_sib:
                            avg_sib_deficit = sum(_safe_float(s.get("hr_deficit_pct")) for s in recent_sib) / len(recent_sib)
                            if avg_sib_deficit > 2.0:
                                sibling_nominal = False
                                break

                if sibling_nominal:
                    avg_chain_deficit = sum(_safe_float(s.get("hr_deficit_pct")) for s in deficit_hits) / len(deficit_hits)
                    msg = (
                        f"Déficit sostenido de hashrate ({avg_chain_deficit:.1f}% >= {deficit_threshold_pct:.1f}%) "
                        f"durante >={deficit_duration_hours:.0f}h con placas adyacentes nominales (<=2.0%)."
                    )
                    return PredictiveChainRisk(
                        miner_name=m_name,
                        chain_id=c_id,
                        risk_type=RISK_TYPE_CHIP_DEGRADATION,
                        severity=SEVERITY_WARNING,
                        persistence_hours=round(deficit_duration_hours, 1),
                        error_sample_pct=round(deficit_sample_pct, 1),
                        faulty_locs=(),
                        message=msg,
                        observed_ts=now,
                    )

        return None

    def correlate_electrical_group(
        self,
        risks: List[PredictiveChainRisk],
        miners_config: Optional[List[Dict[str, Any]]] = None,
        now_ts: Optional[float] = None,
        group_time_window_s: float = 60.0,
    ) -> List[PredictiveChainRisk]:
        """Correlaciona perturbaciones eléctricas por elevador con fallback seguro (Spec 069 QA-069-02)."""
        if not risks:
            return []
        if not miners_config:
            return list(risks)

        now = float(now_ts) if now_ts is not None else time.time()

        # Build map of miner name / host -> electrical group
        miner_to_group: Dict[str, str] = {}
        for m in miners_config:
            grp = str(m.get("electrical_group") or m.get("group") or m.get("elevator") or "").strip()
            if grp and grp.lower() != "default":
                if m.get("name"):
                    miner_to_group[str(m["name"])] = grp
                if m.get("host"):
                    miner_to_group[str(m["host"])] = grp

        # Separate silicon degradation risks (subject to electrical group correlation)
        # from other risks (e.g. I2C persistent errors which are hardware sensor faults)
        group_candidates: Dict[str, List[PredictiveChainRisk]] = {}
        preserved_risks: List[PredictiveChainRisk] = []

        for r in risks:
            if r.risk_type in (RISK_TYPE_CHIP_DEGRADATION, "DEFICIT", "HASH_DROP"):
                grp = miner_to_group.get(r.miner_name) or miner_to_group.get(r.miner_name.split("|")[0])
                if grp:
                    group_candidates.setdefault(grp, []).append(r)
                else:
                    preserved_risks.append(r)
            else:
                preserved_risks.append(r)

        # For each group, check if >= 2 distinct miners are affected
        for grp, grp_risks in group_candidates.items():
            distinct_miners = sorted(set(r.miner_name for r in grp_risks))
            if len(distinct_miners) >= 2:
                # Check timing: within group_time_window_s
                timestamps = [r.observed_ts for r in grp_risks if r.observed_ts > 0.0]
                is_simultaneous = True
                if len(timestamps) >= 2:
                    if (max(timestamps) - min(timestamps)) > group_time_window_s:
                        is_simultaneous = False

                if is_simultaneous:
                    # Classify as POWER_DISTURBANCE (Spec 069: QA-069-02)
                    # Suppress individual chip degradation alerts
                    dist_risk = PredictiveChainRisk(
                        miner_name=f"Grupo {grp}",
                        chain_id=0,
                        risk_type=RISK_TYPE_POWER_DISTURBANCE,
                        severity=SEVERITY_WARNING,
                        persistence_hours=0.0,
                        error_sample_pct=100.0,
                        faulty_locs=(),
                        message=(
                            f"Perturbación eléctrica en {grp} afectando a "
                            f"{len(distinct_miners)} mineros ({', '.join(distinct_miners)}) simultáneamente. "
                            "Alerta de silicio individual suprimida."
                        ),
                        observed_ts=now,
                    )
                    preserved_risks.append(dist_risk)
                    continue

            # Fallback: keep individual risks intact
            preserved_risks.extend(grp_risks)

        return preserved_risks


def build_predictive_chain_risk_card(risk: PredictiveChainRisk) -> str:
    """Format a Mobile-First card (width <= 32 cols) for predictive chain break risk alerts (Spec 069)."""
    lines = [
        "⚠️ *RIESGO CHAIN BREAK*",
        MOBILE_CARD_SEPARATOR,
        f"• Minero: {risk.miner_name}",
    ]
    is_group = risk.miner_name.startswith("Grupo ") or risk.risk_type in (
        RISK_TYPE_POWER_DISTURBANCE,
        RISK_TYPE_ELECTRICAL_SAG,
    )
    if not is_group and risk.chain_id is not None and risk.chain_id >= 0:
        lines.append(f"• Cadena: {risk.chain_id} (Board {risk.chain_id})")

    sev_badge = "🔴" if risk.severity.upper() == "CRITICAL" else "⚠️"
    lines.append(f"• Severidad: {sev_badge} {risk.severity.upper()}")
    lines.append(MOBILE_CARD_SEPARATOR)

    lines.append("💡 *Diagnóstico:*")
    lines.extend(wrap_mobile_lines(risk.message, width=MOBILE_LINE_WIDTH_LIMIT))
    lines.append(MOBILE_CARD_SEPARATOR)

    lines.append("🛠 *Recomendación:*")
    if risk.risk_type == RISK_TYPE_I2C_PERSISTENT_ERROR:
        rec = "Programar inspección física para evitar parada abrupta por firmware."
    elif risk.risk_type == RISK_TYPE_CHIP_DEGRADATION:
        rec = "Revisar dominio de tensión y chips estrangulados en la placa."
    elif risk.risk_type in (RISK_TYPE_POWER_DISTURBANCE, RISK_TYPE_ELECTRICAL_SAG):
        rec = "Verificar caída de fase o estabilidad de tensión en el elevador."
    else:
        rec = "Monitorear telemetría y programar revisión técnica."
    lines.extend(wrap_mobile_lines(rec, width=MOBILE_LINE_WIDTH_LIMIT))
    lines.append(MOBILE_CARD_SEPARATOR)

    return "\n".join(lines)

