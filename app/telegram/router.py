"""Telegram Dispatcher and Router Subsystem (Spec 058).

Routes parsed text commands and inline keyboard callbacks to dedicated,
decoupled command handlers with strict authorization, error isolation,
and No-Silence guarantees.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.telegram.commands.base import BaseCommandHandler
from app.telegram.context import TelegramRequestContext

logger = logging.getLogger("miner-alerts")


class TelegramCommandRouter:
    """Registry and dispatcher for Telegram text commands."""

    def __init__(self) -> None:
        self._handlers: List[BaseCommandHandler] = []
        self._command_map: Dict[str, BaseCommandHandler] = {}

    def register(self, handler: BaseCommandHandler) -> TelegramCommandRouter:
        """Register a command handler and bind its canonical name and aliases."""
        self._handlers.append(handler)
        self._command_map[handler.name.lower()] = handler
        for alias in handler.aliases:
            self._command_map[alias.lower()] = handler
        return self

    def find_handler(self, cmd_token: str) -> Optional[BaseCommandHandler]:
        """Find handler by command token or alias."""
        clean = (cmd_token or "").strip().lower()
        if clean.startswith("/"):
            clean = clean[1:]
        if "@" in clean:
            clean = clean.split("@", 1)[0]
        h = self._command_map.get(clean)
        if h:
            return h
        for handler in self._handlers:
            if handler.matches(clean):
                return handler
        return None

    def dispatch(
        self,
        cmd_name: str,
        args: List[str],
        context: TelegramRequestContext,
        update_id: Optional[int] = None,
        from_id: Optional[Any] = None,
        message_id: Optional[int] = None,
    ) -> bool:
        """Dispatch a parsed command to its registered handler."""
        handler = self.find_handler(cmd_name)
        if not handler:
            return False

        # Authorization check
        if not handler.check_authorization(context, from_id):
            logger.warning(
                f"[TG_AUTH_FAIL] Unauthorized command /{cmd_name} from_id={from_id} "
                f"expected={context.chat_id} update_id={update_id}"
            )
            return True

        # Execution with error boundary
        try:
            return handler.handle(
                context=context,
                args=args,
                update_id=update_id,
                from_id=from_id,
                message_id=message_id,
                cmd_name=cmd_name,
            )
        except Exception as exc:
            logger.error(
                f"[TG_CMD_ERR] Error executing command /{cmd_name}: {exc}",
                exc_info=True,
            )
            # Enforce No-Silence Policy
            context.send_message(
                f"⚠️ *Error ejecutando /{cmd_name}*: Ocurrió una excepción interna.\n`{type(exc).__name__}: {exc}`",
                msg_type="ERROR",
            )
            return True


class TelegramCallbackRouter:
    """Dispatcher for inline keyboard callbacks."""

    @staticmethod
    def dispatch(
        cb_query: dict,
        context: TelegramRequestContext,
    ) -> None:
        """Route callback queries to dedicated subsystem handlers."""
        cb_data = str(cb_query.get("data") or "")
        cb_id = str(cb_query.get("id") or "")
        from_user = cb_query.get("from") or {}
        from_id = from_user.get("id")
        msg = cb_query.get("message") or {}
        message_id = msg.get("message_id")
        cb_chat_id = (msg.get("chat") or {}).get("id") or context.chat_id

        # Strict authentication
        try:
            authorized = from_id is not None and int(from_id) == int(context.chat_id)
        except (TypeError, ValueError):
            authorized = False

        from app.miner_monitor import answer_callback_query

        if not authorized:
            logger.warning(f"CB_AUTH_FAIL cb_id={cb_id} from_id={from_id} expected={context.chat_id}")
            answer_callback_query(context.bot_token, cb_id, text="⛔ No autorizado.", show_alert=True)
            return

        # 1. Command Center callbacks (cc:*)
        if cb_data.startswith("cc:"):
            from app.miner_monitor import _handle_command_center_callback
            _handle_command_center_callback(
                cb_query,
                config=context.config,
                bot_token=context.bot_token,
                chat_id=str(context.chat_id),
                cb_chat_id=cb_chat_id,
                message_id=message_id,
                cb_id=cb_id,
                miners=context.miners,
                states=context.states,
                state_lock=context.state_lock,
                state_path=context.state_path,
                current_last_update_id=context.current_last_update_id,
                hashcore_cfg=context.hashcore_cfg,
                event_store=context.event_store,
                qa_mode=context.qa_mode,
                qa_allow_actions=context.qa_allow_actions,
                token_registry=context.token_registry,
            )
            return

        # 2. Help callbacks (help:*)
        if cb_data.startswith("help:"):
            from app.miner_monitor import _handle_help_callback
            _handle_help_callback(
                cb_query,
                bot_token=context.bot_token,
                cb_chat_id=cb_chat_id,
                message_id=message_id,
                cb_id=cb_id,
            )
            return

        # 3. Diagnostic callbacks (diag:*)
        if cb_data.startswith("diag:"):
            from app.miner_monitor import _handle_diagnostic_callback
            _handle_diagnostic_callback(
                cb_query,
                config=context.config,
                bot_token=context.bot_token,
                cb_chat_id=cb_chat_id,
                message_id=message_id,
                cb_id=cb_id,
                miners=context.miners,
                states=context.states,
                state_lock=context.state_lock,
                event_store=context.event_store,
            )
            return

        # 4. Discrete action callbacks (rb_*, snz:*, chart:*)
        from app.miner_monitor import _handle_callback_query
        _handle_callback_query(
            cb_query,
            config=context.config,
            bot_token=context.bot_token,
            chat_id=str(context.chat_id),
            miners=context.miners,
            states=context.states,
            state_lock=context.state_lock,
            state_path=context.state_path,
            current_last_update_id=context.current_last_update_id,
            hashcore_cfg=context.hashcore_cfg,
            event_store=context.event_store,
            qa_mode=context.qa_mode,
            qa_allow_actions=context.qa_allow_actions,
            token_registry=context.token_registry,
        )


def create_default_command_router() -> TelegramCommandRouter:
    """Instantiate and populate the standard production command router with all registered handlers."""
    from app.telegram.commands.status import StatusCommand, InfoCommand
    from app.telegram.commands.fans import FansCommand, SilentCommand, GovernorCommand
    from app.telegram.commands.interventions import (
        InterventionsCommand,
        ContingencyCommand,
        BalancerCommand,
        ElevatorsCommand,
    )
    from app.telegram.commands.reboot import RebootCommand, RebootNoOkCommand, ConfirmCommand
    from app.telegram.commands.diagnostics import (
        DiagnoseCommand,
        FirmwareCommand,
        QualityCommand,
        HealthCommand,
        ChartCommand,
        EventsCommand,
        EventCommand,
        WhyCommand,
        ChainsCommand,
        EfficiencyCommand,
        PresetsCommand,
        SelftestCommand,
    )
    from app.telegram.commands.maintenance import (
        SnoozeCommand,
        UnsnoozeCommand,
        SnoozedCommand,
        ShutdownCommand,
        ResumeCommand,
        ScheduleMaintenanceCommand,
        ScheduledCommand,
    )
    from app.telegram.commands.help import HelpCommand, MenuCommand, DigestCommand

    router = TelegramCommandRouter()
    # Status & Info
    router.register(StatusCommand()).register(InfoCommand())
    # Fans & Governor
    router.register(FansCommand()).register(SilentCommand()).register(GovernorCommand())
    # Interventions, Balancer, Elevators
    router.register(InterventionsCommand()).register(ContingencyCommand()).register(BalancerCommand()).register(ElevatorsCommand())
    # Reboot & Confirm
    router.register(RebootCommand()).register(RebootNoOkCommand()).register(ConfirmCommand())
    # Diagnostics & Telemetry
    router.register(DiagnoseCommand()).register(FirmwareCommand()).register(QualityCommand()).register(HealthCommand())
    router.register(ChartCommand()).register(EventsCommand()).register(EventCommand()).register(WhyCommand())
    router.register(ChainsCommand()).register(EfficiencyCommand()).register(PresetsCommand()).register(SelftestCommand())
    # Maintenance & Schedules
    router.register(SnoozeCommand()).register(UnsnoozeCommand()).register(SnoozedCommand())
    router.register(ShutdownCommand()).register(ResumeCommand()).register(ScheduleMaintenanceCommand()).register(ScheduledCommand())
    # Help & Dashboard
    router.register(HelpCommand()).register(MenuCommand()).register(DigestCommand())

    return router
