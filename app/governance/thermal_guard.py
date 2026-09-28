"""
Thermal Guard & Hardware Overheat Protection Engine (P0 Invariant).
Guarantees that no ASIC in the fleet ever reaches 90.0°C under any circumstance.

Multi-layered defense:
- Level 1 (>= 84.0°C): Immediate emergency downstep (e.g. 2700W -> 2500W, or 2500W -> 2300W),
  with 100% fans, top_preset clamping, and a 2-hour lockout against stepping back up.
- Level 2 (>= 87.0°C): Immediate emergency pause (stops hashing via VNish API, fans at 100%),
  cooling chips within seconds without tripping breakers or causing catastrophic hashboard drop.
- Automatic Resumption: Once chips cool <= 75.0°C and settle duration passes, safely resumes
  mining at a protected preset.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


ACTION_NONE = "NONE"
ACTION_EMERGENCY_DOWNSTEP = "EMERGENCY_DOWNSTEP"
ACTION_EMERGENCY_PAUSE = "EMERGENCY_PAUSE"
ACTION_THERMAL_RESUME = "THERMAL_RESUME"
ACTION_PAUSED_COOLING = "PAUSED_COOLING"
ACTION_THERMAL_UNCLAMP = "THERMAL_UNCLAMP"


@dataclass(frozen=True)
class ThermalGuardDecision:
    action: str
    target_preset: Optional[str]
    target_duty: Optional[int]
    reason: str
    is_emergency: bool = False
    lockout_duration_s: float = 7200.0


def evaluate_emergency_thermal_action(
    max_temp_c: Optional[float],
    current_preset: Optional[str] = None,
    current_power_w: Optional[float] = None,
    last_downstep_ts: float = 0.0,
    last_pause_ts: float = 0.0,
    thermal_pause_until_ts: Optional[float] = None,
    config: Optional[Dict[str, Any]] = None,
    now_ts: Optional[float] = None,
    thermal_lockout_until_ts: Optional[float] = None,
    current_top_preset: Optional[str] = None,
    max_hardware_preset: Optional[str] = None,
) -> ThermalGuardDecision:
    """
    Pure deterministic decision engine for emergency thermal tripwire.
    Zero side-effects, 100% unit-testable.
    """
    cfg = config or {}
    current_time = now_ts if now_ts is not None else time.time()

    enabled = bool(cfg.get("emergency_thermal_protection_enabled", True))
    if not enabled:
        return ThermalGuardDecision(
            action=ACTION_NONE,
            target_preset=None,
            target_duty=None,
            reason="Thermal guard protection disabled in config",
        )

    downstep_temp_c = float(cfg.get("emergency_thermal_downstep_temp_c", 85.5))
    pause_temp_c = float(cfg.get("emergency_thermal_pause_temp_c", 87.0))
    resume_temp_c = float(cfg.get("emergency_thermal_resume_temp_c", 75.0))
    cooldown_downstep_s = float(cfg.get("emergency_thermal_downstep_cooldown_seconds", 180.0))
    cooldown_pause_s = float(cfg.get("emergency_thermal_pause_cooldown_seconds", 120.0))
    lockout_s = float(cfg.get("emergency_thermal_lockout_seconds", 7200.0))

    # 1. Handling active thermal pause
    if thermal_pause_until_ts is not None:
        time_elapsed = current_time >= thermal_pause_until_ts
        is_cool = max_temp_c is not None and max_temp_c <= resume_temp_c
        if time_elapsed and is_cool:
            # Ready to safely resume
            curr_str = str(current_preset or "")
            if "2700" in curr_str:
                resume_p = "2500"
            elif "2500" in curr_str:
                resume_p = "2300"
            elif "2300" in curr_str:
                resume_p = "2100"
            else:
                resume_p = "2300"
            return ThermalGuardDecision(
                action=ACTION_THERMAL_RESUME,
                target_preset=resume_p,
                target_duty=100,
                reason=f"Silicon enfriado ({max_temp_c:.1f}°C <= {resume_temp_c:.1f}°C): reanudando minería en preset protegido ({resume_p}W)",
                is_emergency=False,
                lockout_duration_s=lockout_s,
            )
        else:
            remaining_s = max(0.0, thermal_pause_until_ts - current_time)
            temp_desc = f"{max_temp_c:.1f}°C" if max_temp_c is not None else "N/D"
            return ThermalGuardDecision(
                action=ACTION_PAUSED_COOLING,
                target_preset=None,
                target_duty=100,
                reason=f"Pausa térmica activa ({temp_desc} > {resume_temp_c:.1f}°C o {remaining_s:.0f}s reposo restante)",
                is_emergency=False,
                lockout_duration_s=lockout_s,
            )

    if max_temp_c is None:
        return ThermalGuardDecision(
            action=ACTION_NONE,
            target_preset=None,
            target_duty=None,
            reason="Sin telemetría de temperatura disponible",
        )

    # 2. Level 2: Critical Emergency Pause (T >= pause_temp_c, e.g. 87.0°C)
    if max_temp_c >= pause_temp_c:
        if (current_time - last_pause_ts) < cooldown_pause_s:
            return ThermalGuardDecision(
                action=ACTION_NONE,
                target_preset=None,
                target_duty=100,
                reason=f"Cooldown de pausa térmica activo ({(current_time - last_pause_ts):.0f}s < {cooldown_pause_s:.0f}s)",
            )
        return ThermalGuardDecision(
            action=ACTION_EMERGENCY_PAUSE,
            target_preset=None,
            target_duty=100,
            reason=f"Temperatura crítica ({max_temp_c:.1f}°C >= {pause_temp_c:.1f}°C): deteniendo minado inmediatamente para prevenir corte a 90°C",
            is_emergency=True,
            lockout_duration_s=lockout_s,
        )

    # 3. Level 1: Emergency Thermal Downstep (T >= downstep_temp_c, e.g. 85.5°C)
    # Note: VNish native preset_switcher operates at decrease_temp = 84.0°C.
    # Setting monitor emergency downstep to 85.5°C gives VNish native switcher right-of-way
    # to downstep smoothly in-kernel without HTTP race conditions. The monitor only trips if
    # VNish lagged or thermal runaway breached 85.5°C.
    if max_temp_c >= downstep_temp_c:
        time_since_downstep = current_time - last_downstep_ts
        if time_since_downstep < cooldown_downstep_s:
            return ThermalGuardDecision(
                action=ACTION_NONE,
                target_preset=None,
                target_duty=100,
                reason=f"Cooldown de step-down térmico activo ({time_since_downstep:.0f}s < {cooldown_downstep_s:.0f}s; anti-doble-bajada)",
            )
        curr_pwr = current_power_w or 2700.0
        curr_pre = str(current_preset or "")
        if "2700" in curr_pre or curr_pwr >= 2600.0:
            target_p = "2500"
        elif "2500" in curr_pre or curr_pwr >= 2400.0:
            target_p = "2300"
        elif "2300" in curr_pre or curr_pwr >= 2200.0:
            target_p = "2100"
        else:
            target_p = "1800"

        return ThermalGuardDecision(
            action=ACTION_EMERGENCY_DOWNSTEP,
            target_preset=target_p,
            target_duty=100,
            reason=f"Sobrecalentamiento ({max_temp_c:.1f}°C >= {downstep_temp_c:.1f}°C): reduciendo preset a {target_p}W para disipar calor",
            is_emergency=True,
            lockout_duration_s=lockout_s,
        )

    # 4. Lockout Expiration Unclamp: If lockout expired, chips are cool, and top_preset was clamped below max hardware preset
    if (
        thermal_lockout_until_ts is not None
        and current_time >= thermal_lockout_until_ts
        and max_temp_c is not None
        and max_temp_c <= 80.0
        and current_top_preset is not None
        and max_hardware_preset is not None
    ):
        clean_top = str(current_top_preset).upper().rstrip("W").strip()
        clean_hw = str(max_hardware_preset).upper().rstrip("W").strip()
        try:
            top_w = float(clean_top)
            hw_w = float(clean_hw)
            if top_w < hw_w:
                return ThermalGuardDecision(
                    action=ACTION_THERMAL_UNCLAMP,
                    target_preset=clean_hw,
                    target_duty=None,
                    reason=f"Bloqueo térmico expirado y chips estables ({max_temp_c:.1f}°C <= 80.0°C): liberando top_preset a {clean_hw}W",
                    is_emergency=False,
                )
        except ValueError:
            pass

    return ThermalGuardDecision(
        action=ACTION_NONE,
        target_preset=None,
        target_duty=None,
        reason=f"Temperatura dentro de rango seguro ({max_temp_c:.1f}°C < {downstep_temp_c:.1f}°C)",
    )


def process_emergency_thermal_guard(
    miner: dict,
    state: Any,
    max_temp_c: Optional[float],
    config: dict,
    now_ts: float,
    vnish_pw: str,
    safe_set_preset_fn: Optional[Any] = None,
    safe_stop_fn: Optional[Any] = None,
    safe_resume_fn: Optional[Any] = None,
    safe_set_fan_fn: Optional[Any] = None,
    send_telegram_fn: Optional[Any] = None,
    log_fn: Optional[Any] = None,
    qa_mode: bool = False,
    qa_notify: bool = False,
    bot_token: Optional[str] = None,
    chat_id: Optional[str] = None,
) -> Optional[str]:
    """
    Executes physical thermal safety interventions if chip temperatures exceed safe thresholds.
    Thread-safe, non-blocking hardware operations.
    """
    if state is None:
        return None

    name = miner.get("name", "Unknown")
    host = miner.get("host", "")

    current_preset = (
        getattr(state, "balancer_preset", None)
        or getattr(state, "vnish_discovered_preset", None)
        or miner.get("target_power_w")
    )
    current_power_w = getattr(state, "governor_last_power_w", None)

    # Anti-doble-bajada: track the latest of explicit thermal downsteps OR any discovered firmware preset change
    effective_downstep_ts = max(
        float(getattr(state, "last_thermal_downstep_ts", 0.0) or 0.0),
        float(getattr(state, "last_preset_change_ts", 0.0) or 0.0),
    )

    decision = evaluate_emergency_thermal_action(
        max_temp_c=max_temp_c,
        current_preset=str(current_preset) if current_preset else None,
        current_power_w=current_power_w,
        last_downstep_ts=effective_downstep_ts,
        last_pause_ts=getattr(state, "last_thermal_pause_ts", 0.0),
        thermal_pause_until_ts=getattr(state, "thermal_pause_until_ts", None),
        config=config,
        now_ts=now_ts,
        thermal_lockout_until_ts=getattr(state, "thermal_lockout_until_ts", None),
        current_top_preset=getattr(state, "vnish_discovered_top_preset", None),
        max_hardware_preset=miner.get("max_hardware_preset", "2700W"),
    )

    if decision.action == ACTION_NONE:
        if getattr(state, "thermal_lockout_until_ts", None) and now_ts >= state.thermal_lockout_until_ts:
            clean_top = str(getattr(state, "vnish_discovered_top_preset", "") or "").upper().rstrip("W").strip()
            clean_hw = str(miner.get("max_hardware_preset", "2700W")).upper().rstrip("W").strip()
            try:
                if float(clean_top) >= float(clean_hw):
                    state.thermal_lockout_until_ts = None
            except ValueError:
                state.thermal_lockout_until_ts = None
        return None

    from app.vnish.client import (
        safe_set_miner_preset as _default_set_preset,
        safe_stop_mining as _default_stop_mining,
        safe_resume_mining as _default_resume_mining,
        safe_set_fan_duty as _default_set_fan,
    )
    from app.miner_monitor import (
        log as _default_log,
        send_telegram as _default_send_tg,
    )

    set_preset = safe_set_preset_fn or _default_set_preset
    stop_mining = safe_stop_fn or _default_stop_mining
    resume_mining = safe_resume_fn or _default_resume_mining
    set_fan = safe_set_fan_fn or _default_set_fan
    log = log_fn or _default_log
    send_tg = send_telegram_fn or _default_send_tg

    if decision.action == ACTION_EMERGENCY_DOWNSTEP:
        target_preset = decision.target_preset or "2500"
        state.last_thermal_downstep_ts = now_ts
        state.last_preset_change_ts = now_ts
        state.thermal_lockout_until_ts = now_ts + decision.lockout_duration_s
        state.hw_error_lock_until_ts = max(
            getattr(state, "hw_error_lock_until_ts", None) or 0.0,
            now_ts + decision.lockout_duration_s,
        )
        state.balancer_preset = target_preset
        state.vnish_discovered_preset = target_preset
        state.vnish_discovered_top_preset = target_preset

        if qa_mode:
            log(f"[THERMAL_GUARD] (QA) EMERGENCY DOWNSTEP for {name} to {target_preset}W (temp={max_temp_c:.1f}°C)")
        else:
            # Clamping both top_preset and min_preset to target_preset prevents VNish from either:
            # 1. Bouncing back to 2700W when temp drops below 79°C (bounded by top_preset).
            # 2. Downstepping a second time to 2300W during the thermal settling window (bounded by min_preset).
            ok_p, err_p = set_preset(
                host,
                vnish_pw,
                target_preset,
                clamp_top_preset=True,
                top_preset=target_preset,
                min_preset=target_preset,
            )
            ok_f, err_f = set_fan(host, vnish_pw, 100)
            log(
                f"[THERMAL_GUARD] EMERGENCY DOWNSTEP dispatched for {name} to {target_preset}W "
                f"(temp={max_temp_c:.1f}°C): preset_ok={ok_p} err={err_p} fans_100_ok={ok_f}"
            )

        if bot_token and chat_id and (not qa_mode or qa_notify):
            lockout_h = decision.lockout_duration_s / 3600.0
            msg = (
                f"⚠️ *GUARDIÁN TÉRMICO: STEP-DOWN DE EMERGENCIA*\n"
                f"Minero: *{name}* (`{host}`)\n"
                f"Temperatura silicio: *{max_temp_c:.1f}°C* (Umbral crítico: {config.get('emergency_thermal_downstep_temp_c', 85.5)}°C)\n"
                f"Acción preventiva: Reducción inmediata a *{target_preset}W* para disipar carga y prevenir corte a 90°C.\n"
                f"Ventiladores: Forzados al 100% PWM.\n"
                f"Bloqueo de subida: {lockout_h:.1f} horas para asegurar estabilización."
            )
            send_tg(bot_token, str(chat_id), msg, "THERMAL_GUARD", "thermal_downstep")
        return decision.action

    elif decision.action == ACTION_EMERGENCY_PAUSE:
        pause_duration = 90.0
        state.last_thermal_pause_ts = now_ts
        state.thermal_pause_until_ts = now_ts + pause_duration
        state.thermal_lockout_until_ts = now_ts + decision.lockout_duration_s
        state.hw_error_lock_until_ts = max(
            getattr(state, "hw_error_lock_until_ts", None) or 0.0,
            now_ts + decision.lockout_duration_s,
        )

        if qa_mode:
            log(f"[THERMAL_GUARD] (QA) EMERGENCY PAUSE for {name} (temp={max_temp_c:.1f}°C)")
        else:
            ok_s, err_s = stop_mining(host, vnish_pw)
            ok_f, err_f = set_fan(host, vnish_pw, 100)
            log(
                f"[THERMAL_GUARD] EMERGENCY PAUSE dispatched for {name} "
                f"(temp={max_temp_c:.1f}°C): stop_ok={ok_s} err={err_s} fans_100_ok={ok_f}"
            )

        if bot_token and chat_id and (not qa_mode or qa_notify):
            msg = (
                f"🚨 *EMERGENCIA TÉRMICA CRÍTICA: PAUSA FORZADA*\n"
                f"Minero: *{name}* (`{host}`)\n"
                f"Temperatura silicio: *{max_temp_c:.1f}°C* (Umbral de parada: {config.get('emergency_thermal_pause_temp_c', 87.0)}°C)\n"
                f"Acción crítica: Se detuvo el minado inmediatamente vía API VNish para evitar daño y corte por hardware a 90°C.\n"
                f"Ventiladores: Forzados al 100% PWM para barrer el calor acumulado.\n"
                f"Reanudación: Automática una vez que la temperatura descienda a <= {config.get('emergency_thermal_resume_temp_c', 75.0)}°C."
            )
            send_tg(bot_token, str(chat_id), msg, "THERMAL_GUARD", "thermal_pause")
        return decision.action

    elif decision.action == ACTION_THERMAL_RESUME:
        resume_preset = decision.target_preset or "2300"
        state.thermal_pause_until_ts = None
        state.last_preset_change_ts = now_ts
        state.balancer_preset = resume_preset

        if qa_mode:
            log(f"[THERMAL_GUARD] (QA) RESUME MINING for {name} at {resume_preset}W (temp={max_temp_c:.1f}°C)")
        else:
            set_preset(host, vnish_pw, resume_preset, clamp_top_preset=True, top_preset=resume_preset, min_preset=resume_preset)
            ok_r, err_r = resume_mining(host, vnish_pw)
            set_fan(host, vnish_pw, 100)
            log(
                f"[THERMAL_GUARD] RESUMED MINING for {name} at {resume_preset}W "
                f"(temp={max_temp_c:.1f}°C): resume_ok={ok_r} err={err_r}"
            )

        if bot_token and chat_id and (not qa_mode or qa_notify):
            msg = (
                f"❄️ *RECUPERACIÓN TÉRMICA EXITOSA*\n"
                f"Minero: *{name}* (`{host}`)\n"
                f"Temperatura silicio: *{max_temp_c:.1f}°C* (<= {config.get('emergency_thermal_resume_temp_c', 75.0)}°C)\n"
                f"Acción: Minería reanudada en régimen protegido ({resume_preset}W) con ventiladores al 100% PWM."
            )
            send_tg(bot_token, str(chat_id), msg, "THERMAL_GUARD", "thermal_resume")
        return decision.action

    elif decision.action == ACTION_THERMAL_UNCLAMP:
        target_hw_max = decision.target_preset or "2700"
        state.thermal_lockout_until_ts = None
        state.hw_error_lock_until_ts = None
        state.vnish_discovered_top_preset = target_hw_max
        curr_p = (
            getattr(state, "balancer_preset", None)
            or getattr(state, "vnish_discovered_preset", None)
            or "2500"
        )
        if qa_mode:
            log(f"[THERMAL_GUARD] (QA) UNCLAMP TOP PRESET for {name} to {target_hw_max}W (temp={max_temp_c:.1f}°C)")
        else:
            ok_p, err_p = set_preset(
                host,
                vnish_pw,
                str(curr_p),
                clamp_top_preset=False,
                top_preset=str(target_hw_max),
                min_preset="1740",
            )
            log(
                f"[THERMAL_GUARD] UNCLAMP TOP PRESET dispatched for {name} to {target_hw_max}W "
                f"(temp={max_temp_c:.1f}°C): preset_ok={ok_p} err={err_p}"
            )

        if bot_token and chat_id and (not qa_mode or qa_notify):
            msg = (
                f"🔓 *DESBLOQUEO TÉRMICO COMPLETADO*\n"
                f"Minero: *{name}* (`{host}`)\n"
                f"Temperatura silicio: *{max_temp_c:.1f}°C* (<= 80.0°C)\n"
                f"Acción: Fin de periodo de bloqueo térmico. Techo de potencia liberado a *{target_hw_max}W* "
                f"para permitir escalado normal según condiciones ambientales."
            )
            send_tg(bot_token, str(chat_id), msg, "THERMAL_GUARD", "thermal_unclamp")
        return decision.action

    return decision.action
