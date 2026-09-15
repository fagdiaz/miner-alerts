"""Reboot and Restart Command Handlers with 2-Step Safety Verification (Spec 058)."""

from __future__ import annotations

import logging
import random
import re
import time
from typing import Any, List, Optional

from app.telegram.commands.base import BaseCommandHandler
from app.telegram.context import TelegramRequestContext

logger = logging.getLogger("miner-alerts")


class RebootCommand(BaseCommandHandler):
    name = "reboot"
    aliases = ["restart", "reiniciar"]
    description = "Reinicio de mineros con verificación en dos pasos y bloqueo de seguridad."

    def handle(
        self,
        context: TelegramRequestContext,
        args: List[str],
        update_id: Optional[int] = None,
        from_id: Optional[Any] = None,
        message_id: Optional[int] = None,
        cmd_name: str = "",
    ) -> bool:
        from app.miner_monitor import (
            resolve_miner,
            display_name,
            log,
            run_hashcore_cli,
            record_action_outcome,
            _is_command_like,
            DBG_TELEGRAM,
            DBG_TELEGRAM_COMMANDS_ONLY,
        )

        msg_chat_id = context.chat_id
        pending_reboots = context.pending_reboots if context.pending_reboots is not None else {}
        pending_lock = context.pending_lock

        if not args:
            lines = [
                "╔══════════════════════════════════════╗",
                "║       REINICIAR MINEROS (2-PASOS)    ║",
                "╚══════════════════════════════════════╝",
                "",
                "Para reiniciar un minero específico:",
                "  `/reboot <nombre_o_ip>`  (ej: `/reboot 23`)",
                "",
                "Para reiniciar en masa mineros NO-OK:",
                "  `/reboot_no_ok`",
                "",
                "Flota actual:",
            ]
            states_snap = context.get_states_snapshot()
            for m in context.miners:
                dname = display_name(m.get("name", ""))
                mhost = m.get("host", "")
                sk = f"{m.get('name','')}|{mhost}:{m.get('port', 4028)}"
                st = states_snap.get(sk)
                st_state = getattr(st, "state", "UNKNOWN") if st else "UNKNOWN"
                lines.append(f"• *{dname}* ({mhost}): `{st_state}`")
            lines.append("")
            lines.append("ℹ️ Todos los reinicios manuales requieren confirmación con token de 60s.")

            context.send_message(
                "\n".join(lines),
                msg_type="HELP",
                dedup_key="cmd_reboot_help",
                dbg_cmd="reboot:help",
                dbg_update_id=update_id,
            )
            return True

        miner_token = args[0].strip()
        miner = resolve_miner(miner_token, context.miners)
        if not miner:
            context.send_message(
                f"⚠️ Minero '{miner_token}' no encontrado.\nUso: `/reboot <nombre_o_ip>`",
                msg_type="ERROR",
                dedup_key="cmd_reboot_err",
                dbg_cmd="reboot:not_found",
                dbg_update_id=update_id,
            )
            return True

        action = "reboot"
        state_key = f"{miner['name']}|{miner['host']}:{miner['port']}"
        now_ts = time.time()

        with context.state_lock:
            st = context.states.get(state_key)
            last_manual = getattr(st, "last_manual_reboot_ts", None) if st else None
            is_stopped = getattr(st, "is_shutdown_maintenance", False) if st else False

        if is_stopped:
            context.send_message(
                f"🛑 *Reinicio Bloqueado*: El minero *{display_name(miner['name'])}* está en Parada Segura.\n"
                f"Ejecute `/resume {display_name(miner['name'])}` antes de reiniciar.",
                msg_type="ERROR",
                dedup_key="cmd_reboot_stopped",
                dbg_cmd="reboot:stopped",
                dbg_update_id=update_id,
            )
            return True

        if last_manual and (now_ts - last_manual) < 600:
            remaining = int(600 - (now_ts - last_manual))
            context.send_message(
                f"⏳ Cooldown activo para *{display_name(miner['name'])}*. Restan {remaining}s.",
                msg_type="ERROR",
                dedup_key="cmd_reboot_cooldown",
                dbg_cmd="reboot:cooldown",
                dbg_update_id=update_id,
            )
            return True

        code = f"{random.randint(100000, 999999)}"
        if pending_lock:
            with pending_lock:
                pending_reboots[state_key] = {
                    "action": action,
                    "created_ts": now_ts,
                    "expires_ts": now_ts + 60,
                    "code": code,
                    "token": miner_token,
                }
        else:
            pending_reboots[state_key] = {
                "action": action,
                "created_ts": now_ts,
                "expires_ts": now_ts + 60,
                "code": code,
                "token": miner_token,
            }

        msg = (
            f"⚠️ *Confirmar Reinicio*: {display_name(miner['name'])}\n\n"
            f"Para proceder, envíe:\n"
            f"`/confirm {action} {miner_token} {code}`\n\n"
            f"⏱️ Este código expira en 60 segundos."
        )
        context.send_message(
            msg,
            msg_type="REBOOT",
            dedup_key=f"cmd_reboot_{miner_token}",
            dbg_cmd="reboot:prompt",
            dbg_update_id=update_id,
        )
        return True


class RebootNoOkCommand(BaseCommandHandler):
    name = "reboot_no_ok"
    aliases = ["reboot-no-ok"]
    description = "Reinicio masivo para todos los mineros en estado NO-OK."

    def handle(
        self,
        context: TelegramRequestContext,
        args: List[str],
        update_id: Optional[int] = None,
        from_id: Optional[Any] = None,
        message_id: Optional[int] = None,
        cmd_name: str = "",
    ) -> bool:
        from app.miner_monitor import display_name, is_miner_no_ok, log

        BULK_REBOOT_CAP = 5
        targets = []
        with context.state_lock:
            for miner in context.miners:
                name_display = display_name(miner["name"])
                host = miner["host"]
                port = miner.get("port", 4028)
                state_key = f"{miner['name']}|{host}:{port}"
                state = context.states.get(state_key)
                if is_miner_no_ok(state):
                    targets.append(name_display)

        if not targets:
            context.send_message(
                "No hay mineros en estado NO-OK.",
                msg_type="REBOOT",
                dedup_key="cmd_reboot_bulk_empty",
                dbg_cmd="reboot_bulk_preview",
                dbg_update_id=update_id,
            )
            return True

        truncated = False
        if len(targets) > BULK_REBOOT_CAP:
            targets = targets[:BULK_REBOOT_CAP]
            truncated = True

        code = f"{random.randint(100000, 999999)}"
        now_ts = time.time()
        pending_key = f"{context.chat_id}:reboot_no_ok"

        pending_reboots = context.pending_reboots if context.pending_reboots is not None else {}
        pending_lock = context.pending_lock
        if pending_lock:
            with pending_lock:
                pending_reboots[pending_key] = {
                    "type": "bulk",
                    "action": "reboot_no_ok",
                    "created_ts": now_ts,
                    "expires_ts": now_ts + 60,
                    "code": code,
                    "target_ids": targets,
                }
        else:
            pending_reboots[pending_key] = {
                "type": "bulk",
                "action": "reboot_no_ok",
                "created_ts": now_ts,
                "expires_ts": now_ts + 60,
                "code": code,
                "target_ids": targets,
            }

        log(f'action="reboot" target="{",".join(targets)}" mode="bulk"')
        preview_lines = [
            f"NO-OK detectados: {len(targets)} ({', '.join(targets)})",
            f"Confirmar: /c{code}",
            "Expira en 60s.",
        ]
        if truncated:
            preview_lines.insert(1, "Se aplico limite: 5 maximos.")

        context.send_message(
            "\n".join(preview_lines),
            msg_type="REBOOT",
            dedup_key="cmd_reboot_bulk_preview",
            dbg_cmd="reboot_no_ok",
            dbg_update_id=update_id,
        )
        return True


class ConfirmCommand(BaseCommandHandler):
    name = "confirm"
    aliases = []
    description = "Confirma una orden de reinicio previa mediante código numérico de un solo uso."

    def matches(self, cmd_token: str) -> bool:
        clean = (cmd_token or "").strip().lower()
        if clean.startswith("/"):
            clean = clean[1:]
        if "@" in clean:
            clean = clean.split("@", 1)[0]
        if clean == "confirm":
            return True
        if re.fullmatch(r"c(\d{4,10})", clean):
            return True
        if clean == "reboot-confirm":
            return True
        return False

    def handle(
        self,
        context: TelegramRequestContext,
        args: List[str],
        update_id: Optional[int] = None,
        from_id: Optional[Any] = None,
        message_id: Optional[int] = None,
        cmd_name: str = "",
    ) -> bool:
        import app.miner_monitor as mm
        from app.miner_monitor import (
            resolve_miner,
            display_name,
            log,
            run_hashcore_cli,
            record_action_outcome,
        )

        msg_chat_id = context.chat_id
        pending_reboots = context.pending_reboots if context.pending_reboots is not None else {}
        pending_lock = context.pending_lock
        now_ts = time.time()

        # Check if called as /c<digits>
        m_c = re.fullmatch(r"c(\d{4,10})", (cmd_name or "").strip().lower())
        if m_c:
            code = m_c.group(1)
            action = "reboot_no_ok"
            miner_token = ""
        elif args and re.fullmatch(r"\d{4,10}", args[0]):
            code = args[0]
            action = "reboot_no_ok"
            miner_token = ""
        elif len(args) >= 2 and args[0] in ("reboot_no_ok", "reboot-no-ok"):
            action = "reboot_no_ok"
            code = args[1]
            miner_token = ""
        elif len(args) >= 3:
            action = args[0]
            miner_token = args[1]
            code = args[2]
        else:
            context.send_message(
                "Uso: /confirm <accion> <codigo>\nEj: /confirm reboot_no_ok 123456",
                msg_type="HELP",
                dedup_key="cmd_confirm_usage",
                dbg_cmd="confirm:usage",
                dbg_update_id=update_id,
            )
            return True

        if action in ("reboot_no_ok", "reboot-no-ok"):
            pending_key = f"{msg_chat_id}:reboot_no_ok"
            if pending_lock:
                with pending_lock:
                    pending = pending_reboots.get(pending_key)
            else:
                pending = pending_reboots.get(pending_key)

            if not pending or pending.get("expires_ts", 0) < now_ts:
                if pending_lock:
                    with pending_lock:
                        pending_reboots.pop(pending_key, None)
                else:
                    pending_reboots.pop(pending_key, None)
                context.send_message(
                    "Confirmacion expirada.",
                    msg_type="ERROR",
                    dedup_key="cmd_confirm_expired",
                    dbg_cmd="confirm:reboot_no_ok",
                    dbg_update_id=update_id,
                )
                return True

            if pending.get("code") != code:
                context.send_message(
                    "Codigo invalido.",
                    msg_type="ERROR",
                    dedup_key="cmd_confirm_badcode",
                    dbg_cmd="confirm:reboot_no_ok",
                    dbg_update_id=update_id,
                )
                return True

            targets = pending.get("target_ids", [])
            if pending_lock:
                with pending_lock:
                    pending_reboots.pop(pending_key, None)
            else:
                pending_reboots.pop(pending_key, None)

            results = []
            for token in targets:
                miner = resolve_miner(token, context.miners)
                if not miner:
                    results.append(f"{token}  FAIL (not_found)")
                    continue
                ok, msg = run_hashcore_cli(
                    context.hashcore_cfg,
                    miner,
                    "reboot",
                    context.config,
                    context.qa_mode,
                    context.qa_allow_actions,
                )
                record_action_outcome(
                    context.event_store,
                    occurred_ts=now_ts,
                    miner=miner,
                    action="reboot",
                    source="manual",
                    ok=ok,
                    message=msg,
                )
                if ok:
                    results.append(f"{display_name(miner['name'])}  OK")
                    state_key = f"{miner['name']}|{miner['host']}:{miner.get('port', 4028)}"
                    with context.state_lock:
                        state = context.states.get(state_key)
                        if state:
                            state.last_manual_reboot_ts = now_ts
                            state.low_since_ts = None
                else:
                    results.append(f"{display_name(miner['name'])}  FAIL (error)")

            reply = ["MANUAL-REBOOT-NO-OK ejecutado:", "", *results]
            context.send_message(
                "\n".join(reply),
                msg_type="REBOOT",
                dedup_key="cmd_confirm_result",
                dbg_cmd="confirm:reboot_no_ok",
                dbg_update_id=update_id,
            )
            return True

        # Single miner reboot confirmation
        miner = resolve_miner(miner_token, context.miners)
        if not miner:
            context.send_message(
                "Miner no encontrado.",
                msg_type="ERROR",
                dedup_key="cmd_confirm_notfound",
                dbg_cmd=f"confirm:{action}",
                dbg_update_id=update_id,
            )
            return True

        if context.qa_mode and not context.qa_allow_actions:
            log("[WARN] Accion bloqueada por QA (telegram).")
            context.send_message(
                "Accion bloqueada (QA). Habilita qa_allow_real_actions=true para permitir reboots reales.",
                msg_type="ERROR",
                dedup_key="qa_block",
                dbg_cmd=f"confirm:{action}",
                dbg_update_id=update_id,
            )
            return True

        state_key = f"{miner['name']}|{miner['host']}:{miner.get('port', 4028)}"
        if pending_lock:
            with pending_lock:
                pending = pending_reboots.get(state_key)
        else:
            pending = pending_reboots.get(state_key)

        if not pending or pending.get("expires_ts", 0) < now_ts:
            context.send_message(
                "Confirmacion expirada.",
                msg_type="ERROR",
                dedup_key="cmd_confirm_expired",
                dbg_cmd=f"confirm:{action}",
                dbg_update_id=update_id,
            )
            return True

        if pending.get("code") != code:
            context.send_message(
                "Codigo invalido.",
                msg_type="ERROR",
                dedup_key="cmd_confirm_badcode",
                dbg_cmd=f"confirm:{action}",
                dbg_update_id=update_id,
            )
            return True

        if pending.get("action") != action:
            context.send_message(
                "Accion invalida.",
                msg_type="ERROR",
                dedup_key="cmd_confirm_badaction",
                dbg_cmd=f"confirm:{action}",
                dbg_update_id=update_id,
            )
            return True

        ok, msg = run_hashcore_cli(
            context.hashcore_cfg,
            miner,
            action,
            context.config,
            context.qa_mode,
            context.qa_allow_actions,
        )
        record_action_outcome(
            context.event_store,
            occurred_ts=now_ts,
            miner=miner,
            action=action,
            source="manual",
            ok=ok,
            message=msg,
        )
        if not ok:
            context.send_message(
                msg,
                msg_type="ERROR",
                dedup_key="cmd_confirm_fail",
                dbg_cmd=f"confirm:{action}",
                dbg_update_id=update_id,
            )
            return True

        with context.state_lock:
            state = context.states.get(state_key)
            if state:
                state.last_manual_reboot_ts = now_ts
                state.low_since_ts = None
        context.persist_state_safely()

        if pending_lock:
            with pending_lock:
                pending_reboots.pop(state_key, None)
        else:
            pending_reboots.pop(state_key, None)

        context.send_message(
            f"MANUAL-{action.upper()}: {display_name(miner['name'])} enviado.",
            msg_type="REBOOT" if action == "reboot" else "RESTART",
            dedup_key="cmd_confirm_ok",
            dbg_cmd=f"confirm:{action}",
            dbg_update_id=update_id,
        )
        return True
