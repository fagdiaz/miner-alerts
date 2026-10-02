"""
app/governance/_orchestrator_state.py
Spec 085 — Extracción del Orquestador de Gobernanza (PROP-021)

Módulo de estado compartido para los ciclos de gobernanza.
Centraliza los globals mutables que antes vivían directamente en miner_monitor.py,
eliminando el acoplamiento directo entre los handlers de Telegram y el monolito.

Diseño:
- Sin dependencias en miner_monitor.py (evita importaciones circulares).
- Thread-safe: accessors usando threading.Lock para todas las escrituras.
- Los handlers de Telegram (fans.py, interventions.py) importan de aquí en vez de
  acceder directamente a mm._GOVERNOR_RUNTIME_ENABLED etc.
- execute_governor_cycle() y execute_balancer_cycle() también leen de aquí.
"""
from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.governance.intervention_policy import InterventionGovernance

# ── Lock de acceso ────────────────────────────────────────────────────────────
_STATE_LOCK = threading.Lock()

# ── Fan Governor runtime override ─────────────────────────────────────────────
# None = usar valor de config; True/False = override manual (persiste hasta restart)
# Equivale al anterior _GOVERNOR_RUNTIME_ENABLED en miner_monitor.py
_governor_enabled: Optional[bool] = None

# ── Dynamic Preset Balancer runtime override ──────────────────────────────────
# None = usar valor de config; True/False = override manual (persiste hasta restart)
# Equivale al anterior _BALANCER_RUNTIME_ENABLED en miner_monitor.py
_balancer_enabled: Optional[bool] = None

# ── Timestamps de último ciclo ────────────────────────────────────────────────
_last_vnish_sync_ts: float = 0.0
_last_balancer_cycle_ts: float = 0.0

# ── InterventionGovernance singleton ─────────────────────────────────────────
# Inicializado con lazy import para evitar circularidades en el import time.
_intervention_gov: Optional["InterventionGovernance"] = None
_intervention_gov_lock = threading.Lock()


# ─────────────────────────────────────────────────────────────────────────────
# Fan Governor accessors
# ─────────────────────────────────────────────────────────────────────────────


def get_governor_enabled() -> Optional[bool]:
    """Retorna el override runtime del Fan Governor (None = usar config)."""
    with _STATE_LOCK:
        return _governor_enabled


def set_governor_enabled(val: Optional[bool]) -> None:
    """Establece el override runtime del Fan Governor. Thread-safe."""
    global _governor_enabled
    with _STATE_LOCK:
        _governor_enabled = val


# ─────────────────────────────────────────────────────────────────────────────
# Balancer accessors
# ─────────────────────────────────────────────────────────────────────────────


def get_balancer_enabled() -> Optional[bool]:
    """Retorna el override runtime del Balancer (None = usar config)."""
    with _STATE_LOCK:
        return _balancer_enabled


def set_balancer_enabled(val: Optional[bool]) -> None:
    """Establece el override runtime del Balancer. Thread-safe."""
    global _balancer_enabled
    with _STATE_LOCK:
        _balancer_enabled = val


# ─────────────────────────────────────────────────────────────────────────────
# Vnish sync timestamp accessors
# ─────────────────────────────────────────────────────────────────────────────


def get_last_vnish_sync_ts() -> float:
    """Retorna el timestamp del último sync de settings VNish."""
    with _STATE_LOCK:
        return _last_vnish_sync_ts


def set_last_vnish_sync_ts(ts: float) -> None:
    """Actualiza el timestamp del último sync de settings VNish. Thread-safe."""
    global _last_vnish_sync_ts
    with _STATE_LOCK:
        _last_vnish_sync_ts = ts


# ─────────────────────────────────────────────────────────────────────────────
# Balancer cycle timestamp accessors
# ─────────────────────────────────────────────────────────────────────────────


def get_last_balancer_cycle_ts() -> float:
    """Retorna el timestamp del último ciclo del Balancer."""
    with _STATE_LOCK:
        return _last_balancer_cycle_ts


def set_last_balancer_cycle_ts(ts: float) -> None:
    """Actualiza el timestamp del último ciclo del Balancer. Thread-safe."""
    global _last_balancer_cycle_ts
    with _STATE_LOCK:
        _last_balancer_cycle_ts = ts


# ─────────────────────────────────────────────────────────────────────────────
# InterventionGovernance singleton accessor
# ─────────────────────────────────────────────────────────────────────────────


def get_intervention_gov() -> "InterventionGovernance":
    """
    Retorna el singleton InterventionGovernance compartido.
    Lazy-initialized para evitar circularidades en import time.
    Thread-safe: usa un lock dedicado para la inicialización.
    """
    global _intervention_gov
    if _intervention_gov is None:
        with _intervention_gov_lock:
            if _intervention_gov is None:
                from app.governance.intervention_policy import InterventionGovernance
                _intervention_gov = InterventionGovernance()
    return _intervention_gov


def set_intervention_gov(gov: "InterventionGovernance") -> None:
    """
    Reemplaza el singleton InterventionGovernance.
    Usado por miner_monitor.py para inyectar el singleton ya existente
    en _GLOBAL_INTERVENTION_GOV y mantener continuidad de estado.
    Thread-safe.
    """
    global _intervention_gov
    with _intervention_gov_lock:
        _intervention_gov = gov
