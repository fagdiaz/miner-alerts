"""Diagnostics, Telemetry, Fusion, Health, and Quality Command Handlers (Spec 058)."""

from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path
from typing import Any, List, Optional

from app.telegram.commands.base import BaseCommandHandler
from app.telegram.command_center import format_miner_key
from app.telegram.context import TelegramRequestContext

logger = logging.getLogger("miner-alerts")


class DiagnoseCommand(BaseCommandHandler):
    name = "diagnose"
    aliases = ["diagnostico"]
    description = "Diagnóstico exhaustivo y correlación de incidentes con motor de fusión."

    def handle(
        self,
        context: TelegramRequestContext,
        args: List[str],
        update_id: Optional[int] = None,
        from_id: Optional[Any] = None,
        message_id: Optional[int] = None,
        **kwargs: Any,
    ) -> bool:
        from app.miner_monitor import (
            build_miner_diagnosis_text,
            render_multi_diagnosis,
            FusionConfig,
            IncidentAssessment,
            _FUSION_RULESET_VERSION,
            adapt_evidence_to_assessment,
            run_fusion_evaluation,
            format_incident_assessment_for_telegram,
            resolve_miner,
        )
        from app.telegram.fleet_cards import build_diagnostic_keyboard

        config = context.config
        event_store = context.event_store
        miners = context.miners

        try:
            diagnosis_stale_seconds = float(config.get("diagnosis_stale_seconds", 900.0))
        except (TypeError, ValueError):
            diagnosis_stale_seconds = 900.0
        try:
            diagnosis_firmware_window_hours = float(config.get("diagnosis_firmware_window_hours", 24.0))
        except (TypeError, ValueError):
            diagnosis_firmware_window_hours = 24.0
        try:
            diagnosis_collector_stale_seconds = float(config.get("diagnosis_collector_stale_seconds", 3600.0))
        except (TypeError, ValueError):
            diagnosis_collector_stale_seconds = 3600.0

        fusion_texts: list[str] = []
        fusion_cfg, fusion_warnings = FusionConfig.from_mapping(config)
        if fusion_cfg.enabled and event_store is not None and event_store.available:
            assessment_now_ts = time.time()
            context_s = fusion_cfg.context_hours * 3600.0
            win_start = assessment_now_ts - context_s
            target_miners = miners
            if args:
                matched = resolve_miner(args[0], miners)
                if matched:
                    target_miners = [matched]
            for m in target_miners:
                m_name = m.get("name", "")
                m_key = f"{m_name}|{m.get('host','')}:{m.get('port', 4028)}"
                samples = event_store.list_samples(m_key, start_ts=win_start, end_ts=assessment_now_ts)
                events = event_store.list_events(limit=50, miner_key=m_key)
                fw_logs = event_store.list_firmware_events(miner_name=m_name, limit=50)
                incident_data = adapt_evidence_to_assessment(m_name, samples, events, fw_logs, now_ts=assessment_now_ts)
                assessment = run_fusion_evaluation(incident_data, config=fusion_cfg)
                if assessment.recommended_action != "NO_ACTION" or assessment.confidence_level != "NONE":
                    fusion_texts.append(format_incident_assessment_for_telegram(assessment))

        if fusion_texts:
            diag_text = "\n\n".join(fusion_texts)
        else:
            miner_key_arg = args[0] if args else None
            diag_text = build_miner_diagnosis_text(
                event_store,
                miners,
                miner_key_arg,
                stale_after_seconds=diagnosis_stale_seconds,
                firmware_window_hours=diagnosis_firmware_window_hours,
                collector_stale_seconds=diagnosis_collector_stale_seconds,
            )

        diag_kb = build_diagnostic_keyboard("diagnose")
        context.send_message(
            diag_text,
            reply_markup=diag_kb,
            msg_type="DIAGNOSE",
            dedup_key="cmd_diagnose",
            dbg_cmd="diagnose",
            dbg_update_id=update_id,
        )
        return True


class FirmwareCommand(BaseCommandHandler):
    name = "firmware"
    aliases = ["fw"]
    description = "Eventos de firmware internos de Vnish y reinicios de watchdog."

    def handle(
        self,
        context: TelegramRequestContext,
        args: List[str],
        update_id: Optional[int] = None,
        from_id: Optional[Any] = None,
        message_id: Optional[int] = None,
        **kwargs: Any,
    ) -> bool:
        from app.miner_monitor import build_firmware_events_text
        from app.telegram.fleet_cards import build_diagnostic_keyboard

        firmware_text = build_firmware_events_text(
            context.event_store,
            context.miners,
            args[0] if args else None,
        )
        fw_kb = build_diagnostic_keyboard("firmware")
        context.send_message(
            firmware_text,
            reply_markup=fw_kb,
            msg_type="FIRMWARE",
            dedup_key="cmd_firmware",
            dbg_cmd="firmware",
            dbg_update_id=update_id,
        )
        return True


class QualityCommand(BaseCommandHandler):
    name = "quality"
    aliases = ["calidad"]
    description = "Calidad de minado: shares inválidos, rechazados y errores de hardware."

    def handle(
        self,
        context: TelegramRequestContext,
        args: List[str],
        update_id: Optional[int] = None,
        from_id: Optional[Any] = None,
        message_id: Optional[int] = None,
        **kwargs: Any,
    ) -> bool:
        from app.miner_monitor import build_mining_quality_text
        from app.telegram.fleet_cards import build_diagnostic_keyboard

        config = context.config
        try:
            quality_window_hours = float(config.get("quality_window_hours", 24.0))
        except (TypeError, ValueError):
            quality_window_hours = 24.0
        try:
            quality_min_intervals = int(config.get("quality_min_intervals", 3))
        except (TypeError, ValueError):
            quality_min_intervals = 3
        try:
            reject_warning_percent = float(config.get("quality_reject_warning_percent", 1.0))
        except (TypeError, ValueError):
            reject_warning_percent = 1.0
        try:
            stale_warning_percent = float(config.get("quality_stale_warning_percent", 1.0))
        except (TypeError, ValueError):
            stale_warning_percent = 1.0
        try:
            hw_error_delta_warning = int(config.get("quality_hw_error_delta_warning", 50))
        except (TypeError, ValueError):
            hw_error_delta_warning = 50
        try:
            no_share_warning_seconds = float(config.get("quality_no_share_warning_seconds", 900.0))
        except (TypeError, ValueError):
            no_share_warning_seconds = 900.0

        quality_text = build_mining_quality_text(
            context.event_store,
            context.miners,
            args[0] if args else None,
            now_ts=time.time(),
            window_hours=quality_window_hours,
            min_intervals=quality_min_intervals,
            reject_warning_percent=reject_warning_percent,
            stale_warning_percent=stale_warning_percent,
            hw_error_delta_warning=hw_error_delta_warning,
            no_share_warning_seconds=no_share_warning_seconds,
        )
        qual_kb = build_diagnostic_keyboard("quality")
        context.send_message(
            quality_text,
            reply_markup=qual_kb,
            msg_type="QUALITY",
            dedup_key="cmd_quality",
            dbg_cmd="quality",
            dbg_update_id=update_id,
        )
        return True


class HealthCommand(BaseCommandHandler):
    name = "health"
    aliases = ["salud"]
    description = "Salud y estabilidad operacional a largo plazo (7 días)."

    def handle(
        self,
        context: TelegramRequestContext,
        args: List[str],
        update_id: Optional[int] = None,
        from_id: Optional[Any] = None,
        message_id: Optional[int] = None,
        **kwargs: Any,
    ) -> bool:
        from app.miner_monitor import build_stability_health_text
        from app.telegram.fleet_cards import build_diagnostic_keyboard

        config = context.config
        try:
            window_hours = float(config.get("stability_window_hours", 168.0))
        except (TypeError, ValueError):
            window_hours = 168.0
        try:
            min_samples = int(config.get("stability_min_samples", 12))
        except (TypeError, ValueError):
            min_samples = 12
        try:
            stale_seconds = float(config.get("stability_stale_seconds", 900.0))
        except (TypeError, ValueError):
            stale_seconds = 900.0

        health_text = build_stability_health_text(
            context.event_store,
            context.miners,
            args[0] if args else None,
            now_ts=time.time(),
            window_hours=window_hours,
            min_samples=min_samples,
            stale_after_seconds=stale_seconds,
        )
        hlth_kb = build_diagnostic_keyboard("health")
        context.send_message(
            health_text,
            reply_markup=hlth_kb,
            msg_type="HEALTH",
            dedup_key="cmd_health",
            dbg_cmd="health",
            dbg_update_id=update_id,
        )
        return True


class ChartCommand(BaseCommandHandler):
    name = "chart"
    aliases = ["grafico", "grafica"]
    description = "Generación de gráficos de telemetría (hashrate, temperatura, frecuencia)."

    def handle(
        self,
        context: TelegramRequestContext,
        args: List[str],
        update_id: Optional[int] = None,
        from_id: Optional[Any] = None,
        message_id: Optional[int] = None,
        **kwargs: Any,
    ) -> bool:
        from app.miner_monitor import (
            resolve_miner,
            resolve_db_path,
            display_name,
            send_telegram_photo,
            log,
        )
        from app.telegram.charts import (
            fetch_miner_chart_data,
            fetch_fleet_chart_data,
            fetch_group_chart_data,
            render_miner_chart_png,
            render_fleet_chart_png,
            render_group_chart_png,
            build_chart_range_keyboard,
        )

        sub_target = args[0].lower() if args else "fleet"
        hours = 1.0
        if len(args) >= 2:
            try:
                val = args[1].lower().replace("h", "")
                hours = max(0.25, min(168.0, float(val)))
            except ValueError:
                hours = 1.0
        elif sub_target.endswith("h") and sub_target[:-1].isdigit():
            try:
                hours = max(0.25, min(168.0, float(sub_target[:-1])))
                sub_target = "fleet"
            except ValueError:
                hours = 1.0

        try:
            db_path = resolve_db_path(context.config)
            if sub_target in ("fleet", "all", ""):
                fleet_data = fetch_fleet_chart_data(db_path, context.miners, hours=hours)
                if fleet_data["count"] == 0:
                    context.send_message(
                        f"Gráfico: no hay muestras disponibles para la flota en las últimas {hours:.0f}h.",
                        msg_type="CHART",
                        dedup_key="chart_empty",
                        dbg_cmd="chart",
                        dbg_update_id=update_id,
                    )
                else:
                    png_bytes = render_fleet_chart_png(fleet_data, hours=hours)
                    caption = f"📊 Flota completa ({hours:.0f}h) — {fleet_data['count']} mineros activos"
                    kb = build_chart_range_keyboard("fleet", current_hours=hours)
                    send_telegram_photo(context.bot_token, str(context.chat_id), png_bytes, caption=caption, reply_markup=kb)
            else:
                groups = {
                    (_m.get("electrical_group") or _m.get("group") or "").strip().lower()
                    for _m in context.miners
                }
                groups.discard("")
                matched_group = None
                for grp in groups:
                    if sub_target == grp or sub_target == grp.replace("_", "") or sub_target in grp:
                        matched_group = grp
                        break

                if matched_group:
                    group_data = fetch_group_chart_data(db_path, matched_group, context.miners, hours=hours)
                    if group_data["count"] == 0:
                        context.send_message(
                            f"Gráfico: no hay muestras disponibles para el grupo '{matched_group}' en las últimas {hours:.0f}h.",
                            msg_type="CHART",
                            dedup_key="chart_group_empty",
                            dbg_cmd="chart",
                            dbg_update_id=update_id,
                        )
                    else:
                        png_bytes = render_group_chart_png(group_data, hours=hours)
                        caption = (
                            f"📊 Grupo {matched_group.upper()} ({hours:.0f}h) — "
                            f"{group_data['count']}/{group_data['total_miners']} mineros activos"
                        )
                        kb = build_chart_range_keyboard(matched_group, current_hours=hours)
                        send_telegram_photo(context.bot_token, str(context.chat_id), png_bytes, caption=caption, reply_markup=kb)
                else:
                    miner = resolve_miner(sub_target, context.miners)
                    if not miner:
                        avail_miners = ", ".join(display_name(m["name"]) for m in context.miners)
                        avail_groups = ", ".join(sorted(groups)) if groups else "ninguno"
                        context.send_message(
                            f"Gráfico: objetivo '{sub_target}' no encontrado.\nMineros: {avail_miners}\nGrupos: {avail_groups}",
                            msg_type="CHART",
                            dedup_key="chart_miner_not_found",
                            dbg_cmd="chart",
                            dbg_update_id=update_id,
                        )
                    else:
                        chart_data = fetch_miner_chart_data(db_path, miner["name"], hours=hours)
                        if chart_data["count"] == 0:
                            context.send_message(
                                f"Gráfico: no hay muestras disponibles para {miner['name']} en las últimas {hours:.0f}h.",
                                msg_type="CHART",
                                dedup_key="chart_empty",
                                dbg_cmd="chart",
                                dbg_update_id=update_id,
                            )
                        else:
                            png_bytes = render_miner_chart_png(chart_data, hours=hours)
                            caption = (
                                f"📊 {chart_data['miner_name']} ({hours:.0f}h) | "
                                f"Actual: {chart_data['rates'][-1]:.1f} TH/s | "
                                f"Max Temp: {chart_data['max_temp']:.0f}°C"
                            )
                            kb = build_chart_range_keyboard(chart_data["miner_id"], current_hours=hours)
                            send_telegram_photo(context.bot_token, str(context.chat_id), png_bytes, caption=caption, reply_markup=kb)
        except Exception as exc:
            log(f"CMD_CHART_ERR exc={exc}")
            context.send_message(
                f"Error al generar gráfico: {exc}",
                msg_type="CHART",
                dedup_key="chart_err",
                dbg_cmd="chart",
                dbg_update_id=update_id,
            )
        return True


class EventsCommand(BaseCommandHandler):
    name = "events"
    aliases = ["eventos"]
    description = "Historial de incidentes y eventos operacionales registrados."

    def handle(
        self,
        context: TelegramRequestContext,
        args: List[str],
        update_id: Optional[int] = None,
        from_id: Optional[Any] = None,
        message_id: Optional[int] = None,
        **kwargs: Any,
    ) -> bool:
        from app.miner_monitor import resolve_miner, render_event_list
        from app.telegram.fleet_cards import build_diagnostic_keyboard

        if context.event_store is None or not context.event_store.available:
            events_text = "Historial no disponible."
        else:
            miner_key = None
            if args:
                miner = resolve_miner(args[0], context.miners)
                if not miner:
                    context.send_message(
                        "Miner no encontrado.",
                        msg_type="ERROR",
                        dedup_key="cmd_events_notfound",
                        dbg_cmd="events",
                        dbg_update_id=update_id,
                    )
                    return True
                miner_key = format_miner_key(miner)
            recent_events = context.event_store.list_events(limit=8, miner_key=miner_key)
            events_text = (
                "Historial temporalmente no disponible."
                if context.event_store.last_error
                else render_event_list(recent_events)
            )

        events_kb = build_diagnostic_keyboard("events")
        context.send_message(
            events_text,
            reply_markup=events_kb,
            msg_type="EVENTS",
            dedup_key="cmd_events",
            dbg_cmd="events",
            dbg_update_id=update_id,
        )
        return True


class EventCommand(BaseCommandHandler):
    name = "event"
    aliases = ["evento"]
    description = "Detalle de un evento operacional específico por su identificador."

    def handle(
        self,
        context: TelegramRequestContext,
        args: List[str],
        update_id: Optional[int] = None,
        from_id: Optional[Any] = None,
        message_id: Optional[int] = None,
        **kwargs: Any,
    ) -> bool:
        from app.miner_monitor import render_event_detail

        if not args or not args[0].isdigit():
            event_text = "Uso: /event <id>"
        elif context.event_store is None or not context.event_store.available:
            event_text = "Historial no disponible."
        else:
            stored_event = context.event_store.get_event(int(args[0]))
            related_events = context.event_store.list_episode_events(int(args[0]))
            event_text = (
                "Historial temporalmente no disponible."
                if context.event_store.last_error
                else render_event_detail(stored_event, related_events=related_events)
            )
        context.send_message(
            event_text,
            msg_type="EVENTS",
            dedup_key="cmd_event",
            dbg_cmd="event",
            dbg_update_id=update_id,
        )
        return True


class WhyCommand(BaseCommandHandler):
    name = "why"
    aliases = ["porque"]
    description = "Explicación de la última decisión automática de reinicio o alerta."

    def handle(
        self,
        context: TelegramRequestContext,
        args: List[str],
        update_id: Optional[int] = None,
        from_id: Optional[Any] = None,
        message_id: Optional[int] = None,
        **kwargs: Any,
    ) -> bool:
        from app.miner_monitor import resolve_miner, render_reboot_decision

        if context.event_store is None or not context.event_store.available:
            why_text = "Diagnostico historico temporalmente no disponible."
        else:
            miner_key = None
            if args:
                miner = resolve_miner(args[0], context.miners)
                if not miner:
                    context.send_message(
                        "Miner no encontrado.",
                        msg_type="ERROR",
                        dedup_key="cmd_why_notfound",
                        dbg_cmd="why",
                        dbg_update_id=update_id,
                    )
                    return True
                miner_key = format_miner_key(miner)
            decision = context.event_store.latest_reboot_decision(miner_key=miner_key)
            why_text = (
                "Diagnostico historico temporalmente no disponible."
                if context.event_store.last_error
                else render_reboot_decision(decision)
            )

        context.send_message(
            why_text,
            msg_type="DIAGNOSE",
            dedup_key="cmd_why",
            dbg_cmd="why",
            dbg_update_id=update_id,
        )
        return True


class ChainsCommand(BaseCommandHandler):
    name = "chains"
    aliases = ["chain", "placas"]
    description = "Estado de placas de hash y chips ASIC por minero."

    def handle(
        self,
        context: TelegramRequestContext,
        args: List[str],
        update_id: Optional[int] = None,
        from_id: Optional[Any] = None,
        message_id: Optional[int] = None,
        **kwargs: Any,
    ) -> bool:
        from app.governance.chain_health import (
            assess_miner_chains,
            build_chains_card_text,
            build_chains_fleet_summary_text,
        )
        from app.telegram.fleet_cards import build_chains_keyboard
        from app.miner_monitor import resolve_miner

        target_arg = args[0].strip().lower() if args else None
        if target_arg and target_arg != "all":
            matched_miner = resolve_miner(target_arg, context.miners)
            if matched_miner:
                m_name = matched_miner.get("name", target_arg)
                m_key = format_miner_key(matched_miner)
                samples = (
                    context.event_store.get_latest_chain_samples(m_key)
                    if (context.event_store and context.event_store.available)
                    else []
                )
                ass = assess_miner_chains(m_name, samples)
                chains_msg = build_chains_card_text(ass)
                chains_kb = build_chains_keyboard(current_miner=m_name, miners=context.miners)
            else:
                chains_msg = f"⚠️ Minero '{target_arg}' no encontrado.\nUso: /chains [minero]"
                chains_kb = build_chains_keyboard(miners=context.miners)
        else:
            assessments_list = []
            for m in context.miners:
                m_key = format_miner_key(m)
                samples = (
                    context.event_store.get_latest_chain_samples(m_key)
                    if (context.event_store and context.event_store.available)
                    else []
                )
                assessments_list.append(assess_miner_chains(m.get("name", "Miner"), samples))
            chains_msg = build_chains_fleet_summary_text(assessments_list)
            chains_kb = build_chains_keyboard(miners=context.miners)

        context.send_message(
            chains_msg,
            reply_markup=chains_kb,
            msg_type="CHAINS",
            dedup_key="cmd_chains",
            dbg_cmd="chains",
            dbg_update_id=update_id,
        )
        return True


class EfficiencyCommand(BaseCommandHandler):
    name = "efficiency"
    aliases = ["eff"]
    description = "Métricas de eficiencia energética (J/TH) de la flota."

    def handle(
        self,
        context: TelegramRequestContext,
        args: List[str],
        update_id: Optional[int] = None,
        from_id: Optional[Any] = None,
        message_id: Optional[int] = None,
        **kwargs: Any,
    ) -> bool:
        from app.governance.energy_efficiency import (
            fetch_latest_efficiency_assessments,
            build_efficiency_table_text,
            build_miner_efficiency_detail_text,
        )
        from app.telegram.fleet_cards import build_diagnostic_keyboard
        from app.miner_monitor import resolve_db_path, resolve_miner

        db_p = resolve_db_path(context.config)
        with context.state_lock:
            assessments = fetch_latest_efficiency_assessments(
                db_path=db_p,
                miners=context.miners,
                states=context.states,
                config=context.config,
            )
        target_arg = args[0].strip().lower() if args else None
        eff_kb = None
        if target_arg and target_arg != "all":
            from app.telegram.command_center import find_assessment_by_target
            matched_ass = find_assessment_by_target(assessments, target_arg, context.miners)
            if matched_ass:
                eff_msg = build_miner_efficiency_detail_text(matched_ass)
            else:
                eff_msg = f"⚠️ Minero '{target_arg}' no encontrado.\nUso: /efficiency [minero]"
        else:
            eff_msg = build_efficiency_table_text(assessments)
            eff_kb = build_diagnostic_keyboard("eff")

        context.send_message(
            eff_msg,
            reply_markup=eff_kb,
            msg_type="EFFICIENCY",
            dedup_key="cmd_efficiency",
            dbg_cmd="efficiency",
            dbg_update_id=update_id,
        )
        return True


class PresetsCommand(BaseCommandHandler):
    name = "presets"
    aliases = ["preset", "profile"]
    description = "Perfiles de overclocking y voltajes configurados en la flota."

    def handle(
        self,
        context: TelegramRequestContext,
        args: List[str],
        update_id: Optional[int] = None,
        from_id: Optional[Any] = None,
        message_id: Optional[int] = None,
        **kwargs: Any,
    ) -> bool:
        from app.vnish.presets import (
            fetch_latest_preset_assessments,
            build_presets_table_text,
            build_miner_preset_detail_text,
        )
        from app.telegram.fleet_cards import build_diagnostic_keyboard
        from app.miner_monitor import resolve_db_path, resolve_miner

        db_p = resolve_db_path(context.config)
        with context.state_lock:
            assessments = fetch_latest_preset_assessments(
                db_path=db_p,
                miners=context.miners,
                states=context.states,
                config=context.config,
            )
        target_arg = args[0].strip().lower() if args else None
        preset_kb = None
        if target_arg and target_arg != "all":
            from app.telegram.command_center import find_assessment_by_target
            matched_ass = find_assessment_by_target(assessments, target_arg, context.miners)
            if matched_ass:
                preset_msg = build_miner_preset_detail_text(matched_ass)
            else:
                preset_msg = f"⚠️ Minero '{target_arg}' no encontrado.\nUso: /presets [minero]"
        else:
            preset_msg = build_presets_table_text(assessments)
            preset_kb = build_diagnostic_keyboard("presets")

        context.send_message(
            preset_msg,
            reply_markup=preset_kb,
            msg_type="PRESETS",
            dedup_key="cmd_presets",
            dbg_cmd="presets",
            dbg_update_id=update_id,
        )
        return True


class SelftestCommand(BaseCommandHandler):
    name = "selftest"
    aliases = ["test"]
    description = "Autoprueba integral de conectividad, base de datos, Hashcore y Telegram."

    def handle(
        self,
        context: TelegramRequestContext,
        args: List[str],
        update_id: Optional[int] = None,
        from_id: Optional[Any] = None,
        message_id: Optional[int] = None,
        **kwargs: Any,
    ) -> bool:
        from app.miner_monitor import (
            read_summary,
            _hashcore_cli_path,
            _NO_WINDOW_CREATION_FLAGS,
            qa_verbose_enabled,
            log,
        )

        cmd_start = time.monotonic()
        responded = 0
        for miner in context.miners:
            rate, _, ok, _ = read_summary(miner["host"], miner.get("port", 4028), timeout=5)
            if ok:
                responded += 1
        total = len(context.miners)

        hashcore_ok = "FAIL"
        cli_path = _hashcore_cli_path(context.hashcore_cfg)
        if context.hashcore_cfg.get("enabled", True) and cli_path and Path(cli_path).exists():
            try:
                cmd = ["cmd.exe", "/c", cli_path, "version"]
                result = subprocess.run(
                    cmd,
                    cwd=context.hashcore_cfg.get("working_dir") or None,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=10,
                    shell=False,
                    creationflags=_NO_WINDOW_CREATION_FLAGS,
                )
                if result.returncode != 0:
                    cmd = ["cmd.exe", "/c", cli_path, "--help"]
                    result = subprocess.run(
                        cmd,
                        cwd=context.hashcore_cfg.get("working_dir") or None,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        timeout=10,
                        shell=False,
                        creationflags=_NO_WINDOW_CREATION_FLAGS,
                    )
                hashcore_ok = "OK" if result.returncode == 0 else "FAIL"
            except Exception:
                hashcore_ok = "FAIL"
        else:
            hashcore_ok = f"FAIL (cli_path={cli_path or 'VACIO'})"

        history_status = (
            "DISABLED"
            if context.event_store is None
            else ("OK" if context.event_store.available else "FAIL")
        )
        msg_text = (
            f"SELFTEST: Telegram=OK Hashcore={hashcore_ok} "
            f"History={history_status} Miners={responded}/{total}"
        )
        context.send_message(
            msg_text,
            msg_type="SELFTEST",
            dedup_key="cmd_selftest",
            dbg_cmd="selftest",
            dbg_update_id=update_id,
        )
        return True
