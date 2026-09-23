"""
Thermal Policy & Canonical Temperature Ladder (Spec 079 / QA Audit Hardening).

Centralizes all thermal safety thresholds, temperature deadbands, and thermal tripwires
for Antminer S19j Pro fleet under VNish firmware across the entire codebase.

Canonical Thermal Ladder:
  1. <= 80.0°C: Safe step-up ceiling (allows promotion to 2700W if fan duty < 90%).
  2.    81.0°C: Nominal operating target temperature.
  3.    82.5°C: High deadband ceiling (fan governor starts aggressive ramp-up).
  4.    83.0°C: Sustained thermal tripwire (emergency 100% fan duty / 60s sustained alert).
  5.    83.5°C: Immediate progression fallback tripwire (drop 2700W -> 2500W immediately).
  6. >= 84.0°C: Critical hardware protection ceiling (mandatory step-down to 2300W/2500W).

Pure deterministic domain logic, zero network I/O, 100% testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

# Canonical constants (°C)
TEMP_STEP_UP_CEILING_C: float = 80.0
FAN_STEP_UP_MAX_DUTY_PCT: float = 90.0

TEMP_TARGET_OPERATING_C: float = 81.0
TEMP_DEADBAND_LOW_C: float = 81.0
TEMP_DEADBAND_HIGH_C: float = 82.5

TEMP_SUSTAINED_TRIPWIRE_C: float = 83.0
SUSTAINED_TRIPWIRE_WINDOW_S: float = 60.0

TEMP_IMMEDIATE_TRIPWIRE_C: float = 83.5
THERMAL_LOCKOUT_SECONDS: float = 1800.0  # 30 minutes

TEMP_CRITICAL_DOWNSTEP_C: float = 84.0

# Severity Levels
SEVERITY_OPTIMAL = "OPTIMAL"        # <= 78°C
SEVERITY_NORMAL = "NORMAL"          # 78°C - 80°C
SEVERITY_WARM = "WARM"              # 80°C - 82.5°C
SEVERITY_ELEVATED = "ELEVATED"      # 82.5°C - 83.0°C
SEVERITY_SUSTAINED = "SUSTAINED"    # 83.0°C - 83.5°C
SEVERITY_FALLBACK = "FALLBACK"      # 83.5°C - 84.0°C
SEVERITY_CRITICAL = "CRITICAL"      # >= 84.0°C


@dataclass(frozen=True)
class ThermalLadder:
    step_up_max_chip_c: float = TEMP_STEP_UP_CEILING_C
    step_up_max_fan_pct: float = FAN_STEP_UP_MAX_DUTY_PCT
    target_operating_c: float = TEMP_TARGET_OPERATING_C
    deadband_low_c: float = TEMP_DEADBAND_LOW_C
    deadband_high_c: float = TEMP_DEADBAND_HIGH_C
    sustained_tripwire_c: float = TEMP_SUSTAINED_TRIPWIRE_C
    sustained_window_s: float = SUSTAINED_TRIPWIRE_WINDOW_S
    immediate_tripwire_c: float = TEMP_IMMEDIATE_TRIPWIRE_C
    critical_downstep_c: float = TEMP_CRITICAL_DOWNSTEP_C
    lockout_seconds: float = THERMAL_LOCKOUT_SECONDS

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_up_max_chip_c": self.step_up_max_chip_c,
            "step_up_max_fan_pct": self.step_up_max_fan_pct,
            "target_operating_c": self.target_operating_c,
            "deadband_low_c": self.deadband_low_c,
            "deadband_high_c": self.deadband_high_c,
            "sustained_tripwire_c": self.sustained_tripwire_c,
            "sustained_window_s": self.sustained_window_s,
            "immediate_tripwire_c": self.immediate_tripwire_c,
            "critical_downstep_c": self.critical_downstep_c,
            "lockout_seconds": self.lockout_seconds,
        }


@dataclass(frozen=True)
class ThermalAssessment:
    chip_temp_c: float
    severity: str
    fan_duty_pct: Optional[float] = None
    can_step_up: bool = False
    requires_fallback: bool = False
    requires_critical_downstep: bool = False
    fan_emergency_required: bool = False
    reason: str = ""


_DEFAULT_LADDER = ThermalLadder()


def get_canonical_thermal_ladder(config: Optional[Dict[str, Any]] = None) -> ThermalLadder:
    """Resolve the canonical thermal ladder from optional configuration dict or defaults."""
    if not config or not isinstance(config, dict):
        return _DEFAULT_LADDER

    tp_cfg = config.get("thermal_policy", {})
    if not isinstance(tp_cfg, dict):
        tp_cfg = {}

    return ThermalLadder(
        step_up_max_chip_c=float(tp_cfg.get("step_up_max_chip_c", config.get("power_progression_max_chip_temp_c", TEMP_STEP_UP_CEILING_C))),
        step_up_max_fan_pct=float(tp_cfg.get("step_up_max_fan_pct", config.get("power_progression_max_fan_duty_pct", FAN_STEP_UP_MAX_DUTY_PCT))),
        target_operating_c=float(tp_cfg.get("target_operating_c", config.get("fan_governor_target_temp", TEMP_TARGET_OPERATING_C))),
        deadband_low_c=float(tp_cfg.get("deadband_low_c", config.get("fan_governor_deadband_low", TEMP_DEADBAND_LOW_C))),
        deadband_high_c=float(tp_cfg.get("deadband_high_c", config.get("fan_governor_deadband_high", TEMP_DEADBAND_HIGH_C))),
        sustained_tripwire_c=float(tp_cfg.get("sustained_tripwire_c", config.get("power_progression_sustained_tripwire_c", TEMP_SUSTAINED_TRIPWIRE_C))),
        sustained_window_s=float(tp_cfg.get("sustained_window_s", config.get("power_progression_sustained_seconds", SUSTAINED_TRIPWIRE_WINDOW_S))),
        immediate_tripwire_c=float(tp_cfg.get("immediate_tripwire_c", config.get("power_progression_thermal_tripwire_c", TEMP_IMMEDIATE_TRIPWIRE_C))),
        critical_downstep_c=float(tp_cfg.get("critical_downstep_c", TEMP_CRITICAL_DOWNSTEP_C)),
        lockout_seconds=float(tp_cfg.get("lockout_seconds", config.get("power_progression_thermal_lockout_seconds", THERMAL_LOCKOUT_SECONDS))),
    )


def evaluate_chip_thermal_state(
    chip_temp_c: float,
    fan_duty_pct: Optional[float] = None,
    ladder: Optional[ThermalLadder] = None,
) -> ThermalAssessment:
    """
    Evaluate chip temperature against the canonical thermal ladder.
    Returns a deterministic ThermalAssessment.
    """
    lad = ladder or _DEFAULT_LADDER
    t = float(chip_temp_c)

    if t >= lad.critical_downstep_c:
        return ThermalAssessment(
            chip_temp_c=t,
            severity=SEVERITY_CRITICAL,
            fan_duty_pct=fan_duty_pct,
            can_step_up=False,
            requires_fallback=True,
            requires_critical_downstep=True,
            fan_emergency_required=True,
            reason=f"Chip {t:.1f}°C >= Techo crítico ({lad.critical_downstep_c:.1f}°C): desescalada obligatoria",
        )

    if t >= lad.immediate_tripwire_c:
        return ThermalAssessment(
            chip_temp_c=t,
            severity=SEVERITY_FALLBACK,
            fan_duty_pct=fan_duty_pct,
            can_step_up=False,
            requires_fallback=True,
            requires_critical_downstep=False,
            fan_emergency_required=True,
            reason=f"Chip {t:.1f}°C >= Tripwire inmediato ({lad.immediate_tripwire_c:.1f}°C): fallback a 2500W",
        )

    if t >= lad.sustained_tripwire_c:
        return ThermalAssessment(
            chip_temp_c=t,
            severity=SEVERITY_SUSTAINED,
            fan_duty_pct=fan_duty_pct,
            can_step_up=False,
            requires_fallback=False,
            requires_critical_downstep=False,
            fan_emergency_required=True,
            reason=f"Chip {t:.1f}°C en zona de alerta sostenida (>={lad.sustained_tripwire_c:.1f}°C): fans al 100%",
        )

    if t > lad.deadband_high_c:
        return ThermalAssessment(
            chip_temp_c=t,
            severity=SEVERITY_ELEVATED,
            fan_duty_pct=fan_duty_pct,
            can_step_up=False,
            requires_fallback=False,
            requires_critical_downstep=False,
            fan_emergency_required=False,
            reason=f"Chip {t:.1f}°C por encima de banda muerta ({lad.deadband_high_c:.1f}°C): rampa de ventilación",
        )

    if t > lad.step_up_max_chip_c:
        return ThermalAssessment(
            chip_temp_c=t,
            severity=SEVERITY_WARM,
            fan_duty_pct=fan_duty_pct,
            can_step_up=False,
            requires_fallback=False,
            requires_critical_downstep=False,
            fan_emergency_required=False,
            reason=f"Chip {t:.1f}°C excede techo para escalada ({lad.step_up_max_chip_c:.1f}°C)",
        )

    # Chip is <= step_up_max_chip_c (<= 80.0°C)
    fan_ok = True
    fan_reason = ""
    if fan_duty_pct is not None:
        if fan_duty_pct >= lad.step_up_max_fan_pct:
            fan_ok = False
            fan_reason = f"Fans saturados ({fan_duty_pct:.0f}% >= {lad.step_up_max_fan_pct:.0f}%)"

    severity = SEVERITY_OPTIMAL if t <= 78.0 else SEVERITY_NORMAL
    if not fan_ok:
        return ThermalAssessment(
            chip_temp_c=t,
            severity=severity,
            fan_duty_pct=fan_duty_pct,
            can_step_up=False,
            requires_fallback=False,
            requires_critical_downstep=False,
            fan_emergency_required=False,
            reason=f"Chip {t:.1f}°C apto, pero {fan_reason}",
        )

    return ThermalAssessment(
        chip_temp_c=t,
        severity=severity,
        fan_duty_pct=fan_duty_pct,
        can_step_up=True,
        requires_fallback=False,
        requires_critical_downstep=False,
        fan_emergency_required=False,
        reason=f"Chip {t:.1f}°C dentro de envolvente térmica segura para operación/escalada",
    )


def is_safe_for_step_up(
    chip_temp_c: float,
    fan_duty_pct: Optional[float] = None,
    ladder: Optional[ThermalLadder] = None,
) -> Tuple[bool, str]:
    """Convenience helper to check if miner thermal status permits power promotion."""
    assessment = evaluate_chip_thermal_state(chip_temp_c, fan_duty_pct=fan_duty_pct, ladder=ladder)
    return assessment.can_step_up, assessment.reason
