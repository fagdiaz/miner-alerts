"""Dynamic Power & Preset Balancer Cycle (Spec 040 & Spec 088).

Extracts and manages the Dynamic Power & Preset Balancer execution cycle.
Periodically (or on force) extracts restart and thermal metrics,
evaluates stability per miner and across electrical groups (elevators),
and executes non-blocking parallel hardware preset changes if required.

Design:
- Extracted from miner_monitor.py as part of Spec 088 (Governance Cycles Decoupling).
- Accesses shared governance state via app.governance._orchestrator_state.
- Supports dynamic fallback to miner_monitor for backwards compatibility with tests.
- Zero network I/O outside of safe_set_miner_preset / refresh_vnish_overclock_settings.
"""
from __future__ import annotations

import concurrent.futures
import logging
import threading
import time
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from app.governance._orchestrator_state import (
    get_balancer_enabled,
    get_intervention_gov,
    get_last_balancer_cycle_ts,
    set_last_balancer_cycle_ts,
)
from app.governance.intervention_policy import (
    ACTION_PRESET_BALANCER,
    should_allow_intervention,
)
from app.governance.preset_balancer import (
    ACTION_STEP_DOWN_CASCADE,
    ACTION_STEP_DOWN_HW_ERRORS,
    ACTION_STEP_DOWN_RESTARTS,
    ACTION_STEP_DOWN_THERMAL,
    BalancerConfig,
    BalancerDecision,
    StabilityMetrics,
    evaluate_balancer_step,
    extract_miner_stability_metrics,
    render_hw_error_tripwire_card,
)
from app.governance.governor_cycle import refresh_vnish_overclock_settings
from app.vnish.client import safe_set_miner_preset

if TYPE_CHECKING:
    from app.miner_monitor import MinerState

_logger = logging.getLogger("miner_alerts.balancer_cycle")


def execute_balancer_cycle(
    miners: list,
    states: Dict[str, Any],
    state_lock: threading.Lock,
    config: dict,
    now_ts: float,
    qa_mode: bool,
    db_path: str = "data/miner_alerts.db",
    force: bool = False,
    send_telegram_fn: Optional[Callable] = None,
    bot_token: str = "",
    chat_id: str = "",
    log_fn: Optional[Callable[[str], None]] = None,
) -> List[Tuple[StabilityMetrics, BalancerDecision]]:
    """Spec 040 & 088: Dynamic Power & Preset Balancer execution cycle.

    Periodically (or on force) extracts restart and thermal metrics,
    evaluates stability per miner and across electrical groups (elevators),
    and executes non-blocking parallel hardware preset changes if required.
    """
    import app.miner_monitor as mm

    _log = log_fn or getattr(mm, "log", _logger.info)

    # Dynamic mock resolutions to preserve test compatibility
    _extract_metrics_fn = getattr(mm, "extract_miner_stability_metrics", extract_miner_stability_metrics)
    _safe_set_preset_fn = getattr(mm, "safe_set_miner_preset", safe_set_miner_preset)
    _refresh_vnish_fn = getattr(mm, "refresh_vnish_overclock_settings", refresh_vnish_overclock_settings)
    _eval_step_fn = getattr(mm, "evaluate_balancer_step", evaluate_balancer_step)

    bal_enabled_cfg = bool(config.get("preset_balancer_enabled", False))
    _rt_bal = get_balancer_enabled()
    if _rt_bal is None:
        _rt_bal = getattr(mm, "_BALANCER_RUNTIME_ENABLED", None)
    bal_enabled = (
        _rt_bal
        if _rt_bal is not None
        else bal_enabled_cfg
    )
    interval = float(config.get("preset_balancer_interval_seconds", 1800.0))
    dry_run = bool(config.get("preset_balancer_dry_run", True))

    last_cycle_ts = getattr(mm, "_LAST_BALANCER_CYCLE_TS", None)
    if last_cycle_ts is None:
        last_cycle_ts = get_last_balancer_cycle_ts()

    if not force:
        if not bal_enabled or qa_mode:
            return []
        # Spec 057: Check intervention governance for Preset Balancer
        gov_obj = getattr(mm, "_GLOBAL_INTERVENTION_GOV", None) or get_intervention_gov()
        if gov_obj is not None and not should_allow_intervention(ACTION_PRESET_BALANCER, gov_obj, now_ts)[0]:
            return []
        if (now_ts - last_cycle_ts) < interval:
            return []

    set_last_balancer_cycle_ts(now_ts)
    if hasattr(mm, "_LAST_BALANCER_CYCLE_TS"):
        setattr(mm, "_LAST_BALANCER_CYCLE_TS", now_ts)

    # Hardware ceiling locks from autotune watchdog state
    autotune_state = getattr(mm, "_AUTOTUNE_WATCHDOG_STATE", None)
    facility_state = getattr(mm, "_FACILITY_BUDGET_STATE", None)

    miner_hw_limits = {}
    if isinstance(config.get("miners"), list):
        for m_item in config.get("miners", []):
            if isinstance(m_item, dict):
                m_name = m_item.get("name") or m_item.get("host")
                m_lim = m_item.get("max_hardware_preset") or m_item.get("hardware_ceiling")
                if m_name and m_lim:
                    miner_hw_limits[m_name] = m_lim
    if isinstance(config.get("miner_hardware_limits"), dict):
        miner_hw_limits.update(config.get("miner_hardware_limits"))
    if autotune_state and autotune_state.hardware_ceiling_locks:
        miner_hw_limits.update(autotune_state.hardware_ceiling_locks)

    bal_cfg = BalancerConfig(
        enabled=True,
        dry_run=dry_run,
        restarts_threshold_step_down=int(config.get("preset_balancer_restarts_step_down", 2)),
        soak_hours_step_up=float(config.get("preset_balancer_soak_hours_step_up", 72.0)),
        default_max_preset=str(config.get("preset_balancer_default_max_preset", "2700W")),
        group_cascade_threshold=int(config.get("preset_balancer_group_cascade_threshold", 2)),
        group_cascade_window_s=float(config.get("preset_balancer_group_cascade_window_s", 1800.0)),
        min_thermal_headroom_c=float(config.get("preset_balancer_min_thermal_headroom_c", 4.0)),
        hw_error_rate_threshold_pct=float(config.get("preset_balancer_hw_error_rate_threshold_pct", 0.5)),
        hw_error_delta_threshold=int(config.get("preset_balancer_hw_error_delta_threshold", 200)),
        hw_error_lock_hours=float(config.get("preset_balancer_hw_error_lock_hours", 48.0)),
        miner_hardware_limits=miner_hw_limits,
    )

    vnish_pw = str(config.get("vnish_api_password", "admin"))
    _refresh_vnish_fn(
        miners=miners,
        states=states,
        state_lock=state_lock,
        vnish_pw=vnish_pw,
        timeout=float(config.get("fan_governor_request_timeout", 2.5)),
        force=force,
        now_ts=now_ts,
    )

    with state_lock:
        metrics_list = _extract_metrics_fn(
            db_path=db_path,
            miners=miners,
            states=states,
            config=config,
            now_ts=now_ts,
        )

    decisions: List[Tuple[StabilityMetrics, BalancerDecision]] = []
    miner_map = {m.get("name", m.get("host", "")): m for m in miners}

    for m_metrics in metrics_list:
        m_dict = miner_map.get(m_metrics.miner_name, {})
        st = None
        with state_lock:
            for sk, s in states.items():
                if m_metrics.miner_name in sk or (m_dict.get("host") and m_dict["host"] in sk):
                    st = s
                    break
        if st and getattr(st, "is_shutdown_maintenance", False):
            continue
        max_override = m_dict.get("max_preset")
        decision = _eval_step_fn(
            metrics=m_metrics,
            config=bal_cfg,
            group_metrics=metrics_list,
            max_preset_override=max_override,
            current_time=now_ts,
            facility_state=facility_state,
        )
        decisions.append((m_metrics, decision))
        if getattr(decision, "boost_cooling_requested", False) and st is not None:
            with state_lock:
                st.boost_cooling_active = True
                st.boost_cooling_expires_ts = now_ts + 180.0
            _log(f"[HEADROOM-CHILLING] {m_metrics.miner_name}: solicitando boost cooling (100% PWM) por 180s para habilitar escalamiento de preset ({decision.reason})")

    writers = [
        (miner_map.get(m.miner_name, {}), m, d)
        for m, d in decisions
        if d.requires_write and not dry_run
    ]

    write_results: Dict[str, tuple] = {}
    if writers:
        # Spec 077 (REQ-002): Facility-Wide Staggered Queue across shared service drop.
        # Only 1 miner executes a preset change per cycle, enforcing a 180s settle window.
        # Prioritize emergency step-downs (thermal/HW errors/restarts) before step-ups.
        def _writer_priority(w_item):
            _, _, d = w_item
            if d.action in (
                ACTION_STEP_DOWN_THERMAL,
                ACTION_STEP_DOWN_HW_ERRORS,
                ACTION_STEP_DOWN_RESTARTS,
                ACTION_STEP_DOWN_CASCADE,
            ):
                return 0  # Highest priority: emergency relief
            return 1      # Normal optimization

        writers.sort(key=_writer_priority)
        target_dict, m_tgt, d_tgt = writers[0]

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        fleet_timeout = float(config.get("fan_governor_fleet_timeout", 5.0))
        req_timeout = float(config.get("fan_governor_request_timeout", 2.5))
        try:
            future = executor.submit(
                _safe_set_preset_fn,
                target_dict.get("host", ""),
                vnish_pw,
                d_tgt.target_preset,
                timeout=req_timeout,
            )
            try:
                ok, err = future.result(timeout=fleet_timeout)
                write_results[m_tgt.miner_name] = (ok, err)
                if ok:
                    if facility_state is not None:
                        facility_state.record_transition(
                            m_tgt.miner_name,
                            d_tgt.target_preset,
                            now_ts=now_ts,
                        )
                    _log(
                        f"[STAGGERED_BALANCER] Transición ejecutada con éxito en {m_tgt.miner_name}: "
                        f"{d_tgt.current_preset} -> {d_tgt.target_preset}. Ventana de reposo de 180s iniciada en bajada compartida."
                    )
                else:
                    _log(
                        f"[STAGGERED_BALANCER_ERR] Fallo aplicando preset {d_tgt.target_preset} a {m_tgt.miner_name}: {err}"
                    )
            except concurrent.futures.TimeoutError:
                write_results[m_tgt.miner_name] = (False, "fleet_timeout")
                _log(f"[STAGGERED_BALANCER_ERR] Timeout de flota ({fleet_timeout}s) aplicando preset a {m_tgt.miner_name}")
            except Exception as exc:
                write_results[m_tgt.miner_name] = (False, str(exc))
        finally:
            executor.shutdown(wait=False)

    with state_lock:
        for m_metrics, decision in decisions:
            m_dict = miner_map.get(m_metrics.miner_name, {})
            m_name = m_metrics.miner_name
            m_host = m_dict.get("host", "")
            m_port = m_dict.get("port", 4028)
            sk = f"{m_name}|{m_host}:{m_port}"
            st = states.get(sk)

            write_ok = True
            write_err = None
            if decision.requires_write and not dry_run:
                write_ok, write_err = write_results.get(m_name, (False, "no_result"))

            if st is not None:
                st.balancer_last_action = decision.action
                st.balancer_last_reason = decision.reason
                if decision.requires_write and (dry_run or write_ok):
                    st.balancer_preset = decision.target_preset
                    st.balancer_last_change_ts = now_ts
                    st.last_preset_change_ts = now_ts  # Spec: atribuir reinicios post-preset a esta acción
                    if decision.action == ACTION_STEP_DOWN_HW_ERRORS:
                        if not st.hw_error_lock_until_ts or st.hw_error_lock_until_ts <= now_ts:
                            st.hw_error_lock_until_ts = now_ts + (bal_cfg.hw_error_lock_hours * 3600.0)
                        st.hw_error_locked_preset = decision.target_preset
                elif not st.balancer_preset:
                    st.balancer_preset = decision.current_preset

            if decision.action == ACTION_STEP_DOWN_HW_ERRORS and (dry_run or write_ok):
                try:
                    card_msg = render_hw_error_tripwire_card(
                        miner_name=m_name,
                        electrical_group=m_metrics.electrical_group,
                        hw_errors_10m=m_metrics.hw_errors_delta_10m,
                        hw_error_rate_pct=m_metrics.hw_error_rate_pct,
                        current_preset=decision.current_preset,
                        target_preset=decision.target_preset,
                        lock_hours=bal_cfg.hw_error_lock_hours,
                    )
                    tg_fn = send_telegram_fn or getattr(mm, "send_telegram", None)
                    b_tok = bot_token or str(config.get("telegram_bot_token", ""))
                    c_id = chat_id or str(config.get("telegram_chat_id", ""))
                    if tg_fn and b_tok and c_id and not qa_mode:
                        tg_fn(b_tok, c_id, card_msg, "BALANCER", "hw_error_tripwire")
                        _log(f"[BALANCER] Telegram tripwire card sent for miner={m_name}")
                except Exception as _tg_exc:
                    _log(f"[BALANCER_ERR] Failed sending tripwire telegram card: {_tg_exc}")

            dr_tag = " DRY" if dry_run else ""
            err_tag = f" err={write_err}" if write_err else ""
            _log(
                f"[BALANCER{dr_tag}] miner={m_name} group={m_metrics.electrical_group} "
                f"action={decision.action} preset={decision.current_preset}->{decision.target_preset} "
                f"restarts_24h={m_metrics.restarts_24h} uptime={m_metrics.hours_since_last_restart:.0f}h "
                f"reason='{decision.reason}'{err_tag}"
            )

    return decisions
