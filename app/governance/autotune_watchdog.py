"""Autotune Stall Watchdog Governance Module (Spec 078 / PROP-013).

Supervises ASIC miners running VNish firmware to detect and resolve autotune stalls:
When a miner attempts a preset that exceeds its individual silicon capability (e.g. Miner 25 at 2700W),
it can remain trapped in 'auto-tuning' state indefinitely while consuming full rated wattage (2700W)
and delivering near-zero hashrate (0.0 TH/s).

This uncompensated reactive/inductive load creates continuous heating, line sag, and severe electrical
noise on the shared service drop and elevator transformers, leading to brownouts and cascade restarts.

The Watchdog detects:
  miner_state == 'auto-tuning' AND miner_state_time >= autotune_timeout_s (default 600s) AND hr_realtime < min_hashrate_ths (default 20.0 TH/s)

Upon detection:
  1. Identifies state as AUTOTUNE_STALLED.
  2. Steps down to safe preset (default 2500W or 2300W) with auto_restart_mining=True.
  3. Locks hardware ceiling in memory (hardware_ceiling_lock) to prevent re-escalation.
  4. Generates an explanatory Telegram alert.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any, Dict, List, Optional, Tuple

from app.governance.adaptive_contingency import normalize_miner_name
from app.governance.elevator_budget import parse_preset_wattage
from app.governance.preset_balancer import DEFAULT_PRESET_LADDER, find_preset_index

# Watchdog Constants
DEFAULT_AUTOTUNE_TIMEOUT_S: float = 600.0  # 10 minutes maximum allowed in auto-tuning without hashrate
DEFAULT_MIN_ACTIVE_HASHRATE_THS: float = 20.0  # Below 20 TH/s indicates failed PLL/clock locking
DEFAULT_SAFE_STEPDOWN_PRESET: str = "2500W"

ACTION_AUTOTUNE_OK = "AUTOTUNE_OK"
ACTION_AUTOTUNE_STALLED = "AUTOTUNE_STALLED"
ACTION_AUTOTUNE_ACTIVE_MINING = "AUTOTUNE_ACTIVE_MINING"


@dataclass(frozen=True)
class AutotuneStallDecision:
    """Outcome of evaluating whether a miner is stalled in autotuning."""
    action: str
    miner_name: str
    is_stalled: bool
    miner_state: str
    elapsed_seconds: int
    current_hashrate_ths: float
    current_preset: str
    safe_preset: str
    reason: str
    requires_step_down: bool


def determine_safe_rescue_preset(
    current_preset: str,
    max_hardware_preset: Optional[str] = None,
    default_fallback: str = DEFAULT_SAFE_STEPDOWN_PRESET,
) -> str:
    """Determine the safe step-down preset to rescue a stalled miner.
    
    If at 2700W or higher -> steps down to 2500W (or max_hardware_preset if lower).
    If already at 2500W -> steps down to 2300W.
    """
    curr_w = parse_preset_wattage(current_preset)
    if max_hardware_preset:
        hw_w = parse_preset_wattage(max_hardware_preset)
        if curr_w > hw_w:
            return max_hardware_preset

    if curr_w >= 2700:
        return "2500W"
    elif curr_w >= 2500:
        return "2300W"
    elif curr_w >= 2300:
        return "2150W"
    return "2000W"


def evaluate_autotune_stall(
    miner_name: str,
    miner_state: str,
    miner_state_time: int,
    current_hashrate_ths: float,
    current_preset: str,
    timeout_s: float = DEFAULT_AUTOTUNE_TIMEOUT_S,
    min_hashrate_ths: float = DEFAULT_MIN_ACTIVE_HASHRATE_THS,
    max_hardware_preset: Optional[str] = None,
) -> AutotuneStallDecision:
    """Pure evaluation of whether an ASIC is trapped in autotuning stall.
    
    Conditions for AUTOTUNE_STALLED:
    - miner_state is 'auto-tuning' (or contains 'tune' / 'tuning')
    - continuous time in state >= timeout_s (600s)
    - realtime hashrate < min_hashrate_ths (20.0 TH/s)
    
    Note: If a miner is in 'auto-tuning' but producing healthy hashrate
    (e.g. 95-102 TH/s like Miner 24), it is actively hashing and NOT stalled.
    """
    st_clean = str(miner_state).strip().lower()
    is_tuning = "tune" in st_clean or "tuning" in st_clean

    if not is_tuning:
        return AutotuneStallDecision(
            action=ACTION_AUTOTUNE_OK,
            miner_name=miner_name,
            is_stalled=False,
            miner_state=miner_state,
            elapsed_seconds=miner_state_time,
            current_hashrate_ths=current_hashrate_ths,
            current_preset=current_preset,
            safe_preset=current_preset,
            reason=f"Minero en estado normal '{miner_state}', autotuning inactivo",
            requires_step_down=False,
        )

    # In tuning: check if it's actively mining while tuning
    if current_hashrate_ths >= min_hashrate_ths:
        return AutotuneStallDecision(
            action=ACTION_AUTOTUNE_ACTIVE_MINING,
            miner_name=miner_name,
            is_stalled=False,
            miner_state=miner_state,
            elapsed_seconds=miner_state_time,
            current_hashrate_ths=current_hashrate_ths,
            current_preset=current_preset,
            safe_preset=current_preset,
            reason=(
                f"Autotune activo pero hasheando con normalidad: {current_hashrate_ths:.1f} TH/s >= {min_hashrate_ths:.1f} TH/s "
                f"({miner_state_time}s transcurridos)"
            ),
            requires_step_down=False,
        )

    # In tuning and hashrate is below threshold: check elapsed time
    if miner_state_time < timeout_s:
        rem_s = max(0, int(timeout_s - miner_state_time))
        return AutotuneStallDecision(
            action=ACTION_AUTOTUNE_OK,
            miner_name=miner_name,
            is_stalled=False,
            miner_state=miner_state,
            elapsed_seconds=miner_state_time,
            current_hashrate_ths=current_hashrate_ths,
            current_preset=current_preset,
            safe_preset=current_preset,
            reason=(
                f"Autotune en ventana permitida ({miner_state_time}s/{timeout_s:.0f}s, restan {rem_s}s). "
                f"Hashrate transitorio: {current_hashrate_ths:.1f} TH/s"
            ),
            requires_step_down=False,
        )

    # STALLED!
    safe_preset = determine_safe_rescue_preset(
        current_preset=current_preset,
        max_hardware_preset=max_hardware_preset,
    )
    return AutotuneStallDecision(
        action=ACTION_AUTOTUNE_STALLED,
        miner_name=miner_name,
        is_stalled=True,
        miner_state=miner_state,
        elapsed_seconds=miner_state_time,
        current_hashrate_ths=current_hashrate_ths,
        current_preset=current_preset,
        safe_preset=safe_preset,
        reason=(
            f"AUTOTUNE_STALLED: {miner_name} atrapado en autotuning durante {miner_state_time}s (> {timeout_s:.0f}s) "
            f"a {current_preset} con hashrate nulo/crítico ({current_hashrate_ths:.2f} TH/s < {min_hashrate_ths:.1f} TH/s). "
            f"Falla de sincronización PLL de silicio. Rescate defensivo a {safe_preset} con recarga transaccional."
        ),
        requires_step_down=True,
    )


class LockStatus(tuple):
    """Tuple containing (is_locked, locked_preset) with intuitive boolean evaluation."""
    def __new__(cls, is_locked: bool, preset: Optional[str] = None):
        return super().__new__(cls, (bool(is_locked), preset))

    def __bool__(self) -> bool:
        return bool(self[0])


@dataclass
class AutotuneWatchdogState:
    """Maintains state of autotune stall watchdog and hardware locks."""
    stalled_miners: Dict[str, bool] = field(default_factory=dict)
    hardware_ceiling_locks: Dict[str, str] = field(default_factory=dict)
    last_rescue_ts: Dict[str, float] = field(default_factory=dict)

    def record_stall_rescue(self, miner_name: str, locked_preset: str, now_ts: float) -> None:
        norm = normalize_miner_name(miner_name)
        self.stalled_miners[norm] = True
        self.hardware_ceiling_locks[norm] = locked_preset
        self.last_rescue_ts[norm] = float(now_ts)

    def is_hardware_locked(self, miner_name: str) -> LockStatus:
        norm = normalize_miner_name(miner_name)
        if norm in self.hardware_ceiling_locks:
            return LockStatus(True, self.hardware_ceiling_locks[norm])
        return LockStatus(False, None)

    def get_locked_preset(self, miner_name: str) -> Optional[str]:
        norm = normalize_miner_name(miner_name)
        return self.hardware_ceiling_locks.get(norm)

    def clear_lock(self, miner_name: str) -> None:
        norm = normalize_miner_name(miner_name)
        self.stalled_miners.pop(norm, None)
        self.hardware_ceiling_locks.pop(norm, None)
        self.last_rescue_ts.pop(norm, None)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stalled_miners": dict(self.stalled_miners),
            "hardware_ceiling_locks": dict(self.hardware_ceiling_locks),
            "last_rescue_ts": dict(self.last_rescue_ts),
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> AutotuneWatchdogState:
        if not data or not isinstance(data, dict):
            return cls()
        return cls(
            stalled_miners={str(k): bool(v) for k, v in data.get("stalled_miners", {}).items()},
            hardware_ceiling_locks={str(k): str(v) for k, v in data.get("hardware_ceiling_locks", {}).items()},
            last_rescue_ts={str(k): float(v) for k, v in data.get("last_rescue_ts", {}).items()},
        )
