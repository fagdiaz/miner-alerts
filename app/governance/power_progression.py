"""
Power Progression & Graceful Fallback Orchestrator (PROP-014 / Spec 079 Addendum).

Provides deterministic progression towards maximum fleet power (up to 4x 2700W)
with immediate, multi-tier fallback alternatives whenever thermal saturation,
fan limits, autotune stalls, or electrical noise occur.

Strictly deterministic, zero network I/O, 100% testable.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.governance.thermal_policy import (
    TEMP_STEP_UP_CEILING_C,
    FAN_STEP_UP_MAX_DUTY_PCT,
    TEMP_SUSTAINED_TRIPWIRE_C,
    SUSTAINED_TRIPWIRE_WINDOW_S,
    TEMP_IMMEDIATE_TRIPWIRE_C,
    THERMAL_LOCKOUT_SECONDS,
)

# Supported Fleet Profiles
PROFILE_C4_MAX_POWER = "C4_MAX_POWER"          # 2700 / 2700 / 2700 / 2700 (10.8 kW, ~400 TH/s)
PROFILE_C1_ASYMMETRIC = "C1_ASYMMETRIC"        # 2700 / 2700 / 2500 / 2700 (10.6 kW, ~392 TH/s)
PROFILE_C2_ELEV1_BALANCED = "C2_ELEV1_BALANCED"# 2700 / 2500 / 2500 / 2700 (10.4 kW, ~384 TH/s)
PROFILE_C0_BASE_STABLE = "C0_BASE_STABLE"      # 2500 / 2500 / 2500 / 2500 (10.0 kW, ~376 TH/s)
PROFILE_EMERGENCY_COOL = "EMERGENCY_COOL"      # 2300 / 2300 / 2300 / 2300 (9.2 kW, ~350 TH/s)

PROFILE_ALIASES: Dict[str, str] = {
    "c0": PROFILE_C0_BASE_STABLE,
    "c1": PROFILE_C1_ASYMMETRIC,
    "c2": PROFILE_C2_ELEV1_BALANCED,
    "c4": PROFILE_C4_MAX_POWER,
    "c0_base_stable": PROFILE_C0_BASE_STABLE,
    "c1_asymmetric": PROFILE_C1_ASYMMETRIC,
    "c2_elev1_balanced": PROFILE_C2_ELEV1_BALANCED,
    "c4_max_power": PROFILE_C4_MAX_POWER,
    "base": PROFILE_C0_BASE_STABLE,
    "max": PROFILE_C4_MAX_POWER,
    "max_power": PROFILE_C4_MAX_POWER,
    "asymmetric": PROFILE_C1_ASYMMETRIC,
    "balanced": PROFILE_C2_ELEV1_BALANCED,
    "emergency": PROFILE_EMERGENCY_COOL,
}

PROFILE_TARGETS: Dict[str, Dict[str, str]] = {
    PROFILE_C4_MAX_POWER: {
        "S19JPRO-23": "2700W",
        "S19JPRO-24": "2700W",
        "S19JPRO-25": "2700W",
        "S19JPRO-26": "2700W",
    },
    PROFILE_C1_ASYMMETRIC: {
        "S19JPRO-23": "2700W",
        "S19JPRO-24": "2700W",
        "S19JPRO-25": "2500W",
        "S19JPRO-26": "2700W",
    },
    PROFILE_C2_ELEV1_BALANCED: {
        "S19JPRO-23": "2700W",
        "S19JPRO-24": "2500W",
        "S19JPRO-25": "2500W",
        "S19JPRO-26": "2700W",
    },
    PROFILE_C0_BASE_STABLE: {
        "S19JPRO-23": "2500W",
        "S19JPRO-24": "2500W",
        "S19JPRO-25": "2500W",
        "S19JPRO-26": "2500W",
    },
    PROFILE_EMERGENCY_COOL: {
        "S19JPRO-23": "2300W",
        "S19JPRO-24": "2300W",
        "S19JPRO-25": "2300W",
        "S19JPRO-26": "2300W",
    },
}

# Operational Safety Thresholds (linked to Canonical Thermal Ladder)
DEFAULT_STEP_UP_MAX_CHIP_TEMP_C: float = TEMP_STEP_UP_CEILING_C
DEFAULT_STEP_UP_MAX_FAN_DUTY_PCT: float = FAN_STEP_UP_MAX_DUTY_PCT
DEFAULT_PROMOTION_SOAK_SECONDS: float = 900.0       # 15 min between promotions
DEFAULT_THERMAL_TRIPWIRE_C: float = TEMP_IMMEDIATE_TRIPWIRE_C            # Immediate fallback tripwire
DEFAULT_SUSTAINED_TRIPWIRE_C: float = TEMP_SUSTAINED_TRIPWIRE_C          # Sustained fallback tripwire
DEFAULT_SUSTAINED_SECONDS: float = SUSTAINED_TRIPWIRE_WINDOW_S             # Sustained duration
DEFAULT_THERMAL_LOCKOUT_SECONDS: float = THERMAL_LOCKOUT_SECONDS     # 30 min lockout post-fallback
DEFAULT_MAX_ELEVATOR_POWER_W: float = 5400.0        # Max 5400W per elevator

# Action Types
ACTION_PROMOTE_2700W = "PROMOTE_2700W"
ACTION_FALLBACK_2500W = "FALLBACK_2500W"
ACTION_HOLD_SOAK = "HOLD_SOAK"
ACTION_HOLD_FAN_SATURATED = "HOLD_FAN_SATURATED"
ACTION_HOLD_THERMAL = "HOLD_THERMAL"
ACTION_HOLD_LOCKOUT = "HOLD_LOCKOUT"
ACTION_HOLD_HARDWARE_LIMIT = "HOLD_HARDWARE_LIMIT"
ACTION_HOLD_ELEVATOR_BUDGET = "HOLD_ELEVATOR_BUDGET"
ACTION_NO_ACTION = "NO_ACTION"


@dataclass
class MinerProgressionState:
    miner_name: str
    current_preset: str = "2500W"
    last_promotion_ts: float = 0.0
    thermal_lockout_until_ts: float = 0.0
    failed_attempts_2700w: int = 0
    permanent_hardware_ceiling: Optional[str] = None
    consecutive_hot_seconds: float = 0.0

    def is_in_lockout(self, now_ts: float) -> Tuple[bool, float]:
        if self.thermal_lockout_until_ts > now_ts:
            return True, self.thermal_lockout_until_ts - now_ts
        return False, 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> MinerProgressionState:
        if not data or not isinstance(data, dict):
            return cls(miner_name="")
        return cls(
            miner_name=str(data.get("miner_name", "")),
            current_preset=str(data.get("current_preset", "2500W")),
            last_promotion_ts=float(data.get("last_promotion_ts", 0.0)),
            thermal_lockout_until_ts=float(data.get("thermal_lockout_until_ts", 0.0)),
            failed_attempts_2700w=int(data.get("failed_attempts_2700w", 0)),
            permanent_hardware_ceiling=data.get("permanent_hardware_ceiling"),
            consecutive_hot_seconds=float(data.get("consecutive_hot_seconds", 0.0)),
        )


@dataclass
class ProgressionOrchestratorState:
    desired_profile: str = PROFILE_C0_BASE_STABLE
    current_profile: str = PROFILE_C0_BASE_STABLE
    last_transition_ts: float = 0.0
    active_transition_miner: str = ""
    soak_seconds: float = DEFAULT_PROMOTION_SOAK_SECONDS
    miner_states: Dict[str, MinerProgressionState] = field(default_factory=dict)
    group_incident_ts: Dict[str, float] = field(default_factory=dict)

    def is_in_soak(self, now_ts: float) -> Tuple[bool, float]:
        if self.last_transition_ts <= 0.0:
            return False, 0.0
        elapsed = now_ts - self.last_transition_ts
        rem = max(0.0, self.soak_seconds - elapsed)
        return (rem > 0.0), rem

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> ProgressionOrchestratorState:
        if not data or not isinstance(data, dict):
            return cls()
        m_states = {}
        for k, v in data.get("miner_states", {}).items():
            m_states[k] = MinerProgressionState.from_dict(v)
        grp_inc = {str(k): float(v) for k, v in data.get("group_incident_ts", {}).items()}
        return cls(
            desired_profile=str(data.get("desired_profile", PROFILE_C0_BASE_STABLE)),
            current_profile=str(data.get("current_profile", PROFILE_C0_BASE_STABLE)),
            last_transition_ts=float(data.get("last_transition_ts", 0.0)),
            active_transition_miner=str(data.get("active_transition_miner", "")),
            soak_seconds=float(data.get("soak_seconds", DEFAULT_PROMOTION_SOAK_SECONDS)),
            miner_states=m_states,
            group_incident_ts=grp_inc,
        )


_GLOBAL_PROGRESSION_STATE: ProgressionOrchestratorState = ProgressionOrchestratorState()


def get_global_progression_state() -> ProgressionOrchestratorState:
    global _GLOBAL_PROGRESSION_STATE
    return _GLOBAL_PROGRESSION_STATE


def set_global_desired_profile(profile_str: str) -> Tuple[bool, str]:
    global _GLOBAL_PROGRESSION_STATE
    key = str(profile_str).strip().lower()
    canonical = PROFILE_ALIASES.get(key)
    if not canonical:
        valid_opts = ", ".join(sorted(PROFILE_TARGETS.keys()))
        return False, f"Perfil desconocido '{profile_str}'. Opciones válidas: {valid_opts} (o atajos: c0, c1, c2, c4)"
    _GLOBAL_PROGRESSION_STATE.desired_profile = canonical
    return True, canonical


@dataclass(frozen=True)
class ProgressionDecision:
    action: str
    target_miner: str = ""
    target_preset: str = ""
    current_preset: str = ""
    reason: str = ""
    active_profile: str = ""
    projected_elevator_power_w: Dict[str, float] = field(default_factory=dict)


def parse_preset_w(p_str: Any) -> float:
    if not p_str:
        return 2500.0
    clean = str(p_str).upper().replace("W", "").strip()
    try:
        return float(clean)
    except (ValueError, TypeError):
        return 2500.0


def evaluate_progression_cycle(
    telemetry_list: List[Dict[str, Any]],
    state: ProgressionOrchestratorState,
    now_ts: float,
    config: Optional[Dict[str, Any]] = None,
) -> ProgressionDecision:
    """
    Evaluates power progression towards desired profile with safety-first fallback priority.
    
    Order of Evaluation:
    1. Safety-Critical Fallbacks (Overheated chips, sustained high temp, or autotune stalls).
    2. Settle / Inrush Soak Window (Must allow previous promotions to reach thermal equilibrium).
    3. Staggered Step-Up Promotion (Promotes 1 miner at a time towards desired profile).
    """
    cfg = config or {}
    tripwire_c = float(cfg.get("progression_tripwire_c", DEFAULT_THERMAL_TRIPWIRE_C))
    sustained_c = float(cfg.get("progression_sustained_tripwire_c", DEFAULT_SUSTAINED_TRIPWIRE_C))
    max_step_up_temp = float(cfg.get("valley_step_up_max_chip_temp_c", DEFAULT_STEP_UP_MAX_CHIP_TEMP_C))
    max_step_up_duty = float(cfg.get("valley_step_up_max_fan_duty_pct", DEFAULT_STEP_UP_MAX_FAN_DUTY_PCT))
    max_group_w = float(cfg.get("soft_contingency_valley_budget_w", DEFAULT_MAX_ELEVATOR_POWER_W))

    # Ensure all miners have state tracking
    for m in telemetry_list:
        m_name = m.get("name", "")
        if m_name and m_name not in state.miner_states:
            hw_lim = m.get("max_hardware_preset")
            state.miner_states[m_name] = MinerProgressionState(
                miner_name=m_name,
                current_preset=m.get("preset", "2500W"),
                permanent_hardware_ceiling=hw_lim,
            )

    # -------------------------------------------------------------------------
    # STAGE 1: SAFETY-FIRST FALLBACKS (Immediate Protection)
    # -------------------------------------------------------------------------
    for m in telemetry_list:
        m_name = m.get("name", "")
        m_st = state.miner_states.get(m_name)
        chip_t = float(m.get("chip_temp_c") or m.get("max_chip_temp") or 0.0)
        curr_p = str(m.get("preset") or (m_st.current_preset if m_st else "2500W"))
        pwr_w = float(m.get("power_w") or parse_preset_w(curr_p))

        # Check if miner is at 2700W (or consuming > 2550W)
        if parse_preset_w(curr_p) > 2500 or pwr_w > 2550.0:
            # Immediate thermal tripwire (>= 83.5°C)
            if chip_t >= tripwire_c:
                if m_st:
                    m_st.thermal_lockout_until_ts = now_ts + DEFAULT_THERMAL_LOCKOUT_SECONDS
                    m_st.failed_attempts_2700w += 1
                state.last_transition_ts = now_ts
                state.active_transition_miner = m_name

                # Degrade profile if needed
                if state.current_profile == PROFILE_C4_MAX_POWER:
                    state.current_profile = PROFILE_C1_ASYMMETRIC
                elif state.current_profile == PROFILE_C1_ASYMMETRIC and m_name in ("S19JPRO-23", "S19JPRO-24"):
                    state.current_profile = PROFILE_C2_ELEV1_BALANCED

                return ProgressionDecision(
                    action=ACTION_FALLBACK_2500W,
                    target_miner=m_name,
                    target_preset="2500W",
                    current_preset=curr_p,
                    reason=f"Alivio térmico inmediato: chip={chip_t:.1f}°C >= {tripwire_c:.1f}°C en 2700W",
                    active_profile=state.current_profile,
                )

            # Sustained thermal accumulation (> 83.0°C for > 60s)
            if chip_t >= sustained_c:
                if m_st:
                    m_st.consecutive_hot_seconds += 30.0  # Approx tick duration
                    if m_st.consecutive_hot_seconds >= DEFAULT_SUSTAINED_SECONDS:
                        m_st.thermal_lockout_until_ts = now_ts + DEFAULT_THERMAL_LOCKOUT_SECONDS
                        m_st.failed_attempts_2700w += 1
                        m_st.consecutive_hot_seconds = 0.0
                        state.last_transition_ts = now_ts
                        state.active_transition_miner = m_name
                        return ProgressionDecision(
                            action=ACTION_FALLBACK_2500W,
                            target_miner=m_name,
                            target_preset="2500W",
                            current_preset=curr_p,
                            reason=f"Alivio térmico acumulado: chip={chip_t:.1f}°C sostenido > {sustained_c:.1f}°C",
                            active_profile=state.current_profile,
                        )
            else:
                if m_st:
                    m_st.consecutive_hot_seconds = 0.0

    # -------------------------------------------------------------------------
    # STAGE 2: SETTLE / INRUSH SOAK WINDOW
    # -------------------------------------------------------------------------
    in_soak, rem_soak = state.is_in_soak(now_ts)
    if in_soak:
        return ProgressionDecision(
            action=ACTION_HOLD_SOAK,
            target_miner=state.active_transition_miner,
            reason=f"Reposo y remojo térmico de planta activo ({rem_soak:.0f}s restantes)",
            active_profile=state.current_profile,
        )

    # -------------------------------------------------------------------------
    # STAGE 3: STAGGERED STEP-UP PROMOTION TOWARDS DESIRED PROFILE
    # -------------------------------------------------------------------------
    desired_allocations = PROFILE_TARGETS.get(state.desired_profile, PROFILE_TARGETS[PROFILE_C1_ASYMMETRIC])

    # Find candidate miner whose current preset is below desired preset
    for m in telemetry_list:
        m_name = m.get("name", "")
        m_st = state.miner_states.get(m_name)
        curr_p = str(m.get("preset") or (m_st.current_preset if m_st else "2500W"))
        target_p = desired_allocations.get(m_name, "2500W")

        if parse_preset_w(curr_p) < parse_preset_w(target_p):
            # Candidate found! Evaluate safety gates:

            # Gate 1: Permanent hardware ceiling
            hw_lim = m_st.permanent_hardware_ceiling if m_st else m.get("max_hardware_preset")
            if hw_lim and parse_preset_w(hw_lim) < parse_preset_w(target_p):
                continue

            # Gate 2: Thermal lockout
            if m_st:
                in_lock, rem_lock = m_st.is_in_lockout(now_ts)
                if in_lock:
                    return ProgressionDecision(
                        action=ACTION_HOLD_LOCKOUT,
                        target_miner=m_name,
                        target_preset=target_p,
                        current_preset=curr_p,
                        reason=f"Minero en reposo térmico post-desescalada ({rem_lock:.0f}s restantes)",
                        active_profile=state.current_profile,
                    )

            # Gate 3: Live thermal headroom
            chip_t = float(m.get("chip_temp_c") or m.get("max_chip_temp") or 0.0)
            if chip_t >= max_step_up_temp:
                return ProgressionDecision(
                    action=ACTION_HOLD_THERMAL,
                    target_miner=m_name,
                    target_preset=target_p,
                    current_preset=curr_p,
                    reason=f"Chip a {chip_t:.1f}°C >= {max_step_up_temp:.1f}°C (esperando enfriamiento)",
                    active_profile=state.current_profile,
                )

            # Gate 4: Fan reserve headroom
            fan_duty = float(m.get("fan_duty_pct") or m.get("duty") or 0.0)
            if fan_duty >= max_step_up_duty:
                return ProgressionDecision(
                    action=ACTION_HOLD_FAN_SATURATED,
                    target_miner=m_name,
                    target_preset=target_p,
                    current_preset=curr_p,
                    reason=f"Ventiladores saturados al {fan_duty:.0f}% >= {max_step_up_duty:.0f}% (sin reserva para +200W)",
                    active_profile=state.current_profile,
                )

            # Gate 5: Group / Elevator power budget
            grp = m.get("electrical_group") or "elevator_1"
            grp_miners = [xm for xm in telemetry_list if (xm.get("electrical_group") or "elevator_1") == grp]
            projected_grp_pwr = sum(
                (parse_preset_w(target_p) if xm.get("name") == m_name else parse_preset_w(xm.get("preset", "2500W")))
                for xm in grp_miners
            )
            if projected_grp_pwr > max_group_w:
                return ProgressionDecision(
                    action=ACTION_HOLD_ELEVATOR_BUDGET,
                    target_miner=m_name,
                    target_preset=target_p,
                    current_preset=curr_p,
                    reason=f"Potencia proyectada en elevador {grp} ({projected_grp_pwr:.0f}W) supera límite seguro {max_group_w:.0f}W",
                    active_profile=state.current_profile,
                )

            # All gates passed! Promote this single miner!
            if m_st:
                m_st.last_promotion_ts = now_ts
                m_st.current_preset = target_p
            state.last_transition_ts = now_ts
            state.active_transition_miner = m_name

            return ProgressionDecision(
                action=ACTION_PROMOTE_2700W,
                target_miner=m_name,
                target_preset=target_p,
                current_preset=curr_p,
                reason=f"Promoción autorizada a 2700W: chip={chip_t:.1f}°C, fans={fan_duty:.0f}%, elevador={projected_grp_pwr:.0f}W",
                active_profile=state.desired_profile,
            )

    return ProgressionDecision(
        action=ACTION_NO_ACTION,
        reason="Flota optimizada en estado estacionario según el perfil activo",
        active_profile=state.current_profile,
    )
