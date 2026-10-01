"""
app/governance/fga_actuator.py
Spec 083 — FGA Actuator Loop: Conexión FGA → Elevator Budget → VNish (PROP-019)

Puente desacoplado entre:
1. El Facility Governance Agent (evaluación asimétrica y modelado térmico de silicio).
2. El orquestador de presupuestos de potencia (ElevatorBudget Gates 0-6).
3. El actuador seguro de firmware (safe_set_miner_preset).
4. La persistencia de decisiones en SQLite (EventStore.facility_agent_actions).

Invariantes:
- Cero I/O en la función pura de evaluación evaluate_fga_actuator_step().
- Toda modulación pasa por Gates 0-6 antes de llamar a la API de hardware.
- Respeto estricto a las políticas de intervención (presets_enabled, is_warming_up).
- Compatible con entornos de simulación (qa_mode) e inyección de dependencias en tests.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple, Union

from app.governance.facility_agent import (
    STRATEGY_BALANCED,
    FacilityAgentDecision,
    evaluate_asymmetric_allocation,
)
from app.governance.elevator_budget import (
    ACTION_ALLOW_TRANSITION,
    FacilityBudgetState,
    evaluate_facility_transition_permission,
    get_miner_max_hardware_preset,
    parse_preset_wattage,
)

if TYPE_CHECKING:
    from app.governance.governance_context import MinerGovernanceContext
    from app.core.event_store import EventStore


@dataclass(frozen=True)
class FgaActuatorDecision:
    """
    Decisión estructurada e inmutable del ciclo del actuador FGA.
    """
    candidate_miner: str
    target_preset: str
    current_preset: str
    strategy: str
    can_proceed: bool
    gate_action: str
    gate_reason: str
    action_status: str  # 'PERMITTED' | 'BLOCKED' | 'EXECUTED' | 'FAILED' | 'SIMULATED' | 'NOOP'
    remaining_settle_s: float = 0.0
    projected_group_power_w: float = 0.0
    power_w: Optional[float] = None
    chip_temp_c: Optional[float] = None
    thermal_resistance: Optional[float] = None
    electrical_group: Optional[str] = None
    created_ts: float = field(default_factory=time.time)


def evaluate_fga_actuator_step(
    governance_contexts: List[Any],
    facility_state: FacilityBudgetState,
    now_dt: datetime,
    now_ts: float,
    strategy: str = STRATEGY_BALANCED,
    config: Optional[Dict[str, Any]] = None,
    presets_enabled: bool = True,
) -> FgaActuatorDecision:
    """
    Evaluación pura y determinista de una oportunidad de actuación del FGA.
    
    1. Ejecuta evaluate_asymmetric_allocation() sobre la flota.
    2. Si surge un candidate_step, extrae el minero y preset objetivo.
    3. Verifica salvaguardas (is_warming_up, presets_enabled).
    4. Somete la transición a evaluate_facility_transition_permission() (Gates 0-6).
    5. Retorna un FgaActuatorDecision inmutable con la autorización o causa de retención.
    """
    fga_dec: FacilityAgentDecision = evaluate_asymmetric_allocation(
        governance_contexts,
        strategy=strategy,
    )

    if not fga_dec.candidate_step:
        return FgaActuatorDecision(
            candidate_miner="",
            target_preset="",
            current_preset="",
            strategy=strategy,
            can_proceed=False,
            gate_action="NO_CANDIDATE",
            gate_reason="Flota optimizada de acuerdo con la estrategia FGA; no hay candidatos de modulación.",
            action_status="NOOP",
            created_ts=now_ts,
        )

    miner_name, target_preset, fga_reason = fga_dec.candidate_step

    # Buscar contexto específico del candidato
    cand_ctx = None
    for c in governance_contexts:
        c_name = getattr(c, "miner_name", "") or (c.get("name", "") if isinstance(c, dict) else "")
        if c_name == miner_name:
            cand_ctx = c
            break

    curr_p = "2500W"
    elec_group = "elevator_1"
    chip_t = 80.0
    pwr_w = 2500.0
    r_th = 0.022
    is_warming = False

    if cand_ctx is not None:
        if isinstance(cand_ctx, dict):
            curr_p = cand_ctx.get("preset", "2500W")
            elec_group = cand_ctx.get("electrical_group") or cand_ctx.get("group", "elevator_1")
            chip_t = cand_ctx.get("chip_temp_c", 80.0) or 80.0
            pwr_w = cand_ctx.get("power_w", 2500.0) or 2500.0
            is_warming = bool(cand_ctx.get("is_warming_up", False))
        else:
            curr_p = (
                getattr(cand_ctx, "executed_preset", None)
                or getattr(cand_ctx, "configured_preset", None)
                or "2500W"
            )
            elec_group = getattr(cand_ctx, "electrical_group", None) or "elevator_1"
            chip_t = getattr(cand_ctx, "chip_temp_c", None) or 80.0
            pwr_w = getattr(cand_ctx, "current_power_w", None) or 2500.0
            r_th = getattr(cand_ctx, "fga_thermal_resistance", None) or 0.022
            is_warming = bool(getattr(cand_ctx, "is_warming_up", False))

    if curr_p and curr_p.isdigit():
        curr_p = f"{curr_p}W"

    # Guardia 1: Fase de calentamiento (cold-boot grace)
    if is_warming:
        return FgaActuatorDecision(
            candidate_miner=miner_name,
            target_preset=target_preset,
            current_preset=curr_p,
            strategy=strategy,
            can_proceed=False,
            gate_action="HOLD_WARMING_UP",
            gate_reason=f"Minero '{miner_name}' en fase de gracia de arranque (cold-boot grace / autotune).",
            action_status="BLOCKED",
            power_w=pwr_w,
            chip_temp_c=chip_t,
            thermal_resistance=r_th,
            electrical_group=elec_group,
            created_ts=now_ts,
        )

    # Guardia 2: Intervención de presets habilitada en configuración
    if not presets_enabled:
        return FgaActuatorDecision(
            candidate_miner=miner_name,
            target_preset=target_preset,
            current_preset=curr_p,
            strategy=strategy,
            can_proceed=False,
            gate_action="HOLD_PRESETS_DISABLED",
            gate_reason="Gobernanza autónoma de presets deshabilitada en la configuración del monitor.",
            action_status="BLOCKED",
            power_w=pwr_w,
            chip_temp_c=chip_t,
            thermal_resistance=r_th,
            electrical_group=elec_group,
            created_ts=now_ts,
        )

    # Construir mapa de presets del elevador para evaluación de compuertas
    group_presets: Dict[str, str] = {}
    for c in governance_contexts:
        c_name = getattr(c, "miner_name", "") or (c.get("name", "") if isinstance(c, dict) else "")
        c_grp = getattr(c, "electrical_group", None) or (
            c.get("electrical_group") or c.get("group", "elevator_1") if isinstance(c, dict) else "elevator_1"
        )
        if c_grp == elec_group:
            c_p = (
                getattr(c, "executed_preset", None)
                or getattr(c, "configured_preset", None)
                or (c.get("preset", "2500W") if isinstance(c, dict) else "2500W")
            )
            if c_p and str(c_p).isdigit():
                c_p = f"{c_p}W"
            group_presets[c_name] = c_p

    hw_max = get_miner_max_hardware_preset(miner_name, config=config)

    staggered = evaluate_facility_transition_permission(
        miner_name=miner_name,
        current_preset=curr_p,
        target_preset=target_preset,
        group_presets=group_presets,
        facility_state=facility_state,
        now_dt=now_dt,
        now_ts=now_ts,
        group_name=elec_group,
        config=config,
        max_chip_temp_c=chip_t,
        miner_hardware_max_preset=hw_max,
    )

    status = "PERMITTED" if staggered.can_proceed else "BLOCKED"

    return FgaActuatorDecision(
        candidate_miner=miner_name,
        target_preset=target_preset,
        current_preset=curr_p,
        strategy=strategy,
        can_proceed=staggered.can_proceed,
        gate_action=staggered.action,
        gate_reason=staggered.reason,
        action_status=status,
        remaining_settle_s=staggered.remaining_settle_seconds,
        projected_group_power_w=staggered.projected_group_power_w,
        power_w=pwr_w,
        chip_temp_c=chip_t,
        thermal_resistance=r_th,
        electrical_group=elec_group,
        created_ts=now_ts,
    )


def execute_fga_actuator_step(
    decision: FgaActuatorDecision,
    host: str,
    password: str,
    facility_state: FacilityBudgetState,
    now_ts: float,
    config: Optional[Dict[str, Any]] = None,
    qa_mode: bool = False,
    event_store: Optional[EventStore] = None,
    miner_state: Optional[Any] = None,
    state_lock: Optional[Any] = None,
    safe_set_fn: Optional[Callable[..., Tuple[bool, str]]] = None,
) -> FgaActuatorDecision:
    """
    Ejecución controlada de la decisión emitida por evaluate_fga_actuator_step().

    - Si la decisión está bloqueada (can_proceed=False), la persiste en EventStore y retorna.
    - Si está autorizada (can_proceed=True), aplica el cambio de preset vía safe_set_fn
      (o simula si qa_mode=True), registra la transición en FacilityBudgetState y en EventStore.
    """
    if not decision.can_proceed:
        if event_store is not None:
            event_store.record_facility_agent_action(
                miner_name=decision.candidate_miner,
                electrical_group=decision.electrical_group,
                strategy=decision.strategy,
                from_preset=decision.current_preset,
                to_preset=decision.target_preset,
                action_status=decision.action_status,
                gate_name=decision.gate_action,
                reason=decision.gate_reason,
                power_w=decision.power_w,
                chip_temp_c=decision.chip_temp_c,
                thermal_resistance=decision.thermal_resistance,
                created_ts=now_ts,
            )
        return decision

    # Transición autorizada
    if qa_mode:
        ok, msg = True, "qa_simulated"
        status = "SIMULATED"
    else:
        if safe_set_fn is None:
            from app.vnish.client import safe_set_miner_preset
            set_fn = safe_set_miner_preset
        else:
            set_fn = safe_set_fn

        timeout = float((config or {}).get("fan_governor_request_timeout", 2.5))
        ok, msg = set_fn(
            host,
            password,
            decision.target_preset,
            timeout=timeout,
            clamp_top_preset=True,
            top_preset=decision.target_preset,
            min_preset="1740",
            auto_restart_mining=False,
        )
        status = "EXECUTED" if ok else "FAILED"

    if ok:
        facility_state.record_transition(decision.candidate_miner, decision.target_preset, now_ts)
        if miner_state is not None:
            if state_lock is not None:
                with state_lock:
                    miner_state.balancer_preset = decision.target_preset
                    miner_state.vnish_discovered_top_preset = decision.target_preset.rstrip("W")
                    miner_state.vnish_discovered_preset = decision.target_preset.rstrip("W")
                    miner_state.vnish_discovered_target_power_w = float(parse_preset_wattage(decision.target_preset))
                    miner_state.last_preset_change_ts = now_ts
            else:
                miner_state.balancer_preset = decision.target_preset
                miner_state.vnish_discovered_top_preset = decision.target_preset.rstrip("W")
                miner_state.vnish_discovered_preset = decision.target_preset.rstrip("W")
                miner_state.vnish_discovered_target_power_w = float(parse_preset_wattage(decision.target_preset))
                miner_state.last_preset_change_ts = now_ts

    if event_store is not None:
        rec_reason = decision.gate_reason if ok else f"{decision.gate_reason} | error: {msg}"
        event_store.record_facility_agent_action(
            miner_name=decision.candidate_miner,
            electrical_group=decision.electrical_group,
            strategy=decision.strategy,
            from_preset=decision.current_preset,
            to_preset=decision.target_preset,
            action_status=status,
            gate_name=decision.gate_action,
            reason=rec_reason,
            power_w=decision.power_w,
            chip_temp_c=decision.chip_temp_c,
            thermal_resistance=decision.thermal_resistance,
            created_ts=now_ts,
        )

    return FgaActuatorDecision(
        candidate_miner=decision.candidate_miner,
        target_preset=decision.target_preset,
        current_preset=decision.current_preset,
        strategy=decision.strategy,
        can_proceed=decision.can_proceed,
        gate_action=decision.gate_action,
        gate_reason=decision.gate_reason if ok else f"{decision.gate_reason} (Fallo: {msg})",
        action_status=status,
        remaining_settle_s=facility_state.settle_window_seconds if ok else 0.0,
        projected_group_power_w=decision.projected_group_power_w,
        power_w=decision.power_w,
        chip_temp_c=decision.chip_temp_c,
        thermal_resistance=decision.thermal_resistance,
        electrical_group=decision.electrical_group,
        created_ts=now_ts,
    )
