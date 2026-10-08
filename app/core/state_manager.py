"""State Manager — Atomic persistence and in-memory state container (Spec 060).

Wraps the atomic two-phase commit pattern (_build_state_payload / _flush_state_payload)
already implemented in miner_monitor.py, exposing a clean object-oriented interface for
Spec 060 and future migration of main() toward a dependency-injected architecture.

Design invariants:
  - Lock hierarchy: state_lock (L1, memory) -> _SAVE_STATE_LOCK (L2, disk I/O).
  - The snapshot (payload build) occurs inside state_lock.
  - The disk flush (json.dumps + fsync + os.replace) occurs outside state_lock, under
    _SAVE_STATE_LOCK only. This eliminates 10-200ms NTFS fsync hold on the memory lock.
  - StateManager is thread-safe when state_lock is a threading.RLock shared with main().

All functions in this module are compatible with the existing miner_monitor.py globals
and do NOT import from miner_monitor to avoid circular dependencies.
"""

from __future__ import annotations

import json
import os
import shutil
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# ---------------------------------------------------------------------------
# Re-export the disk-level lock so callers can share the same singleton.
# miner_monitor.py owns the canonical _SAVE_STATE_LOCK; we do NOT redefine it
# here to avoid creating a second independent lock.  StateManager.flush_payload()
# must be called with the lock already held OR uses _SAVE_STATE_LOCK directly
# via the module-level helper below.
# ---------------------------------------------------------------------------

_STATE_MANAGER_FLUSH_LOCK = threading.Lock()
"""Dedicated flush lock for StateManager instances.

When StateManager is created independently (e.g. in tests), it uses this lock.
When used inside miner_monitor.py, callers should pass flush_lock=_SAVE_STATE_LOCK
at construction time so both share the same exclusion region.
"""


class StateManager:
    """Atomic state persistence manager for a fleet of MinerState objects.

    Usage pattern (inside main()):
        sm = StateManager(state_path, state_lock, flush_lock=_SAVE_STATE_LOCK)
        # Build payload under state_lock, flush to disk outside state_lock:
        with state_lock:
            payload = sm.build_payload(states, last_update_id)
        sm.flush_payload(state_path, payload)

    Or use the convenience method that does both atomically:
        sm.save(states, last_update_id)
    """

    def __init__(
        self,
        state_path: Path,
        state_lock: threading.RLock,
        flush_lock: Optional[threading.Lock] = None,
        get_globals_fn: Optional[Any] = None,
    ) -> None:
        """
        Args:
            state_path: Absolute path to state.json.
            state_lock: Shared RLock that guards the in-memory ``states`` dict (L1).
            flush_lock: Lock for disk I/O (L2). Defaults to _STATE_MANAGER_FLUSH_LOCK.
                        Pass miner_monitor._SAVE_STATE_LOCK when integrating with main().
            get_globals_fn: Optional callable() -> dict for snapshotting module globals
                            (_GLOBAL_INTERVENTION_GOV, _ELEVATOR_CONTINGENCY_STATES, etc.).
                            When None, intervention governance and contingency are omitted.
        """
        self._state_path = state_path
        self._state_lock = state_lock
        self._flush_lock = flush_lock if flush_lock is not None else _STATE_MANAGER_FLUSH_LOCK
        self._get_globals = get_globals_fn

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(
        self,
        states: Dict[str, Any],
        last_update_id: Optional[int],
        last_daily_digest_date: Optional[str] = None,
    ) -> None:
        """Build the state payload under state_lock and flush to disk outside it.

        This is the preferred atomic save method.  It minimises the time state_lock
        is held by releasing it before the expensive os.fsync call.
        """
        with self._state_lock:
            payload = self.build_payload(states, last_update_id, last_daily_digest_date)
        # state_lock released here — disk I/O runs under flush_lock only
        self.flush_payload(self._state_path, payload)

    def build_payload(
        self,
        states: Dict[str, Any],
        last_update_id: Optional[int],
        last_daily_digest_date: Optional[str] = None,
    ) -> dict:
        """Snapshot states + governance into a serialisable dict.

        MUST be called while state_lock is held by the caller.
        Does NOT perform any disk I/O.
        """
        g = self._get_globals() if self._get_globals is not None else {}
        gov_obj = g.get("_GLOBAL_INTERVENTION_GOV")
        cont_states = g.get("_ELEVATOR_CONTINGENCY_STATES") or {}
        sch_win = g.get("_ACTIVE_SCHEDULED_WINDOW")

        payload: Dict[str, Any] = {
            "saved_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
            "last_update_id": last_update_id,
            "last_daily_digest_date": last_daily_digest_date,
            "scheduled_maintenance": sch_win.to_dict() if sch_win is not None else None,
            "intervention_governance": gov_obj.to_dict() if gov_obj is not None else None,
            "elevator_contingency": (
                {grp: s.to_dict() for grp, s in cont_states.items()}
                if cont_states else None
            ),
            "states": {},
        }

        for key, state in list(states.items()):
            payload["states"][key] = _serialise_miner_state(state)

        return payload

    def flush_payload(self, state_path: Path, payload: dict) -> None:
        """Write payload to disk atomically (.tmp → .bak → os.replace).

        May be called WITHOUT state_lock held.  Acquires flush_lock internally.
        """
        tmp_path = state_path.with_suffix(".tmp")
        bak_path = state_path.with_suffix(".bak")
        with self._flush_lock:
            try:
                content = json.dumps(payload, indent=2)
                with open(tmp_path, "w", encoding="utf-8") as f:
                    f.write(content)
                    f.flush()
                    os.fsync(f.fileno())
                if state_path.exists():
                    try:
                        shutil.copyfile(state_path, bak_path)
                    except Exception:
                        pass
                os.replace(tmp_path, state_path)
            except Exception:
                # Non-fatal: state will be saved on next tick
                pass

    def get_state(self, states: Dict[str, Any], key: str) -> Optional[Any]:
        """Thread-safe read of a single MinerState by key."""
        with self._state_lock:
            return states.get(key)

    def update_state(self, states: Dict[str, Any], key: str, **kwargs: Any) -> Optional[Any]:
        """Thread-safe mutation of a MinerState's fields by keyword.

        Returns the mutated state, or None if key not found.
        """
        with self._state_lock:
            state = states.get(key)
            if state is None:
                return None
            for attr, value in kwargs.items():
                setattr(state, attr, value)
            return state

    @staticmethod
    def serialize_miner_state(state: Any) -> Dict[str, Any]:
        """Convert a MinerState instance to a JSON-serialisable dict (Spec 072)."""
        return _serialise_miner_state(state)


# ---------------------------------------------------------------------------
# Internal helper — mirrors _build_state_payload field list in miner_monitor.py
# ---------------------------------------------------------------------------

def _serialise_miner_state(state: Any) -> Dict[str, Any]:
    """Convert a MinerState instance to a JSON-serialisable dict.

    Mirrors the field list in miner_monitor._build_state_payload exactly so
    that state.json round-trips are identical whether written by the legacy
    function or by StateManager.
    """
    return {
        "state": state.state,
        "low_streak": state.low_streak,
        "offline_streak": state.offline_streak,
        "ok_streak": state.ok_streak,
        "initialized": state.initialized,
        "last_elapsed": state.last_elapsed,
        "last_seen_ts": state.last_seen_ts,
        "reboot_pending_until": state.reboot_pending_until,
        "reboot_pending_reason": state.reboot_pending_reason,
        "reboot_pending_elapsed": state.reboot_pending_elapsed,
        "last_reboot_ts": state.last_reboot_ts,
        "low_since_ts": state.low_since_ts,
        "hashboard_since_ts": getattr(state, "hashboard_since_ts", None),
        "last_manual_reboot_ts": state.last_manual_reboot_ts,
        "last_auto_reboot_ts": state.last_auto_reboot_ts,
        "last_preset_change_ts": getattr(state, "last_preset_change_ts", None),
        "last_auto_restart_ts": getattr(state, "last_auto_restart_ts", None),
        "auto_restart_count": getattr(state, "auto_restart_count", 0),
        "auto_reboot_timestamps": list(getattr(state, "auto_reboot_timestamps", None) or []),
        "degraded_mode": state.degraded_mode,
        "last_hourly_status_ts": state.last_hourly_status_ts,
        "snooze_until_ts": state.snooze_until_ts,
        "cooling_streak": getattr(state, "cooling_streak", 0),
        "last_cooling_warning_ts": getattr(state, "last_cooling_warning_ts", None),
        "efficiency_streak": getattr(state, "efficiency_streak", 0),
        "last_efficiency_warning_ts": getattr(state, "last_efficiency_warning_ts", None),
        "baseline_frequency_mhz": getattr(state, "baseline_frequency_mhz", None),
        "last_preset_warning_ts": getattr(state, "last_preset_warning_ts", None),
        "chain_warnings_ts": dict(getattr(state, "chain_warnings_ts", None) or {}),
        # Spec 039: Fan Governor
        "governor_duty": getattr(state, "governor_duty", None),
        "governor_holds": getattr(state, "governor_holds", 0),
        "governor_last_change_ts": getattr(state, "governor_last_change_ts", 0.0),
        "governor_failures": getattr(state, "governor_failures", 0),
        "governor_last_action": getattr(state, "governor_last_action", ""),
        "governor_last_temp_c": getattr(state, "governor_last_temp_c", None),
        "governor_last_power_w": getattr(state, "governor_last_power_w", None),
        "governor_recovery_since_ts": getattr(state, "governor_recovery_since_ts", None),
        # Spec 040: Dynamic Preset Balancer
        "balancer_preset": getattr(state, "balancer_preset", None),
        "balancer_last_change_ts": getattr(state, "balancer_last_change_ts", 0.0),
        "balancer_last_action": getattr(state, "balancer_last_action", ""),
        "balancer_last_reason": getattr(state, "balancer_last_reason", ""),
        # Spec 062: HW Error Tripwire & Anti-Cascade Lock
        "hw_error_lock_until_ts": getattr(state, "hw_error_lock_until_ts", None),
        "hw_error_locked_preset": getattr(state, "hw_error_locked_preset", None),
        # Dynamic Vnish Overclock & Autoswitch State Discovery
        "vnish_discovered_target_power_w": getattr(state, "vnish_discovered_target_power_w", None),
        "vnish_discovered_preset": getattr(state, "vnish_discovered_preset", None),
        "vnish_discovered_top_preset": getattr(state, "vnish_discovered_top_preset", None),
        "vnish_discovered_switcher_enabled": getattr(state, "vnish_discovered_switcher_enabled", None),
        "vnish_discovered_ts": getattr(state, "vnish_discovered_ts", 0.0),
        # Spec 044: Silent Mode
        "silent_mode_active": getattr(state, "silent_mode_active", False),
        "silent_mode_revert_ts": getattr(state, "silent_mode_revert_ts", None),
        "silent_mode_prev_duty": getattr(state, "silent_mode_prev_duty", None),
        "silent_mode_prev_preset": getattr(state, "silent_mode_prev_preset", None),
        "silent_mode_target_max_duty": getattr(state, "silent_mode_target_max_duty", 50),
        # Spec 048: Safe Fleet Shutdown & Maintenance Mode
        "is_shutdown_maintenance": getattr(state, "is_shutdown_maintenance", False),
        "shutdown_maintenance_ts": getattr(state, "shutdown_maintenance_ts", 0.0),
        # Spec 046: Live Telemetry Snapshot
        "last_rate_ths": getattr(state, "last_rate_ths", None),
        "last_active_boards": getattr(state, "last_active_boards", None),
        "last_expected_boards": getattr(state, "last_expected_boards", None),
        "last_max_chip_temp": getattr(state, "last_max_chip_temp", None),
        "last_fan_duty_percent": getattr(state, "last_fan_duty_percent", None),
        "last_power_w": getattr(state, "last_power_w", None),
        "last_efficiency_j_th": getattr(state, "last_efficiency_j_th", None),
        "last_responded": getattr(state, "last_responded", False),
        "inlet_temp_c": getattr(state, "inlet_temp_c", None),
        # Spec 075: Soft-Landing Recovery & APW12 Latch-Off Defense
        "stopped_since_ts": getattr(state, "stopped_since_ts", None),
        "is_pre_clamped": getattr(state, "is_pre_clamped", False),
        "original_preset_before_clamp": getattr(state, "original_preset_before_clamp", None),
        "staged_ramp_up_pending": getattr(state, "staged_ramp_up_pending", False),
        "staged_ramp_up_soak_start_ts": getattr(state, "staged_ramp_up_soak_start_ts", None),
        # P0 Thermal Tripwire Hardware Protection
        "last_thermal_downstep_ts": getattr(state, "last_thermal_downstep_ts", 0.0),
        "last_thermal_pause_ts": getattr(state, "last_thermal_pause_ts", 0.0),
        "thermal_pause_until_ts": getattr(state, "thermal_pause_until_ts", None),
        "thermal_lockout_until_ts": getattr(state, "thermal_lockout_until_ts", None),
        # Spec 081: Pending Preset Restart Watchdog
        "vnish_restart_required": getattr(state, "vnish_restart_required", False),
        "vnish_restart_detected_ts": getattr(state, "vnish_restart_detected_ts", None),
        "last_preset_restart_ts": getattr(state, "last_preset_restart_ts", None),
    }


# Public alias for unified serialization across the application
serialize_miner_state = _serialise_miner_state

_SAVE_STATE_LOCK = threading.Lock()
_LAST_DAILY_DIGEST_DATE: Optional[str] = None


def _build_state_payload(
    states: Dict[str, Any],
    last_update_id: Optional[int],
    last_daily_digest_date: Optional[str] = None,
) -> dict:
    """Snapshot states + governance into a serialisable payload dictionary."""
    global _LAST_DAILY_DIGEST_DATE
    if last_daily_digest_date is not None:
        _LAST_DAILY_DIGEST_DATE = last_daily_digest_date

    from app.core.system import now_str
    from app.governance._orchestrator_state import (
        get_intervention_gov,
        get_elevator_contingency_states,
        get_scheduled_window,
        get_facility_budget_state,
        get_autotune_watchdog_state,
    )

    sch_win = get_scheduled_window()
    gov_obj = get_intervention_gov()
    cont_states = get_elevator_contingency_states()
    fac_budget = get_facility_budget_state()
    at_watchdog = get_autotune_watchdog_state()

    payload = {
        "saved_at": now_str(),
        "last_update_id": last_update_id,
        "last_daily_digest_date": _LAST_DAILY_DIGEST_DATE,
        "scheduled_maintenance": sch_win.to_dict() if sch_win is not None else None,
        "intervention_governance": gov_obj.to_dict() if gov_obj is not None else None,
        "elevator_contingency": {grp: s.to_dict() for grp, s in list(cont_states.items())} if cont_states else None,
        "facility_budget": fac_budget.to_dict() if fac_budget is not None else None,
        "autotune_watchdog": at_watchdog.to_dict() if at_watchdog is not None else None,
        "states": {},
    }

    for key, state in list(states.items()):
        payload["states"][key] = _serialise_miner_state(state)
    return payload


def _flush_state_payload(state_path: Path, payload: dict) -> None:
    """Atomically write the payload to disk (.tmp -> .bak -> replace)."""
    from app.core.config import log
    tmp_path = state_path.with_suffix(".tmp")
    bak_path = state_path.with_suffix(".bak")
    with _SAVE_STATE_LOCK:
        try:
            content = json.dumps(payload, indent=2)
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            if state_path.exists():
                try:
                    shutil.copyfile(state_path, bak_path)
                except Exception:
                    pass
            os.replace(tmp_path, state_path)
        except Exception:
            log("[WARN] No se pudo guardar state.json.")


def save_state(
    state_path: Path,
    states: Dict[str, Any],
    last_update_id: Optional[int],
    last_daily_digest_date: Optional[str] = None,
) -> None:
    """Save the supervisory state atomically to disk."""
    payload = _build_state_payload(states, last_update_id, last_daily_digest_date)
    _flush_state_payload(state_path, payload)


def load_state(state_path: Path) -> Tuple[Dict[str, Any], Optional[int]]:
    """Load and deserialize fleet and governance states from state.json."""
    global _LAST_DAILY_DIGEST_DATE
    from datetime import datetime
    from app.core.config import log
    from app.core.models import MinerState
    from app.core.reboot_safety import STATE_OK

    if not state_path.exists():
        return {}, None
    bak_path = state_path.with_suffix(".bak")
    raw = None
    try:
        content = state_path.read_text(encoding="utf-8").strip()
        if not content or content.replace("\x00", "") == "":
            raise ValueError("empty or null-byte corrupted file")
        raw = json.loads(content)
    except Exception as primary_exc:
        log(f"[WARN] state.json corrupto o ilegible ({primary_exc}). Intentando recuperar desde .bak...")
        if bak_path.exists():
            try:
                bak_content = bak_path.read_text(encoding="utf-8").strip()
                if bak_content and bak_content.replace("\x00", "") != "":
                    raw = json.loads(bak_content)
                    log("[INFO] Estado restaurado exitosamente desde state.json.bak")
            except Exception as bak_exc:
                log(f"[WARN] state.json.bak también corrupto o ilegible ({bak_exc}).")
        if raw is None:
            log("[WARN] state.json corrupto. Se ignora.")
            return {}, None

    try:
        _LAST_DAILY_DIGEST_DATE = raw.get("last_daily_digest_date")
        saved_at = raw.get("saved_at")
        if saved_at:
            try:
                saved_dt = datetime.strptime(saved_at, "%Y-%m-%d %H:%M:%S")
                if (datetime.now() - saved_dt).total_seconds() > 48 * 3600:
                    log("[WARN] state.json esta stale (>48h). Se ignora.")
                    return {}, None
            except Exception:
                pass
        states = {}
        raw_states = raw.get("states", {})
        for key, data in raw_states.items():
            raw_auto = data.get("auto_reboot_timestamps", [])
            if not isinstance(raw_auto, list):
                raw_auto = []
            auto_list = []
            for ts in raw_auto:
                try:
                    auto_list.append(float(ts))
                except (TypeError, ValueError):
                    continue
            state = MinerState(
                low_streak=0,
                offline_streak=int(data.get("offline_streak", 0)),
                ok_streak=int(data.get("ok_streak", 0)),
                state=str(data.get("state", STATE_OK)),
                initialized=bool(data.get("initialized", False)),
                last_elapsed=data.get("last_elapsed"),
                last_seen_ts=float(data.get("last_seen_ts", 0.0)),
                reboot_pending_until=float(data.get("reboot_pending_until", 0.0)),
                reboot_pending_reason=str(data.get("reboot_pending_reason", "")),
                reboot_pending_elapsed=data.get("reboot_pending_elapsed"),
                last_reboot_ts=float(data.get("last_reboot_ts", 0.0)),
                low_since_ts=None,
                hashboard_since_ts=None,
                last_manual_reboot_ts=(
                    float(data.get("last_manual_reboot_ts"))
                    if data.get("last_manual_reboot_ts") is not None
                    else None
                ),
                last_auto_reboot_ts=(
                    float(data.get("last_auto_reboot_ts"))
                    if data.get("last_auto_reboot_ts") is not None
                    else None
                ),
                last_preset_change_ts=(
                    float(data.get("last_preset_change_ts"))
                    if data.get("last_preset_change_ts") is not None
                    else None
                ),
                last_auto_restart_ts=(
                    float(data.get("last_auto_restart_ts"))
                    if data.get("last_auto_restart_ts") is not None
                    else None
                ),
                auto_restart_count=int(data.get("auto_restart_count", 0)),
                auto_reboot_timestamps=auto_list,
                degraded_mode=bool(data.get("degraded_mode", False)),
                last_hourly_status_ts=(
                    float(data.get("last_hourly_status_ts"))
                    if data.get("last_hourly_status_ts") is not None
                    else None
                ),
                snooze_until_ts=(
                    float(data.get("snooze_until_ts"))
                    if data.get("snooze_until_ts") is not None
                    else None
                ),
                cooling_streak=int(data.get("cooling_streak", 0)),
                last_cooling_warning_ts=(
                    float(data.get("last_cooling_warning_ts"))
                    if data.get("last_cooling_warning_ts") is not None
                    else None
                ),
                efficiency_streak=int(data.get("efficiency_streak", 0)),
                last_efficiency_warning_ts=(
                    float(data.get("last_efficiency_warning_ts"))
                    if data.get("last_efficiency_warning_ts") is not None
                    else None
                ),
                baseline_frequency_mhz=(
                    float(data.get("baseline_frequency_mhz"))
                    if data.get("baseline_frequency_mhz") is not None
                    else None
                ),
                last_preset_warning_ts=(
                    float(data.get("last_preset_warning_ts"))
                    if data.get("last_preset_warning_ts") is not None
                    else None
                ),
                chain_warnings_ts=dict(data.get("chain_warnings_ts") or {}),
                governor_duty=data.get("governor_duty"),
                governor_holds=int(data.get("governor_holds", 0)),
                governor_last_change_ts=float(data.get("governor_last_change_ts", 0.0)),
                governor_failures=int(data.get("governor_failures", 0)),
                governor_last_action=str(data.get("governor_last_action", "")),
                governor_last_temp_c=(
                    float(data.get("governor_last_temp_c"))
                    if data.get("governor_last_temp_c") is not None
                    else None
                ),
                governor_last_power_w=(
                    float(data.get("governor_last_power_w"))
                    if data.get("governor_last_power_w") is not None
                    else None
                ),
                governor_recovery_since_ts=(
                    float(data.get("governor_recovery_since_ts"))
                    if data.get("governor_recovery_since_ts") is not None
                    else None
                ),
                balancer_preset=data.get("balancer_preset"),
                balancer_last_change_ts=float(data.get("balancer_last_change_ts", 0.0)),
                balancer_last_action=str(data.get("balancer_last_action", "")),
                balancer_last_reason=str(data.get("balancer_last_reason", "")),
                hw_error_lock_until_ts=(
                    float(data.get("hw_error_lock_until_ts"))
                    if data.get("hw_error_lock_until_ts") is not None
                    else None
                ),
                hw_error_locked_preset=data.get("hw_error_locked_preset"),
                vnish_discovered_target_power_w=(
                    float(data.get("vnish_discovered_target_power_w"))
                    if data.get("vnish_discovered_target_power_w") is not None
                    else None
                ),
                vnish_discovered_preset=data.get("vnish_discovered_preset"),
                vnish_discovered_top_preset=data.get("vnish_discovered_top_preset"),
                vnish_discovered_switcher_enabled=data.get("vnish_discovered_switcher_enabled"),
                vnish_discovered_ts=float(data.get("vnish_discovered_ts", 0.0)),
                silent_mode_active=bool(data.get("silent_mode_active", False)),
                silent_mode_revert_ts=(
                    float(data.get("silent_mode_revert_ts"))
                    if data.get("silent_mode_revert_ts") is not None
                    else None
                ),
                silent_mode_prev_duty=data.get("silent_mode_prev_duty"),
                silent_mode_prev_preset=data.get("silent_mode_prev_preset"),
                silent_mode_target_max_duty=int(data.get("silent_mode_target_max_duty", 50)),
                is_shutdown_maintenance=bool(data.get("is_shutdown_maintenance", False)),
                shutdown_maintenance_ts=float(data.get("shutdown_maintenance_ts", 0.0)),
                last_rate_ths=(
                    float(data.get("last_rate_ths"))
                    if data.get("last_rate_ths") is not None
                    else None
                ),
                last_active_boards=(
                    int(data.get("last_active_boards"))
                    if data.get("last_active_boards") is not None
                    else None
                ),
                last_expected_boards=(
                    int(data.get("last_expected_boards"))
                    if data.get("last_expected_boards") is not None
                    else None
                ),
                last_max_chip_temp=(
                    float(data.get("last_max_chip_temp"))
                    if data.get("last_max_chip_temp") is not None
                    else None
                ),
                last_fan_duty_percent=(
                    float(data.get("last_fan_duty_percent"))
                    if data.get("last_fan_duty_percent") is not None
                    else None
                ),
                last_power_w=(
                    float(data.get("last_power_w"))
                    if data.get("last_power_w") is not None
                    else None
                ),
                last_efficiency_j_th=(
                    float(data.get("last_efficiency_j_th"))
                    if data.get("last_efficiency_j_th") is not None
                    else None
                ),
                last_responded=bool(data.get("last_responded", False)),
                inlet_temp_c=(
                    float(data.get("inlet_temp_c"))
                    if data.get("inlet_temp_c") is not None
                    else None
                ),
                stopped_since_ts=(
                    float(data.get("stopped_since_ts"))
                    if data.get("stopped_since_ts") is not None
                    else None
                ),
                is_pre_clamped=bool(data.get("is_pre_clamped", False)),
                original_preset_before_clamp=data.get("original_preset_before_clamp"),
                staged_ramp_up_pending=bool(data.get("staged_ramp_up_pending", False)),
                staged_ramp_up_soak_start_ts=(
                    float(data.get("staged_ramp_up_soak_start_ts"))
                    if data.get("staged_ramp_up_soak_start_ts") is not None
                    else None
                ),
                last_thermal_downstep_ts=float(data.get("last_thermal_downstep_ts", 0.0)),
                last_thermal_pause_ts=float(data.get("last_thermal_pause_ts", 0.0)),
                thermal_pause_until_ts=(
                    float(data.get("thermal_pause_until_ts"))
                    if data.get("thermal_pause_until_ts") is not None
                    else None
                ),
                thermal_lockout_until_ts=(
                    float(data.get("thermal_lockout_until_ts"))
                    if data.get("thermal_lockout_until_ts") is not None
                    else None
                ),
                vnish_restart_required=bool(data.get("vnish_restart_required", False)),
                vnish_restart_detected_ts=(
                    float(data.get("vnish_restart_detected_ts"))
                    if data.get("vnish_restart_detected_ts") is not None
                    else None
                ),
                last_preset_restart_ts=(
                    float(data.get("last_preset_restart_ts"))
                    if data.get("last_preset_restart_ts") is not None
                    else None
                ),
            )
            states[key] = state

        from app.governance._orchestrator_state import (
            set_intervention_gov,
            set_elevator_contingency_states,
            set_scheduled_window,
        )
        from app.governance.intervention_policy import InterventionGovernance
        from app.governance.adaptive_contingency import GroupContingencyState
        from app.governance.maintenance_scheduler import ScheduledWindow

        ig_data = raw.get("intervention_governance")
        if ig_data and isinstance(ig_data, dict):
            try:
                set_intervention_gov(InterventionGovernance.from_dict(ig_data))
            except Exception:
                pass

        ec_data = raw.get("elevator_contingency")
        if ec_data and isinstance(ec_data, dict):
            try:
                c_states = {
                    grp: GroupContingencyState.from_dict(s)
                    for grp, s in ec_data.items()
                    if isinstance(s, dict)
                }
                set_elevator_contingency_states(c_states)
            except Exception:
                pass

        sm_data = raw.get("scheduled_maintenance")
        if sm_data and isinstance(sm_data, dict):
            try:
                set_scheduled_window(ScheduledWindow.from_dict(sm_data))
            except Exception:
                pass

        return states, raw.get("last_update_id")
    except Exception as exc:
        log(f"[WARN] Error al procesar state.json ({exc}). Se inicia con estado limpio.")
        return {}, None
