"""
Governance Dashboard and Directive Status Formatter (Spec 084 / PROP-020).

Provides unified observability across all 16 active directives in 5 layers (P0-P4):
- P0: Thermal Guard, Failsafe Fan, Recovery Max Cooling.
- P1: Stock Firmware Fallback, Thermal Pause Interlock.
- P2: Soft Contingency Schedule, Solar Thermal Envelope, Thermal Headroom Gate.
- P3: Incident Quiet Window, Facility Settle Window, Symmetric Balance, FGA Cohorts.
- P4: VNish Internal Daemon, Headroom Chilling.

Strict Mobile-First formatting: every text line is guaranteed <= 32 columns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import datetime
import time
from typing import Any, Dict, List, Optional

from app.governance.governance_context import MinerGovernanceContext


@dataclass(frozen=True)
class GovernanceSnapshot:
    """Consolidated immutable snapshot of all governance directives acting on a miner."""

    created_ts: float
    miner_name: str
    fan_action: str
    fan_duty: int
    target_power_w: Optional[int]
    current_power_w: Optional[float]
    chip_temp_c: Optional[float]
    fga_cohort: str
    fga_r_th: Optional[float]
    elevator_group: str
    elevator_gate_status: str
    solar_envelope_active: bool
    contingency_mode: str
    restart_required: bool
    is_deadlocked: bool
    details: Dict[str, Any] = field(default_factory=dict)


def evaluate_recovery_deadlock(
    action: Optional[str],
    recovery_since_ts: Optional[float],
    now_ts: float,
    is_warming_up: bool = False,
    threshold_seconds: float = 300.0,
    rate_ths: Optional[float] = None,
    active_boards: Optional[int] = None,
    current_power_w: Optional[float] = None,
) -> bool:
    """Detect if a miner is trapped in ACTION_RECOVERY_MAX_COOLING for too long (F-02 deadlock)."""
    if is_warming_up:
        return False
    if not action or "RECOVERY_MAX_COOLING" not in action.upper():
        return False
    if recovery_since_ts is None:
        return False
    duration = float(now_ts) - float(recovery_since_ts)
    if duration <= float(threshold_seconds):
        return False

    # Thermal adaptation health check:
    # If the miner is actively hashing at normal levels (rate >= 80 TH/s), has healthy boards (>= 3 or None),
    # and power is an intermediate thermal preset (>= 2200W), this is an ambient temperature step-down
    # governed legitimately by VNish, NOT a hardware cooling deadlock stall.
    if (
        rate_ths is not None
        and rate_ths >= 80.0
        and (active_boards is None or active_boards >= 3)
        and (current_power_w is not None and current_power_w >= 2200.0)
    ):
        return False

    return True


def _pad_box_line(text: str, width: int = 32) -> str:
    """Format text inside box borders: ║ text ║ with width characters."""
    inner_width = width - 4  # 2 for '║ ' and 2 for ' ║'
    clipped = text[:inner_width]
    return f"║ {clipped.ljust(inner_width)} ║"


def _short_name(name: str) -> str:
    """Shorten miner identifier to fit compact table (e.g. S19JPRO-24 -> M24)."""
    clean = str(name).strip()
    if clean.upper().startswith("S19JPRO-"):
        return f"M{clean[8:]}"
    if clean.upper().startswith("MINER-") or clean.upper().startswith("MINER_"):
        return f"M{clean[6:]}"
    return clean[:6]


def build_fleet_directives_card(
    contexts: List[MinerGovernanceContext],
    elevator_states: Optional[Dict[str, Any]] = None,
    solar_active: bool = False,
    now_ts: Optional[float] = None,
) -> str:
    """Build compact fleet-wide governance status card (strictly <= 32 cols)."""
    ts = float(now_ts if now_ts is not None else time.time())
    lines = [
        "╔══════════════════════════════╗",
        "║  DIRECTIVAS DE GOBERNANZA   ║",
        "╚══════════════════════════════╝",
    ]

    deadlocked_miners = []

    if not contexts:
        lines.append("Sin mineros registrados.")
    else:
        for ctx in sorted(contexts, key=lambda c: c.miner_name):
            m_short = _short_name(ctx.miner_name)
            pwr_str = f"{int(ctx.current_power_w or 0)}W" if ctx.current_power_w else "---W"
            duty_str = f"{ctx.fan_duty}%" if ctx.fan_duty is not None else "--%"

            action_raw = str(ctx.fan_action or "OK").replace("ACTION_", "")
            if "HOLD" in action_raw:
                act_tag = "HOLD"
            elif "DOWN" in action_raw:
                act_tag = "DOWN"
            elif "UP" in action_raw:
                act_tag = "UP"
            elif "RECOVERY" in action_raw:
                act_tag = "COOL"
            elif "SPIKE" in action_raw:
                act_tag = "SPK"
            elif "FAILSAFE" in action_raw:
                act_tag = "FAIL"
            else:
                act_tag = action_raw[:4]

            # Deadlock check
            deadlocked = evaluate_recovery_deadlock(
                ctx.fan_action,
                ctx.recovery_since_ts,
                ts,
                ctx.is_warming_up,
                rate_ths=ctx.rate_ths,
                active_boards=ctx.active_boards,
                current_power_w=ctx.current_power_w,
            )
            if deadlocked:
                deadlocked_miners.append(m_short)
                status_icon = "⚠️"
            elif ctx.is_warming_up:
                status_icon = "⏳"
            elif ctx.restart_required:
                status_icon = "🔄"
            else:
                status_icon = "OK"

            # Line structure: M24 2698W 92% HOLD OK
            line = f"{m_short:<3} {pwr_str:>5} {duty_str:>3} {act_tag:<4} {status_icon}"
            lines.append(line[:32])

    lines.append("--------------------------------")

    # Environmental & macro governance summary
    solar_tag = "ACTIVO (2500W)" if solar_active else "INACTIVO"
    lines.append(f"SOLAR: {solar_tag}"[:32])

    if elevator_states:
        for grp, pwr in sorted(elevator_states.items()):
            grp_short = grp.replace("elevator_", "ELEV").upper()
            grp_val = f"{int(pwr)}W"
            lines.append(f"{grp_short}: {grp_val}"[:32])

    if deadlocked_miners:
        lines.append(f"DEADLOCK: ⚠️ {', '.join(deadlocked_miners)}"[:32])
    else:
        lines.append("DEADLOCK: NINGUNO")

    lines.append("--------------------------------")
    lines.append("Detalle: /directivas <minero>")

    # Final guarantee of <= 32 cols for every line
    return "\n".join(l[:32] for l in lines)


def build_miner_directive_card(
    ctx: MinerGovernanceContext,
    elevator_group: Optional[str] = None,
    elevator_gate_status: Optional[str] = None,
    solar_active: bool = False,
    is_deadlocked: bool = False,
    deadlock_duration_s: float = 0.0,
    contingency_mode: str = "VALLE (5400W)",
    now_ts: Optional[float] = None,
) -> str:
    """Build detailed per-miner directive inspection card (strictly <= 32 cols)."""
    ts = float(now_ts if now_ts is not None else time.time())

    title = f"DIRECTIVAS: {ctx.miner_name}"
    lines = [
        "╔══════════════════════════════╗",
        _pad_box_line(title),
        "╚══════════════════════════════╝",
    ]

    # P0: Thermal Guard & Cooling Safety
    lines.append("P0: SEGURIDAD HARDWARE")
    act_str = str(ctx.fan_action or "NONE").replace("ACTION_", "")
    duty_val = f"{ctx.fan_duty}%" if ctx.fan_duty is not None else "--%"
    lines.append(f"  Fan: {act_str} ({duty_val})"[:32])

    chip_t = f"{ctx.max_chip_temp_c:.1f}°C" if ctx.max_chip_temp_c is not None else "N/A"
    lines.append(f"  Chips: {chip_t} (Techo 84°C)"[:32])

    if is_deadlocked:
        lines.append(f"  Deadlock: ⚠️ SI ({int(deadlock_duration_s)}s)"[:32])
    else:
        lines.append("  Deadlock: NO (0s)")

    # P1: Firmware & Restart Interlock
    lines.append("P1: FIRMWARE & REINICIO")
    fw_tag = "VNISH" if not ctx.is_stock_firmware else "STOCK (ALERTA)"
    lines.append(f"  Firmware: {fw_tag}"[:32])

    rst_tag = "SI (Pendiente)" if ctx.restart_required else "NO"
    lines.append(f"  RestartReq: {rst_tag}"[:32])

    # P2: Elevator & Environment
    lines.append("P2: ELEVADOR & AMBIENTE")
    grp = str(elevator_group or ctx.electrical_group or "elevator_1")
    lines.append(f"  Grupo: {grp}"[:32])

    curr_p = int(ctx.current_power_w or 0)
    tgt_p = int(ctx.target_power_w or 2700)
    lines.append(f"  Potencia: {curr_p}W / {tgt_p}W"[:32])

    sol_tag = "ACTIVO (cap 2500)" if solar_active else "INACTIVO"
    lines.append(f"  Solar: {sol_tag}"[:32])

    hr_ok = "OK (<80°C)" if (ctx.max_chip_temp_c or 0) < 80.0 else "BLOQUEO (>=80°)"
    lines.append(f"  Headroom: {hr_ok}"[:32])

    # P3: Facility Agent (FGA) & Gates
    lines.append("P3: AGENTE DE PLANTA (FGA)")
    cohort = str(ctx.fga_cohort or "STANDARD")
    r_th_str = f"{ctx.fga_thermal_resistance:.3f}" if ctx.fga_thermal_resistance else "0.022"
    lines.append(f"  Cohorte: {cohort} (Rth:{r_th_str})"[:32])

    gate_st = str(elevator_gate_status or "PERMITIDO")
    lines.append(f"  Elevator Gate: {gate_st}"[:32])

    lines.append(f"  Contingencia: {contingency_mode}"[:32])

    # P4: Firmware Target State
    lines.append("P4: ESTADO FIRMWARE")
    preset_str = str(ctx.configured_preset or f"{tgt_p}W")
    lines.append(f"  Preset Activo: {preset_str}"[:32])

    lines.append("--------------------------------")
    overall = "⚠️ ATENCIÓN" if (is_deadlocked or ctx.restart_required) else "✅ NOMINAL"
    lines.append(f"Estado: {overall}"[:32])

    # Final guarantee of <= 32 cols for every line
    return "\n".join(l[:32] for l in lines)


def build_deadlock_alert_text(
    miner_name: str,
    current_power_w: float,
    target_power_w: float,
    duration_seconds: float,
) -> str:
    """Format proactive deadlock warning for Telegram (strictly <= 32 cols)."""
    lines = [
        "⚠️ ALERTA DE GOBERNANZA",
        "--------------------------------",
        f"Minero: {miner_name}"[:32],
        "Estado: RECOVERY_MAX_COOLING",
        f"Duración: {int(duration_seconds)}s (>300s)",
        f"Potencia: {int(current_power_w)}W / {int(target_power_w)}W"[:32],
        "--------------------------------",
        "Estancamiento de enfriamiento.",
        "Ventiladores al 100% PWM.",
        "Verificar: /directivas o /agent",
    ]
    return "\n".join(l[:32] for l in lines)
