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
    }


# Public alias for unified serialization across the application
serialize_miner_state = _serialise_miner_state
