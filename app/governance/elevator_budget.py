"""Elevator Budget & Staggered Facility Governance Module (Spec 077 / PROP-012).

Manages physical infrastructure constraints across the shared electrical service drop
and individual elevator transformers:
1. Facility Settle Window (180s): Shared service drop cannot tolerate concurrent
   step-ups/step-downs due to inductive surge (L di/dt) and cable heating.
2. Soft-Contingency Schedule: Mon-Fri morning (08:30-10:30) and evening (19:30-22:30) peak
   windows capped at 5000W per elevator (2x 2500W). Off-peak allows up to 5400W (2x 2700W).
3. Symmetric Balancing: Prioritizes 2x 2500W over asymmetric 2700W + 2300W.
4. Co-governance Envelope: Binds VNish macro limits while letting its PLLs autotune chips.

Strictly deterministic and free of network I/O.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, time as dtime
import re
from typing import Any, Dict, List, Optional, Tuple

from app.governance.adaptive_contingency import normalize_miner_name
from app.governance.preset_balancer import (
    DEFAULT_PRESET_LADDER,
    PresetTier,
    find_preset_index,
)

# Operational Constants
DEFAULT_FACILITY_SETTLE_WINDOW_S: float = 180.0  # 3 minutes between any miner transition across plant
DEFAULT_PEAK_ELEVATOR_BUDGET_W: int = 5000       # 2x 2500W during peak soft-contingency
DEFAULT_VALLEY_ELEVATOR_BUDGET_W: int = 5400     # 2x 2700W during off-peak windows
DEFAULT_PEAK_MAX_PRESET: str = "2500W"
DEFAULT_VALLEY_MAX_PRESET: str = "2700W"

# Spec 078: Incident Quiet Window and Solar Thermal Constants
DEFAULT_INCIDENT_QUIET_WINDOW_S: float = 300.0  # 5 minutes quiet window on an elevator group after an incident
DEFAULT_SOLAR_WINDOW_START: dtime = dtime(11, 0)
DEFAULT_SOLAR_WINDOW_END: dtime = dtime(17, 0)
DEFAULT_SOLAR_MAX_PRESET: str = "2500W"
DEFAULT_SOLAR_CRITICAL_TEMP_C: float = 82.0

# Decision Actions
ACTION_ALLOW_TRANSITION = "ALLOW_TRANSITION"
ACTION_HOLD_FACILITY_SETTLE = "HOLD_FACILITY_SETTLE"
ACTION_HOLD_BUDGET_LIMIT = "HOLD_BUDGET_LIMIT"
ACTION_HOLD_ASYMMETRY_PREFERENCE = "HOLD_ASYMMETRY_PREFERENCE"
ACTION_HOLD_SCHEDULE_CEILING = "HOLD_SCHEDULE_CEILING"
ACTION_HOLD_INCIDENT_QUIET = "HOLD_INCIDENT_QUIET"
ACTION_HOLD_HARDWARE_LIMIT = "HOLD_HARDWARE_LIMIT"
ACTION_HOLD_SOLAR_ENVELOPE = "HOLD_SOLAR_ENVELOPE"
ACTION_HOLD_THERMAL_HEADROOM = "HOLD_THERMAL_HEADROOM"

DEFAULT_VALLEY_STEP_UP_MAX_CHIP_TEMP_C: float = 80.0

# Preset to Wattage mapping (derived from hardware validated ladder)
PRESET_WATTAGE_MAP: Dict[str, int] = {
    "1740W": 1740,
    "1800W": 1800,
    "1850W": 1850,
    "2000W": 2000,
    "2150W": 2150,
    "2300W": 2300,
    "2500W": 2500,
    "2700W": 2700,
    "2970W": 2970,
}


def parse_preset_wattage(preset_str: str) -> int:
    """Extract nominal wattage integer from preset string like '2500W' or '2500'."""
    clean = str(preset_str).strip().upper()
    if not clean.endswith("W") and clean.isdigit():
        clean = f"{clean}W"
    if clean in PRESET_WATTAGE_MAP:
        return PRESET_WATTAGE_MAP[clean]
    digits = re.findall(r"\d+", clean)
    if digits:
        return int(digits[0])
    return 2500


def parse_time_str(val: Any, default_time: dtime) -> dtime:
    """Parse 'HH:MM' string into datetime.time object safely."""
    if not val or not isinstance(val, str):
        return default_time
    try:
        parts = [int(p) for p in val.strip().split(":")]
        if len(parts) >= 2:
            return dtime(parts[0], parts[1])
    except Exception:
        pass
    return default_time



@dataclass
class FacilityBudgetState:
    """Tracks global transition state across the shared electrical drop line."""
    last_facility_transition_ts: float = 0.0
    active_transition_miner: str = ""
    active_transition_target_preset: str = ""
    settle_window_seconds: float = DEFAULT_FACILITY_SETTLE_WINDOW_S
    incident_quiet_window_s: float = DEFAULT_INCIDENT_QUIET_WINDOW_S
    last_group_incident_ts: Dict[str, float] = field(default_factory=dict)

    def is_facility_in_settle(self, now_ts: float) -> Tuple[bool, float, str]:
        """Check if facility is currently waiting for a miner transition to settle.
        
        Returns:
            Tuple[bool, float, str]: (in_settle, remaining_seconds, active_miner)
        """
        if self.last_facility_transition_ts <= 0.0:
            return False, 0.0, ""
        elapsed = now_ts - self.last_facility_transition_ts
        remaining = max(0.0, self.settle_window_seconds - elapsed)
        if remaining > 0.0:
            return True, remaining, self.active_transition_miner
        return False, 0.0, ""

    def record_transition(self, miner_name: str, target_preset: str, now_ts: float) -> None:
        """Register a new preset transition, locking the facility settle window."""
        self.last_facility_transition_ts = float(now_ts)
        self.active_transition_miner = str(miner_name)
        self.active_transition_target_preset = str(target_preset)

    def clear_settle(self) -> None:
        """Manually clear the settle window."""
        self.last_facility_transition_ts = 0.0
        self.active_transition_miner = ""
        self.active_transition_target_preset = ""

    def record_group_incident(self, group_name: str, now_ts: float) -> None:
        """Register an unexpected restart or contingency incident on an elevator group."""
        if not group_name:
            return
        self.last_group_incident_ts[str(group_name)] = float(now_ts)

    def is_group_in_incident_quiet(self, group_name: str, now_ts: float) -> Tuple[bool, float]:
        """Check if an elevator group is currently waiting for the incident quiet window (300s).
        
        Returns:
            Tuple[bool, float]: (in_quiet, remaining_seconds)
        """
        if not group_name or str(group_name) not in self.last_group_incident_ts:
            return False, 0.0
        ts = self.last_group_incident_ts[str(group_name)]
        if ts <= 0.0:
            return False, 0.0
        elapsed = now_ts - ts
        remaining = max(0.0, self.incident_quiet_window_s - elapsed)
        if remaining > 0.0:
            return True, remaining
        return False, 0.0

    def clear_group_incident(self, group_name: str) -> None:
        """Clear incident quiet window for an elevator group."""
        if group_name and str(group_name) in self.last_group_incident_ts:
            del self.last_group_incident_ts[str(group_name)]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> FacilityBudgetState:
        if not data or not isinstance(data, dict):
            return cls()
        inc_ts_raw = data.get("last_group_incident_ts", {})
        inc_ts = {str(k): float(v) for k, v in inc_ts_raw.items()} if isinstance(inc_ts_raw, dict) else {}
        return cls(
            last_facility_transition_ts=float(data.get("last_facility_transition_ts", 0.0)),
            active_transition_miner=str(data.get("active_transition_miner", "")),
            active_transition_target_preset=str(data.get("active_transition_target_preset", "")),
            settle_window_seconds=float(data.get("settle_window_seconds", DEFAULT_FACILITY_SETTLE_WINDOW_S)),
            incident_quiet_window_s=float(data.get("incident_quiet_window_s", DEFAULT_INCIDENT_QUIET_WINDOW_S)),
            last_group_incident_ts=inc_ts,
        )


@dataclass(frozen=True)
class ScheduleEvaluation:
    """Outcome of evaluating soft-contingency calendar rules."""
    is_peak_window: bool
    window_name: str                  # "morning_peak", "evening_peak", "off_peak_weekday", "weekend_valley"
    max_individual_preset: str        # "2500W" in peak, "2700W" in valley
    max_elevator_budget_w: int        # 5000W in peak, 5400W in valley
    reason: str


def evaluate_soft_contingency_schedule(
    now_dt: Optional[datetime] = None,
    config: Optional[Dict[str, Any]] = None,
) -> ScheduleEvaluation:
    """Evaluate whether the current moment falls in an electrical grid peak window.
    
    Schedule (Local Time):
    - Weekdays (Monday=0 through Friday=4):
      - Morning Peak: Configurable (defaults to 08:30-10:30 if config is None, or 08:30-09:30 if config provided)
      - Evening Peak: Configurable (defaults to 19:30-22:30 if config is None, or 20:00-21:15 if config provided)
    - Weekends (Saturday=5, Sunday=6):
      - 100% valley / stable operation. Full exploration allowed.
      
    Args:
        now_dt: Optional datetime instance (defaults to datetime.now())
        config: Optional configuration dictionary
        
    Returns:
        ScheduleEvaluation with peak status, allowed ceilings, and descriptive reason.
    """
    dt = now_dt or datetime.now()
    weekday = dt.weekday()  # 0=Mon, 4=Fri, 5=Sat, 6=Sun
    t = dt.time()

    # Weekends are completely open for full power exploration
    if weekday in (5, 6):
        day_str = "Sábado" if weekday == 5 else "Domingo"
        return ScheduleEvaluation(
            is_peak_window=False,
            window_name="weekend_valley",
            max_individual_preset=DEFAULT_VALLEY_MAX_PRESET,
            max_elevator_budget_w=DEFAULT_VALLEY_ELEVATOR_BUDGET_W,
            reason=f"Fin de semana ({day_str}): red de alta estabilidad, sin soft-contingencia horaria",
        )

    if config is not None and isinstance(config, dict):
        morning_start = parse_time_str(config.get("soft_contingency_morning_start"), dtime(8, 30))
        morning_end = parse_time_str(config.get("soft_contingency_morning_end"), dtime(9, 30))
        evening_start = parse_time_str(config.get("soft_contingency_evening_start"), dtime(20, 0))
        evening_end = parse_time_str(config.get("soft_contingency_evening_end"), dtime(21, 15))
        peak_preset = str(config.get("soft_contingency_peak_max_preset", DEFAULT_PEAK_MAX_PRESET))
        valley_preset = str(config.get("soft_contingency_valley_max_preset", DEFAULT_VALLEY_MAX_PRESET))
    else:
        morning_start = dtime(8, 30)
        morning_end = dtime(10, 30)
        evening_start = dtime(19, 30)
        evening_end = dtime(22, 30)
        peak_preset = DEFAULT_PEAK_MAX_PRESET
        valley_preset = DEFAULT_VALLEY_MAX_PRESET

    peak_budget_w = parse_preset_wattage(peak_preset) * 2
    valley_budget_w = parse_preset_wattage(valley_preset) * 2

    # Weekdays: Check Morning Peak
    if morning_start <= t < morning_end:
        return ScheduleEvaluation(
            is_peak_window=True,
            window_name="morning_peak",
            max_individual_preset=peak_preset,
            max_elevator_budget_w=peak_budget_w,
            reason=f"Franja pico matutina día hábil ({morning_start.strftime('%H:%M')}-{morning_end.strftime('%H:%M')}): soft-contingencia activa a {peak_preset} ({peak_budget_w}W/elevador)",
        )

    # Weekdays: Check Evening Peak
    if evening_start <= t < evening_end:
        return ScheduleEvaluation(
            is_peak_window=True,
            window_name="evening_peak",
            max_individual_preset=peak_preset,
            max_elevator_budget_w=peak_budget_w,
            reason=f"Franja pico nocturna día hábil ({evening_start.strftime('%H:%M')}-{evening_end.strftime('%H:%M')}): soft-contingencia activa a {peak_preset} ({peak_budget_w}W/elevador)",
        )

    # Weekdays off-peak
    return ScheduleEvaluation(
        is_peak_window=False,
        window_name="off_peak_weekday",
        max_individual_preset=valley_preset,
        max_elevator_budget_w=valley_budget_w,
        reason=f"Horario valle día hábil: autorizada exploración escalonada hasta {valley_preset} ({valley_budget_w}W/elevador)",
    )


@dataclass(frozen=True)
class SolarEnvelopeEvaluation:
    """Outcome of evaluating solar thermal envelope rules (11:00-17:00 hs)."""
    is_solar_window: bool
    is_overheated: bool
    max_authorized_preset: str
    reason: str


def evaluate_solar_thermal_envelope(
    now_dt: Optional[datetime] = None,
    max_chip_temp_c: float = 0.0,
    config: Optional[Dict[str, Any]] = None,
) -> SolarEnvelopeEvaluation:
    """Evaluate solar thermal constraints during the midday/afternoon solar heating window.
    
    Hours: 11:00 to 17:00 hs every day (local time UTC-3).
    Rule: Fleet ceiling is clamped to 2500W to avoid hitting VNish 84°C decrease_temp tripwire.
    If max_chip_temp_c >= 82.0°C: strictly enforces 2500W and signals critical thermal relief.
    If outside 11:00-17:00 hs: solar constraint is inactive (valley default allowed).
    """
    dt = now_dt or datetime.now()
    t = dt.time()

    solar_start = parse_time_str(
        config.get("solar_thermal_start") if config else None,
        DEFAULT_SOLAR_WINDOW_START,
    )
    solar_end = parse_time_str(
        config.get("solar_thermal_end") if config else None,
        DEFAULT_SOLAR_WINDOW_END,
    )
    solar_preset = str(
        config.get("solar_thermal_max_preset", DEFAULT_SOLAR_MAX_PRESET)
        if config else DEFAULT_SOLAR_MAX_PRESET
    )
    crit_temp = float(
        config.get("solar_thermal_critical_temp_c", DEFAULT_SOLAR_CRITICAL_TEMP_C)
        if config else DEFAULT_SOLAR_CRITICAL_TEMP_C
    )

    if solar_start <= t < solar_end:
        if max_chip_temp_c >= crit_temp:
            return SolarEnvelopeEvaluation(
                is_solar_window=True,
                is_overheated=True,
                max_authorized_preset=DEFAULT_SOLAR_MAX_PRESET,
                reason=(
                    f"Franja solar crítica ({solar_start.strftime('%H:%M')}-{solar_end.strftime('%H:%M')}) "
                    f"con chip a {max_chip_temp_c:.1f}°C >= {crit_temp:.1f}°C: "
                    f"techo forzado a {DEFAULT_SOLAR_MAX_PRESET} para prevenir corte brusco VNish a 84°C."
                ),
            )
        return SolarEnvelopeEvaluation(
            is_solar_window=True,
            is_overheated=False,
            max_authorized_preset=solar_preset,
            reason=(
                f"Franja solar activa ({solar_start.strftime('%H:%M')}-{solar_end.strftime('%H:%M')}): "
                f"techo preventivo fijado en {solar_preset}."
            ),
        )

    return SolarEnvelopeEvaluation(
        is_solar_window=False,
        is_overheated=False,
        max_authorized_preset=DEFAULT_VALLEY_MAX_PRESET,
        reason="Fuera de franja solar: autorizada plena exploración según calendario y red.",
    )


def get_miner_max_hardware_preset(
    miner_name: str,
    config: Optional[Dict[str, Any]] = None,
    default_preset: str = DEFAULT_VALLEY_MAX_PRESET,
) -> str:
    """Retrieve the maximum hardware capability ceiling for an individual miner.
    
    Reads from miner definition in config['miners'] or config['miner_hardware_limits'].
    Defaults to default_preset (2700W) if not restricted.
    """
    if not config or not isinstance(config, dict):
        return default_preset

    norm = normalize_miner_name(miner_name)
    miners_list = config.get("miners", [])
    if isinstance(miners_list, list):
        for m in miners_list:
            if isinstance(m, dict):
                m_name = m.get("name", "")
                m_ip = m.get("ip", "")
                if normalize_miner_name(m_name) == norm or normalize_miner_name(m_ip) == norm:
                    hw_limit = m.get("max_hardware_preset") or m.get("hardware_ceiling")
                    if hw_limit:
                        clean = str(hw_limit).strip().upper()
                        if not clean.endswith("W") and clean.isdigit():
                            clean = f"{clean}W"
                        return clean

    hw_map = config.get("miner_hardware_limits")
    if isinstance(hw_map, dict):
        for k, v in hw_map.items():
            if normalize_miner_name(k) == norm:
                clean = str(v).strip().upper()
                if not clean.endswith("W") and clean.isdigit():
                    clean = f"{clean}W"
                return clean

    return default_preset



def calculate_group_wattage(group_presets: Dict[str, str]) -> int:
    """Compute combined nominal wattage for an elevator group."""
    total = 0
    for p in group_presets.values():
        total += parse_preset_wattage(p)
    return total


def can_step_up_within_budget(
    candidate_miner: str,
    target_preset: str,
    group_presets: Dict[str, str],
    max_budget_w: int = DEFAULT_VALLEY_ELEVATOR_BUDGET_W,
) -> Tuple[bool, int, str]:
    """Check if stepping candidate_miner up to target_preset stays within max_budget_w.
    
    Args:
        candidate_miner: Miner requesting step-up.
        target_preset: Desired new preset.
        group_presets: Dict of miner_name -> current_preset for the elevator group.
        max_budget_w: Maximum allowed group wattage (5000W or 5400W).
        
    Returns:
        Tuple[bool, int, str]: (is_allowed, projected_total_w, reason_msg)
    """
    target_w = parse_preset_wattage(target_preset)
    norm_cand = normalize_miner_name(candidate_miner)

    projected_total = 0
    found_cand = False
    for m_name, p_name in group_presets.items():
        if normalize_miner_name(m_name) == norm_cand:
            projected_total += target_w
            found_cand = True
        else:
            projected_total += parse_preset_wattage(p_name)

    if not found_cand:
        projected_total += target_w

    if projected_total <= max_budget_w:
        return True, projected_total, "OK"

    return False, projected_total, (
        f"Excede presupuesto de elevador: {projected_total}W > {max_budget_w}W máximo"
    )


def evaluate_symmetric_balance_preference(
    candidate_miner: str,
    target_preset: str,
    group_presets: Dict[str, str],
) -> Tuple[bool, str]:
    """Enforce symmetric balance preference (REQ-001).
    
    Two miners at 2500W (5000W) are strictly prioritized over an extreme
    asymmetric configuration like 2700W + 2300W. A miner cannot step up to 2700W
    if its partner in the elevator group has not yet reached 2500W.
    
    Args:
        candidate_miner: Miner attempting to step up.
        target_preset: Target preset requested.
        group_presets: All presets currently running in this elevator group.
        
    Returns:
        Tuple[bool, str]: (allowed, reason)
    """
    target_idx = find_preset_index(target_preset)
    idx_2700 = find_preset_index("2700W")
    idx_2500 = find_preset_index("2500W")

    # If not attempting to exceed 2500W (e.g. stepping up to 2300W or 2500W), symmetry rule is met
    if target_idx < idx_2700:
        return True, "OK"

    norm_cand = normalize_miner_name(candidate_miner)
    for m_name, p_name in group_presets.items():
        if normalize_miner_name(m_name) != norm_cand:
            partner_idx = find_preset_index(p_name)
            if partner_idx < idx_2500:
                return False, (
                    f"Preferencia simétrica de elevador: compañero {m_name} ({p_name}) "
                    f"debe alcanzar 2500W antes de que {candidate_miner} suba a {target_preset} "
                    f"(se prioriza balance 2x 2500W sobre asimetría 2700W/2300W)"
                )
    return True, "OK"


@dataclass(frozen=True)
class StaggeredDecision:
    """Comprehensive decision on whether a preset transition may proceed."""
    action: str
    can_proceed: bool
    miner_name: str
    target_preset: str
    reason: str
    remaining_settle_seconds: float = 0.0
    projected_group_power_w: int = 0
    max_authorized_budget_w: int = 0


def evaluate_facility_transition_permission(
    miner_name: str,
    current_preset: str,
    target_preset: str,
    group_name: str,
    group_presets: Dict[str, str],
    now_ts: float,
    facility_state: FacilityBudgetState,
    now_dt: Optional[datetime] = None,
    is_step_down: bool = False,
    config: Optional[Dict[str, Any]] = None,
    max_chip_temp_c: float = 0.0,
    miner_hardware_max_preset: Optional[str] = None,
) -> StaggeredDecision:
    """Pure evaluation of whether an ASIC miner is authorized to change preset.
    
    Step-downs are emergency relief actions and are ALWAYS permitted to relieve
    electrical or thermal stress, but they still register with the facility settle
    tracker to give the shared drop line time to stabilize.
    
    Step-ups MUST satisfy:
    0. Group Incident Quiet Window (300s elapsed post-incident on this elevator group).
    1. Facility Settle Window (180s elapsed since last transition across the whole plant).
    2. Individual Hardware Ceiling (e.g. Miner 25 silicon limit of 2500W).
    3. Solar Thermal Envelope (11:00-17:00 hs clamped to 2500W if overheated/solar window).
    4. Soft-Contingency Schedule: Cannot exceed schedule max preset (e.g. 2500W in peak).
    5. Group Power Budget: Total group wattage <= allowed budget (5000W or 5400W).
    6. Symmetric Balance: Partner must be at least 2500W before candidate reaches 2700W.
    """
    curr_w = parse_preset_wattage(current_preset)
    target_w = parse_preset_wattage(target_preset)
    sched = evaluate_soft_contingency_schedule(now_dt, config=config)

    # Step-downs (downward power reductions)
    if is_step_down or target_w < curr_w:
        proj_ok, proj_w, _ = can_step_up_within_budget(
            miner_name, target_preset, group_presets, max_budget_w=sched.max_elevator_budget_w
        )
        return StaggeredDecision(
            action=ACTION_ALLOW_TRANSITION,
            can_proceed=True,
            miner_name=miner_name,
            target_preset=target_preset,
            reason=f"Desescalada permitida (alivio de red): {current_preset} -> {target_preset}",
            remaining_settle_seconds=0.0,
            projected_group_power_w=proj_w,
            max_authorized_budget_w=sched.max_elevator_budget_w,
        )

    # Gate 0 — Group Incident Quiet Window (Spec 078 / PROP-013)
    in_quiet, rem_q = facility_state.is_group_in_incident_quiet(group_name, now_ts)
    if in_quiet:
        return StaggeredDecision(
            action=ACTION_HOLD_INCIDENT_QUIET,
            can_proceed=False,
            miner_name=miner_name,
            target_preset=target_preset,
            reason=(
                f"Grupo '{group_name}' en reposo post-incidente: {rem_q:.0f}s restantes de ventana de "
                f"{facility_state.incident_quiet_window_s:.0f}s. Evitando perturbación inductiva y ruido en elevador."
            ),
            remaining_settle_seconds=rem_q,
            projected_group_power_w=calculate_group_wattage(group_presets),
            max_authorized_budget_w=sched.max_elevator_budget_w,
        )

    # Gate 1 — Facility Settle Lock across shared drop line (Spec 077 / PROP-012)
    in_settle, rem_s, active_m = facility_state.is_facility_in_settle(now_ts)
    if in_settle:
        return StaggeredDecision(
            action=ACTION_HOLD_FACILITY_SETTLE,
            can_proceed=False,
            miner_name=miner_name,
            target_preset=target_preset,
            reason=(
                f"Bajada compartida en estabilización: {rem_s:.0f}s restantes de ventana de 180s "
                f"(último cambio en {active_m}). Esperando reposo inductivo/térmico de acometida."
            ),
            remaining_settle_seconds=rem_s,
            projected_group_power_w=calculate_group_wattage(group_presets),
            max_authorized_budget_w=sched.max_elevator_budget_w,
        )

    # Gate 2 — Individual Silicon Hardware Ceiling (Spec 078 / PROP-013)
    hw_max = miner_hardware_max_preset or get_miner_max_hardware_preset(miner_name, config=config)
    hw_idx = find_preset_index(hw_max)
    target_idx = find_preset_index(target_preset)
    if hw_idx >= 0 and target_idx > hw_idx:
        return StaggeredDecision(
            action=ACTION_HOLD_HARDWARE_LIMIT,
            can_proceed=False,
            miner_name=miner_name,
            target_preset=target_preset,
            reason=(
                f"Límite de silicio de hardware individual para {miner_name}: techo fijado en {hw_max}. "
                f"No se autoriza escalamiento a {target_preset} por inestabilidad de PLL/autotune comprobada."
            ),
            remaining_settle_seconds=0.0,
            projected_group_power_w=calculate_group_wattage(group_presets),
            max_authorized_budget_w=sched.max_elevator_budget_w,
        )

    # Gate 3 — Solar Thermal Envelope Check (Spec 078 / PROP-013)
    solar_eval = evaluate_solar_thermal_envelope(now_dt, max_chip_temp_c=max_chip_temp_c, config=config)
    solar_max_idx = find_preset_index(solar_eval.max_authorized_preset)
    if solar_eval.is_solar_window and solar_max_idx >= 0 and target_idx > solar_max_idx:
        return StaggeredDecision(
            action=ACTION_HOLD_SOLAR_ENVELOPE,
            can_proceed=False,
            miner_name=miner_name,
            target_preset=target_preset,
            reason=f"Límite térmico solar activo: {solar_eval.reason}",
            remaining_settle_seconds=0.0,
            projected_group_power_w=calculate_group_wattage(group_presets),
            max_authorized_budget_w=sched.max_elevator_budget_w,
        )

    # Gate 3.1 — Thermal Headroom Gate for Presets > 2500W
    limit_2500_idx = find_preset_index("2500W")
    if limit_2500_idx >= 0 and target_idx > limit_2500_idx:
        max_th_temp = float(
            config.get("valley_step_up_max_chip_temp_c", DEFAULT_VALLEY_STEP_UP_MAX_CHIP_TEMP_C)
            if config else DEFAULT_VALLEY_STEP_UP_MAX_CHIP_TEMP_C
        )
        if max_chip_temp_c > 0.0 and max_chip_temp_c >= max_th_temp:
            return StaggeredDecision(
                action=ACTION_HOLD_THERMAL_HEADROOM,
                can_proceed=False,
                miner_name=miner_name,
                target_preset=target_preset,
                reason=(
                    f"Margen térmico insuficiente para {miner_name}: chip a {max_chip_temp_c:.1f}°C >= {max_th_temp:.1f}°C. "
                    f"Se requiere chip < {max_th_temp:.1f}°C antes de permitir escalamiento a {target_preset}."
                ),
                remaining_settle_seconds=0.0,
                projected_group_power_w=calculate_group_wattage(group_presets),
                max_authorized_budget_w=sched.max_elevator_budget_w,
            )

    # Gate 4 — Schedule ceiling check (Soft-Contingency Peak)
    sched_max_idx = find_preset_index(sched.max_individual_preset)
    if sched_max_idx >= 0 and target_idx > sched_max_idx:
        return StaggeredDecision(
            action=ACTION_HOLD_SCHEDULE_CEILING,
            can_proceed=False,
            miner_name=miner_name,
            target_preset=target_preset,
            reason=(
                f"Límite de soft-contingencia horaria activo ({sched.window_name}): "
                f"techo máximo autorizado es {sched.max_individual_preset}. {sched.reason}"
            ),
            remaining_settle_seconds=0.0,
            projected_group_power_w=calculate_group_wattage(group_presets),
            max_authorized_budget_w=sched.max_elevator_budget_w,
        )

    # Gate 5 — Group Power Budget
    budget_ok, proj_w, budget_msg = can_step_up_within_budget(
        candidate_miner=miner_name,
        target_preset=target_preset,
        group_presets=group_presets,
        max_budget_w=sched.max_elevator_budget_w,
    )
    if not budget_ok:
        return StaggeredDecision(
            action=ACTION_HOLD_BUDGET_LIMIT,
            can_proceed=False,
            miner_name=miner_name,
            target_preset=target_preset,
            reason=budget_msg,
            remaining_settle_seconds=0.0,
            projected_group_power_w=proj_w,
            max_authorized_budget_w=sched.max_elevator_budget_w,
        )

    # Gate 6 — Symmetric Balance Preference
    symm_ok, symm_msg = evaluate_symmetric_balance_preference(
        candidate_miner=miner_name,
        target_preset=target_preset,
        group_presets=group_presets,
    )
    if not symm_ok:
        return StaggeredDecision(
            action=ACTION_HOLD_ASYMMETRY_PREFERENCE,
            can_proceed=False,
            miner_name=miner_name,
            target_preset=target_preset,
            reason=symm_msg,
            remaining_settle_seconds=0.0,
            projected_group_power_w=proj_w,
            max_authorized_budget_w=sched.max_elevator_budget_w,
        )

    # All gates passed!
    return StaggeredDecision(
        action=ACTION_ALLOW_TRANSITION,
        can_proceed=True,
        miner_name=miner_name,
        target_preset=target_preset,
        reason="Autorizado: cumple presupuesto de elevador, simetría, límites de silicio y reposo de bajada compartida",
        remaining_settle_seconds=0.0,
        projected_group_power_w=proj_w,
        max_authorized_budget_w=sched.max_elevator_budget_w,
    )
