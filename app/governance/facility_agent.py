"""
Facility Governance Agent (FGA) - Core Deterministic Engine (Spec 079 / PROP-015).

Provides pure mathematical calculations, empirical silicon thermal modeling (R_th),
asymmetric multi-miner power allocation, and deterministic explanatory diagnostics.
Zero token cost, zero external API dependencies, 100% testable and bounded.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import time

from app.governance.thermal_policy import (
    TEMP_DEADBAND_HIGH_C,
    TEMP_CRITICAL_DOWNSTEP_C,
)

STRATEGY_BALANCED = "balanced"        # 2700W on cool silicon, 2500W on warm silicon
STRATEGY_MAX_POWER = "max_power"      # Push 2700W wherever safe margin exists
STRATEGY_EFFICIENCY = "efficiency"    # Sweet spot 2300W-2500W for best J/TH
STRATEGY_COOL_QUIET = "cool_quiet"    # Keep all <= 2300W and low acoustics

VALID_STRATEGIES = {
    STRATEGY_BALANCED,
    STRATEGY_MAX_POWER,
    STRATEGY_EFFICIENCY,
    STRATEGY_COOL_QUIET,
}

# Physical bounds for S19j Pro (linked to Canonical Thermal Ladder)
DEFAULT_THERMAL_RESISTANCE = 0.022  # °C/W
MIN_THERMAL_RESISTANCE = 0.012      # Exceptional cooling / low inlet
MAX_THERMAL_RESISTANCE = 0.035      # Severely choked airflow
SAFE_TARGET_TEMP_C = TEMP_DEADBAND_HIGH_C           # Target deadband high ceiling (82.5°C)
TRIPWIRE_TEMP_C = TEMP_CRITICAL_DOWNSTEP_C              # Thermal step-down ceiling (84.0°C)
DEFAULT_INLET_TEMP_C = 25.0         # Nominal facility ambient


@dataclass
class MinerThermalProfile:
    miner_name: str
    chip_temp_c: float
    inlet_temp_c: float
    current_power_w: float
    current_preset: str
    thermal_resistance: float
    predicted_temp_2700w: float
    predicted_temp_2500w: float
    predicted_temp_2300w: float
    is_overheating: bool
    cooling_margin_c: float
    cohort: str  # COOL, STANDARD, HOT


@dataclass
class FacilityAgentDecision:
    strategy: str
    target_allocations: Dict[str, str] = field(default_factory=dict)
    candidate_step: Optional[Tuple[str, str, str]] = None  # (miner_name, target_preset, reason)
    total_projected_power_w: float = 0.0
    group_projected_power_w: Dict[str, float] = field(default_factory=dict)
    explanations: Dict[str, str] = field(default_factory=dict)


def calculate_thermal_resistance(
    chip_temp_c: Optional[float],
    inlet_temp_c: Optional[float],
    power_w: Optional[float],
) -> float:
    """Calculate R_th = (T_chip - T_inlet) / P in °C/W.
    
    If telemetry is missing, unreliable, or power < 500W, returns default nominal R_th.
    """
    if (
        chip_temp_c is None
        or inlet_temp_c is None
        or power_w is None
        or power_w < 500.0
        or chip_temp_c <= inlet_temp_c
    ):
        return DEFAULT_THERMAL_RESISTANCE

    delta_t = chip_temp_c - inlet_temp_c
    r_th = delta_t / power_w
    return round(max(MIN_THERMAL_RESISTANCE, min(MAX_THERMAL_RESISTANCE, r_th)), 5)


def predict_chip_temperature(
    inlet_temp_c: float,
    target_power_w: float,
    thermal_resistance: float,
) -> float:
    """Predict chip temperature under steady-state load: T_pred = T_inlet + R_th * P_target."""
    return round(inlet_temp_c + (thermal_resistance * target_power_w), 1)


def classify_silicon_cohort(thermal_resistance: float) -> str:
    """Classify miner silicon and airflow performance."""
    if thermal_resistance <= 0.020:
        return "COOL"      # Low thermal resistance, prime candidate for 2700W
    elif thermal_resistance <= 0.024:
        return "STANDARD"  # Nominal thermal resistance, ideal for 2500W
    else:
        return "HOT"       # Higher thermal resistance, needs lower preset or higher fan flow


def build_thermal_profile(
    miner_name: str,
    chip_temp_c: Optional[float],
    inlet_temp_c: Optional[float],
    power_w: Optional[float],
    current_preset: str = "2500W",
) -> MinerThermalProfile:
    """Construct complete empirical thermal profile for a miner."""
    t_chip = chip_temp_c if chip_temp_c is not None else 80.0
    t_inlet = inlet_temp_c if inlet_temp_c is not None else DEFAULT_INLET_TEMP_C
    p_w = power_w if power_w is not None else 2500.0

    r_th = calculate_thermal_resistance(t_chip, t_inlet, p_w)
    pred_2700 = predict_chip_temperature(t_inlet, 2700.0, r_th)
    pred_2500 = predict_chip_temperature(t_inlet, 2500.0, r_th)
    pred_2300 = predict_chip_temperature(t_inlet, 2300.0, r_th)

    is_overheat = t_chip >= TRIPWIRE_TEMP_C
    margin = round(SAFE_TARGET_TEMP_C - t_chip, 1)
    cohort = classify_silicon_cohort(r_th)

    return MinerThermalProfile(
        miner_name=miner_name,
        chip_temp_c=t_chip,
        inlet_temp_c=t_inlet,
        current_power_w=p_w,
        current_preset=current_preset,
        thermal_resistance=r_th,
        predicted_temp_2700w=pred_2700,
        predicted_temp_2500w=pred_2500,
        predicted_temp_2300w=pred_2300,
        is_overheating=is_overheat,
        cooling_margin_c=margin,
        cohort=cohort,
    )


def evaluate_asymmetric_allocation(
    miners_telemetry: List[Dict[str, Any]],
    max_group_power_w: float = 5400.0,
    max_facility_power_w: float = 10400.0,
    strategy: str = STRATEGY_BALANCED,
) -> FacilityAgentDecision:
    """
    Pure optimization engine. Determines optimal asymmetric power allocation per miner.
    
    Invariants:
    1. Group Power <= max_group_power_w (5400W per elevator).
    2. Total Facility Power <= max_facility_power_w (10400W).
    3. Predicted chip temp T_pred <= 82.5°C before authorizing 2700W.
    4. Overheated miners (T >= 84°C) are capped at <= 2500W (or 2300W).
    """
    strat = strategy if strategy in VALID_STRATEGIES else STRATEGY_BALANCED
    decision = FacilityAgentDecision(strategy=strat)

    profiles: Dict[str, MinerThermalProfile] = {}
    groups: Dict[str, List[Dict[str, Any]]] = {}

    for m in miners_telemetry:
        name = m.get("name", "")
        grp = m.get("electrical_group") or m.get("group", "elevator_1")
        groups.setdefault(grp, []).append(m)

        prof = build_thermal_profile(
            miner_name=name,
            chip_temp_c=m.get("chip_temp_c"),
            inlet_temp_c=m.get("inlet_temp_c"),
            power_w=m.get("power_w"),
            current_preset=m.get("preset", "2500W"),
        )
        profiles[name] = prof

    # Preset wattage map
    power_map = {"2700W": 2700.0, "2500W": 2500.0, "2300W": 2300.0, "1800W": 1800.0}

    # Step 1: Assign baseline presets per strategy
    for grp, m_list in groups.items():
        for m in m_list:
            name = m.get("name", "")
            prof = profiles[name]
            curr_p = m.get("preset", "2500W")

            if strat == STRATEGY_COOL_QUIET:
                decision.target_allocations[name] = "2300W"
                decision.explanations[name] = "Estrategia silenciosa/fría activa (límite 2300W)."

            elif strat == STRATEGY_EFFICIENCY:
                decision.target_allocations[name] = "2300W" if prof.cohort == "HOT" else "2500W"
                decision.explanations[name] = f"Estrategia de eficiencia J/TH activa (cohorte {prof.cohort})."

            elif strat == STRATEGY_MAX_POWER:
                # Max power: try 2700W if predicted temp <= 82.5°C, else 2500W
                if not prof.is_overheating and prof.predicted_temp_2700w <= SAFE_TARGET_TEMP_C:
                    decision.target_allocations[name] = "2700W"
                    decision.explanations[name] = (
                        f"Potencia máxima autorizada (R_th={prof.thermal_resistance:.4f}°C/W, "
                        f"T_pred={prof.predicted_temp_2700w:.1f}°C <= {SAFE_TARGET_TEMP_C}°C)."
                    )
                else:
                    decision.target_allocations[name] = "2500W"
                    decision.explanations[name] = (
                        f"Limitado a 2500W por margen térmico (T_pred a 2700W={prof.predicted_temp_2700w:.1f}°C > {SAFE_TARGET_TEMP_C}°C)."
                    )

            else:  # STRATEGY_BALANCED (Default)
                # Cool silicon or miners in cool elevator can run 2700W
                if (
                    not prof.is_overheating
                    and prof.cohort == "COOL"
                    and prof.predicted_temp_2700w <= SAFE_TARGET_TEMP_C
                ):
                    decision.target_allocations[name] = "2700W"
                    decision.explanations[name] = (
                        f"Asignación asimétrica a 2700W: silicio frío (R_th={prof.thermal_resistance:.4f}°C/W, "
                        f"T_pred={prof.predicted_temp_2700w:.1f}°C)."
                    )
                else:
                    decision.target_allocations[name] = "2500W"
                    decision.explanations[name] = (
                        f"Asignación estable a 2500W: cohorte {prof.cohort} "
                        f"(T actual={prof.chip_temp_c:.1f}°C, T_pred a 2700W={prof.predicted_temp_2700w:.1f}°C)."
                    )

    # Step 2: Enforce Group Constraints (max_group_power_w)
    for grp, m_list in groups.items():
        grp_pwr = sum(power_map.get(decision.target_allocations[m.get("name", "")], 2500.0) for m in m_list)
        if grp_pwr > max_group_power_w:
            # Step down the warmest miner in the group to 2500W or 2300W
            sorted_by_warmth = sorted(
                m_list,
                key=lambda x: profiles[x.get("name", "")].thermal_resistance,
                reverse=True,
            )
            for warm_m in sorted_by_warmth:
                w_name = warm_m.get("name", "")
                if decision.target_allocations[w_name] == "2700W":
                    decision.target_allocations[w_name] = "2500W"
                    decision.explanations[w_name] += f" [Ajustado a 2500W por balance de elevador ({grp_pwr}W > {max_group_power_w}W)]."
                    grp_pwr -= 200.0
                    if grp_pwr <= max_group_power_w:
                        break
        decision.group_projected_power_w[grp] = grp_pwr

    # Step 3: Compute total projected power
    decision.total_projected_power_w = sum(decision.group_projected_power_w.values())

    # Step 4: Identify candidate action if a change is warranted
    for m in miners_telemetry:
        m_name = m.get("name", "")
        curr_p = m.get("preset", "2500W")
        tgt_p = decision.target_allocations.get(m_name, curr_p)
        if curr_p != tgt_p:
            decision.candidate_step = (
                m_name,
                tgt_p,
                decision.explanations.get(m_name, "Optimización de potencia FGA"),
            )
            break

    return decision


def explain_miner_state(
    miner_name: str,
    profile: MinerThermalProfile,
    target_preset: str,
    strategy: str,
) -> str:
    """Generate clear, transparent, deterministic explanation for operator."""
    return (
        f"🤖 *Diagnóstico FGA para {miner_name}*:\n"
        f"• Preset Actual / Objetivo: *{profile.current_preset}* ➔ *{target_preset}*\n"
        f"• Estrategia Activa: *{strategy.upper()}*\n"
        f"• Resistencia Térmica: *{profile.thermal_resistance:.4f} °C/W* (Cohorte: *{profile.cohort}*)\n"
        f"• Temperatura Chip: *{profile.chip_temp_c:.1f}°C* (Inlet: {profile.inlet_temp_c:.1f}°C)\n"
        f"• Proyecciones: 2700W (*{profile.predicted_temp_2700w:.1f}°C*) | 2500W (*{profile.predicted_temp_2500w:.1f}°C*)\n"
        f"• Margen a Límite Seguro (82.5°C): *{profile.cooling_margin_c:+.1f}°C*"
    )
