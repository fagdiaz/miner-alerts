"""Core Supervisory Engine — Spec 065: Pipeline Declarativo de Hooks (ST-04).

Extiende la arquitectura de Spec 060 con:
- HookStage: enum ordenado de etapas del ciclo de supervisión.
- SupervisoryHook: clase base para hooks registrables.
- HookResult: resultado tipado de cada ejecución de hook.
- CoreSupervisoryEngine.register_hook() + execute_tick(): pipeline ordenado
  y con contención defensiva por hook.
- PersistenceHook, GovernanceInterlockHook, TimingGuardHook: hooks canónicos.
- Modelo monotónico de tiempo: poll_seconds = intervalo mínimo entre tick_start,
  no tiempo de sleep puro.

Invariantes de diseño (NO CAMBIAR):
- main() permanece íntegro en miner_monitor.py. Los hooks son ADITIVOS.
- Los 4 tests de inspect.getsource(main) permanecen 100% compatibles.
- La etapa PERSISTENCE siempre se ejecuta aunque fallen etapas anteriores.
"""

from __future__ import annotations

import enum
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from app.core.context import MonitorContext

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# HookStage — orden de etapas del pipeline
# ---------------------------------------------------------------------------

class HookStage(enum.IntEnum):
    """Etapas del pipeline de supervisión, ordenadas por precedencia.

    El valor entero define el orden de ejecución: menor valor = antes.
    No se deben añadir etapas sin actualizar execute_tick() y los tests.
    """
    PRE_TICK = 10
    ACQUISITION = 20
    DETECTION = 30
    GOVERNANCE = 40
    ACTUATOR = 50
    PERSISTENCE = 60    # Siempre se ejecuta, incluso si etapas previas fallan
    POST_TICK = 70


# ---------------------------------------------------------------------------
# HookResult — resultado tipado por ejecución
# ---------------------------------------------------------------------------

@dataclass
class HookResult:
    """Resultado de la ejecución de un SupervisoryHook."""
    hook_name: str
    stage: HookStage
    ok: bool = True
    duration_seconds: float = 0.0
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# SupervisoryHook — clase base
# ---------------------------------------------------------------------------

class SupervisoryHook:
    """Clase base para hooks registrables en CoreSupervisoryEngine.

    Subclases deben implementar execute() y definir name y stage.
    """

    name: str = "base_hook"
    stage: HookStage = HookStage.POST_TICK

    def execute(
        self,
        context: MonitorContext,
        tick_sequence: int,
        now_ts: float,
        tick_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Ejecutar la lógica del hook.

        Args:
            context: Contenedor de dependencias del monitor.
            tick_sequence: Número de tick actual (1-indexed).
            now_ts: Timestamp wall-clock del inicio del tick (time.time()).
            tick_data: Diccionario compartido de datos del tick actual.
                       Los hooks pueden leer y escribir en él para comunicarse
                       entre etapas sin estado global.

        Returns:
            Diccionario de datos adicionales a fusionar en tick_data, o None.
        """
        return None


# ---------------------------------------------------------------------------
# TickResult — resultado agregado del tick
# ---------------------------------------------------------------------------

class TickResult:
    """Resultado agregado de todas las etapas de un tick supervisorio."""

    def __init__(
        self,
        tick_sequence: int,
        tick_duration_seconds: float,
        miners_responded: int,
        miners_failed: int,
        reboots_triggered: List[str],
        governance_blocked: int,
        errors: List[str],
    ) -> None:
        self.tick_sequence = tick_sequence
        self.tick_duration_seconds = tick_duration_seconds
        self.miners_responded = miners_responded
        self.miners_failed = miners_failed
        self.reboots_triggered = reboots_triggered
        self.governance_blocked = governance_blocked
        self.errors = errors
        self.timestamp = time.time()
        self.hook_results: List[HookResult] = []

    def __repr__(self) -> str:
        return (
            f"TickResult(seq={self.tick_sequence} "
            f"responded={self.miners_responded} "
            f"failed={self.miners_failed} "
            f"reboots={self.reboots_triggered} "
            f"duration={self.tick_duration_seconds:.3f}s "
            f"errors={len(self.errors)})"
        )


# ---------------------------------------------------------------------------
# CoreSupervisoryEngine — orquestador con pipeline por etapas
# ---------------------------------------------------------------------------

class CoreSupervisoryEngine:
    """Orchestrator for the authoritative 30-second supervisory cycle.

    Spec 065 extiende Spec 060:
    - register_hook(hook): registra SupervisoryHook ordenados por HookStage.
    - execute_tick(): ejecuta el pipeline con contención defensiva por hook,
      garantizando que PERSISTENCE siempre se ejecuta.
    - register_tick_hook(): compatible con la API anterior (Spec 060).

    Modelo de tiempo monotónico:
        tick_start = time.monotonic()
        ... (ejecución de hooks) ...
        elapsed = time.monotonic() - tick_start
        sleep_seconds = max(0.0, poll_seconds - elapsed)
        shutdown_event.wait(timeout=sleep_seconds)

    Esto garantiza que poll_seconds es el intervalo MÍNIMO entre tick_starts,
    independientemente de la duración de los hooks.
    """

    def __init__(self, context: MonitorContext) -> None:
        self._ctx = context
        # Hooks del sistema de pipeline declarativo (Spec 065)
        self._hooks: List[SupervisoryHook] = []
        # Hooks de la API legada callable (Spec 060, compatible)
        self._tick_hooks: List[Callable[[MonitorContext, int, float], "TickResult"]] = []
        self._running = False
        self._tick_sequence = 0
        self._shutdown_event = threading.Event()

    # ------------------------------------------------------------------
    # Spec 065 API: hooks declarativos
    # ------------------------------------------------------------------

    def register_hook(self, hook: SupervisoryHook) -> None:
        """Registrar un SupervisoryHook en el pipeline.

        Los hooks se ordenan automáticamente por HookStage al registrarse.
        """
        self._hooks.append(hook)
        self._hooks.sort(key=lambda h: h.stage)

    # ------------------------------------------------------------------
    # Spec 060 API legada: callables (compatible, no deprecated)
    # ------------------------------------------------------------------

    def register_tick_hook(
        self,
        hook: Callable[[MonitorContext, int, float], "TickResult"],
    ) -> None:
        """Registrar un callable de tick (API legada Spec 060).

        Signature: hook(context, tick_sequence, now_ts) -> TickResult
        """
        self._tick_hooks.append(hook)

    # ------------------------------------------------------------------
    # execute_tick — pipeline con contención defensiva
    # ------------------------------------------------------------------

    def execute_tick(
        self,
        states: Dict[str, Any],
        last_update_id_ref: Dict[str, Optional[int]],
        now_ts: float,
        tick_sequence: Optional[int] = None,
    ) -> TickResult:
        """Ejecutar un tick completo del pipeline de supervisión.

        Garantías:
        - Los hooks se ejecutan en orden estricto de HookStage
          (PRE_TICK < ACQUISITION < DETECTION < GOVERNANCE < ACTUATOR < PERSISTENCE < POST_TICK).
        - Si un hook falla, el error se registra en TickResult.errors
          y la ejecución continúa con el siguiente hook.
        - Las etapas críticas (PERSISTENCE y POST_TICK) siempre se ejecutan,
          incluso si todas las etapas anteriores fallaron.
        - tick_data es el mecanismo de comunicación entre etapas.
        """
        if tick_sequence is not None:
            self._tick_sequence = tick_sequence

        tick_data: Dict[str, Any] = {
            "states": states,
            "last_update_id_ref": last_update_id_ref,
            "now_ts": now_ts,
            "tick_sequence": self._tick_sequence,
        }
        result = TickResult(
            tick_sequence=self._tick_sequence,
            tick_duration_seconds=0.0,
            miners_responded=0,
            miners_failed=0,
            reboots_triggered=[],
            governance_blocked=0,
            errors=[],
        )

        # Ejecutar hooks en orden estricto de HookStage con contención individual defensiva
        for hook in self._hooks:
            t0 = time.monotonic()
            try:
                extra = hook.execute(self._ctx, self._tick_sequence, now_ts, tick_data)
                if extra:
                    tick_data.update(extra)
                hook_result = HookResult(
                    hook_name=hook.name,
                    stage=hook.stage,
                    ok=True,
                    duration_seconds=time.monotonic() - t0,
                )
            except Exception as exc:
                msg = f"hook={hook.name} stage={hook.stage.name} error={type(exc).__name__}: {exc}"
                if hook.stage == HookStage.PERSISTENCE:
                    logger.error(msg)
                else:
                    logger.warning(msg)
                result.errors.append(msg)
                hook_result = HookResult(
                    hook_name=hook.name,
                    stage=hook.stage,
                    ok=False,
                    duration_seconds=time.monotonic() - t0,
                    error=str(exc),
                )
            result.hook_results.append(hook_result)

        return result

    # ------------------------------------------------------------------
    # run — loop principal con modelo monotónico de tiempo
    # ------------------------------------------------------------------

    def run(
        self,
        states: Dict[str, Any],
        last_update_id_ref: Dict[str, Optional[int]],
        on_tick_complete: Optional[Callable[[TickResult], None]] = None,
    ) -> None:
        """Bloquear y ejecutar el supervisory loop hasta KeyboardInterrupt o shutdown().

        Modelo de tiempo monotónico garantizado:
            sleep_remaining = max(0.0, poll_seconds - elapsed)
        Si el tick tarda más que poll_seconds, el siguiente tick inicia
        inmediatamente (sleep=0), sin deriva acumulativa.
        """
        self._running = True
        poll_seconds = self._ctx.poll_seconds
        logger.info(
            "CoreSupervisoryEngine started: miners=%d poll_seconds=%d qa=%s hooks=%d",
            len(self._ctx.miners),
            poll_seconds,
            self._ctx.qa_mode,
            len(self._hooks),
        )

        try:
            while not self._shutdown_event.is_set():
                tick_start = time.monotonic()
                now_ts = time.time()
                self._tick_sequence += 1

                # Ejecutar pipeline declarativo (Spec 065)
                result = self.execute_tick(states, last_update_id_ref, now_ts)

                # Ejecutar hooks legados callable (Spec 060 API)
                for hook in self._tick_hooks:
                    try:
                        r = hook(self._ctx, self._tick_sequence, now_ts)
                        if r is not None:
                            result = r
                    except Exception as exc:
                        msg = f"tick_hook={getattr(hook, '__name__', repr(hook))} error={type(exc).__name__}: {exc}"
                        logger.warning(msg)
                        result.errors.append(msg)

                # Modelo monotónico: poll_seconds = intervalo mínimo entre tick_starts
                elapsed = time.monotonic() - tick_start
                result.tick_duration_seconds = elapsed

                if on_tick_complete is not None:
                    try:
                        on_tick_complete(result)
                    except Exception:
                        pass

                sleep_seconds = max(0.0, poll_seconds - elapsed)
                self._shutdown_event.wait(timeout=sleep_seconds)

        except KeyboardInterrupt:
            logger.info("CoreSupervisoryEngine: KeyboardInterrupt received, stopping.")
        finally:
            self._running = False
            logger.info(
                "CoreSupervisoryEngine stopped after %d ticks. Total hooks: %d",
                self._tick_sequence,
                len(self._hooks),
            )

    def shutdown(self) -> None:
        """Signal the loop to stop after the current tick completes."""
        self._shutdown_event.set()

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def tick_sequence(self) -> int:
        return self._tick_sequence

    @property
    def registered_hooks(self) -> List[SupervisoryHook]:
        """Lista de hooks declarativos registrados, ordenados por etapa."""
        return list(self._hooks)

    # ------------------------------------------------------------------
    # Convenience class method — compatible con Spec 060
    # ------------------------------------------------------------------

    @classmethod
    def run_forever(
        cls,
        context: MonitorContext,
        tick_callable: Callable[[MonitorContext, int, float], TickResult],
        states: Dict[str, Any],
        last_update_id_ref: Dict[str, Optional[int]],
    ) -> None:
        """Crear un engine, registrar un tick hook, y ejecutar hasta interrupción."""
        engine = cls(context)
        engine.register_tick_hook(tick_callable)
        engine.run(states, last_update_id_ref)


# ---------------------------------------------------------------------------
# Hooks canónicos — PersistenceHook, GovernanceInterlockHook, TimingGuardHook
# ---------------------------------------------------------------------------

class PersistenceHook(SupervisoryHook):
    """Hook de persistencia atómica: delega en StateManager.save() fuera de state_lock.

    Etapa PERSISTENCE — siempre se ejecuta, incluso si etapas previas fallaron.

    Comportamiento de skip: si tick_data['_state_persisted'] es True, el loop
    principal ya persistió el estado en este tick (patrón legacy). El hook
    actúa como respaldo únicamente cuando esa marca no está presente.

    last_daily_digest_date: se lee de tick_data['last_daily_digest_date'] si está
    disponible (inyectado por el caller), para evitar usar el valor stale del contexto.
    """

    name = "persistence"
    stage = HookStage.PERSISTENCE

    def execute(
        self,
        context: MonitorContext,
        tick_sequence: int,
        now_ts: float,
        tick_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        # Skip guard: si el loop legacy ya persistió en este tick, evitar doble escritura.
        if tick_data.get("_state_persisted", False):
            return {"persistence_skipped": True, "reason": "already_persisted_by_main_loop"}

        states = tick_data.get("states", {})
        last_update_id_ref = tick_data.get("last_update_id_ref", {})
        last_update_id = last_update_id_ref.get("value") if last_update_id_ref else None

        # Prefer tick_data value (injected by caller with current _LAST_DAILY_DIGEST_DATE)
        # over context.last_daily_digest_date which may be stale (set only at startup).
        last_daily_digest_date = tick_data.get(
            "last_daily_digest_date",
            getattr(context, "last_daily_digest_date", None),
        )

        if context.state_manager is not None:
            context.state_manager.save(states, last_update_id, last_daily_digest_date)
            return {"persistence_saved": True}

        return {"persistence_skipped": True, "reason": "no_state_manager"}



class GovernanceInterlockHook(SupervisoryHook):
    """Hook de evaluación de expiración de temporizadores de gobernanza.

    Lee context.governance y evalúa si el temporizador venció.
    La acción real (mutación del global) ocurre en main() para preservar
    los contratos de inspect.getsource(main). Este hook sólo registra
    el estado para telemetría y tests.
    """

    name = "governance_interlock"
    stage = HookStage.GOVERNANCE

    def execute(
        self,
        context: MonitorContext,
        tick_sequence: int,
        now_ts: float,
        tick_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        gov = context.governance
        if gov is None:
            return {"governance_expired": False}

        expired = (
            gov.expires_at_ts is not None
            and gov.is_expired(now_ts)
        )
        return {"governance_expired": expired, "governance_master": getattr(gov, "master_enabled", True)}


class TimingGuardHook(SupervisoryHook):
    """Hook de telemetría de timing: mide latencia del tick y emite advertencia si supera umbral.

    Etapa PRE_TICK: registra tick_start en tick_data.
    Debe usarse en conjunto con un hook POST_TICK para medir el delta.
    """

    name = "timing_guard"
    stage = HookStage.PRE_TICK

    def __init__(self, warn_threshold_seconds: float = 25.0) -> None:
        self._warn_threshold = warn_threshold_seconds
        self._last_tick_start: Optional[float] = None

    def execute(
        self,
        context: MonitorContext,
        tick_sequence: int,
        now_ts: float,
        tick_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        mono_now = time.monotonic()
        tick_data["_timing_guard_start"] = mono_now

        if self._last_tick_start is not None:
            interval = mono_now - self._last_tick_start
            poll_seconds = context.poll_seconds
            if interval > poll_seconds + self._warn_threshold:
                logger.warning(
                    "TimingGuardHook: tick#%d interval=%.1fs exceeds poll=%ds+threshold=%ds",
                    tick_sequence,
                    interval,
                    poll_seconds,
                    self._warn_threshold,
                )
        self._last_tick_start = mono_now
        return {"timing_guard_mono": mono_now}


# ---------------------------------------------------------------------------
# Pure helper functions (Spec 060 legado — mantenidas para compatibilidad)
# ---------------------------------------------------------------------------

def log_tick_header(tick_sequence: int, now_ts: float, qa_mode: bool) -> None:
    """Log the start of a supervisory tick (no-op in production, useful in tests)."""
    if qa_mode:
        logger.debug("TICK#%d ts=%.3f", tick_sequence, now_ts)


def check_governance_expiry(context: MonitorContext, now_ts: float) -> bool:
    """Return True if the governance timer has expired."""
    gov = context.governance
    if gov is None:
        return False
    if gov.is_expired(now_ts) and not gov.master_enabled:
        return True
    return False


def should_skip_actuators(context: MonitorContext, now_ts: float) -> bool:
    """Return True if actuators should be suppressed (QA mode or governance)."""
    if context.qa_mode and not context.qa_allow_actions:
        return True
    gov = context.governance
    if gov is None:
        return False
    allowed, _ = _check_master(gov, now_ts)
    return not allowed


def _check_master(gov: Any, now_ts: float) -> tuple:  # type: ignore[type-arg]
    """Thin wrapper around should_allow_intervention for the master switch."""
    try:
        from app.governance.intervention_policy import ACTION_REBOOT_L2, should_allow_intervention
        return should_allow_intervention(ACTION_REBOOT_L2, gov, now_ts)
    except Exception:
        return True, "error_fallback_allow"
