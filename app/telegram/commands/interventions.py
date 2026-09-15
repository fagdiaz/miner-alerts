"""Intervention Governance, Contingency, Balancer, and Elevators Commands (Spec 058)."""

from __future__ import annotations

import logging
import time
from typing import Any, List, Optional

from app.telegram.commands.base import BaseCommandHandler
from app.telegram.context import TelegramRequestContext

logger = logging.getLogger("miner-alerts")


class InterventionsCommand(BaseCommandHandler):
    name = "interventions"
    aliases = ["intervenciones"]
    description = "Gobernanza de actuadores: ver estado, pausar con temporizador o reactivar."

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
        from app.governance.intervention_policy import (
            apply_governance_toggle,
            format_governance_summary,
        )
        from app.telegram.command_center import render_interventions_menu
        from app.miner_monitor import _build_state_payload, _flush_state_payload

        sub = (args[0].lower().strip() if args else "status")
        now_ts = time.time()
        if sub in ("status", "estado"):
            msg_text, msg_markup = render_interventions_menu(mm._GLOBAL_INTERVENTION_GOV, now_ts)
        elif sub in ("on", "activar"):
            mm._GLOBAL_INTERVENTION_GOV = apply_governance_toggle(mm._GLOBAL_INTERVENTION_GOV, "all_on", now_ts)
            with context.state_lock:
                for st in context.states.values():
                    st.intervention_gov = mm._GLOBAL_INTERVENTION_GOV
                payload = _build_state_payload(context.states, context.current_last_update_id)
            _flush_state_payload(context.state_path, payload)
            msg_text, msg_markup = render_interventions_menu(mm._GLOBAL_INTERVENTION_GOV, now_ts)
        elif sub in ("off", "desactivar", "libre"):
            mm._GLOBAL_INTERVENTION_GOV = apply_governance_toggle(mm._GLOBAL_INTERVENTION_GOV, "all_off", now_ts)
            with context.state_lock:
                for st in context.states.values():
                    st.intervention_gov = mm._GLOBAL_INTERVENTION_GOV
                payload = _build_state_payload(context.states, context.current_last_update_id)
            _flush_state_payload(context.state_path, payload)
            msg_text, msg_markup = render_interventions_menu(mm._GLOBAL_INTERVENTION_GOV, now_ts)
        elif sub in ("30m", "1h", "2h", "4h"):
            dur_map = {"30m": 1800.0, "1h": 3600.0, "2h": 7200.0, "4h": 14400.0}
            dur = dur_map.get(sub)
            mm._GLOBAL_INTERVENTION_GOV = apply_governance_toggle(
                mm._GLOBAL_INTERVENTION_GOV, "all_off", now_ts, duration_seconds=dur
            )
            with context.state_lock:
                for st in context.states.values():
                    st.intervention_gov = mm._GLOBAL_INTERVENTION_GOV
                payload = _build_state_payload(context.states, context.current_last_update_id)
            _flush_state_payload(context.state_path, payload)
            msg_text, msg_markup = render_interventions_menu(mm._GLOBAL_INTERVENTION_GOV, now_ts)
        else:
            msg_text = (
                "ℹ️ *Uso de /interventions*:\n\n"
                "• `/interventions status`: Ver estado actual de actuadores\n"
                "• `/interventions on`: Reactivar todas las intervenciones\n"
                "• `/interventions off`: Desactivar todas (Modo Vnish Libre)\n"
                "• `/interventions 30m|1h|2h|4h`: Desactivar con temporizador automático"
            )
            msg_markup = None

        context.send_message(
            msg_text,
            reply_markup=msg_markup,
            msg_type="STATUS",
            dedup_key="cmd_interventions",
            dbg_cmd="interventions",
            dbg_update_id=update_id,
        )
        return True


class ContingencyCommand(BaseCommandHandler):
    name = "contingency"
    aliases = ["contingencia"]
    description = "Supervisión y reset manual de la contingencia adaptativa por elevadores."

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
        from app.governance.adaptive_contingency import (
            DEFAULT_CANARY_MAP,
            GroupContingencyState,
            evaluate_canary_contingency,
        )
        from app.miner_monitor import save_state

        sub = (args[0].lower().strip() if args else "status")
        now_ts = time.time()
        if sub in ("reset", "resetear", "nominal"):
            for grp in list(mm._ELEVATOR_CONTINGENCY_STATES.keys()):
                dec = evaluate_canary_contingency("manual_reset", "", grp, {}, now_ts)
                if dec.updated_group_state:
                    mm._ELEVATOR_CONTINGENCY_STATES[grp] = dec.updated_group_state
            context.persist_state_safely()
            msg_text = "✅ *Contingencia de elevadores restablecida a valores nominales.*"
        else:
            c_lines = [
                "╔══════════════════════════════════════╗",
                "║  ⚡ CONTINGENCIA ADAPTATIVA ELEVADORES║",
                "╚══════════════════════════════════════╝",
                "",
            ]
            for grp, can in DEFAULT_CANARY_MAP.items():
                st_grp = mm._ELEVATOR_CONTINGENCY_STATES.get(grp)
                act = st_grp.active if st_grp else False
                rem_soak = ""
                if act and st_grp and st_grp.last_restart_ts:
                    elapsed = now_ts - st_grp.last_restart_ts
                    rem_s = max(0.0, st_grp.soak_duration_seconds - elapsed)
                    rem_soak = f" (restan {int(rem_s//60)}m para recuperación)"
                st_str = f"🔴 ACTIVA{rem_soak}" if act else "🟢 NOMINAL (Estable)"
                c_lines.append(f"• *{grp.upper()}*: {st_str}")
                c_lines.append(f"  - Minero Canario: `{can}`")
                if st_grp and st_grp.step_down_count > 0:
                    c_lines.append(f"  - Desescalas acumuladas: {st_grp.step_down_count}")
                c_lines.append("")
            c_lines.append("ℹ️ `/contingency reset`: Restablecer a nominal")
            msg_text = "\n".join(c_lines)

        context.send_message(
            msg_text,
            msg_type="STATUS",
            dedup_key="cmd_contingency",
            dbg_cmd="contingency",
            dbg_update_id=update_id,
        )
        return True


class BalancerCommand(BaseCommandHandler):
    name = "balancer"
    aliases = ["bal", "power"]
    description = "Control y estado del balanceador dinámico de potencia y presets."

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
        from app.governance.preset_balancer import (
            BalancerConfig,
            evaluate_balancer_step,
            build_balancer_table_text,
            build_miner_balancer_detail_text,
            extract_miner_stability_metrics,
            analyze_elevator_sensitivity,
            build_elevator_sensitivity_text,
        )
        from app.telegram.fleet_cards import build_diagnostic_keyboard
        from app.miner_monitor import resolve_db_path, log, execute_balancer_cycle

        sub = args[0].strip().lower() if args else ""
        bal_enabled_cfg = bool(context.config.get("preset_balancer_enabled", False))
        bal_dry_run = bool(context.config.get("preset_balancer_dry_run", True))
        db_p = resolve_db_path(context.config)

        if sub == "on":
            mm._BALANCER_RUNTIME_ENABLED = True
            bal_msg = (
                "✅ *Dynamic Preset Balancer: ACTIVADO*\n"
                f"Modo: {'🔇 DRY-RUN (simulación)' if bal_dry_run else '⚡ ACTIVO (escribe hardware)'}\n"
                f"Intervalo: {context.config.get('preset_balancer_interval_seconds', 1800)}s | Umbral: {context.config.get('preset_balancer_restarts_step_down', 2)} reinicios/24h"
            )
            log("[BALANCER] Balancer habilitado por comando /balancer on")

        elif sub == "off":
            mm._BALANCER_RUNTIME_ENABLED = False
            bal_msg = "🛑 *Dynamic Preset Balancer: DESACTIVADO*\n(Los presets actuales se mantendrán fijos)"
            log("[BALANCER] Balancer deshabilitado por comando /balancer off")

        elif sub == "run":
            decisions = execute_balancer_cycle(
                miners=context.miners,
                states=context.states,
                state_lock=context.state_lock,
                config=context.config,
                now_ts=time.time(),
                qa_mode=context.qa_mode,
                db_path=db_p,
                force=True,
            )
            is_enabled = (
                mm._BALANCER_RUNTIME_ENABLED
                if mm._BALANCER_RUNTIME_ENABLED is not None
                else bal_enabled_cfg
            )
            bal_msg = "🔄 *Ciclo Forzado Ejecutado*\n" + build_balancer_table_text(
                decisions, is_enabled=is_enabled, is_dry_run=bal_dry_run
            )

        elif sub == "setmax" and len(args) >= 3:
            target_miner_arg = args[1].strip()
            target_preset_arg = args[2].strip().upper()
            matched_miner = None
            for m in context.miners:
                m_n = str(m.get("name", ""))
                m_h = str(m.get("host", ""))
                if (target_miner_arg.lower() in m_n.lower()) or (target_miner_arg in m_h):
                    matched_miner = m
                    break
            if not matched_miner:
                bal_msg = f"⚠️ Minero '{target_miner_arg}' no encontrado en la configuración."
            else:
                matched_miner["max_preset"] = target_preset_arg
                bal_msg = (
                    f"✅ Techo máximo para *{matched_miner.get('name')}* ajustado a *{target_preset_arg}*.\n"
                    "El balanceador no escalará por encima de este nivel."
                )
                log(f"[BALANCER] Techo max de {matched_miner.get('name')} fijado a {target_preset_arg}")

        elif sub in ("elevadores", "elevators", "sensibilidad", "elev"):
            with context.state_lock:
                metrics_list = extract_miner_stability_metrics(
                    db_path=db_p,
                    miners=context.miners,
                    states=context.states,
                    config=context.config,
                    now_ts=time.time(),
                )
            summaries = analyze_elevator_sensitivity(metrics_list, db_path=db_p)
            bal_msg = build_elevator_sensitivity_text(summaries)

        elif sub and sub not in ("status", "table", "help"):
            with context.state_lock:
                metrics_list = extract_miner_stability_metrics(
                    db_path=db_p,
                    miners=context.miners,
                    states=context.states,
                    config=context.config,
                    now_ts=time.time(),
                )
            matched = None
            for m_metrics in metrics_list:
                if (sub.lower() in m_metrics.miner_name.lower()) or (sub in m_metrics.miner_name):
                    matched = m_metrics
                    break
            if matched:
                m_dict = next((m for m in context.miners if m.get("name") == matched.miner_name), {})
                max_ov = m_dict.get("max_preset")
                bal_cfg = BalancerConfig(
                    enabled=True,
                    dry_run=bal_dry_run,
                    default_max_preset=str(context.config.get("preset_balancer_default_max_preset", "2700W")),
                )
                dec = evaluate_balancer_step(
                    matched,
                    config=bal_cfg,
                    group_metrics=metrics_list,
                    max_preset_override=max_ov,
                )
                bal_msg = build_miner_balancer_detail_text(matched, dec)
            else:
                bal_msg = f"⚠️ Minero '{sub}' no encontrado. Use `/balancer` para ver la flota."

        else:
            with context.state_lock:
                metrics_list = extract_miner_stability_metrics(
                    db_path=db_p,
                    miners=context.miners,
                    states=context.states,
                    config=context.config,
                    now_ts=time.time(),
                )
            decisions_tuples = []
            bal_cfg = BalancerConfig(
                enabled=True,
                dry_run=bal_dry_run,
                default_max_preset=str(context.config.get("preset_balancer_default_max_preset", "2700W")),
            )
            for m_metrics in metrics_list:
                m_dict = next((m for m in context.miners if m.get("name") == m_metrics.miner_name), {})
                max_ov = m_dict.get("max_preset")
                dec = evaluate_balancer_step(
                    m_metrics,
                    config=bal_cfg,
                    group_metrics=metrics_list,
                    max_preset_override=max_ov,
                )
                decisions_tuples.append((m_metrics, dec))
            is_enabled = (
                mm._BALANCER_RUNTIME_ENABLED
                if mm._BALANCER_RUNTIME_ENABLED is not None
                else bal_enabled_cfg
            )
            bal_msg = build_balancer_table_text(
                decisions_tuples,
                is_enabled=is_enabled,
                is_dry_run=bal_dry_run,
            )

        balancer_kb = build_diagnostic_keyboard("balancer")
        context.send_message(
            bal_msg,
            reply_markup=balancer_kb,
            msg_type="BALANCER",
            dedup_key="cmd_balancer",
            dbg_cmd="balancer",
            dbg_update_id=update_id,
        )
        return True


class ElevatorsCommand(BaseCommandHandler):
    name = "elevadores"
    aliases = ["elevators", "sensibilidad", "elev"]
    description = "Sensibilidad y análisis de reactividad por grupos de elevadores."

    def handle(
        self,
        context: TelegramRequestContext,
        args: List[str],
        update_id: Optional[int] = None,
        from_id: Optional[Any] = None,
        message_id: Optional[int] = None,
        **kwargs: Any,
    ) -> bool:
        from app.governance.preset_balancer import (
            extract_miner_stability_metrics,
            analyze_elevator_sensitivity,
            build_elevator_sensitivity_text,
        )
        from app.telegram.fleet_cards import build_diagnostic_keyboard
        from app.miner_monitor import resolve_db_path

        db_p = resolve_db_path(context.config)
        with context.state_lock:
            metrics_list = extract_miner_stability_metrics(
                db_path=db_p,
                miners=context.miners,
                states=context.states,
                config=context.config,
                now_ts=time.time(),
            )
        summaries = analyze_elevator_sensitivity(metrics_list, db_path=db_p)
        elev_msg = build_elevator_sensitivity_text(summaries)
        elev_kb = build_diagnostic_keyboard("elev")
        context.send_message(
            elev_msg,
            reply_markup=elev_kb,
            msg_type="BALANCER",
            dedup_key="cmd_elevadores",
            dbg_cmd="elevadores",
            dbg_update_id=update_id,
        )
        return True
