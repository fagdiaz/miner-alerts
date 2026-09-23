"""Unit tests for Thermal Policy and Canonical Temperature Ladder (Hallazgo 7)."""

import pytest
from app.governance.thermal_policy import (
    TEMP_STEP_UP_CEILING_C,
    FAN_STEP_UP_MAX_DUTY_PCT,
    TEMP_TARGET_OPERATING_C,
    TEMP_DEADBAND_LOW_C,
    TEMP_DEADBAND_HIGH_C,
    TEMP_SUSTAINED_TRIPWIRE_C,
    SUSTAINED_TRIPWIRE_WINDOW_S,
    TEMP_IMMEDIATE_TRIPWIRE_C,
    THERMAL_LOCKOUT_SECONDS,
    TEMP_CRITICAL_DOWNSTEP_C,
    SEVERITY_OPTIMAL,
    SEVERITY_NORMAL,
    SEVERITY_WARM,
    SEVERITY_ELEVATED,
    SEVERITY_SUSTAINED,
    SEVERITY_FALLBACK,
    SEVERITY_CRITICAL,
    ThermalLadder,
    ThermalAssessment,
    get_canonical_thermal_ladder,
    evaluate_chip_thermal_state,
    is_safe_for_step_up,
)


def test_thermal_ladder_defaults():
    ladder = get_canonical_thermal_ladder()
    assert ladder.step_up_max_chip_c == 80.0
    assert ladder.step_up_max_fan_pct == 90.0
    assert ladder.target_operating_c == 81.0
    assert ladder.deadband_low_c == 81.0
    assert ladder.deadband_high_c == 82.5
    assert ladder.sustained_tripwire_c == 83.0
    assert ladder.sustained_window_s == 60.0
    assert ladder.immediate_tripwire_c == 83.5
    assert ladder.critical_downstep_c == 84.0
    assert ladder.lockout_seconds == 1800.0


def test_thermal_ladder_config_override():
    config = {
        "thermal_policy": {
            "step_up_max_chip_c": 79.0,
            "step_up_max_fan_pct": 85.0,
            "target_operating_c": 80.0,
            "deadband_high_c": 82.0,
            "sustained_tripwire_c": 82.5,
            "immediate_tripwire_c": 83.0,
            "critical_downstep_c": 83.5,
            "lockout_seconds": 900.0,
        }
    }
    ladder = get_canonical_thermal_ladder(config)
    assert ladder.step_up_max_chip_c == 79.0
    assert ladder.step_up_max_fan_pct == 85.0
    assert ladder.target_operating_c == 80.0
    assert ladder.deadband_high_c == 82.0
    assert ladder.sustained_tripwire_c == 82.5
    assert ladder.immediate_tripwire_c == 83.0
    assert ladder.critical_downstep_c == 83.5
    assert ladder.lockout_seconds == 900.0


def test_evaluate_chip_thermal_state_critical():
    res = evaluate_chip_thermal_state(84.5)
    assert res.severity == SEVERITY_CRITICAL
    assert res.requires_critical_downstep is True
    assert res.requires_fallback is True
    assert res.can_step_up is False
    assert res.fan_emergency_required is True
    assert "Techo crítico" in res.reason


def test_evaluate_chip_thermal_state_immediate_tripwire():
    res = evaluate_chip_thermal_state(83.6)
    assert res.severity == SEVERITY_FALLBACK
    assert res.requires_fallback is True
    assert res.requires_critical_downstep is False
    assert res.can_step_up is False
    assert res.fan_emergency_required is True
    assert "Tripwire inmediato" in res.reason


def test_evaluate_chip_thermal_state_sustained_tripwire():
    res = evaluate_chip_thermal_state(83.1)
    assert res.severity == SEVERITY_SUSTAINED
    assert res.requires_fallback is False
    assert res.requires_critical_downstep is False
    assert res.can_step_up is False
    assert res.fan_emergency_required is True
    assert "alerta sostenida" in res.reason


def test_evaluate_chip_thermal_state_elevated():
    res = evaluate_chip_thermal_state(82.7)
    assert res.severity == SEVERITY_ELEVATED
    assert res.requires_fallback is False
    assert res.can_step_up is False
    assert res.fan_emergency_required is False
    assert "banda muerta" in res.reason


def test_evaluate_chip_thermal_state_warm():
    res = evaluate_chip_thermal_state(81.5)
    assert res.severity == SEVERITY_WARM
    assert res.requires_fallback is False
    assert res.can_step_up is False
    assert "excede techo para escalada" in res.reason


def test_evaluate_chip_thermal_state_step_up_safe():
    res = evaluate_chip_thermal_state(79.5, fan_duty_pct=75.0)
    assert res.severity == SEVERITY_NORMAL
    assert res.can_step_up is True
    assert res.requires_fallback is False
    assert "segura" in res.reason


def test_evaluate_chip_thermal_state_step_up_blocked_by_fans():
    res = evaluate_chip_thermal_state(79.0, fan_duty_pct=95.0)
    assert res.severity == SEVERITY_NORMAL
    assert res.can_step_up is False
    assert "Fans saturados" in res.reason


def test_evaluate_chip_thermal_state_optimal():
    res = evaluate_chip_thermal_state(77.0, fan_duty_pct=60.0)
    assert res.severity == SEVERITY_OPTIMAL
    assert res.can_step_up is True


def test_is_safe_for_step_up_helper():
    ok, reason = is_safe_for_step_up(78.5, fan_duty_pct=85.0)
    assert ok is True

    ok, reason = is_safe_for_step_up(81.0, fan_duty_pct=85.0)
    assert ok is False
    assert "excede techo" in reason

    ok, reason = is_safe_for_step_up(79.0, fan_duty_pct=92.0)
    assert ok is False
    assert "Fans saturados" in reason
