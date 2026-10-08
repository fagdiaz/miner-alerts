"""Declarative Supervisory Pipeline Stages & Hooks (Spec 091).

Implements the 7 ordered stages of the supervisory cycle:
1. StagePreTick (10): Liveness & Monotonic Time Tracking
2. StageAcquisition (20): Parallel Sockets & Telemetry Normalization
3. StageDetection (30): Anomaly Streaks, Preventative Health & Classification
4. StageGovernance (40): Fan Governor, Balancer, Solar Window & FGA Actuator
5. StageActuator (50): Safe Reboots, Presets, Cooldowns & Alert Dispatch
6. StagePersistence (60): Atomic Disk Flush & SQLite WAL Maintenance
7. StagePostTick (70): Daily Executive Digest & Monotonic Sleep
"""

from __future__ import annotations

import logging
import math
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from app.core.config import log, resolve_db_path
from app.core.system import argentina_now, now_str
from app.core.context import MonitorContext
from app.core.engine import (
    ActuatorHook,
    DetectionHook,
    HookResult,
    HookStage,
    PersistenceHook,
    SupervisoryHook,
)
from app.core.liveness import MonitorHeartbeat, write_heartbeat_atomic
from app.core.models import MinerState
from app.core.reboot_safety import (
    STATE_HASHBOARD,
    STATE_LOW,
    STATE_OFFLINE,
    STATE_OK,
    evaluate_auto_reboot_interlocks,
)
from app.core.restart_intelligence import (
    _async_execute_mining_restart,
    _async_execute_preset_restart,
    evaluate_auto_restart_candidate,
    evaluate_preset_restart_candidate,
)
from app.core.system import run_hashcore_cli
from app.governance.adaptive_contingency import (
    ACTION_NO_ACTION,
    ACTION_RESTORE_INRUSH_DAMPENER,
    ACTION_RESTORE_NOMINAL,
    GroupContingencyState,
    evaluate_canary_contingency,
    normalize_miner_name,
)
from app.governance.autotune_watchdog import (
    AutotuneWatchdogState,
    check_autotune_watchdog,
)
from app.governance.balancer_cycle import execute_balancer_cycle
from app.governance.elevator_budget import (
    FacilityBudgetState,
    evaluate_soft_contingency_schedule,
    evaluate_solar_thermal_envelope,
    get_miner_max_hardware_preset,
    parse_preset_wattage,
)
from app.governance.preset_balancer import record_elevator_restart_circumstance
from app.governance.governor_cycle import (
    execute_governor_cycle,
    refresh_vnish_overclock_settings,
)
from app.governance.intervention_policy import (
    ACTION_CONTINGENCY,
    ACTION_PRESET_BALANCER,
    ACTION_REBOOT_L2,
    InterventionGovernance,
    apply_governance_toggle,
    should_allow_intervention,
)
from app.governance.maintenance_scheduler import (
    ScheduledWindow,
    process_maintenance_scheduler_cycle,
)
from app.governance.phase_drop_discriminator import process_phase_drop_cycle
from app.governance.post_blackout_guard import (
    PostBlackoutTracker,
    execute_post_blackout_cycle,
)
from app.governance.power_progression import (
    PROFILE_ALIASES,
    PROFILE_C0_BASE_STABLE,
    PROFILE_EMERGENCY_COOL,
    PROFILE_TARGETS,
    get_global_progression_state,
)
from app.hardware.chain_collector import (
    _CHAIN_HEALTH_STREAKS,
    _SETTINGS_CORRUPTION_ALERTS,
    _SETTINGS_HEALTH_TIMESTAMPS,
    _async_collect_chain_telemetry,
    _async_evaluate_predictive_chain_break,
)
from app.network.cgminer_client import (
    read_stats_snapshot,
    read_summary,
)
from app.core.acquisition import (
    AcquisitionConfig,
    AcquisitionEpoch,
    Api4028Transport,
    BoundedAcquirer,
    MinerEndpoint,
)
from app.vnish.telemetry import (
    VnishTelemetry,
    normalize_vnish_stats,
)
from app.core.mining_quality import normalize_mining_quality
from app.governance.fan_health import (
    assess_miner_cooling,
    evaluate_cooling_alerts,
)
from app.governance.energy_efficiency import (
    assess_miner_efficiency,
    evaluate_efficiency_alerts,
)
from app.vnish.presets import (
    assess_miner_preset,
    evaluate_preset_alerts,
)
from app.core.restart_intelligence import classify_restart
from app.telegram.fleet_cards import display_name
from app.core.alert_episodes import (
    IrregularEpisodeCoordinator,
    render_episode_notification_batch,
)
from app.telegram.callbacks import build_alert_keyboard
from app.telegram.poller import _WAKEUP_EVENT
from app.telegram.sender import send_telegram
from app.telegram.snooze import filter_snoozed_episodes
from app.vnish.client import safe_set_miner_preset

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared Module State Singletons
# ---------------------------------------------------------------------------
_BALANCER_RUNTIME_ENABLED: Optional[bool] = None
_LAST_BALANCER_CYCLE_TS: float = 0.0
_POST_BLACKOUT_TRACKER: PostBlackoutTracker = PostBlackoutTracker()
_LAST_PHASE_DROP_ALERT_TS: Dict[str, float] = {}
_ACTIVE_PHASE_DROPS: Set[str] = set()
_ACTIVE_SCHEDULED_WINDOW: Optional[ScheduledWindow] = None
_GLOBAL_INTERVENTION_GOV: InterventionGovernance = InterventionGovernance()

_ELEVATOR_CONTINGENCY_STATES: Dict[str, GroupContingencyState] = {}
_FACILITY_BUDGET_STATE: FacilityBudgetState = FacilityBudgetState()
_AUTOTUNE_WATCHDOG_STATE: AutotuneWatchdogState = AutotuneWatchdogState()

# Inject into governance orchestrator state
from app.governance._orchestrator_state import (
    set_intervention_gov as _set_igov,
    set_elevator_contingency_states as _set_ec_states,
    set_facility_budget_state as _set_fb_state,
    set_autotune_watchdog_state as _set_at_state,
)
_set_igov(_GLOBAL_INTERVENTION_GOV)
_set_ec_states(_ELEVATOR_CONTINGENCY_STATES)
_set_fb_state(_FACILITY_BUDGET_STATE)
_set_at_state(_AUTOTUNE_WATCHDOG_STATE)
_LAST_SOFT_CONTINGENCY_PEAK_STATE: Optional[bool] = None
_LAST_SOLAR_WINDOW_STATE: Optional[bool] = None
_LAST_FGA_ACTUATOR_TS: float = 0.0
_LAST_DEADLOCK_ALERT_TS: Dict[str, float] = {}
_DEADLOCK_ALERT_ACTIVE: Dict[str, bool] = {}
_LAST_DAILY_DIGEST_DATE: Optional[str] = None
_INCIDENT_AUTOPSY_ENGINE: Any = None


# ---------------------------------------------------------------------------
# Formatting and Recording Utilities
# ---------------------------------------------------------------------------

def format_rate(rate: Optional[float]) -> str:
    return f"{rate:.2f} TH/s" if rate is not None else "N/A"


def format_fleet_restored_line(
    name_display: str,
    rate_ths: Optional[float],
    temp_c: Optional[float] = None,
) -> str:
    """Format a single miner status line for the 🟢 FLOTA RESTABLECIDA card."""
    rate_str = f"{float(rate_ths):.1f} TH/s" if rate_ths is not None else "N/A"
    temp_str = f" {float(temp_c):.0f}°C" if temp_c is not None else ""
    return f"- {name_display}: {rate_str} [OK]{temp_str}"


def is_fleet_warmup_complete(
    miners: list,
    states: dict,
    threshold_ths: float,
    expected_boards: int = 3,
) -> bool:
    """Check if all valid miners have responded and reached the warm-up hashrate threshold."""
    if not miners:
        return False
    for m in miners:
        m_name = m.get("name", "")
        m_host = m.get("host", "")
        m_sk = f"{m_name}|{m_host}:{m.get('port', 4028)}"
        m_st = states.get(m_sk)
        if m_st is None:
            return False
        if not getattr(m_st, "last_responded", False):
            return False
        rate = getattr(m_st, "last_rate_ths", None)
        if rate is None or float(rate) < float(threshold_ths):
            return False
        boards = getattr(m_st, "last_active_boards", None)
        if boards is not None and int(boards) < int(expected_boards):
            return False
    return True


def record_action_outcome(
    event_store: Optional[Any],
    *,
    occurred_ts: float,
    miner: dict,
    action: str,
    source: str,
    ok: bool,
    message: str,
) -> None:
    if event_store is None or not getattr(event_store, "available", False):
        return
    miner_name = display_name(str(miner.get("name", "")))
    event_store.record_event(
        occurred_ts=occurred_ts,
        miner_key=f"{miner.get('name')}|{miner.get('host')}:{miner.get('port')}",
        miner_name=miner_name,
        host=str(miner.get("host", "")),
        event_type=f"{source}_{action}_{'success' if ok else 'failed'}",
        severity="info" if ok else "warning",
        classification=f"{source}_{action}",
        action_source=source,
        action_ts=occurred_ts,
        summary=(
            f"{source} {action} enviado"
            if ok
            else f"{source} {action} fallo: {message[:120]}"
        ),
        details={"ok": ok},
    )


def record_auto_reboot_decision(
    event_store: Optional[Any],
    *,
    evaluated_ts: float,
    miner: dict,
    state: MinerState,
    result: str,
    responded: bool,
    rate_ths: Optional[float],
    threshold_ths: float,
    active_boards: Optional[int],
    expected_boards: int,
    telemetry: VnishTelemetry,
    startup_guard_active: bool,
    qa_mode: bool,
    cooldown_remaining_seconds: Optional[float],
    window_seconds: int,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    if event_store is None or not getattr(event_store, "available", False):
        return
    low_elapsed = None
    if state.low_since_ts is not None:
        low_elapsed = max(0.0, evaluated_ts - state.low_since_ts)
    elif state.hashboard_since_ts is not None:
        low_elapsed = max(0.0, evaluated_ts - state.hashboard_since_ts)
    event_store.record_reboot_decision(
        evaluated_ts=evaluated_ts,
        miner_key=f"{miner.get('name')}|{miner.get('host')}:{miner.get('port')}",
        miner_name=display_name(str(miner.get("name", ""))),
        host=str(miner.get("host", "")),
        result=result,
        state=state.state,
        responded=responded,
        rate_ths=rate_ths,
        threshold_ths=threshold_ths,
        low_elapsed_seconds=low_elapsed,
        active_boards=active_boards,
        expected_boards=expected_boards,
        startup_guard_active=startup_guard_active,
        qa_mode=qa_mode,
        cooldown_remaining_seconds=cooldown_remaining_seconds,
        window_count=len(state.auto_reboot_timestamps),
        window_seconds=window_seconds,
        telemetry=telemetry.as_dict() if hasattr(telemetry, "as_dict") else {},
        details=details,
    )


# ---------------------------------------------------------------------------
# Canonical Pipeline Hooks
# ---------------------------------------------------------------------------

class PreTickHook(SupervisoryHook):
    """StagePreTick (10): Liveness & Monotonic Time Sync."""

    name = "pre_tick"
    stage = HookStage.PRE_TICK

    def execute(
        self,
        context: MonitorContext,
        tick_sequence: int,
        now_ts: float,
        tick_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        tick_start = tick_data.get("tick_start", time.monotonic())
        process_start_ts = tick_data.get("process_start_ts", now_ts)
        startup_fleet_grace_period_seconds = int(
            context.config.get("startup_fleet_grace_period_seconds", 180)
        )
        startup_grace_active = tick_data.get(
            "startup_grace_active",
            (now_ts - process_start_ts) < startup_fleet_grace_period_seconds,
        )

        if startup_grace_active and (now_ts - process_start_ts) >= startup_fleet_grace_period_seconds:
            startup_grace_active = False
            log(
                f"[COLD_BOOT_GRACE] Período de gracia finalizado por timeout "
                f"({now_ts - process_start_ts:.1f}s >= {startup_fleet_grace_period_seconds}s)"
            )
        elif startup_grace_active:
            log(
                f"[COLD_BOOT_GRACE] Fase WARMING_UP activa "
                f"(elapsed={now_ts - process_start_ts:.1f}s/{startup_fleet_grace_period_seconds}s)"
            )

        return {
            "tick_start": tick_start,
            "startup_grace_active": startup_grace_active,
            "reboot_names_tick": [],
            "miner_lines": [],
            "degraded_candidates": [],
            "current_tick_signals": {},
            "tick_failed_miners": [],
            "tick_responded_miners": [],
            "tick_maintenance_ids": set(),
        }


class AcquisitionHook(SupervisoryHook):
    """StageAcquisition (20): Parallel Sockets & Telemetry Normalization."""

    name = "acquisition"
    stage = HookStage.ACQUISITION

    def execute(
        self,
        context: MonitorContext,
        tick_sequence: int,
        now_ts: float,
        tick_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        states = tick_data.get("states", {})
        valid_miners = context.miners
        config = context.config
        qa_mode = context.qa_mode
        threshold_ths = context.threshold_ths
        expected_boards = int(config.get("expected_boards", 3))
        acq_config = tick_data.get("acq_config")
        acquirer: Optional[BoundedAcquirer] = tick_data.get("acquirer")
        acq_endpoints = tick_data.get("acq_endpoints", ())
        tick_start = tick_data.get("tick_start", time.monotonic())
        vnish_api_password = str(config.get("vnish_api_password", "admin"))
        state_lock = context.state_lock
        event_store = context.event_store
        telemetry_sample_seconds = max(30, int(config.get("telemetry_sample_seconds", 300)))
        last_sample_ts = tick_data.setdefault("last_sample_ts", {})

        tick_envelopes: Optional[Dict[str, Any]] = None
        if acq_config and acq_config.enabled and acquirer is not None:
            try:
                _epoch = AcquisitionEpoch(
                    epoch_id=tick_sequence,
                    scheduled_monotonic=tick_start,
                    deadline_monotonic=tick_start + acq_config.deadline_seconds,
                    observed_ts=now_ts,
                )
                tick_envelopes = acquirer.collect_authoritative(acq_endpoints, _epoch)
            except Exception as _acq_exc:
                log(f"[WARN] Adaptive acquisition epoch failed: {_acq_exc}. Using sequential fallback.")
                tick_envelopes = None

        tick_maintenance_ids: Set[str] = set()
        tick_responded_miners: List[Dict[str, Any]] = []
        tick_failed_miners: List[Dict[str, Any]] = []
        miner_results: Dict[str, Any] = {}

        for miner in valid_miners:
            name = miner["name"]
            name_display = display_name(name)
            host = miner["host"]
            port = miner["port"]
            state_key = f"{name}|{host}:{port}"
            state = states.setdefault(state_key, MinerState())

            if tick_envelopes is not None and state_key in tick_envelopes:
                _env = tick_envelopes[state_key]
                rate_ths = _env.rate_ths
                elapsed = _env.elapsed_seconds
                responded = _env.responded
                summary_entry = _env.summary_entry
                active_boards = _env.active_boards
                stats_response = _env.stats_response
            else:
                rate_ths, elapsed, responded, summary_entry = read_summary(host, port)
                active_boards = None
                stats_response = None
                if responded:
                    active_boards, _, stats_response = read_stats_snapshot(host, port)

            vnish_telemetry = normalize_vnish_stats(
                stats_response,
                expected_boards=expected_boards,
            )
            quality_telemetry = normalize_mining_quality(
                summary_entry,
                stats_response,
                expected_boards=expected_boards,
            )

            if qa_mode:
                qa_force = config.get("qa_force_state", {})
                if isinstance(qa_force, dict):
                    forced = qa_force.get(name_display) or qa_force.get(name)
                    if forced == "OFFLINE":
                        responded = False
                        rate_ths = None
                    elif forced == "LOW":
                        responded = True
                        rate_ths = threshold_ths - 1.0
                    elif forced == "HASHBOARD":
                        responded = True
                        active_boards = max(0, expected_boards - 1)

            is_maint_dev = getattr(state, "is_shutdown_maintenance", False) or (
                state.snooze_until_ts is not None and now_ts < state.snooze_until_ts
            )
            if is_maint_dev:
                tick_maintenance_ids.add(name)
                tick_maintenance_ids.add(state_key)

            if responded:
                tick_responded_miners.append(miner)
                state.last_seen_ts = now_ts
            else:
                tick_failed_miners.append(miner)

            previous_elapsed = state.last_elapsed
            reboot_reason = ""
            if responded and elapsed is not None:
                if state.last_elapsed is not None:
                    if elapsed < state.last_elapsed - 600:
                        reboot_reason = "elapsed_drop"
                    elif elapsed < 300 and state.last_elapsed > 3600:
                        reboot_reason = "elapsed_reset"
                if reboot_reason:
                    state.low_since_ts = None
                    state.hashboard_since_ts = None
                    gov_obj = getattr(state, "intervention_gov", None) or _GLOBAL_INTERVENTION_GOV
                    allowed_tw = True
                    if gov_obj is not None:
                        allowed_tw, _ = should_allow_intervention(ACTION_PRESET_BALANCER, gov_obj, now_ts)
                    if (
                        allowed_tw
                        and state.hw_error_lock_until_ts
                        and now_ts < state.hw_error_lock_until_ts
                        and state.hw_error_locked_preset
                    ):
                        log(
                            f"[TRIPWIRE_INTERLOCK] miner={name} reinicio detectado ({reboot_reason}) "
                            f"con candado activo hasta {state.hw_error_lock_until_ts:.0f} (objetivo={state.hw_error_locked_preset}). "
                            "Programando restauracion defensiva de preset post-reboot."
                        )
                        def _async_restore_locked_preset(
                            h=host,
                            pw=vnish_api_password,
                            pr=state.hw_error_locked_preset,
                            nm=name,
                        ):
                            try:
                                time.sleep(15.0)
                                ok_p, err_p = safe_set_miner_preset(h, pw, pr)
                                if ok_p:
                                    log(f"[TRIPWIRE_INTERLOCK] miner={nm} preset defensivo restaurado con exito a {pr}")
                                else:
                                    log(f"[TRIPWIRE_INTERLOCK_ERR] miner={nm} fallo restaurando a {pr}: {err_p}")
                            except Exception as _th_exc:
                                log(f"[TRIPWIRE_INTERLOCK_ERR] miner={nm} excepcion restaurando preset a {pr}: {_th_exc}")

                        threading.Thread(
                            target=_async_restore_locked_preset,
                            daemon=True,
                            name=f"TripwireRestore_{name}",
                        ).start()

                state.last_elapsed = elapsed
                if (
                    state.last_preset_change_ts is None
                    and elapsed is not None
                    and elapsed < float(config.get("autotune_grace_period_seconds", 900.0))
                ):
                    state.last_preset_change_ts = now_ts - elapsed

            # Telemetry to MinerState & Governor
            eff_j_th: Optional[float] = None
            if responded and vnish_telemetry.chain_power_w_total is not None and rate_ths and rate_ths > 0:
                eff_j_th = round(vnish_telemetry.chain_power_w_total / rate_ths, 2)

            with state_lock:
                state.last_responded = bool(responded)
                if responded:
                    state.last_rate_ths = rate_ths
                    state.last_active_boards = active_boards
                    state.last_expected_boards = expected_boards
                    state.last_max_chip_temp = vnish_telemetry.max_temp_c
                    state.last_fan_duty_percent = vnish_telemetry.fan_pwm_percent
                    state.last_power_w = vnish_telemetry.chain_power_w_total
                    state.last_efficiency_j_th = eff_j_th
                    state.inlet_temp_c = vnish_telemetry.inlet_temp_c
                    state.last_fan_mode = vnish_telemetry.fan_mode
                    if vnish_telemetry.max_temp_c is not None:
                        state.governor_last_temp_c = vnish_telemetry.max_temp_c
                    if vnish_telemetry.chain_power_w_total is not None:
                        state.governor_last_power_w = vnish_telemetry.chain_power_w_total
                    if vnish_telemetry.fan_pwm_percent is not None:
                        _hw_duty = int(round(vnish_telemetry.fan_pwm_percent))
                        if state.governor_duty is None:
                            state.governor_duty = _hw_duty
                        elif (
                            now_ts - (state.governor_last_change_ts or 0.0) >= 30.0
                            and abs(state.governor_duty - _hw_duty) >= 2
                        ):
                            state.governor_duty = _hw_duty
                            state.governor_holds = 0
                else:
                    state.last_rate_ths = 0.0
                    state.last_active_boards = 0
                    state.last_expected_boards = expected_boards
                    state.last_max_chip_temp = None
                    state.last_fan_duty_percent = None
                    state.last_power_w = 0.0
                    state.last_efficiency_j_th = None
                    state.inlet_temp_c = None
                    state.governor_last_temp_c = None
                    state.governor_last_power_w = None

            # Record sample in event store
            if event_store is not None and getattr(event_store, "available", False):
                last_sample = last_sample_ts.get(state_key, 0.0)
                if (now_ts - last_sample) >= telemetry_sample_seconds:
                    last_sample_ts[state_key] = now_ts
                    event_store.record_sample(
                        observed_ts=now_ts,
                        miner_key=state_key,
                        miner_name=name_display,
                        host=host,
                        state=state.state,
                        responded=responded,
                        rate_ths=rate_ths,
                        threshold_ths=threshold_ths,
                        active_boards=active_boards,
                        expected_boards=expected_boards,
                        elapsed_seconds=elapsed,
                        telemetry={
                            **vnish_telemetry.as_dict(),
                            **quality_telemetry.as_dict(),
                        },
                    )

            miner_results[state_key] = {
                "miner": miner,
                "state": state,
                "responded": responded,
                "rate_ths": rate_ths,
                "elapsed": elapsed,
                "previous_elapsed": previous_elapsed,
                "reboot_reason": reboot_reason,
                "active_boards": active_boards,
                "vnish_telemetry": vnish_telemetry,
                "quality_telemetry": quality_telemetry,
            }

        return {
            "miner_results": miner_results,
            "tick_responded_miners": tick_responded_miners,
            "tick_failed_miners": tick_failed_miners,
            "tick_maintenance_ids": tick_maintenance_ids,
        }


class GovernanceHook(SupervisoryHook):
    """StageGovernance (40): Fan Governor, Balancer, Solar Window & FGA Actuator."""

    name = "governance"
    stage = HookStage.GOVERNANCE

    def execute(
        self,
        context: MonitorContext,
        tick_sequence: int,
        now_ts: float,
        tick_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        valid_miners = context.miners
        states = tick_data.get("states", {})
        state_lock = context.state_lock
        config = context.config
        qa_mode = context.qa_mode
        qa_notify = context.qa_notify
        bot_token = context.bot_token
        chat_id = context.chat_id

        # Governance Interlock Timer Expiry
        global _GLOBAL_INTERVENTION_GOV
        if _GLOBAL_INTERVENTION_GOV.expires_at_ts is not None and _GLOBAL_INTERVENTION_GOV.is_expired(now_ts):
            _GLOBAL_INTERVENTION_GOV = apply_governance_toggle(_GLOBAL_INTERVENTION_GOV, "all_on", now_ts)
            with state_lock:
                for st in states.values():
                    st.intervention_gov = _GLOBAL_INTERVENTION_GOV
            log("[INTERVENTIONS] Temporary suppression expired. Interventions automatically restored to ALL ON.")
            send_telegram(
                bot_token,
                str(chat_id),
                "🛡️ *INTERVENCIONES REACTIVADAS AUTOMÁTICAMENTE*\n\nFinalizó la ventana temporal de suspensión. Todos los actuadores automáticos (Reinicios L1/L2, Fan Governor, Presets, Contingencia) han sido restaurados.",
                "STATUS",
                "interventions_auto_reactivated",
                is_command=True,
            )

        # Dynamic Vnish overclock & autoswitch settings sync (every 300s)
        try:
            refresh_vnish_overclock_settings(
                miners=valid_miners,
                states=states,
                state_lock=state_lock,
                vnish_pw=str(config.get("vnish_api_password", "admin")),
                timeout=float(config.get("fan_governor_request_timeout", 2.5)),
                now_ts=now_ts,
            )
        except Exception as _sync_exc:
            log(f"[VNISH_SYNC_ERR] Vnish sync failed: {_sync_exc}")

        # Fan Governor Cycle
        try:
            execute_governor_cycle(
                miners=valid_miners,
                states=states,
                state_lock=state_lock,
                config=config,
                now_ts=now_ts,
                qa_mode=qa_mode,
            )
        except Exception as _gov_exc:
            log(f"[GOV_ERR] Governor cycle failed: {_gov_exc}")

        # Dynamic Preset Balancer Cycle
        try:
            execute_balancer_cycle(
                miners=valid_miners,
                states=states,
                state_lock=state_lock,
                config=config,
                now_ts=now_ts,
                qa_mode=qa_mode,
                db_path=resolve_db_path(config),
                send_telegram_fn=send_telegram,
                bot_token=bot_token,
                chat_id=str(chat_id),
            )
        except Exception as _bal_exc:
            log(f"[BALANCER_ERR] Balancer cycle failed: {_bal_exc}")

        # Autotune Stall Watchdog Cycle
        try:
            check_autotune_watchdog(
                miners=valid_miners,
                states=states,
                state_lock=state_lock,
                config=config,
                now_ts=now_ts,
                send_telegram_fn=send_telegram,
                bot_token=bot_token,
                chat_id=str(chat_id),
                qa_mode=qa_mode,
            )
        except Exception as _atw_exc:
            log(f"[AUTOTUNE_WATCHDOG_ERR] Autotune watchdog cycle failed: {_atw_exc}")

        return {"governance_completed": True}


class PostTickHook(SupervisoryHook):
    """StagePostTick (70): Daily Executive Digest & Monotonic Sleep."""

    name = "post_tick"
    stage = HookStage.POST_TICK

    def execute(
        self,
        context: MonitorContext,
        tick_sequence: int,
        now_ts: float,
        tick_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        global _LAST_DAILY_DIGEST_DATE
        config = context.config
        bot_token = context.bot_token
        chat_id = context.chat_id
        qa_mode = context.qa_mode
        qa_notify = context.qa_notify
        states = tick_data.get("states", {})
        miners = context.miners
        state_lock = context.state_lock
        first_tick = tick_data.get("first_tick", False)

        daily_digest_enabled = bool(config.get("daily_digest_enabled", True))
        daily_digest_time = str(config.get("daily_digest_time", "08:00"))

        if daily_digest_enabled and not first_tick and ((not qa_mode) or qa_notify):
            ar_now = argentina_now()
            from app.telegram.daily_digest import (
                fetch_daily_digest_metrics,
                format_daily_digest,
                get_due_digest_slot,
            )
            due_slot = get_due_digest_slot(ar_now, daily_digest_time, _LAST_DAILY_DIGEST_DATE)
            if due_slot is not None:
                try:
                    db_p = resolve_db_path(config)
                    b_root = config.get("backup_root", "backups")
                    with state_lock:
                        digest_metrics = fetch_daily_digest_metrics(
                            db_path=db_p,
                            miners=miners,
                            now_ts=now_ts,
                            backup_root=b_root,
                            states=states,
                        )
                    today_ar_str = ar_now.strftime("%Y-%m-%d")
                    digest_msg = format_daily_digest(digest_metrics, date_str=ar_now.strftime("%d/%m/%Y"))
                    send_telegram(
                        bot_token,
                        str(chat_id),
                        digest_msg,
                        "DIGEST",
                        "scheduled_daily_digest",
                    )
                    if _LAST_DAILY_DIGEST_DATE and today_ar_str in _LAST_DAILY_DIGEST_DATE:
                        _LAST_DAILY_DIGEST_DATE = f"{_LAST_DAILY_DIGEST_DATE},{due_slot}"
                    else:
                        _LAST_DAILY_DIGEST_DATE = due_slot
                    log(f"DAILY_DIGEST_SENT slot={due_slot} date={today_ar_str} time={daily_digest_time}")
                except Exception as exc:
                    log(f"DAILY_DIGEST_ERR exc={exc}")

        return {"last_daily_digest_date": _LAST_DAILY_DIGEST_DATE}
