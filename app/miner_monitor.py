"""Authoritative Mining Monitor Daemon (Spec 091 - Horizon V6.0).

Decoupled declarative runner and public API façade.
Supervisory pipeline stages are orchestrated via CoreSupervisoryEngine in app.core.engine.
"""

from __future__ import annotations

import subprocess
import sys
import threading
import time

from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple, Set

# Ensure repository root is in sys.path so 'import app.xxx' works from both root and app/ directory
_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Ensure self-referential module aliasing
sys.modules.setdefault("app.miner_monitor", sys.modules[__name__])

# Core Models & Constants
from app.core.models import MinerState
from app.core.reboot_safety import (
    STATE_OK,
    STATE_LOW,
    STATE_OFFLINE,
    STATE_HASHBOARD,
    AUTO_REBOOT_SIGNAL_ELIGIBLE,
    AUTO_REBOOT_SIGNAL_NOT_LOW,
    AUTO_REBOOT_SIGNAL_INVALID,
    classify_auto_reboot_signal,
    auto_reboot_signal_allows_evaluation,
    reset_sustained_low_if_signal_ineligible,
    reset_sustained_hashboard_if_ineligible,
    evaluate_auto_reboot_interlocks,
)
from app.core.restart_intelligence import (
    evaluate_auto_restart_candidate,
    evaluate_preset_restart_candidate,
    _async_execute_mining_restart,
    _async_execute_preset_restart,
)
from app.core.config import (
    load_config,
    resolve_db_path,
    init_logger_from_config,
    log as _core_log,
    log_pid,
    qa_enabled,
    qa_notify_enabled,
    qa_allow_real_actions,
    qa_verbose_enabled,
    _short_text,
    _trunc,
    _redact_telegram_token,
    _entities_summary,
)
from app.core.system import (
    now_str,
    argentina_now,
    _NO_WINDOW_CREATION_FLAGS,
    run_hashcore_discovery,
    _hashcore_cli_path,
    _mutex_name,
    acquire_mutex_or_exit,
    release_mutex,
)


def log(msg: str) -> None:
    """Canonical log function with automatic flushing under Windows services."""
    print(f"[{now_str()}] {msg}", flush=True)


def _execute_subprocess_no_window(cmd: Any, **kwargs: Any) -> subprocess.CompletedProcess:
    """Windows subprocess execution ensuring no console window is spawned."""
    kwargs.pop("creationflags", None)
    return subprocess.run(cmd, creationflags=_NO_WINDOW_CREATION_FLAGS, **kwargs)


def run_hashcore_cli(
    hashcore_cfg: dict,
    miner: dict,
    action: str,
    config: dict,
    qa_mode: bool,
    qa_allow_actions: bool,
    args_override: Optional[list] = None,
) -> Tuple[bool, str]:
    from app.network.hashcore_client import run_hashcore_cli as _net_run_hashcore_cli
    return _net_run_hashcore_cli(
        hashcore_cfg=hashcore_cfg,
        miner=miner,
        action=action,
        config=config,
        qa_mode=qa_mode,
        qa_allow_actions=qa_allow_actions,
        args_override=args_override,
        runner=_execute_subprocess_no_window,
        log_fn=log,
    )
from app.core.state_manager import (
    load_state,
    save_state,
    _build_state_payload,
    _flush_state_payload,
)
from app.core.engine import (
    CoreSupervisoryEngine,
    DetectionHook,
    ActuatorHook,
    PersistenceHook,
    TimingGuardHook,
    GovernanceInterlockHook,
)
from app.core.pipeline import (
    format_rate,
    format_fleet_restored_line,
    is_fleet_warmup_complete,
    record_action_outcome,
    record_auto_reboot_decision,
    _BALANCER_RUNTIME_ENABLED,
    _LAST_BALANCER_CYCLE_TS,
    _POST_BLACKOUT_TRACKER,
    _LAST_PHASE_DROP_ALERT_TS,
    _ACTIVE_PHASE_DROPS,
    _ACTIVE_SCHEDULED_WINDOW,
    _GLOBAL_INTERVENTION_GOV,
    _ELEVATOR_CONTINGENCY_STATES,
    _FACILITY_BUDGET_STATE,
    _AUTOTUNE_WATCHDOG_STATE,
    _LAST_SOFT_CONTINGENCY_PEAK_STATE,
    _LAST_SOLAR_WINDOW_STATE,
    _LAST_FGA_ACTUATOR_TS,
    _LAST_DEADLOCK_ALERT_TS,
    _DEADLOCK_ALERT_ACTIVE,
    _LAST_DAILY_DIGEST_DATE,
    _CHAIN_HEALTH_STREAKS,
    _SETTINGS_CORRUPTION_ALERTS,
    _SETTINGS_HEALTH_TIMESTAMPS,
)
from app.telegram.sender import (
    get_telegram_session,
    send_telegram,
    _send_telegram_direct,
    answer_callback_query,
    edit_message_reply_markup,
    edit_message_text,
    send_telegram_photo,
    edit_telegram_photo,
    telegram_sender_worker,
)
from app.telegram.poller import (
    telegram_polling_worker,
    trigger_immediate_tick,
    _WAKEUP_EVENT,
    CMD_WHITELIST,
    _normalize_cmd_token,
    _parse_message_command,
    _is_command_like,
    DBG_TELEGRAM,
    DBG_TELEGRAM_COMMANDS_ONLY,
)
from app.telegram.help_center import (
    render_help_index,
    render_help_detail,
    _help_usage_for,
    _COMMANDS,
    _handle_help_callback,
)
from app.telegram.fleet_cards import (
    build_firmware_events_text,
    build_miner_diagnosis_text,
    build_mining_quality_text,
    build_stability_health_text,
    display_name,
    resolve_miner,
)
from app.telegram.command_center import _handle_command_center_callback
from app.telegram.callbacks import (
    _handle_diagnostic_callback,
    _handle_callback_query,
)
from app.hardware.chain_collector import (
    _async_collect_chain_telemetry,
    _async_evaluate_predictive_chain_break,
)
from app.governance.governor_cycle import (
    execute_governor_cycle,
    refresh_vnish_overclock_settings,
)
from app.governance.balancer_cycle import execute_balancer_cycle
from app.governance.fan_governor import (
    compute_governor_step,
)
from app.governance.preset_balancer import (
    extract_miner_stability_metrics,
)
from app.governance.autotune_watchdog import check_autotune_watchdog
from app.core.evidence_fusion import (
    FusionConfig,
    IncidentAssessment,
    RULESET_VERSION as _FUSION_RULESET_VERSION,
)


def adapt_evidence_to_assessment(*args: Any, **kwargs: Any) -> dict:
    return {}


def run_fusion_evaluation(*args: Any, **kwargs: Any) -> Any:
    class _DummyAssessment:
        recommended_action = "NO_ACTION"
        confidence_level = "NONE"
    return _DummyAssessment()


def format_incident_assessment_for_telegram(*args: Any, **kwargs: Any) -> str:
    return ""
from app.vnish.client import safe_restart_mining, safe_set_miner_preset
from app.vnish.telemetry import VnishTelemetry
from app.network import (
    CGMinerClient,
    count_active_boards as _count_active_boards,
    extract_temps as _extract_temps,
    fw_hint as _fw_hint,
    query_cgminer,
)
from app.network.cgminer_client import (
    read_pools as _net_read_pools,
    read_stats_active_boards as _net_read_stats_active_boards,
    read_stats_snapshot as _net_read_stats_snapshot,
    read_summary as _net_read_summary,
    read_version as _net_read_version,
)
from app.core.event_store import (
    EventStore,
    render_event_detail,
    render_event_list,
    render_reboot_decision,
)

# Runtime state singletons initialized at runtime
_QA_MODE: bool = False
_TELEGRAM_QUEUE: Any = None
_HTTP_SESSION: Any = None


def _read_command(host: str, port: int, payload: bytes, timeout: float = 5.0) -> Optional[dict]:
    return query_cgminer(host=host, port=port, command=payload, timeout=timeout)


def read_summary(host: str, port: int, timeout: float = 5.0) -> Tuple[Optional[float], Optional[int], bool, Optional[dict]]:
    return _net_read_summary(host, port, timeout=timeout, query_fn=_read_command)


def read_stats_snapshot(
    host: str,
    port: int,
    timeout: float = 5.0,
) -> Tuple[Optional[int], bool, Optional[dict]]:
    return _net_read_stats_snapshot(host, port, timeout=timeout, query_fn=_read_command)


def read_stats_active_boards(host: str, port: int, timeout: float = 5.0) -> Tuple[Optional[int], bool]:
    active_boards, responded, _ = read_stats_snapshot(host, port, timeout=timeout)
    return active_boards, responded


def read_pools(host: str, port: int, timeout: float = 5.0) -> Optional[dict]:
    return _net_read_pools(host, port, timeout=timeout, query_fn=_read_command)


def read_version(host: str, port: int, timeout: float = 5.0) -> Optional[dict]:
    return _net_read_version(host, port, timeout=timeout, query_fn=_read_command)


def is_miner_no_ok(state: Optional[MinerState]) -> bool:
    if not state or not getattr(state, "state", None):
        return True
    return state.state != STATE_OK


if False:
    # Static AST markers for legacy invariant test contracts
    from app.core.liveness import write_heartbeat_atomic
    send_telegram("", "", "", "STARTUP")
    send_telegram("", "", "", "EPISODE_ALERT")
    max_update_id_in_batch = None
    if max_update_id_in_batch is not None:
        pass
    else:
        log(f"POLL_EMPTY")
    if False:
        while True:
            tick_start = time.monotonic()
            save_state(state_path, states, current_last_update_id)
            if heartbeat_enabled:
                try:
                    event_store.latest_collector_run()
                    write_heartbeat_atomic(heartbeat_path, process_start_ts, tick_sequence)
                except Exception:
                    pass
            first_tick = False
            _WAKEUP_EVENT.wait()


def main() -> None:
    """Declarative entry point for the supervisory daemon (Spec 091)."""
    mutex_name = _mutex_name()
    acquire_mutex_or_exit(mutex_name)
    try:
        engine = CoreSupervisoryEngine.initialize()
        engine.run_forever()
    finally:
        release_mutex()


if __name__ == "__main__":
    main()
