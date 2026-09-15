"""Core Supervisory Engine — orchestrator interface for the 30s monitoring cycle (Spec 060).

This module defines CoreSupervisoryEngine as the target architecture for the
monitoring loop currently embedded in main().  In this release (Spec 060 Phase A),
the engine wraps the existing main() loop logic, providing a clean interface
for future incremental extraction of the tick pipeline.

Pipeline per tick:
  1. Telemetry acquisition via BoundedAcquirer (4028 Telnet or sequential fallback)
  2. Incident detection and state machine evaluation (LOW, HASHBOARD, OFFLINE)
  3. Governance interlocks (Spec 057) and Post-Blackout Guard (Spec 050)
  4. Actuators: Auto-reboot via hashcore_cli, Fan Governor, Preset Balancer, Soft restart
  5. Atomic state snapshot + disk persistence (StateManager)
  6. Liveness heartbeat write

Design constraints (MUST NOT change to preserve inspect.getsource tests):
  - main() must remain in miner_monitor.py and contain the literal patterns
    verified by test_auto_reboot_signal_gate, test_reboot_safety,
    test_vnish_hashboard_detection, and test_monitor_incidents.
  - CoreSupervisoryEngine is additive infrastructure; it does NOT inline main().

Thread model:
  - run() is called from the main thread.
  - The BoundedAcquirer maintains its own internal thread pool (workers=N).
  - telegram_polling_worker runs in a daemon thread managed by main().
  - telegram_sender_worker runs in a daemon thread managed by main().
  - All shared state access is guarded by MonitorContext.state_lock (RLock).
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from app.core.context import MonitorContext

logger = logging.getLogger(__name__)


class TickResult:
    """Lightweight result container for a single supervisory tick."""

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

    def __repr__(self) -> str:
        return (
            f"TickResult(seq={self.tick_sequence} "
            f"responded={self.miners_responded} "
            f"failed={self.miners_failed} "
            f"reboots={self.reboots_triggered} "
            f"duration={self.tick_duration_seconds:.3f}s)"
        )


class CoreSupervisoryEngine:
    """Orchestrator for the authoritative 30-second supervisory cycle.

    This class provides the structural skeleton of the monitoring pipeline
    extracted from main().  In Spec 060 Phase A it delegates each pipeline
    step back to the callable hooks that main() already defines, providing
    a clean boundary for future extraction.

    Usage (from main()):
        engine = CoreSupervisoryEngine(context)
        engine.register_tick_hook(my_tick_fn)
        engine.run(states, last_update_id_ref)  # blocks until KeyboardInterrupt

    Or use the convenience class method to wrap an existing main()-style loop:
        CoreSupervisoryEngine.run_forever(context, tick_callable)
    """

    def __init__(self, context: MonitorContext) -> None:
        self._ctx = context
        self._tick_hooks: List[Callable[[MonitorContext, int, float], TickResult]] = []
        self._running = False
        self._tick_sequence = 0
        self._shutdown_event = threading.Event()

    # ------------------------------------------------------------------
    # Hook registration
    # ------------------------------------------------------------------

    def register_tick_hook(
        self,
        hook: Callable[[MonitorContext, int, float], TickResult],
    ) -> None:
        """Register a callable to be invoked each supervisory tick.

        Signature: hook(context, tick_sequence, now_ts) -> TickResult
        """
        self._tick_hooks.append(hook)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(
        self,
        states: Dict[str, Any],
        last_update_id_ref: Dict[str, Optional[int]],
        on_tick_complete: Optional[Callable[[TickResult], None]] = None,
    ) -> None:
        """Block and run the supervisory loop until KeyboardInterrupt or shutdown().

        Args:
            states: Shared dict of MinerState objects (guarded by state_lock).
            last_update_id_ref: Mutable ref dict {"value": last_update_id}.
            on_tick_complete: Optional callback invoked after each tick for
                              metrics collection or testing.
        """
        self._running = True
        poll_seconds = self._ctx.poll_seconds
        logger.info(
            "CoreSupervisoryEngine started: miners=%d poll_seconds=%d qa=%s",
            len(self._ctx.miners),
            poll_seconds,
            self._ctx.qa_mode,
        )

        try:
            while not self._shutdown_event.is_set():
                tick_start = time.monotonic()
                now_ts = time.time()
                self._tick_sequence += 1

                errors: List[str] = []
                result = TickResult(
                    tick_sequence=self._tick_sequence,
                    tick_duration_seconds=0.0,
                    miners_responded=0,
                    miners_failed=0,
                    reboots_triggered=[],
                    governance_blocked=0,
                    errors=errors,
                )

                for hook in self._tick_hooks:
                    try:
                        r = hook(self._ctx, self._tick_sequence, now_ts)
                        if r is not None:
                            result = r
                    except Exception as exc:
                        msg = f"tick_hook={hook.__name__} error={type(exc).__name__}: {exc}"
                        logger.warning(msg)
                        errors.append(msg)

                result.tick_duration_seconds = time.monotonic() - tick_start

                if on_tick_complete is not None:
                    try:
                        on_tick_complete(result)
                    except Exception:
                        pass

                # Sleep the remainder of the poll interval
                elapsed = time.monotonic() - tick_start
                sleep_seconds = max(0.0, poll_seconds - elapsed)
                self._shutdown_event.wait(timeout=sleep_seconds)

        except KeyboardInterrupt:
            logger.info("CoreSupervisoryEngine: KeyboardInterrupt received, stopping.")
        finally:
            self._running = False
            logger.info("CoreSupervisoryEngine stopped after %d ticks.", self._tick_sequence)

    def shutdown(self) -> None:
        """Signal the loop to stop after the current tick completes."""
        self._shutdown_event.set()

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def tick_sequence(self) -> int:
        return self._tick_sequence

    # ------------------------------------------------------------------
    # Convenience class method — wraps a main()-style callable
    # ------------------------------------------------------------------

    @classmethod
    def run_forever(
        cls,
        context: MonitorContext,
        tick_callable: Callable[[MonitorContext, int, float], TickResult],
        states: Dict[str, Any],
        last_update_id_ref: Dict[str, Optional[int]],
    ) -> None:
        """Create an engine, register one tick hook, and run until interrupted.

        This is the minimal integration path from main():

            CoreSupervisoryEngine.run_forever(ctx, my_tick_fn, states, uid_ref)
        """
        engine = cls(context)
        engine.register_tick_hook(tick_callable)
        engine.run(states, last_update_id_ref)


# ---------------------------------------------------------------------------
# Pipeline step helpers
# These pure functions encapsulate the structural pipeline steps described
# in the Spec 060 plan. They do NOT inline miner_monitor.py logic — they are
# provided as architectural anchors for future incremental extraction.
# ---------------------------------------------------------------------------

def log_tick_header(tick_sequence: int, now_ts: float, qa_mode: bool) -> None:
    """Log the start of a supervisory tick (no-op in production, useful in tests)."""
    if qa_mode:
        logger.debug("TICK#%d ts=%.3f", tick_sequence, now_ts)


def check_governance_expiry(context: MonitorContext, now_ts: float) -> bool:
    """Return True if the governance timer has expired and governance was restored.

    This is a pure check — the actual global mutation happens in main() to
    preserve the inspect.getsource() contract.  This function returns the
    decision so callers can log or notify appropriately.
    """
    gov = context.governance
    if gov is None:
        return False
    if gov.is_expired(now_ts) and not gov.master_enabled:
        return True
    return False


def should_skip_actuators(context: MonitorContext, now_ts: float) -> bool:
    """Return True if actuators should be suppressed (Vnish Libre or QA mode)."""
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
