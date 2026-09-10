"""Scheduled Electrical Maintenance Windows & Soft Pre-Ramp Planner (Spec 052).

Provides programmatic scheduling of electrical maintenance windows (/schedule_maintenance)
with automated progressive pre-ramp power step-downs at T-10m and T-5m, followed by
safe zero-load shutdown, active thermal purge, and automatic maintenance snooze at T-0.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
import math
import re
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple
import uuid

from app.governance.fleet_shutdown import (
    DEFAULT_PURGE_FAN_DUTY,
    execute_parallel_fan_duty,
    execute_parallel_shutdown,
    render_safe_area_card,
)
from app.telegram.help_center import visible_line_width, wrap_mobile_lines
from app.vnish.client import safe_set_miner_preset


class ScheduledStage(str, Enum):
    """Stages of a scheduled maintenance window."""
    PENDING = "pending"
    PRE_RAMP_TIER_1 = "pre_ramp_t1"   # T-10m: 2300W
    PRE_RAMP_TIER_2 = "pre_ramp_t2"   # T-5m: 2100W
    EXECUTED = "executed"             # T-0: shutdown + purge ramp + snooze
    CANCELLED = "cancelled"
    COMPLETED = "completed"


@dataclass
class ScheduledWindow:
    """Represents a scheduled electrical maintenance window."""
    window_id: str
    start_ts: float
    duration_seconds: float
    created_ts: float
    created_by: str = ""
    stage: ScheduledStage = ScheduledStage.PENDING
    stage_updated_ts: float = 0.0

    @property
    def end_ts(self) -> float:
        return self.start_ts + self.duration_seconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "window_id": self.window_id,
            "start_ts": self.start_ts,
            "duration_seconds": self.duration_seconds,
            "created_ts": self.created_ts,
            "created_by": self.created_by,
            "stage": self.stage.value if isinstance(self.stage, ScheduledStage) else str(self.stage),
            "stage_updated_ts": self.stage_updated_ts,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ScheduledWindow:
        stage_val = data.get("stage", ScheduledStage.PENDING.value)
        try:
            stage_enum = ScheduledStage(stage_val)
        except ValueError:
            stage_enum = ScheduledStage.PENDING

        return cls(
            window_id=str(data.get("window_id", "")),
            start_ts=float(data.get("start_ts", 0.0)),
            duration_seconds=float(data.get("duration_seconds", 7200.0)),
            created_ts=float(data.get("created_ts", 0.0)),
            created_by=str(data.get("created_by", "")),
            stage=stage_enum,
            stage_updated_ts=float(data.get("stage_updated_ts", 0.0)),
        )


def argentina_now(ts: Optional[float] = None) -> datetime:
    """Returns local Argentina datetime (UTC-3)."""
    base_ts = time.time() if ts is None else float(ts)
    utc_dt = datetime.fromtimestamp(base_ts, tz=timezone.utc).replace(tzinfo=None)
    return utc_dt + timedelta(hours=-3)


def parse_duration_seconds(expr: str) -> Optional[float]:
    """Parses duration string like '2h', '30m', '1h30m', '90m' into seconds."""
    clean = expr.strip().lower()
    if not clean:
        return None

    # Matches combos like 1h30m or single units like 2h, 45m
    pattern = r"^(?:(\d+(?:\.\d+)?)\s*h(?:ours?)?)?\s*(?:(\d+)\s*m(?:in(?:utes?)?)?)?$"
    m = re.match(pattern, clean)
    if not m:
        return None

    hours_part, mins_part = m.groups()
    if not hours_part and not mins_part:
        return None

    total_sec = 0.0
    if hours_part:
        total_sec += float(hours_part) * 3600.0
    if mins_part:
        total_sec += float(mins_part) * 60.0

    return total_sec


def parse_schedule_expression(
    time_expr: str,
    duration_expr: Optional[str] = None,
    now_ts: Optional[float] = None,
    user_id: str = "",
) -> Tuple[bool, Optional[ScheduledWindow], Optional[str]]:
    """
    Parses natural schedule expressions.
    Supports relative ('in 30m', 'in 2h', '+45m') and absolute ('YYYY-MM-DD HH:MM', 'HH:MM').
    Returns (success, window, error_message).
    """
    cur_ts = time.time() if now_ts is None else float(now_ts)
    cur_ar = argentina_now(cur_ts)

    # 1. Parse duration
    dur_sec = 7200.0  # Default 2h
    if duration_expr and duration_expr.strip():
        parsed_dur = parse_duration_seconds(duration_expr.strip())
        if parsed_dur is None:
            return False, None, f"Formato de duración inválido: '{duration_expr}'. Use ej: '2h', '30m'."
        dur_sec = parsed_dur

    if dur_sec < 900.0 or dur_sec > 86400.0:
        return False, None, "La duración debe ser entre 15 minutos y 24 horas."

    # 2. Parse time expression
    clean_t = time_expr.strip().lower()
    start_ts: Optional[float] = None

    # Relative syntax: 'in 30m', 'in 2h', '+30m', '45m'
    rel_match = re.match(r"^(?:in|\+)?\s*(\d+(?:\.\d+)?)\s*(m|min|h|hs|hours?)$", clean_t)
    if rel_match:
        val_str, unit = rel_match.groups()
        val = float(val_str)
        if unit.startswith("h"):
            delta_sec = val * 3600.0
        else:
            delta_sec = val * 60.0
        start_ts = cur_ts + delta_sec

    # Absolute syntax: 'YYYY-MM-DD HH:MM' or 'DD/MM/YYYY HH:MM'
    if start_ts is None:
        for fmt in ("%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M", "%Y-%m-%dT%H:%M"):
            try:
                parsed_dt = datetime.strptime(time_expr.strip(), fmt)
                # Convert from Argentina local time (UTC-3) to unix epoch
                utc_equiv = parsed_dt + timedelta(hours=3)
                start_ts = utc_equiv.replace(tzinfo=timezone.utc).timestamp()
                break
            except ValueError:
                continue

    # Absolute syntax: 'HH:MM' (today or tomorrow)
    if start_ts is None:
        time_match = re.match(r"^(\d{1,2}):(\d{2})$", clean_t)
        if time_match:
            h, mn = int(time_match.group(1)), int(time_match.group(2))
            if 0 <= h <= 23 and 0 <= mn <= 59:
                target_ar = cur_ar.replace(hour=h, minute=mn, second=0, microsecond=0)
                target_utc = target_ar + timedelta(hours=3)
                candidate_ts = target_utc.replace(tzinfo=timezone.utc).timestamp()
                # If target is less than 5 minutes in future, assume tomorrow
                if candidate_ts < cur_ts + 300.0:
                    target_ar += timedelta(days=1)
                    target_utc = target_ar + timedelta(hours=3)
                    candidate_ts = target_utc.replace(tzinfo=timezone.utc).timestamp()
                start_ts = candidate_ts

    if start_ts is None:
        return False, None, (
            f"No se pudo interpretar el horario '{time_expr}'. "
            f"Use 'in 30m', 'in 2h', '14:30' o 'YYYY-MM-DD HH:MM'."
        )

    # 3. Minimum future window validation (>= 5 minutes from now)
    if start_ts < cur_ts + 295.0:
        return False, None, "El inicio debe ser al menos 5 minutos en el futuro para permitir la pre-rampa."

    # Maximum scheduling limit: 30 days
    if start_ts > cur_ts + 30 * 86400.0:
        return False, None, "No se pueden programar mantenimientos a más de 30 días."

    w_id = f"win_{int(cur_ts)}_{uuid.uuid4().hex[:6]}"
    window = ScheduledWindow(
        window_id=w_id,
        start_ts=start_ts,
        duration_seconds=dur_sec,
        created_ts=cur_ts,
        created_by=user_id,
        stage=ScheduledStage.PENDING,
        stage_updated_ts=cur_ts,
    )
    return True, window, None


def evaluate_window_stage(window: ScheduledWindow, now_ts: float) -> Tuple[ScheduledStage, Optional[str]]:
    """
    Evaluates progression of a scheduled maintenance window based on current clock.
    Transitions:
    - now_ts >= end_ts -> COMPLETED
    - now_ts >= start_ts -> EXECUTED (T-0)
    - now_ts >= start_ts - 300 (T-5m) -> PRE_RAMP_TIER_2 (2100W)
    - now_ts >= start_ts - 600 (T-10m) -> PRE_RAMP_TIER_1 (2300W)
    - otherwise -> PENDING
    """
    if window.stage in (ScheduledStage.CANCELLED, ScheduledStage.COMPLETED):
        return window.stage, None

    if now_ts >= window.end_ts:
        return ScheduledStage.COMPLETED, "Ventana de mantenimiento finalizada."

    if now_ts >= window.start_ts:
        return ScheduledStage.EXECUTED, "T-0 alcanzado: ejecutando parada segura y purga térmica."

    if now_ts >= window.start_ts - 300.0:
        if window.stage != ScheduledStage.PRE_RAMP_TIER_2:
            return ScheduledStage.PRE_RAMP_TIER_2, "T-5m alcanzado: pre-rampa Tier 2 a 2100W."
        return window.stage, None

    if now_ts >= window.start_ts - 600.0:
        if window.stage == ScheduledStage.PENDING:
            return ScheduledStage.PRE_RAMP_TIER_1, "T-10m alcanzado: pre-rampa Tier 1 a 2300W."
        return window.stage, None

    return ScheduledStage.PENDING, None


def format_remaining_short(seconds: float) -> str:
    """Formats remaining seconds into short human string (e.g. '45m', '2h 10m')."""
    sec = max(0, int(seconds))
    if sec < 60:
        return f"{sec}s"
    mins = sec // 60
    if mins < 60:
        return f"{mins}m"
    hours = mins // 60
    rem_mins = mins % 60
    if rem_mins == 0:
        return f"{hours}h"
    return f"{hours}h {rem_mins}m"


def render_schedule_confirmation_card(window: ScheduledWindow) -> Tuple[str, Dict[str, Any]]:
    """
    Renders confirmation card when a maintenance window is scheduled.
    Strictly guarantees visible_line_width <= 32 on 100% of lines (RFC C1-C10).
    """
    st_dt = argentina_now(window.start_ts)
    end_dt = argentina_now(window.end_ts)
    dur_str = format_remaining_short(window.duration_seconds)
    rem_str = format_remaining_short(window.start_ts - time.time())

    raw_lines = [
        "📅 *MANTENIMIENTO PROGRAMADO*",
        "─" * 32,
        f"Inicio: {st_dt.strftime('%d/%m/%Y %H:%M')}",
        f"Faltan: {rem_str}",
        f"Duración: {dur_str}",
        f"Fin:    {end_dt.strftime('%H:%M')} ART",
        "─" * 32,
        "⚡ *Pre-rampa suave activa*:",
        "• T-10m: Desescalado a 2300W",
        "• T-5m:  Desescalado a 2100W",
        "• T-0:   Parada y purga 100%",
        "─" * 32,
        "Tocá el botón para cancelar:",
    ]

    final_lines: List[str] = []
    for line in raw_lines:
        if visible_line_width(line) <= 32:
            final_lines.append(line)
        else:
            final_lines.extend(wrap_mobile_lines(line, width=32))

    keyboard = [
        [{"text": "❌ Cancelar Ventana", "callback_data": f"sch:cancel:{window.window_id}"}]
    ]
    return "\n".join(final_lines), {"inline_keyboard": keyboard}


def render_scheduled_status_card(
    window: Optional[ScheduledWindow],
    now_ts: Optional[float] = None,
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    Renders status card for /scheduled query.
    Strictly guarantees visible_line_width <= 32 on 100% of lines (RFC C1-C10).
    """
    cur_ts = time.time() if now_ts is None else float(now_ts)

    if window is None or window.stage in (ScheduledStage.CANCELLED, ScheduledStage.COMPLETED):
        raw_lines = [
            "📅 *VENTANA DE MANTENIMIENTO*",
            "─" * 32,
            "No hay ventanas activas",
            "programadas en este momento.",
            "─" * 32,
            "Programar con:",
            "/schedule_maintenance <t> [dur]",
            "Ej: /schedule_maintenance in 1h 2h",
        ]
        final_lines = []
        for line in raw_lines:
            if visible_line_width(line) <= 32:
                final_lines.append(line)
            else:
                final_lines.extend(wrap_mobile_lines(line, width=32))
        return "\n".join(final_lines), None

    st_dt = argentina_now(window.start_ts)
    dur_str = format_remaining_short(window.duration_seconds)

    stage_desc = "⏳ Programada"
    if window.stage == ScheduledStage.PRE_RAMP_TIER_1:
        stage_desc = "⚡ Pre-rampa T1 (2300W)"
    elif window.stage == ScheduledStage.PRE_RAMP_TIER_2:
        stage_desc = "⚡ Pre-rampa T2 (2100W)"
    elif window.stage == ScheduledStage.EXECUTED:
        stage_desc = "🛑 En mantenimiento"

    rem_time = window.start_ts - cur_ts
    rem_label = f"Faltan: {format_remaining_short(rem_time)}" if rem_time > 0 else "Estado: En curso"

    raw_lines = [
        "📅 *VENTANA DE MANTENIMIENTO*",
        "─" * 32,
        f"Etapa: {stage_desc}",
        f"Inicio: {st_dt.strftime('%d/%m/%Y %H:%M')}",
        rem_label,
        f"Duración: {dur_str}",
        "─" * 32,
    ]

    if window.stage != ScheduledStage.EXECUTED:
        raw_lines.append("Pre-rampa programada activa.")
    else:
        raw_lines.append("Flota detenida con snooze.")

    final_lines = []
    for line in raw_lines:
        if visible_line_width(line) <= 32:
            final_lines.append(line)
        else:
            final_lines.extend(wrap_mobile_lines(line, width=32))

    keyboard = [
        [{"text": "❌ Cancelar Ventana", "callback_data": f"sch:cancel:{window.window_id}"}]
    ]
    return "\n".join(final_lines), {"inline_keyboard": keyboard}


def render_pre_ramp_card(tier: int, target_w: int, mins_to_stop: int) -> str:
    """
    Renders Telegram alert when a pre-ramp stage triggers.
    Strictly guarantees visible_line_width <= 32 on 100% of lines (RFC C1-C10).
    """
    raw_lines = [
        "⚡ *PRE-RAMPA DE DESCARGA*",
        "─" * 32,
        f"Etapa: Tier {tier} ({mins_to_stop}m a T-0)",
        f"Target potencia: *{target_w}W*",
        "─" * 32,
        "Descargando transformadores",
        "antes de la parada programada.",
    ]
    final_lines = []
    for line in raw_lines:
        if visible_line_width(line) <= 32:
            final_lines.append(line)
        else:
            final_lines.extend(wrap_mobile_lines(line, width=32))
    return "\n".join(final_lines)


def render_schedule_cancelled_card() -> str:
    """
    Renders confirmation card when a window is cancelled.
    Strictly guarantees visible_line_width <= 32 on 100% of lines.
    """
    raw_lines = [
        "❌ *VENTANA CANCELADA*",
        "─" * 32,
        "La ventana de mantenimiento fue",
        "anulada exitosamente.",
        "Flota continúa en operación.",
    ]
    final_lines = []
    for line in raw_lines:
        if visible_line_width(line) <= 32:
            final_lines.append(line)
        else:
            final_lines.extend(wrap_mobile_lines(line, width=32))
    return "\n".join(final_lines)


def process_maintenance_scheduler_cycle(
    window: Optional[ScheduledWindow],
    miners: Sequence[Dict[str, Any]],
    states: Dict[str, Any],
    config: Dict[str, Any],
    now_ts: float,
    send_telegram_fn: Optional[Callable[..., Any]] = None,
    record_event_fn: Optional[Callable[..., Any]] = None,
    log_fn: Optional[Callable[[str], None]] = None,
    save_state_fn: Optional[Callable[..., Any]] = None,
    state_path: Optional[Any] = None,
    current_last_update_id: Optional[int] = None,
    bot_token: Optional[str] = None,
    chat_id: Optional[str] = None,
    qa_mode: bool = False,
    qa_notify: bool = False,
    preset_fn: Optional[Callable[..., Any]] = None,
    shutdown_fn: Optional[Callable[..., Any]] = None,
    fan_fn: Optional[Callable[..., Any]] = None,
) -> Optional[ScheduledWindow]:
    """
    Periodically evaluates active scheduled maintenance window and triggers pre-ramp or shutdown.
    """
    if window is None or window.stage in (ScheduledStage.CANCELLED, ScheduledStage.COMPLETED):
        return window

    new_stage, reason = evaluate_window_stage(window, now_ts)
    if new_stage == window.stage:
        return window

    pw = str(config.get("vnish_api_password", "admin"))
    p_fn = preset_fn or safe_set_miner_preset
    s_fn = shutdown_fn or execute_parallel_shutdown
    f_fn = fan_fn or execute_parallel_fan_duty

    if new_stage == ScheduledStage.PRE_RAMP_TIER_1:
        window.stage = ScheduledStage.PRE_RAMP_TIER_1
        window.stage_updated_ts = now_ts
        if log_fn:
            log_fn(f"[SCHEDULER] Triggering Pre-Ramp Tier 1 (2300W): {reason}")

        # Step down to 2300W
        for m in miners:
            host = m.get("host")
            if host:
                p_fn(host, pw, "2300W", timeout=2.5)

        card = render_pre_ramp_card(1, 2300, 10)
        if send_telegram_fn and bot_token and chat_id and ((not qa_mode) or qa_notify):
            send_telegram_fn(bot_token, str(chat_id), card, "SCHEDULER", "pre_ramp_t1")

        if record_event_fn:
            record_event_fn(
                action="scheduled_pre_ramp_t1",
                source="scheduler",
                ok=True,
                message="Pre-rampa suave T-10m aplicada: presets a 2300W",
            )

    elif new_stage == ScheduledStage.PRE_RAMP_TIER_2:
        window.stage = ScheduledStage.PRE_RAMP_TIER_2
        window.stage_updated_ts = now_ts
        if log_fn:
            log_fn(f"[SCHEDULER] Triggering Pre-Ramp Tier 2 (2100W): {reason}")

        # Step down to 2100W
        for m in miners:
            host = m.get("host")
            if host:
                p_fn(host, pw, "2100W", timeout=2.5)

        card = render_pre_ramp_card(2, 2100, 5)
        if send_telegram_fn and bot_token and chat_id and ((not qa_mode) or qa_notify):
            send_telegram_fn(bot_token, str(chat_id), card, "SCHEDULER", "pre_ramp_t2")

        if record_event_fn:
            record_event_fn(
                action="scheduled_pre_ramp_t2",
                source="scheduler",
                ok=True,
                message="Pre-rampa suave T-5m aplicada: presets a 2100W",
            )

    elif new_stage == ScheduledStage.EXECUTED:
        window.stage = ScheduledStage.EXECUTED
        window.stage_updated_ts = now_ts
        if log_fn:
            log_fn(f"[SCHEDULER] Triggering T-0 Safe Shutdown: {reason}")

        # Stop mining and trigger 45s purge ramp (Spec 048 & 049)
        succ_results = s_fn(list(miners), pw)
        f_fn(list(miners), DEFAULT_PURGE_FAN_DUTY, pw)

        # Apply maintenance snooze until window.end_ts
        snooze_until = window.end_ts
        stopped_names = []
        for m in miners:
            sk = f"{m.get('name','')}|{m.get('host','')}:{m.get('port',4028)}"
            st = states.get(sk)
            if st:
                st.is_shutdown_maintenance = True
                st.snooze_until_ts = snooze_until
            stopped_names.append(m.get("name", sk))

        safe_card = render_safe_area_card(stopped_names, snooze_hours=window.duration_seconds / 3600.0)
        if send_telegram_fn and bot_token and chat_id and ((not qa_mode) or qa_notify):
            send_telegram_fn(bot_token, str(chat_id), safe_card, "SHUTDOWN_SAFE", "scheduled_t0_executed")

        if record_event_fn:
            record_event_fn(
                action="scheduled_shutdown_t0",
                source="scheduler",
                ok=True,
                message=f"Parada programada ejecutada en T-0 con snooze {int(window.duration_seconds // 60)}m",
            )

    elif new_stage == ScheduledStage.COMPLETED:
        window.stage = ScheduledStage.COMPLETED
        window.stage_updated_ts = now_ts
        if log_fn:
            log_fn(f"[SCHEDULER] Maintenance window {window.window_id} completed.")
        if record_event_fn:
            record_event_fn(
                action="scheduled_completed",
                source="scheduler",
                ok=True,
                message=f"Ventana de mantenimiento {window.window_id} completada.",
            )

    if save_state_fn and state_path:
        try:
            save_state_fn(state_path, states, current_last_update_id)
        except Exception:
            pass

    return window
