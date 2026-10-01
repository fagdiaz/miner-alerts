"""
tests/test_governance_context_contracts.py
Spec 082 — MinerGovernanceContext: Tests de Contrato (T001–T011)

Fase 2: Módulo puro (T001–T003)
Fase 3: Integración Fan Governor (T004–T011)
"""
from __future__ import annotations

import time
from dataclasses import FrozenInstanceError
from typing import Any, Dict, Optional

import pytest

from app.governance.governance_context import MinerGovernanceContext
from app.governance.fan_governor import (
    GovernorConfig,
    GovernorDecision,
    compute_governor_step,
    ACTION_RECOVERY_MAX_COOLING,
    ACTION_HOLD_DWELL,
    ACTION_HOLD_TARGET,
    ACTION_STEP_DOWN,
    ACTION_STEP_UP,
    ACTION_UNKNOWN,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers / Fixtures
# ─────────────────────────────────────────────────────────────────────────────


def make_state(**kwargs: Any) -> Any:
    """Crea un estado mock usando SimpleNamespace con campos controlables."""
    from types import SimpleNamespace
    defaults: Dict[str, Any] = {
        "last_power_w": None,
        "vnish_discovered_preset": None,
        "last_max_chip_temp": None,
        "inlet_temp_c": None,
        "fga_thermal_resistance": None,
        "fga_cohort": None,
        "vnish_restart_required": False,
        "vnish_restart_detected_ts": None,
        "thermal_pause_until_ts": None,
        "thermal_lockout_until_ts": None,
        "last_elapsed": None,
        "reboot_pending_until": 0.0,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def make_config(**kwargs: Any) -> Dict[str, Any]:
    defaults: Dict[str, Any] = {
        "name": "S19JPRO-TEST",
        "electrical_group": "elevator_1",
        "autotune_grace_period_seconds": 900.0,
    }
    defaults.update(kwargs)
    return defaults


# ─────────────────────────────────────────────────────────────────────────────
# Fase 2 — Módulo Puro (T001–T003)
# ─────────────────────────────────────────────────────────────────────────────


class TestT001_Immutability:
    """T001: frozen=True garantiza inmutabilidad post-construcción."""

    def test_context_is_immutable(self) -> None:
        ctx = MinerGovernanceContext()
        with pytest.raises(FrozenInstanceError):
            ctx.restart_required = True  # type: ignore[misc]

    def test_context_immutable_optional_field(self) -> None:
        ctx = MinerGovernanceContext(current_power_w=2700.0)
        with pytest.raises(FrozenInstanceError):
            ctx.current_power_w = 0.0  # type: ignore[misc]

    def test_context_immutable_bool_field(self) -> None:
        ctx = MinerGovernanceContext(thermal_pause_active=True)
        with pytest.raises(FrozenInstanceError):
            ctx.thermal_pause_active = False  # type: ignore[misc]


class TestT002_FromStateBasic:
    """T002: from_state() construye correctamente desde campos reales."""

    def test_from_state_basic_construction(self) -> None:
        now_ts = time.time()
        state = make_state(
            last_power_w=2700.0,
            last_max_chip_temp=78.5,
            inlet_temp_c=30.0,
            vnish_restart_required=False,
            last_elapsed=3600.0,
        )
        cfg = make_config()
        ctx = MinerGovernanceContext.from_state(state, now_ts, cfg)

        assert ctx.current_power_w == 2700.0
        assert ctx.chip_temp_c == 78.5
        assert ctx.inlet_temp_c == 30.0
        assert ctx.restart_required is False
        assert ctx.uptime_seconds == 3600.0
        assert ctx.miner_name == "S19JPRO-TEST"
        assert ctx.electrical_group == "elevator_1"
        assert ctx.is_warming_up is False  # 3600 >= 900 grace

    def test_from_state_restart_required_true(self) -> None:
        now_ts = time.time()
        state = make_state(
            last_power_w=2498.0,
            vnish_restart_required=True,
            vnish_restart_detected_ts=now_ts - 60.0,
        )
        cfg = make_config()
        ctx = MinerGovernanceContext.from_state(state, now_ts, cfg)

        assert ctx.restart_required is True
        assert ctx.restart_detected_ts is not None
        assert ctx.current_power_w == 2498.0

    def test_from_state_thermal_pause_active(self) -> None:
        now_ts = time.time()
        future_ts = now_ts + 120.0
        state = make_state(thermal_pause_until_ts=future_ts)
        cfg = make_config()
        ctx = MinerGovernanceContext.from_state(state, now_ts, cfg)

        assert ctx.thermal_pause_active is True

    def test_from_state_thermal_pause_expired(self) -> None:
        now_ts = time.time()
        past_ts = now_ts - 10.0
        state = make_state(thermal_pause_until_ts=past_ts)
        cfg = make_config()
        ctx = MinerGovernanceContext.from_state(state, now_ts, cfg)

        assert ctx.thermal_pause_active is False

    def test_from_state_is_warming_up_within_grace(self) -> None:
        now_ts = time.time()
        state = make_state(last_elapsed=300.0)  # 300s < 900s grace
        cfg = make_config()
        ctx = MinerGovernanceContext.from_state(state, now_ts, cfg)

        assert ctx.is_warming_up is True

    def test_from_state_miner_name_from_display_name(self) -> None:
        now_ts = time.time()
        state = make_state()
        cfg = make_config(name="", display_name="S19JPRO-24")
        ctx = MinerGovernanceContext.from_state(state, now_ts, cfg)

        assert ctx.miner_name == "S19JPRO-24"

    def test_built_at_ts_monotonic(self) -> None:
        now_ts = time.time()
        t_before = time.monotonic()
        state = make_state()
        cfg = make_config()
        ctx = MinerGovernanceContext.from_state(state, now_ts, cfg)
        t_after = time.monotonic()

        assert t_before <= ctx.built_at_ts <= t_after


class TestT003_FromStateNoneFields:
    """T003: Manejo defensivo cuando campos son None o no existen."""

    def test_all_none_state(self) -> None:
        """from_state() con estado completamente vacío no lanza excepción."""
        now_ts = time.time()
        state = make_state()  # todos los campos son None/False
        cfg = make_config()
        ctx = MinerGovernanceContext.from_state(state, now_ts, cfg)

        assert ctx.current_power_w is None
        assert ctx.chip_temp_c is None
        assert ctx.inlet_temp_c is None
        assert ctx.fga_thermal_resistance is None
        assert ctx.fga_cohort is None
        assert ctx.restart_required is False
        assert ctx.restart_detected_ts is None
        assert ctx.thermal_pause_active is False
        assert ctx.thermal_lockout_active is False
        assert ctx.uptime_seconds is None
        assert ctx.is_warming_up is False

    def test_fga_cohort_none_when_not_set(self) -> None:
        now_ts = time.time()
        state = make_state(fga_cohort=None)
        cfg = make_config()
        ctx = MinerGovernanceContext.from_state(state, now_ts, cfg)

        assert ctx.fga_cohort is None

    def test_fga_cohort_propagated(self) -> None:
        now_ts = time.time()
        state = make_state(fga_cohort="HOT")
        cfg = make_config()
        ctx = MinerGovernanceContext.from_state(state, now_ts, cfg)

        assert ctx.fga_cohort == "HOT"

    def test_electrical_group_from_group_key(self) -> None:
        """Fallback a 'group' cuando 'electrical_group' no existe en config."""
        now_ts = time.time()
        state = make_state()
        cfg = {"name": "M25", "group": "elevator_2"}
        ctx = MinerGovernanceContext.from_state(state, now_ts, cfg)

        assert ctx.electrical_group == "elevator_2"

    def test_electrical_group_none_when_absent(self) -> None:
        now_ts = time.time()
        state = make_state()
        cfg = {"name": "M25"}
        ctx = MinerGovernanceContext.from_state(state, now_ts, cfg)

        assert ctx.electrical_group is None


# ─────────────────────────────────────────────────────────────────────────────
# Fase 3 — Integración Fan Governor (T004–T011)
# ─────────────────────────────────────────────────────────────────────────────


def _base_cfg() -> GovernorConfig:
    return GovernorConfig(
        enabled=True,
        dry_run=True,
        target_temp_c=82.0,
        deadband_low_c=81.0,
        deadband_high_c=82.5,
        emergency_spike_temp_c=83.0,
        min_fan_duty_percent=30,
        max_fan_duty_percent=100,
        power_margin_w=120.0,
    )


class TestT004_NoRecoveryWhenRestartRequired:
    """T004: restart_required=True + current < target → NO RECOVERY_MAX_COOLING."""

    def test_governor_no_recovery_when_restart_required(self) -> None:
        """
        S19JPRO-24: corría a 2498W con target 2700W y restart_required=True.
        Sin ctx: hubiera entrado en RECOVERY_MAX_COOLING (bug F-01).
        Con ctx.restart_required=True: el effective_target_w se ajusta a current_power_w,
        eliminando la brecha de 202W que disparaba el recovery loop.
        """
        cfg = _base_cfg()
        ctx = MinerGovernanceContext(
            current_power_w=2498.0,
            target_power_w=2700.0,
            restart_required=True,
        )
        decision = compute_governor_step(
            max_temp_c=78.0,
            current_duty=85,
            seconds_since_last_change=200.0,
            config=cfg,
            current_power_w=ctx.current_power_w,
            target_power_w=ctx.effective_target_power_w,
            ctx=ctx,
        )
        assert decision.action != ACTION_RECOVERY_MAX_COOLING, (
            f"Con restart_required=True no debe entrar en RECOVERY_MAX_COOLING "
            f"(acción real: {decision.action})"
        )


class TestT005_RecoveryWithoutCtx:
    """T005: sin ctx, comportamiento idéntico al baseline pre-Spec082."""

    def test_governor_recovery_without_ctx(self) -> None:
        """Sin ctx, current=2498W < target-120=2580W → RECOVERY_MAX_COOLING."""
        cfg = _base_cfg()
        decision = compute_governor_step(
            max_temp_c=78.0,
            current_duty=85,
            seconds_since_last_change=200.0,
            config=cfg,
            current_power_w=2498.0,
            target_power_w=2700.0,
            ctx=None,
        )
        assert decision.action == ACTION_RECOVERY_MAX_COOLING


class TestT006_RecoveryWithCtxFalse:
    """T006: ctx.restart_required=False + current < target → SÍ RECOVERY_MAX_COOLING."""

    def test_governor_recovery_with_ctx_false(self) -> None:
        cfg = _base_cfg()
        ctx = MinerGovernanceContext(
            current_power_w=2498.0,
            target_power_w=2700.0,
            restart_required=False,
        )
        decision = compute_governor_step(
            max_temp_c=78.0,
            current_duty=85,
            seconds_since_last_change=200.0,
            config=cfg,
            current_power_w=ctx.current_power_w,
            target_power_w=ctx.effective_target_power_w,
            ctx=ctx,
        )
        assert decision.action == ACTION_RECOVERY_MAX_COOLING


class TestT007_ThermalPauseActive:
    """T007: ctx.thermal_pause_active no rompe la firma de compute_governor_step."""

    def test_ctx_thermal_pause_active(self) -> None:
        cfg = _base_cfg()
        ctx = MinerGovernanceContext(
            current_power_w=2700.0,
            target_power_w=2700.0,
            thermal_pause_active=True,
            restart_required=False,
        )
        # Con thermal_pause no hay recovery (current == target), debe tomar decisión normal
        decision = compute_governor_step(
            max_temp_c=78.0,
            current_duty=85,
            seconds_since_last_change=200.0,
            config=cfg,
            current_power_w=ctx.current_power_w,
            target_power_w=ctx.effective_target_power_w,
            ctx=ctx,
        )
        # No debe fallar y debe devolver una decisión válida
        assert isinstance(decision, GovernorDecision)
        assert decision.action in {
            ACTION_HOLD_DWELL, ACTION_HOLD_TARGET, ACTION_STEP_DOWN, ACTION_STEP_UP,
            ACTION_RECOVERY_MAX_COOLING, ACTION_UNKNOWN,
        }


class TestT008_FgaCohortPropagation:
    """T008: fga_cohort se propaga correctamente desde state a ctx."""

    def test_ctx_fga_cohort_propagation(self) -> None:
        now_ts = time.time()
        for cohort in ("COOL", "STANDARD", "HOT", None):
            state = make_state(fga_cohort=cohort)
            cfg = make_config()
            ctx = MinerGovernanceContext.from_state(state, now_ts, cfg)
            assert ctx.fga_cohort == cohort


class TestT009_EffectiveTargetOverride:
    """T009: ctx.effective_target_power_w colapsa target cuando restart_required."""

    def test_governor_ctx_overrides_effective_target(self) -> None:
        """
        Cuando restart_required=True, effective_target_power_w == current_power_w,
        eliminando la brecha que causa el recovery loop.
        """
        ctx_restart = MinerGovernanceContext(
            current_power_w=2498.0,
            target_power_w=2700.0,
            restart_required=True,
        )
        assert ctx_restart.effective_target_power_w == 2498.0

    def test_effective_target_unchanged_when_no_restart(self) -> None:
        ctx_no_restart = MinerGovernanceContext(
            current_power_w=2498.0,
            target_power_w=2700.0,
            restart_required=False,
        )
        assert ctx_no_restart.effective_target_power_w == 2700.0

    def test_effective_target_when_restart_and_no_configured_target(self) -> None:
        """
        Cuando restart_required=True y target_power_w=None (no configurado),
        effective_target_power_w devuelve current_power_w como ancla segura.
        Esto evita que un target None cause brecha ficticia o división por cero.
        """
        ctx = MinerGovernanceContext(
            current_power_w=2498.0,
            target_power_w=None,
            restart_required=True,
        )
        # Con restart=True, el ancla es current_power_w (comportamiento seguro)
        assert ctx.effective_target_power_w == 2498.0


class TestT010_BackwardsCompatNoCtx:
    """T010: compute_governor_step() sin ctx produce resultados idénticos al baseline."""

    def test_governor_backwards_compat_no_ctx(self) -> None:
        cfg = _base_cfg()
        kwargs = dict(
            max_temp_c=75.0,
            current_duty=80,
            seconds_since_last_change=200.0,
            config=cfg,
            current_power_w=2700.0,
            target_power_w=2700.0,
        )
        decision_no_ctx = compute_governor_step(**kwargs)
        decision_ctx_none = compute_governor_step(**kwargs, ctx=None)

        assert decision_no_ctx.action == decision_ctx_none.action
        assert decision_no_ctx.target_duty == decision_ctx_none.target_duty
        assert decision_no_ctx.requires_write == decision_ctx_none.requires_write

    def test_governor_backwards_compat_step_up(self) -> None:
        """Con T > deadband_high sin ctx → STEP_UP igual que antes."""
        cfg = _base_cfg()
        decision = compute_governor_step(
            max_temp_c=83.5,
            current_duty=90,
            seconds_since_last_change=200.0,
            config=cfg,
        )
        # 83.5 >= 83.0 (emergency_spike) → EMERGENCY_SPIKE
        from app.governance.fan_governor import ACTION_EMERGENCY_SPIKE
        assert decision.action == ACTION_EMERGENCY_SPIKE


class TestT011_CtxConstructionPerformance:
    """T011: from_state() < 1ms (sin I/O, puro cálculo en memoria)."""

    def test_ctx_construction_performance(self) -> None:
        now_ts = time.time()
        state = make_state(
            last_power_w=2700.0,
            last_max_chip_temp=78.5,
            inlet_temp_c=30.0,
            fga_cohort="HOT",
            vnish_restart_required=False,
            last_elapsed=3600.0,
        )
        cfg = make_config()

        ITERATIONS = 1000
        t_start = time.perf_counter()
        for _ in range(ITERATIONS):
            MinerGovernanceContext.from_state(state, now_ts, cfg)
        t_end = time.perf_counter()

        avg_ms = ((t_end - t_start) / ITERATIONS) * 1000
        assert avg_ms < 1.0, (
            f"from_state() tardó {avg_ms:.3f}ms en promedio (máximo: 1ms)"
        )
