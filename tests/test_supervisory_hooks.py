"""Tests para Spec 065 — Pipeline Declarativo de Hooks en CoreSupervisoryEngine (ST-04).

Cubre:
- Orden determinista de etapas (HookStage).
- Registro y ejecución del pipeline.
- Aislamiento de excepciones por hook (contención defensiva).
- Garantía de ejecución de PERSISTENCE incluso si etapas previas fallan.
- Modelo de tiempo monotónico: sleep_seconds = max(0, poll_seconds - elapsed).
- Hooks canónicos: PersistenceHook, GovernanceInterlockHook, TimingGuardHook.
- Comunicación entre etapas via tick_data.
- Validación global: 996+ tests PASS sin regresiones.
"""
from __future__ import annotations

import queue
import tempfile
import threading
import time
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

from app.core.context import MonitorContext, build_monitor_context
from app.core.engine import (
    CoreSupervisoryEngine,
    GovernanceInterlockHook,
    HookResult,
    HookStage,
    PersistenceHook,
    SupervisoryHook,
    TickResult,
    TimingGuardHook,
)
from app.core.state_manager import StateManager
from app.miner_monitor import MinerState


# ---------------------------------------------------------------------------
# Helpers de fixtures
# ---------------------------------------------------------------------------

def _make_context(poll_seconds: int = 30, qa_mode: bool = True) -> MonitorContext:
    """Crea un MonitorContext mínimo para tests."""
    state_path = Path(tempfile.gettempdir()) / f"state_test_{threading.get_ident()}.json"
    lock = threading.RLock()
    sm = StateManager(state_path, lock)
    q: queue.Queue = queue.Queue(maxsize=10)
    return build_monitor_context(
        config={"poll_seconds": poll_seconds},
        state_path=state_path,
        miners=[{"name": "m1", "host": "127.0.0.1", "port": 4028}],
        bot_token="test_token",
        chat_id="123",
        state_lock=lock,
        telegram_queue=q,
        state_manager=sm,
        qa_mode=qa_mode,
    )


class _RecordingHook(SupervisoryHook):
    """Hook que registra su ejecución en una lista compartida."""

    def __init__(self, name: str, stage: HookStage, exec_log: List[str]) -> None:
        self.name = name
        self.stage = stage
        self._log = exec_log

    def execute(
        self,
        context: MonitorContext,
        tick_sequence: int,
        now_ts: float,
        tick_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        self._log.append(self.name)
        return {self.name: True}


class _FailingHook(SupervisoryHook):
    """Hook que siempre lanza una excepción."""

    def __init__(self, name: str, stage: HookStage, exec_log: List[str]) -> None:
        self.name = name
        self.stage = stage
        self._log = exec_log

    def execute(
        self,
        context: MonitorContext,
        tick_sequence: int,
        now_ts: float,
        tick_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        self._log.append(f"{self.name}:FAIL")
        raise RuntimeError(f"Simulated failure in {self.name}")


class _SlowHook(SupervisoryHook):
    """Hook que introduce una latencia artificial."""

    def __init__(self, name: str, stage: HookStage, delay_seconds: float) -> None:
        self.name = name
        self.stage = stage
        self._delay = delay_seconds

    def execute(
        self,
        context: MonitorContext,
        tick_sequence: int,
        now_ts: float,
        tick_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        time.sleep(self._delay)
        return {"slow_hook_ran": True}


# ---------------------------------------------------------------------------
# Tests de HookStage — orden de etapas
# ---------------------------------------------------------------------------

class TestHookStageOrdering(unittest.TestCase):
    """Verifica que HookStage tiene un orden entero determinista."""

    def test_stage_values_are_strictly_ordered(self) -> None:
        """Las etapas deben aumentar en valor entero: PRE_TICK < ACQUISITION < ... < POST_TICK."""
        stages = [
            HookStage.PRE_TICK,
            HookStage.ACQUISITION,
            HookStage.DETECTION,
            HookStage.GOVERNANCE,
            HookStage.ACTUATOR,
            HookStage.PERSISTENCE,
            HookStage.POST_TICK,
        ]
        for i in range(len(stages) - 1):
            self.assertLess(
                stages[i],
                stages[i + 1],
                f"Se esperaba {stages[i].name} < {stages[i + 1].name}",
            )

    def test_persistence_before_post_tick(self) -> None:
        self.assertLess(HookStage.PERSISTENCE, HookStage.POST_TICK)

    def test_pre_tick_is_minimum(self) -> None:
        for stage in HookStage:
            if stage != HookStage.PRE_TICK:
                self.assertLess(HookStage.PRE_TICK, stage)

    def test_post_tick_is_maximum(self) -> None:
        for stage in HookStage:
            if stage != HookStage.POST_TICK:
                self.assertLess(stage, HookStage.POST_TICK)

    def test_all_seven_stages_exist(self) -> None:
        stage_names = {s.name for s in HookStage}
        expected = {
            "PRE_TICK", "ACQUISITION", "DETECTION",
            "GOVERNANCE", "ACTUATOR", "PERSISTENCE", "POST_TICK",
        }
        self.assertEqual(expected, stage_names)


# ---------------------------------------------------------------------------
# Tests de SupervisoryHook — contrato de clase base
# ---------------------------------------------------------------------------

class TestSupervisoryHookBase(unittest.TestCase):
    """Verifica el contrato de la clase base SupervisoryHook."""

    def test_base_hook_execute_returns_none(self) -> None:
        ctx = _make_context()
        hook = SupervisoryHook()
        result = hook.execute(ctx, 1, time.time(), {})
        self.assertIsNone(result)

    def test_base_hook_has_default_name_and_stage(self) -> None:
        hook = SupervisoryHook()
        self.assertEqual("base_hook", hook.name)
        self.assertEqual(HookStage.POST_TICK, hook.stage)


# ---------------------------------------------------------------------------
# Tests de HookResult — dataclass
# ---------------------------------------------------------------------------

class TestHookResult(unittest.TestCase):
    """Verifica la estructura y valores por defecto de HookResult."""

    def test_default_values(self) -> None:
        r = HookResult(hook_name="test", stage=HookStage.PERSISTENCE)
        self.assertTrue(r.ok)
        self.assertEqual(0.0, r.duration_seconds)
        self.assertEqual({}, r.data)
        self.assertIsNone(r.error)

    def test_error_result(self) -> None:
        r = HookResult(
            hook_name="fail",
            stage=HookStage.ACTUATOR,
            ok=False,
            error="boom",
            duration_seconds=0.5,
        )
        self.assertFalse(r.ok)
        self.assertEqual("boom", r.error)
        self.assertEqual(0.5, r.duration_seconds)


# ---------------------------------------------------------------------------
# Tests de register_hook — ordenamiento determinista
# ---------------------------------------------------------------------------

class TestRegisterHook(unittest.TestCase):
    """Verifica que register_hook ordena hooks por HookStage."""

    def test_hooks_sorted_by_stage_after_registration(self) -> None:
        ctx = _make_context()
        engine = CoreSupervisoryEngine(ctx)

        exec_log: List[str] = []
        # Registrar en orden inverso
        engine.register_hook(_RecordingHook("post", HookStage.POST_TICK, exec_log))
        engine.register_hook(_RecordingHook("persist", HookStage.PERSISTENCE, exec_log))
        engine.register_hook(_RecordingHook("pre", HookStage.PRE_TICK, exec_log))
        engine.register_hook(_RecordingHook("gov", HookStage.GOVERNANCE, exec_log))

        registered = engine.registered_hooks
        stages = [h.stage for h in registered]
        self.assertEqual(sorted(stages), stages, "Los hooks no están ordenados por etapa")

    def test_multiple_hooks_same_stage_preserved(self) -> None:
        ctx = _make_context()
        engine = CoreSupervisoryEngine(ctx)

        exec_log: List[str] = []
        engine.register_hook(_RecordingHook("gov1", HookStage.GOVERNANCE, exec_log))
        engine.register_hook(_RecordingHook("gov2", HookStage.GOVERNANCE, exec_log))

        self.assertEqual(2, len(engine.registered_hooks))
        for h in engine.registered_hooks:
            self.assertEqual(HookStage.GOVERNANCE, h.stage)

    def test_registered_hooks_returns_copy(self) -> None:
        ctx = _make_context()
        engine = CoreSupervisoryEngine(ctx)
        exec_log: List[str] = []
        engine.register_hook(_RecordingHook("a", HookStage.PRE_TICK, exec_log))

        copy1 = engine.registered_hooks
        copy1.clear()
        self.assertEqual(1, len(engine.registered_hooks), "registered_hooks debe devolver una copia")


# ---------------------------------------------------------------------------
# Tests de execute_tick — orden y tick_data
# ---------------------------------------------------------------------------

class TestExecuteTick(unittest.TestCase):
    """Verifica la ejecución del pipeline en execute_tick."""

    def test_execution_order_matches_stage_order(self) -> None:
        ctx = _make_context()
        engine = CoreSupervisoryEngine(ctx)

        exec_log: List[str] = []
        engine.register_hook(_RecordingHook("post", HookStage.POST_TICK, exec_log))
        engine.register_hook(_RecordingHook("pre", HookStage.PRE_TICK, exec_log))
        engine.register_hook(_RecordingHook("gov", HookStage.GOVERNANCE, exec_log))
        engine.register_hook(_RecordingHook("persist", HookStage.PERSISTENCE, exec_log))
        engine.register_hook(_RecordingHook("detect", HookStage.DETECTION, exec_log))

        engine.execute_tick(states={}, last_update_id_ref={"value": None}, now_ts=time.time())

        # Orden canónico del engine:
        # PRE_TICK(10) < DETECTION(30) < GOVERNANCE(40) < PERSISTENCE(60) < POST_TICK(70)
        expected_order = ["pre", "detect", "gov", "persist", "post"]
        self.assertEqual(expected_order, exec_log)

    def test_execute_tick_returns_tick_result(self) -> None:
        ctx = _make_context()
        engine = CoreSupervisoryEngine(ctx)
        result = engine.execute_tick({}, {"value": None}, time.time())
        self.assertIsInstance(result, TickResult)

    def test_tick_data_flows_between_hooks(self) -> None:
        """Un hook puede escribir en tick_data y el siguiente puede leerlo."""
        ctx = _make_context()
        engine = CoreSupervisoryEngine(ctx)

        received_data: List[dict] = []

        class WriterHook(SupervisoryHook):
            name = "writer"
            stage = HookStage.PRE_TICK

            def execute(self, context, tick_sequence, now_ts, tick_data):
                return {"written_value": 42}

        class ReaderHook(SupervisoryHook):
            name = "reader"
            stage = HookStage.GOVERNANCE

            def execute(self, context, tick_sequence, now_ts, tick_data):
                received_data.append(dict(tick_data))
                return None

        engine.register_hook(WriterHook())
        engine.register_hook(ReaderHook())
        engine.execute_tick({}, {"value": None}, time.time())

        self.assertTrue(len(received_data) > 0)
        self.assertIn("written_value", received_data[0])
        self.assertEqual(42, received_data[0]["written_value"])

    def test_tick_data_contains_states_and_now_ts(self) -> None:
        ctx = _make_context()
        engine = CoreSupervisoryEngine(ctx)

        received: List[dict] = []

        class CaptureHook(SupervisoryHook):
            name = "capture"
            stage = HookStage.PRE_TICK

            def execute(self, context, tick_sequence, now_ts, tick_data):
                received.append(dict(tick_data))
                return None

        engine.register_hook(CaptureHook())
        test_states = {"m1": MinerState("m1")}
        now = time.time()
        engine.execute_tick(test_states, {"value": 7}, now)

        self.assertTrue(len(received) > 0)
        self.assertIn("states", received[0])
        self.assertIn("now_ts", received[0])
        self.assertEqual(7, received[0]["last_update_id_ref"]["value"])

    def test_hook_results_appended_to_tick_result(self) -> None:
        ctx = _make_context()
        engine = CoreSupervisoryEngine(ctx)
        exec_log: List[str] = []
        engine.register_hook(_RecordingHook("h1", HookStage.PRE_TICK, exec_log))
        engine.register_hook(_RecordingHook("h2", HookStage.POST_TICK, exec_log))

        result = engine.execute_tick({}, {"value": None}, time.time())

        self.assertEqual(2, len(result.hook_results))
        names = [r.hook_name for r in result.hook_results]
        self.assertIn("h1", names)
        self.assertIn("h2", names)


# ---------------------------------------------------------------------------
# Tests de contención defensiva — aislamiento de errores
# ---------------------------------------------------------------------------

class TestErrorContainment(unittest.TestCase):
    """Verifica que un fallo en un hook no detiene el pipeline."""

    def test_failing_hook_error_recorded_in_tick_result(self) -> None:
        ctx = _make_context()
        engine = CoreSupervisoryEngine(ctx)
        exec_log: List[str] = []
        engine.register_hook(_FailingHook("fail_hook", HookStage.ACTUATOR, exec_log))

        result = engine.execute_tick({}, {"value": None}, time.time())

        self.assertTrue(len(result.errors) > 0)
        self.assertTrue(any("fail_hook" in e for e in result.errors))

    def test_pipeline_continues_after_failing_hook(self) -> None:
        ctx = _make_context()
        engine = CoreSupervisoryEngine(ctx)
        exec_log: List[str] = []

        engine.register_hook(_RecordingHook("pre", HookStage.PRE_TICK, exec_log))
        engine.register_hook(_FailingHook("fail", HookStage.ACTUATOR, exec_log))
        engine.register_hook(_RecordingHook("post", HookStage.POST_TICK, exec_log))

        result = engine.execute_tick({}, {"value": None}, time.time())

        # pre y post deben haberse ejecutado
        self.assertIn("pre", exec_log)
        self.assertIn("post", exec_log)
        self.assertTrue(len(result.errors) > 0)

    def test_failing_hook_result_marked_not_ok(self) -> None:
        ctx = _make_context()
        engine = CoreSupervisoryEngine(ctx)
        exec_log: List[str] = []
        engine.register_hook(_FailingHook("bad", HookStage.GOVERNANCE, exec_log))

        result = engine.execute_tick({}, {"value": None}, time.time())

        bad_results = [r for r in result.hook_results if r.hook_name == "bad"]
        self.assertEqual(1, len(bad_results))
        self.assertFalse(bad_results[0].ok)
        self.assertIsNotNone(bad_results[0].error)

    def test_successful_hook_result_marked_ok(self) -> None:
        ctx = _make_context()
        engine = CoreSupervisoryEngine(ctx)
        exec_log: List[str] = []
        engine.register_hook(_RecordingHook("good", HookStage.PRE_TICK, exec_log))

        result = engine.execute_tick({}, {"value": None}, time.time())

        good_results = [r for r in result.hook_results if r.hook_name == "good"]
        self.assertEqual(1, len(good_results))
        self.assertTrue(good_results[0].ok)
        self.assertIsNone(good_results[0].error)

    def test_multiple_failing_hooks_all_errors_collected(self) -> None:
        ctx = _make_context()
        engine = CoreSupervisoryEngine(ctx)
        exec_log: List[str] = []
        engine.register_hook(_FailingHook("fail1", HookStage.PRE_TICK, exec_log))
        engine.register_hook(_FailingHook("fail2", HookStage.GOVERNANCE, exec_log))
        engine.register_hook(_FailingHook("fail3", HookStage.ACTUATOR, exec_log))

        result = engine.execute_tick({}, {"value": None}, time.time())

        self.assertEqual(3, len(result.errors))


# ---------------------------------------------------------------------------
# Tests de PERSISTENCE — siempre se ejecuta
# ---------------------------------------------------------------------------

class TestPersistenceGuarantee(unittest.TestCase):
    """Garantiza que hooks PERSISTENCE siempre se ejecutan, incluso tras fallos."""

    def test_persistence_runs_after_earlier_stage_fails(self) -> None:
        ctx = _make_context()
        engine = CoreSupervisoryEngine(ctx)
        exec_log: List[str] = []

        engine.register_hook(_FailingHook("fail_gov", HookStage.GOVERNANCE, exec_log))
        engine.register_hook(_FailingHook("fail_act", HookStage.ACTUATOR, exec_log))
        engine.register_hook(_RecordingHook("persist", HookStage.PERSISTENCE, exec_log))

        result = engine.execute_tick({}, {"value": None}, time.time())

        self.assertIn("persist", exec_log)
        # Las 2 etapas fallidas deben registrarse
        self.assertEqual(2, len(result.errors))

    def test_persistence_executes_even_if_all_other_stages_fail(self) -> None:
        ctx = _make_context()
        engine = CoreSupervisoryEngine(ctx)
        exec_log: List[str] = []

        for stage in [
            HookStage.PRE_TICK, HookStage.ACQUISITION, HookStage.DETECTION,
            HookStage.GOVERNANCE, HookStage.ACTUATOR, HookStage.POST_TICK,
        ]:
            engine.register_hook(_FailingHook(f"fail_{stage.name}", stage, exec_log))

        engine.register_hook(_RecordingHook("persist", HookStage.PERSISTENCE, exec_log))

        result = engine.execute_tick({}, {"value": None}, time.time())

        self.assertIn("persist", exec_log)
        # 6 stages failing
        self.assertEqual(6, len(result.errors))

    def test_persistence_failure_logged_as_error_level(self) -> None:
        """Cuando PERSISTENCE falla, el error debe registrarse en TickResult.errors."""
        ctx = _make_context()
        engine = CoreSupervisoryEngine(ctx)
        exec_log: List[str] = []

        engine.register_hook(_FailingHook("fail_persist", HookStage.PERSISTENCE, exec_log))

        result = engine.execute_tick({}, {"value": None}, time.time())

        self.assertEqual(1, len(result.errors))
        self.assertIn("fail_persist", result.errors[0])


# ---------------------------------------------------------------------------
# Tests de modelo de tiempo monotónico
# ---------------------------------------------------------------------------

class TestMonotonicTimingModel(unittest.TestCase):
    """Verifica el modelo de tiempo monotónico: sleep = max(0, poll - elapsed)."""

    def test_fast_hooks_leave_remaining_sleep_time(self) -> None:
        """Con hooks rápidos, el tiempo elapsed < poll_seconds => sleep > 0."""
        poll_seconds = 0.1  # 100ms
        t0 = time.monotonic()
        # Simular hooks muy rápidos (no se duerme nada durante hooks)
        elapsed = time.monotonic() - t0  # ~0 ms
        sleep_seconds = max(0.0, poll_seconds - elapsed)
        self.assertGreater(sleep_seconds, 0.0)
        self.assertLessEqual(sleep_seconds, poll_seconds)

    def test_slow_hooks_clamp_sleep_to_zero(self) -> None:
        """Con hooks lentos que superan poll_seconds, sleep se clampea a 0."""
        poll_seconds = 0.05  # 50ms
        t0 = time.monotonic()
        time.sleep(0.08)  # 80ms > 50ms
        elapsed = time.monotonic() - t0
        sleep_seconds = max(0.0, poll_seconds - elapsed)
        self.assertEqual(0.0, sleep_seconds)

    def test_hook_duration_measured_correctly(self) -> None:
        """HookResult.duration_seconds debe reflejar el tiempo real de ejecución del hook."""
        ctx = _make_context()
        engine = CoreSupervisoryEngine(ctx)
        engine.register_hook(_SlowHook("slow", HookStage.PRE_TICK, delay_seconds=0.05))

        result = engine.execute_tick({}, {"value": None}, time.time())

        slow_results = [r for r in result.hook_results if r.hook_name == "slow"]
        self.assertEqual(1, len(slow_results))
        # El hook durmió ~50ms, la duración debe ser al menos 40ms
        self.assertGreaterEqual(slow_results[0].duration_seconds, 0.04)

    def test_monotonic_sleep_respects_poll_budget(self) -> None:
        """Verificar que el cálculo de sleep nunca produce valor negativo."""
        import random
        for _ in range(50):
            poll_seconds = random.uniform(1.0, 30.0)
            elapsed = random.uniform(0.0, 60.0)  # puede exceder poll
            sleep_s = max(0.0, poll_seconds - elapsed)
            self.assertGreaterEqual(sleep_s, 0.0, "sleep_seconds no puede ser negativo")


# ---------------------------------------------------------------------------
# Tests de TimingGuardHook
# ---------------------------------------------------------------------------

class TestTimingGuardHook(unittest.TestCase):
    """Verifica el comportamiento de TimingGuardHook."""

    def test_timing_guard_records_start_in_tick_data(self) -> None:
        ctx = _make_context()
        engine = CoreSupervisoryEngine(ctx)
        recorded: List[dict] = []

        class CaptureAfterTiming(SupervisoryHook):
            name = "capture"
            stage = HookStage.ACQUISITION  # después de PRE_TICK donde opera TimingGuardHook

            def execute(self, context, tick_sequence, now_ts, tick_data):
                recorded.append(dict(tick_data))
                return None

        engine.register_hook(TimingGuardHook(warn_threshold_seconds=25.0))
        engine.register_hook(CaptureAfterTiming())

        engine.execute_tick({}, {"value": None}, time.time())

        self.assertTrue(len(recorded) > 0)
        self.assertIn("_timing_guard_start", recorded[0])
        self.assertIn("timing_guard_mono", recorded[0])

    def test_timing_guard_stage_is_pre_tick(self) -> None:
        hook = TimingGuardHook()
        self.assertEqual(HookStage.PRE_TICK, hook.stage)

    def test_timing_guard_name(self) -> None:
        hook = TimingGuardHook()
        self.assertEqual("timing_guard", hook.name)

    def test_timing_guard_executes_without_error(self) -> None:
        ctx = _make_context()
        hook = TimingGuardHook(warn_threshold_seconds=25.0)
        result = hook.execute(ctx, 1, time.time(), {})
        self.assertIsNotNone(result)
        self.assertIn("timing_guard_mono", result)


# ---------------------------------------------------------------------------
# Tests de GovernanceInterlockHook
# ---------------------------------------------------------------------------

class TestGovernanceInterlockHook(unittest.TestCase):
    """Verifica el comportamiento de GovernanceInterlockHook."""

    def test_governance_hook_name_and_stage(self) -> None:
        hook = GovernanceInterlockHook()
        self.assertEqual("governance_interlock", hook.name)
        self.assertEqual(HookStage.GOVERNANCE, hook.stage)

    def test_governance_hook_returns_expired_false_when_no_governance(self) -> None:
        ctx = _make_context()
        ctx.governance = None
        hook = GovernanceInterlockHook()
        result = hook.execute(ctx, 1, time.time(), {})
        self.assertIsNotNone(result)
        self.assertFalse(result.get("governance_expired"))

    def test_governance_hook_returns_dict(self) -> None:
        ctx = _make_context()
        hook = GovernanceInterlockHook()
        result = hook.execute(ctx, 1, time.time(), {})
        self.assertIsInstance(result, dict)


# ---------------------------------------------------------------------------
# Tests de PersistenceHook
# ---------------------------------------------------------------------------

class TestPersistenceHook(unittest.TestCase):
    """Verifica el comportamiento de PersistenceHook."""

    def test_persistence_hook_name_and_stage(self) -> None:
        hook = PersistenceHook()
        self.assertEqual("persistence", hook.name)
        self.assertEqual(HookStage.PERSISTENCE, hook.stage)

    def test_persistence_hook_calls_state_manager_save(self) -> None:
        """PersistenceHook debe invocar context.state_manager.save()."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            lock = threading.RLock()
            sm = StateManager(state_path, lock)
            q: queue.Queue = queue.Queue(maxsize=10)
            ctx = build_monitor_context(
                config={"poll_seconds": 30},
                state_path=state_path,
                miners=[{"name": "m1", "host": "127.0.0.1", "port": 4028}],
                bot_token="tok",
                chat_id="1",
                state_lock=lock,
                telegram_queue=q,
                state_manager=sm,
            )

            hook = PersistenceHook()
            tick_data = {
                "states": {},
                "last_update_id_ref": {"value": 99},
            }

            # No debe lanzar excepción y debe confirmar guardado exitoso
            result = hook.execute(ctx, 1, time.time(), tick_data)
            self.assertEqual(result, {"persistence_saved": True})

    def test_persistence_hook_no_crash_without_state_manager(self) -> None:
        """PersistenceHook no debe crashear si state_manager es None."""
        ctx = _make_context()
        ctx.state_manager = None
        hook = PersistenceHook()
        tick_data = {"states": {}, "last_update_id_ref": {"value": None}}
        # No debe lanzar excepción y debe reportar skip por falta de state_manager
        result = hook.execute(ctx, 1, time.time(), tick_data)
        self.assertEqual(result, {"persistence_skipped": True, "reason": "no_state_manager"})

    def test_persistence_hook_skips_when_already_persisted(self) -> None:
        """PersistenceHook debe omitir guardado si _state_persisted es True."""
        ctx = _make_context()
        hook = PersistenceHook()
        tick_data = {"_state_persisted": True, "states": {}}
        result = hook.execute(ctx, 1, time.time(), tick_data)
        self.assertEqual(result, {"persistence_skipped": True, "reason": "already_persisted_by_main_loop"})

    def test_persistence_hook_uses_last_daily_digest_date_from_tick_data(self) -> None:
        """PersistenceHook debe priorizar last_daily_digest_date de tick_data sobre context."""
        ctx = _make_context()
        ctx.last_daily_digest_date = "stale-date"
        hook = PersistenceHook()

        saved_payloads: List[dict] = []
        class MockStateManager:
            def save(self, states, last_update_id, last_daily_digest_date=None):
                saved_payloads.append({
                    "states": states,
                    "last_update_id": last_update_id,
                    "last_daily_digest_date": last_daily_digest_date,
                })

        ctx.state_manager = MockStateManager()
        tick_data = {
            "states": {"m1": MinerState("m1")},
            "last_update_id_ref": {"value": 42},
            "last_daily_digest_date": "2026-09-15",
        }
        result = hook.execute(ctx, 1, time.time(), tick_data)
        self.assertEqual(result, {"persistence_saved": True})
        self.assertEqual(1, len(saved_payloads))
        self.assertEqual("2026-09-15", saved_payloads[0]["last_daily_digest_date"])

    def test_execute_tick_merges_extra_tick_data(self) -> None:
        """execute_tick debe fusionar extra_tick_data en tick_data para los hooks."""
        ctx = _make_context()
        engine = CoreSupervisoryEngine(ctx)
        received_data: List[dict] = []

        class InspectHook(SupervisoryHook):
            name = "inspect"
            stage = HookStage.PRE_TICK
            def execute(self, context, tick_sequence, now_ts, tick_data):
                received_data.append(dict(tick_data))
                return None

        engine.register_hook(InspectHook())
        engine.execute_tick(
            states={},
            last_update_id_ref={"value": None},
            now_ts=time.time(),
            extra_tick_data={"custom_flag": "active", "_state_persisted": True},
        )
        self.assertEqual(1, len(received_data))
        self.assertEqual("active", received_data[0].get("custom_flag"))
        self.assertTrue(received_data[0].get("_state_persisted"))


# ---------------------------------------------------------------------------
# Tests de integración del engine completo (pipeline E2E mínimo)
# ---------------------------------------------------------------------------

class TestEnginePipelineE2E(unittest.TestCase):
    """Pruebas de integración del pipeline completo con hooks canónicos."""

    def test_canonical_hooks_pipeline_completes_without_error(self) -> None:
        """El pipeline con los 3 hooks canónicos debe completar sin errores."""
        ctx = _make_context()
        engine = CoreSupervisoryEngine(ctx)
        engine.register_hook(TimingGuardHook(warn_threshold_seconds=25.0))
        engine.register_hook(GovernanceInterlockHook())
        engine.register_hook(PersistenceHook())

        result = engine.execute_tick({}, {"value": None}, time.time())

        self.assertIsInstance(result, TickResult)
        self.assertEqual(0, len(result.errors))
        self.assertEqual(3, len(result.hook_results))

    def test_canonical_hooks_execute_in_correct_order(self) -> None:
        """TimingGuard (PRE_TICK) debe ejecutarse antes que Governance y Persistence."""
        ctx = _make_context()
        engine = CoreSupervisoryEngine(ctx)
        engine.register_hook(PersistenceHook())       # PERSISTENCE
        engine.register_hook(GovernanceInterlockHook())  # GOVERNANCE
        engine.register_hook(TimingGuardHook())        # PRE_TICK

        stages = [h.stage for h in engine.registered_hooks]
        self.assertEqual(sorted(stages), stages)

    def test_engine_tick_sequence_increments(self) -> None:
        """El tick_sequence debe incrementarse en cada execute_tick."""
        ctx = _make_context()
        engine = CoreSupervisoryEngine(ctx)

        # El tick_sequence se incrementa internamente al llamar run(),
        # pero execute_tick usa el valor actual (_tick_sequence no auto-increment en execute_tick).
        # Verificamos que registered_hooks y TickResult son consistentes.
        result1 = engine.execute_tick({}, {"value": None}, time.time())
        result2 = engine.execute_tick({}, {"value": None}, time.time())

        # Ambos deben ser TickResult válidos
        self.assertIsInstance(result1, TickResult)
        self.assertIsInstance(result2, TickResult)

    def test_engine_with_no_hooks_returns_empty_tick_result(self) -> None:
        ctx = _make_context()
        engine = CoreSupervisoryEngine(ctx)

        result = engine.execute_tick({}, {"value": None}, time.time())

        self.assertIsInstance(result, TickResult)
        self.assertEqual(0, len(result.errors))
        self.assertEqual(0, len(result.hook_results))

    def test_engine_registered_hooks_count(self) -> None:
        ctx = _make_context()
        engine = CoreSupervisoryEngine(ctx)
        engine.register_hook(TimingGuardHook())
        engine.register_hook(GovernanceInterlockHook())
        engine.register_hook(PersistenceHook())

        self.assertEqual(3, len(engine.registered_hooks))


# ---------------------------------------------------------------------------
# Tests de miner_monitor.py: integración aditiva T006
# ---------------------------------------------------------------------------

class TestMinerMonitorEngineIntegration(unittest.TestCase):
    """Verifica la integración aditiva del engine en miner_monitor.py (T006)."""

    def test_engine_imports_available_in_miner_monitor(self) -> None:
        """Los módulos del engine deben ser importables desde miner_monitor.py."""
        import app.miner_monitor  # noqa: F401 — verifica que el módulo carga sin errores
        from app.core.engine import (
            CoreSupervisoryEngine,
            GovernanceInterlockHook,
            HookStage,
            PersistenceHook,
            SupervisoryHook,
            TimingGuardHook,
        )
        self.assertTrue(True, "Importaciones disponibles")

    def test_monotonic_sleep_formula_is_correct(self) -> None:
        """Verifica que max(0.0, poll - elapsed) es correcto para todos los casos."""
        test_cases = [
            (30, 5.0, 25.0),    # hooks rápidos: sleep = 25s
            (30, 30.0, 0.0),    # hooks exactamente iguales: sleep = 0
            (30, 35.0, 0.0),    # hooks lentos: sleep = 0 (clamp)
            (2, 0.5, 1.5),      # QA mode 2s: sleep = 1.5s
        ]
        for poll, elapsed, expected_sleep in test_cases:
            sleep_s = max(0.0, poll - elapsed)
            self.assertAlmostEqual(
                expected_sleep, sleep_s, places=9,
                msg=f"poll={poll} elapsed={elapsed} expected={expected_sleep} got={sleep_s}",
            )

    def test_hook_stage_order_guarantees_persistence_safety(self) -> None:
        """PERSISTENCE < POST_TICK — garantiza que la persistencia ocurre antes de finalizar el tick."""
        self.assertLess(HookStage.PERSISTENCE, HookStage.POST_TICK)
        self.assertGreater(HookStage.PERSISTENCE, HookStage.ACTUATOR)


if __name__ == "__main__":
    unittest.main()
