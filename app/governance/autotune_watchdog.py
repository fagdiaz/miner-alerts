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
import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

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


_logger = logging.getLogger("miner_alerts.autotune_watchdog")


def check_autotune_watchdog(
    miners: list,
    states: Dict[str, Any],
    state_lock: threading.Lock,
    config: dict,
    now_ts: float,
    send_telegram_fn: Optional[Callable] = None,
    bot_token: str = "",
    chat_id: str = "",
    qa_mode: bool = False,
    summaries: Optional[Dict[str, dict]] = None,
    log_fn: Optional[Callable[[str], None]] = None,
) -> list:
    """Supervises active miners for autotune stalls (Spec 078 / PROP-013 / QA Hardening / Spec 088).

    If any miner is stuck in 'auto-tuning' for > autotune_timeout_s (default 600s)
    with hashrate < 20 TH/s, steps down to safe preset with auto_restart_mining=True,
    locks hardware ceiling, and alerts Telegram.

    Single-pass parallel ingestion prevents port 80 socket exhaustion on ASIC control boards.
    """
    import app.miner_monitor as mm
    _log = log_fn or getattr(mm, "log", _logger.info)

    from app.governance._orchestrator_state import get_intervention_gov
    from app.governance.intervention_policy import ACTION_AUTOTUNE_WATCHDOG, should_allow_intervention
    from app.governance.elevator_budget import get_miner_max_hardware_preset, parse_preset_wattage
    from app.vnish.client import fetch_fleet_vnish_summaries, safe_set_miner_preset

    # Spec 057: Check intervention governance for Autotune Watchdog
    gov_obj = getattr(mm, "_GLOBAL_INTERVENTION_GOV", None) or get_intervention_gov()
    if gov_obj is not None:
        allowed, reason = should_allow_intervention(ACTION_AUTOTUNE_WATCHDOG, gov_obj, now_ts)
        if not allowed:
            return []

    timeout_s = float(config.get("autotune_timeout_s", 600.0))
    min_ths = float(config.get("autotune_min_active_hashrate_ths", 20.0))
    vnish_pw = str(config.get("vnish_api_password", "admin"))
    req_timeout = float(config.get("fan_governor_request_timeout", 2.5))

    autotune_state = getattr(mm, "_AUTOTUNE_WATCHDOG_STATE", None)
    facility_state = getattr(mm, "_FACILITY_BUDGET_STATE", None)

    # Single-pass ingestion: fetch all summaries in parallel if not pre-provided
    if summaries is None:
        hosts = [m.get("host") for m in miners if m.get("host")]
        summaries = fetch_fleet_vnish_summaries(hosts, timeout=req_timeout)

    stalls_handled = []
    for m_item in miners:
        m_host = m_item.get("host")
        m_name = m_item.get("name") or str(m_host)
        if not m_host:
            continue

        summary = summaries.get(m_host)
        if not summary:
            continue

        m_state = summary.get("miner_state", "")
        m_state_time = summary.get("miner_state_time", 0)
        hr_rt = summary.get("hr_realtime_ths", 0.0)

        hw_max = get_miner_max_hardware_preset(m_name, config=config)

        m_sk = f"{m_name}|{m_host}:{m_item.get('port', 4028)}"
        with state_lock:
            st = states.get(m_sk)
            curr_p = (
                getattr(st, "vnish_discovered_preset", None)
                or getattr(st, "balancer_preset", None)
                or m_item.get("target_power_w", "2700W")
            ) if st else "2700W"

        decision = evaluate_autotune_stall(
            miner_name=m_name,
            miner_state=m_state,
            miner_state_time=m_state_time,
            current_hashrate_ths=hr_rt,
            current_preset=str(curr_p),
            timeout_s=timeout_s,
            min_hashrate_ths=min_ths,
            max_hardware_preset=hw_max,
        )

        if decision.is_stalled and decision.action == ACTION_AUTOTUNE_STALLED:
            _log(f"[AUTOTUNE_WATCHDOG] STALL DETECTED on {m_name}: {decision.reason}")
            if autotune_state is not None:
                autotune_state.record_stall_rescue(
                    miner_name=m_name,
                    locked_preset=decision.safe_preset,
                    now_ts=now_ts,
                )
            # Record incident quiet on the elevator group to suppress secondary noise
            m_group = m_item.get("electrical_group") or m_item.get("group")
            if m_group and facility_state is not None:
                facility_state.record_group_incident(m_group, now_ts)

            if not qa_mode:
                ok_set, msg_set = safe_set_miner_preset(
                    m_host,
                    vnish_pw,
                    decision.safe_preset,
                    timeout=req_timeout,
                    clamp_top_preset=True,
                    top_preset=decision.safe_preset,
                    auto_restart_mining=True,
                )
                _log(f"[AUTOTUNE_WATCHDOG] Rescate aplicado a {m_name}: {curr_p} -> {decision.safe_preset} (ok={ok_set}, msg={msg_set})")
            else:
                ok_set = True
                msg_set = "qa_mode_simulated"

            if ok_set:
                if facility_state is not None:
                    facility_state.record_transition(m_name, decision.safe_preset, now_ts)
                with state_lock:
                    if st:
                        st.balancer_preset = decision.safe_preset
                        st.vnish_discovered_top_preset = decision.safe_preset
                        st.vnish_discovered_preset = decision.safe_preset
                        st.vnish_discovered_target_power_w = float(parse_preset_wattage(decision.safe_preset))
                        st.last_preset_change_ts = now_ts

                tg_fn = send_telegram_fn or getattr(mm, "send_telegram", None)
                if tg_fn:
                    tg_msg = (
                        f"🚨 *WATCHDOG: AUTOTUNE TRABADO RESCATADO*\n\n"
                        f"• Minero: *{m_name}* (Elevador: `{m_group or 'N/D'}`)\n"
                        f"• Problema: *Atrapado en auto-tuning durante {m_state_time}s* (> {timeout_s:.0f}s) a *{curr_p}* con hashrate {hr_rt:.2f} TH/s.\n"
                        f"• Causa física: Límite de silicio / falla de PLLs.\n"
                        f"• Acción de rescate: *Desescalado a {decision.safe_preset}* con reinicio de minado transaccional.\n"
                        f"• Protección: Cerrojo de hardware fijado en *{decision.safe_preset}* y ventana de reposo de 300s en elevador."
                    )
                    tg_fn(
                        bot_token,
                        str(chat_id),
                        tg_msg,
                        "CRITICAL",
                        f"autotune_stall_{m_name}",
                        is_command=True,
                    )
            stalls_handled.append(decision)

    return stalls_handled


execute_autotune_watchdog_cycle = check_autotune_watchdog
