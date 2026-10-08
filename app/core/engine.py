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
from pathlib import Path
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
        extra_tick_data: Optional[Dict[str, Any]] = None,
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

        import app.core.pipeline as _pipeline
        current_digest_date = (
            getattr(_pipeline, "_LAST_DAILY_DIGEST_DATE", None)
            or getattr(self._ctx, "last_daily_digest_date", None)
        )
        tick_data: Dict[str, Any] = {
            "states": states,
            "last_update_id_ref": last_update_id_ref,
            "now_ts": now_ts,
            "process_start_ts": getattr(self, "process_start_ts", now_ts),
            "previous_signals": getattr(self, "_last_signals", {}),
            "tick_sequence": self._tick_sequence,
            "last_daily_digest_date": current_digest_date,
        }
        if extra_tick_data:
            tick_data.update(extra_tick_data)
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

        if "current_tick_signals" in tick_data:
            self._last_signals = tick_data["current_tick_signals"]
        if tick_data.get("last_daily_digest_date"):
            self._ctx.last_daily_digest_date = tick_data["last_daily_digest_date"]
        result.miners_responded = len(tick_data.get("tick_responded_miners", []))
        result.miners_failed = len(tick_data.get("tick_failed_miners", []))
        result.reboots_triggered = tick_data.get("reboots_triggered", [])
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
                if not self._shutdown_event.is_set():
                    try:
                        from app.telegram.poller import _WAKEUP_EVENT
                        _WAKEUP_EVENT.wait(timeout=sleep_seconds)
                        _WAKEUP_EVENT.clear()
                    except Exception:
                        self._shutdown_event.wait(timeout=sleep_seconds)

        except KeyboardInterrupt:
            logger.info("CoreSupervisoryEngine: KeyboardInterrupt received, stopping.")
        finally:
            self._running = False
            if getattr(self, "watchdog_ipc_server", None) is not None:
                try:
                    self.watchdog_ipc_server.stop()
                except Exception:
                    pass
            if getattr(self, "acquirer", None) is not None:
                try:
                    self.acquirer.close()
                except Exception:
                    pass
            if getattr(self._ctx, "event_store", None) is not None:
                try:
                    self._ctx.event_store.close()
                except Exception:
                    pass
            if getattr(self, "gateway_heartbeat", None) is not None:
                try:
                    self.gateway_heartbeat.stop()
                except Exception:
                    pass
            logger.info(
                "CoreSupervisoryEngine stopped after %d ticks. Total hooks: %d",
                self._tick_sequence,
                len(self._hooks),
            )

    def shutdown(self) -> None:
        """Signal the loop to stop after the current tick completes."""
        self._shutdown_event.set()
        try:
            from app.telegram.poller import _WAKEUP_EVENT
            _WAKEUP_EVENT.set()
        except Exception:
            pass

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

    def register_standard_hooks(self) -> None:
        """Register the 7 canonical pipeline stages in deterministic sequence."""
        from app.core.pipeline import (
            AcquisitionHook,
            GovernanceHook,
            PostTickHook,
            PreTickHook,
        )
        self.register_hook(TimingGuardHook(warn_threshold_seconds=25.0))
        self.register_hook(PreTickHook())
        self.register_hook(AcquisitionHook())
        self.register_hook(DetectionHook())
        self.register_hook(GovernanceInterlockHook())
        self.register_hook(GovernanceHook())
        self.register_hook(ActuatorHook())
        self.register_hook(PersistenceHook())
        self.register_hook(PostTickHook())

    @classmethod
    def initialize(
        cls,
        config: Optional[Dict[str, Any]] = None,
        state_path: Optional[Path] = None,
    ) -> CoreSupervisoryEngine:
        import os
        import platform
        import queue
        import sys
        from app.core.config import (
            init_logger_from_config,
            load_config,
            log,
            qa_allow_real_actions,
            qa_enabled,
            qa_notify_enabled,
            qa_verbose_enabled,
        )
        from app.core.context import build_monitor_context
        from app.core.state_manager import StateManager, load_state, _SAVE_STATE_LOCK
        from app.core.system import release_mutex
        from app.core.event_store import EventStore
        from app.core.acquisition import (
            AcquisitionConfig,
            Api4028Transport,
            BoundedAcquirer,
            MinerEndpoint,
        )
        from app.telegram.poller import telegram_polling_worker
        from app.telegram.sender import telegram_sender_worker

        process_start_ts = time.time()
        if config is None:
            config = load_config()
        init_logger_from_config(config)

        log(f"script={Path(__file__).resolve()}")
        log(f"executable={sys.executable}")
        log(f"cwd={os.getcwd()}")
        log(f"sys.version={sys.version}")
        log(f"sys._base_executable={getattr(sys, '_base_executable', None)}")
        log(f"platform={platform.platform()}")
        base_exe = getattr(sys, "_base_executable", None)
        launcher_suspect = False
        if base_exe and os.path.abspath(base_exe) != os.path.abspath(sys.executable):
            launcher_suspect = True
        if "py.exe" in (sys.executable or "").lower():
            launcher_suspect = True
        if launcher_suspect:
            log("[WARN] Posible launcher/shim detectado. Ver README (Windows) para diagnostico.")

        env_qa_mode = os.getenv("QA_MODE") or "VACIO"
        env_qa_mode_force = os.getenv("QA_MODE_FORCE") or "VACIO"
        env_qa_allow = os.getenv("QA_ALLOW_REAL_ACTIONS") or "VACIO"
        log(
            f"ENV QA_MODE={env_qa_mode} QA_MODE_FORCE={env_qa_mode_force} "
            f"QA_ALLOW_REAL_ACTIONS={env_qa_allow}"
        )
        qa_mode, qa_mode_source = qa_enabled(config)
        import app.miner_monitor as _mm
        _mm._QA_MODE = qa_mode
        qa_notify = qa_notify_enabled(config)
        qa_verbose = qa_verbose_enabled(config)
        qa_allow_actions = qa_allow_real_actions(config)

        startup_guard_seconds = int(config.get("startup_guard_seconds", 600))
        log(
            f"Startup safety guard activo por {startup_guard_seconds} segundos: "
            "auto-reboot deshabilitado durante este período"
        )
        log(
            f"qa_mode={str(qa_mode).lower()} source={qa_mode_source} "
            f"qa_allow_real_actions={str(qa_allow_actions).lower()} "
            f"qa_verbose={str(qa_verbose).lower()}"
        )

        miners = config.get("miners", [])
        telegram_cfg = config.get("telegram", {})
        bot_token = telegram_cfg.get("bot_token")
        chat_id = telegram_cfg.get("chat_id")

        if not bot_token or not chat_id:
            log("ERROR: telegram.bot_token y telegram.chat_id son obligatorios en app/config.json.")
            release_mutex()
            sys.exit(1)

        if not miners:
            log("ERROR: Debe definir al menos un minero en app/config.json.")
            release_mutex()
            sys.exit(1)

        valid_miners = []
        for miner in miners:
            name = miner.get("name", "sin-nombre")
            host = miner.get("host", "")
            port_raw = miner.get("port", 4028)
            try:
                port = int(port_raw)
            except (TypeError, ValueError):
                port = 0
            if not host or port <= 0:
                log(f"[WARN] Minero invalido, se omite: {name} ({host}:{port_raw})")
                continue
            valid_miner = dict(miner)
            valid_miner["name"] = name
            valid_miner["host"] = host
            valid_miner["port"] = port
            valid_miners.append(valid_miner)

        if not valid_miners:
            log("ERROR: No hay mineros validos para monitorear.")
            release_mutex()
            sys.exit(1)

        event_store_enabled = bool(config.get("event_store_enabled", True))
        event_store: Optional[EventStore] = None
        if event_store_enabled:
            event_store_path_raw = str(config.get("event_store_path", "data/miner_alerts.db"))
            event_store_path = Path(event_store_path_raw).expanduser()
            if not event_store_path.is_absolute():
                event_store_path = Path(__file__).resolve().parent.parent.parent / event_store_path
            event_store = EventStore(
                event_store_path,
                on_error=lambda message: log(f"[ERROR] {message}"),
            )
            log(
                f"EVENT_STORE enabled=true path={event_store.path} "
                f"available={str(event_store.available).lower()} schema={event_store.schema_version}"
            )
            if event_store.available:
                deleted = event_store.prune(
                    now_ts=process_start_ts,
                    sample_retention_days=max(1, int(config.get("telemetry_retention_days", 90))),
                    event_retention_days=max(1, int(config.get("event_retention_days", 365))),
                    decision_retention_days=max(1, int(config.get("decision_retention_days", 180))),
                )
                log(
                    f"EVENT_STORE retention samples_deleted={deleted['samples']} "
                    f"events_deleted={deleted['events']} decisions_deleted={deleted['decisions']} "
                    f"firmware_events_deleted={deleted['firmware_events']} "
                    f"collector_runs_deleted={deleted['collector_runs']}"
                )
        else:
            log("EVENT_STORE enabled=false")

        if state_path is None:
            state_path = Path(__file__).resolve().parent.parent / "state.json"
        states, last_update_id = load_state(state_path)
        last_update_id_ref = {"value": last_update_id}
        last_update_lock = threading.Lock()
        snapshot_ref: Dict[str, Optional[str]] = {"value": None}
        snapshot_lock = threading.Lock()
        state_lock = threading.RLock()
        pending_reboots: Dict[str, dict] = {}
        pending_lock = threading.Lock()

        tg_queue: queue.Queue = queue.Queue(maxsize=200)
        _mm._TELEGRAM_QUEUE = tg_queue
        import app.telegram.sender as _ts
        _ts._TELEGRAM_QUEUE = tg_queue

        from app.core.pipeline import (
            _ACTIVE_SCHEDULED_WINDOW,
            _ELEVATOR_CONTINGENCY_STATES,
            _GLOBAL_INTERVENTION_GOV,
        )
        import app.core.pipeline as _pipeline

        state_manager = StateManager(
            state_path,
            state_lock,
            flush_lock=_SAVE_STATE_LOCK,
            get_globals_fn=lambda: vars(_mm),
        )

        loaded_digest_date = state_manager.last_daily_digest_date
        _pipeline._LAST_DAILY_DIGEST_DATE = loaded_digest_date

        monitor_ctx = build_monitor_context(
            config=config,
            state_path=state_path,
            miners=valid_miners,
            bot_token=bot_token,
            chat_id=str(chat_id),
            state_lock=state_lock,
            telegram_queue=tg_queue,
            state_manager=state_manager,
            event_store=event_store,
            qa_mode=qa_mode,
            qa_allow_actions=qa_allow_actions,
            qa_notify=qa_notify,
            qa_verbose=qa_verbose,
            hashcore_cfg=config.get("hashcore", {}),
            governance=_GLOBAL_INTERVENTION_GOV,
            elevator_contingency=_ELEVATOR_CONTINGENCY_STATES,
            scheduled_window=_ACTIVE_SCHEDULED_WINDOW,
            last_daily_digest_date=loaded_digest_date,
        )

        sender_thread = threading.Thread(
            target=telegram_sender_worker,
            args=(bot_token, tg_queue, qa_mode),
            daemon=True,
            name="TelegramSender",
        )
        sender_thread.start()

        telegram_thread = threading.Thread(
            target=telegram_polling_worker,
            args=(
                bot_token,
                str(chat_id),
                state_path,
                states,
                last_update_id_ref,
                last_update_lock,
                snapshot_ref,
                snapshot_lock,
                state_lock,
                valid_miners,
                config.get("hashcore", {}),
                pending_reboots,
                pending_lock,
                config,
                qa_mode,
                qa_allow_actions,
                event_store,
            ),
            daemon=True,
            name="TelegramPolling",
        )
        telegram_thread.start()

        acq_config, acq_warnings = AcquisitionConfig.from_mapping(config)
        for warning in acq_warnings:
            log(f"[WARN] {warning}")
        acquirer: Optional[BoundedAcquirer] = None
        acq_endpoints: tuple = ()
        if acq_config.enabled:
            acq_endpoints = tuple(
                MinerEndpoint(
                    key=f"{m['name']}|{m['host']}:{m['port']}",
                    host=m["host"],
                    port=m["port"],
                )
                for m in valid_miners
            )
            acquirer = BoundedAcquirer(
                Api4028Transport(),
                workers=acq_config.workers,
                timeout_seconds=acq_config.timeout_seconds,
            )
            log(
                f"ADAPTIVE_ACQUISITION acquirer_ready=true "
                f"endpoints={len(acq_endpoints)} workers={acq_config.workers}"
            )

        gateway_heartbeat = None
        if config.get("gateway_heartbeat_enabled", False):
            try:
                from app.network.gateway_heartbeat import GatewayHeartbeatWorker
                gateway_heartbeat = GatewayHeartbeatWorker(
                    host=str(config.get("gateway_host", "192.168.100.1")),
                    port=int(config.get("gateway_port", 80)),
                    interval_s=float(config.get("gateway_heartbeat_interval_s", 5.0)),
                    connect_timeout_s=float(config.get("gateway_connect_timeout_ms", 50)) / 1000.0,
                    fallback_port=int(config.get("gateway_fallback_port", 53)),
                )
                gateway_heartbeat.start()
            except Exception as _gw_exc:
                log(f"[WARN] GATEWAY_HEARTBEAT failed to start: {_gw_exc}")
                gateway_heartbeat = None

        watchdog_ipc_server = None
        if config.get("watchdog_ipc_enabled", True):
            try:
                from app.ipc.watchdog_pipe import WatchdogIPCServer

                def _get_ipc_status() -> tuple[int, float, float]:
                    return (getattr(engine, "_tick_sequence", 0), process_start_ts, getattr(engine, "_last_tick_duration", 0.0))

                _ipc_pipe_name = str(config.get("watchdog_ipc_pipe_name", r"\\.\pipe\MinerAlertsWatchdog"))
                _ipc_fallback_port = int(config.get("watchdog_ipc_fallback_port", 4029))
                _ipc_timeout_s = float(config.get("watchdog_ipc_timeout_ms", 100)) / 1000.0
                _ipc_forensics_dir = (
                    Path(config["log_file_path"]).parent
                    if config.get("log_file_path")
                    else Path("logs")
                )
                watchdog_ipc_server = WatchdogIPCServer(
                    pipe_name=_ipc_pipe_name,
                    fallback_port=_ipc_fallback_port,
                    timeout_s=_ipc_timeout_s,
                    get_status_callback=_get_ipc_status,
                    forensics_dir=_ipc_forensics_dir,
                )
                watchdog_ipc_server.start()
            except Exception as _ipc_exc:
                log(f"[WARN] WATCHDOG_IPC failed to start: {_ipc_exc}")
                watchdog_ipc_server = None

        engine = cls(monitor_ctx)
        engine.states = states
        engine.last_update_id_ref = last_update_id_ref
        engine.snapshot_ref = snapshot_ref
        engine.pending_reboots = pending_reboots
        engine.acquirer = acquirer
        engine.acq_config = acq_config
        engine.acq_endpoints = acq_endpoints
        engine.gateway_heartbeat = gateway_heartbeat
        engine.watchdog_ipc_server = watchdog_ipc_server
        engine.process_start_ts = process_start_ts
        engine.register_standard_hooks()
        return engine

    def run_forever(
        self_or_cls,
        context: Optional[MonitorContext] = None,
        tick_callable: Optional[Callable[[MonitorContext, int, float], TickResult]] = None,
        states: Optional[Dict[str, Any]] = None,
        last_update_id_ref: Optional[Dict[str, Optional[int]]] = None,
    ) -> None:
        """Run the supervisory pipeline until interrupt or shutdown.

        Supports both instance call (engine.run_forever()) and legacy classmethod call.
        """
        if isinstance(self_or_cls, CoreSupervisoryEngine):
            st = getattr(self_or_cls, "states", states or {})
            upd = getattr(self_or_cls, "last_update_id_ref", last_update_id_ref or {"value": None})
            self_or_cls.run(st, upd)
        else:
            cls = self_or_cls
            if context is None:
                raise ValueError("context is required when calling CoreSupervisoryEngine.run_forever as classmethod")
            engine = cls(context)
            if tick_callable is not None:
                engine.register_tick_hook(tick_callable)
            engine.run(states or {}, last_update_id_ref or {"value": None})


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
        gov = tick_data.get("governance") or context.governance
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


class DetectionHook(SupervisoryHook):
    """Hook de detección y clasificación de estado operacional del minero (Spec 070).

    Etapa DETECTION (30) — clasifica el estado operacional (OK, LOW, OFFLINE, HASHBOARD)
    garantizando la precedencia constitucional de placas faltantes sobre tasa baja.
    """

    name = "detection"
    stage = HookStage.DETECTION

    @staticmethod
    def classify_state(
        *,
        responded: bool,
        rate_ths: Optional[float],
        threshold_ths: float,
        active_boards: Optional[int],
        expected_boards: int = 3,
        startup_grace_active: bool = False,
        offline_streak: int = 1,
        low_streak: int = 1,
        ok_streak: int = 1,
        fails_before_alert: int = 1,
        recovery_successes: int = 1,
        prev_state: str = "OK",
    ) -> str:
        """Clasificar estado operacional con precedencia determinista:
        1. Si startup_grace_active es True, no transiciona a OFFLINE/HASHBOARD/LOW.
        2. Si no responde y offline_streak >= fails -> OFFLINE.
        3. Si responde y active_boards < expected_boards -> HASHBOARD (precedencia sobre LOW).
        4. Si responde y rate_ths < threshold_ths y low_streak >= fails -> LOW.
        5. Si responde y rate_ths >= threshold_ths y ok_streak >= recovery -> OK.
        """
        new_state = prev_state
        if not startup_grace_active:
            if not responded and offline_streak >= fails_before_alert:
                new_state = "OFFLINE"
            elif responded and active_boards is not None and active_boards < expected_boards:
                new_state = "HASHBOARD"
            elif (
                responded
                and rate_ths is not None
                and rate_ths < threshold_ths
                and low_streak >= fails_before_alert
            ):
                new_state = "LOW"
        if (
            responded
            and rate_ths is not None
            and rate_ths >= threshold_ths
            and ok_streak >= recovery_successes
        ):
            new_state = "OK"
        return new_state

    def execute(
        self,
        context: MonitorContext,
        tick_sequence: int,
        now_ts: float,
        tick_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        from app.core.config import log
        from app.core.pipeline import format_fleet_restored_line, format_rate
        from app.core.reboot_safety import (
            STATE_HASHBOARD,
            STATE_LOW,
            STATE_OFFLINE,
            STATE_OK,
        )
        from app.core.restart_intelligence import classify_restart
        from app.governance.energy_efficiency import (
            assess_miner_efficiency,
            evaluate_efficiency_alerts,
        )
        from app.governance.fan_health import (
            assess_miner_cooling,
            evaluate_cooling_alerts,
        )
        from app.governance.thermal_guard import process_emergency_thermal_guard
        from app.hardware.chain_collector import _async_collect_chain_telemetry
        from app.telegram.fleet_cards import display_name
        from app.telegram.sender import send_telegram
        from app.vnish.presets import (
            assess_miner_preset,
            evaluate_preset_alerts,
        )

        miner_results = tick_data.get("miner_results", {})
        startup_grace_active = tick_data.get("startup_grace_active", False)
        states = tick_data.get("states", {})
        config = context.config
        state_lock = context.state_lock
        event_store = context.event_store
        bot_token = context.bot_token
        chat_id = context.chat_id
        qa_mode = context.qa_mode
        qa_notify = context.qa_notify

        fails_before_alert = int(config.get("fails_before_alert", 3))
        recovery_successes = int(config.get("recovery_successes", 1))
        threshold_ths = context.threshold_ths
        expected_boards = int(config.get("expected_boards", 3))
        notify_reboot = bool(config.get("notify_reboot", True))
        reboot_cooldown_seconds = int(config.get("reboot_cooldown_seconds", 1800))
        reboot_window_seconds = int(config.get("reboot_window_seconds", 300))
        chain_telemetry_enabled = bool(config.get("chain_telemetry_enabled", True))
        vnish_api_password = str(config.get("vnish_api_password", "admin"))

        reboot_names_tick: List[str] = []
        current_tick_signals: Dict[str, str] = {}

        for state_key, res in miner_results.items():
            miner = res["miner"]
            state = res["state"]
            responded = res["responded"]
            rate_ths = res["rate_ths"]
            elapsed = res["elapsed"]
            previous_elapsed = res["previous_elapsed"]
            reboot_reason = res["reboot_reason"]
            active_boards = res["active_boards"]
            vnish_telemetry = res["vnish_telemetry"]
            name = miner["name"]
            name_display = display_name(name)
            host = miner["host"]

            with state_lock:
                if not responded:
                    state.offline_streak += 1
                    state.low_streak = 0
                    state.ok_streak = 0
                elif rate_ths is None:
                    state.offline_streak = 0
                    state.low_streak = 0
                    state.ok_streak = 0
                elif rate_ths < threshold_ths:
                    state.low_streak += 1
                    state.offline_streak = 0
                    state.ok_streak = 0
                else:
                    state.ok_streak += 1
                    state.low_streak = 0
                    state.offline_streak = 0

                if startup_grace_active:
                    state.offline_streak = 0
                    state.low_streak = 0

                prev_state = state.state
                new_state = DetectionHook.classify_state(
                    responded=responded,
                    rate_ths=rate_ths,
                    threshold_ths=threshold_ths,
                    active_boards=active_boards,
                    expected_boards=expected_boards,
                    startup_grace_active=startup_grace_active,
                    offline_streak=state.offline_streak,
                    low_streak=state.low_streak,
                    ok_streak=state.ok_streak,
                    fails_before_alert=fails_before_alert,
                    recovery_successes=recovery_successes,
                    prev_state=prev_state or STATE_OK,
                )

                if new_state != prev_state and new_state in (STATE_HASHBOARD, STATE_LOW):
                    if chain_telemetry_enabled and event_store is not None and getattr(event_store, "available", False):
                        threading.Thread(
                            target=_async_collect_chain_telemetry,
                            args=(
                                context.miners,
                                event_store,
                                vnish_api_password,
                                name,
                                config,
                                bot_token,
                                chat_id,
                                qa_mode,
                                qa_notify,
                                states,
                                state_lock,
                            ),
                            daemon=True,
                            name=f"ChainTelemetryTransition_{name}",
                        ).start()

                state.state = new_state

                if new_state == STATE_OK:
                    state.low_streak = 0
                    state.offline_streak = 0
                    state.hashboard_since_ts = None
                    state.auto_restart_count = 0

                if new_state == STATE_LOW:
                    if state.low_since_ts is None:
                        state.low_since_ts = now_ts
                else:
                    state.low_since_ts = None
                    state.low_streak = 0

                if new_state == STATE_HASHBOARD:
                    if state.hashboard_since_ts is None:
                        state.hashboard_since_ts = now_ts
                else:
                    state.hashboard_since_ts = None

                if startup_grace_active:
                    state.low_since_ts = None
                    state.hashboard_since_ts = None

            # State transition logging and event recording
            if new_state != prev_state and prev_state is not None:
                log(f"[{name_display}] Transición de estado: {prev_state} -> {new_state}")
                if event_store is not None and getattr(event_store, "available", False):
                    try:
                        event_store.record_event(
                            occurred_ts=now_ts,
                            miner_key=state_key,
                            miner_name=name_display,
                            host=host,
                            event_type="state_transition",
                            severity="warning" if new_state != STATE_OK else "info",
                            previous_state=prev_state,
                            new_state=new_state,
                            rate_ths=rate_ths,
                            threshold_ths=threshold_ths,
                            summary=f"{prev_state} -> {new_state}",
                            details={
                                "active_boards": active_boards,
                                "expected_boards": expected_boards,
                                "responded": responded,
                            },
                        )
                    except Exception:
                        pass

                # Telegram alert dispatch for state changes
                if (not qa_mode) or qa_notify:
                    if new_state == STATE_OK:
                        all_ok = all(
                            getattr(s, "state", None) == STATE_OK
                            for s in states.values()
                        )
                        if all_ok:
                            restored_text = "🟢 *FLOTA RESTABLECIDA*\n\nTodos los mineros operando normalmente.\n\n"
                            for m_item in context.miners:
                                m_st = states.get(f"{m_item['name']}|{m_item['host']}:{m_item.get('port', 4028)}")
                                m_r = getattr(m_st, "last_rate_ths", None)
                                m_t = getattr(m_st, "last_max_chip_temp", None)
                                restored_text += format_fleet_restored_line(display_name(m_item["name"]), m_r, m_t) + "\n"
                            send_telegram(
                                bot_token,
                                str(chat_id),
                                restored_text,
                                "STATUS",
                                "fleet_restored",
                            )
                        else:
                            send_telegram(
                                bot_token,
                                str(chat_id),
                                f"🟢 *{name_display} RECUPERADO*\n\nEstado restablecido a *OK* ({format_rate(rate_ths)}).",
                                "STATUS",
                                f"recovered_{name}",
                            )
                    elif new_state == STATE_HASHBOARD:
                        send_telegram(
                            bot_token,
                            str(chat_id),
                            f"⚠️ *FALLA DE PLACAS*\n\nMinero: *{name_display}*\nPlacas activas: *{active_boards}/{expected_boards}*\nHashrate: *{format_rate(rate_ths)}*\n\nEstado: *HASHBOARD*",
                            "HASHBOARD",
                            f"hashboard_{name}",
                        )
                    elif new_state == STATE_LOW:
                        send_telegram(
                            bot_token,
                            str(chat_id),
                            f"⚠️ *BAJA PRODUCCIÓN*\n\nMinero: *{name_display}*\nHashrate: *{format_rate(rate_ths)}* (umbral: {threshold_ths:.1f} TH/s)\n\nEstado: *LOW*",
                            "LOW_HASHRATE",
                            f"low_{name}",
                        )
                    elif new_state == STATE_OFFLINE:
                        send_telegram(
                            bot_token,
                            str(chat_id),
                            f"🔴 *MINERO OFFLINE*\n\nMinero: *{name_display}* ({host})\nSin respuesta del socket 4028.\n\nEstado: *OFFLINE*",
                            "OFFLINE",
                            f"offline_{name}",
                        )

            # Preventative health checks
            cooling_alert_enabled = bool(config.get("cooling_alert_enabled", True))
            if cooling_alert_enabled and responded and vnish_telemetry:
                cooling_ass = assess_miner_cooling(
                    miner_name=name_display,
                    max_temp_c=vnish_telemetry.max_temp_c,
                    fan_rpm_max=vnish_telemetry.fan_rpm_max,
                    fan_pwm_percent=vnish_telemetry.fan_pwm_percent,
                    diagnostic_flags=vnish_telemetry.diagnostic_flags,
                    rate_ths=rate_ths,
                    critical_temp_c=float(config.get("cooling_critical_temp_c", 84.5)),
                    saturate_temp_c=float(config.get("cooling_saturate_temp_c", 84.0)),
                    saturate_pwm_pct=float(config.get("cooling_saturate_pwm_pct", 98.0)),
                    saturate_rpm=int(config.get("cooling_saturate_rpm", 5800)),
                    fan_mode=vnish_telemetry.fan_mode,
                )
                cooling_warning = evaluate_cooling_alerts(
                    state=state,
                    assessment=cooling_ass,
                    now_ts=now_ts,
                    config=config,
                )
                is_currently_snoozed = (
                    state.snooze_until_ts is not None and now_ts < state.snooze_until_ts
                )
                if cooling_warning and not is_currently_snoozed and ((not qa_mode) or qa_notify):
                    send_telegram(
                        bot_token,
                        str(chat_id),
                        cooling_warning,
                        "COOLING_WARNING",
                        "cooling_warning",
                    )
                    log(f"[COOLING_WARNING] miner={name_display} status={cooling_ass.status}")

            # Thermal guard protection
            if not getattr(state, "is_shutdown_maintenance", False) and (
                responded or getattr(state, "thermal_pause_until_ts", None) is not None
            ):
                try:
                    process_emergency_thermal_guard(
                        miner=miner,
                        state=state,
                        max_temp_c=vnish_telemetry.max_temp_c if (responded and vnish_telemetry) else getattr(state, "governor_last_temp_c", None),
                        config=config,
                        now_ts=now_ts,
                        vnish_pw=vnish_api_password,
                        qa_mode=qa_mode,
                        qa_notify=qa_notify,
                        bot_token=bot_token,
                        chat_id=str(chat_id),
                    )
                except Exception as _tg_exc:
                    log(f"[THERMAL_GUARD_ERR] Emergency thermal guard error for miner={name_display}: {_tg_exc}")

            # Restart detection
            if reboot_reason and previous_elapsed is not None and elapsed is not None:
                restart_attribution_window_seconds = int(config.get("restart_attribution_window_seconds", 3600))
                restart_classification = classify_restart(
                    restart_reason=reboot_reason,
                    detected_ts=now_ts,
                    last_manual_action_ts=state.last_manual_reboot_ts,
                    last_auto_action_ts=state.last_auto_reboot_ts,
                    last_preset_change_ts=getattr(state, "last_preset_change_ts", None),
                    last_shutdown_ts=getattr(state, "shutdown_maintenance_ts", None),
                    attribution_window_seconds=restart_attribution_window_seconds,
                )
                m_group = miner.get("electrical_group", "default")
                recent_chain_samples = None
                if event_store is not None and getattr(event_store, "available", False):
                    try:
                        recent_chain_samples = (
                            event_store.get_latest_chain_samples(name)
                            or event_store.get_latest_chain_samples(name_display)
                            or event_store.get_latest_chain_samples(state_key)
                        )
                    except Exception:
                        pass

                from app.governance.preset_balancer import record_elevator_restart_circumstance
                elev_circumstance = record_elevator_restart_circumstance(
                    miner_name=name_display,
                    electrical_group=m_group,
                    miners=context.miners,
                    states=states,
                    now_ts=now_ts,
                    cascade_window_s=float(config.get("preset_balancer_group_cascade_window_s", 1800.0)),
                    chain_samples=recent_chain_samples,
                )
                restart_details = {
                    "reason": reboot_reason,
                    "first_tick": False,
                    "electrical_group": m_group,
                    "group_total_power_w": elev_circumstance.get("group_total_power_w", 0.0),
                    "pre_restart_power_w": state.governor_last_power_w,
                    "pre_restart_temp_c": state.governor_last_temp_c,
                    "is_elevator_cascade": elev_circumstance.get("is_elevator_cascade", False),
                    "cascade_peer": elev_circumstance.get("cascade_peer"),
                    "cascade_delta_s": elev_circumstance.get("cascade_delta_s"),
                    "culprit_chain": elev_circumstance.get("culprit_chain"),
                }
                incident_summary = f"Uptime reiniciado: {previous_elapsed}s -> {elapsed}s"
                culprit = elev_circumstance.get("culprit_chain")
                if culprit and isinstance(culprit, dict):
                    incident_summary += f" | Causa aislada: Cadena {culprit.get('chain_id')} ({culprit.get('reason')})"

                if event_store is not None and getattr(event_store, "available", False):
                    try:
                        event_store.record_event(
                            occurred_ts=now_ts,
                            miner_key=state_key,
                            miner_name=name_display,
                            host=host,
                            event_type="restart_detected",
                            severity=restart_classification.severity,
                            classification=restart_classification.classification,
                            previous_state=prev_state,
                            new_state=new_state,
                            rate_ths=rate_ths,
                            threshold_ths=threshold_ths,
                            previous_elapsed=previous_elapsed,
                            current_elapsed=elapsed,
                            action_source=restart_classification.action_source,
                            action_ts=restart_classification.action_ts,
                            summary=incident_summary,
                            details=restart_details,
                        )
                    except Exception:
                        pass
                log(f"[{name_display}] Reinicio detectado ({reboot_reason}): {incident_summary}")

                if notify_reboot:
                    if (now_ts - (state.last_reboot_ts or 0.0)) >= reboot_cooldown_seconds:
                        if new_state in (STATE_LOW, STATE_OFFLINE):
                            reboot_names_tick.append(name_display)
                            state.last_reboot_ts = now_ts
                            state.reboot_pending_until = 0.0
                            state.reboot_pending_reason = ""
                            state.reboot_pending_elapsed = None
                        else:
                            state.reboot_pending_until = now_ts + reboot_window_seconds
                            state.reboot_pending_reason = reboot_reason
                            state.reboot_pending_elapsed = elapsed

            current_tick_signals[state_key] = new_state

        return {
            "detection_completed": True,
            "reboot_names_tick": reboot_names_tick,
            "current_tick_signals": current_tick_signals,
        }


class ActuatorHook(SupervisoryHook):
    """Hook de actuación y evaluación de políticas de auto-reboot (Spec 070).

    Etapa ACTUATOR (50) — evalúa compuertas de señal, guardas de arranque,
    temporizadores sostenidos, interlocks de seguridad (térmico, transición, flota),
    cooldowns y ventanas de cuota de reinicio.
    """

    name = "actuator"
    stage = HookStage.ACTUATOR

    @staticmethod
    def evaluate_auto_reboot_policy(
        *,
        state: Any,
        miner: Dict[str, Any],
        new_state: str,
        responded: bool,
        rate_ths: Optional[float],
        threshold_ths: float,
        active_boards: Optional[int],
        expected_boards: int = 3,
        now_ts: float = 1000.0,
        process_start_ts: float = 0.0,
        startup_guard_seconds: int = 600,
        low_sustained_seconds: int = 900,
        hashboard_sustained_seconds: int = 600,
        hashboard_reboot_enabled: bool = True,
        allow_partial_hashboard: bool = False,
        reboot_cooldown_seconds: int = 1800,
        max_reboots_per_window: int = 3,
        auto_reboot_window_seconds: int = 21600,
        interlock_decision: Optional[Any] = None,
        qa_mode: bool = False,
        qa_allow_actions: bool = False,
    ) -> Dict[str, Any]:
        """Evaluar compuertas e interlocks en orden estricto constitucional."""
        if hasattr(state, "auto_reboot_timestamps"):
            state.auto_reboot_timestamps = [
                ts for ts in state.auto_reboot_timestamps if (now_ts - ts) <= auto_reboot_window_seconds
            ]
        startup_guard_active = (now_ts - process_start_ts) < startup_guard_seconds

        from app.core.reboot_safety import (
            classify_auto_reboot_signal,
            auto_reboot_signal_allows_evaluation,
            reset_sustained_low_if_signal_ineligible,
            reset_sustained_hashboard_if_ineligible,
            STATE_LOW,
            STATE_HASHBOARD,
            INTERLOCK_FIRMWARE_TRANSITION,
        )

        signal = classify_auto_reboot_signal(responded, rate_ths, threshold_ths)

        if new_state == STATE_LOW and getattr(state, "low_since_ts", None):
            if not auto_reboot_signal_allows_evaluation(new_state, state.low_since_ts, signal):
                reset_sustained_low_if_signal_ineligible(state, signal)
                return {"allowed": False, "reason": "ineligible_signal", "signal": signal}

            if startup_guard_active:
                return {"allowed": False, "reason": "startup_guard", "signal": signal}

            if (now_ts - state.low_since_ts) < low_sustained_seconds:
                return {"allowed": False, "reason": "not_sustained", "signal": signal}

            if interlock_decision and not interlock_decision.allowed:
                if getattr(interlock_decision, "reason", None) == INTERLOCK_FIRMWARE_TRANSITION:
                    state.low_since_ts = now_ts
                return {"allowed": False, "reason": interlock_decision.reason, "signal": signal}

            last_reboot_ts = getattr(state, "last_auto_reboot_ts", None)
            if getattr(state, "last_manual_reboot_ts", None) is not None:
                last_reboot_ts = (
                    state.last_manual_reboot_ts
                    if last_reboot_ts is None
                    else max(last_reboot_ts, state.last_manual_reboot_ts)
                )
            if last_reboot_ts is not None and (now_ts - last_reboot_ts) < reboot_cooldown_seconds:
                return {"allowed": False, "reason": "cooldown", "signal": signal}

            if len(getattr(state, "auto_reboot_timestamps", [])) >= max_reboots_per_window:
                state.degraded_mode = True
                return {"allowed": False, "reason": "window", "signal": signal}

            if qa_mode and not qa_allow_actions:
                return {"allowed": False, "reason": "qa", "signal": signal}

            return {"allowed": True, "reason": "eligible", "signal": signal}

        elif (
            new_state == STATE_HASHBOARD
            and getattr(state, "hashboard_since_ts", None)
            and hashboard_reboot_enabled
        ):
            if not auto_reboot_signal_allows_evaluation(
                new_state=new_state,
                low_since_ts=None,
                signal_classification=signal,
                hashboard_since_ts=state.hashboard_since_ts,
                active_boards=active_boards,
                expected_boards=expected_boards,
                allow_partial_hashboard=allow_partial_hashboard,
                hashboard_reboot_enabled=hashboard_reboot_enabled,
            ):
                reset_sustained_hashboard_if_ineligible(
                    state=state,
                    signal_classification=signal,
                    active_boards=active_boards,
                    expected_boards=expected_boards,
                    allow_partial_hashboard=allow_partial_hashboard,
                )
                return {"allowed": False, "reason": "ineligible_signal", "signal": signal}

            if startup_guard_active:
                return {"allowed": False, "reason": "startup_guard", "signal": signal}

            if (now_ts - state.hashboard_since_ts) < hashboard_sustained_seconds:
                return {"allowed": False, "reason": "not_sustained", "signal": signal}

            if interlock_decision and not interlock_decision.allowed:
                if getattr(interlock_decision, "reason", None) == INTERLOCK_FIRMWARE_TRANSITION:
                    state.hashboard_since_ts = now_ts
                return {"allowed": False, "reason": interlock_decision.reason, "signal": signal}

            last_reboot_ts = getattr(state, "last_auto_reboot_ts", None)
            if getattr(state, "last_manual_reboot_ts", None) is not None:
                last_reboot_ts = (
                    state.last_manual_reboot_ts
                    if last_reboot_ts is None
                    else max(last_reboot_ts, state.last_manual_reboot_ts)
                )
            if last_reboot_ts is not None and (now_ts - last_reboot_ts) < reboot_cooldown_seconds:
                return {"allowed": False, "reason": "cooldown", "signal": signal}

            if len(getattr(state, "auto_reboot_timestamps", [])) >= max_reboots_per_window:
                state.degraded_mode = True
                return {"allowed": False, "reason": "window", "signal": signal}

            if qa_mode and not qa_allow_actions:
                return {"allowed": False, "reason": "qa", "signal": signal}

            return {"allowed": True, "reason": "eligible", "signal": signal}

        return {"allowed": False, "reason": "not_candidate", "signal": signal}

    def execute(
        self,
        context: MonitorContext,
        tick_sequence: int,
        now_ts: float,
        tick_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        from app.core.config import log, _short_text
        from app.core.pipeline import record_action_outcome, record_auto_reboot_decision
        from app.core.reboot_safety import (
            STATE_HASHBOARD,
            STATE_LOW,
            STATE_OFFLINE,
            STATE_OK,
            classify_auto_reboot_signal,
            evaluate_auto_reboot_interlocks,
        )
        from app.core.restart_intelligence import (
            _async_execute_mining_restart,
            _async_execute_preset_restart,
            evaluate_auto_restart_candidate,
            evaluate_preset_restart_candidate,
        )
        from app.core.system import run_hashcore_cli
        from app.telegram.fleet_cards import display_name
        from app.telegram.sender import send_telegram

        miner_results = tick_data.get("miner_results", {})
        startup_grace_active = tick_data.get("startup_grace_active", False)
        process_start_ts = tick_data.get("process_start_ts", now_ts)
        previous_signals = tick_data.get("previous_signals", {})
        config = context.config
        state_lock = context.state_lock
        event_store = context.event_store
        bot_token = context.bot_token
        chat_id = context.chat_id
        qa_mode = context.qa_mode
        qa_allow_actions = context.qa_allow_actions
        qa_notify = context.qa_notify

        threshold_ths = context.threshold_ths
        expected_boards = int(config.get("expected_boards", 3))
        auto_restart_mining_enabled = bool(config.get("auto_restart_mining_enabled", True))
        auto_restart_min_elapsed_seconds = int(config.get("auto_restart_min_elapsed_seconds", 120))
        auto_restart_cooldown_seconds = int(config.get("auto_restart_cooldown_seconds", 300))
        auto_restart_max_retries = int(config.get("auto_restart_max_retries_before_reboot", 3))
        safe_recovery_pre_clamp_preset = str(config.get("safe_recovery_pre_clamp_preset", "2300W"))
        vnish_api_password = str(config.get("vnish_api_password", "admin"))
        hashcore_cfg = context.hashcore_cfg or config.get("hashcore", {})

        reboots_triggered: List[str] = []

        for state_key, res in miner_results.items():
            miner = res["miner"]
            state = res["state"]
            responded = res["responded"]
            rate_ths = res["rate_ths"]
            elapsed = res["elapsed"]
            active_boards = res["active_boards"]
            vnish_telemetry = res["vnish_telemetry"]
            quality_telemetry = res["quality_telemetry"]
            name = miner["name"]
            name_display = display_name(name)
            host = miner["host"]

            is_hash_degraded = (
                state.state in (STATE_LOW, STATE_HASHBOARD)
                or (rate_ths is not None and rate_ths <= 0.0)
                or (active_boards is not None and active_boards == 0)
            )

            # 1. Preset Watchdog (Spec 081 / PROP-017)
            if not is_hash_degraded:
                if getattr(state, "vnish_restart_required", False) and responded and auto_restart_mining_enabled:
                    miner_is_warming = (elapsed is not None and elapsed < auto_restart_min_elapsed_seconds) or startup_grace_active
                    curr_chip_t = (
                        vnish_telemetry.max_temp_c
                        if vnish_telemetry and vnish_telemetry.max_temp_c is not None
                        else getattr(state, "governor_last_temp_c", None)
                    )
                    t_pause = (
                        getattr(state, "thermal_pause_until_ts", None) is not None
                        and now_ts < state.thermal_pause_until_ts
                    )
                    is_preset_cand, preset_reason = evaluate_preset_restart_candidate(
                        now_ts=now_ts,
                        vnish_restart_required=True,
                        is_hash_degraded=False,
                        is_warming_up=miner_is_warming,
                        max_chip_temp_c=curr_chip_t,
                        detected_ts=getattr(state, "vnish_restart_detected_ts", None),
                        last_restart_ts=getattr(state, "last_preset_restart_ts", None),
                        soak_window_seconds=float(config.get("preset_restart_soak_seconds", 300.0)),
                        cooldown_seconds=float(config.get("preset_restart_cooldown_seconds", 180.0)),
                        max_safe_temp_c=float(config.get("preset_restart_max_temp_c", 80.0)),
                        thermal_pause_active=t_pause,
                    )
                    if is_preset_cand:
                        if qa_mode and not qa_allow_actions:
                            log(f"[PRESET-WATCHDOG] blocked_by=qa miner={name_display} reason={preset_reason}")
                        else:
                            with state_lock:
                                state.last_preset_restart_ts = now_ts
                            target_p_str = getattr(state, "balancer_preset", "2300W") or "2300W"
                            threading.Thread(
                                target=_async_execute_preset_restart,
                                args=(
                                    host,
                                    vnish_api_password,
                                    name,
                                    miner,
                                    target_p_str,
                                    bot_token,
                                    chat_id,
                                    qa_mode,
                                    qa_notify,
                                    event_store,
                                ),
                                daemon=True,
                                name=f"PresetRestart_{name}",
                            ).start()

            # 2. Level 1: Soft Auto-Restart (Vnish API)
            if auto_restart_mining_enabled and responded:
                is_restart_cand, restart_reason, restart_cd = evaluate_auto_restart_candidate(
                    now_ts=now_ts,
                    responded=responded,
                    rate_ths=rate_ths,
                    threshold_ths=threshold_ths,
                    active_boards=active_boards,
                    expected_boards=expected_boards,
                    miner_state="mining" if responded else "stopped",
                    restart_required=getattr(state, "vnish_restart_required", False),
                    reboot_required=False,
                    auto_restart_enabled=auto_restart_mining_enabled,
                    last_auto_restart_ts=state.last_auto_restart_ts,
                    auto_restart_cooldown_seconds=auto_restart_cooldown_seconds,
                    auto_restart_count=state.auto_restart_count,
                    max_retries_before_reboot=auto_restart_max_retries,
                    in_maintenance=getattr(state, "is_shutdown_maintenance", False),
                    is_snoozed=(state.snooze_until_ts is not None and now_ts < state.snooze_until_ts),
                    elapsed=elapsed,
                    min_elapsed_seconds=auto_restart_min_elapsed_seconds,
                    startup_grace_active=startup_grace_active,
                )
                if is_restart_cand:
                    if qa_mode and not qa_allow_actions:
                        log(f"[AUTO-RESTART] blocked_by=qa miner={name_display} reason={restart_reason}")
                    else:
                        with state_lock:
                            state.last_auto_restart_ts = now_ts
                            state.auto_restart_count += 1
                        threading.Thread(
                            target=_async_execute_mining_restart,
                            args=(
                                host,
                                vnish_api_password,
                                name,
                                miner,
                                restart_reason,
                                state.auto_restart_count,
                                auto_restart_max_retries,
                                bot_token,
                                chat_id,
                                qa_mode,
                                qa_notify,
                                event_store,
                                safe_recovery_pre_clamp_preset,
                            ),
                            daemon=True,
                            name=f"AutoRestart_{name}",
                        ).start()

            # 3. Level 2: Auto-Reboot (Hashcore CLI)
            curr_signal = classify_auto_reboot_signal(responded, rate_ths, threshold_ths)
            interlock_decision = evaluate_auto_reboot_interlocks(
                current_miner_key=state_key,
                current_signal=curr_signal,
                previous_signals=previous_signals,
                previous_signals_observed_ts=now_ts,
                evaluated_ts=now_ts,
                fleet_snapshot_max_age_seconds=float(config.get("auto_reboot_fleet_snapshot_max_age_seconds", 300.0)),
                fleet_min_affected=int(config.get("auto_reboot_fleet_guard_min_affected", 2)),
                max_temp_c=vnish_telemetry.max_temp_c if vnish_telemetry else None,
                thermal_guard_enabled=bool(config.get("auto_reboot_thermal_guard_enabled", True)),
                thermal_limit_c=float(config.get("auto_reboot_max_temp_c", 82.0)),
                fleet_guard_enabled=bool(config.get("auto_reboot_fleet_guard_enabled", True)),
                firmware_transition_guard_enabled=bool(config.get("auto_reboot_firmware_transition_guard_enabled", True)),
                chains_transitioning_count=quality_telemetry.chains_transitioning_count if quality_telemetry else 0,
            )

            decision_dict = ActuatorHook.evaluate_auto_reboot_policy(
                state=state,
                miner=miner,
                new_state=state.state,
                responded=responded,
                rate_ths=rate_ths,
                threshold_ths=threshold_ths,
                active_boards=active_boards,
                expected_boards=expected_boards,
                now_ts=now_ts,
                process_start_ts=process_start_ts,
                startup_guard_seconds=int(config.get("startup_guard_seconds", 600)),
                low_sustained_seconds=int(config.get("low_sustained_seconds", 900)),
                hashboard_sustained_seconds=int(config.get("hashboard_sustained_seconds", 600)),
                hashboard_reboot_enabled=bool(config.get("hashboard_reboot_enabled", True)),
                reboot_cooldown_seconds=int(config.get("reboot_cooldown_seconds", 1800)),
                max_reboots_per_window=int(config.get("max_reboots_per_window", 3)),
                auto_reboot_window_seconds=int(config.get("auto_reboot_window_seconds", 21600)),
                interlock_decision=interlock_decision,
                qa_mode=qa_mode,
                qa_allow_actions=qa_allow_actions,
            )

            if event_store is not None and getattr(event_store, "available", False):
                record_auto_reboot_decision(
                    event_store,
                    evaluated_ts=now_ts,
                    miner=miner,
                    state=state,
                    result=decision_dict.get("reason", "unknown"),
                    responded=responded,
                    rate_ths=rate_ths,
                    threshold_ths=threshold_ths,
                    low_elapsed_seconds=(now_ts - state.low_since_ts) if state.low_since_ts else None,
                    active_boards=active_boards,
                    expected_boards=expected_boards,
                    startup_guard_active=(now_ts - process_start_ts) < int(config.get("startup_guard_seconds", 600)),
                    qa_mode=qa_mode,
                    cooldown_remaining_seconds=None,
                    window_count=len(getattr(state, "auto_reboot_timestamps", [])),
                    window_seconds=int(config.get("auto_reboot_window_seconds", 21600)),
                    telemetry=vnish_telemetry,
                    details={"signal": decision_dict.get("signal")},
                )

            if decision_dict["allowed"]:
                ok, msg = run_hashcore_cli(hashcore_cfg, miner, "reboot", config, qa_mode, qa_allow_actions)
                record_action_outcome(
                    event_store,
                    occurred_ts=now_ts,
                    miner=miner,
                    action="reboot",
                    source="auto",
                    ok=ok,
                    message=msg,
                )
                if ok:
                    with state_lock:
                        state.last_auto_reboot_ts = now_ts
                        state.auto_reboot_timestamps.append(now_ts)
                        state.low_since_ts = None
                        state.auto_restart_count = 0
                    reboots_triggered.append(name_display)
                    log(f"[AUTO-REBOOT] {name_display} auto-reboot ejecutado con éxito vía Hashcore.")
                    if (not qa_mode) or qa_notify:
                        send_telegram(
                            bot_token,
                            str(chat_id),
                            f"🚨 *AUTO-REBOOT ENVIADO*\n\nMinero: *{name_display}*\nAcción: Reinicio eléctrico aplicado vía Hashcore.",
                            "REBOOT",
                            f"auto_reboot_{name}",
                        )

        return {
            "actuator_completed": True,
            "reboots_triggered": reboots_triggered,
        }


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


def __getattr__(name: str) -> Any:
    if name in ("AcquisitionHook", "GovernanceHook", "PostTickHook", "PreTickHook"):
        import app.core.pipeline as _p
        return getattr(_p, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
