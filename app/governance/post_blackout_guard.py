"""Post-Blackout Recovery Guard (Spec 050).

Provides pure evaluation, safety interlocks, in-memory state tracking, and Mobile-First
Telegram cards (<= 32 cols) for detecting and safely resuming ASICs that remain in
'stopped' state following a power outage.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.governance.fleet_shutdown import (
    DEFAULT_PURGE_FAN_DUTY,
    execute_parallel_fan_duty,
    execute_parallel_resume,
    extract_miner_identifier,
)
from app.telegram.help_center import visible_line_width, wrap_mobile_lines

DEFAULT_CONFIRM_TICKS = 2
DEFAULT_MAX_CHIP_TEMP_C = 85.0
DEFAULT_GRACE_PERIOD_SECONDS = 180


@dataclass(frozen=True)
class PostBlackoutTarget:
    """Descriptor of an ASIC evaluated for post-blackout recovery."""
    miner_id: str
    name: str
    host: str
    uptime_seconds: Optional[int] = None
    consecutive_stopped_ticks: int = 0
    miner_state: str = "stopped"
    rate_ths: float = 0.0
    chip_temp_c: Optional[float] = None
    first_stopped_ts: Optional[float] = None


class PostBlackoutTracker:
    """In-memory state tracker for post-blackout candidate miners across cycles."""

    def __init__(self) -> None:
        self._stopped_ticks: Dict[str, int] = {}
        self._first_stopped_ts: Dict[str, float] = {}
        self._alert_sent: Dict[str, bool] = {}
        self._resumed_auto: Dict[str, bool] = {}

    def get_stopped_ticks(self, miner_id: str) -> int:
        return self._stopped_ticks.get(miner_id, 0)

    def record_tick(self, miner_id: str, is_candidate: bool, now_ts: float) -> int:
        """Record evaluation for miner. Increments ticks if candidate, resets otherwise."""
        if is_candidate:
            cnt = self._stopped_ticks.get(miner_id, 0) + 1
            self._stopped_ticks[miner_id] = cnt
            if miner_id not in self._first_stopped_ts:
                self._first_stopped_ts[miner_id] = now_ts
            return cnt
        else:
            self.reset(miner_id)
            return 0

    def get_first_stopped_ts(self, miner_id: str) -> Optional[float]:
        return self._first_stopped_ts.get(miner_id)

    def is_alert_sent(self, miner_id: str) -> bool:
        return self._alert_sent.get(miner_id, False)

    def mark_alert_sent(self, miner_id: str) -> None:
        self._alert_sent[miner_id] = True

    def is_resumed_auto(self, miner_id: str) -> bool:
        return self._resumed_auto.get(miner_id, False)

    def mark_resumed_auto(self, miner_id: str) -> None:
        self._resumed_auto[miner_id] = True

    def reset(self, miner_id: str) -> None:
        self._stopped_ticks.pop(miner_id, None)
        self._first_stopped_ts.pop(miner_id, None)
        self._alert_sent.pop(miner_id, None)
        self._resumed_auto.pop(miner_id, None)

    def reset_all(self) -> None:
        self._stopped_ticks.clear()
        self._first_stopped_ts.clear()
        self._alert_sent.clear()
        self._resumed_auto.clear()


def is_transient_state(miner_state: str) -> bool:
    """Check if state is a transient booting/initializing state."""
    st = (miner_state or "").strip().lower()
    return st in ("starting", "benchmarking", "init", "initializing", "rebooting", "booting")


def is_stopped_state(miner_state: str, rate_ths: float) -> bool:
    """Check if state indicates mining is stopped or halted without hashrate."""
    st = (miner_state or "").strip().lower()
    if st in ("stopped", "paused", "idle", "stop", "halted"):
        return True
    return False


def evaluate_miner_post_blackout(
    miner_id: str,
    name: str,
    host: str,
    miner_state: str,
    rate_ths: float,
    uptime_seconds: Optional[int],
    consecutive_stopped_ticks: int,
    in_maintenance: bool = False,
    is_snoozed: bool = False,
    startup_guard_active: bool = False,
    chip_temp_c: Optional[float] = None,
    max_chip_temp_c: float = DEFAULT_MAX_CHIP_TEMP_C,
    confirm_ticks: int = DEFAULT_CONFIRM_TICKS,
) -> Tuple[bool, Optional[str]]:
    """
    Evaluates whether a miner should be flagged by the Post-Blackout Recovery Guard.
    Returns: (is_candidate: bool, reason_or_blocker: Optional[str])
    """
    if in_maintenance:
        return False, "in_maintenance"
    if is_snoozed:
        return False, "snoozed"
    if startup_guard_active:
        return False, "startup_guard_active"
    if chip_temp_c is not None and chip_temp_c >= max_chip_temp_c:
        return False, "thermal_interlock"
    if is_transient_state(miner_state):
        return False, "transient_starting"
    if not is_stopped_state(miner_state, rate_ths):
        return False, "active_or_normal"
    if consecutive_stopped_ticks < confirm_ticks:
        return False, "awaiting_confirmation"
    return True, None


def format_uptime_short(seconds: Optional[int]) -> str:
    """Format uptime into compact string <= 7 chars."""
    if seconds is None or seconds < 0:
        return "N/D"
    if seconds < 60:
        return f"{seconds}s"
    m = seconds // 60
    if m < 60:
        return f"{m}m"
    h = m // 60
    rem_m = m % 60
    if h < 24:
        return f"{h}h {rem_m}m" if rem_m else f"{h}h"
    d = h // 24
    rem_h = h % 24
    return f"{d}d {rem_h}h"


def render_post_blackout_alert(
    stopped_miners: List[PostBlackoutTarget],
    auto_resume_seconds: Optional[int] = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    Renders Telegram alert card and inline keyboard for post-blackout stopped miners.
    Returns (message_text, reply_markup_dict).
    Enforces <= 32 visible columns per line.
    """
    lines = [
        "⚡ *RECUPERACIÓN POST-CORTE*",
        "─" * 32,
        "Mineros en línea pero detenidos",
        "tras retorno de tensión o red:",
        "",
    ]
    for m in stopped_miners:
        upt = format_uptime_short(m.uptime_seconds)
        lines.append(f"• *{m.name}*")
        lines.append("  Estado: 🛑 Detenido")
        lines.append(f"  Uptime: {upt} | Hash: 0.0 T")

    lines.append("")
    if auto_resume_seconds is not None and auto_resume_seconds > 0:
        lines.append(f"⏳ *Auto-reanudación*: {auto_resume_seconds}s")
        lines.append("─" * 32)
        lines.append("Reanudá ya o cancelá con snooze:")
    else:
        lines.append("─" * 32)
        lines.append("Tocá el botón para reanudar:")

    # Keyboard layout
    keyboard: List[List[Dict[str, str]]] = []
    if len(stopped_miners) >= 2:
        keyboard.append([
            {"text": f"▶️ Reanudar Flota ({len(stopped_miners)})", "callback_data": "pbr:resume:all"}
        ])
    elif len(stopped_miners) == 1:
        single_id = stopped_miners[0].miner_id
        keyboard.append([
            {"text": f"▶️ Reanudar {stopped_miners[0].name}", "callback_data": f"pbr:resume:{single_id}"}
        ])

    keyboard.append([
        {"text": "🔕 Silenciar 1h", "callback_data": "pbr:snooze:60"}
    ])

    reply_markup = {"inline_keyboard": keyboard}
    return "\n".join(lines), reply_markup


def render_recovery_action_card(
    resumed_names: List[str],
    automated: bool = False,
) -> str:
    """
    Render confirmation card when miners have been resumed following a blackout.
    Enforces <= 32 visible columns per line.
    """
    title = "🤖 *AUTO-REANUDACIÓN OK*" if automated else "▶️ *FLOTA REANUDADA*"
    lines = [
        title,
        "─" * 32,
        "Minado reactivado con éxito:",
    ]
    for name in resumed_names:
        lines.append(f"• *{name}*")
        lines.append("  └ Hash: ON | Fans: 100%")
    lines.extend([
        "",
        "Supervisión térmica activa.",
        "Monitoreando autotuning.",
        "─" * 32,
    ])
    return "\n".join(lines)


def resolve_target_miners(target_id: str, miners: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter miners list matching identifier or return all."""
    if not target_id or target_id.lower() == "all":
        return list(miners)
    matched = []
    for m in miners:
        m_id = extract_miner_identifier(m)
        if m_id == target_id or m.get("name") == target_id or m.get("host") == target_id:
            matched.append(m)
    return matched


def execute_post_blackout_cycle(
    miners: List[Dict[str, Any]],
    states: Dict[str, Any],
    state_lock: Any,
    config: Dict[str, Any],
    now_ts: float,
    process_start_ts: float,
    tracker: PostBlackoutTracker,
    send_telegram_fn: Optional[Callable[..., Any]] = None,
    record_event_fn: Optional[Callable[..., Any]] = None,
    resume_fn: Optional[Callable[..., Any]] = None,
    fan_fn: Optional[Callable[..., Any]] = None,
    log_fn: Optional[Callable[..., Any]] = None,
    bot_token: str = "",
    chat_id: str = "",
    qa_mode: bool = False,
    qa_notify: bool = False,
) -> Dict[str, Any]:
    """
    Supervise fleet for stopped ASICs post-boot/blackout.
    Dispatches alerts and performs optional auto-resume.
    """
    _log = log_fn or print
    pbr_cfg = config.get("post_blackout_guard", {})
    if pbr_cfg.get("enabled", True) is False:
        return {"status": "disabled", "candidates": []}

    confirm_ticks = int(pbr_cfg.get("confirm_ticks", DEFAULT_CONFIRM_TICKS))
    auto_resume = bool(pbr_cfg.get("auto_resume", False))
    grace_period = float(pbr_cfg.get("grace_period_seconds", DEFAULT_GRACE_PERIOD_SECONDS))
    max_chip_temp_c = float(pbr_cfg.get("max_chip_temp_c", DEFAULT_MAX_CHIP_TEMP_C))
    startup_guard_seconds = float(config.get("startup_safety_guard_seconds", 600.0))
    startup_guard_active = (now_ts - process_start_ts) < startup_guard_seconds

    qualifying: List[PostBlackoutTarget] = []
    for m in miners:
        m_id = extract_miner_identifier(m)
        m_name = m.get("name", m.get("host", m_id))
        m_host = m.get("host", "")
        sk = f"{m.get('name','')}|{m.get('host','')}:{m.get('port',4028)}"

        with state_lock:
            st = states.get(sk) or states.get(m_name)
            in_maint = getattr(st, "is_shutdown_maintenance", False) if st else False
            snooze_until = getattr(st, "snooze_until_ts", None) if st else None
            is_snz = (snooze_until is not None and snooze_until > now_ts)
            st_state = getattr(st, "last_miner_state", getattr(st, "state", "stopped")) if st else "stopped"
            rate_ths = getattr(st, "last_rate_ths", 0.0) or 0.0
            uptime = getattr(st, "last_uptime_seconds", None)
            chip_temp = getattr(st, "last_max_chip_temp", None) or getattr(st, "governor_last_temp_c", None)

        is_stopped_cand = (
            not in_maint
            and not is_snz
            and not startup_guard_active
            and (chip_temp is None or chip_temp < max_chip_temp_c)
            and not is_transient_state(st_state)
            and is_stopped_state(st_state, rate_ths)
        )
        ticks = tracker.record_tick(m_id, is_stopped_cand, now_ts)
        if is_stopped_cand and ticks >= confirm_ticks:
            qualifying.append(
                PostBlackoutTarget(
                    miner_id=m_id,
                    name=m_name,
                    host=m_host,
                    uptime_seconds=uptime,
                    consecutive_stopped_ticks=ticks,
                    miner_state=st_state,
                    rate_ths=rate_ths,
                    chip_temp_c=chip_temp,
                    first_stopped_ts=tracker.get_first_stopped_ts(m_id),
                )
            )

    if not qualifying:
        return {"status": "ok", "candidates": []}

    # Check alert dispatch
    unnotified = [q for q in qualifying if not tracker.is_alert_sent(q.miner_id)]
    if unnotified and send_telegram_fn:
        earliest_ts = min((q.first_stopped_ts or now_ts) for q in qualifying)
        rem_grace = int(max(0, grace_period - (now_ts - earliest_ts))) if auto_resume else None
        alert_text, reply_markup = render_post_blackout_alert(qualifying, auto_resume_seconds=rem_grace)

        if (not qa_mode) or qa_notify:
            send_telegram_fn(
                bot_token,
                str(chat_id),
                alert_text,
                "POST_BLACKOUT",
                "post_blackout_alert",
                reply_markup=reply_markup,
            )
        _log(f"[POST_BLACKOUT] Alert dispatched for {len(qualifying)} stopped miner(s): {[q.name for q in qualifying]}")

        for q in qualifying:
            tracker.mark_alert_sent(q.miner_id)
            if record_event_fn:
                record_event_fn(
                    miner={"name": q.name, "host": q.host},
                    action="post_blackout_alert",
                    source="guard",
                    ok=True,
                    message=f"Alerta post-corte: equipo en stopped ({q.consecutive_stopped_ticks} ticks)",
                )

    # Check auto-resume condition
    auto_resumed_names: List[str] = []
    if auto_resume:
        earliest_ts = min((q.first_stopped_ts or now_ts) for q in qualifying)
        if (now_ts - earliest_ts) >= grace_period:
            pending_auto = [q for q in qualifying if not tracker.is_resumed_auto(q.miner_id)]
            if pending_auto:
                _log(f"[POST_BLACKOUT] Grace period ({grace_period:.0f}s) elapsed. Executing auto-resume...")
                target_dicts = [m for m in miners if extract_miner_identifier(m) in {q.miner_id for q in pending_auto}]
                vnish_pw = str(config.get("vnish_api_password", "admin"))
                r_fn = resume_fn or execute_parallel_resume
                f_fn = fan_fn or execute_parallel_fan_duty

                results = r_fn(target_dicts, vnish_pw)
                with state_lock:
                    for td in target_dicts:
                        tid = extract_miner_identifier(td)
                        r_item = results.get(tid)
                        if r_item and r_item.success:
                            tsk = f"{td.get('name','')}|{td.get('host','')}:{td.get('port',4028)}"
                            st_obj = states.get(tsk)
                            if st_obj:
                                st_obj.is_shutdown_maintenance = False
                                st_obj.snooze_until_ts = None
                            tracker.reset(tid)

                succ_dicts = [td for td in target_dicts if results.get(extract_miner_identifier(td)) and results[extract_miner_identifier(td)].success]
                if succ_dicts:
                    f_fn(succ_dicts, DEFAULT_PURGE_FAN_DUTY, vnish_pw)

                for q in pending_auto:
                    r_item = results.get(q.miner_id)
                    s_ok = r_item.success if r_item else False
                    if s_ok:
                        tracker.mark_resumed_auto(q.miner_id)
                        auto_resumed_names.append(q.name)
                    if record_event_fn:
                        record_event_fn(
                            miner={"name": q.name, "host": q.host},
                            action="post_blackout_resume_auto",
                            source="guard_auto",
                            ok=s_ok,
                            message="Auto-reanudación ejecutada tras ventana de gracia",
                        )

                if auto_resumed_names and send_telegram_fn:
                    action_card = render_recovery_action_card(auto_resumed_names, automated=True)
                    if (not qa_mode) or qa_notify:
                        send_telegram_fn(
                            bot_token,
                            str(chat_id),
                            action_card,
                            "POST_BLACKOUT",
                            "post_blackout_auto_resume",
                        )
                    _log(f"[POST_BLACKOUT] Auto-resumed {len(auto_resumed_names)} miner(s): {auto_resumed_names}")

    return {
        "status": "alerted",
        "candidates": [q.miner_id for q in qualifying],
        "auto_resumed": auto_resumed_names,
    }


def process_post_blackout_callback(
    cb_data: str,
    cb_id: str,
    cb_chat_id: Any,
    message_id: Optional[int],
    miners: List[Dict[str, Any]],
    states: Dict[str, Any],
    state_lock: Any,
    state_path: Any,
    config: Dict[str, Any],
    bot_token: str,
    answer_cb_fn: Callable[..., Any],
    edit_msg_fn: Callable[..., Any],
    save_state_fn: Callable[..., Any],
    record_event_fn: Optional[Callable[..., Any]] = None,
    resume_fn: Optional[Callable[..., Any]] = None,
    fan_fn: Optional[Callable[..., Any]] = None,
    qa_mode: bool = False,
    qa_allow_actions: bool = False,
    tracker: Optional[PostBlackoutTracker] = None,
    current_last_update_id: Optional[int] = None,
) -> bool:
    """
    Handle incoming 'pbr:*' Telegram callback query.
    Returns True if handled, False otherwise.
    """
    if not cb_data or not cb_data.startswith("pbr:"):
        return False

    parts = cb_data.strip().split(":")
    if len(parts) < 3:
        answer_cb_fn(bot_token, cb_id, text="⚠️ Callback inválido.")
        return True

    action_type = parts[1]  # "resume" or "snooze"
    param = parts[2]        # "all", <miner_id>, or "60"

    # --- Snooze Flow ---
    if action_type == "snooze":
        answer_cb_fn(bot_token, cb_id, text="🔕 Silenciando por 60m...")
        try:
            mins = float(param)
        except ValueError:
            mins = 60.0
        now_ts = time.time()
        snooze_until = now_ts + (mins * 60.0)

        with state_lock:
            for m in miners:
                sk = f"{m.get('name','')}|{m.get('host','')}:{m.get('port',4028)}"
                st = states.get(sk)
                if st:
                    st.snooze_until_ts = snooze_until
            save_state_fn(state_path, states, current_last_update_id)

        if tracker:
            tracker.reset_all()

        if message_id is not None:
            snooze_card = f"🔕 *Flota silenciada por {int(mins)}m*.\nGuardián post-corte pausado."
            edit_msg_fn(bot_token, str(cb_chat_id), message_id, snooze_card)
        return True

    # --- Resume Flow ---
    if action_type == "resume":
        answer_cb_fn(bot_token, cb_id, text="▶️ Reanudando minado...")
        target_miners = resolve_target_miners(param, miners)
        if not target_miners:
            if message_id is not None:
                edit_msg_fn(bot_token, str(cb_chat_id), message_id, f"❌ Minero {param} no encontrado.")
            return True

        if qa_mode and not qa_allow_actions:
            if message_id is not None:
                edit_msg_fn(bot_token, str(cb_chat_id), message_id, "🚫 Reanudación bloqueada (modo QA).")
            return True

        vnish_pw = str(config.get("vnish_api_password", "admin"))
        r_fn = resume_fn or execute_parallel_resume
        f_fn = fan_fn or execute_parallel_fan_duty

        results = r_fn(target_miners, vnish_pw)

        with state_lock:
            for m in target_miners:
                m_id = extract_miner_identifier(m)
                res = results.get(m_id)
                if res and res.success:
                    sk = f"{m.get('name','')}|{m.get('host','')}:{m.get('port',4028)}"
                    st = states.get(sk)
                    if st:
                        st.is_shutdown_maintenance = False
                        st.snooze_until_ts = None
                    if tracker:
                        tracker.reset(m_id)
            save_state_fn(state_path, states, current_last_update_id)

        succ_miners = [m for m in target_miners if results.get(extract_miner_identifier(m)) and results[extract_miner_identifier(m)].success]
        if succ_miners:
            f_fn(succ_miners, DEFAULT_PURGE_FAN_DUTY, vnish_pw)

        for m in target_miners:
            m_id = extract_miner_identifier(m)
            res = results.get(m_id)
            s_ok = res.success if res else False
            if record_event_fn:
                record_event_fn(
                    miner=m,
                    action="post_blackout_resume_manual",
                    source="telegram_pbr",
                    ok=s_ok,
                    message="Reanudación manual post-corte",
                )

        if message_id is not None:
            succ_names = [m.get("name", extract_miner_identifier(m)) for m in succ_miners]
            if succ_names:
                card = render_recovery_action_card(succ_names, automated=False)
            else:
                card = "❌ *Fallo al reanudar minado*.\nVerificá conexión a los equipos."
            edit_msg_fn(bot_token, str(cb_chat_id), message_id, card)

        return True

    return False
