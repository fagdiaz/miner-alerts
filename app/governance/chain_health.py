"""Predictive Hashboard and Chain Health Assessment Engine (Spec 054).

Analyzes granular telemetry from /api/v1/chains to identify physical sensor
anomalies (I2C bus errors), performance deficits, and impending chain breaks
before catastrophic hardware failures or abrupt miner reboots occur.
"""

from __future__ import annotations

import json
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
        for s in getattr(chain, "sensors", []):
            if hasattr(s, "is_healthy") and not s.is_healthy:
                if getattr(s, "loc", None) is not None:
                    faulty_locs_list.append(int(s.loc))
            elif isinstance(s, dict) and str(s.get("state", "")).lower() != "measure":
                if s.get("loc") is not None:
                    faulty_locs_list.append(int(s["loc"]))
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
        if isinstance(sensors_raw, str):
            try:
                sensors_list = json.loads(sensors_raw)
                if isinstance(sensors_list, list):
                    for s in sensors_list:
                        if isinstance(s, dict) and str(s.get("state", "")).lower() != "measure":
                            if s.get("loc") is not None:
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
) -> Tuple[bool, Optional[str]]:
    """Evaluate consecutive fault streaks and cooldown to avoid alert spam.

    Returns:
        (should_alert: bool, alert_card_text: Optional[str])
    """
    now = now_ts if now_ts is not None else time.time()

    if assessment.overall_status in (STATUS_CHAIN_SENSOR_ERROR, STATUS_CHAIN_FAULT):
        current_streak = int(streak_data.get("fault_streak", 0)) + 1
        streak_data["fault_streak"] = current_streak
        last_alert_ts = float(streak_data.get("last_alert_ts", 0.0))

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
    lines.append("Falla de bus/sensor en placa.")
    lines.append("Vnish puede abortar cadena")
    lines.append("(chain_break) abruptamente.")
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
