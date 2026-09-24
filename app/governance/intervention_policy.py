"""Intervention Governance Policy & Actuator Interlocking (Spec 057).

Provides pure data structures and functions to govern automated interventions
over ASIC miners (Soft Auto-Restart, Hard Auto-Reboot, Fan Governor, Preset Balancer,
and Adaptive Elevator Contingency).
Supports global 'Vnish Libre' mode (read-only monitoring) as well as selective toggles,
with optional safety countdown timers for automatic reactivation.

All functions in this module are strictly deterministic and free of network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional, Tuple

ACTION_REBOOT_L1 = "reboot_l1"
ACTION_REBOOT_L2 = "reboot_l2"
ACTION_FAN_GOVERNOR = "fan_governor"
ACTION_PRESET_BALANCER = "preset_balancer"
ACTION_CONTINGENCY = "contingency"
ACTION_AUTOTUNE_WATCHDOG = "autotune_watchdog"

ALL_ACTIONS = frozenset({
    ACTION_REBOOT_L1,
    ACTION_REBOOT_L2,
    ACTION_FAN_GOVERNOR,
    ACTION_PRESET_BALANCER,
    ACTION_CONTINGENCY,
    ACTION_AUTOTUNE_WATCHDOG,
})


@dataclass(frozen=True)
class InterventionGovernance:
    """Immutable state container for intervention permissions."""
    master_enabled: bool = True          # False = Modo 'Vnish Libre' total (solo lectura)
    reboots_enabled: bool = True         # Auto-Restart Nivel 1 y Auto-Reboot Nivel 2
    governor_enabled: bool = True        # Fan Governor modulando PWM a 82°C
    contingency_enabled: bool = True     # Contingencia asimétrica adaptativa de elevadores
    presets_enabled: bool = True         # Preset Balancer dinámico
    expires_at_ts: Optional[float] = None # Timestamp epoch para reactivación automática
    disabled_reason: str = ""            # Ej: "manual_indefinite", "manual_timer_60m"

    def is_expired(self, now_ts: float) -> bool:
        """Check if temporary suppression timer has expired."""
        if self.expires_at_ts is None:
            return False
        return now_ts >= self.expires_at_ts

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> InterventionGovernance:
        if not data or not isinstance(data, dict):
            return cls()
        return cls(
            master_enabled=bool(data.get("master_enabled", True)),
            reboots_enabled=bool(data.get("reboots_enabled", True)),
            governor_enabled=bool(data.get("governor_enabled", True)),
            contingency_enabled=bool(data.get("contingency_enabled", True)),
            presets_enabled=bool(data.get("presets_enabled", True)),
            expires_at_ts=float(data["expires_at_ts"]) if data.get("expires_at_ts") is not None else None,
            disabled_reason=str(data.get("disabled_reason", "")),
        )


def should_allow_intervention(
    action_type: str,
    gov: InterventionGovernance,
    now_ts: float,
) -> Tuple[bool, str]:
    """Pure evaluation of whether an automated mutating action is allowed.
    
    Returns:
        (allowed: bool, reason: str)
    """
    # 1. Check timer expiration: if expired, master is effectively restored
    if gov.is_expired(now_ts):
        return True, "timer_expired_restored"

    # 2. Master switch overrides all actuators
    if not gov.master_enabled:
        return False, f"master_interventions_disabled:vnish_libre({gov.disabled_reason or 'manual'})"

    # 3. Check selective permissions
    if action_type in (ACTION_REBOOT_L1, ACTION_REBOOT_L2):
        if not gov.reboots_enabled:
            return False, "reboots_disabled"
    elif action_type == ACTION_FAN_GOVERNOR:
        if not gov.governor_enabled:
            return False, "fan_governor_disabled"
    elif action_type == ACTION_CONTINGENCY:
        if not gov.contingency_enabled:
            return False, "contingency_disabled"
    elif action_type == ACTION_PRESET_BALANCER:
        if not gov.presets_enabled:
            return False, "presets_disabled"
    elif action_type == ACTION_AUTOTUNE_WATCHDOG:
        if not gov.presets_enabled:
            return False, "presets_disabled"
        if not gov.reboots_enabled:
            return False, "reboots_disabled"

    return True, "allowed"


def apply_governance_toggle(
    gov: InterventionGovernance,
    target: str,
    now_ts: float,
    duration_seconds: Optional[float] = None,
) -> InterventionGovernance:
    """Return a new InterventionGovernance instance after applying a user toggle.
    
    Target options:
    - "all_off": Master disabled (Vnish Libre).
    - "all_on": Master enabled and all individual actuators enabled.
    - "toggle_reboots": Invert reboots_enabled.
    - "toggle_governor": Invert governor_enabled.
    - "toggle_contingency": Invert contingency_enabled.
    - "toggle_presets": Invert presets_enabled.
    - "timer": Set duration_seconds on current state.
    """
    expires_at = (now_ts + duration_seconds) if duration_seconds and duration_seconds > 0 else None
    reason_suffix = f"timer_{int(duration_seconds//60)}m" if expires_at else "manual"

    if target == "all_off":
        return InterventionGovernance(
            master_enabled=False,
            reboots_enabled=False,
            governor_enabled=False,
            contingency_enabled=False,
            presets_enabled=False,
            expires_at_ts=expires_at,
            disabled_reason=f"all_off_{reason_suffix}",
        )
    elif target == "all_on":
        return InterventionGovernance(
            master_enabled=True,
            reboots_enabled=True,
            governor_enabled=True,
            contingency_enabled=True,
            presets_enabled=True,
            expires_at_ts=None,
            disabled_reason="",
        )
    elif target == "toggle_reboots":
        new_val = not gov.reboots_enabled
        return InterventionGovernance(
            master_enabled=gov.master_enabled,
            reboots_enabled=new_val,
            governor_enabled=gov.governor_enabled,
            contingency_enabled=gov.contingency_enabled,
            presets_enabled=gov.presets_enabled,
            expires_at_ts=gov.expires_at_ts,
            disabled_reason=gov.disabled_reason,
        )
    elif target == "toggle_governor":
        new_val = not gov.governor_enabled
        return InterventionGovernance(
            master_enabled=gov.master_enabled,
            reboots_enabled=gov.reboots_enabled,
            governor_enabled=new_val,
            contingency_enabled=gov.contingency_enabled,
            presets_enabled=gov.presets_enabled,
            expires_at_ts=gov.expires_at_ts,
            disabled_reason=gov.disabled_reason,
        )
    elif target == "toggle_contingency":
        new_val = not gov.contingency_enabled
        return InterventionGovernance(
            master_enabled=gov.master_enabled,
            reboots_enabled=gov.reboots_enabled,
            governor_enabled=gov.governor_enabled,
            contingency_enabled=new_val,
            presets_enabled=gov.presets_enabled,
            expires_at_ts=gov.expires_at_ts,
            disabled_reason=gov.disabled_reason,
        )
    elif target == "toggle_presets":
        new_val = not gov.presets_enabled
        return InterventionGovernance(
            master_enabled=gov.master_enabled,
            reboots_enabled=gov.reboots_enabled,
            governor_enabled=gov.governor_enabled,
            contingency_enabled=gov.contingency_enabled,
            presets_enabled=new_val,
            expires_at_ts=gov.expires_at_ts,
            disabled_reason=gov.disabled_reason,
        )
    elif target == "timer":
        return InterventionGovernance(
            master_enabled=gov.master_enabled,
            reboots_enabled=gov.reboots_enabled,
            governor_enabled=gov.governor_enabled,
            contingency_enabled=gov.contingency_enabled,
            presets_enabled=gov.presets_enabled,
            expires_at_ts=expires_at,
            disabled_reason=f"timer_{int(duration_seconds//60)}m" if expires_at else "indefinite",
        )
    return gov


def format_governance_summary(gov: InterventionGovernance, now_ts: float) -> Tuple[str, str]:
    """Produce status badge and detailed text for Telegram cards.
    
    Returns:
        (badge: str, status_text: str)
    """
    if gov.is_expired(now_ts):
        return "🟢 ON", "🟢 ACTIVAS (Temporizador vencido -> restaurado)"

    if not gov.master_enabled:
        remaining_str = ""
        if gov.expires_at_ts:
            rem_m = int(max(0.0, gov.expires_at_ts - now_ts) // 60)
            remaining_str = f" (restan {rem_m}m)"
        return "🔴 LIBRE", f"🔴 DESACTIVADAS (Vnish Libre){remaining_str}"

    active_count = sum([
        gov.reboots_enabled,
        gov.governor_enabled,
        gov.contingency_enabled,
        gov.presets_enabled,
    ])
    if active_count == 4:
        return "🟢 ON", "🟢 ACTIVAS (Supervisión Total)"
    elif active_count == 0:
        return "🔴 LIBRE", "🔴 TODAS DESACTIVADAS"
    else:
        return "🟡 PARCIAL", f"🟡 PARCIAL ({active_count}/4 activos)"
