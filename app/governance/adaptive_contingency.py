"""Adaptive Elevator Contingency & Canary Throttle Module (Spec 057).

Implements asymmetric electrical contingency per elevator group to protect against
morning grid voltage sags and tap-changer brownouts without degrading the entire fleet.

Key Principles:
1. Relative to Current State: Never assumes 2700W as fixed baseline; measures current preset.
2. Canary Miner First: Each elevator group designates a canary miner (more sensitive to voltage/I2C).
   On initial restart in the group, ONLY the canary drops 1 preset tier. The robust partner is untouched.
3. Limit Exploration: If the canary restarts again at reduced power, it steps down further (e.g. 2500W -> 2300W).
   If the robust partner restarts, it steps down 1 tier relative to its current state.
4. Step-Up Soak: 2 hours of sustained stability without restarts triggers progressive ramp-up back to nominal.

All functions in this module are strictly deterministic and free of network I/O.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Dict, List, Optional, Tuple

from app.governance.preset_balancer import (
    DEFAULT_PRESET_LADDER,
    PresetTier,
    find_preset_index,
)

# Canonical canary assignments per electrical group
DEFAULT_CANARY_MAP: Dict[str, str] = {
    "elevator_1": "S19JPRO-24",  # Miner 24 (I2C bus sensitivity on chain 2)
    "elevator_2": "S19JPRO-25",  # Miner 25 (experienced 4 restarts during 2026-09-14 brownouts)
}

ACTION_STEP_DOWN_CANARY = "STEP_DOWN_CANARY"
ACTION_STEP_DOWN_LIMIT = "STEP_DOWN_LIMIT"
ACTION_STEP_DOWN_PARTNER = "STEP_DOWN_PARTNER"
ACTION_HOLD_CONTINGENCY = "HOLD_CONTINGENCY"
ACTION_STEP_UP_SOAK = "STEP_UP_SOAK"
ACTION_RESTORE_NOMINAL = "RESTORE_NOMINAL"
ACTION_RESTORE_INRUSH_DAMPENER = "RESTORE_INRUSH_DAMPENER"
ACTION_NO_ACTION = "NO_ACTION"

DEFAULT_SOAK_SECONDS = 7200.0       # 2 continuous hours without restart to initiate recovery
DEFAULT_INRUSH_DAMPENER_SECONDS = 300.0  # 5 minutes temporary partner dampening during inrush
DEFAULT_MIN_PRESET_FLOOR = "2150W"   # Lower limit for automated contingency reductions (calibrated to hardware)
DEFAULT_MAX_CEILING = "2700W"


def normalize_miner_name(name: str) -> str:
    """Normalize names like '24', 'Miner 24', 'S19JPRO-24' to canonical uppercase alphanumeric."""
    cleaned = str(name).strip().upper()
    digits = re.findall(r"\d+", cleaned)
    if digits:
        return f"S19JPRO-{digits[-1]}"
    return cleaned


def is_canary_miner(
    miner_name: str,
    group: str,
    canary_map: Optional[Dict[str, str]] = None,
) -> bool:
    """Check if the given miner is designated as the canary for its electrical group."""
    cmap = canary_map or DEFAULT_CANARY_MAP
    canary_entry = cmap.get(group)
    if not canary_entry:
        return False
    return normalize_miner_name(miner_name) == normalize_miner_name(canary_entry)


def find_previous_preset_tier(
    current_preset: str,
    ladder: Optional[Tuple[PresetTier, ...]] = None,
    min_floor: str = DEFAULT_MIN_PRESET_FLOOR,
) -> Optional[str]:
    """Find one tier lower in the preset ladder relative to current state.
    
    Returns None if already at or below min_floor or at bottom of ladder.
    """
    tiers = ladder or DEFAULT_PRESET_LADDER
    idx = find_preset_index(current_preset, list(tiers))
    if idx <= 0:
        return None
    floor_idx = find_preset_index(min_floor, list(tiers))
    if floor_idx >= 0 and idx <= floor_idx:
        return None
    return tiers[idx - 1].name


def find_next_preset_tier(
    current_preset: str,
    ladder: Optional[Tuple[PresetTier, ...]] = None,
    max_ceiling: str = DEFAULT_MAX_CEILING,
) -> Optional[str]:
    """Find one tier higher in the preset ladder relative to current state.
    
    Returns None if already at or above max_ceiling or at top of ladder.
    """
    tiers = ladder or DEFAULT_PRESET_LADDER
    idx = find_preset_index(current_preset, list(tiers))
    if idx < 0 or idx >= len(tiers) - 1:
        return None
    ceil_idx = find_preset_index(max_ceiling, list(tiers))
    if ceil_idx >= 0 and idx >= ceil_idx:
        return None
    return tiers[idx + 1].name


@dataclass
class GroupContingencyState:
    """Tracks state of asymmetric contingency for an electrical group."""
    group_name: str
    active: bool = False
    trigger_miner: str = ""
    started_ts: Optional[float] = None
    last_restart_ts: Optional[float] = None
    step_down_count: int = 0
    canary_initial_preset: Optional[str] = None
    partner_initial_preset: Optional[str] = None
    soak_duration_seconds: float = DEFAULT_SOAK_SECONDS
    inrush_dampener_active: bool = False
    inrush_dampener_expires_ts: Optional[float] = None
    inrush_dampener_partner: str = ""
    inrush_dampener_restored_preset: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> GroupContingencyState:
        if not data or not isinstance(data, dict):
            return cls(group_name="unknown")
        return cls(
            group_name=str(data.get("group_name", "unknown")),
            active=bool(data.get("active", False)),
            trigger_miner=str(data.get("trigger_miner", "")),
            started_ts=float(data["started_ts"]) if data.get("started_ts") is not None else None,
            last_restart_ts=float(data["last_restart_ts"]) if data.get("last_restart_ts") is not None else None,
            step_down_count=int(data.get("step_down_count", 0)),
            canary_initial_preset=data.get("canary_initial_preset"),
            partner_initial_preset=data.get("partner_initial_preset"),
            soak_duration_seconds=float(data.get("soak_duration_seconds", DEFAULT_SOAK_SECONDS)),
            inrush_dampener_active=bool(data.get("inrush_dampener_active", False)),
            inrush_dampener_expires_ts=float(data["inrush_dampener_expires_ts"]) if data.get("inrush_dampener_expires_ts") is not None else None,
            inrush_dampener_partner=str(data.get("inrush_dampener_partner", "")),
            inrush_dampener_restored_preset=data.get("inrush_dampener_restored_preset"),
        )


@dataclass(frozen=True)
class ContingencyDecision:
    """Action outcome from evaluating an adaptive contingency event."""
    action: str
    group_name: str
    target_miner: str
    previous_preset: str
    target_preset: str
    reason: str
    requires_write: bool = False
    notification_msg: str = ""
    updated_group_state: Optional[GroupContingencyState] = None
    partner_miner: str = ""
    partner_target_preset: str = ""
    partner_requires_write: bool = False


def evaluate_canary_contingency(
    event_type: str,
    miner_name: str,
    group_name: str,
    current_presets: Dict[str, str],
    now_ts: float,
    group_state: Optional[GroupContingencyState] = None,
    canary_map: Optional[Dict[str, str]] = None,
    min_preset_floor: str = DEFAULT_MIN_PRESET_FLOOR,
    soak_seconds: float = DEFAULT_SOAK_SECONDS,
    enable_paired_inrush: bool = False,
    inrush_dampener_seconds: float = DEFAULT_INRUSH_DAMPENER_SECONDS,
) -> ContingencyDecision:
    """Pure evaluation of adaptive contingency logic.
    
    Args:
        event_type: "unexpected_restart", "soak_tick", or "manual_reset"
        miner_name: Name of the miner involved (or "" for periodic soak ticks)
        group_name: Electrical group (e.g. "elevator_1", "elevator_2")
        current_presets: Dict mapping miner name -> current preset (e.g. "2700W")
        now_ts: Current epoch timestamp
        group_state: Current GroupContingencyState instance or None
        canary_map: Canary assignments override
        min_preset_floor: Minimum wattage allowed for reduction (default "2100W")
        soak_seconds: Stability seconds required for recovery (default 7200s = 2h)
        enable_paired_inrush: If True, temporary dampens partner miner during restart inrush
        inrush_dampener_seconds: Duration of temporary partner dampening (default 300s)
    
    Returns:
        ContingencyDecision with complete action, target miner, presets, and updated state.
    """
    cmap = canary_map or DEFAULT_CANARY_MAP
    norm_miner = normalize_miner_name(miner_name) if miner_name else ""
    is_canary = is_canary_miner(norm_miner, group_name, cmap) if norm_miner else False
    
    state = group_state or GroupContingencyState(group_name=group_name, soak_duration_seconds=soak_seconds)

    # -----------------------------------------------------------------------
    # Case 1: Manual Reset
    # -----------------------------------------------------------------------
    if event_type == "manual_reset":
        reset_state = GroupContingencyState(group_name=group_name, soak_duration_seconds=soak_seconds)
        return ContingencyDecision(
            action=ACTION_NO_ACTION,
            group_name=group_name,
            target_miner=miner_name,
            previous_preset="",
            target_preset="",
            reason="Contingencia reseteada manualmente a valores nominales",
            requires_write=False,
            notification_msg=f"ℹ️ Contingencia de elevador [{group_name}] restablecida.",
            updated_group_state=reset_state,
        )

    # -----------------------------------------------------------------------
    # Case 1.5: Inrush Dampener Restoration Check on soak_tick
    # -----------------------------------------------------------------------
    if event_type == "soak_tick" and state.inrush_dampener_active and state.inrush_dampener_expires_ts:
        if now_ts >= state.inrush_dampener_expires_ts:
            target_p = state.inrush_dampener_partner
            curr_p = current_presets.get(target_p) or current_presets.get(normalize_miner_name(target_p), "")
            restored_p = state.inrush_dampener_restored_preset or curr_p or DEFAULT_MAX_CEILING
            new_st = GroupContingencyState(
                group_name=state.group_name,
                active=state.active,
                trigger_miner=state.trigger_miner,
                started_ts=state.started_ts,
                last_restart_ts=state.last_restart_ts,
                step_down_count=state.step_down_count,
                canary_initial_preset=state.canary_initial_preset,
                partner_initial_preset=state.partner_initial_preset,
                soak_duration_seconds=state.soak_duration_seconds,
                inrush_dampener_active=False,
                inrush_dampener_expires_ts=None,
                inrush_dampener_partner="",
                inrush_dampener_restored_preset=None,
            )
            return ContingencyDecision(
                action=ACTION_RESTORE_INRUSH_DAMPENER,
                group_name=group_name,
                target_miner=target_p,
                previous_preset=curr_p,
                target_preset=restored_p,
                reason=f"Amortiguación de arranque completada: restaurando compañero {target_p} a {restored_p}",
                requires_write=True,
                notification_msg=f"⚡ *AMORTIGUACIÓN DE ELEVADOR FINALIZADA [{group_name}]*\n• Minero compañero *{target_p}* restablecido a *{restored_p}* tras arranque estable.",
                updated_group_state=new_st,
            )

    # -----------------------------------------------------------------------
    # Case 2: Unexpected Restart Event (Canary vs Robust Partner)
    # -----------------------------------------------------------------------
    if event_type == "unexpected_restart":
        # Resolve current preset of the restarting miner
        curr_p = current_presets.get(miner_name) or current_presets.get(norm_miner, "2700W")
        
        # Identify partner miner in the group from current_presets
        partner_name = ""
        partner_preset = ""
        for m_k, p_k in current_presets.items():
            if normalize_miner_name(m_k) != norm_miner:
                partner_name = m_k
                partner_preset = p_k
                break

        # A) Canary Miner Restarted
        if is_canary:
            if not state.active:
                # First restart in the elevator group -> enter contingency
                prev_tier = find_previous_preset_tier(curr_p, min_floor=min_preset_floor)
                if not prev_tier:
                    return ContingencyDecision(
                        action=ACTION_HOLD_CONTINGENCY,
                        group_name=group_name,
                        target_miner=miner_name,
                        previous_preset=curr_p,
                        target_preset=curr_p,
                        reason=f"Canario {miner_name} ya se encuentra en el piso mínimo ({curr_p})",
                        requires_write=False,
                        updated_group_state=state,
                    )

                partner_damp_tier = ""
                partner_write = False
                damp_active = False
                damp_exp = None
                damp_target = ""
                damp_restored = None
                if enable_paired_inrush and partner_name and partner_preset:
                    p_tier = find_previous_preset_tier(partner_preset, min_floor=min_preset_floor)
                    if p_tier:
                        partner_damp_tier = p_tier
                        partner_write = True
                        damp_active = True
                        damp_exp = now_ts + inrush_dampener_seconds
                        damp_target = partner_name
                        damp_restored = partner_preset

                new_state = GroupContingencyState(
                    group_name=group_name,
                    active=True,
                    trigger_miner=miner_name,
                    started_ts=now_ts,
                    last_restart_ts=now_ts,
                    step_down_count=1,
                    canary_initial_preset=curr_p,
                    partner_initial_preset=partner_preset,
                    soak_duration_seconds=soak_seconds,
                    inrush_dampener_active=damp_active,
                    inrush_dampener_expires_ts=damp_exp,
                    inrush_dampener_partner=damp_target,
                    inrush_dampener_restored_preset=damp_restored,
                )

                partner_display = f"{partner_name} se mantiene en {partner_preset}." if partner_name else ""
                if partner_write and partner_damp_tier:
                    partner_display = f"{partner_name} amortigua a {partner_damp_tier} ({int(inrush_dampener_seconds)}s)."
                notif = (
                    f"⚡ *CONTINGENCIA ASIMÉTRICA [{group_name}]*\n\n"
                    f"Reinicio inesperado en minero canario *{miner_name}*.\n"
                    f"• Acción: Reduciendo de *{curr_p}* a *{prev_tier}* (-1 peldaño relativo).\n"
                    f"• Minero robusto: {partner_display}\n"
                    f"• Objetivo: Aliviar la corriente del elevador evitando perturbaciones de red."
                )

                return ContingencyDecision(
                    action=ACTION_STEP_DOWN_CANARY,
                    group_name=group_name,
                    target_miner=miner_name,
                    previous_preset=curr_p,
                    target_preset=prev_tier,
                    reason=f"Reinicio en minero canario {miner_name}: reducción asimétrica {curr_p} -> {prev_tier}",
                    requires_write=True,
                    notification_msg=notif,
                    updated_group_state=new_state,
                    partner_miner=partner_name if partner_write else "",
                    partner_target_preset=partner_damp_tier if partner_write else "",
                    partner_requires_write=partner_write,
                )
            else:
                # Already in contingency: Canary restarted AGAIN! (Prueba en los límites)
                prev_tier = find_previous_preset_tier(curr_p, min_floor=min_preset_floor)
                new_state = GroupContingencyState(
                    group_name=group_name,
                    active=True,
                    trigger_miner=state.trigger_miner or miner_name,
                    started_ts=state.started_ts or now_ts,
                    last_restart_ts=now_ts,
                    step_down_count=state.step_down_count + 1,
                    canary_initial_preset=state.canary_initial_preset or curr_p,
                    partner_initial_preset=state.partner_initial_preset or partner_preset,
                    soak_duration_seconds=soak_seconds,
                )

                if not prev_tier:
                    return ContingencyDecision(
                        action=ACTION_HOLD_CONTINGENCY,
                        group_name=group_name,
                        target_miner=miner_name,
                        previous_preset=curr_p,
                        target_preset=curr_p,
                        reason=f"Canario {miner_name} alcanzó piso mínimo ({curr_p}) durante prueba en los límites",
                        requires_write=False,
                        updated_group_state=new_state,
                    )

                notif = (
                    f"⚡ *CONTINGENCIA [PRUEBA EN LOS LÍMITES] [{group_name}]*\n\n"
                    f"Segundo reinicio en minero canario *{miner_name}* operando en *{curr_p}*.\n"
                    f"• Acción: Explorando límite inferior: Reduciendo a *{prev_tier}*.\n"
                    f"• Conteo de desescalas en elevador: {new_state.step_down_count}."
                )

                return ContingencyDecision(
                    action=ACTION_STEP_DOWN_LIMIT,
                    group_name=group_name,
                    target_miner=miner_name,
                    previous_preset=curr_p,
                    target_preset=prev_tier,
                    reason=f"Reinicio persistente en canario {miner_name}: desescalando a {prev_tier}",
                    requires_write=True,
                    notification_msg=notif,
                    updated_group_state=new_state,
                )

        # B) Robust Partner Restarted
        else:
            prev_tier = find_previous_preset_tier(curr_p, min_floor=min_preset_floor)
            new_state = GroupContingencyState(
                group_name=group_name,
                active=True,
                trigger_miner=state.trigger_miner or miner_name,
                started_ts=state.started_ts or now_ts,
                last_restart_ts=now_ts,
                step_down_count=state.step_down_count + 1,
                canary_initial_preset=state.canary_initial_preset,
                partner_initial_preset=state.partner_initial_preset or curr_p,
                soak_duration_seconds=soak_seconds,
            )

            if not prev_tier:
                return ContingencyDecision(
                    action=ACTION_HOLD_CONTINGENCY,
                    group_name=group_name,
                    target_miner=miner_name,
                    previous_preset=curr_p,
                    target_preset=curr_p,
                    reason=f"Minero robusto {miner_name} alcanzó piso mínimo ({curr_p})",
                    requires_write=False,
                    updated_group_state=new_state,
                )

            notif = (
                f"⚡ *CONTINGENCIA [MINERO ROBUSTO] [{group_name}]*\n\n"
                f"Reinicio inesperado en minero robusto *{miner_name}* (perturbación severa de red).\n"
                f"• Acción: Reduciendo de *{curr_p}* a *{prev_tier}* (-1 peldaño relativo)."
            )

            return ContingencyDecision(
                action=ACTION_STEP_DOWN_PARTNER,
                group_name=group_name,
                target_miner=miner_name,
                previous_preset=curr_p,
                target_preset=prev_tier,
                reason=f"Reinicio en minero robusto {miner_name}: reducción relativa {curr_p} -> {prev_tier}",
                requires_write=True,
                notification_msg=notif,
                updated_group_state=new_state,
            )

    # -----------------------------------------------------------------------
    # Case 3: Periodic Soak Tick (Recovery / Step-Up Soak)
    # -----------------------------------------------------------------------
    if event_type == "soak_tick" and state.active and state.last_restart_ts:
        elapsed = now_ts - state.last_restart_ts
        if elapsed >= state.soak_duration_seconds:
            # 2 hours without restart! Find candidate miner to step up
            target_miner_cand = ""
            init_preset = ""
            curr_p = ""

            # Check canary
            canary_name = cmap.get(group_name, "")
            canary_curr = current_presets.get(canary_name, "")
            canary_init = state.canary_initial_preset

            # Check partner miner in group
            partner_name = ""
            partner_curr = ""
            for m_k, p_k in current_presets.items():
                if normalize_miner_name(m_k) != normalize_miner_name(canary_name):
                    partner_name = m_k
                    partner_curr = p_k
                    break
            partner_init = state.partner_initial_preset

            # Priority 1: Step up canary if it is below its recorded initial preset
            if canary_curr and canary_init and find_preset_index(canary_curr) < find_preset_index(canary_init):
                target_miner_cand = canary_name
                init_preset = canary_init
                curr_p = canary_curr
            # Priority 2: Step up partner if canary is nominal but partner is below its recorded initial preset
            elif partner_curr and partner_init and find_preset_index(partner_curr) < find_preset_index(partner_init):
                target_miner_cand = partner_name
                init_preset = partner_init
                curr_p = partner_curr

            if target_miner_cand:
                next_tier = find_next_preset_tier(curr_p, max_ceiling=init_preset)
                if next_tier:
                    # Full restore only if both canary and partner are at or above their initial presets
                    canary_restored = True
                    if canary_init and canary_curr:
                        if target_miner_cand == canary_name:
                            canary_restored = (find_preset_index(next_tier) >= find_preset_index(canary_init))
                        else:
                            canary_restored = (find_preset_index(canary_curr) >= find_preset_index(canary_init))

                    partner_restored = True
                    if partner_init and partner_curr:
                        if target_miner_cand == partner_name:
                            partner_restored = (find_preset_index(next_tier) >= find_preset_index(partner_init))
                        else:
                            partner_restored = (find_preset_index(partner_curr) >= find_preset_index(partner_init))

                    is_full_restore = canary_restored and partner_restored
                    new_state = GroupContingencyState(
                        group_name=group_name,
                        active=not is_full_restore,
                        trigger_miner=state.trigger_miner if not is_full_restore else "",
                        started_ts=state.started_ts if not is_full_restore else None,
                        last_restart_ts=now_ts,  # Reset soak timer for next step
                        step_down_count=max(0, state.step_down_count - 1),
                        canary_initial_preset=state.canary_initial_preset if not is_full_restore else None,
                        partner_initial_preset=state.partner_initial_preset if not is_full_restore else None,
                        soak_duration_seconds=soak_seconds,
                    )

                    notif = (
                        f"🌱 *RECUPERACIÓN PROGRESIVA [{group_name}]*\n\n"
                        f"Estabilidad sostenida (2 horas continuas sin reinicios).\n"
                        f"• Minero: *{target_miner_cand}*\n"
                        f"• Rampa suave: Subiendo de *{curr_p}* a *{next_tier}*.\n"
                        f"• Estado: {'Restauración completa nominal alcanzada' if is_full_restore else 'Recuperación escalonada en progreso'}."
                    )

                    return ContingencyDecision(
                        action=ACTION_RESTORE_NOMINAL if is_full_restore else ACTION_STEP_UP_SOAK,
                        group_name=group_name,
                        target_miner=target_miner_cand,
                        previous_preset=curr_p,
                        target_preset=next_tier,
                        reason=f"Estabilidad eléctrica de 2h: rampa hacia arriba {curr_p} -> {next_tier}",
                        requires_write=True,
                        notification_msg=notif,
                        updated_group_state=new_state,
                    )

    return ContingencyDecision(
        action=ACTION_NO_ACTION,
        group_name=group_name,
        target_miner="",
        previous_preset="",
        target_preset="",
        reason="Condiciones estables sin acción requerida",
        requires_write=False,
        updated_group_state=state,
    )
