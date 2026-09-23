"""
Power Progression Orchestrator Telegram Command Handler (Spec 079 / PROP-014).

Provides interactive supervision and manual profile steering for the
multi-tier power progression and graceful fallback orchestrator:
- /progression: View active profile, elevator power, miner constraints, and next action.
- /progression <profile>: Set desired progression profile (c0, c1, c2, c4, etc.).
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from app.telegram.commands.base import BaseCommandHandler
from app.telegram.context import TelegramRequestContext
from app.governance.power_progression import (
    PROFILE_ALIASES,
    PROFILE_TARGETS,
    PROFILE_C0_BASE_STABLE,
    PROFILE_C1_ASYMMETRIC,
    PROFILE_C2_ELEV1_BALANCED,
    PROFILE_C4_MAX_POWER,
    ProgressionDecision,
    evaluate_progression_cycle,
    get_global_progression_state,
    set_global_desired_profile,
    parse_preset_w,
)


def _gather_progression_telemetry(context: TelegramRequestContext) -> List[Dict[str, Any]]:
    """Extract live telemetry snapshot from miners and runtime states."""
    telemetry: List[Dict[str, Any]] = []
    with context.state_lock:
        for m in context.miners:
            name = m.get("name", "")
            host = m.get("host", "")
            port = m.get("port", 4028)
            sk = f"{name}|{host}:{port}"
            st = context.states.get(sk)

            chip_t = (
                getattr(st, "last_max_chip_temp", None)
                or getattr(st, "governor_last_temp_c", None)
                or getattr(st, "last_temp_c", None)
                or 0.0
            )
            fan_duty = (
                getattr(st, "last_fan_duty_percent", None)
                or getattr(st, "fan_duty", None)
                or 0.0
            )
            pwr = (
                getattr(st, "last_power_w", None)
                or getattr(st, "governor_last_power_w", None)
                or 2500.0
            )
            preset = getattr(st, "balancer_preset", None) or "2500W"

            # Derive ground truth preset wattage if power is known
            if pwr and pwr >= 500:
                if pwr >= 2600:
                    preset = "2700W"
                elif pwr >= 2400:
                    preset = "2500W"
                elif pwr >= 2200:
                    preset = "2300W"

            telemetry.append({
                "name": name,
                "host": host,
                "port": port,
                "electrical_group": m.get("electrical_group") or m.get("group", "elevator_1"),
                "chip_temp_c": float(chip_t),
                "fan_duty_pct": float(fan_duty),
                "power_w": float(pwr),
                "preset": str(preset),
                "max_hardware_preset": m.get("max_hardware_preset"),
            })
    return telemetry


class ProgressionCommand(BaseCommandHandler):
    name = "progression"
    aliases = ["prog", "perfil", "profiles", "power_progression"]
    description = "Supervisión y control del orquestador de progresión de potencia (C0, C1, C2, C4)."

    def handle(
        self,
        context: TelegramRequestContext,
        args: List[str],
        update_id: Optional[int] = None,
        from_id: Optional[Any] = None,
        message_id: Optional[int] = None,
        **kwargs: Any,
    ) -> bool:
        now_ts = time.time()
        prog_state = get_global_progression_state()

        if args:
            sub = args[0].strip().lower()
            if sub not in ("status", "info"):
                # Profile mutation request
                ok, target_or_err = set_global_desired_profile(sub)
                if not ok:
                    context.send_message(
                        f"❌ {target_or_err}",
                        msg_type="ERROR",
                        dedup_key="cmd_prog_err",
                    )
                    return True

                desired_targets = PROFILE_TARGETS.get(target_or_err, {})
                lines = [
                    "🎯 *PERFIL OBJETIVO ACTUALIZADO*",
                    "────────────────────────────",
                    f"• Nuevo perfil deseado: *{target_or_err}*",
                    "• Asignación proyectada:",
                ]
                for m_name, p_val in sorted(desired_targets.items()):
                    lines.append(f"  - {m_name}: *{p_val}*")
                lines.extend([
                    "────────────────────────────",
                    "El orquestador evaluará la progresión en el próximo ciclo con reposo de 15m y compuertas de seguridad.",
                ])
                context.send_message(
                    "\n".join(lines),
                    msg_type="STATUS",
                    dedup_key="cmd_prog_updated",
                )
                return True

        # Telemetry & progression evaluation
        telemetry = _gather_progression_telemetry(context)
        decision: ProgressionDecision = evaluate_progression_cycle(
            telemetry_list=telemetry,
            state=prog_state,
            now_ts=now_ts,
            config=context.config,
        )

        total_pwr = sum(m.get("power_w", 0.0) for m in telemetry)
        elev1_pwr = sum(m.get("power_w", 0.0) for m in telemetry if m.get("electrical_group") == "elevator_1")
        elev2_pwr = sum(m.get("power_w", 0.0) for m in telemetry if m.get("electrical_group") == "elevator_2")

        lines = [
            "⚡ *POWER PROGRESSION ORCHESTRATOR*",
            "────────────────────────────",
            f"• Perfil Activo: *{prog_state.current_profile}*",
            f"• Perfil Objetivo: *{prog_state.desired_profile}*",
            f"• Potencia Total: *{total_pwr:.0f} W* (~{total_pwr / 1000.0:.2f} kW)",
            "────────────────────────────",
            f"🏢 *ELEVADOR 1* ({elev1_pwr:.0f}W / 5400W máx):",
        ]

        # Elev 1 miners
        for m in sorted([x for x in telemetry if x.get("electrical_group") == "elevator_1"], key=lambda x: x.get("name", "")):
            m_name = m.get("name", "")
            preset = m.get("preset", "2500W")
            t_chip = m.get("chip_temp_c", 0.0)
            duty = m.get("fan_duty_pct", 0.0)
            status_tag = "🚀 2700W" if parse_preset_w(preset) >= 2700 else "🛡️ 2500W"
            if duty >= 95.0:
                status_tag += " (⚠️ Fans saturados)"
            lines.append(f"  - {m_name}: *{preset}* (T={t_chip:.1f}°C, Fans={duty:.0f}%, {status_tag})")

        lines.append(f"🏢 *ELEVADOR 2* ({elev2_pwr:.0f}W / 5400W máx):")
        # Elev 2 miners
        for m in sorted([x for x in telemetry if x.get("electrical_group") == "elevator_2"], key=lambda x: x.get("name", "")):
            m_name = m.get("name", "")
            preset = m.get("preset", "2500W")
            t_chip = m.get("chip_temp_c", 0.0)
            duty = m.get("fan_duty_pct", 0.0)
            status_tag = "🚀 2700W" if parse_preset_w(preset) >= 2700 else "🛡️ 2500W"
            hw_lim = m.get("max_hardware_preset")
            if hw_lim and parse_preset_w(hw_lim) <= 2500:
                status_tag += " (🔒 Techo HW)"
            elif duty >= 95.0:
                status_tag += " (⚠️ Fans saturados)"
            lines.append(f"  - {m_name}: *{preset}* (T={t_chip:.1f}°C, Fans={duty:.0f}%, {status_tag})")

        lines.extend([
            "────────────────────────────",
            "🔍 *ESTADO DEL ORQUESTADOR*:",
            f"• Acción: `{decision.action}`",
            f"• Motivo: {decision.reason}",
            "────────────────────────────",
            "💡 Comandos de perfil:",
            "• `/progression c0` (Base 4x 2500W, 10.0 kW)",
            "• `/progression c1` (Asimétrica 2700/2700/2500/2700, 10.6 kW)",
            "• `/progression c2` (Elev1 Balance 2700/2500/2500/2700, 10.4 kW)",
            "• `/progression c4` (Máxima potencia 4x 2700W, 10.8 kW)",
        ])

        context.send_message(
            "\n".join(lines),
            msg_type="STATUS",
            dedup_key="cmd_prog_dashboard",
            dbg_cmd="progression",
            dbg_update_id=update_id,
        )
        return True
