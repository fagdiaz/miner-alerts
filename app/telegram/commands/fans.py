"""Fans, Silent Mode, and Governor Command Handlers (Spec 058)."""

from __future__ import annotations

import logging
import time
from typing import Any, List, Optional

from app.telegram.commands.base import BaseCommandHandler
from app.telegram.command_center import format_miner_key
from app.telegram.context import TelegramRequestContext

logger = logging.getLogger("miner-alerts")


class FansCommand(BaseCommandHandler):
    name = "fans"
    aliases = ["fan"]
    description = "Muestra el estado de ventilación y métricas de enfriamiento de la flota."

    def handle(
        self,
        context: TelegramRequestContext,
        args: List[str],
        update_id: Optional[int] = None,
        from_id: Optional[Any] = None,
        message_id: Optional[int] = None,
        **kwargs: Any,
    ) -> bool:
        from app.governance.fan_health import (
            fetch_latest_cooling_assessments,
            build_fans_table_text,
            build_miner_fan_detail_text,
        )
        from app.miner_monitor import resolve_db_path, resolve_miner

        db_p = resolve_db_path(context.config)
        with context.state_lock:
            assessments = fetch_latest_cooling_assessments(
                db_path=db_p,
                miners=context.miners,
                states=context.states,
                config=context.config,
            )
        target_arg = args[0].strip().lower() if args else None
        fans_kb = None
        if target_arg and target_arg != "all":
            from app.telegram.command_center import find_assessment_by_target
            matched_ass = find_assessment_by_target(assessments, target_arg, context.miners)
            if matched_ass:
                fans_msg = build_miner_fan_detail_text(matched_ass)
            else:
                fans_msg = f"⚠️ Minero '{target_arg}' no encontrado.\nUso: /fans [minero]"
        else:
            from app.telegram.fleet_cards import build_diagnostic_keyboard
            fans_msg = build_fans_table_text(assessments)
            fans_kb = build_diagnostic_keyboard("fans")

        context.send_message(
            fans_msg,
            reply_markup=fans_kb,
            msg_type="FANS",
            dedup_key="cmd_fans",
            dbg_cmd="fans",
            dbg_update_id=update_id,
        )
        return True


class SilentCommand(BaseCommandHandler):
    name = "silent"
    aliases = ["silencio", "modo_silencio"]
    description = "Control del modo silencioso / visitas (PWM acotado y guardián térmico)."

    def handle(
        self,
        context: TelegramRequestContext,
        args: List[str],
        update_id: Optional[int] = None,
        from_id: Optional[Any] = None,
        message_id: Optional[int] = None,
        **kwargs: Any,
    ) -> bool:
        from app.miner_monitor import MinerState, log

        sub = args[0].strip().lower() if args else ""
        sm_target_max = int(context.config.get("silent_mode_target_max_duty", 50))
        sm_min = int(context.config.get("silent_mode_min_duty_pct", 30))

        sm_durations = {
            "30m": 30, "30min": 30,
            "1h": 60, "1hora": 60,
            "2h": 120, "2horas": 120,
            "4h": 240, "4horas": 240,
            "6h": 360, "6horas": 360,
            "indef": None, "indefinido": None, "inf": None,
        }

        if sub in ("off", "cancelar", "desactivar"):
            cancelled = []
            with context.state_lock:
                for m in context.miners:
                    m_name = m.get("name", "")
                    sk = format_miner_key(m)
                    st = context.states.get(sk)
                    if st is not None and st.silent_mode_active:
                        st.silent_mode_active = False
                        st.silent_mode_revert_ts = None
                        cancelled.append(m_name)
                        log(f"[SILENT_MODE] Manually cancelled via /silent off: miner={m_name}")
            if cancelled:
                silent_msg = (
                    f"🔊 *Modo Silencio CANCELADO*\n"
                    f"Mineros: {', '.join(cancelled)}\n"
                    f"El Fan Governor restaurará el régimen normal en el próximo tick.\n"
                    f"_(Las órdenes de ventilador se actualizarán gradualmente)_"
                )
            else:
                silent_msg = "ℹ️ Modo Silencio no estaba activo en ningún minero."
            log("[SILENT_MODE] /silent off executed")

        elif sub in sm_durations:
            duration_min = sm_durations[sub]
            revert_ts = (time.time() + duration_min * 60.0) if duration_min is not None else None
            activated = []
            with context.state_lock:
                for m in context.miners:
                    m_name = m.get("name", "")
                    sk = format_miner_key(m)
                    st = context.states.get(sk)
                    if st is None:
                        context.states[sk] = MinerState()
                        st = context.states[sk]
                    if not st.silent_mode_active:
                        st.silent_mode_prev_duty = st.governor_duty
                        st.silent_mode_prev_preset = st.balancer_preset
                    st.silent_mode_active = True
                    st.silent_mode_revert_ts = revert_ts
                    st.silent_mode_target_max_duty = sm_target_max
                    activated.append(m_name)
                    log(f"[SILENT_MODE] Activated miner={m_name} max={sm_target_max}% revert_at={'indef' if revert_ts is None else revert_ts}")

            if duration_min is None:
                dur_str = "♾️ Sin límite de tiempo"
            elif duration_min < 60:
                dur_str = f"⏱️ {duration_min} minutos"
            else:
                dur_str = f"⏱️ {duration_min // 60}h{'%02d' % (duration_min % 60) if duration_min % 60 else ''}"
            silent_msg = (
                f"🔇 *Modo Silencio ACTIVADO*\n"
                f"Mineros: {', '.join(activated)}\n"
                f"Techo acústico: {sm_min}% – {sm_target_max}% PWM\n"
                f"Duración: {dur_str}\n"
                f"_El Fan Governor aplicará los límites desde el próximo tick._\n"
                f"\n⚠️ El Guardián Térmico anula el silencio si T ≥ {context.config.get('fan_governor_emergency_temp_c', 83.5)}°C."
            )

        else:
            lines = [
                "🔇 *Modo Silencio / Visitas*",
                f"Límite acústico: {sm_min}% – {sm_target_max}% PWM | Guardián: {context.config.get('fan_governor_emergency_temp_c', 83.5)}°C",
                "",
            ]
            with context.state_lock:
                for m in context.miners:
                    m_name = m.get("name", "")
                    sk = format_miner_key(m)
                    st = context.states.get(sk)
                    if st is None:
                        lines.append(f"  {m_name}: sin datos")
                        continue
                    if st.silent_mode_active:
                        if st.silent_mode_revert_ts is not None:
                            remaining_s = max(0, st.silent_mode_revert_ts - time.time())
                            rem_m = int(remaining_s // 60)
                            rem_str = f"{rem_m}m restantes"
                        else:
                            rem_str = "♾️ indefinido"
                        lines.append(f"  🔇 {m_name}: ACTIVO — {rem_str} (techo={st.silent_mode_target_max_duty}%)")
                    else:
                        lines.append(f"  🔊 {m_name}: inactivo")
            lines.append("")
            lines.append("Comandos: `/silent 30m` | `/silent 1h` | `/silent 2h` | `/silent 4h` | `/silent 6h` | `/silent indef` | `/silent off`")
            silent_msg = "\n".join(lines)

        context.send_message(
            silent_msg,
            msg_type="SILENT_MODE",
            dedup_key="cmd_silent",
            dbg_cmd="silent",
            dbg_update_id=update_id,
        )
        return True


class GovernorCommand(BaseCommandHandler):
    name = "governor"
    aliases = ["gov"]
    description = "Control del Fan Governor adaptativo (on, off, set <temp>, status)."

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
        from app.miner_monitor import log

        sub = args[0].strip().lower() if args else ""
        gov_enabled_cfg = bool(context.config.get("fan_governor_enabled", False))
        gov_dry_run = bool(context.config.get("fan_governor_dry_run", True))
        gov_target = float(context.config.get("fan_governor_target_temp_c", 82.0))
        gov_min_duty = int(context.config.get("fan_governor_min_duty_pct", 30))

        if sub == "on":
            mm._GOVERNOR_RUNTIME_ENABLED = True
            gov_msg = (
                "✅ *Fan Governor: ACTIVADO*\n"
                f"Target: {gov_target:.1f}°C | Piso: {gov_min_duty}% | "
                f"Modo: {'🔇 DRY-RUN' if gov_dry_run else '⚡ ACTIVO (escribe hardware)'}"
            )
            log("[GOV] Governor habilitado por comando /gov on")

        elif sub == "off":
            mm._GOVERNOR_RUNTIME_ENABLED = False
            vnish_pw = str(context.config.get("vnish_api_password", "admin"))
            fallback_results = []
            for m in context.miners:
                m_host = m.get("host", "")
                m_name = m.get("name", m_host)
                if not gov_dry_run and m_host:
                    from app.vnish.client import safe_set_fan_duty as _ssfd
                    try:
                        ok, err = _ssfd(m_host, vnish_pw, 100, timeout=2.5)
                        fallback_results.append(f"  {m_name}: {'✅ 100%' if ok else f'⚠️ {err}'}")
                    except Exception as exc:
                        fallback_results.append(f"  {m_name}: ⚠️ {exc}")
                else:
                    fallback_results.append(f"  {m_name}: ⏭️ DRY-RUN (sin acción)")
            fallback_str = "\n".join(fallback_results) if fallback_results else "  (sin mineros)"
            gov_msg = (
                "🛑 *Fan Governor: DESACTIVADO*\n"
                "Fallback de seguridad a 100% PWM:\n"
                f"{fallback_str}"
            )
            log("[GOV] Governor deshabilitado por comando /gov off. Fallback a 100% ejecutado.")

        elif sub == "set" and len(args) >= 2:
            try:
                new_temp = float(args[1].strip())
                if not (75.0 <= new_temp <= 83.0):
                    gov_msg = (
                        f"⚠️ Temperatura fuera de rango: {new_temp:.1f}°C\n"
                        "Rango válido: 75.0°C — 83.0°C"
                    )
                else:
                    context.config["fan_governor_target_temp_c"] = new_temp
                    gov_msg = (
                        f"✅ Target térmico actualizado: *{new_temp:.1f}°C*\n"
                        "(Efectivo en el próximo ciclo del gobernador)"
                    )
                    log(f"[GOV] Target térmico ajustado a {new_temp:.1f}°C por /gov set")
            except (ValueError, IndexError):
                gov_msg = "⚠️ Uso: `/gov set <temp>` (ej: `/gov set 81.5`)"

        else:
            is_enabled = (
                mm._GOVERNOR_RUNTIME_ENABLED
                if mm._GOVERNOR_RUNTIME_ENABLED is not None
                else gov_enabled_cfg
            )
            status_icon = "🟢 ON" if is_enabled else "🔴 OFF"
            mode_icon = "🔇 DRY-RUN" if gov_dry_run else "⚡ ACTIVO"
            lines = [
                f"🌀 *Fan Governor* — {status_icon} | {mode_icon}",
                f"Target: {gov_target:.1f}°C | Piso: {gov_min_duty}% | Dwell: {context.config.get('fan_governor_dwell_seconds', 90)}s",
                "",
            ]
            with context.state_lock:
                for m in context.miners:
                    m_name = m.get("name", "")
                    sk = format_miner_key(m)
                    st = context.states.get(sk)
                    if st is None:
                        lines.append(f"  {m_name}: sin datos")
                        continue
                    duty_str = f"{st.governor_duty}%" if st.governor_duty is not None else "N/D"
                    temp_str = f"{st.governor_last_temp_c:.1f}°C" if st.governor_last_temp_c is not None else "N/D"
                    pwr_val = getattr(st, "governor_last_power_w", None)
                    tgt_val = m.get("target_power_w")
                    if pwr_val is not None and tgt_val is not None:
                        pwr_str = f" {pwr_val:.0f}/{tgt_val:.0f}W"
                    elif pwr_val is not None:
                        pwr_str = f" {pwr_val:.0f}W"
                    else:
                        pwr_str = ""
                    action_str = st.governor_last_action or "IDLE"
                    holds_str = f"holds={st.governor_holds}"
                    fail_str = f" ⚠️fails={st.governor_failures}" if st.governor_failures > 0 else ""
                    lines.append(
                        f"  {m_name}: T={temp_str}{pwr_str} PWM={duty_str} [{action_str}] {holds_str}{fail_str}"
                    )
            lines.append("")
            lines.append("Comandos: `/gov on` | `/gov off` | `/gov set <temp>`")
            gov_msg = "\n".join(lines)

        context.send_message(
            gov_msg,
            msg_type="GOVERNOR",
            dedup_key="cmd_governor",
            dbg_cmd="gov",
            dbg_update_id=update_id,
        )
        return True
