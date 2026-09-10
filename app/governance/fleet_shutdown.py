"""Fleet Shutdown and Thermal Purge Orchestrator (Spec 048).

Provides pure formatting, selection helpers, and concurrent execution routines
for graceful ASIC shutdown, active thermal cooldown, and electrical maintenance mode.
All UI text functions strictly enforce the mobile line-length limit (<= 32 visible cols).
"""

from __future__ import annotations

import concurrent.futures
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.telegram.help_center import visible_line_width, wrap_mobile_lines
from app.vnish.client import safe_resume_mining, safe_set_fan_duty, safe_stop_mining

DEFAULT_PURGE_SECONDS = 45
DEFAULT_MAINTENANCE_SNOOZE_HOURS = 4.0
DEFAULT_PURGE_FAN_DUTY = 100
DEFAULT_IDLE_FAN_DUTY = 40


@dataclass(frozen=True)
class ShutdownTarget:
    """Target miner descriptor for shutdown/resume operations."""
    miner_id: str
    name: str
    host: str
    port: int = 4028


@dataclass(frozen=True)
class OperationResult:
    """Outcome of a stop or resume action on an individual miner."""
    miner_id: str
    success: bool
    error: Optional[str] = None


# ── Bitmask Selection Helpers ──────────────────────────────────────────

def make_empty_bitmask(total: int) -> str:
    """Generate all-zeros bitmask string for the given total count."""
    return "0" * max(0, total)


def make_full_bitmask(total: int) -> str:
    """Generate all-ones bitmask string for the given total count."""
    return "1" * max(0, total)


def toggle_selection_bitmask(bitmask: str, index: int) -> str:
    """Toggle the bit at the given 0-indexed position."""
    if not bitmask or index < 0 or index >= len(bitmask):
        return bitmask
    chars = list(bitmask)
    chars[index] = "1" if chars[index] == "0" else "0"
    return "".join(chars)


def parse_selection_indices(bitmask: str) -> List[int]:
    """Return 0-based indices of all '1' bits in bitmask."""
    return [i for i, c in enumerate(bitmask) if c == "1"]


def resolve_selected_miners(
    bitmask: str,
    miners: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Return miner dicts corresponding to '1' bits in the bitmask."""
    indices = parse_selection_indices(bitmask)
    return [miners[i] for i in indices if i < len(miners)]


def extract_miner_identifier(miner: Dict[str, Any]) -> str:
    """Extract human-readable short identifier (e.g. '23' from 'S19JPRO-23')."""
    name = str(miner.get("name") or miner.get("host") or "")
    if "-" in name:
        parts = name.split("-")
        return parts[-1]
    return name


# ── Concurrent Dispatchers ─────────────────────────────────────────────

def execute_parallel_shutdown(
    miners: List[Dict[str, Any]],
    password: str,
    timeout: float = 3.0,
    stop_fn: Optional[Callable[..., Tuple[bool, Optional[str]]]] = None,
) -> Dict[str, OperationResult]:
    """
    Dispatch POST /api/v1/mining/stop across selected miners in parallel.
    Uses ThreadPoolExecutor bounded to the number of targets (max 4).
    """
    caller = stop_fn or safe_stop_mining
    results: Dict[str, OperationResult] = {}
    if not miners:
        return results

    def _call(m: Dict[str, Any]) -> Tuple[str, bool, Optional[str]]:
        m_id = extract_miner_identifier(m)
        host = m.get("host", "")
        ok, err = caller(host, password, timeout=timeout)
        return m_id, ok, err

    max_w = min(4, len(miners))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_w) as pool:
        futures = [pool.submit(_call, m) for m in miners]
        for f in concurrent.futures.as_completed(futures):
            try:
                m_id, ok, err = f.result()
                results[m_id] = OperationResult(miner_id=m_id, success=ok, error=err)
            except Exception as exc:
                # Handle unexpected executor failures safely
                m_id = "unknown"
                results[m_id] = OperationResult(miner_id=m_id, success=False, error=str(exc))

    return results


def execute_parallel_resume(
    miners: List[Dict[str, Any]],
    password: str,
    timeout: float = 3.0,
    resume_fn: Optional[Callable[..., Tuple[bool, Optional[str]]]] = None,
) -> Dict[str, OperationResult]:
    """
    Dispatch POST /api/v1/mining/resume across selected miners in parallel.
    Uses ThreadPoolExecutor bounded to the number of targets (max 4).
    """
    caller = resume_fn or safe_resume_mining
    results: Dict[str, OperationResult] = {}
    if not miners:
        return results

    def _call(m: Dict[str, Any]) -> Tuple[str, bool, Optional[str]]:
        m_id = extract_miner_identifier(m)
        host = m.get("host", "")
        ok, err = caller(host, password, timeout=timeout)
        return m_id, ok, err

    max_w = min(4, len(miners))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_w) as pool:
        futures = [pool.submit(_call, m) for m in miners]
        for f in concurrent.futures.as_completed(futures):
            try:
                m_id, ok, err = f.result()
                results[m_id] = OperationResult(miner_id=m_id, success=ok, error=err)
            except Exception as exc:
                m_id = "unknown"
                results[m_id] = OperationResult(miner_id=m_id, success=False, error=str(exc))

    return results


def execute_parallel_fan_duty(
    miners: List[Dict[str, Any]],
    duty_percent: int,
    password: str,
    timeout: float = 2.5,
    fan_fn: Optional[Callable[..., Tuple[bool, Optional[str]]]] = None,
) -> Dict[str, OperationResult]:
    """
    Dispatch fan duty setting across selected miners in parallel (Spec 049).
    Uses ThreadPoolExecutor bounded to the number of targets (max 4).
    """
    caller = fan_fn or safe_set_fan_duty
    results: Dict[str, OperationResult] = {}
    if not miners:
        return results

    def _call(m: Dict[str, Any]) -> Tuple[str, bool, Optional[str]]:
        m_id = extract_miner_identifier(m)
        host = m.get("host", "")
        ok, err = caller(host, password, duty_percent, timeout=timeout)
        return m_id, ok, err

    max_w = min(4, len(miners))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_w) as pool:
        futures = [pool.submit(_call, m) for m in miners]
        for f in concurrent.futures.as_completed(futures):
            try:
                m_id, ok, err = f.result()
                results[m_id] = OperationResult(miner_id=m_id, success=ok, error=err)
            except Exception as exc:
                m_id = "unknown"
                results[m_id] = OperationResult(miner_id=m_id, success=False, error=str(exc))

    return results


# ── Mobile-First Card Layouts (<= 32 visible cols) ─────────────────────

def render_shutdown_in_progress(
    targets: List[str],
    purge_seconds: int = DEFAULT_PURGE_SECONDS,
    purge_duty: int = DEFAULT_PURGE_FAN_DUTY,
) -> str:
    """Render in-progress notification card during active thermal purge (Spec 049)."""
    lines = [
        "🛑 *PARADA EN PROGRESO*",
        "─" * 32,
        "• *Carga Hash*: Desactivada (0W)",
        f"• *Equipos*: {', '.join(targets)}",
        f"• *Purga*: Rampa {purge_duty}% activa",
        f"⏳ Barriendo calor ({purge_seconds}s)",
        "",
        "⚠️ *ATENCIÓN*:",
        "NO cortar la corriente aún.",
        "Coolers forzados expulsando",
        "el calor residual de chips.",
        "─" * 32,
    ]
    return "\n".join(lines)


def render_safe_area_card(
    targets: List[str],
    snooze_hours: float = DEFAULT_MAINTENANCE_SNOOZE_HOURS,
    idle_duty: int = DEFAULT_IDLE_FAN_DUTY,
) -> str:
    """Render confirmation that thermal purge is complete and AC cut is safe (Spec 049)."""
    lines = [
        "✅ *ÁREA ELÉCTRICA SEGURA*",
        "─" * 32,
        "• *Equipos Detenidos*:",
    ]
    for t in targets:
        lines.append(f"  └ S19JPRO-{t}")
    lines.extend([
        "• *Potencia Hash*: 0.0 kW",
        "• *Reposo*: <25W por equipo",
        f"• *Coolers*: Reposo ({idle_duty}% PWM)",
        "• *Disipadores*: Fríos (<35°C)",
        f"• *Snooze*: Activo ({snooze_hours:.0f}h)",
        "",
        "🔌 *Ya podés bajar la térmica*",
        "o desenchufar sin arcos ni",
        "estrés en componentes.",
        "─" * 32,
        "Usá /resume al dar corriente.",
    ])
    return "\n".join(lines)


def render_resume_success_card(targets: List[str]) -> str:
    """Render confirmation card when miners have resumed mining."""
    lines = [
        "▶️ *MINADO REANUDADO*",
        "─" * 32,
        "• *Equipos Reactivados*:",
    ]
    for t in targets:
        lines.append(f"  └ S19JPRO-{t}")
    lines.extend([
        "• *Rieles DC*: Encendidos (12V)",
        "• *Autotuning*: Inicializando...",
        "• *Snooze*: Removido",
        "",
        "🟢 Supervisión normal activa.",
        "─" * 32,
    ])
    return "\n".join(lines)


def render_shutdown_error_card(errors: Dict[str, str]) -> str:
    """Render card detailing any errors encountered during shutdown/resume."""
    lines = [
        "⚠️ *ALERTA EN MANIOBRA*",
        "─" * 32,
        "No se pudo completar la orden",
        "en los siguientes mineros:",
    ]
    for m_id, err in errors.items():
        for w in wrap_mobile_lines(f"{m_id}: {err}", width=28, indent="  ", first_indent="• "):
            lines.append(w)
    lines.extend([
        "",
        "Verificá conectividad de red.",
        "─" * 32,
    ])
    return "\n".join(lines)

