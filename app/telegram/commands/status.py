"""Status and Fleet Overview Command Handlers (Spec 058)."""

from __future__ import annotations

import time
from typing import Any, List, Optional

from app.telegram.commands.base import BaseCommandHandler
from app.telegram.context import TelegramRequestContext


class StatusCommand(BaseCommandHandler):
    name = "status"
    aliases = ["estado", "resumen", "metrics"]
    description = "Muestra la tarjeta Mobile-First con el estado consolidado de la flota."

    def handle(
        self,
        context: TelegramRequestContext,
        args: List[str],
        update_id: Optional[int] = None,
        from_id: Optional[Any] = None,
        message_id: Optional[int] = None,
        **kwargs: Any,
    ) -> bool:
        from app.telegram.fleet_cards import render_fleet_status_card
        from app.miner_monitor import now_str, log_pid

        states_snapshot = context.get_states_snapshot()
        status_text, status_markup = render_fleet_status_card(
            states_snapshot, config=context.config, miners=context.miners, now_ts_str=now_str()
        )
        cmd_start = time.monotonic()
        context.send_message(
            status_text,
            reply_markup=status_markup,
            msg_type="STATUS",
            dedup_key="cmd_status",
        )
        if context.qa_mode:
            log_pid(f"[TEL] command=status duration={time.monotonic() - cmd_start:.3f}s")
        return True


class InfoCommand(BaseCommandHandler):
    name = "info"
    aliases = ["detalle"]
    description = "Detalle resumido de telemetría por minero."

    def handle(
        self,
        context: TelegramRequestContext,
        args: List[str],
        update_id: Optional[int] = None,
        from_id: Optional[Any] = None,
        message_id: Optional[int] = None,
        **kwargs: Any,
    ) -> bool:
        from app.miner_monitor import display_name, now_str

        states_snapshot = context.get_states_snapshot()
        lines = [f"ℹ️ *INFO DE FLOTA* ({now_str()})"]
        for miner in context.miners:
            name_disp = display_name(miner.get("name", ""))
            host = miner.get("host", "")
            port = miner.get("port", 4028)
            state_key = f"{miner.get('name','')}|{host}:{port}"
            st = states_snapshot.get(state_key)
            state_str = getattr(st, "state", "UNKNOWN") if st else "UNKNOWN"
            rate = getattr(st, "last_rate_ths", None)
            rate_str = f"{rate:.1f} TH/s" if rate is not None else "N/D"
            lines.append(f"• *{name_disp}* ({host}): `{state_str}` | `{rate_str}`")

        context.send_message("\n".join(lines), msg_type="INFO", dedup_key="cmd_info")
        return True
