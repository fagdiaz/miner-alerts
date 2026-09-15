"""Help, Menu/Dashboard, and Daily Digest Commands (Spec 058)."""

from __future__ import annotations

import logging
import time
from typing import Any, List, Optional

from app.telegram.commands.base import BaseCommandHandler
from app.telegram.context import TelegramRequestContext

logger = logging.getLogger("miner-alerts")


class HelpCommand(BaseCommandHandler):
    name = "help"
    aliases = ["ayuda"]
    description = "Centro de ayuda interactivo categorizado y detalle de comandos."

    def handle(
        self,
        context: TelegramRequestContext,
        args: List[str],
        update_id: Optional[int] = None,
        from_id: Optional[Any] = None,
        message_id: Optional[int] = None,
        **kwargs: Any,
    ) -> bool:
        from app.telegram.help_center import render_help_command_detail, render_help_home

        cmd_start = time.monotonic()
        if args:
            msg, kb = render_help_command_detail(args[0])
        else:
            msg, kb = render_help_home()

        context.send_message(
            msg,
            reply_markup=kb,
            msg_type="HELP",
            dedup_key="cmd_help",
            dbg_cmd="help",
            dbg_update_id=update_id,
        )
        return True


class MenuCommand(BaseCommandHandler):
    name = "menu"
    aliases = ["start", "panel"]
    description = "Panel táctil Mobile-First Command Center para control operativo."

    def handle(
        self,
        context: TelegramRequestContext,
        args: List[str],
        update_id: Optional[int] = None,
        from_id: Optional[Any] = None,
        message_id: Optional[int] = None,
        **kwargs: Any,
    ) -> bool:
        from app.telegram.command_center import render_main_dashboard

        states_snapshot = context.get_states_snapshot()
        dash_text, dash_markup = render_main_dashboard(
            states_snapshot,
            context.config,
            context.miners,
        )
        context.send_message(
            dash_text,
            reply_markup=dash_markup,
            msg_type="MENU",
            dedup_key="cmd_menu",
            dbg_cmd="menu",
            dbg_update_id=update_id,
        )
        return True


class DigestCommand(BaseCommandHandler):
    name = "digest"
    aliases = ["summary", "resumen_diario"]
    description = "Resumen diario de producción, reinicios, eficiencia y anomalías."

    def handle(
        self,
        context: TelegramRequestContext,
        args: List[str],
        update_id: Optional[int] = None,
        from_id: Optional[Any] = None,
        message_id: Optional[int] = None,
        **kwargs: Any,
    ) -> bool:
        from app.telegram.daily_digest import fetch_daily_digest_metrics, format_daily_digest
        from app.telegram.fleet_cards import build_diagnostic_keyboard
        from app.miner_monitor import resolve_db_path

        db_p = resolve_db_path(context.config)
        b_root = context.config.get("backup_root", "backups")
        with context.state_lock:
            digest_metrics = fetch_daily_digest_metrics(
                db_path=db_p,
                miners=context.miners,
                now_ts=time.time(),
                backup_root=b_root,
                states=context.states,
            )
        digest_msg = format_daily_digest(digest_metrics)
        digest_kb = build_diagnostic_keyboard("digest")
        context.send_message(
            digest_msg,
            reply_markup=digest_kb,
            msg_type="DIGEST",
            dedup_key="cmd_digest",
            dbg_cmd="digest",
            dbg_update_id=update_id,
        )
        return True
