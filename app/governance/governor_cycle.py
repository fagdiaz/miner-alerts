"""
app/governance/governor_cycle.py
Spec 085 — Extracción del Orquestador de Gobernanza (PROP-021)

Módulo de ciclo Fan Governor extraído de miner_monitor.py.
Contiene execute_governor_cycle() y refresh_vnish_overclock_settings()
con firmas idénticas a las originales para retrocompatibilidad total.

NO importa de miner_monitor.py (evita importaciones circulares).
Lee/escribe globals de gobernanza vía app.governance._orchestrator_state.
"""
from __future__ import annotations

import concurrent.futures
import logging
import re
import threading
import time
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from app.governance._orchestrator_state import (
    get_governor_enabled,
    get_intervention_gov,
    get_last_vnish_sync_ts,
    set_last_vnish_sync_ts,
)
from app.governance.fan_governor import (
    ACTION_EMERGENCY_SPIKE,
    ACTION_FAILSAFE_FAULT,
    ACTION_HOLD_DWELL,
    ACTION_HOLD_TARGET,
    ACTION_RECOVERY_MAX_COOLING,
    GovernorConfig,
    compute_governor_step,
)
from app.governance.governance_context import MinerGovernanceContext
from app.vnish.client import (
    safe_get_overclock_settings,
    safe_set_fan_duty,
    safe_set_miner_preset,
)

if TYPE_CHECKING:
    from app.miner_monitor import MinerState

# Fallback logger — usado solo si el caller no pasa log_fn
_logger = logging.getLogger("miner_alerts.governor_cycle")


def _make_log(log_fn: Optional[Callable[[str], None]]) -> Callable[[str], None]:
    """Retorna log_fn si se proporcionó, o un wrapper sobre el logger del módulo."""
    if log_fn is not None:
        return log_fn
    return lambda msg: _logger.info(msg)


# ---------------------------------------------------------------------------
# T014: Fan Governor execution cycle (Spec 039)
# ---------------------------------------------------------------------------


def execute_governor_cycle(
    miners: list,
    states: Dict[str, "MinerState"],
    state_lock: threading.Lock,
    config: dict,
    now_ts: float,
    qa_mode: bool = False,
    log_fn: Optional[Callable[[str], None]] = None,
) -> list:
    """Execute one fan governor tick: evaluate decisions for all miners, dispatch
    hardware writes in parallel via ThreadPoolExecutor (R2 constraint), and update
    per-miner state fields under state_lock.

    This function is defensive: any exception in the entire cycle is caught and
    logged without propagating to the authoritative 4028 tick.

    Args:
        miners: List of miner config dicts.
        states: Dict mapping state_key -> MinerState.
        state_lock: Threading lock protecting `states`.
        config: Full application config dict.
        now_ts: Current epoch timestamp (float).
        qa_mode: If True, governor is skipped (QA safety gate).
        log_fn: Optional logging callable (signature: (str) -> None).
                If omitted, falls back to module logger.
    """
    log = _make_log(log_fn)

    gov_enabled_cfg = bool(config.get("fan_governor_enabled", False))
    _rt_gov = get_governor_enabled()
    gov_enabled = (
        _rt_gov
        if _rt_gov is not None
        else gov_enabled_cfg
    )
    if not gov_enabled or qa_mode:
        return []

    # Spec 057: Check intervention governance for Fan Governor
    from app.governance.intervention_policy import ACTION_FAN_GOVERNOR, should_allow_intervention
    gov_obj = get_intervention_gov()
    if gov_obj is not None and not should_allow_intervention(ACTION_FAN_GOVERNOR, gov_obj, time.time())[0]:
        return []

    dry_run = bool(config.get("fan_governor_dry_run", True))
    vnish_pw = str(config.get("vnish_api_password", "admin"))
    gov_cfg = GovernorConfig(
        enabled=True,
        dry_run=dry_run,
        target_temp_c=float(config.get("fan_governor_target_temp_c", 79.0)),
        deadband_low_c=float(config.get("fan_governor_deadband_low_c", 76.0)),
        deadband_high_c=float(config.get("fan_governor_deadband_high_c", 80.5)),
        emergency_spike_temp_c=float(config.get("fan_governor_emergency_temp_c", 82.0)),
        min_fan_duty_percent=int(config.get("fan_governor_min_duty_pct", 30)),
        max_fan_duty_percent=100,
        step_down_percent=int(config.get("fan_governor_step_down_pct", 2)),
        step_up_percent=int(config.get("fan_governor_step_up_pct", 3)),
        dwell_seconds=int(config.get("fan_governor_dwell_seconds", 90)),
        adaptive_dwell_seconds=int(config.get("fan_governor_adaptive_dwell_seconds", 120)),
        consecutive_holds_threshold=int(config.get("fan_governor_holds_threshold", 3)),
        request_timeout_seconds=float(config.get("fan_governor_request_timeout", 2.5)),
        fleet_timeout_seconds=float(config.get("fan_governor_fleet_timeout", 5.0)),
        max_consecutive_failures=int(config.get("fan_governor_max_failures", 3)),
        power_margin_w=float(config.get("fan_governor_power_margin_w", 120.0)),
        # Spec 063: Ambient-Aware Thermal PID (GOV-02)
        seasonal_enabled=bool(config.get("fan_governor_seasonal_enabled", True)),
        winter_ambient_threshold_c=float(config.get("fan_governor_winter_ambient_threshold_c", 18.0)),
        summer_ambient_threshold_c=float(config.get("fan_governor_summer_ambient_threshold_c", 28.0)),
        winter_target_temp_c=float(config.get("fan_governor_winter_target_temp_c", 76.0)),
        winter_min_duty_percent=int(config.get("fan_governor_winter_min_duty_pct", 45)),
        summer_target_temp_c=float(config.get("fan_governor_summer_target_temp_c", 80.0)),
        summer_min_duty_percent=int(config.get("fan_governor_summer_min_duty_pct", 65)),
        summer_step_up_percent=int(config.get("fan_governor_summer_step_up_pct", 5)),
        power_floor_2700w=int(config.get("fan_governor_power_floor_2700w", 100)),
        power_floor_2500w=int(config.get("fan_governor_power_floor_2500w", 95)),
        power_floor_2300w=int(config.get("fan_governor_power_floor_2300w", 75)),
        power_floor_1800w=int(config.get("fan_governor_power_floor_1800w", 50)),
        recovery_max_cooling_timeout_seconds=float(config.get("fan_governor_recovery_max_cooling_timeout_seconds", 0.0)),
    )

    # Build (miner, state, decision) triples
    miner_decisions: list = []
    with state_lock:
        # Spec 063: Ambient temperature aggregation across electrical groups and fleet
        group_inlet_temps: Dict[str, List[float]] = {}
        fleet_inlet_temps: List[float] = []
        for m in miners:
            m_name = m.get("name", "")
            m_host = m.get("host", "")
            m_port = m.get("port", 4028)
            st = states.get(f"{m_name}|{m_host}:{m_port}")
            inlet = getattr(st, "inlet_temp_c", None) if st else None
            if inlet is not None and -10.0 <= inlet <= 60.0:
                grp = m.get("electrical_group") or m.get("group")
                if grp:
                    group_inlet_temps.setdefault(str(grp), []).append(inlet)
                fleet_inlet_temps.append(inlet)

        for miner in miners:
            name = miner.get("name", "")
            host = miner.get("host", "")
            port = miner.get("port", 4028)
            state_key = f"{name}|{host}:{port}"
            state = states.get(state_key)
            if state is None:
                continue
            if getattr(state, "is_shutdown_maintenance", False):
                continue
            seconds_since = now_ts - (state.governor_last_change_ts or 0.0)

            # Directiva Fan Governor: Si un minero NO está hasheando a máxima potencia (2700W),
            # los ventiladores DEBEN mantenerse al 100% PWM (ACTION_RECOVERY_MAX_COOLING).
            # Cuando alcanza los 2700W, modula en lazo cerrado para normalizar a 82.0°C.
            # Cada minero se evalúa de forma estrictamente independiente.
            # Por tanto, target_pwr representa el techo nominal máximo del minero (2700W),
            # y nunca debe degradarse por presets intermedios o bajados (ej. 2500W).
            # Prioridad de resolución independiente:
            # 1. target_power_w configurado por minero (ej. 2700.0)
            # 2. max_hardware_preset configurado por minero (ej. "2700W")
            # 3. max_preset configurado por minero (ej. "2700W")
            # 4. vnish_discovered_top_preset reportado por la API Vnish (ej. "2700W")
            # 5. fan_governor_target_power_w global (default 2700.0)
            def _parse_preset_w(val: Any) -> Optional[float]:
                if val is None:
                    return None
                s = str(val).upper().replace("W", "").strip()
                try:
                    p = float(s)
                    return p if p > 0 else None
                except ValueError:
                    return None

            target_pwr = (
                miner.get("target_power_w")
                or _parse_preset_w(miner.get("max_hardware_preset"))
                or _parse_preset_w(miner.get("max_preset"))
                or _parse_preset_w(getattr(state, "vnish_discovered_top_preset", None))
                or float(config.get("fan_governor_target_power_w", 2700.0))
            )

            # Per-miner configuration overrides (if present in miner config dict)
            miner_gov_cfg = gov_cfg
            if any(k in miner for k in ("target_temp_c", "deadband_low_c", "deadband_high_c", "emergency_temp_c", "min_duty_pct", "power_margin_w")):
                miner_gov_cfg = GovernorConfig(
                    enabled=gov_cfg.enabled,
                    dry_run=gov_cfg.dry_run,
                    target_temp_c=float(miner.get("target_temp_c", gov_cfg.target_temp_c)),
                    deadband_low_c=float(miner.get("deadband_low_c", gov_cfg.deadband_low_c)),
                    deadband_high_c=float(miner.get("deadband_high_c", gov_cfg.deadband_high_c)),
                    emergency_spike_temp_c=float(miner.get("emergency_temp_c", gov_cfg.emergency_spike_temp_c)),
                    min_fan_duty_percent=int(miner.get("min_duty_pct", gov_cfg.min_fan_duty_percent)),
                    max_fan_duty_percent=gov_cfg.max_fan_duty_percent,
                    step_down_percent=gov_cfg.step_down_percent,
                    step_up_percent=gov_cfg.step_up_percent,
                    dwell_seconds=gov_cfg.dwell_seconds,
                    adaptive_dwell_seconds=gov_cfg.adaptive_dwell_seconds,
                    consecutive_holds_threshold=gov_cfg.consecutive_holds_threshold,
                    request_timeout_seconds=gov_cfg.request_timeout_seconds,
                    fleet_timeout_seconds=gov_cfg.fleet_timeout_seconds,
                    max_consecutive_failures=gov_cfg.max_consecutive_failures,
                    power_margin_w=float(miner.get("power_margin_w", gov_cfg.power_margin_w)),
                    seasonal_enabled=gov_cfg.seasonal_enabled,
                    winter_ambient_threshold_c=gov_cfg.winter_ambient_threshold_c,
                    summer_ambient_threshold_c=gov_cfg.summer_ambient_threshold_c,
                    winter_target_temp_c=gov_cfg.winter_target_temp_c,
                    winter_min_duty_percent=gov_cfg.winter_min_duty_percent,
                    summer_target_temp_c=gov_cfg.summer_target_temp_c,
                    summer_min_duty_percent=gov_cfg.summer_min_duty_percent,
                    summer_step_up_percent=gov_cfg.summer_step_up_percent,
                    power_floor_2700w=gov_cfg.power_floor_2700w,
                    power_floor_2500w=gov_cfg.power_floor_2500w,
                    power_floor_2300w=gov_cfg.power_floor_2300w,
                    power_floor_1800w=gov_cfg.power_floor_1800w,
                    recovery_max_cooling_timeout_seconds=gov_cfg.recovery_max_cooling_timeout_seconds,
                )

            # Spec 044 C3: If silent mode active for this miner, constrain the Governor to
            # operate within the acoustic ceiling. EMERGENCY_SPIKE overrides max_fan_duty_percent
            # by its own rule (goes to 100% regardless), so this is safe.
            if getattr(state, "silent_mode_active", False):
                _sm_min = int(config.get("silent_mode_min_duty_pct", 30))
                _sm_max = int(getattr(state, "silent_mode_target_max_duty", 50))
                _eff_min = min(_sm_min, _sm_max)
                _eff_max = max(_sm_min, _sm_max)
                miner_gov_cfg = GovernorConfig(
                    enabled=miner_gov_cfg.enabled,
                    dry_run=miner_gov_cfg.dry_run,
                    target_temp_c=miner_gov_cfg.target_temp_c,
                    deadband_low_c=miner_gov_cfg.deadband_low_c,
                    deadband_high_c=miner_gov_cfg.deadband_high_c,
                    emergency_spike_temp_c=miner_gov_cfg.emergency_spike_temp_c,
                    min_fan_duty_percent=_eff_min,
                    max_fan_duty_percent=_eff_max,  # Acoustic ceiling
                    step_down_percent=miner_gov_cfg.step_down_percent,
                    step_up_percent=miner_gov_cfg.step_up_percent,
                    dwell_seconds=miner_gov_cfg.dwell_seconds,
                    adaptive_dwell_seconds=miner_gov_cfg.adaptive_dwell_seconds,
                    consecutive_holds_threshold=miner_gov_cfg.consecutive_holds_threshold,
                    request_timeout_seconds=miner_gov_cfg.request_timeout_seconds,
                    fleet_timeout_seconds=miner_gov_cfg.fleet_timeout_seconds,
                    max_consecutive_failures=miner_gov_cfg.max_consecutive_failures,
                    power_margin_w=miner_gov_cfg.power_margin_w,
                    seasonal_enabled=miner_gov_cfg.seasonal_enabled,
                    winter_ambient_threshold_c=miner_gov_cfg.winter_ambient_threshold_c,
                    summer_ambient_threshold_c=miner_gov_cfg.summer_ambient_threshold_c,
                    winter_target_temp_c=miner_gov_cfg.winter_target_temp_c,
                    winter_min_duty_percent=miner_gov_cfg.winter_min_duty_percent,
                    summer_target_temp_c=miner_gov_cfg.summer_target_temp_c,
                    summer_min_duty_percent=miner_gov_cfg.summer_min_duty_percent,
                    summer_step_up_percent=miner_gov_cfg.summer_step_up_percent,
                    power_floor_2700w=miner_gov_cfg.power_floor_2700w,
                    power_floor_2500w=miner_gov_cfg.power_floor_2500w,
                    power_floor_2300w=miner_gov_cfg.power_floor_2300w,
                    power_floor_1800w=miner_gov_cfg.power_floor_1800w,
                    recovery_max_cooling_timeout_seconds=miner_gov_cfg.recovery_max_cooling_timeout_seconds,
                )

            # Spec 063: Determine effective ambient temperature for this miner
            miner_grp = miner.get("electrical_group") or miner.get("group")
            amb_temp: Optional[float] = None
            if miner_grp and str(miner_grp) in group_inlet_temps and group_inlet_temps[str(miner_grp)]:
                amb_temp = round(sum(group_inlet_temps[str(miner_grp)]) / len(group_inlet_temps[str(miner_grp)]), 2)
            else:
                own_inlet = getattr(state, "inlet_temp_c", None)
                if own_inlet is not None and -10.0 <= own_inlet <= 60.0:
                    amb_temp = own_inlet
                elif fleet_inlet_temps:
                    amb_temp = round(sum(fleet_inlet_temps) / len(fleet_inlet_temps), 2)

            gov_target_pwr = None if getattr(state, "silent_mode_active", False) else target_pwr
            gov_curr_pwr = None if getattr(state, "silent_mode_active", False) else getattr(state, "governor_last_power_w", None)
            # Spec 081 / Fricción F-02: Si el preset está pendiente de restart (configurado pero no aplicado),
            # usar la potencia real en ejecución como target para el Fan Governor.
            # Evita RECOVERY_MAX_COOLING permanente cuando restart_required=True.
            if getattr(state, "vnish_restart_required", False) and gov_curr_pwr is not None and gov_curr_pwr >= 500.0:
                gov_target_pwr = gov_curr_pwr
            _autotune_grace_s = float(config.get("autotune_grace_period_seconds", 900.0))
            _elapsed = getattr(state, "last_elapsed", None)
            miner_is_warming_up = (
                (_elapsed is not None and 0 <= _elapsed < _autotune_grace_s)
                or (getattr(state, "reboot_pending_until", 0.0) > now_ts)
            )
            boost_cooling_is_active = bool(
                getattr(state, "boost_cooling_active", False)
                and (getattr(state, "boost_cooling_expires_ts", 0.0) > now_ts)
            )
            if getattr(state, "boost_cooling_active", False) and not boost_cooling_is_active:
                with state_lock:
                    state.boost_cooling_active = False
                    state.boost_cooling_expires_ts = None

            rec_since = getattr(state, "governor_recovery_since_ts", None)
            if (
                rec_since is None
                and getattr(state, "governor_last_action", "") == ACTION_RECOVERY_MAX_COOLING
                and getattr(state, "governor_last_change_ts", 0.0) > 0
            ):
                rec_since = state.governor_last_change_ts
                with state_lock:
                    state.governor_recovery_since_ts = rec_since

            rec_duration_s = max(0.0, now_ts - rec_since) if rec_since is not None else 0.0

            # Spec 082 / PROP-018: Construir contexto de gobernanza centralizado
            # gov_ctx centraliza la lógica de restart_required, is_warming_up, fga_cohort, etc.
            # Reemplaza la lógica inline dispersa por una fuente de verdad única por ciclo.
            gov_ctx = MinerGovernanceContext.from_state(state, now_ts, miner)

            decision = compute_governor_step(
                max_temp_c=state.governor_last_temp_c,
                current_duty=state.governor_duty,
                seconds_since_last_change=seconds_since,
                consecutive_holds=state.governor_holds,
                consecutive_failures=state.governor_failures,
                config=miner_gov_cfg,
                current_power_w=gov_curr_pwr,
                target_power_w=gov_target_pwr,
                ambient_temp_c=amb_temp,
                is_warming_up=miner_is_warming_up,
                boost_cooling=boost_cooling_is_active,
                recovery_cooling_seconds=rec_duration_s,
                ctx=gov_ctx,
            )
            miner_decisions.append((miner, state_key, decision, target_pwr, miner_gov_cfg))

    if not miner_decisions:
        return []

    # Dispatch parallel hardware writes for miners that need action (R2)
    write_results: Dict[str, tuple] = {}  # state_key -> (success, error)
    writers = [
        (miner, sk, dec)
        for miner, sk, dec, _tgt, _cfg in miner_decisions
        if dec.requires_write and not dry_run
    ]
    if writers:
        executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=min(4, len(writers))
        )
        try:
            future_to_key = {
                executor.submit(
                    safe_set_fan_duty,
                    miner.get("host", ""),
                    vnish_pw,
                    dec.target_duty,
                    gov_cfg.request_timeout_seconds,
                ): sk
                for miner, sk, dec in writers
            }
            deadline = time.monotonic() + gov_cfg.fleet_timeout_seconds
            for future in concurrent.futures.as_completed(
                future_to_key.keys(),
                timeout=gov_cfg.fleet_timeout_seconds,
            ):
                sk = future_to_key[future]
                try:
                    ok, err = future.result(timeout=max(0.1, deadline - time.monotonic()))
                    write_results[sk] = (ok, err)
                except Exception as exc:
                    write_results[sk] = (False, str(exc))
        except concurrent.futures.TimeoutError:
            # Fleet timeout expired — record remaining futures as timed out
            for future, sk in future_to_key.items():
                if sk not in write_results:
                    write_results[sk] = (False, "fleet_timeout")
        finally:
            # Abandon (don't wait for) any in-flight threads beyond the timeout
            executor.shutdown(wait=False)

    # Update per-miner state under state_lock — also handles C4 Thermal Guard
    thermal_guard_events: list = []  # (miner_name, temp_c, action) for caller to notify Telegram
    with state_lock:
        for miner, sk, dec, tgt_pwr, miner_gov_cfg in miner_decisions:
            state = states.get(sk)
            if state is None:
                continue
            name_display = miner.get("name", sk)
            action = dec.action
            new_duty = dec.target_duty

            # Determine if write succeeded
            write_ok = True
            write_err = None
            if dec.requires_write and not dry_run:
                write_ok, write_err = write_results.get(sk, (False, "no_result"))

            # Update failure counter
            if dec.requires_write and not dry_run:
                if write_ok:
                    state.governor_failures = 0
                else:
                    state.governor_failures = state.governor_failures + 1
            else:
                if write_ok:
                    state.governor_failures = 0

            # Update duty and holds
            if action == ACTION_HOLD_TARGET:
                state.governor_holds = state.governor_holds + 1
            elif action != ACTION_HOLD_DWELL:
                state.governor_holds = 0

            if dec.requires_write and (dry_run or write_ok):
                state.governor_duty = new_duty
                state.governor_last_change_ts = now_ts

            state.governor_last_action = action

            # Update recovery cooling episode tracker
            pwr_val = getattr(state, "governor_last_power_w", None)
            is_under_power_target = (
                pwr_val is not None
                and tgt_pwr is not None
                and tgt_pwr > 0
                and pwr_val >= 500.0
                and pwr_val < (tgt_pwr - miner_gov_cfg.power_margin_w)
            )
            if is_under_power_target:
                if getattr(state, "governor_recovery_since_ts", None) is None:
                    state.governor_recovery_since_ts = now_ts
            else:
                state.governor_recovery_since_ts = None

            # Spec 044 C4: Thermal Guard — atomically cancel silent_mode on emergency.
            # EMERGENCY_SPIKE (T >= emergency_spike_temp_c) or FAILSAFE_FAULT (3 HTTP failures)
            # must override the acoustic ceiling immediately and clear state.json.
            if action in (ACTION_EMERGENCY_SPIKE, ACTION_FAILSAFE_FAULT):
                if getattr(state, "silent_mode_active", False):
                    prev_max = getattr(state, "silent_mode_target_max_duty", 50)
                    state.silent_mode_active = False
                    state.silent_mode_revert_ts = None
                    temp_c = state.governor_last_temp_c
                    thermal_guard_events.append((name_display, temp_c, action, prev_max))
                    log(
                        f"[THERMAL_GUARD] Silent mode CANCELLED for miner={name_display} "
                        f"action={action} temp={temp_c}°C prev_max={prev_max}%"
                    )

            # Structured log
            dr_tag = " DRY" if dry_run else ""
            duty_tag = f"duty={state.governor_duty}%" if state.governor_duty is not None else "duty=?"
            err_tag = f" err={write_err}" if write_err else ""
            pwr_val = getattr(state, "governor_last_power_w", None)
            if pwr_val is not None and tgt_pwr is not None:
                pwr_tag = f" pwr={pwr_val:.0f}/{tgt_pwr:.0f}W"
            elif pwr_val is not None:
                pwr_tag = f" pwr={pwr_val:.0f}W"
            else:
                pwr_tag = ""
            season_tag = f" season={dec.seasonal_mode}" if getattr(dec, "seasonal_mode", None) else ""
            log(
                f"[GOV{dr_tag}] miner={name_display} action={action} "
                f"{duty_tag} target={new_duty}% "
                f"holds={state.governor_holds} fails={state.governor_failures}{pwr_tag}{season_tag}{err_tag}"
            )

    return thermal_guard_events


# ---------------------------------------------------------------------------
# Dynamic Vnish Overclock & Autoswitch State Discovery
# ---------------------------------------------------------------------------


def refresh_vnish_overclock_settings(
    miners: list,
    states: Dict[str, "MinerState"],
    state_lock: threading.Lock,
    vnish_pw: str,
    timeout: float = 2.5,
    force: bool = False,
    now_ts: Optional[float] = None,
    log_fn: Optional[Callable[[str], None]] = None,
) -> Dict[str, dict]:
    """
    Query Vnish REST API for all miners in parallel to discover active overclock
    preset and preset_switcher configuration (top_preset).
    Updates state.vnish_discovered_* fields dynamically.
    Guarantees non-blocking execution with fleet timeout.

    Args:
        log_fn: Optional logging callable. Falls back to module logger if omitted.
    """
    log = _make_log(log_fn)

    current_ts = now_ts or time.time()
    last_sync = get_last_vnish_sync_ts()
    if not force and (current_ts - last_sync) < 300.0:
        return {}
    set_last_vnish_sync_ts(current_ts)

    active_miners = [m for m in miners if m.get("host")]
    if not active_miners:
        return {}

    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(active_miners))) as pool:
        futures = {
            pool.submit(safe_get_overclock_settings, m.get("host", ""), vnish_pw, timeout=timeout): m
            for m in active_miners
        }
        try:
            for future in concurrent.futures.as_completed(futures, timeout=timeout * 2):
                m = futures[future]
                m_name = m.get("name") or str(m.get("host"))
                m_host = m.get("host", "")
                m_port = m.get("port", 4028)
                sk = f"{m_name}|{m_host}:{m_port}"
                try:
                    ok, data, err = future.result()
                    if ok and data:
                        results[sk] = data
                        with state_lock:
                            st = states.get(sk)
                            if st is not None:
                                old_tgt = st.vnish_discovered_target_power_w
                                old_p = st.vnish_discovered_preset
                                st.vnish_discovered_target_power_w = data.get("target_power_w")
                                st.vnish_discovered_preset = data.get("preset")
                                st.vnish_discovered_top_preset = data.get("top_preset")
                                st.vnish_discovered_switcher_enabled = data.get("switcher_enabled")
                                st.vnish_discovered_ts = current_ts
                                # Spec 081: Track restart_required status for Watchdog
                                prev_req = getattr(st, "vnish_restart_required", False)
                                new_req = bool(data.get("restart_required", False))
                                st.vnish_restart_required = new_req
                                if new_req:
                                    if getattr(st, "vnish_restart_detected_ts", None) is None:
                                        st.vnish_restart_detected_ts = current_ts
                                        log(f"[PRESET-WATCHDOG] miner={m_name} detecto restart_required=True. Iniciando ventana soak...")
                                else:
                                    st.vnish_restart_detected_ts = None
                                if old_p is not None and st.vnish_discovered_preset is not None and old_p != st.vnish_discovered_preset:
                                    st.last_preset_change_ts = current_ts
                                    st.last_thermal_downstep_ts = current_ts
                                    st.balancer_preset = st.vnish_discovered_preset
                                    log(
                                        f"[VNISH_SYNC] miner={m_name} detecto cambio autonomo de preset en VNish: "
                                        f"{old_p} -> {st.vnish_discovered_preset}. Sincronizando timestamps para proteccion anti-doble-bajada."
                                    )
                                if old_tgt != st.vnish_discovered_target_power_w and old_tgt is not None:
                                    log(
                                        f"[VNISH_SYNC] miner={m_name} target_power_w adaptado dinamicamente: "
                                        f"{old_tgt}W -> {st.vnish_discovered_target_power_w}W "
                                        f"(top_preset={st.vnish_discovered_top_preset}, switcher={st.vnish_discovered_switcher_enabled})"
                                    )
                                elif old_tgt is None and st.vnish_discovered_target_power_w is not None:
                                    log(
                                        f"[VNISH_SYNC] miner={m_name} overclock descubierto: "
                                        f"preset={st.vnish_discovered_preset} top_preset={st.vnish_discovered_top_preset} "
                                        f"target_pwr={st.vnish_discovered_target_power_w}W switcher={st.vnish_discovered_switcher_enabled}"
                                    )
                                # Spec 062: Anti-Cascade Post-Reboot Interlock
                                # Enforce locked preset if firmware booted or switched to a higher preset
                                if (
                                    st.hw_error_lock_until_ts
                                    and current_ts < st.hw_error_lock_until_ts
                                    and st.hw_error_locked_preset
                                    and st.vnish_discovered_preset
                                ):
                                    from app.governance.preset_balancer import find_preset_index
                                    curr_p_idx = find_preset_index(st.vnish_discovered_preset)
                                    lock_p_idx = find_preset_index(st.hw_error_locked_preset)
                                    if curr_p_idx >= 0 and lock_p_idx >= 0:
                                        is_higher = (curr_p_idx > lock_p_idx)
                                    else:
                                        curr_digits = re.findall(r"\d+", str(st.vnish_discovered_preset))
                                        lock_digits = re.findall(r"\d+", str(st.hw_error_locked_preset))
                                        curr_w = int(curr_digits[0]) if curr_digits else 0
                                        lock_w = int(lock_digits[0]) if lock_digits else 0
                                        is_higher = (curr_w > lock_w > 0)
                                    if is_higher:
                                        gov_obj = get_intervention_gov()
                                        allowed_tw = True
                                        if gov_obj is not None:
                                            from app.governance.intervention_policy import ACTION_PRESET_BALANCER, should_allow_intervention
                                            allowed_tw, _ = should_allow_intervention(ACTION_PRESET_BALANCER, gov_obj, current_ts)
                                        if allowed_tw:
                                            log(
                                                f"[TRIPWIRE_INTERLOCK] miner={m_name} detecto preset superior ({st.vnish_discovered_preset}) "
                                                f"a candado ({st.hw_error_locked_preset}). Forzando restauracion defensiva."
                                            )
                                        def _async_restore_tripwire_preset(
                                            _h=m_host,
                                            _pw=vnish_pw,
                                            _pr=st.hw_error_locked_preset,
                                            _to=timeout,
                                            _nm=m_name,
                                        ):
                                            try:
                                                ok_r, err_r = safe_set_miner_preset(_h, _pw, _pr, timeout=_to)
                                                if ok_r:
                                                    log(f"[TRIPWIRE_INTERLOCK_RESTORE_OK] miner={_nm} preset restaurado defensivamente a {_pr}")
                                                else:
                                                    log(f"[TRIPWIRE_INTERLOCK_RESTORE_FAIL] miner={_nm} fallo restaurando a {_pr}: {err_r}")
                                            except Exception as _th_exc:
                                                log(f"[TRIPWIRE_INTERLOCK_RESTORE_ERR] miner={_nm} excepcion en hilo de restauracion: {type(_th_exc).__name__}: {_th_exc}")

                                        threading.Thread(
                                            target=_async_restore_tripwire_preset,
                                            daemon=True,
                                            name=f"RestoreLock_{m_name}",
                                        ).start()
                except Exception as exc:
                    log(f"[WARN] Error procesando overclock de {m_name}: {exc}")
        except concurrent.futures.TimeoutError:
            pass
    return results
