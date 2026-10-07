"""Telegram interactive callbacks and inline keyboard helpers (Spec 031).

Provides pure data models, serialization grammar, validation, and bounded
in-memory token registry for 1-Tap interactive buttons.
"""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

MAX_CALLBACK_DATA_BYTES = 64
DEFAULT_TOKEN_TTL_SECONDS = 60.0
DEFAULT_MAX_TOKENS = 10


@dataclass(frozen=True)
class CallbackAction:
    action_type: str
    miner_id: str
    token: Optional[str] = None
    param: Optional[str] = None


def parse_callback_data(raw_data: str) -> Optional[CallbackAction]:
    """Parse a callback_data string into a structured CallbackAction.

    Supported formats:
    - diag:<miner_id>
    - chart:<miner_id>
    - snz:<miner_id>:<minutes>
    - rb_req:<miner_id>
    - rb_cfm:<token>:<miner_id>
    - rb_ccl:<miner_id>
    - noop
    """
    if not raw_data or not isinstance(raw_data, str):
        return None

    parts = raw_data.strip().split(":")
    tag = parts[0]

    if tag == "noop":
        return CallbackAction(action_type="noop", miner_id="")
    elif tag in ("diag", "chart", "rb_req", "rb_ccl", "flash_req", "flash_ccl"):
        if len(parts) == 2 and parts[1]:
            return CallbackAction(action_type=tag, miner_id=parts[1])
        return None
    elif tag in ("snz", "chart_range"):
        if len(parts) == 3 and parts[1] and parts[2]:
            return CallbackAction(action_type=tag, miner_id=parts[1], param=parts[2])
        return None
    elif tag in ("rb_cfm", "flash_cfm"):
        if len(parts) == 3 and parts[1] and parts[2]:
            return CallbackAction(action_type=tag, miner_id=parts[2], token=parts[1])
        return None

    return None


def build_callback_data(
    action_type: str,
    miner_id: str,
    token: Optional[str] = None,
    param: Optional[str] = None,
) -> str:
    """Build a normalized callback_data string guaranteed under 64 bytes."""
    if action_type == "noop":
        return "noop"
    elif action_type in ("diag", "chart", "rb_req", "rb_ccl", "flash_req", "flash_ccl"):
        res = f"{action_type}:{miner_id}"
    elif action_type == "snz":
        res = f"snz:{miner_id}:{param or '60'}"
    elif action_type == "chart_range":
        res = f"chart_range:{miner_id}:{param or '1'}"
    elif action_type in ("rb_cfm", "flash_cfm"):
        res = f"{action_type}:{token or ''}:{miner_id}"
    else:
        res = f"{action_type}:{miner_id}"

    if len(res.encode("utf-8")) > MAX_CALLBACK_DATA_BYTES:
        raise ValueError(f"callback_data exceeds {MAX_CALLBACK_DATA_BYTES} bytes: {res}")
    return res


class CallbackTokenRegistry:
    """Bounded, thread-safe in-memory confirmation token cache."""

    def __init__(self, ttl_seconds: float = DEFAULT_TOKEN_TTL_SECONDS, max_tokens: int = DEFAULT_MAX_TOKENS):
        self._ttl_seconds = ttl_seconds
        self._max_tokens = max_tokens
        self._lock = threading.Lock()
        # Mapping: token -> (miner_id, action, created_ts, [ttl_seconds])
        self._tokens: Dict[str, Tuple[Any, ...]] = {}

    def _prune(self, now: float):
        expired = [
            tok for tok, entry in list(self._tokens.items())
            if now - entry[2] > (entry[3] if len(entry) > 3 else self._ttl_seconds)
        ]
        for tok in expired:
            self._tokens.pop(tok, None)

        if len(self._tokens) >= self._max_tokens:
            # Sort by created_ts ascending and drop oldest
            sorted_tokens = sorted(self._tokens.items(), key=lambda item: item[1][2])
            to_remove = len(self._tokens) - self._max_tokens + 1
            for tok, _ in sorted_tokens[:to_remove]:
                self._tokens.pop(tok, None)

    def create_token(self, miner_id: str, action: str = "reboot", ttl: Optional[float] = None) -> str:
        now = time.time()
        effective_ttl = float(ttl) if ttl is not None else self._ttl_seconds
        with self._lock:
            self._prune(now)
            token = secrets.token_hex(3)  # 6 hex chars
            self._tokens[token] = (miner_id, action, now, effective_ttl)
            return token

    generate = create_token

    def consume_token(self, token: str) -> Tuple[bool, Optional[str], str]:
        now = time.time()
        with self._lock:
            entry = self._tokens.pop(token, None)
            self._prune(now)

            if entry is None:
                return False, None, "token_not_found"

            miner_id = entry[0]
            action = entry[1]
            created_ts = entry[2]
            tok_ttl = entry[3] if len(entry) > 3 else self._ttl_seconds

            if now - created_ts > tok_ttl:
                return False, None, "token_expired"

            return True, miner_id, "ok"

    def invalidate_miner(self, miner_id: str) -> int:
        with self._lock:
            to_del = [tok for tok, entry in list(self._tokens.items()) if entry[0] == miner_id]
            for tok in to_del:
                self._tokens.pop(tok, None)
            return len(to_del)


def build_alert_keyboard(miner_id: str) -> Dict[str, Any]:
    """Build the 1-Tap action bar for episode alerts."""
    return {
        "inline_keyboard": [
            [
                {"text": "🩺 Diagnosticar", "callback_data": build_callback_data("diag", miner_id)},
                {"text": "📊 Ver Gráfico", "callback_data": build_callback_data("chart", miner_id)},
            ],
            [
                {"text": f"🔄 Reiniciar {miner_id}", "callback_data": build_callback_data("rb_req", miner_id)},
                {"text": "🔕 Silenciar 1h", "callback_data": build_callback_data("snz", miner_id, param="60")},
            ],
        ]
    }


def build_confirmation_keyboard(miner_id: str, token: str) -> Dict[str, Any]:
    """Build the safe 2-step confirmation keyboard."""
    return {
        "inline_keyboard": [
            [
                {
                    "text": f"⚠️ CONFIRMAR REINICIO {miner_id}",
                    "callback_data": build_callback_data("rb_cfm", miner_id, token=token),
                }
            ],
            [
                {
                    "text": "❌ Cancelar",
                    "callback_data": build_callback_data("rb_ccl", miner_id),
                }
            ],
        ]
    }


def build_settled_keyboard(text: str = "Reinicio Solicitado") -> Dict[str, Any]:
    """Build a neutral settled action bar after confirmation."""
    return {
        "inline_keyboard": [
            [
                {"text": text, "callback_data": "noop"}
            ]
        ]
    }


def _handle_diagnostic_callback(
    cb_query: dict,
    *,
    config: dict,
    bot_token: str,
    cb_chat_id: Any,
    message_id: Optional[int],
    cb_id: str,
    miners: list,
    states: Dict[str, Any],
    state_lock: threading.Lock,
    event_store: Optional[Any] = None,
) -> None:
    """Handle diagnostic report refresh callbacks (diag:ref:*) with instant ACK (Spec 046 & 047 & 087)."""
    import app.miner_monitor as mm
    from app.miner_monitor import (
        answer_callback_query,
        edit_message_text,
        log,
        now_str,
        resolve_db_path,
        resolve_miner,
    )
    from app.telegram.fleet_cards import (
        build_diagnostic_keyboard,
        parse_diagnostic_callback,
        render_fleet_status_card,
    )
    cb_data = cb_query.get("data") or ""
    action = parse_diagnostic_callback(cb_data)
    if not action:
        log(f"DIAG_CB_PARSE_FAIL cb_id={cb_id} data={cb_data[:40]!r}")
        answer_callback_query(bot_token, cb_id, text="⚠️ Opción no reconocida.")
        return

    # Acknowledge immediately to clear the UI spinner (< 50ms)
    answer_callback_query(bot_token, cb_id)

    new_text: Optional[str] = None
    new_markup: Optional[Dict[str, Any]] = None

    try:
        if action.report_type == "status":
            with state_lock:
                states_snapshot = {k: v for k, v in states.items()}
            new_text, new_markup = render_fleet_status_card(
                states_snapshot, config=config, miners=miners, now_ts_str=now_str()
            )
        elif action.report_type == "fans":
            from app.governance.fan_health import (
                build_fans_table_text,
                fetch_latest_cooling_assessments,
            )
            db_p = resolve_db_path(config)
            with state_lock:
                assessments = fetch_latest_cooling_assessments(
                    db_path=db_p,
                    miners=miners,
                    states=states,
                    config=config,
                )
            new_text = build_fans_table_text(assessments)
            new_markup = build_diagnostic_keyboard("fans")
        elif action.report_type == "eff":
            from app.governance.energy_efficiency import (
                build_efficiency_table_text,
                fetch_latest_efficiency_assessments,
            )
            db_p = resolve_db_path(config)
            with state_lock:
                assessments = fetch_latest_efficiency_assessments(
                    db_path=db_p,
                    miners=miners,
                    states=states,
                    config=config,
                )
            new_text = build_efficiency_table_text(assessments)
            new_markup = build_diagnostic_keyboard("eff")
        elif action.report_type == "presets":
            from app.vnish.presets import (
                build_presets_table_text,
                fetch_latest_preset_assessments,
            )
            db_p = resolve_db_path(config)
            with state_lock:
                assessments = fetch_latest_preset_assessments(
                    db_path=db_p,
                    miners=miners,
                    states=states,
                    config=config,
                )
            new_text = build_presets_table_text(assessments)
            new_markup = build_diagnostic_keyboard("presets")
        elif action.report_type == "balancer":
            from app.governance.preset_balancer import (
                BalancerConfig,
                build_balancer_table_text,
                evaluate_balancer_step,
                extract_miner_stability_metrics,
            )
            bal_dry_run = bool(config.get("preset_balancer_dry_run", True))
            bal_enabled_cfg = bool(config.get("preset_balancer_enabled", False))
            db_p = resolve_db_path(config)
            with state_lock:
                metrics_list = extract_miner_stability_metrics(
                    db_path=db_p,
                    miners=miners,
                    states=states,
                    config=config,
                    now_ts=time.time(),
                )
            decisions_tuples = []
            bal_cfg = BalancerConfig(
                enabled=True,
                dry_run=bal_dry_run,
                default_max_preset=str(config.get("preset_balancer_default_max_preset", "2700W")),
            )
            for m_metrics in metrics_list:
                m_dict = next((m for m in miners if m.get("name") == m_metrics.miner_name), {})
                max_ov = m_dict.get("max_preset")
                dec = evaluate_balancer_step(
                    m_metrics,
                    config=bal_cfg,
                    group_metrics=metrics_list,
                    max_preset_override=max_ov,
                )
                decisions_tuples.append((m_metrics, dec))
            from app.governance._orchestrator_state import get_balancer_enabled
            _rt_bal_cb = get_balancer_enabled()
            if _rt_bal_cb is None:
                _rt_bal_cb = getattr(mm, "_BALANCER_RUNTIME_ENABLED", None)
            is_enabled = _rt_bal_cb if _rt_bal_cb is not None else bal_enabled_cfg
            new_text = build_balancer_table_text(
                decisions_tuples,
                is_enabled=is_enabled,
                is_dry_run=bal_dry_run,
            )
            new_markup = build_diagnostic_keyboard("balancer")
        elif action.report_type == "elev":
            from app.governance.preset_balancer import (
                analyze_elevator_sensitivity,
                build_elevator_sensitivity_text,
                extract_miner_stability_metrics,
            )
            db_p = resolve_db_path(config)
            with state_lock:
                metrics_list = extract_miner_stability_metrics(
                    db_path=db_p,
                    miners=miners,
                    states=states,
                    config=config,
                    now_ts=time.time(),
                )
            summaries = analyze_elevator_sensitivity(metrics_list, db_path=db_p)
            new_text = build_elevator_sensitivity_text(summaries)
            new_markup = build_diagnostic_keyboard("elev")
        elif action.report_type == "digest":
            from app.telegram.daily_digest import (
                fetch_daily_digest_metrics,
                format_daily_digest,
            )
            db_p = resolve_db_path(config)
            b_root = config.get("backup_root", "backups")
            with state_lock:
                digest_metrics = fetch_daily_digest_metrics(
                    db_path=db_p,
                    miners=miners,
                    now_ts=time.time(),
                    backup_root=b_root,
                    states=states,
                )
            new_text = format_daily_digest(digest_metrics)
            new_markup = build_diagnostic_keyboard("digest")
        elif action.report_type == "events":
            from app.core.event_store import render_event_list
            if event_store is not None and event_store.available:
                recent_events = event_store.list_events(limit=8)
                new_text = (
                    "Historial temporalmente no disponible."
                    if event_store.last_error
                    else render_event_list(recent_events)
                )
            else:
                new_text = "Historial no disponible."
            new_markup = build_diagnostic_keyboard("events")
        elif action.report_type in ("anom_comp", "anom_desc", "anomalies"):
            from app.core.event_store import (
                render_anomalies_compact,
                render_anomalies_detailed,
            )
            from app.telegram.fleet_cards import build_anomalies_keyboard
            if event_store is not None and event_store.available:
                anomalies = event_store.list_anomalies_24h(limit=50)
                if action.report_type == "anom_desc":
                    new_text = (
                        "Historial temporalmente no disponible."
                        if event_store.last_error
                        else render_anomalies_detailed(anomalies)
                    )
                    new_markup = build_anomalies_keyboard("detailed")
                else:
                    new_text = (
                        "Historial temporalmente no disponible."
                        if event_store.last_error
                        else render_anomalies_compact(anomalies)
                    )
                    new_markup = build_anomalies_keyboard("compact")
            else:
                new_text = "Historial de anomalías no disponible."
                new_markup = build_diagnostic_keyboard("digest")
        elif action.report_type == "chains":
            from app.governance.chain_health import (
                assess_miner_chains,
                build_chains_card_text,
                build_chains_fleet_summary_text,
            )
            from app.telegram.fleet_cards import build_chains_keyboard
            miner_arg = action.miner_id
            if miner_arg:
                matched_miner = resolve_miner(miner_arg, miners)
                m_name = matched_miner.get("name") if matched_miner else miner_arg
                m_key = f"{matched_miner['name']}|{matched_miner['host']}:{matched_miner['port']}" if matched_miner else miner_arg
                samples = event_store.get_latest_chain_samples(m_key) if (event_store and event_store.available) else []
                ass = assess_miner_chains(m_name, samples)
                new_text = build_chains_card_text(ass)
                new_markup = build_chains_keyboard(current_miner=m_name, miners=miners)
            else:
                assessments_list = []
                for m in miners:
                    m_key = f"{m.get('name')}|{m.get('host')}:{m.get('port')}"
                    samples = event_store.get_latest_chain_samples(m_key) if (event_store and event_store.available) else []
                    assessments_list.append(assess_miner_chains(m.get("name", "Miner"), samples))
                new_text = build_chains_fleet_summary_text(assessments_list)
                new_markup = build_chains_keyboard(miners=miners)
    except Exception as exc:
        log(f"DIAG_CB_ERR cb_id={cb_id} report={action.report_type} exc={exc}")
        return

    if message_id is not None and new_text and new_markup:
        edit_message_text(
            bot_token,
            str(cb_chat_id),
            message_id,
            new_text,
            reply_markup=new_markup,
            parse_mode="Markdown",
        )


def _handle_callback_query(
    cb_query: dict,
    *,
    config: dict,
    bot_token: str,
    chat_id: str,
    miners: list,
    states: Dict[str, Any],
    state_lock: threading.Lock,
    state_path: Any,
    current_last_update_id: Optional[int],
    hashcore_cfg: dict,
    event_store: Optional[Any],
    qa_mode: bool,
    qa_allow_actions: bool,
    token_registry: CallbackTokenRegistry,
) -> None:
    """Handle a single Telegram callback_query from an inline keyboard tap (Spec 031 & 087).

    Authentication, parsing, and action dispatch are all performed here.
    answerCallbackQuery is always called to acknowledge the tap within 1s.
    """
    import app.miner_monitor as mm
    from app.miner_monitor import (
        answer_callback_query,
        build_miner_diagnosis_text,
        display_name,
        edit_message_reply_markup,
        edit_message_text,
        edit_telegram_photo,
        is_miner_no_ok,
        log,
        record_action_outcome,
        resolve_db_path,
        resolve_miner,
        run_hashcore_cli,
        save_state,
        send_telegram,
        send_telegram_photo,
        _build_state_payload,
        _flush_state_payload,
    )
    from app.governance.adaptive_contingency import normalize_miner_name
    from app.governance.maintenance_scheduler import ScheduledStage, render_schedule_cancelled_card

    cb_id = cb_query.get("id") or ""
    from_user = cb_query.get("from") or {}
    from_id = from_user.get("id")
    cb_data = cb_query.get("data") or ""
    msg = cb_query.get("message") or {}
    message_id = msg.get("message_id")
    cb_chat_id = (msg.get("chat") or {}).get("id") or chat_id

    # --- Strict authentication: from.id must match the configured chat_id ---
    try:
        authorized = from_id is not None and int(from_id) == int(chat_id)
    except (TypeError, ValueError):
        authorized = False

    if not authorized:
        log(
            f"CB_AUTH_FAIL cb_id={cb_id} from_id={from_id} "
            f"expected={chat_id}"
        )
        answer_callback_query(
            bot_token,
            cb_id,
            text="⛔ Acceso no autorizado",
            show_alert=True,
        )
        return

    # T007 / Spec 043: Handle interactive Command Center callbacks
    from app.telegram.command_center import CC_PREFIX, _handle_command_center_callback
    if cb_data.startswith(CC_PREFIX):
        _handle_command_center_callback(
            cb_query=cb_query,
            config=config,
            bot_token=bot_token,
            chat_id=chat_id,
            cb_chat_id=cb_chat_id,
            message_id=message_id,
            cb_id=cb_id,
            miners=miners,
            states=states,
            state_lock=state_lock,
            state_path=state_path,
            current_last_update_id=current_last_update_id,
            hashcore_cfg=hashcore_cfg,
            event_store=event_store,
            qa_mode=qa_mode,
            qa_allow_actions=qa_allow_actions,
            token_registry=token_registry,
        )
        return

    # Spec 045: Handle interactive Help Center callbacks (help:*)
    from app.telegram.help_center import HELP_PREFIX, _handle_help_callback
    if cb_data.startswith(HELP_PREFIX):
        _handle_help_callback(
            cb_query=cb_query,
            bot_token=bot_token,
            cb_chat_id=cb_chat_id,
            message_id=message_id,
            cb_id=cb_id,
        )
        return

    # Spec 046: Handle diagnostic report refresh callbacks (diag:ref:*)
    from app.telegram.fleet_cards import DIAG_PREFIX
    if cb_data.startswith(DIAG_PREFIX):
        _handle_diagnostic_callback(
            cb_query=cb_query,
            config=config,
            bot_token=bot_token,
            cb_chat_id=cb_chat_id,
            message_id=message_id,
            cb_id=cb_id,
            miners=miners,
            states=states,
            state_lock=state_lock,
            event_store=event_store,
        )
        return

    # Spec 050: Handle Post-Blackout Recovery callbacks (pbr:*)
    if cb_data.startswith("pbr:"):
        from app.governance.post_blackout_guard import process_post_blackout_callback
        tracker = getattr(mm, "_POST_BLACKOUT_TRACKER", None)
        process_post_blackout_callback(
            cb_data=cb_data,
            cb_id=cb_id,
            cb_chat_id=cb_chat_id,
            message_id=message_id,
            miners=miners,
            states=states,
            state_lock=state_lock,
            state_path=state_path,
            config=config,
            bot_token=bot_token,
            answer_cb_fn=answer_callback_query,
            edit_msg_fn=edit_message_text,
            save_state_fn=save_state,
            record_event_fn=lambda **kw: record_action_outcome(
                event_store,
                occurred_ts=time.time(),
                miner=kw.get("miner"),
                action=kw.get("action"),
                source=kw.get("source", "telegram_pbr"),
                ok=kw.get("ok", True),
                message=kw.get("message", ""),
            ),
            qa_mode=qa_mode,
            qa_allow_actions=qa_allow_actions,
            tracker=tracker,
            current_last_update_id=current_last_update_id,
        )
        return

    # Spec 052: Handle Maintenance Scheduler callbacks (sch:*)
    if cb_data.startswith("sch:"):
        answer_callback_query(bot_token, cb_id, text="Cancelando ventana...")
        active_scheduled_window = getattr(mm, "_ACTIVE_SCHEDULED_WINDOW", None)
        if active_scheduled_window and active_scheduled_window.stage not in (ScheduledStage.CANCELLED, ScheduledStage.COMPLETED):
            active_scheduled_window.stage = ScheduledStage.CANCELLED
            setattr(mm, "_ACTIVE_SCHEDULED_WINDOW", active_scheduled_window)
            with state_lock:
                _payload = _build_state_payload(states, current_last_update_id)
            _flush_state_payload(state_path, _payload)
            card = render_schedule_cancelled_card()
            if message_id is not None:
                edit_message_text(bot_token, str(cb_chat_id), message_id, card)
            if event_store is not None and event_store.available:
                record_action_outcome(
                    event_store,
                    occurred_ts=time.time(),
                    miner={"name": "FLOTA", "host": ""},
                    action="scheduled_maintenance_cancelled",
                    source="telegram_sch",
                    ok=True,
                    message=f"Ventana {active_scheduled_window.window_id} cancelada manualmente",
                )
            log(f"[SCHEDULER] Maintenance window {active_scheduled_window.window_id} cancelled by user.")
        else:
            if message_id is not None:
                edit_message_text(bot_token, str(cb_chat_id), message_id, "ℹ️ No hay ventana activa para cancelar.")
        return

    # --- Parse callback data ---
    action = parse_callback_data(cb_data)
    if action is None:
        log(f"CB_PARSE_FAIL cb_id={cb_id} data={cb_data[:40]!r}")
        answer_callback_query(bot_token, cb_id, text="⚠️ Acción desconocida.")
        return

    log(
        f"CB_DISPATCH action={action.action_type} miner={action.miner_id} "
        f"token={action.token or '-'} cb_id={cb_id}"
    )

    # --- noop: static informational button, just acknowledge ---
    if action.action_type == "noop":
        answer_callback_query(bot_token, cb_id)
        return

    # --- diag:<miner_id>: run diagnostic and send result ---
    if action.action_type == "diag":
        answer_callback_query(bot_token, cb_id, text="🩺 Obteniendo diagnóstico...")
        miner = resolve_miner(action.miner_id, miners)
        if not miner:
            send_telegram(
                bot_token,
                str(cb_chat_id),
                f"Diagnóstico: minero '{action.miner_id}' no encontrado.",
                "DIAGNOSE",
                "cb_diag_not_found",
                is_command=True,
            )
            return
        try:
            diagnosis_stale_seconds = float(config.get("diagnosis_stale_seconds", 900.0))
        except (TypeError, ValueError):
            diagnosis_stale_seconds = 900.0
        try:
            diagnosis_firmware_window_hours = float(
                config.get("diagnosis_firmware_window_hours", 24.0)
            )
        except (TypeError, ValueError):
            diagnosis_firmware_window_hours = 24.0
        try:
            diagnosis_collector_stale_seconds = float(
                config.get("diagnosis_collector_stale_seconds", 120.0)
            )
        except (TypeError, ValueError):
            diagnosis_collector_stale_seconds = 120.0
        diagnosis_text = build_miner_diagnosis_text(
            event_store,
            miners,
            action.miner_id,
            now_ts=time.time(),
            stale_after_seconds=diagnosis_stale_seconds,
            firmware_window_hours=diagnosis_firmware_window_hours,
            collector_stale_seconds=diagnosis_collector_stale_seconds,
        )
        send_telegram(
            bot_token,
            str(cb_chat_id),
            diagnosis_text,
            "DIAGNOSE",
            "cb_diag",
            is_command=True,
        )
        return

    # --- chart:<miner_id>: generate and send visual chart ---
    if action.action_type == "chart":
        answer_callback_query(bot_token, cb_id, text="📊 Generando gráfico...")
        miner = resolve_miner(action.miner_id, miners)
        if not miner:
            send_telegram(
                bot_token,
                str(cb_chat_id),
                f"Gráfico: minero '{action.miner_id}' no encontrado.",
                "CHART",
                "cb_chart_not_found",
                is_command=True,
            )
            return
        try:
            from app.telegram.charts import (
                fetch_miner_chart_data,
                render_miner_chart_png,
                build_chart_range_keyboard,
            )
            db_path = resolve_db_path(config)
            chart_data = fetch_miner_chart_data(db_path, miner["name"], hours=1.0)
            if chart_data["count"] == 0:
                send_telegram(
                    bot_token,
                    str(cb_chat_id),
                    f"Gráfico: no hay muestras recientes para {miner['name']}.",
                    "CHART",
                    "cb_chart_empty",
                    is_command=True,
                )
                return
            png_bytes = render_miner_chart_png(chart_data, hours=1.0)
            caption = f"📊 {chart_data['miner_name']} (1h) | Actual: {chart_data['rates'][-1]:.1f} TH/s | Max Temp: {chart_data['max_temp']:.0f}°C"
            kb = build_chart_range_keyboard(chart_data["miner_id"], current_hours=1.0)
            send_telegram_photo(bot_token, str(cb_chat_id), png_bytes, caption=caption, reply_markup=kb)
        except Exception as exc:
            log(f"CB_CHART_ERR miner={action.miner_id} exc={exc}")
            send_telegram(
                bot_token,
                str(cb_chat_id),
                f"Error al generar gráfico para {action.miner_id}: {exc}",
                "CHART",
                "cb_chart_err",
                is_command=True,
            )
        return

    # --- rb_req:<miner_id>: start 2-step reboot confirmation ---
    if action.action_type == "rb_req":
        token = token_registry.create_token(action.miner_id)
        if message_id is not None:
            edit_message_reply_markup(
                bot_token,
                str(cb_chat_id),
                message_id,
                build_confirmation_keyboard(action.miner_id, token),
            )
        answer_callback_query(
            bot_token,
            cb_id,
            text="⚠️ Confirmación requerida (expira en 60s)",
        )
        return

    # --- rb_ccl:<miner_id>: cancel reboot, restore original keyboard ---
    if action.action_type == "rb_ccl":
        token_registry.invalidate_miner(action.miner_id)
        if message_id is not None:
            if action.miner_id == "bulk_no_ok":
                edit_message_reply_markup(
                    bot_token,
                    str(cb_chat_id),
                    message_id,
                    build_settled_keyboard("❌ Reinicio Masivo Cancelado"),
                )
            else:
                edit_message_reply_markup(
                    bot_token,
                    str(cb_chat_id),
                    message_id,
                    build_alert_keyboard(action.miner_id),
                )
        answer_callback_query(bot_token, cb_id, text="❌ Reinicio cancelado")
        return

    # --- rb_cfm:<token>:<miner_id>: consume token and execute reboot ---
    if action.action_type == "rb_cfm":
        token_val = action.token or ""
        valid, _consumed_miner, status = token_registry.consume_token(token_val)
        if not valid:
            if status == "token_expired":
                answer_callback_query(
                    bot_token,
                    cb_id,
                    text="⏱️ El token de confirmación ha expirado.",
                    show_alert=True,
                )
            else:
                answer_callback_query(
                    bot_token,
                    cb_id,
                    text="⚠️ Confirmación inválida o ya usada.",
                    show_alert=True,
                )
            return

        if qa_mode and not qa_allow_actions:
            answer_callback_query(
                bot_token,
                cb_id,
                text="🚫 Reinicio bloqueado (modo QA).",
                show_alert=True,
            )
            log("CB_REBOOT_QA_BLOCK miner=%s" % action.miner_id)
            return

        if action.miner_id == "bulk_no_ok":
            # Bulk reboot execution for miners in NO-OK state
            if message_id is not None:
                edit_message_reply_markup(
                    bot_token,
                    str(cb_chat_id),
                    message_id,
                    build_settled_keyboard("✅ Reinicio Masivo Iniciado"),
                )
            answer_callback_query(bot_token, cb_id, text="🚀 Reinicio masivo iniciado")

            BULK_REBOOT_CAP = 5
            now_ts = time.time()
            targets_to_reboot = []
            with state_lock:
                for m in miners:
                    sk = f"{m['name']}|{m['host']}:{m.get('port', 4028)}"
                    st = states.get(sk)
                    if is_miner_no_ok(st):
                        targets_to_reboot.append(m)

            if len(targets_to_reboot) > BULK_REBOOT_CAP:
                targets_to_reboot = targets_to_reboot[:BULK_REBOOT_CAP]

            log(f"CB_BULK_REBOOT_START count={len(targets_to_reboot)}")
            rebooted_names = []
            for m in targets_to_reboot:
                ok, msg_result = run_hashcore_cli(
                    hashcore_cfg, m, "reboot", config, qa_mode, qa_allow_actions
                )
                record_action_outcome(
                    event_store,
                    occurred_ts=now_ts,
                    miner=m,
                    action="reboot",
                    source="manual_bulk",
                    ok=ok,
                    message=msg_result,
                )
                sk = f"{m['name']}|{m['host']}:{m.get('port', 4028)}"
                if ok:
                    rebooted_names.append(display_name(m['name']))
                    with state_lock:
                        st = states.get(sk)
                        if st:
                            st.last_manual_reboot_ts = now_ts
                            st.low_since_ts = None
            with state_lock:
                _payload = _build_state_payload(states, current_last_update_id)
            _flush_state_payload(state_path, _payload)
            log(f"CB_BULK_REBOOT_DONE targets={','.join(rebooted_names)}")
            return

        miner = resolve_miner(action.miner_id, miners)
        if not miner:
            answer_callback_query(
                bot_token,
                cb_id,
                text="❌ Minero no encontrado.",
                show_alert=True,
            )
            return

        # Update keyboard to settled state before executing reboot
        if message_id is not None:
            edit_message_reply_markup(
                bot_token,
                str(cb_chat_id),
                message_id,
                build_settled_keyboard("✅ Reinicio Iniciado (Enfriamiento 15m)"),
            )
        answer_callback_query(bot_token, cb_id, text="🔄 Iniciando reinicio...")

        now_ts = time.time()
        ok, msg_result = run_hashcore_cli(
            hashcore_cfg, miner, "reboot", config, qa_mode, qa_allow_actions
        )
        record_action_outcome(
            event_store,
            occurred_ts=now_ts,
            miner=miner,
            action="reboot",
            source="manual",
            ok=ok,
            message=msg_result,
        )
        state_key = f"{miner['name']}|{miner['host']}:{miner['port']}"
        if ok:
            with state_lock:
                state = states.get(state_key)
                if state:
                    state.last_manual_reboot_ts = now_ts
                    state.low_since_ts = None
                _payload = _build_state_payload(states, current_last_update_id)
            _flush_state_payload(state_path, _payload)
            log(
                f"CB_REBOOT_OK miner={display_name(miner['name'])} "
                f"host={miner['host']}"
            )
        else:
            send_telegram(
                bot_token,
                str(cb_chat_id),
                f"❌ Reinicio FAIL: {display_name(miner['name'])} — {msg_result}",
                "REBOOT",
                "cb_reboot_fail",
                is_command=True,
            )
            log(
                f"CB_REBOOT_FAIL miner={display_name(miner['name'])} "
                f"msg={msg_result}"
            )
        return

    # --- flash_ccl:<miner_id>: cancel flash confirmation ---
    if action.action_type == "flash_ccl":
        answer_callback_query(bot_token, cb_id, text="❌ Flasheo cancelado.")
        if message_id is not None:
            edit_message_text(bot_token, str(cb_chat_id), message_id, f"❌ Flasheo cancelado para {action.miner_id}.")
        return

    # --- flash_cfm:<miner_id>: execute flash pipeline ---
    if action.action_type == "flash_cfm":
        answer_callback_query(bot_token, cb_id, text="🚀 Iniciando flasheo VNish...")
        miner = resolve_miner(action.miner_id, miners)
        if not miner:
            if message_id is not None:
                edit_message_text(bot_token, str(cb_chat_id), message_id, f"❌ Minero '{action.miner_id}' no encontrado.")
            return

        miner_raw_name = miner.get("name", "")
        name = display_name(miner_raw_name)
        host = miner.get("host", "")
        norm = normalize_miner_name(miner_raw_name)

        from app.telegram.commands.flash import is_flash_in_progress, run_flash_and_provision_pipeline, _RUNNING_FLASH_JOBS, _FLASH_JOBS_LOCK
        from app.telegram.context import TelegramRequestContext

        if is_flash_in_progress(norm):
            if message_id is not None:
                edit_message_text(bot_token, str(cb_chat_id), message_id, f"⏳ Ya hay un flasheo en progreso para {name}.")
            return

        if message_id is not None:
            edit_message_text(bot_token, str(cb_chat_id), message_id, f"🚀 *Flasheo VNish iniciado en background para {name}* (`{host}`)...\nRecibirá actualizaciones por fases.")

        ctx = TelegramRequestContext(
            config=config,
            bot_token=bot_token,
            chat_id=str(cb_chat_id),
            miners=miners,
            states=states,
            state_lock=state_lock,
            state_path=state_path,
            current_last_update_id=current_last_update_id,
            hashcore_cfg=hashcore_cfg,
            event_store=event_store,
            qa_mode=qa_mode,
            qa_allow_actions=qa_allow_actions,
            token_registry=token_registry,
        )
        vnish_pw = str(config.get("vnish_api_password", "admin"))
        th = threading.Thread(
            target=run_flash_and_provision_pipeline,
            args=(host, norm, ctx),
            kwargs={"vnish_pw": vnish_pw},
            name=f"FlashWorker_{norm}",
            daemon=True,
        )
        with _FLASH_JOBS_LOCK:
            _RUNNING_FLASH_JOBS[norm] = th
        th.start()
        return

    # --- snz:<miner_id>:<minutes>: maintenance snooze ---
    if action.action_type == "snz":
        miner = resolve_miner(action.miner_id, miners)
        if not miner:
            answer_callback_query(
                bot_token,
                cb_id,
                text="❌ Minero no encontrado.",
                show_alert=True,
            )
            return
        try:
            minutes = float(action.param) if action.param else 60.0
        except ValueError:
            minutes = 60.0
        from app.telegram.snooze import MIN_SNOOZE_MINUTES, MAX_SNOOZE_MINUTES
        minutes = max(MIN_SNOOZE_MINUTES, min(MAX_SNOOZE_MINUTES, minutes))
        now_ts = time.time()
        snooze_until = now_ts + (minutes * 60.0)
        state_key = f"{miner['name']}|{miner['host']}:{miner['port']}"
        with state_lock:
            st = states.get(state_key)
            if st:
                st.snooze_until_ts = snooze_until
            _payload = _build_state_payload(states, current_last_update_id)
        _flush_state_payload(state_path, _payload)
        disp_name = display_name(miner["name"])
        answer_callback_query(
            bot_token,
            cb_id,
            text=f"🔕 {disp_name} silenciado por {int(minutes)}m",
        )
        if message_id is not None:
            edit_message_reply_markup(
                bot_token,
                str(cb_chat_id),
                message_id,
                build_settled_keyboard(f"🔕 Silenciado ({int(minutes)}m)"),
            )
        log(f"CB_SNOOZE miner={disp_name} minutes={minutes} until={snooze_until}")
        return

    # --- chart_range:<target>:<hours>: update chart in-place ---
    if action.action_type == "chart_range":
        if message_id is None:
            answer_callback_query(bot_token, cb_id, text="⚠️ No se puede editar el gráfico.")
            return

        try:
            hours = max(0.25, min(168.0, float(action.param or "1.0")))
        except ValueError:
            hours = 1.0

        target = action.miner_id.strip()
        target_lower = target.lower()

        try:
            from app.telegram.charts import (
                fetch_miner_chart_data,
                fetch_fleet_chart_data,
                fetch_group_chart_data,
                render_miner_chart_png,
                render_fleet_chart_png,
                render_group_chart_png,
                build_chart_range_keyboard,
            )
            db_path = resolve_db_path(config)

            if target_lower in ("fleet", "all"):
                fleet_data = fetch_fleet_chart_data(db_path, miners, hours=hours)
                if fleet_data["count"] == 0:
                    answer_callback_query(
                        bot_token, cb_id, text=f"No hay muestras de flota en {hours:.0f}h.", show_alert=True
                    )
                    return
                png_bytes = render_fleet_chart_png(fleet_data, hours=hours)
                caption = f"📊 Flota completa ({hours:.0f}h) — {fleet_data['count']} mineros activos"
                kb = build_chart_range_keyboard("fleet", current_hours=hours)
            else:
                groups = {
                    (_m.get("electrical_group") or _m.get("group") or "").strip().lower()
                    for _m in miners
                }
                groups.discard("")
                matched_group = None
                for grp in groups:
                    if target_lower == grp or target_lower == grp.replace("_", "") or target_lower in grp:
                        matched_group = grp
                        break

                if matched_group:
                    group_data = fetch_group_chart_data(db_path, matched_group, miners, hours=hours)
                    if group_data["count"] == 0:
                        answer_callback_query(
                            bot_token,
                            cb_id,
                            text=f"No hay muestras para grupo {matched_group} en {hours:.0f}h.",
                            show_alert=True,
                        )
                        return
                    png_bytes = render_group_chart_png(group_data, hours=hours)
                    caption = (
                        f"📊 Grupo {matched_group.upper()} ({hours:.0f}h) — "
                        f"{group_data['count']}/{group_data['total_miners']} mineros activos"
                    )
                    kb = build_chart_range_keyboard(matched_group, current_hours=hours)
                else:
                    miner = resolve_miner(target, miners)
                    if not miner:
                        answer_callback_query(
                            bot_token, cb_id, text=f"Minero '{target}' no encontrado.", show_alert=True
                        )
                        return
                    chart_data = fetch_miner_chart_data(db_path, miner["name"], hours=hours)
                    if chart_data["count"] == 0:
                        answer_callback_query(
                            bot_token,
                            cb_id,
                            text=f"No hay muestras para {miner['name']} en {hours:.0f}h.",
                            show_alert=True,
                        )
                        return
                    png_bytes = render_miner_chart_png(chart_data, hours=hours)
                    caption = (
                        f"📊 {chart_data['miner_name']} ({hours:.0f}h) | "
                        f"Actual: {chart_data['rates'][-1]:.1f} TH/s | "
                        f"Max Temp: {chart_data['max_temp']:.0f}°C"
                    )
                    kb = build_chart_range_keyboard(chart_data["miner_id"], current_hours=hours)

            ok = edit_telegram_photo(
                bot_token,
                str(cb_chat_id),
                message_id,
                png_bytes,
                caption=caption,
                reply_markup=kb,
            )
            if ok:
                range_map = {1.0: "1h", 6.0: "6h", 24.0: "24h", 168.0: "7d"}
                range_label = range_map.get(hours, f"{int(hours)}h" if hours < 24 else f"{int(hours / 24)}d")
                answer_callback_query(bot_token, cb_id, text=f"Rango actualizado: {range_label}")
            else:
                answer_callback_query(
                    bot_token, cb_id, text="Error al actualizar gráfico.", show_alert=True
                )
        except Exception as exc:
            log(f"CB_CHART_RANGE_ERR target={target} exc={exc}")
            answer_callback_query(
                bot_token, cb_id, text=f"Error: {exc}", show_alert=True
            )
        return

    # Unknown action type (forward-compat: just ack)
    log(f"CB_UNHANDLED action_type={action.action_type} cb_id={cb_id}")
    answer_callback_query(bot_token, cb_id)
