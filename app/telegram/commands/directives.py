"""
Governance Directives Dashboard Command Handlers (Spec 084 / PROP-020).

Exposes real-time mobile observability for all 16 directives in 5 layers (P0-P4):
- /directivas: Fleet overview card with per-miner status, solar envelope, and elevator powers.
- /directivas <minero>: Detailed 5-layer directive breakdown for a specific miner.
- Aliases: /gov_status, /gov, /directives.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from app.telegram.commands.base import BaseCommandHandler
from app.telegram.context import TelegramRequestContext
from app.governance.governance_context import MinerGovernanceContext
from app.governance.directives_dashboard import (
    build_fleet_directives_card,
    build_miner_directive_card,
    evaluate_recovery_deadlock,
)


class DirectivesCommand(BaseCommandHandler):
    """Mobile dashboard command for inspecting active governance directives."""

    name = "directivas"
    aliases = ["gov_status", "directives", "directiva"]
    description = "Observabilidad en tiempo real de directivas de gobernanza (P0-P4)."

    def handle(
        self,
        context: TelegramRequestContext,
        args: List[str],
        update_id: Optional[int] = None,
        from_id: Optional[Any] = None,
        message_id: Optional[int] = None,
        cmd_name: str = "",
        **kwargs: Any,
    ) -> bool:
        if not self.check_authorization(context, from_id):
            return False

        now_ts = time.time()
        contexts: List[MinerGovernanceContext] = []
        elevator_powers: Dict[str, float] = {}

        with context.state_lock:
            for m in context.miners:
                name = m.get("name", "")
                host = m.get("host", "")
                port = m.get("port", 4028)
                sk = f"{name}|{host}:{port}"
                st = context.states.get(sk)

                ctx = MinerGovernanceContext.from_state(st, now_ts, m)
                contexts.append(ctx)

                grp = str(m.get("electrical_group") or m.get("group", "elevator_1"))
                pwr = float(ctx.current_power_w or 0.0)
                elevator_powers[grp] = elevator_powers.get(grp, 0.0) + pwr

        # Determine solar envelope status
        solar_active = False
        try:
            from app.governance.elevator_budget import is_solar_envelope_active
            solar_active = is_solar_envelope_active(now_ts, max_temp_c=max((c.max_chip_temp_c or 0.0) for c in contexts) if contexts else 0.0)
        except Exception:
            solar_active = False

        if not args:
            card = build_fleet_directives_card(
                contexts,
                elevator_states=elevator_powers,
                solar_active=solar_active,
                now_ts=now_ts,
            )
        else:
            query = args[0].strip().lower()
            matched_ctx = None
            for c in contexts:
                c_name_lower = c.miner_name.lower()
                if query == c_name_lower:
                    matched_ctx = c
                    break
                if query in c_name_lower:
                    matched_ctx = c
                    break
                if query.isdigit() and query in c_name_lower:
                    matched_ctx = c
                    break

            if matched_ctx is None:
                valid_names = "\n".join(f"• {c.miner_name}" for c in contexts)
                card = (
                    f"Minero '{args[0]}' no existe.\n"
                    "Mineros disponibles:\n"
                    f"{valid_names}"
                )
                # Ensure no line exceeds 32 chars
                card = "\n".join(l[:32] for l in card.splitlines())
            else:
                deadlocked = evaluate_recovery_deadlock(
                    matched_ctx.fan_action,
                    matched_ctx.recovery_since_ts,
                    now_ts,
                    matched_ctx.is_warming_up,
                )
                duration = max(0.0, now_ts - matched_ctx.recovery_since_ts) if matched_ctx.recovery_since_ts else 0.0
                card = build_miner_directive_card(
                    matched_ctx,
                    elevator_group=matched_ctx.electrical_group,
                    solar_active=solar_active,
                    is_deadlocked=deadlocked,
                    deadlock_duration_s=duration,
                    now_ts=now_ts,
                )

        # Telegram markdown monospace formatting
        formatted = f"```\n{card}\n```"
        context.send_message(
            formatted,
            msg_type="STATUS",
            parse_mode="Markdown",
            dedup_key=f"cmd_directivas_{update_id}",
            dbg_cmd="directivas",
            dbg_update_id=update_id,
        )
        return True
