"""
Facility Governance Agent (FGA) Telegram Command Handlers (Spec 079 / PROP-015).

Exposes deterministic conversational interfaces:
- /agent: Executive FGA Dashboard (strategy, power allocation, R_th, efficiency).
- /strategy: View or adjust FGA macro strategy (balanced, max_power, efficiency, cool_quiet).
- /fwhy: Detailed thermal resistance and power allocation explanation per miner.
"""

from datetime import datetime
import time
from typing import Any, Dict, List, Optional
from app.telegram.commands.base import BaseCommandHandler
from app.telegram.context import TelegramRequestContext
from app.governance.facility_agent import (
    STRATEGY_BALANCED,
    STRATEGY_MAX_POWER,
    STRATEGY_EFFICIENCY,
    STRATEGY_COOL_QUIET,
    VALID_STRATEGIES,
    build_thermal_profile,
    evaluate_asymmetric_allocation,
    explain_miner_state,
)
from app.governance.fga_actuator import (
    evaluate_fga_actuator_step,
    execute_fga_actuator_step,
)
from app.governance.elevator_budget import FacilityBudgetState
from app.governance.governance_context import MinerGovernanceContext


def _gather_fleet_telemetry(context: TelegramRequestContext) -> List[Dict[str, Any]]:
    """Extract live telemetry snapshot from miners and states for FGA evaluation."""
    telemetry = []
    with context.state_lock:
        for m in context.miners:
            name = m.get("name", "")
            host = m.get("host", "")
            port = m.get("port", 4028)
            sk = f"{name}|{host}:{port}"
            st = context.states.get(sk)

            chip_t = getattr(st, "governor_last_temp_c", None) or getattr(st, "last_temp_c", None)
            inlet_t = getattr(st, "inlet_temp_c", None) or 25.0
            pwr = getattr(st, "governor_last_power_w", None) or 2500.0
            preset = getattr(st, "balancer_preset", None) or "2500W"
            rate = getattr(st, "rate_ths", None) or 0.0

            telemetry.append({
                "name": name,
                "host": host,
                "port": port,
                "electrical_group": m.get("electrical_group") or m.get("group", "elevator_1"),
                "chip_temp_c": chip_t,
                "inlet_temp_c": inlet_t,
                "power_w": pwr,
                "preset": preset,
                "rate_ths": rate,
            })
    return telemetry


class AgentCommand(BaseCommandHandler):
    name = "agent"
    aliases = ["agente", "fga"]
    description = "Dashboard ejecutivo del Agente Autónomo de Gobernanza de Planta (FGA)."

    def handle(
        self,
        context: TelegramRequestContext,
        args: List[str],
        update_id: Optional[int] = None,
        from_id: Optional[Any] = None,
        message_id: Optional[int] = None,
        **kwargs: Any,
    ) -> bool:
        if args and args[0].lower() in ["run", "ejecutar", "opt"]:
            return self._handle_run(context, args[1:], update_id=update_id)

        if args and args[0].lower() in ["history", "historial", "acciones"]:
            return self._handle_history(context, args[1:], update_id=update_id)

        telemetry = _gather_fleet_telemetry(context)
        current_strategy = context.config.get("facility_agent_strategy", STRATEGY_BALANCED)

        decision = evaluate_asymmetric_allocation(
            telemetry,
            strategy=current_strategy,
        )

        total_rate = sum(m.get("rate_ths", 0.0) for m in telemetry)
        total_pwr = sum(m.get("power_w", 0.0) for m in telemetry)
        eff_j_th = (total_pwr / total_rate) if total_rate > 0 else 0.0

        lines = [
            "🤖 *FACILITY GOVERNANCE AGENT (FGA)*",
            "────────────────────────────",
            f"• Estrategia Activa: *{decision.strategy.upper()}*",
            f"• Hashrate Global: *{total_rate:.1f} TH/s*",
            f"• Consumo Total: *{total_pwr:.0f} W* (Proyectado: *{decision.total_projected_power_w:.0f} W*)",
            f"• Eficiencia Planta: *{eff_j_th:.1f} J/TH*",
            "────────────────────────────",
            "⚡ *ASIGNACIÓN POR ELEVADOR*:",
        ]

        # Group breakdown
        for grp in sorted(decision.group_projected_power_w.keys()):
            p_grp = decision.group_projected_power_w[grp]
            lines.append(f"• *{grp.upper()}*: {p_grp:.0f}W / 5400W máx")
            grp_miners = [m for m in telemetry if m.get("electrical_group") == grp]
            for gm in grp_miners:
                m_name = gm.get("name")
                tgt_p = decision.target_allocations.get(m_name, "2500W")
                t_chip = gm.get("chip_temp_c")
                t_str = f"{t_chip:.1f}°C" if t_chip is not None else "Warming-up"
                prof = build_thermal_profile(m_name, t_chip, gm.get("inlet_temp_c"), gm.get("power_w"), gm.get("preset"))
                lines.append(
                    f"  - {m_name}: *{tgt_p}* (T={t_str}, R_th={prof.thermal_resistance:.4f}, {prof.cohort})"
                )

        lines.extend([
            "────────────────────────────",
            "💡 Comandos disponibles:",
            "• `/agent run` (Forzar optimización)",
            "• `/agent history` (Ver auditoría)",
            "• `/strategy <modo>` (Ajustar estrategia)",
            "• `/fwhy <minero>` (Explicación técnica)",
        ])

        context.send_message(
            "\n".join(lines),
            msg_type="STATUS",
            dedup_key="cmd_agent_dashboard",
            dbg_cmd="agent",
            dbg_update_id=update_id,
        )
        return True

    def _handle_run(
        self,
        context: TelegramRequestContext,
        args: List[str],
        update_id: Optional[int] = None,
    ) -> bool:
        now_ts = time.time()
        now_dt = datetime.now()
        current_strategy = context.config.get("facility_agent_strategy", STRATEGY_BALANCED)
        presets_enabled = bool(context.config.get("presets_enabled", True))

        fac_state = None
        try:
            from app.miner_monitor import _FACILITY_BUDGET_STATE
            fac_state = _FACILITY_BUDGET_STATE
        except Exception:
            pass
        if fac_state is None:
            fac_state = FacilityBudgetState()

        contexts = []
        with context.state_lock:
            for m in context.miners:
                name = m.get("name", "")
                host = m.get("host", "")
                port = m.get("port", 4028)
                sk = f"{name}|{host}:{port}"
                st = context.states.get(sk)
                gov_ctx = MinerGovernanceContext.from_state(st, now_ts, m)
                contexts.append(gov_ctx)

        decision = evaluate_fga_actuator_step(
            governance_contexts=contexts,
            facility_state=fac_state,
            now_dt=now_dt,
            now_ts=now_ts,
            strategy=current_strategy,
            config=context.config,
            presets_enabled=presets_enabled,
        )

        if decision.can_proceed and decision.candidate_miner:
            cand_m = next(
                (m for m in context.miners if m.get("name") == decision.candidate_miner),
                None,
            )
            host = cand_m.get("host", "") if cand_m else ""
            vnish_pw = str(context.config.get("vnish_api_password", "admin"))
            sk = f"{cand_m.get('name', '')}|{host}:{cand_m.get('port', 4028)}" if cand_m else ""
            target_st = None
            with context.state_lock:
                target_st = context.states.get(sk)

            decision = execute_fga_actuator_step(
                decision=decision,
                host=host,
                password=vnish_pw,
                facility_state=fac_state,
                now_ts=now_ts,
                config=context.config,
                qa_mode=context.qa_mode,
                event_store=context.event_store,
                miner_state=target_st,
                state_lock=context.state_lock,
            )
            if decision.action_status in ("EXECUTED", "SIMULATED"):
                context.persist_state_safely()

        lines = [
            "🤖 *FGA ACTUATOR: RUN*",
            "────────────────────────────",
            f"• Estrategia: *{decision.strategy.upper()}*",
        ]
        if decision.candidate_miner:
            lines.extend([
                f"• Minero: *{decision.candidate_miner}*",
                f"• Modulación: *{decision.current_preset}* ➔ *{decision.target_preset}*",
                f"• Estado: *{decision.action_status}*",
                f"• Compuerta: `{decision.gate_action}`",
            ])
            if decision.remaining_settle_s > 0.0:
                lines.append(f"• Reposo Acometida: {decision.remaining_settle_s:.0f}s")
            r_short = (
                decision.gate_reason[:60] + "..."
                if len(decision.gate_reason) > 60
                else decision.gate_reason
            )
            lines.append(f"• Detalle: {r_short}")
        else:
            lines.extend([
                "• Estado: *NOOP (Óptimo)*",
                "• Flota operando en asignación",
                "  óptima. Sin cambios.",
            ])
        lines.append("────────────────────────────")

        context.send_message(
            "\n".join(lines),
            msg_type="STATUS",
            dedup_key="cmd_agent_run",
            dbg_cmd="agent_run",
            dbg_update_id=update_id,
        )
        return True

    def _handle_history(
        self,
        context: TelegramRequestContext,
        args: List[str],
        update_id: Optional[int] = None,
    ) -> bool:
        miner_filter = args[0].strip().upper() if args else None
        store = context.event_store
        if store is None or not getattr(store, "available", False):
            context.send_message(
                "⚠️ Base de datos no disponible para consultar historial FGA.",
                msg_type="STATUS",
                dedup_key="cmd_agent_hist_err",
            )
            return True

        actions = store.get_facility_agent_actions(miner_name=miner_filter, limit=5)
        lines = [
            "📜 *HISTORIAL ACCIONES FGA*",
            "────────────────────────────",
        ]
        if miner_filter:
            lines.append(f"Filtro: *{miner_filter}*")

        if not actions:
            lines.append("No hay acciones FGA registradas.")
        else:
            now_ts = time.time()
            for a in actions:
                m_name = a.get("miner_name", "?")
                status = a.get("action_status", "?")
                from_p = a.get("from_preset", "?")
                to_p = a.get("to_preset", "?")
                gate = a.get("gate_name") or a.get("gate_action") or "GATE"
                created_ts = a.get("created_ts") or now_ts
                age_s = max(0, int(now_ts - created_ts))
                if age_s < 60:
                    age_str = f"{age_s}s"
                elif age_s < 3600:
                    age_str = f"{age_s // 60}m"
                else:
                    age_str = f"{age_s // 3600}h"

                lines.append(f"• *{m_name}* [{status}] ({age_str})")
                lines.append(f"  {from_p} ➔ {to_p} | `{gate}`")

        lines.append("────────────────────────────")
        context.send_message(
            "\n".join(lines),
            msg_type="STATUS",
            dedup_key="cmd_agent_history",
            dbg_cmd="agent_history",
            dbg_update_id=update_id,
        )
        return True


class StrategyCommand(BaseCommandHandler):
    name = "strategy"
    aliases = ["estrategia"]
    description = "Consultar o ajustar la estrategia macro del Agente FGA."

    def handle(
        self,
        context: TelegramRequestContext,
        args: List[str],
        update_id: Optional[int] = None,
        from_id: Optional[Any] = None,
        message_id: Optional[int] = None,
        **kwargs: Any,
    ) -> bool:
        if not args:
            curr = context.config.get("facility_agent_strategy", STRATEGY_BALANCED)
            msg = (
                f"🎯 *ESTRATEGIA FGA ACTUAL*: *{curr.upper()}*\n\n"
                "Modos disponibles:\n"
                "• `/strategy balanced`: 2700W en máquinas frías, 2500W en cálidas (Recomendado).\n"
                "• `/strategy max_power`: Fuerza 2700W si el margen térmico lo permite.\n"
                "• `/strategy efficiency`: Optimiza consumo J/TH en 2300W-2500W.\n"
                "• `/strategy cool_quiet`: Techo 2300W con ventilación contenida."
            )
            context.send_message(msg, msg_type="STATUS", dedup_key="cmd_strategy_info")
            return True

        new_strat = args[0].strip().lower()
        if new_strat not in VALID_STRATEGIES:
            context.send_message(
                f"❌ Estrategia desconocida: '{new_strat}'. Opciones válidas: balanced, max_power, efficiency, cool_quiet.",
                msg_type="ERROR",
                dedup_key="cmd_strategy_err",
            )
            return True

        context.config["facility_agent_strategy"] = new_strat
        context.send_message(
            f"✅ *ESTRATEGIA ACTUALIZADA*\n\nNueva estrategia FGA activa: *{new_strat.upper()}*.\nEl motor determinístico recalculará la asignación en el próximo ciclo.",
            msg_type="STATUS",
            dedup_key="cmd_strategy_updated",
        )
        return True


class AgentWhyCommand(BaseCommandHandler):
    name = "fwhy"
    aliases = ["agent_why", "razon"]
    description = "Explicación física y térmica de la asignación de preset para un minero."

    def handle(
        self,
        context: TelegramRequestContext,
        args: List[str],
        update_id: Optional[int] = None,
        from_id: Optional[Any] = None,
        message_id: Optional[int] = None,
        **kwargs: Any,
    ) -> bool:
        from app.miner_monitor import resolve_miner

        if not args:
            context.send_message(
                "Uso: `/fwhy <minero>` (ejemplo: `/fwhy 23` o `/fwhy S19JPRO-26`)",
                msg_type="STATUS",
                dedup_key="cmd_fwhy_usage",
            )
            return True

        target_m = resolve_miner(args[0], context.miners)
        if not target_m:
            context.send_message(
                f"Minero '{args[0]}' no encontrado.",
                msg_type="ERROR",
                dedup_key="cmd_fwhy_notfound",
            )
            return True

        m_name = target_m.get("name", "")
        telemetry = _gather_fleet_telemetry(context)
        m_data = next((m for m in telemetry if m.get("name") == m_name), None)

        if not m_data:
            context.send_message(
                f"Sin telemetría disponible para {m_name}.",
                msg_type="ERROR",
                dedup_key="cmd_fwhy_nodata",
            )
            return True

        current_strategy = context.config.get("facility_agent_strategy", STRATEGY_BALANCED)
        decision = evaluate_asymmetric_allocation(telemetry, strategy=current_strategy)

        tgt_preset = decision.target_allocations.get(m_name, "2500W")
        prof = build_thermal_profile(
            m_name,
            m_data.get("chip_temp_c"),
            m_data.get("inlet_temp_c"),
            m_data.get("power_w"),
            m_data.get("preset"),
        )

        explanation = explain_miner_state(m_name, prof, tgt_preset, current_strategy)
        context.send_message(
            explanation,
            msg_type="STATUS",
            dedup_key=f"cmd_fwhy_{m_name}",
            dbg_cmd="fwhy",
            dbg_update_id=update_id,
        )
        return True
