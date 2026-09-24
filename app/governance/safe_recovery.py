from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

ACTION_WAIT_SETTLE = "WAIT_SETTLE"
ACTION_PRE_CLAMP_AND_RESTART = "PRE_CLAMP_AND_RESTART"
ACTION_HOLD_DEGRADED = "HOLD_DEGRADED"
ACTION_STAGED_RAMP_UP = "STAGED_RAMP_UP"
ACTION_NORMAL = "NORMAL"
ACTION_INHIBIT_HARDWARE_FAULT = "INHIBIT_HARDWARE_FAULT"

DEFAULT_SETTLE_WINDOW_SECONDS = 120.0
DEFAULT_PRE_CLAMP_PRESET = "1800"
DEFAULT_HEADROOM_CHILLING_DURATION = 180.0
DEFAULT_RAMP_UP_SOAK_SECONDS = 180.0


@dataclass
class SafeRecoveryState:
    miner_name: str
    stopped_since_ts: Optional[float] = None
    recovery_attempts: int = 0
    max_recovery_attempts: int = 1
    pre_clamp_preset: str = DEFAULT_PRE_CLAMP_PRESET
    is_pre_clamped: bool = False
    original_preset: Optional[str] = None
    clamped_ts: Optional[float] = None
    boost_cooling_active: bool = False
    boost_cooling_expires_ts: Optional[float] = None
    staged_ramp_up_pending: bool = False
    staged_ramp_up_soak_start_ts: Optional[float] = None


@dataclass(frozen=True)
class RecoveryDecision:
    action: str
    target_preset: Optional[str] = None
    clamp_top_preset: bool = False
    trigger_restart: bool = False
    reason: str = ""
    boost_cooling: bool = False
    soak_seconds_remaining: float = 0.0


def evaluate_safe_recovery(
    state: SafeRecoveryState,
    current_ts: float,
    miner_state: str,
    chain_fault_present: bool = False,
    current_rate_ths: float = 0.0,
    threshold_ths: float = 60.0,
    settle_window_seconds: float = DEFAULT_SETTLE_WINDOW_SECONDS,
    ramp_up_soak_seconds: float = DEFAULT_RAMP_UP_SOAK_SECONDS,
    stock_firmware_fallback: bool = False,
    sensor_fault_present: bool = False,
) -> Tuple[RecoveryDecision, SafeRecoveryState]:
    """
    Pure functional decision engine for soft-landing recovery and PSU Latch-Off protection.
    Determines whether to wait, pre-clamp to safe floor (1800W), hold in degraded mode,
    or execute a staged ramp-up back to nominal power.
    """
    # 0. Hardware / Firmware Inviolable Inhibitions
    if stock_firmware_fallback:
        return (
            RecoveryDecision(
                action=ACTION_INHIBIT_HARDWARE_FAULT,
                target_preset=None,
                clamp_top_preset=False,
                trigger_restart=False,
                reason="Inhibición defensiva: minero en firmware de fábrica Bitmain (NAND). Tarjeta MicroSD VNish ausente o no detectada.",
            ),
            state,
        )

    if sensor_fault_present:
        return (
            RecoveryDecision(
                action=ACTION_INHIBIT_HARDWARE_FAULT,
                target_preset=None,
                clamp_top_preset=False,
                trigger_restart=False,
                reason="Inhibición defensiva: falla física de sensor térmico I2C en cadena, evitando ciclos de reinicio destructivos.",
            ),
            state,
        )

    # Create a copy or update state cleanly
    is_stopped = (miner_state in ("stopped", "paused", "LOW", "HASHBOARD") or current_rate_ths < 5.0)

    # 1. Normal state: miner is hashing above threshold
    if not is_stopped and current_rate_ths >= threshold_ths:
        # Check if we are in staged ramp up soak
        if state.is_pre_clamped and state.staged_ramp_up_pending:
            if state.staged_ramp_up_soak_start_ts is None:
                new_state = SafeRecoveryState(
                    miner_name=state.miner_name,
                    stopped_since_ts=None,
                    recovery_attempts=0,
                    max_recovery_attempts=state.max_recovery_attempts,
                    pre_clamp_preset=state.pre_clamp_preset,
                    is_pre_clamped=True,
                    original_preset=state.original_preset,
                    clamped_ts=state.clamped_ts,
                    staged_ramp_up_pending=True,
                    staged_ramp_up_soak_start_ts=current_ts,
                )
                return (
                    RecoveryDecision(
                        action=ACTION_STAGED_RAMP_UP,
                        target_preset=state.pre_clamp_preset,
                        clamp_top_preset=True,
                        trigger_restart=False,
                        reason="Minero estabilizado en OK con pre-clamp: iniciando soak de rampa ascendente",
                        soak_seconds_remaining=ramp_up_soak_seconds,
                    ),
                    new_state,
                )
            
            elapsed_soak = current_ts - state.staged_ramp_up_soak_start_ts
            if elapsed_soak >= ramp_up_soak_seconds:
                # Soak completed, restore original nominal preset
                restored_preset = state.original_preset or "2300"
                new_state = SafeRecoveryState(
                    miner_name=state.miner_name,
                    stopped_since_ts=None,
                    recovery_attempts=0,
                    max_recovery_attempts=state.max_recovery_attempts,
                    pre_clamp_preset=state.pre_clamp_preset,
                    is_pre_clamped=False,
                    original_preset=None,
                    clamped_ts=None,
                    staged_ramp_up_pending=False,
                    staged_ramp_up_soak_start_ts=None,
                )
                return (
                    RecoveryDecision(
                        action=ACTION_STAGED_RAMP_UP,
                        target_preset=restored_preset,
                        clamp_top_preset=False,
                        trigger_restart=False,
                        reason=f"Soak de {ramp_up_soak_seconds:.0f}s completado: restaurando preset nominal {restored_preset}W",
                        soak_seconds_remaining=0.0,
                    ),
                    new_state,
                )
            else:
                remaining = max(0.0, ramp_up_soak_seconds - elapsed_soak)
                return (
                    RecoveryDecision(
                        action=ACTION_STAGED_RAMP_UP,
                        target_preset=state.pre_clamp_preset,
                        clamp_top_preset=True,
                        trigger_restart=False,
                        reason=f"Soak de rampa en progreso ({elapsed_soak:.0f}s/{ramp_up_soak_seconds:.0f}s)",
                        soak_seconds_remaining=remaining,
                    ),
                    state,
                )

        # Fully normal operation
        new_state = SafeRecoveryState(
            miner_name=state.miner_name,
            stopped_since_ts=None,
            recovery_attempts=0,
            max_recovery_attempts=state.max_recovery_attempts,
            pre_clamp_preset=state.pre_clamp_preset,
            is_pre_clamped=False,
            original_preset=None,
            clamped_ts=None,
            staged_ramp_up_pending=False,
            staged_ramp_up_soak_start_ts=None,
        )
        return (
            RecoveryDecision(
                action=ACTION_NORMAL,
                target_preset=None,
                clamp_top_preset=False,
                trigger_restart=False,
                reason="Operación normal",
            ),
            new_state,
        )

    # 2. Stopped or degraded state detected
    if state.stopped_since_ts is None:
        new_state = SafeRecoveryState(
            miner_name=state.miner_name,
            stopped_since_ts=current_ts,
            recovery_attempts=state.recovery_attempts,
            max_recovery_attempts=state.max_recovery_attempts,
            pre_clamp_preset=state.pre_clamp_preset,
            is_pre_clamped=state.is_pre_clamped,
            original_preset=state.original_preset,
            clamped_ts=state.clamped_ts,
            staged_ramp_up_pending=False,
            staged_ramp_up_soak_start_ts=None,
        )
        return (
            RecoveryDecision(
                action=ACTION_WAIT_SETTLE,
                reason=f"Detención detectada ({miner_state}): iniciando ventana pasiva de {settle_window_seconds:.0f}s",
                soak_seconds_remaining=settle_window_seconds,
            ),
            new_state,
        )

    elapsed_stopped = current_ts - state.stopped_since_ts

    # 3. Passive settle window active
    if elapsed_stopped < settle_window_seconds:
        remaining = max(0.0, settle_window_seconds - elapsed_stopped)
        return (
            RecoveryDecision(
                action=ACTION_WAIT_SETTLE,
                reason=f"Ventana pasiva de settle activa ({elapsed_stopped:.0f}s/{settle_window_seconds:.0f}s): esperando normalización autónoma de VNish",
                soak_seconds_remaining=remaining,
            ),
            state,
        )

    # 4. Settle window expired, action required
    if state.recovery_attempts >= state.max_recovery_attempts:
        # Max soft attempts reached. If chain fault is physical, DO NOT retry and destroy PSU.
        if chain_fault_present:
            return (
                RecoveryDecision(
                    action=ACTION_HOLD_DEGRADED,
                    target_preset="1800",
                    clamp_top_preset=True,
                    trigger_restart=False,
                    reason="Inhibición defensiva: falla física en cadena persistente, evitando sobrecarga sobre APW12",
                ),
                state,
            )
        else:
            return (
                RecoveryDecision(
                    action=ACTION_HOLD_DEGRADED,
                    target_preset=None,
                    clamp_top_preset=False,
                    trigger_restart=False,
                    reason=f"Máximo de intentos de recuperación alcanzado ({state.recovery_attempts}/{state.max_recovery_attempts})",
                ),
                state,
            )

    # 5. Execute Soft-Landing Pre-Clamp and Restart
    new_state = SafeRecoveryState(
        miner_name=state.miner_name,
        stopped_since_ts=state.stopped_since_ts,
        recovery_attempts=state.recovery_attempts + 1,
        max_recovery_attempts=state.max_recovery_attempts,
        pre_clamp_preset=state.pre_clamp_preset,
        is_pre_clamped=True,
        original_preset=state.original_preset,
        clamped_ts=current_ts,
        staged_ramp_up_pending=True,
        staged_ramp_up_soak_start_ts=None,
    )
    return (
        RecoveryDecision(
            action=ACTION_PRE_CLAMP_AND_RESTART,
            target_preset=state.pre_clamp_preset,
            clamp_top_preset=True,
            trigger_restart=True,
            reason=f"Ventana pasiva agotada ({elapsed_stopped:.0f}s): desescalando a {state.pre_clamp_preset}W y despachando reinicio suave",
        ),
        new_state,
    )


def evaluate_headroom_chilling(
    target_power_w: float,
    max_power_w: float,
    current_temp_c: float,
    current_fan_duty: int,
    step_up_min_margin_c: float = 3.0,
    saturate_temp_c: float = 84.0,
    chilling_duration_seconds: float = DEFAULT_HEADROOM_CHILLING_DURATION,
) -> Tuple[bool, str]:
    """
    Evaluates whether Headroom Chilling should be requested by the Balancer.
    Returns (should_chill: bool, reason: str).
    Condition:
    - Target power has headroom to step up (e.g. 2500W < 2700W)
    - Blocked solely by thermal margin: (saturate_temp_c - current_temp_c) < step_up_min_margin_c
    - Temperature is not in emergency (> 83.0°C) but in opportunity band (80.0°C - 82.5°C)
    - Fan duty has unused capacity (< 98%)
    """
    if target_power_w >= max_power_w:
        return False, "Ya se encuentra en potencia máxima"

    margin_to_saturate = saturate_temp_c - current_temp_c
    is_thermally_blocked = (margin_to_saturate < step_up_min_margin_c)

    if not is_thermally_blocked:
        return False, "Margen térmico suficiente para escalamiento normal"

    # Must be in feasible cooling band (80.0 to 82.5°C)
    if current_temp_c > 82.8:
        return False, "Temperatura demasiado cercana al corte para enfriamiento de oportunidad"

    if current_temp_c < 79.5:
        return False, "Temperatura ya es baja"

    if current_fan_duty >= 98:
        return False, "Ventiladores ya están al máximo de disipación (>=98%)"

    return True, f"Enfriamiento de oportunidad (Headroom Chilling): T={current_temp_c:.1f}°C, duty={current_fan_duty}%, forzando 100% para desbloquear {max_power_w:.0f}W"
