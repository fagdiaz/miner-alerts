"""Maintenance, Snooze, Shutdown, Resume, and Scheduling Commands (Spec 058)."""

from __future__ import annotations

import logging
import time
from typing import Any, List, Optional

from app.telegram.commands.base import BaseCommandHandler
from app.telegram.context import TelegramRequestContext

logger = logging.getLogger("miner-alerts")


class SnoozeCommand(BaseCommandHandler):
    name = "snooze"
    aliases = ["silenciar"]
    description = "Silencia alertas y autorreinicios para uno o todos los mineros por N minutos."

    def handle(
        self,
        context: TelegramRequestContext,
        args: List[str],
        update_id: Optional[int] = None,
        from_id: Optional[Any] = None,
        message_id: Optional[int] = None,
        **kwargs: Any,
    ) -> bool:
        from app.miner_monitor import resolve_miner, display_name
        from app.telegram.snooze import parse_snooze_args, format_snooze_expiry_time

        cmd_arg = " ".join(args).strip()
        target, minutes = parse_snooze_args(cmd_arg)
        if not target:
            context.send_message(
                "Uso: /snooze <minero|all> [minutos]\nEjemplo: /snooze 23 60 (por defecto 60 min, máx 1440m/24h)",
                msg_type="SNOOZE",
                dedup_key="cmd_snooze_usage",
                dbg_cmd="snooze",
                dbg_update_id=update_id,
            )
            return True

        if target.lower() in ("all", "fleet"):
            now_ts = time.time()
            until_ts = now_ts + (minutes * 60.0)
            exp_str = format_snooze_expiry_time(until_ts)
            with context.state_lock:
                for m in context.miners:
                    key = f"{m['name']}|{m['host']}:{m.get('port', 4028)}"
                    st = context.states.get(key)
                    if st:
                        st.snooze_until_ts = until_ts
            context.persist_state_safely()
            context.send_message(
                f"🔕 Toda la flota silenciada durante {int(minutes)}m (hasta las {exp_str}). Alertas y autorreinicios suspendidos.",
                msg_type="SNOOZE",
                dedup_key="cmd_snooze_all",
                dbg_cmd="snooze",
                dbg_update_id=update_id,
            )
            return True

        miner = resolve_miner(target, context.miners)
        if not miner:
            avail = ", ".join(display_name(m["name"]) for m in context.miners)
            context.send_message(
                f"Minero '{target}' no encontrado.\nMineros disponibles: {avail}",
                msg_type="SNOOZE",
                dedup_key="cmd_snooze_not_found",
                dbg_cmd="snooze",
                dbg_update_id=update_id,
            )
            return True

        now_ts = time.time()
        until_ts = now_ts + (minutes * 60.0)
        exp_str = format_snooze_expiry_time(until_ts)
        state_key = f"{miner['name']}|{miner['host']}:{miner.get('port', 4028)}"
        with context.state_lock:
            st = context.states.get(state_key)
            if st:
                st.snooze_until_ts = until_ts
        context.persist_state_safely()
        d_name = display_name(miner["name"])
        context.send_message(
            f"🔕 Minero {miner['name']} ({d_name}) silenciado durante {int(minutes)}m (hasta las {exp_str}). Alertas y autorreinicios suspendidos.",
            msg_type="SNOOZE",
            dedup_key="cmd_snooze_ok",
            dbg_cmd="snooze",
            dbg_update_id=update_id,
        )
        return True


class UnsnoozeCommand(BaseCommandHandler):
    name = "unsnooze"
    aliases = ["desilenciar"]
    description = "Reactiva las alertas y autorreinicios previamente silenciados."

    def handle(
        self,
        context: TelegramRequestContext,
        args: List[str],
        update_id: Optional[int] = None,
        from_id: Optional[Any] = None,
        message_id: Optional[int] = None,
        **kwargs: Any,
    ) -> bool:
        from app.miner_monitor import resolve_miner, display_name

        target = " ".join(args).strip()
        if not target:
            context.send_message(
                "Uso: /unsnooze <minero|all>\nEjemplo: /unsnooze 23",
                msg_type="SNOOZE",
                dedup_key="cmd_unsnooze_usage",
                dbg_cmd="unsnooze",
                dbg_update_id=update_id,
            )
            return True

        if target.lower() in ("all", "fleet"):
            with context.state_lock:
                for m in context.miners:
                    key = f"{m['name']}|{m['host']}:{m.get('port', 4028)}"
                    st = context.states.get(key)
                    if st:
                        st.snooze_until_ts = None
            context.persist_state_safely()
            context.send_message(
                "🔔 Alertas y autorreinicios reactivados para toda la flota.",
                msg_type="SNOOZE",
                dedup_key="cmd_unsnooze_all",
                dbg_cmd="unsnooze",
                dbg_update_id=update_id,
            )
            return True

        miner = resolve_miner(target, context.miners)
        if not miner:
            avail = ", ".join(display_name(m["name"]) for m in context.miners)
            context.send_message(
                f"Minero '{target}' no encontrado.\nMineros disponibles: {avail}",
                msg_type="SNOOZE",
                dedup_key="cmd_unsnooze_not_found",
                dbg_cmd="unsnooze",
                dbg_update_id=update_id,
            )
            return True

        state_key = f"{miner['name']}|{miner['host']}:{miner.get('port', 4028)}"
        with context.state_lock:
            st = context.states.get(state_key)
            if st:
                st.snooze_until_ts = None
        context.persist_state_safely()
        d_name = display_name(miner["name"])
        context.send_message(
            f"🔔 Alertas y autorreinicios reactivados para {miner['name']} ({d_name}).",
            msg_type="SNOOZE",
            dedup_key="cmd_unsnooze_ok",
            dbg_cmd="unsnooze",
            dbg_update_id=update_id,
        )
        return True


class SnoozedCommand(BaseCommandHandler):
    name = "snoozed"
    aliases = ["silenciados"]
    description = "Lista todos los mineros actualmente silenciados y tiempo restante."

    def handle(
        self,
        context: TelegramRequestContext,
        args: List[str],
        update_id: Optional[int] = None,
        from_id: Optional[Any] = None,
        message_id: Optional[int] = None,
        **kwargs: Any,
    ) -> bool:
        from app.telegram.snooze import render_snoozed_list

        states_snap = context.get_states_snapshot()
        text = render_snoozed_list(states_snap, context.miners, time.time())
        context.send_message(
            text,
            msg_type="SNOOZE",
            dedup_key="cmd_snoozed_list",
            dbg_cmd="snoozed",
            dbg_update_id=update_id,
        )
        return True


class ShutdownCommand(BaseCommandHandler):
    name = "shutdown"
    aliases = ["stop", "apagar", "parada"]
    description = "Parada segura de minado con purga térmica previa y rampa acústica baja."

    def handle(
        self,
        context: TelegramRequestContext,
        args: List[str],
        update_id: Optional[int] = None,
        from_id: Optional[Any] = None,
        message_id: Optional[int] = None,
        **kwargs: Any,
    ) -> bool:
        from app.telegram.command_center import (
            render_shutdown_menu,
            render_shutdown_confirmation,
        )
        from app.governance.fleet_shutdown import (
            extract_miner_identifier,
            resolve_selected_miners,
        )

        states_snapshot = context.get_states_snapshot()
        miners = context.miners

        if not args:
            sd_text, sd_markup = render_shutdown_menu(states_snapshot, miners, selected_mask="0" * len(miners))
            context.send_message(
                sd_text,
                reply_markup=sd_markup,
                msg_type="SHUTDOWN",
                dedup_key="cmd_shutdown_menu",
                dbg_cmd="shutdown",
                dbg_update_id=update_id,
            )
            return True

        arg_str = " ".join(args).strip().lower()
        if any(x in arg_str for x in ("all", "granja", "todos")):
            mask = "1" * len(miners)
        else:
            bit_list = ["0"] * len(miners)
            for idx, m in enumerate(miners):
                m_id = extract_miner_identifier(m)
                m_name = str(m.get("name", "")).lower()
                m_host = str(m.get("host", "")).lower()
                for a in args:
                    a_clean = a.strip().lower().replace("s19jpro-", "").replace("s19-", "")
                    if a_clean == m_id.lower() or a_clean in m_name or a_clean in m_host:
                        bit_list[idx] = "1"
            mask = "".join(bit_list)

        if mask.count("1") == 0:
            context.send_message(
                "⚠️ No se identificaron mineros válidos.\nUsá `/shutdown` para abrir el selector táctil.",
                msg_type="SHUTDOWN",
                dedup_key="cmd_shutdown_not_found",
                dbg_cmd="shutdown",
                dbg_update_id=update_id,
            )
            return True

        selected_miners = resolve_selected_miners(mask, miners)
        selected_ids = [extract_miner_identifier(m) for m in selected_miners]
        token = ""
        if context.token_registry:
            token = context.token_registry.create_token(mask, action="shutdown")
        sd_text, sd_markup = render_shutdown_confirmation(selected_ids, token, mask)
        context.send_message(
            sd_text,
            reply_markup=sd_markup,
            msg_type="SHUTDOWN",
            dedup_key="cmd_shutdown_confirm",
            dbg_cmd="shutdown",
            dbg_update_id=update_id,
        )
        return True


class ResumeCommand(BaseCommandHandler):
    name = "resume"
    aliases = ["reanudar"]
    description = "Reanudación controlada de minado tras una parada de mantenimiento."

    def handle(
        self,
        context: TelegramRequestContext,
        args: List[str],
        update_id: Optional[int] = None,
        from_id: Optional[Any] = None,
        message_id: Optional[int] = None,
        **kwargs: Any,
    ) -> bool:
        from app.telegram.command_center import render_resume_menu
        from app.governance.fleet_shutdown import (
            execute_parallel_resume,
            extract_miner_identifier,
            render_resume_success_card,
            render_shutdown_error_card,
        )

        states_snapshot = context.get_states_snapshot()
        miners = context.miners

        if not args:
            res_text, res_markup = render_resume_menu(states_snapshot, miners)
            context.send_message(
                res_text,
                reply_markup=res_markup,
                msg_type="RESUME",
                dedup_key="cmd_resume_menu",
                dbg_cmd="resume",
                dbg_update_id=update_id,
            )
            return True

        arg_str = " ".join(args).strip().lower()
        if any(x in arg_str for x in ("all", "granja", "todos")):
            mask = "1" * len(miners)
        else:
            bit_list = ["0"] * len(miners)
            for idx, m in enumerate(miners):
                m_id = extract_miner_identifier(m)
                m_name = str(m.get("name", "")).lower()
                m_host = str(m.get("host", "")).lower()
                for a in args:
                    a_clean = a.strip().lower().replace("s19jpro-", "").replace("s19-", "")
                    if a_clean == m_id.lower() or a_clean in m_name or a_clean in m_host:
                        bit_list[idx] = "1"
            mask = "".join(bit_list)

        if mask.count("1") == 0:
            context.send_message(
                "⚠️ No se identificaron mineros válidos.\nUsá `/resume` para ver el selector.",
                msg_type="RESUME",
                dedup_key="cmd_resume_not_found",
                dbg_cmd="resume",
                dbg_update_id=update_id,
            )
            return True

        from app.governance.fleet_shutdown import resolve_selected_miners
        target_miners = resolve_selected_miners(mask, miners)
        vnish_pw = str(context.config.get("vnish_api_password", "admin"))
        res_ok, results = execute_parallel_resume(
            miners=target_miners,
            states=context.states,
            state_lock=context.state_lock,
            vnish_password=vnish_pw,
        )
        context.persist_state_safely()

        if res_ok:
            card_text, card_markup = render_resume_success_card(results)
            context.send_message(
                card_text,
                reply_markup=card_markup,
                msg_type="RESUME",
                dedup_key="cmd_resume_ok",
                dbg_cmd="resume",
                dbg_update_id=update_id,
            )
        else:
            card_text, card_markup = render_shutdown_error_card("Reanudar Minado", results)
            context.send_message(
                card_text,
                reply_markup=card_markup,
                msg_type="ERROR",
                dedup_key="cmd_resume_err",
                dbg_cmd="resume",
                dbg_update_id=update_id,
            )
        return True


class ScheduleMaintenanceCommand(BaseCommandHandler):
    name = "schedule_maintenance"
    aliases = ["schedule", "programar"]
    description = "Programa una ventana de mantenimiento futuro con parada y reanudación automática."

    def handle(
        self,
        context: TelegramRequestContext,
        args: List[str],
        update_id: Optional[int] = None,
        from_id: Optional[Any] = None,
        message_id: Optional[int] = None,
        **kwargs: Any,
    ) -> bool:
        import app.miner_monitor as mm
        from app.governance.scheduled_maintenance import (
            ScheduledStage,
            parse_schedule_expression,
            render_schedule_confirmation_card,
            render_scheduled_status_card,
        )
        from app.miner_monitor import record_action_outcome, log

        now_ts = time.time()
        if not args:
            context.send_message(
                "ℹ️ *Uso de /schedule_maintenance*:\n`/schedule_maintenance <tiempo> [duracion]`\n\n"
                "Ejemplos:\n• `/schedule_maintenance in 30m 2h`\n• `/schedule_maintenance in 2h`\n"
                "• `/schedule_maintenance 2026-09-12 08:00 3h`\n• `/schedule_maintenance 14:00 2h`",
                msg_type="HELP",
                dedup_key="cmd_schedule_usage",
                dbg_cmd="schedule_maintenance",
                dbg_update_id=update_id,
            )
            return True

        win = mm._ACTIVE_SCHEDULED_WINDOW
        if win and win.stage in (
            ScheduledStage.PENDING,
            ScheduledStage.PRE_RAMP_TIER_1,
            ScheduledStage.PRE_RAMP_TIER_2,
        ) and now_ts < win.start_ts:
            card_active, markup_active = render_scheduled_status_card(win, now_ts)
            context.send_message(
                f"⚠️ *Ya existe una ventana programada*:\n\n{card_active}",
                reply_markup=markup_active,
                msg_type="WARNING",
                dedup_key="cmd_schedule_conflict",
                dbg_cmd="schedule_maintenance",
                dbg_update_id=update_id,
            )
            return True

        time_expr = args[0]
        dur_expr = args[1] if len(args) > 1 else None
        user_sender = str(from_id or context.chat_id)
        ok, new_win, err_msg = parse_schedule_expression(
            time_expr=time_expr,
            duration_expr=dur_expr,
            now_ts=now_ts,
            user_id=user_sender,
        )
        if not ok or new_win is None:
            context.send_message(
                f"❌ *Error al programar*:\n{err_msg}",
                msg_type="ERROR",
                dedup_key="cmd_schedule_error",
                dbg_cmd="schedule_maintenance",
                dbg_update_id=update_id,
            )
            return True

        mm._ACTIVE_SCHEDULED_WINDOW = new_win
        context.persist_state_safely()
        confirm_card, confirm_markup = render_schedule_confirmation_card(new_win)
        context.send_message(
            confirm_card,
            reply_markup=confirm_markup,
            msg_type="SCHEDULED",
            dedup_key="cmd_schedule_confirm",
            dbg_cmd="schedule_maintenance",
            dbg_update_id=update_id,
        )
        if context.event_store and context.event_store.available:
            record_action_outcome(
                context.event_store,
                occurred_ts=now_ts,
                miner={"name": "FLOTA", "host": ""},
                action="scheduled_maintenance_created",
                source="telegram",
                ok=True,
                message=f"Ventana programada: inicio {new_win.start_ts}, duracion {new_win.duration_seconds}s",
            )
        log(f"[SCHEDULER] Maintenance window scheduled: id={new_win.window_id} start_ts={new_win.start_ts} dur={new_win.duration_seconds}s by={user_sender}")
        return True


class ScheduledCommand(BaseCommandHandler):
    name = "scheduled"
    aliases = ["programado", "mantenimientos"]
    description = "Consulta el estado y progreso de la ventana de mantenimiento programada."

    def handle(
        self,
        context: TelegramRequestContext,
        args: List[str],
        update_id: Optional[int] = None,
        from_id: Optional[Any] = None,
        message_id: Optional[int] = None,
        **kwargs: Any,
    ) -> bool:
        import app.miner_monitor as mm
        from app.governance.scheduled_maintenance import render_scheduled_status_card

        now_ts = time.time()
        card_text, reply_markup = render_scheduled_status_card(mm._ACTIVE_SCHEDULED_WINDOW, now_ts)
        context.send_message(
            card_text,
            reply_markup=reply_markup,
            msg_type="SCHEDULED",
            dedup_key="cmd_scheduled_status",
            dbg_cmd="scheduled",
            dbg_update_id=update_id,
        )
        return True
