import json
import os
import re
import socket
import sys
import threading
import time
import ctypes
import subprocess
import random
import queue
import platform
import hashlib
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

# Ensure repository root is in sys.path so 'import app.xxx' works from both root and app/ directory
_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import requests

from app.core import (
    AcquisitionConfig,
    AcquisitionEpoch,
    Api4028Transport,
    BoundedAcquirer,
    EventStore,
    FusionConfig,
    IncidentAssessment,
    IrregularEpisodeCoordinator,
    MinerEndpoint,
    MonitorHeartbeat,
    analyze_mining_quality,
    analyze_stability,
    classify_restart,
    dispatch_authoritative,
    evaluate_auto_reboot_interlocks,
    format_current_status_line,
    normalize_mining_quality,
    render_episode_notification_batch,
    render_event_detail,
    render_event_list,
    render_mining_quality,
    render_reboot_decision,
    render_stability_assessment,
    write_heartbeat_atomic,
)
from app.core.evidence_fusion import (
    RULESET_VERSION as _FUSION_RULESET_VERSION,
    compute_evidence_digest as _compute_evidence_digest,
    render_assessment_telegram as _render_assessment_telegram,
)
from app.vnish import (
    VnishTelemetry,
    assess_miner_preset,
    build_miner_preset_detail_text,
    build_presets_table_text,
    evaluate_preset_alerts,
    fetch_latest_preset_assessments,
    get_miner_status,
    get_overclock_settings,
    infer_operating_profile,
    mask_secret,
    normalize_vnish_stats,
    parse_miner_status_flags,
    render_firmware_events,
    safe_get_overclock_settings,
    safe_restart_mining,
    safe_set_fan_duty,
    safe_set_miner_preset,
)
from app.telegram import (
    CallbackTokenRegistry,
    build_alert_keyboard,
    build_confirmation_keyboard,
    build_settled_keyboard,
    classify_delivery,
    parse_callback_data,
    split_telegram_message,
)
from app.governance import (
    ACTION_EMERGENCY_SPIKE,
    ACTION_FAILSAFE_FAULT,
    ACTION_HOLD_DWELL,
    ACTION_HOLD_TARGET,
    ACTION_RECOVERY_MAX_COOLING,
    ACTION_STEP_DOWN,
    ACTION_STEP_DOWN_HW_ERRORS,
    ACTION_STEP_UP,
    BalancerConfig,
    BalancerDecision,
    ElevatorSensitivitySummary,
    GovernorConfig,
    GovernorDecision,
    StabilityMetrics,
    analyze_elevator_sensitivity,
    assess_miner_cooling,
    assess_miner_efficiency,
    build_balancer_table_text,
    build_efficiency_table_text,
    build_elevator_sensitivity_text,
    build_fans_table_text,
    build_miner_balancer_detail_text,
    build_miner_efficiency_detail_text,
    build_miner_fan_detail_text,
    calculate_efficiency_j_th,
    compute_governor_step,
    evaluate_balancer_step,
    evaluate_cooling_alerts,
    evaluate_efficiency_alerts,
    extract_miner_stability_metrics,
    fetch_latest_cooling_assessments,
    fetch_latest_efficiency_assessments,
    record_elevator_restart_circumstance,
    render_hw_error_tripwire_card,
)

STATE_OK = "OK"
STATE_LOW = "LOW"
STATE_OFFLINE = "OFFLINE"
STATE_HASHBOARD = "HASHBOARD"

AUTO_REBOOT_SIGNAL_ELIGIBLE = "eligible"
AUTO_REBOOT_SIGNAL_INVALID = "invalid_signal"
AUTO_REBOOT_SIGNAL_NOT_LOW = "not_low"

_MUTEX_HANDLE: Optional[int] = None
_TELEGRAM_QUEUE: Optional[queue.Queue] = None
_TELEGRAM_QUEUE_LOCK = threading.Lock()
_LAST_ENQUEUED: Dict[str, float] = {}
_COALESCE_WINDOWS = {"STATUS": 5, "STARTUP": 5, "STATE_CHANGE": 35}
_LAST_SENT_META: Dict[str, Optional[str]] = {"type": None, "ts": None}
_LAST_SENT_HASH: Dict[str, str] = {}
_LAST_SENT_TS: Dict[str, float] = {}
_QA_MODE: bool = False
_CLI_MISSING_NOTIFIED: Dict[str, float] = {}
_QA_BLOCKED_NOTIFIED: Dict[str, float] = {}
_QA_BLOCKED_LOGGED: bool = False
_LOGGER: Optional[logging.Logger] = None
_QA_TX_COUNTS: Dict[int, int] = {}
_PERF_LOGGED: Dict[int, bool] = {}
_HTTP_SESSION: Optional[requests.Session] = None
_TELEGRAM_POLLER_TS: Optional[float] = None
_TELEGRAM_SENDER_TS: Optional[float] = None
_NO_WINDOW_CREATION_FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)
DBG_TELEGRAM = os.getenv("DBG_TELEGRAM", "0") == "1"
DBG_TELEGRAM_COMMANDS_ONLY = os.getenv("DBG_TELEGRAM_COMMANDS_ONLY", "1") == "1"
try:
    DBG_TELEGRAM_TRUNC = int(os.getenv("DBG_TELEGRAM_TRUNC", "120"))
except ValueError:
    DBG_TELEGRAM_TRUNC = 120
CMD_WHITELIST = {
    "help",
    "status",
    "info",
    "events",
    "event",
    "why",
    "health",
    "quality",
    "diagnose",
    "chart",
    "fans",
    "fan",
    "efficiency",
    "eff",
    "presets",
    "preset",
    "profile",
    "firmware",
    "selftest",
    "reboot",
    "restart",
    "reboot_no_ok",
    "confirm",
    "snooze",
    "unsnooze",
    "snoozed",
    "digest",
    "summary",
    "governor",
    "gov",
    "balancer",
    "bal",
    "power",
    "elevadores",
    "elevators",
    "sensibilidad",
    "elev",
    "menu",
    "start",
    "panel",
    "silent",
    "silencio",
    "modo_silencio",
    "shutdown",
    "stop",
    "apagar",
    "parada",
    "resume",
    "reanudar",
    "schedule_maintenance",
    "schedule",
    "programar",
    "scheduled",
    "programado",
    "interventions",
    "intervenciones",
    "contingency",
    "contingencia",
}


def _is_command_like(cmd_name: str) -> bool:
    if cmd_name in CMD_WHITELIST:
        return True
    if cmd_name.startswith("rb") and cmd_name[2:].isdigit():
        return True
    if cmd_name.startswith("c") and cmd_name[1:].isdigit():
        return True
    return False


def log(msg: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    if _LOGGER:
        _LOGGER.info(line)
    else:
        print(line, flush=True)


def _short_text(text: str, limit: int = 160) -> str:
    if text is None:
        return ""
    clean = text.replace("\n", " ").replace("\r", " ")
    if len(clean) <= limit:
        return clean
    return clean[:limit] + "..."

def _trunc(text: Optional[str], limit: int) -> str:
    if text is None:
        return ""
    raw = repr(str(text))
    if len(raw) <= limit:
        return raw
    return raw[:limit] + "..."


def _redact_telegram_token(value: object, bot_token: Optional[str]) -> str:
    text = str(value)
    if bot_token:
        text = text.replace(bot_token, "<redacted>")
    return re.sub(
        r"(https://api\.telegram\.org/bot)[^/\s?'\"]+",
        r"\1<redacted>",
        text,
    )


def _entities_summary(entities: list) -> str:
    if not isinstance(entities, list) or not entities:
        return "none"
    parts = []
    for ent in entities[:6]:
        etype = ent.get("type", "?")
        off = ent.get("offset", "?")
        length = ent.get("length", "?")
        parts.append(f"{etype}@{off}+{length}")
    more = ""
    if len(entities) > 6:
        more = f"+{len(entities) - 6}more"
    return ",".join(parts) + (f" {more}" if more else "")

def init_logger_from_config(config: dict) -> None:
    global _LOGGER
    log_file_path = str(config.get("log_file_path", "") or "").strip()
    if not log_file_path:
        return
    log_path = Path(log_file_path)
    if log_path.parent and str(log_path.parent) != ".":
        os.makedirs(log_path.parent, exist_ok=True)
    logger = logging.getLogger("miner-alerts")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    formatter = logging.Formatter("%(message)s")
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    from logging.handlers import RotatingFileHandler
    max_bytes = int(config.get("log_max_bytes", 50 * 1024 * 1024))
    backup_count = int(config.get("log_backup_count", 3))
    file_handler = RotatingFileHandler(
        log_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8", mode="a"
    )
    file_handler.setFormatter(formatter)
    logger.handlers.clear()
    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)
    _LOGGER = logger


def log_pid(msg: str) -> None:
    log(f"PID={os.getpid()} {msg}")


def qa_enabled(config: Mapping[str, Any]) -> Tuple[bool, str]:
    force_env = os.getenv("QA_MODE_FORCE", "").strip().lower()
    if force_env in ("1", "true", "yes", "on"):
        env = os.getenv("QA_MODE", "").strip().lower()
        if env in ("1", "true", "yes", "on"):
            return True, "env-forced"
        if env in ("0", "false", "no", "off"):
            return False, "env-forced"
    return bool(config.get("qa_mode", False)), "config"

def qa_notify_enabled(config: Mapping[str, Any]) -> bool:
    env = os.getenv("QA_NOTIFY", "").strip().lower()
    if env in ("1", "true", "yes", "on"):
        return True
    if env in ("0", "false", "no", "off"):
        return False
    return bool(config.get("qa_notify", False))

def qa_allow_real_actions(config: Mapping[str, Any]) -> bool:
    env = os.getenv("QA_ALLOW_REAL_ACTIONS", "").strip().lower()
    if env in ("1", "true", "yes", "on"):
        return True
    if env in ("0", "false", "no", "off"):
        return False
    return bool(config.get("qa_allow_real_actions", False))


def qa_verbose_enabled(config: Mapping[str, Any]) -> bool:
    env = os.getenv("QA_VERBOSE", "").strip().lower()
    if env in ("1", "true", "yes", "on"):
        return True
    if env in ("0", "false", "no", "off"):
        return False
    return bool(config.get("qa_verbose", False))


_COMMANDS = [
    {
        "name": "help",
        "summary": "Muestra ayuda general o detallada.",
        "usage": "/help  |  /help <comando>",
        "detail": [
            "Detalle: lista comandos y muestra ayuda por comando.",
        ],
        "examples": ["/help reboot"],
        "notes": [],
        "danger_level": "safe",
        "aliases": [],
    },
    {
        "name": "status",
        "summary": "Snapshot actual de todos los mineros.",
        "usage": "/status",
        "detail": [
            "Detalle: muestra hashrate y etiquetas actuales.",
        ],
        "examples": ["/status"],
        "notes": [],
        "danger_level": "safe",
        "aliases": [],
    },
    {
        "name": "info",
        "summary": "Detalle resumido de mineros.",
        "usage": "/info  |  /info all  |  /info <miner>",
        "detail": [
            "Detalle: info de no-OK o del minero indicado.",
        ],
        "examples": ["/info", "/info all", "/info 23"],
        "notes": ["Algunos campos dependen del firmware."],
        "danger_level": "safe",
        "aliases": [],
    },
    {
        "name": "events",
        "summary": "Historial reciente de eventos e incidentes.",
        "usage": "/events  |  /events <miner>",
        "detail": [
            "Detalle: consulta eventos locales sin conectarse al minero.",
        ],
        "examples": ["/events", "/events 23"],
        "notes": ["Usa /event <id> para abrir un evento."],
        "danger_level": "safe",
        "aliases": [],
    },
    {
        "name": "event",
        "summary": "Detalle de un incidente registrado.",
        "usage": "/event <id>",
        "detail": [
            "Detalle: muestra evidencia y clasificacion del evento indicado.",
        ],
        "examples": ["/event 42"],
        "notes": ["Es de solo lectura."],
        "danger_level": "safe",
        "aliases": [],
        "official_aliases": ["/e<ID>"],
    },
    {
        "name": "why",
        "summary": "Explica la ultima decision de auto-reboot.",
        "usage": "/why  |  /why <miner>",
        "detail": [
            "Detalle: consulta evidencia local sin conectarse al minero.",
        ],
        "examples": ["/why", "/why 23"],
        "notes": ["El voltaje de cadena no representa voltaje AC de entrada."],
        "danger_level": "safe",
        "aliases": [],
    },
    {
        "name": "health",
        "summary": "Compara la telemetria con el baseline estable del minero.",
        "usage": "/health  |  /health all  |  /health <miner>",
        "detail": [
            "Detalle: diagnostico historico read-only sin conectarse al minero.",
        ],
        "examples": ["/health", "/health 23"],
        "notes": ["WATCH es evidencia para revisar; no ejecuta acciones."],
        "danger_level": "safe",
        "aliases": [],
    },
    {
        "name": "quality",
        "summary": "Analiza shares, errores y estado de cadenas por intervalo.",
        "usage": "/quality  |  /quality all  |  /quality <miner>",
        "detail": [
            "Detalle: diagnostico historico read-only de calidad de minado.",
        ],
        "examples": ["/quality", "/quality 23"],
        "notes": ["Una transicion/autotune se observa; no ejecuta acciones."],
        "danger_level": "safe",
        "aliases": [],
    },
    {
        "name": "firmware",
        "summary": "Muestra evidencia Vnish normalizada desde SQLite.",
        "usage": "/firmware  |  /firmware all  |  /firmware <miner>",
        "detail": [
            "Detalle: consulta eventos de firmware recolectados sin conectarse al minero.",
        ],
        "examples": ["/firmware", "/firmware 23"],
        "notes": ["Es de solo lectura y no ejecuta acciones."],
        "danger_level": "safe",
        "aliases": [],
    },
    {
        "name": "diagnose",
        "summary": "Correlaciona evidencia operativa local por minero.",
        "usage": "/diagnose  |  /diagnose all  |  /diagnose <miner>",
        "detail": [
            "Detalle: combina senal, eventos, decisiones y Vnish desde SQLite.",
        ],
        "examples": ["/diagnose", "/diagnose 23"],
        "notes": ["Es advisory, de solo lectura y no autoriza acciones."],
        "danger_level": "safe",
        "aliases": [],
    },
    {
        "name": "chart",
        "summary": "Genera y envia grafico visual PNG de telemetria.",
        "usage": "/chart  |  /chart <miner> [horas]  |  /chart fleet [horas]",
        "detail": [
            "Detalle: genera curvas de hashrate, umbral y temperaturas desde SQLite.",
        ],
        "examples": ["/chart", "/chart 23", "/chart fleet 24h"],
        "notes": ["Es visual, de solo lectura y se renderiza 100% en memoria."],
        "danger_level": "safe",
        "aliases": [],
    },
    {
        "name": "fans",
        "summary": "Monitorea RPM, PWM %, temperatura máxima y margen térmico.",
        "usage": "/fans  |  /fans all  |  /fans <miner>",
        "detail": [
            "Detalle: supervisa salud de ventiladores, saturación de flujo y margen hacia el corte de 85°C.",
        ],
        "examples": ["/fans", "/fans 23"],
        "notes": ["Es analítico, de solo lectura y se entrega instantáneamente."],
        "danger_level": "safe",
        "aliases": ["fan"],
    },
    {
        "name": "chains",
        "summary": "Salud granular y sensores por placa/hashboard.",
        "usage": "/chains  |  /chains all  |  /chains <miner>",
        "detail": [
            "Detalle: diagnostico predictivo de silicio y bus de sensores I2C por cadena.",
        ],
        "examples": ["/chains", "/chains 24"],
        "notes": ["Identifica placas con sensores en error o deficit de hashrate."],
        "danger_level": "safe",
        "aliases": ["chain", "placas"],
    },
    {
        "name": "efficiency",
        "summary": "Analiza el consumo y ratio de eficiencia en Joules por Terahash (J/TH).",
        "usage": "/efficiency  |  /efficiency all  |  /efficiency <miner>",
        "detail": [
            "Detalle: calcula J/TH en tiempo real (Watts / TH/s) y detecta degradación eléctrica de cadenas.",
        ],
        "examples": ["/efficiency", "/efficiency 23", "/eff"],
        "notes": ["Es analítico, de solo lectura y se entrega instantáneamente."],
        "danger_level": "safe",
        "aliases": ["eff"],
    },
    {
        "name": "presets",
        "summary": "Monitorea frecuencias (MHz), tensión (V) y estado de autotuning Vnish.",
        "usage": "/presets  |  /presets all  |  /presets <miner>",
        "detail": [
            "Detalle: supervisa perfiles de consumo/frecuencia inferidos y estado de calibración dinámica del firmware.",
        ],
        "examples": ["/presets", "/presets 23", "/preset", "/profile"],
        "notes": ["Es analítico, de solo lectura y se entrega instantáneamente."],
        "danger_level": "safe",
        "aliases": ["preset", "profile"],
    },
    {
        "name": "governor",
        "summary": "Controlador térmico de lazo cerrado para coolers Vnish.",
        "usage": "/gov  |  /gov on  |  /gov off  |  /gov set <temp>",
        "detail": [
            "Detalle: supervisa y modula el % PWM para sostener temperatura objetivo estable evitando oscilaciones.",
        ],
        "examples": ["/gov", "/gov on", "/gov off", "/gov set 82.0"],
        "notes": ["Soporta modo dry-run para operar con total seguridad."],
        "danger_level": "safe",
        "aliases": ["gov"],
    },
    {
        "name": "balancer",
        "summary": "Balanceador dinámico de potencia y presets para protección de elevadores.",
        "usage": "/balancer  |  /balancer on  |  /balancer off  |  /balancer setmax <miner> <preset>",
        "detail": [
            "Detalle: optimiza presets Vnish contra reinicios por sensibilidad eléctrica y maximiza hashrate neto.",
        ],
        "examples": ["/balancer", "/balancer on", "/balancer 23", "/balancer setmax 23 2500W"],
        "notes": ["Arranca en dry-run seguro por defecto."],
        "danger_level": "safe",
        "aliases": ["bal", "power"],
    },
    {
        "name": "elevadores",
        "summary": "Diagnóstico de carga eléctrica y sensibilidad de elevadores de tensión.",
        "usage": "/elevadores",
        "detail": [
            "Detalle: correlaciona carga combinada (Watts), reinicios y caídas en cascada por elevador para encontrar la configuración óptima.",
        ],
        "examples": ["/elevadores", "/sensibilidad"],
        "notes": ["Es analítico y de solo lectura."],
        "danger_level": "safe",
        "aliases": ["elevators", "sensibilidad", "elev"],
    },
    {
        "name": "snooze",
        "summary": "Silencia alertas y autorreinicios por mantenimiento.",
        "usage": "/snooze <miner|all> [minutos]",
        "detail": [
            "Detalle: suspende temporalmente alertas y autorreinicios para tareas de mantenimiento.",
        ],
        "examples": ["/snooze 23 60", "/snooze all 30"],
        "notes": ["Por defecto 60 minutos (máx 1440m/24h)."],
        "danger_level": "safe",
        "aliases": [],
    },
    {
        "name": "unsnooze",
        "summary": "Reactiva la supervision normal de un minero silenciado.",
        "usage": "/unsnooze <miner|all>",
        "detail": [
            "Detalle: cancela el silenciamiento y reactiva alertas y autorreinicios inmediatamente.",
        ],
        "examples": ["/unsnooze 23", "/unsnooze all"],
        "notes": [],
        "danger_level": "safe",
        "aliases": [],
    },
    {
        "name": "snoozed",
        "summary": "Lista los mineros actualmente silenciados y tiempo restante.",
        "usage": "/snoozed",
        "detail": [
            "Detalle: muestra el estado de todos los mineros bajo mantenimiento.",
        ],
        "examples": ["/snoozed"],
        "notes": [],
        "danger_level": "safe",
        "aliases": [],
    },
    {
        "name": "digest",
        "summary": "Reporte ejecutivo 24h de salud, métricas y backups.",
        "usage": "/digest  |  /summary",
        "detail": [
            "Detalle: genera el resumen consolidado de las últimas 24 horas (uptime, TH/s, J/TH, shares, eventos, backup).",
        ],
        "examples": ["/digest", "/summary"],
        "notes": ["Es analítico, de solo lectura y se entrega instantáneamente."],
        "danger_level": "safe",
        "aliases": ["summary"],
    },
    {
        "name": "selftest",
        "summary": "Chequeo rapido de Telegram/Hashcore/mineros.",
        "usage": "/selftest  |  /test",
        "detail": [
            "Detalle: valida conectividad y reporte basico.",
        ],
        "examples": ["/selftest"],
        "notes": [],
        "danger_level": "safe",
        "aliases": ["test"],
    },
    {
        "name": "reboot",
        "summary": "Solicita reboot manual (con confirmacion).",
        "usage": "/reboot  |  /reboot <miner>",
        "detail": [
            "Detalle: genera un codigo y pide confirmacion.",
        ],
        "examples": ["/rb23", "/reboot 23"],
        "notes": ["Siempre requiere confirmacion antes de ejecutar."],
        "danger_level": "danger",
        "aliases": [],
        "official_aliases": ["/rb<ID>"],
    },
    {
        "name": "reboot_no_ok",
        "summary": "Prepara un reboot agrupado de mineros NO-OK.",
        "usage": "/reboot_no_ok",
        "detail": [
            "Detalle: crea un preview acotado y un codigo; no ejecuta sin confirmacion.",
        ],
        "examples": ["/reboot_no_ok"],
        "notes": ["Confirmar con el atajo /c<code> recibido en el preview."],
        "danger_level": "danger",
        "aliases": [],
        "official_aliases": [],
    },
    {
        "name": "restart",
        "summary": "Solicita restart manual (con confirmacion).",
        "usage": "/restart <miner>",
        "detail": [
            "Detalle: genera un codigo y pide confirmacion.",
        ],
        "examples": ["/restart 23", "/confirm restart 23 123456"],
        "notes": [],
        "danger_level": "danger",
        "aliases": [],
        "official_aliases": [],
    },
    {
        "name": "confirm",
        "summary": "Confirma una accion pendiente.",
        "usage": "/confirm reboot <miner> <code>  |  /confirm restart <miner> <code>",
        "detail": [
            "Detalle: ejecuta la accion pendiente con codigo.",
        ],
        "examples": ["/confirm reboot 23 123456"],
        "notes": ["El atajo /c<code> confirma un preview de /reboot_no_ok."],
        "danger_level": "danger",
        "aliases": [],
        "official_aliases": ["/c<code>"],
    },
    {
        "name": "menu",
        "summary": "Command Center interactivo con botones.",
        "usage": "/menu  |  /start  |  /panel",
        "detail": [
            "Detalle: abre el panel de control táctil con métricas agregadas y accesos rápidos.",
        ],
        "examples": ["/menu", "/start"],
        "notes": [],
        "danger_level": "safe",
        "aliases": ["start", "panel"],
    },
    {
        "name": "silent",
        "summary": "Modo silencio para coolers (30-50% PWM).",
        "usage": "/silent <duración|off>",
        "detail": [
            "Detalle: limita ventiladores al 30%-50% con guarda térmica de reversión ante >80°C.",
        ],
        "examples": ["/silent 2h", "/silent off"],
        "notes": ["Duraciones: 30m, 1h, 2h, 4h, 6h, indef, off."],
        "danger_level": "safe",
        "aliases": ["silencio", "modo_silencio"],
    },
]


def render_help_index() -> str:
    from app.telegram.help_center import render_legacy_help_index
    return render_legacy_help_index()


def render_help_detail(cmd_name: str) -> str:
    from app.telegram.help_center import render_legacy_help_detail
    return render_legacy_help_detail(cmd_name)


def _normalize_cmd_token(cmd_token: str) -> str:
    if not cmd_token:
        return ""
    t = cmd_token.strip()
    if t.startswith("/"):
        t = t[1:]
    if "@" in t:
        t = t.split("@", 1)[0]
    t = t.lower()
    if t == "reboot-no-ok":
        t = "reboot_no_ok"
    return t


def _parse_message_command(item: dict) -> Tuple[dict, str, str, list, str, dict]:
    if "message" in item:
        message = item.get("message") or {}
        msg_key = "message"
    elif "edited_message" in item:
        message = item.get("edited_message") or {}
        msg_key = "edited_message"
    else:
        message = {}
        msg_key = "unknown"
    text = str(message.get("text", "")).strip()
    if not text:
        return message, "", "", [], msg_key, {}
    entities = message.get("entities") or []
    cmd_token = ""
    args = []
    entity_summary = {"count": len(entities), "bot_cmd_offset0": False, "bot_cmd_len": None}
    if isinstance(entities, list):
        for ent in entities:
            if ent.get("type") != "bot_command":
                continue
            if ent.get("offset") != 0:
                continue
            length = ent.get("length")
            if not isinstance(length, int) or length <= 0 or length > len(text):
                continue
            cmd_piece = text[:length]
            if not cmd_piece.startswith("/"):
                continue
            cmd_token = cmd_piece
            rest = text[length:].strip()
            args = rest.split() if rest else []
            entity_summary["bot_cmd_offset0"] = True
            entity_summary["bot_cmd_len"] = length
            break
    if not cmd_token:
        parts = text.split()
        cmd_token = parts[0]
        args = parts[1:]
    cmd_name = _normalize_cmd_token(cmd_token)
    meta = {
        "cmd_original": cmd_name,
        "cmd_normalized": cmd_name,
        "args_normalized": args[:],
        "alias_used": None,
        "entities_summary": entity_summary,
    }
    if cmd_name not in ("reboot_no_ok", "reboot-confirm"):
        match = re.fullmatch(r"e(\d+)", cmd_name)
        if match:
            event_id = match.group(1)
            cmd_name = "event"
            args = [event_id]
            meta.update(
                {
                    "cmd_normalized": cmd_name,
                    "args_normalized": args[:],
                    "alias_used": "event",
                }
            )
        else:
            match = re.match(r"^rb(\d+)$", cmd_name)
        if match:
            alias_id = match.group(1)
            if cmd_name != "event":
                cmd_name = "reboot"
                args = [alias_id]
                meta.update(
                    {
                        "cmd_normalized": cmd_name,
                        "args_normalized": args[:],
                        "alias_used": "rb",
                    }
                )
        elif cmd_name == "rb" and args and args[0].isdigit():
            cmd_name = "reboot"
            args = [args[0]]
            meta.update(
                {
                    "cmd_normalized": cmd_name,
                    "args_normalized": args[:],
                    "alias_used": "rb",
                }
            )
        elif cmd_name != "event":
            match = re.match(r"^reboot(\d+)$", cmd_name)
            if match:
                alias_id = match.group(1)
                cmd_name = "reboot"
                args = [alias_id]
                meta.update(
                    {
                        "cmd_normalized": cmd_name,
                        "args_normalized": args[:],
                        "alias_used": "stuck",
                    }
                )
    return message, text, cmd_name, args, msg_key, meta


def _help_usage_for(cmd_name: str) -> Optional[str]:
    needle = (cmd_name or "").strip().lstrip("/").lower()
    for cmd in _COMMANDS:
        name = str(cmd.get("name", "")).lower()
        aliases = [a.lower() for a in cmd.get("aliases", [])]
        if needle == name or needle in aliases:
            return str(cmd.get("usage", "")).strip()
    return None


@dataclass
class MinerState:
    low_streak: int = 0
    offline_streak: int = 0
    ok_streak: int = 0
    state: str = STATE_OK
    initialized: bool = False
    last_elapsed: Optional[int] = None
    last_seen_ts: float = 0.0
    reboot_pending_until: float = 0.0
    reboot_pending_reason: str = ""
    reboot_pending_elapsed: Optional[int] = None
    last_reboot_ts: float = 0.0
    low_since_ts: Optional[float] = None
    hashboard_since_ts: Optional[float] = None
    last_auto_restart_ts: Optional[float] = None  # Spec 056: Soft mining restart timestamp
    auto_restart_count: int = 0                   # Spec 056: Soft mining restart attempts
    last_manual_reboot_ts: Optional[float] = None
    last_auto_reboot_ts: Optional[float] = None
    auto_reboot_timestamps: list = field(default_factory=list)
    degraded_mode: bool = False
    last_hourly_status_ts: Optional[float] = None
    snooze_until_ts: Optional[float] = None
    cooling_streak: int = 0
    last_cooling_warning_ts: Optional[float] = None
    efficiency_streak: int = 0
    last_efficiency_warning_ts: Optional[float] = None
    baseline_frequency_mhz: Optional[float] = None
    last_preset_warning_ts: Optional[float] = None
    # Spec 069: Deep Chain Telemetry & Predictive Chain Break Diagnostics (PROP-008)
    chain_warnings_ts: Dict[str, float] = field(default_factory=dict)
    # Spec 039: Fan Governor per-miner persistent state
    governor_duty: Optional[int] = None          # Last commanded duty %
    governor_holds: int = 0                       # Consecutive HOLD ticks
    governor_last_change_ts: float = 0.0          # Timestamp of last duty change
    governor_failures: int = 0                    # Consecutive HTTP failures
    governor_last_action: str = ""                # Last action string for /gov display
    governor_last_temp_c: Optional[float] = None  # Last temp seen by governor
    governor_last_power_w: Optional[float] = None # Last power (W) seen by governor
    # Spec 040: Dynamic Preset Balancer per-miner persistent state
    balancer_preset: Optional[str] = None          # Last known or applied preset (e.g. "2700W")
    balancer_last_change_ts: float = 0.0          # Timestamp of last preset adjustment
    balancer_last_action: str = ""                # Last decision action string
    balancer_last_reason: str = ""                # Last decision reason
    # Spec 062: HW Error Tripwire & Anti-Cascade Lock
    hw_error_lock_until_ts: Optional[float] = None
    hw_error_locked_preset: Optional[str] = None
    # Dynamic Vnish Overclock & Autoswitch State Discovery
    vnish_discovered_target_power_w: Optional[float] = None
    vnish_discovered_preset: Optional[str] = None
    vnish_discovered_top_preset: Optional[str] = None
    vnish_discovered_switcher_enabled: Optional[bool] = None
    vnish_discovered_ts: float = 0.0
    # Spec 044: Silent Mode / Visitor Mode — hardware FSM, SEPARATE from snooze_until_ts
    # C2: Never mix with snooze (alert suppressor). These control physical hardware.
    silent_mode_active: bool = False
    silent_mode_revert_ts: Optional[float] = None      # Unix ts when mode expires; None = indefinite
    silent_mode_prev_duty: Optional[int] = None        # Hardware duty before silent mode activation
    silent_mode_prev_preset: Optional[str] = None      # VNish preset name before activation
    silent_mode_target_max_duty: int = 50              # Acoustic ceiling (default 50%)
    # Spec 048: Safe Fleet Shutdown & Maintenance Mode
    is_shutdown_maintenance: bool = False
    shutdown_maintenance_ts: float = 0.0
    # Spec 046: Live Telemetry Snapshot for /status & mobile fleet cards
    last_rate_ths: Optional[float] = None
    last_active_boards: Optional[int] = None
    last_expected_boards: Optional[int] = None
    last_max_chip_temp: Optional[float] = None
    last_fan_duty_percent: Optional[float] = None
    last_power_w: Optional[float] = None
    last_efficiency_j_th: Optional[float] = None
    last_responded: bool = False
    # Spec 063: Ambient-Aware Thermal PID (GOV-02)
    inlet_temp_c: Optional[float] = None
    # Spec 057: Intervention Governance & Vnish Libre Mode
    intervention_gov: Optional[Any] = None
    # Spec 075: Soft-Landing Recovery & APW12 Latch-Off Defense
    stopped_since_ts: Optional[float] = None
    is_pre_clamped: bool = False
    original_preset_before_clamp: Optional[str] = None
    staged_ramp_up_pending: bool = False
    staged_ramp_up_soak_start_ts: Optional[float] = None
    stock_firmware_fallback_notified: bool = False



def load_config() -> Dict[str, Any]:
    config_env = os.getenv("MINER_ALERTS_CONFIG") or os.getenv("CONFIG_PATH")
    if config_env:
        config_path = Path(config_env).expanduser()
    else:
        config_path = Path(__file__).resolve().parent / "config.json"
    config_path = config_path.resolve()

    exists = config_path.exists()
    size_bytes = 0
    mtime_str = "N/A"
    sha_short = "N/A"
    qa_mode_raw = "N/A"
    qa_mode_type = "N/A"

    if not exists:
        log(
            f"CONFIG path={config_path} exists=false size=0 mtime=N/A sha=N/A "
            "qa_mode_raw=N/A type=N/A"
        )
        log("ERROR: No se encontro app/config.json. Copie app/config.example.json a app/config.json y complete los valores.")
        sys.exit(1)

    try:
        raw_bytes = config_path.read_bytes()
        size_bytes = len(raw_bytes)
        mtime = datetime.fromtimestamp(config_path.stat().st_mtime)
        mtime_str = mtime.isoformat(sep=" ", timespec="seconds")
        sha_short = hashlib.sha256(raw_bytes).hexdigest()[:8]
        try:
            config = json.loads(raw_bytes.decode("utf-8"))
        except json.JSONDecodeError as exc:
            log(
                f"CONFIG path={config_path} exists=true size={size_bytes} mtime={mtime_str} "
                f"sha={sha_short} qa_mode_raw=N/A type=N/A"
            )
            log(f"ERROR: Config invalido ({exc}). Corrija {config_path}.")
            sys.exit(1)
        qa_mode_raw = config.get("qa_mode")
        qa_mode_type = type(qa_mode_raw).__name__
        log(
            f"CONFIG path={config_path} exists=true size={size_bytes} mtime={mtime_str} "
            f"sha={sha_short} qa_mode_raw={qa_mode_raw} type={qa_mode_type}"
        )
        return config
    except Exception as exc:
        log(
            f"CONFIG path={config_path} exists=true size={size_bytes} mtime={mtime_str} "
            f"sha={sha_short} qa_mode_raw=N/A type=N/A"
        )
        log(f"ERROR: No se pudo leer {config_path} ({exc}).")
        sys.exit(1)


def resolve_db_path(config: Mapping[str, Any]) -> str:
    """Resolve the SQLite database path anchored to repo root if relative."""
    raw = str(config.get("event_store_path") or config.get("db_path") or "data/miner_alerts.db")
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = Path(_REPO_ROOT) / p
    return str(p)


# ---------------------------------------------------------------------------
# Spec 059: CGMiner Socket 4028 Client Facades (MT-02)
# ---------------------------------------------------------------------------
from app.network import (
    CGMinerClient,
    count_active_boards as _count_active_boards,
    extract_temps as _extract_temps,
    fw_hint as _fw_hint,
)
from app.network.cgminer_client import (
    read_pools as _net_read_pools,
    read_stats_active_boards as _net_read_stats_active_boards,
    read_stats_snapshot as _net_read_stats_snapshot,
    read_summary as _net_read_summary,
    read_version as _net_read_version,
)


def _read_command(host: str, port: int, payload: bytes, timeout: float = 5.0) -> Optional[dict]:
    from app.network import query_cgminer
    return query_cgminer(host=host, port=port, command=payload, timeout=timeout)


def read_summary(host: str, port: int, timeout: float = 5.0) -> Tuple[Optional[float], Optional[int], bool, Optional[dict]]:
    return _net_read_summary(host, port, timeout=timeout, query_fn=_read_command)


def read_stats_snapshot(
    host: str,
    port: int,
    timeout: float = 5.0,
) -> Tuple[Optional[int], bool, Optional[dict]]:
    return _net_read_stats_snapshot(host, port, timeout=timeout, query_fn=_read_command)


def read_stats_active_boards(host: str, port: int, timeout: float = 5.0) -> Tuple[Optional[int], bool]:
    active_boards, responded, _ = read_stats_snapshot(host, port, timeout=timeout)
    return active_boards, responded


def read_pools(host: str, port: int, timeout: float = 5.0) -> Optional[dict]:
    return _net_read_pools(host, port, timeout=timeout, query_fn=_read_command)


def read_version(host: str, port: int, timeout: float = 5.0) -> Optional[dict]:
    return _net_read_version(host, port, timeout=timeout, query_fn=_read_command)


def is_miner_no_ok(state: Optional["MinerState"]) -> bool:
    if not state or not getattr(state, "state", None):
        return True
    return state.state != STATE_OK


def classify_auto_reboot_signal(
    responded: bool,
    rate_ths: Optional[float],
    threshold_ths: float,
) -> str:
    if not responded or rate_ths is None:
        return AUTO_REBOOT_SIGNAL_INVALID
    try:
        numeric_rate = float(rate_ths)
    except (TypeError, ValueError):
        return AUTO_REBOOT_SIGNAL_INVALID
    if not math.isfinite(numeric_rate):
        return AUTO_REBOOT_SIGNAL_INVALID
    if numeric_rate >= float(threshold_ths):
        return AUTO_REBOOT_SIGNAL_NOT_LOW
    return AUTO_REBOOT_SIGNAL_ELIGIBLE


def auto_reboot_signal_allows_evaluation(
    new_state: str,
    low_since_ts: Optional[float],
    signal_classification: str,
    hashboard_since_ts: Optional[float] = None,
    active_boards: Optional[int] = None,
    expected_boards: int = 3,
    allow_partial_hashboard: bool = False,
    hashboard_reboot_enabled: bool = True,
) -> bool:
    if new_state == STATE_LOW:
        return (
            low_since_ts is not None
            and signal_classification == AUTO_REBOOT_SIGNAL_ELIGIBLE
        )
    if new_state == STATE_HASHBOARD and hashboard_reboot_enabled:
        if hashboard_since_ts is None:
            return False
        if signal_classification == AUTO_REBOOT_SIGNAL_INVALID:
            return False
        if active_boards is not None:
            if active_boards == 0:
                return True
            elif active_boards < expected_boards:
                return bool(allow_partial_hashboard)
            else:
                return False
        return signal_classification == AUTO_REBOOT_SIGNAL_ELIGIBLE
    return False


def reset_sustained_low_if_signal_ineligible(
    state: "MinerState",
    signal_classification: str,
) -> bool:
    if signal_classification == AUTO_REBOOT_SIGNAL_ELIGIBLE:
        return False
    state.low_since_ts = None
    return True


def reset_sustained_hashboard_if_ineligible(
    state: "MinerState",
    signal_classification: str,
    active_boards: Optional[int],
    expected_boards: int = 3,
    allow_partial_hashboard: bool = False,
) -> bool:
    if signal_classification == AUTO_REBOOT_SIGNAL_INVALID:
        state.hashboard_since_ts = None
        return True
    if active_boards is not None:
        if active_boards >= expected_boards:
            state.hashboard_since_ts = None
            return True
        if active_boards > 0 and not allow_partial_hashboard:
            state.hashboard_since_ts = None
            return True
    return False


def evaluate_auto_restart_candidate(
    *,
    now_ts: float,
    responded: bool,
    rate_ths: Optional[float],
    threshold_ths: float,
    active_boards: Optional[int],
    expected_boards: int,
    miner_state: str,
    restart_required: bool,
    reboot_required: bool,
    auto_restart_enabled: bool,
    last_auto_restart_ts: Optional[float],
    auto_restart_cooldown_seconds: float,
    auto_restart_count: int,
    max_retries_before_reboot: int,
    in_maintenance: bool = False,
    is_snoozed: bool = False,
    gov: Optional[Any] = None,
    elapsed: Optional[int] = None,
    min_elapsed_seconds: int = 180,
    startup_grace_active: bool = False,
) -> Tuple[bool, Optional[str], Optional[float]]:
    """
    Evaluates whether a miner qualifies for a Soft Auto-Restart of mining (Level 1).
    Returns: (is_candidate: bool, reason_or_blocker: Optional[str], cooldown_remaining: Optional[float])
    """
    if not auto_restart_enabled:
        return False, "disabled", None

    if startup_grace_active:
        return False, "startup_grace_active", None

    # Spec 057: Intervention Governance Guard
    from app.governance.intervention_policy import ACTION_REBOOT_L1, should_allow_intervention
    gov_check = gov if gov is not None else globals().get("_GLOBAL_INTERVENTION_GOV")
    if gov_check is not None:
        allowed, reason = should_allow_intervention(ACTION_REBOOT_L1, gov_check, now_ts)
        if not allowed:
            return False, f"interventions_blocked:{reason}", None

    if not responded:
        return False, "unresponsive", None
    if in_maintenance or is_snoozed:
        return False, "maintenance_or_snoozed", None
    if reboot_required:
        return False, "hardware_reboot_required", None

    # Individual Miner Warmup Guard: give miner at least min_elapsed_seconds (default 180s) post-boot
    if elapsed is not None and elapsed < min_elapsed_seconds:
        return False, "miner_warming_up", None

    norm_state = (miner_state or "").strip().lower()
    if norm_state in (
        "starting",
        "init",
        "initializing",
        "benchmarking",
        "rebooting",
        "booting",
        "tuning",
        "warmup",
        "warming_up",
    ):
        return False, "transient_starting", None

    # Check degradation triggers
    is_stopped = norm_state in ("stopped", "paused", "idle", "stop", "halted")
    is_zero_hash = (rate_ths is not None and rate_ths <= 0.0)
    is_zero_boards = (active_boards is not None and active_boards <= 0)
    has_restart_flag = bool(restart_required)

    if not (is_stopped or is_zero_hash or is_zero_boards or has_restart_flag):
        return False, "not_needed", None

    # Check retry limit before escalating to hardware reboot
    if auto_restart_count >= max_retries_before_reboot:
        return False, "max_retries_exceeded", None

    # Check cooldown
    if last_auto_restart_ts is not None:
        delta = max(0.0, now_ts - last_auto_restart_ts)
        if delta < auto_restart_cooldown_seconds:
            return False, "cooldown", auto_restart_cooldown_seconds - delta

    trigger_reason = "restart_required_flag" if has_restart_flag else (
        "stopped_state" if is_stopped else (
            "zero_boards" if is_zero_boards else "zero_hashrate"
        )
    )
    return True, trigger_reason, None


def _async_execute_mining_restart(
    host: str,
    password: str,
    miner_name: str,
    miner_dict: dict,
    trigger_reason: str,
    attempt: int,
    max_attempts: int,
    bot_token: str,
    chat_id: str,
    qa_mode: bool,
    qa_notify: bool,
    event_store: Optional[EventStore],
    pre_clamp_preset: str = "1800",
) -> None:
    try:
        ts = time.time()
        disp_name = display_name(miner_name)
        log(f"[AUTO-RESTART] {disp_name} ({host}) iniciando soft restart de minado (intento {attempt}/{max_attempts}, razon={trigger_reason})...")

        # Spec 075 / FR-01: Soft-Landing Pre-Clamp to safe floor (1800W) before restarting
        log(f"[SAFE-RECOVERY] {disp_name} ({host}) aplicando pre-clamp defensivo a {pre_clamp_preset}W para proteger fuente APW12...")
        clamp_ok, clamp_err = safe_set_miner_preset(host, password, pre_clamp_preset, clamp_top_preset=True)
        if clamp_ok:
            log(f"[SAFE-RECOVERY] {disp_name} ({host}) pre-clamp a {pre_clamp_preset}W aplicado con exito. Asentando voltajes (2.0s)...")
            time.sleep(2.0)
        else:
            log(f"[WARN] [SAFE-RECOVERY] {disp_name} ({host}) no se pudo aplicar pre-clamp ({clamp_err}); procediendo con soft restart de minado directo.")

        ok, err = safe_restart_mining(host, password)
        if ok:
            log(f"[AUTO-RESTART] {disp_name} ({host}) soft mining restart enviado exitosamente (intento {attempt}/{max_attempts}).")
            if (not qa_mode) or qa_notify:
                send_telegram(
                    bot_token,
                    str(chat_id),
                    f"[AUTO-RESTART] {disp_name} hasheo detenido ({trigger_reason}) -> reinicio rapido de minado enviado (Nivel 1, intento {attempt}/{max_attempts})\n"
                    f"Diagnostico: /why",
                    "REBOOT",
                    "auto_restart",
                )
            record_action_outcome(
                event_store,
                occurred_ts=ts,
                miner=miner_dict,
                action="restart_mining",
                source="auto",
                ok=True,
                message=f"Soft restart sent ({trigger_reason})",
            )
        else:
            log(f"[WARN] [AUTO-RESTART] {disp_name} ({host}) fallo soft restart de minado: {err}")
            if (not qa_mode) or qa_notify:
                send_telegram(
                    bot_token,
                    str(chat_id),
                    f"[AUTO-RESTART FAILED] {disp_name}: fallo al reiniciar minado: {err}\n"
                    f"Diagnostico: /why",
                    "ERROR",
                    "auto_restart_failed",
                )
            record_action_outcome(
                event_store,
                occurred_ts=ts,
                miner=miner_dict,
                action="restart_mining",
                source="auto",
                ok=False,
                message=str(err),
            )
    except Exception as _exc:
        log(f"[WARN] [AUTO-RESTART] {miner_name} excepcion no esperada en hilo AutoRestart: {type(_exc).__name__}: {_exc}")


def send_telegram(
    bot_token: str,
    chat_id: str,
    message: str,
    msg_type: str,
    reason: str = "",
    qa_update_id: Optional[int] = None,
    qa_cmd: Optional[str] = None,
    perf_ctx: Optional[dict] = None,
    is_command: bool = False,
    dbg_update_id: Optional[int] = None,
    dbg_cmd: Optional[str] = None,
    reply_markup: Optional[Dict[str, Any]] = None,
    dedup_key: Optional[str] = None,
    **kwargs: Any,
) -> None:
    if not msg_type:
        msg_type = "ERROR"
    parts = split_telegram_message(message)
    delivery_class = classify_delivery(msg_type, is_command=is_command)
    if _TELEGRAM_QUEUE is None:
        log(
            f"TG ENQUEUE_FAIL queue=None cmd={dbg_cmd or ''} update_id={dbg_update_id} "
            f"is_command={is_command} msg_type={msg_type}"
        )
        if is_command:
            _send_telegram_direct(
                bot_token,
                chat_id,
                parts,
                dbg_update_id=dbg_update_id,
                dbg_cmd=dbg_cmd,
                reply_markup=reply_markup,
            )
        return
    direct_send = False
    with _TELEGRAM_QUEUE_LOCK:
        now_ts = time.time()
        if DBG_TELEGRAM and (not DBG_TELEGRAM_COMMANDS_ONLY or is_command):
            log(
                f"TGQ update_id={dbg_update_id} cmd={dbg_cmd or ''} qsize_before={_TELEGRAM_QUEUE.qsize()} "
                f"type={msg_type} text_len={len(message or '')} parts={len(parts)}"
            )
        maxsize = _TELEGRAM_QUEUE.maxsize
        capacity_needed = len(parts)
        has_capacity = maxsize <= 0 or (_TELEGRAM_QUEUE.qsize() + capacity_needed) <= maxsize
        if not has_capacity and is_command:
            direct_send = True
            log(
                f"TG QUEUE_BYPASS class=command reason=full type={msg_type} "
                f"update_id={dbg_update_id} parts={len(parts)}"
            )
        elif not has_capacity:
            log(
                f"TG QUEUE_DROP class={delivery_class} reason=full type={msg_type} "
                f"update_id={dbg_update_id} parts={len(parts)}"
            )
            return

        if direct_send:
            pass
        else:
            _LAST_ENQUEUED[msg_type] = now_ts
            batch_id = f"{time.time_ns()}-{threading.get_ident()}"
            for part_index, part in enumerate(parts, start=1):
                _TELEGRAM_QUEUE.put_nowait(
                    (
                        now_ts,
                        chat_id,
                        part,
                        msg_type,
                        reason,
                        qa_update_id,
                        qa_cmd,
                        perf_ctx,
                        is_command,
                        dbg_update_id,
                        dbg_cmd,
                        batch_id,
                        part_index,
                        len(parts),
                        reply_markup if part_index == len(parts) else None,
                    )
                )
            if DBG_TELEGRAM and (not DBG_TELEGRAM_COMMANDS_ONLY or is_command):
                log(
                    f"TGQ update_id={dbg_update_id} cmd={dbg_cmd or ''} "
                    f"ENQUEUED qsize_after={_TELEGRAM_QUEUE.qsize()} "
                    f"type={msg_type} parts={len(parts)}"
                )
        _LAST_SENT_META["type"] = msg_type
        _LAST_SENT_META["ts"] = now_str()
        if _QA_MODE:
            log_pid(f"[QA] enqueue type={msg_type} reason={reason} qsize={_TELEGRAM_QUEUE.qsize()}")
    if direct_send:
        _send_telegram_direct(
            bot_token,
            chat_id,
            parts,
            dbg_update_id=dbg_update_id,
            dbg_cmd=dbg_cmd,
            reply_markup=reply_markup,
        )


def _send_telegram_direct(
    bot_token: str,
    chat_id: str,
    parts: list[str],
    *,
    dbg_update_id: Optional[int],
    dbg_cmd: Optional[str],
    reply_markup: Optional[Dict[str, Any]] = None,
) -> bool:
    tg_send_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    if not tg_send_url.startswith("https://api.telegram.org/bot"):
        log("[ERROR] URL Telegram invalida (sendMessage).")
        return False
    session = _HTTP_SESSION or requests.Session()
    for part_index, part in enumerate(parts, start=1):
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "text": part,
            "disable_web_page_preview": True,
        }
        if reply_markup is not None and part_index == len(parts):
            payload["reply_markup"] = reply_markup
        t0 = time.perf_counter()
        try:
            resp = session.post(tg_send_url, json=payload, timeout=(1.5, 4.0))
            ms = int((time.perf_counter() - t0) * 1000)
            if resp.status_code == 200:
                log(
                    f"TG FALLBACK_SEND ok http=200 ms_send={ms} cmd={dbg_cmd or ''} "
                    f"update_id={dbg_update_id} part={part_index}/{len(parts)}"
                )
                continue
            body = _redact_telegram_token(
                resp.text or "", bot_token
            )[:200].replace("\n", "\\n")
            log(
                f"TG FALLBACK_SEND err http={resp.status_code} ms_send={ms} "
                f"cmd={dbg_cmd or ''} update_id={dbg_update_id} "
                f"part={part_index}/{len(parts)} body=\"{body}\""
            )
            return False
        except Exception as exc:
            ms = int((time.perf_counter() - t0) * 1000)
            log(
                f"TG FALLBACK_SEND exc ms_send={ms} cmd={dbg_cmd or ''} "
                f"update_id={dbg_update_id} part={part_index}/{len(parts)} "
                f"err={type(exc).__name__}:{_redact_telegram_token(exc, bot_token)}"
            )
            return False
    return True


# ---------------------------------------------------------------------------
# T009: Telegram Bot API callback helpers (Spec 031)
# ---------------------------------------------------------------------------

def answer_callback_query(
    bot_token: str,
    callback_query_id: str,
    text: Optional[str] = None,
    show_alert: bool = False,
) -> None:
    """Acknowledge a Telegram callback_query within the mandatory 1.0s window.

    Must be called from within the polling thread for every callback_query
    received, regardless of authorization outcome.
    """
    url = f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery"
    payload: Dict[str, Any] = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    if show_alert:
        payload["show_alert"] = True
    t0 = time.perf_counter()
    try:
        session = _HTTP_SESSION or requests.Session()
        resp = session.post(url, json=payload, timeout=5.0)
        ms = int((time.perf_counter() - t0) * 1000)
        if resp.status_code != 200:
            body = _redact_telegram_token(resp.text or "", bot_token)[:200]
            log(
                f"TG ANSWER_CB err http={resp.status_code} ms={ms} "
                f"cb_id={callback_query_id} body=\"{body}\""
            )
        elif DBG_TELEGRAM:
            log(f"TG ANSWER_CB ok ms={ms} cb_id={callback_query_id}")
    except Exception as exc:
        ms = int((time.perf_counter() - t0) * 1000)
        log(
            f"TG ANSWER_CB exc ms={ms} cb_id={callback_query_id} "
            f"err={type(exc).__name__}:{_redact_telegram_token(exc, bot_token)}"
        )


def edit_message_reply_markup(
    bot_token: str,
    chat_id: str,
    message_id: int,
    reply_markup: Dict[str, Any],
) -> None:
    """Replace the inline keyboard of an existing message in-place.

    Used to transition from alert keyboard -> confirmation keyboard -> settled.
    """
    url = f"https://api.telegram.org/bot{bot_token}/editMessageReplyMarkup"
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "message_id": message_id,
        "reply_markup": reply_markup,
    }
    t0 = time.perf_counter()
    try:
        session = _HTTP_SESSION or requests.Session()
        resp = session.post(url, json=payload, timeout=5.0)
        ms = int((time.perf_counter() - t0) * 1000)
        if resp.status_code != 200:
            body = _redact_telegram_token(resp.text or "", bot_token)[:200]
            log(
                f"TG EDIT_MARKUP err http={resp.status_code} ms={ms} "
                f"chat_id={chat_id} msg_id={message_id} body=\"{body}\""
            )
        elif DBG_TELEGRAM:
            log(f"TG EDIT_MARKUP ok ms={ms} chat_id={chat_id} msg_id={message_id}")
    except Exception as exc:
        ms = int((time.perf_counter() - t0) * 1000)
        log(
            f"TG EDIT_MARKUP exc ms={ms} chat_id={chat_id} msg_id={message_id} "
            f"err={type(exc).__name__}:{_redact_telegram_token(exc, bot_token)}"
        )


def edit_message_text(
    bot_token: str,
    chat_id: str,
    message_id: int,
    text: str,
    reply_markup: Optional[Dict[str, Any]] = None,
    parse_mode: Optional[str] = "Markdown",
) -> bool:
    """Edit both the text and inline keyboard of an existing message in-place.

    Used by the interactive Command Center for seamless in-place menu navigation.
    Gracefully ignores 'message is not modified' responses from Telegram.
    """
    url = f"https://api.telegram.org/bot{bot_token}/editMessageText"
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    if parse_mode is not None:
        payload["parse_mode"] = parse_mode

    t0 = time.perf_counter()
    try:
        session = _HTTP_SESSION or requests.Session()
        resp = session.post(url, json=payload, timeout=5.0)
        ms = int((time.perf_counter() - t0) * 1000)
        if resp.status_code == 200:
            if DBG_TELEGRAM:
                log(f"TG EDIT_TEXT ok ms={ms} chat_id={chat_id} msg_id={message_id}")
            return True
        body = (resp.text or "").lower()
        if "message is not modified" in body:
            return True
        redacted_body = _redact_telegram_token(resp.text or "", bot_token)[:200]
        log(
            f"TG EDIT_TEXT err http={resp.status_code} ms={ms} "
            f"chat_id={chat_id} msg_id={message_id} body=\"{redacted_body}\""
        )
        return False
    except Exception as exc:
        ms = int((time.perf_counter() - t0) * 1000)
        log(
            f"TG EDIT_TEXT exc ms={ms} chat_id={chat_id} msg_id={message_id} "
            f"err={type(exc).__name__}:{_redact_telegram_token(exc, bot_token)}"
        )
        return False


def send_telegram_photo(
    bot_token: str,
    chat_id: str,
    photo_bytes: bytes,
    caption: Optional[str] = None,
    reply_markup: Optional[Dict[str, Any]] = None,
    timeout: float = 15.0,
) -> bool:
    """Send a binary PNG image directly to Telegram via sendPhoto."""
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    data: Dict[str, Any] = {"chat_id": str(chat_id)}
    if caption:
        data["caption"] = caption
    if reply_markup is not None:
        data["reply_markup"] = json.dumps(reply_markup)
    files = {"photo": ("chart.png", photo_bytes, "image/png")}
    t0 = time.perf_counter()
    try:
        session = _HTTP_SESSION or requests.Session()
        resp = session.post(url, data=data, files=files, timeout=timeout)
        ms = int((time.perf_counter() - t0) * 1000)
        if resp.status_code != 200:
            body = _redact_telegram_token(resp.text or "", bot_token)[:200]
            log(f"TG SEND_PHOTO err http={resp.status_code} ms={ms} body=\"{body}\"")
            return False
        if DBG_TELEGRAM:
            log(f"TG SEND_PHOTO ok ms={ms}")
        return True
    except Exception as exc:
        ms = int((time.perf_counter() - t0) * 1000)
        log(f"TG SEND_PHOTO exc ms={ms} err={type(exc).__name__}:{_redact_telegram_token(exc, bot_token)}")
        return False


def edit_telegram_photo(
    bot_token: str,
    chat_id: str,
    message_id: int,
    photo_bytes: bytes,
    caption: Optional[str] = None,
    reply_markup: Optional[Dict[str, Any]] = None,
    timeout: float = 15.0,
) -> bool:
    """Edit an existing photo message in-place using editMessageMedia."""
    url = f"https://api.telegram.org/bot{bot_token}/editMessageMedia"
    media_obj: Dict[str, Any] = {
        "type": "photo",
        "media": "attach://file_0",
    }
    if caption:
        media_obj["caption"] = caption
    data: Dict[str, Any] = {
        "chat_id": str(chat_id),
        "message_id": int(message_id),
        "media": json.dumps(media_obj),
    }
    if reply_markup is not None:
        data["reply_markup"] = json.dumps(reply_markup)
    files = {"file_0": ("chart.png", photo_bytes, "image/png")}
    t0 = time.perf_counter()
    try:
        session = _HTTP_SESSION or requests.Session()
        resp = session.post(url, data=data, files=files, timeout=timeout)
        ms = int((time.perf_counter() - t0) * 1000)
        if resp.status_code != 200:
            body = _redact_telegram_token(resp.text or "", bot_token)[:200]
            if "message is not modified" in body.lower():
                if DBG_TELEGRAM:
                    log(f"TG EDIT_PHOTO not modified ms={ms}")
                return True
            log(f"TG EDIT_PHOTO err http={resp.status_code} ms={ms} body=\"{body}\"")
            return False
        if DBG_TELEGRAM:
            log(f"TG EDIT_PHOTO ok ms={ms}")
        return True
    except Exception as exc:
        ms = int((time.perf_counter() - t0) * 1000)
        log(f"TG EDIT_PHOTO exc ms={ms} err={type(exc).__name__}:{_redact_telegram_token(exc, bot_token)}")
        return False


def telegram_sender_worker(bot_token: str, q: queue.Queue, qa_mode: bool) -> None:
    global _HTTP_SESSION, _TELEGRAM_SENDER_TS
    if _HTTP_SESSION is None:
        _HTTP_SESSION = requests.Session()
    session = _HTTP_SESSION
    tg_send_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    if not tg_send_url.startswith("https://api.telegram.org/bot"):
        log("[ERROR] URL Telegram invalida (sendMessage).")
        return
    last_hb = 0.0
    while True:
        is_command = False
        dbg_update_id = None
        dbg_cmd = None
        try:
            _TELEGRAM_SENDER_TS = time.time()
            try:
                item = q.get(timeout=5.0)
            except queue.Empty:
                _TELEGRAM_SENDER_TS = time.time()
                continue
            (
                enqueue_ts,
                chat_id,
                message,
                msg_type,
                _reason,
                qa_update_id,
                qa_cmd,
                perf_ctx,
                is_command,
                dbg_update_id,
                dbg_cmd,
                batch_id,
                part_index,
                part_count,
                reply_markup,
            ) = item
            if DBG_TELEGRAM and (time.time() - last_hb) >= 30:
                log(f"SENDER_HB alive=1 qsize={q.qsize()}")
                last_hb = time.time()
            with _TELEGRAM_QUEUE_LOCK:
                last_ts = _LAST_ENQUEUED.get(msg_type, 0.0)
            window = _COALESCE_WINDOWS.get(msg_type)
            if part_count == 1 and not is_command and window and enqueue_ts < last_ts and (last_ts - enqueue_ts) <= window:
                if DBG_TELEGRAM and (not DBG_TELEGRAM_COMMANDS_ONLY or is_command):
                    log(
                        f"SEND_SKIP update_id={dbg_update_id} reason=coalesce type={msg_type} "
                        f"window_s={window}"
                    )
                continue
            msg_hash = hashlib.sha256(message.encode("utf-8", errors="ignore")).hexdigest()
            last_hash = _LAST_SENT_HASH.get(msg_type)
            last_sent = _LAST_SENT_TS.get(msg_type, 0.0)
            if part_count == 1 and not is_command and msg_type == "STATE_CHANGE" and last_hash == msg_hash:
                if DBG_TELEGRAM and (not DBG_TELEGRAM_COMMANDS_ONLY or is_command):
                    log(
                        f"SEND_SKIP update_id={dbg_update_id} reason=dedupe type={msg_type} hash={msg_hash[:8]}"
                    )
                continue
            if part_count == 1 and not is_command and last_hash == msg_hash and (time.time() - last_sent) < 60:
                if DBG_TELEGRAM and (not DBG_TELEGRAM_COMMANDS_ONLY or is_command):
                    log(
                        f"SEND_SKIP update_id={dbg_update_id} reason=dedupe type={msg_type} hash={msg_hash[:8]} "
                        f"age_s={int(time.time() - last_sent)}"
                    )
                continue
            payload = {
                "chat_id": chat_id,
                "text": message,
                "disable_web_page_preview": True,
            }
            if reply_markup is not None:
                payload["reply_markup"] = reply_markup
            start = time.monotonic()
            resp = session.post(tg_send_url, json=payload, timeout=(2.0, 6.0))
            _TELEGRAM_SENDER_TS = time.time()
            duration = time.monotonic() - start
            if qa_mode:
                log_pid(
                    f"[TEL] sendMessage duration={duration:.3f}s status={resp.status_code} "
                    f"qsize={q.qsize()} msg_type={msg_type}"
                )
                if qa_update_id is not None:
                    count = _QA_TX_COUNTS.get(qa_update_id, 0) + 1
                    _QA_TX_COUNTS[qa_update_id] = count
                    log_pid(
                        f"TX id={qa_update_id} n={count} cmd={qa_cmd or 'N/A'} status={resp.status_code}"
                    )
            if perf_ctx:
                perf_id = perf_ctx.get("update_id")
                if perf_id is None or not _PERF_LOGGED.get(perf_id):
                    ms_send = int(duration * 1000)
                    start_ts = perf_ctx.get("start_ts", time.time())
                    ms_total = int((time.time() - start_ts) * 1000)
                    log(
                        f"PERF cmd={perf_ctx.get('cmd','')} handler={perf_ctx.get('handler','')} "
                        f"ms_total={ms_total} ms_send={ms_send}"
                    )
                    if ms_send > 2000:
                        log(f"SAFETY slow_send cmd={perf_ctx.get('cmd','')} ms_send={ms_send}")
                    if resp.status_code != 200:
                        body = _redact_telegram_token(
                            resp.text or "", bot_token
                        )[:200].replace("\n", " ")
                        log(f"ERROR telegram_send status={resp.status_code} body=\"{body}\"")
                    if perf_id is not None:
                        _PERF_LOGGED[perf_id] = True
            if resp.status_code != 200:
                body = _redact_telegram_token(
                    resp.text or "", bot_token
                )[:200].replace("\n", " ")
                log(
                    f"TG SEND_ERR http={resp.status_code} cmd={dbg_cmd or ''} "
                    f"update_id={dbg_update_id} body=\"{body}\""
                )
            if DBG_TELEGRAM and (not DBG_TELEGRAM_COMMANDS_ONLY or is_command):
                log(
                    f"SEND_POST update_id={dbg_update_id} cmd={dbg_cmd or ''} "
                    f"http={resp.status_code} ms={int(duration*1000)} type={msg_type}"
                )
                if resp.status_code != 200:
                    body = _redact_telegram_token(
                        resp.text or "", bot_token
                    )[:200].replace("\n", " ")
                    log(f"SEND_ERR update_id={dbg_update_id} cmd={dbg_cmd or ''} http={resp.status_code} body=\"{body}\"")
            if resp.status_code >= 400:
                log(
                    f"[WARN] Telegram retorno {resp.status_code}: "
                    f"{_redact_telegram_token(resp.text, bot_token)}"
                )
            _LAST_SENT_HASH[msg_type] = msg_hash
            _LAST_SENT_TS[msg_type] = time.time()
        except Exception as exc:
            _TELEGRAM_SENDER_TS = time.time()
            if DBG_TELEGRAM and (not DBG_TELEGRAM_COMMANDS_ONLY or is_command):
                log(
                    f"SEND_EXC update_id={dbg_update_id} err={type(exc).__name__}:"
                    f"{_redact_telegram_token(exc, bot_token)}"
                )
            log(
                "[WARN] No se pudo enviar mensaje a Telegram "
                f"({_redact_telegram_token(exc, bot_token)})"
            )
            time.sleep(2)


def format_rate(rate: Optional[float]) -> str:
    return f"{rate:.2f} TH/s" if rate is not None else "N/A"


def format_fleet_restored_line(
    name_display: str,
    rate_ths: Optional[float],
    temp_c: Optional[float] = None,
) -> str:
    """Format a single miner status line for the 🟢 FLOTA RESTABLECIDA card."""
    rate_str = f"{float(rate_ths):.1f} TH/s" if rate_ths is not None else "N/A"
    temp_str = f" {float(temp_c):.0f}°C" if temp_c is not None else ""
    return f"- {name_display}: {rate_str} [OK]{temp_str}"


def is_fleet_warmup_complete(
    miners: list,
    states: dict,
    threshold_ths: float,
    expected_boards: int = 3,
) -> bool:
    """Check if all valid miners have responded and reached the warm-up hashrate threshold."""
    if not miners:
        return False
    for m in miners:
        m_name = m.get("name", "")
        m_host = m.get("host", "")
        m_sk = f"{m_name}|{m_host}:{m.get('port', 4028)}"
        m_st = states.get(m_sk)
        if m_st is None:
            return False
        if not getattr(m_st, "last_responded", False):
            return False
        rate = getattr(m_st, "last_rate_ths", None)
        if rate is None or float(rate) < float(threshold_ths):
            return False
        boards = getattr(m_st, "last_active_boards", None)
        if boards is not None and int(boards) < int(expected_boards):
            return False
    return True


def record_action_outcome(
    event_store: Optional[EventStore],
    *,
    occurred_ts: float,
    miner: dict,
    action: str,
    source: str,
    ok: bool,
    message: str,
) -> None:
    if event_store is None or not event_store.available:
        return
    miner_name = display_name(str(miner.get("name", "")))
    event_store.record_event(
        occurred_ts=occurred_ts,
        miner_key=f"{miner.get('name')}|{miner.get('host')}:{miner.get('port')}",
        miner_name=miner_name,
        host=str(miner.get("host", "")),
        event_type=f"{source}_{action}_{'success' if ok else 'failed'}",
        severity="info" if ok else "warning",
        classification=f"{source}_{action}",
        action_source=source,
        action_ts=occurred_ts,
        summary=(
            f"{source} {action} enviado"
            if ok
            else f"{source} {action} fallo: {_short_text(message, 120)}"
        ),
        details={"ok": ok},
    )


def record_auto_reboot_decision(
    event_store: Optional[EventStore],
    *,
    evaluated_ts: float,
    miner: dict,
    state: "MinerState",
    result: str,
    responded: bool,
    rate_ths: Optional[float],
    threshold_ths: float,
    active_boards: Optional[int],
    expected_boards: int,
    telemetry: VnishTelemetry,
    startup_guard_active: bool,
    qa_mode: bool,
    cooldown_remaining_seconds: Optional[float],
    window_seconds: int,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    if event_store is None or not event_store.available:
        return
    low_elapsed = None
    if state.low_since_ts is not None:
        low_elapsed = max(0.0, evaluated_ts - state.low_since_ts)
    elif state.hashboard_since_ts is not None:
        low_elapsed = max(0.0, evaluated_ts - state.hashboard_since_ts)
    event_store.record_reboot_decision(
        evaluated_ts=evaluated_ts,
        miner_key=f"{miner.get('name')}|{miner.get('host')}:{miner.get('port')}",
        miner_name=display_name(str(miner.get("name", ""))),
        host=str(miner.get("host", "")),
        result=result,
        state=state.state,
        responded=responded,
        rate_ths=rate_ths,
        threshold_ths=threshold_ths,
        low_elapsed_seconds=low_elapsed,
        active_boards=active_boards,
        expected_boards=expected_boards,
        startup_guard_active=startup_guard_active,
        qa_mode=qa_mode,
        cooldown_remaining_seconds=cooldown_remaining_seconds,
        window_count=len(state.auto_reboot_timestamps),
        window_seconds=window_seconds,
        telemetry=telemetry.as_dict(),
        details=details,
    )


def display_name(raw_name: str) -> str:
    if "-" in raw_name:
        return raw_name.split("-")[-1]
    return raw_name


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def argentina_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None).replace(microsecond=0) + timedelta(hours=-3)


def resolve_miner(input_name: str, miners: list) -> Optional[dict]:
    needle = input_name.strip().lower()
    for miner in miners:
        raw = str(miner.get("name", "")).lower()
        disp = display_name(miner.get("name", "")).lower()
        if needle == raw or needle == disp:
            return miner
    for miner in miners:
        host = str(miner.get("host") or miner.get("ip") or "").strip().lower()
        if host and (needle == host or needle == host.split(":")[-1]):
            return miner
    return None


def build_stability_health_text(
    event_store: Optional[EventStore],
    miners: list[dict[str, Any]],
    miner_token: Optional[str],
    *,
    now_ts: float,
    window_hours: float = 168.0,
    min_samples: int = 12,
    stale_after_seconds: float = 900.0,
) -> str:
    """Render bounded historical health without contacting miners or running actions."""
    if event_store is None or not event_store.available:
        return "Diagnostico historico temporalmente no disponible."
    selected_miners = miners
    token = str(miner_token or "").strip()
    if token and token.lower() != "all":
        selected = resolve_miner(token, miners)
        if not selected:
            return "Miner no encontrado."
        selected_miners = [selected]
    omitted_miners = max(0, len(selected_miners) - 10)
    selected_miners = selected_miners[:10]

    safe_hours = max(1.0, min(float(window_hours), 720.0))
    safe_min_samples = max(3, min(int(min_samples), 288))
    safe_stale = max(30.0, float(stale_after_seconds))
    since_ts = float(now_ts) - safe_hours * 3600.0
    sample_limit = min(2_500, max(288, safe_min_samples * 20))
    blocks = ["HEALTH (historial local)"]
    for miner in selected_miners:
        state_key = f"{miner['name']}|{miner['host']}:{miner['port']}"
        samples = event_store.list_samples(
            miner_key=state_key,
            since_ts=since_ts,
            limit=sample_limit,
        )
        if event_store.last_error:
            return "Diagnostico historico temporalmente no disponible."
        assessment = analyze_stability(
            samples,
            now_ts=now_ts,
            stale_after_seconds=safe_stale,
            min_samples=safe_min_samples,
        )
        blocks.append(
            render_stability_assessment(
                display_name(str(miner["name"])),
                assessment,
            )
        )
    if omitted_miners:
        blocks.append(f"... {omitted_miners} mineros omitidos por limite de salida.")
    return "\n\n".join(blocks)


def build_mining_quality_text(
    event_store: Optional[EventStore],
    miners: list[dict[str, Any]],
    miner_token: Optional[str],
    *,
    now_ts: Optional[float] = None,
    window_hours: float = 24.0,
    min_intervals: int = 3,
    reject_warning_percent: float = 1.0,
    stale_warning_percent: float = 1.0,
    hw_error_delta_warning: int = 50,
    no_share_warning_seconds: float = 900.0,
) -> str:
    """Render bounded mining quality from SQLite without miner IO or actions."""
    if event_store is None or not event_store.available:
        return "Diagnostico de calidad temporalmente no disponible."
    selected_miners = miners
    token = str(miner_token or "").strip()
    if token and token.lower() != "all":
        selected = resolve_miner(token, miners)
        if not selected:
            return "Miner no encontrado."
        selected_miners = [selected]
    omitted_miners = max(0, len(selected_miners) - 10)
    selected_miners = selected_miners[:10]

    safe_now = time.time() if now_ts is None else float(now_ts)
    safe_hours = max(1.0, min(float(window_hours), 720.0))
    safe_min_intervals = max(1, min(int(min_intervals), 48))
    since_ts = safe_now - safe_hours * 3600.0
    blocks = ["QUALITY (historial local)"]
    for miner in selected_miners:
        state_key = f"{miner['name']}|{miner['host']}:{miner['port']}"
        samples = event_store.list_samples(
            miner_key=state_key,
            since_ts=since_ts,
            limit=100,
        )
        if event_store.last_error:
            return "Diagnostico de calidad temporalmente no disponible."
        assessment = analyze_mining_quality(
            samples,
            min_intervals=safe_min_intervals,
            reject_warning_percent=reject_warning_percent,
            stale_warning_percent=stale_warning_percent,
            hw_error_delta_warning=hw_error_delta_warning,
            no_share_warning_seconds=no_share_warning_seconds,
        )
        blocks.append(
            render_mining_quality(
                display_name(str(miner["name"])),
                assessment,
            )
        )
    if omitted_miners:
        blocks.append(f"... {omitted_miners} mineros omitidos por limite de salida.")
    return "\n\n".join(blocks)


def build_firmware_events_text(
    event_store: Optional[EventStore],
    miners: list[dict[str, Any]],
    miner_token: Optional[str],
) -> str:
    """Render bounded Vnish evidence from SQLite without miner IO or actions."""
    if event_store is None or not event_store.available:
        return "Diagnostico de firmware temporalmente no disponible."

    token = str(miner_token or "").strip()
    miner_key: Optional[str] = None
    title = "FIRMWARE EVENTS"
    severities: Optional[tuple[str, ...]] = ("warning", "critical")
    limit = 6
    if token and token.lower() != "all":
        miner = resolve_miner(token, miners)
        if not miner:
            return "Miner no encontrado."
        miner_key = f"{miner['name']}|{miner['host']}:{miner['port']}"
        title = f"FIRMWARE EVENTS - {display_name(str(miner['name']))}"
        severities = None
    elif token.lower() == "all":
        severities = None
        limit = 10

    rows = event_store.list_firmware_events(
        limit=limit,
        miner_key=miner_key,
        severities=severities,
    )
    if event_store.last_error:
        return "Diagnostico de firmware temporalmente no disponible."
    return render_firmware_events(rows, title=title, limit=limit)


def build_miner_diagnosis_text(
    event_store: Optional[EventStore],
    miners: list[dict[str, Any]],
    miner_token: Optional[str],
    *,
    now_ts: Optional[float] = None,
    stale_after_seconds: float = 900.0,
    firmware_window_hours: float = 24.0,
    collector_stale_seconds: float = 3_600.0,
) -> str:
    """Correlate bounded persisted evidence without live miner IO or actions."""
    if event_store is None or not event_store.available:
        return "Diagnostico operativo temporalmente no disponible."
    selected_miners = miners
    token = str(miner_token or "").strip()
    if token and token.lower() != "all":
        selected = resolve_miner(token, miners)
        if not selected:
            return "Miner no encontrado."
        selected_miners = [selected]
    omitted = max(0, len(selected_miners) - 10)
    selected_miners = selected_miners[:10]

    effective_now = time.time() if now_ts is None else float(now_ts)
    safe_stale = max(30.0, min(float(stale_after_seconds), 86_400.0))
    safe_firmware_window = max(1.0, min(float(firmware_window_hours), 720.0))
    safe_collector_stale = max(60.0, min(float(collector_stale_seconds), 86_400.0))
    firmware_since = effective_now - safe_firmware_window * 3_600.0
    collector_run = event_store.latest_collector_run()
    collector_text = "SIN EJECUCIONES"
    if collector_run:
        collector_age = max(
            0.0,
            effective_now - float(collector_run.get("completed_ts") or 0.0),
        )
        collector_status = str(collector_run.get("status") or "unknown").upper()
        if collector_age > safe_collector_stale:
            collector_status = f"STALE/{collector_status}"
        collector_text = f"{collector_status} age={int(collector_age)}s"

    blocks: list[str] = []
    for miner in selected_miners:
        miner_key = f"{miner['name']}|{miner['host']}:{miner['port']}"
        samples = event_store.list_samples(miner_key=miner_key, limit=24)
        events = event_store.list_events(miner_key=miner_key, limit=1)
        decision = event_store.latest_reboot_decision(miner_key=miner_key)
        firmware = event_store.list_firmware_events(
            miner_key=miner_key,
            source_since_ts=firmware_since,
            severities=("warning", "critical"),
            limit=3,
        )
        if event_store.last_error:
            return "Diagnostico operativo temporalmente no disponible."

        name = display_name(str(miner["name"]))
        status = "NO_DATA"
        signal = "sin muestras persistidas"
        quality_label = "N/A"
        conclusion = "Esperar una muestra valida antes de diagnosticar."
        if samples:
            latest = samples[0]
            observed_ts = float(latest.get("observed_ts") or 0.0)
            age = max(0.0, effective_now - observed_ts)
            state = str(latest.get("state") or "UNKNOWN").upper()
            responded = bool(latest.get("responded"))
            rate = latest.get("rate_ths")
            threshold = latest.get("threshold_ths")
            signal = (
                f"{state} rate={format_rate(rate)} threshold={format_rate(threshold)} "
                f"age={int(age)}s"
            )
            quality = analyze_mining_quality(samples, min_intervals=3)
            quality_label = quality.status.upper()
            if age > safe_stale:
                status = "STALE"
                conclusion = "Telemetria vencida; no inferir necesidad de reboot."
            elif not responded or state in (STATE_OFFLINE, STATE_HASHBOARD):
                status = "CRITICAL"
                conclusion = "Falla actual verificable; revisar evidencia antes de actuar."
            elif state == STATE_LOW:
                status = "WATCH"
                conclusion = "Hashrate bajo actual; respetar sustained LOW y guardrails."
            elif firmware or quality.status in ("watch", "critical"):
                status = "WATCH"
                conclusion = "Senal actual estable con evidencia reciente para revisar."
            else:
                status = "OK"
                conclusion = "Sin evidencia operativa reciente que justifique intervenir."

        firmware_text = "sin warning/critical en ventana"
        if firmware:
            latest_firmware = firmware[0]
            firmware_text = (
                f"{len(firmware)} fresh; {latest_firmware.get('severity')} "
                f"{latest_firmware.get('code')} @ {latest_firmware.get('source_ts_text')}"
            )
        event_text = "sin evento"
        if events:
            latest_event = events[0]
            event_text = (
                f"{latest_event.get('event_type')} - "
                f"{_short_text(str(latest_event.get('summary') or ''), 80)}"
            )
        decision_text = str(decision.get("result")) if decision else "sin decision"
        blocks.append(
            "\n".join(
                [
                    f"DIAGNOSE {name} - {status}",
                    f"Signal: {signal}",
                    f"Quality: {quality_label}",
                    f"Firmware {safe_firmware_window:g}h: {firmware_text}",
                    f"Evento: {event_text}",
                    f"Auto-reboot: {decision_text}",
                    f"Collector: {collector_text}",
                    f"Conclusion: {conclusion}",
                ]
            )
        )
    if omitted:
        blocks.append(f"... {omitted} mineros omitidos por limite de salida.")
    return "\n\n".join(blocks)


# ---------------------------------------------------------------------------
# Spec 059: Hashcore Hardware Client Facades (MT-02)
# ---------------------------------------------------------------------------
from app.network import (
    HashcoreClient,
    get_hashcore_cli_path as _hashcore_cli_path,
)
from app.network.hashcore_client import (
    run_hashcore_cli as _net_run_hashcore_cli,
    run_hashcore_discovery as _net_run_hashcore_discovery,
)


def _execute_subprocess_no_window(cmd: Any, **kwargs: Any) -> subprocess.CompletedProcess:
    """Windows subprocess execution ensuring no console window is spawned."""
    kwargs.pop("creationflags", None)
    return subprocess.run(cmd, creationflags=_NO_WINDOW_CREATION_FLAGS, **kwargs)


def run_hashcore_discovery(hashcore_cfg: dict) -> None:
    _net_run_hashcore_discovery(
        hashcore_cfg=hashcore_cfg,
        runner=_execute_subprocess_no_window,
        log_fn=log,
    )


def run_hashcore_cli(
    hashcore_cfg: dict,
    miner: dict,
    action: str,
    config: dict,
    qa_mode: bool,
    qa_allow_actions: bool,
    args_override: Optional[list] = None,
) -> Tuple[bool, str]:
    return _net_run_hashcore_cli(
        hashcore_cfg=hashcore_cfg,
        miner=miner,
        action=action,
        config=config,
        qa_mode=qa_mode,
        qa_allow_actions=qa_allow_actions,
        args_override=args_override,
        runner=_execute_subprocess_no_window,
        log_fn=log,
    )


def _mutex_name() -> str:
    return r"Global\MinerAlertsMonitor_fagdiaz"


def acquire_mutex_or_exit(mutex_name: str) -> int:
    global _MUTEX_HANDLE
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.CreateMutexW(None, True, mutex_name)
    if not handle:
        log("ERROR: No se pudo crear el mutex.")
        sys.exit(1)
    last_error = ctypes.get_last_error()
    if last_error == 183:
        log(
            f"PID={os.getpid()} PPID={os.getppid()} mutex={mutex_name} "
            f"last_error={last_error} acquired=False"
        )
        log("Ya hay otra instancia del monitor corriendo (mutex). Saliendo.")
        kernel32.CloseHandle(handle)
        sys.exit(0)
    log(
        f"PID={os.getpid()} PPID={os.getppid()} mutex={mutex_name} "
        f"last_error={last_error} acquired=True"
    )
    _MUTEX_HANDLE = handle
    return last_error


def release_mutex() -> None:
    global _MUTEX_HANDLE
    if not _MUTEX_HANDLE:
        return
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    try:
        kernel32.ReleaseMutex(_MUTEX_HANDLE)
    except Exception:
        pass
    try:
        kernel32.CloseHandle(_MUTEX_HANDLE)
    except Exception:
        pass
    _MUTEX_HANDLE = None


_LAST_DAILY_DIGEST_DATE: Optional[str] = None


def load_state(state_path: Path) -> Tuple[Dict[str, MinerState], Optional[int]]:
    global _LAST_DAILY_DIGEST_DATE
    if not state_path.exists():
        return {}, None
    bak_path = state_path.with_suffix(".bak")
    raw = None
    try:
        content = state_path.read_text(encoding="utf-8").strip()
        if not content or content.replace("\x00", "") == "":
            raise ValueError("empty or null-byte corrupted file")
        raw = json.loads(content)
    except Exception as primary_exc:
        log(f"[WARN] state.json corrupto o ilegible ({primary_exc}). Intentando recuperar desde .bak...")
        if bak_path.exists():
            try:
                bak_content = bak_path.read_text(encoding="utf-8").strip()
                if bak_content and bak_content.replace("\x00", "") != "":
                    raw = json.loads(bak_content)
                    log("[INFO] Estado restaurado exitosamente desde state.json.bak")
            except Exception as bak_exc:
                log(f"[WARN] state.json.bak también corrupto o ilegible ({bak_exc}).")
        if raw is None:
            log("[WARN] state.json corrupto. Se ignora.")
            return {}, None

    try:
        _LAST_DAILY_DIGEST_DATE = raw.get("last_daily_digest_date")
        saved_at = raw.get("saved_at")
        if saved_at:
            saved_dt = datetime.strptime(saved_at, "%Y-%m-%d %H:%M:%S")
            if (datetime.now() - saved_dt).total_seconds() > 48 * 3600:
                log("[WARN] state.json esta stale (>48h). Se ignora.")
                return {}, None
        states = {}
        raw_states = raw.get("states", {})
        for key, data in raw_states.items():
            raw_auto = data.get("auto_reboot_timestamps", [])
            if not isinstance(raw_auto, list):
                raw_auto = []
            auto_list = []
            for ts in raw_auto:
                try:
                    auto_list.append(float(ts))
                except (TypeError, ValueError):
                    continue
            state = MinerState(
                low_streak=0,
                offline_streak=int(data.get("offline_streak", 0)),
                ok_streak=int(data.get("ok_streak", 0)),
                state=str(data.get("state", STATE_OK)),
                initialized=bool(data.get("initialized", False)),
                last_elapsed=data.get("last_elapsed"),
                last_seen_ts=float(data.get("last_seen_ts", 0.0)),
                reboot_pending_until=float(data.get("reboot_pending_until", 0.0)),
                reboot_pending_reason=str(data.get("reboot_pending_reason", "")),
                reboot_pending_elapsed=data.get("reboot_pending_elapsed"),
                last_reboot_ts=float(data.get("last_reboot_ts", 0.0)),
                low_since_ts=None,
                hashboard_since_ts=None,
                last_manual_reboot_ts=(
                    float(data.get("last_manual_reboot_ts"))
                    if data.get("last_manual_reboot_ts") is not None
                    else None
                ),
                last_auto_reboot_ts=(
                    float(data.get("last_auto_reboot_ts"))
                    if data.get("last_auto_reboot_ts") is not None
                    else None
                ),
                last_auto_restart_ts=(
                    float(data.get("last_auto_restart_ts"))
                    if data.get("last_auto_restart_ts") is not None
                    else None
                ),
                auto_restart_count=int(data.get("auto_restart_count", 0)),
                auto_reboot_timestamps=auto_list,
                degraded_mode=bool(data.get("degraded_mode", False)),
                last_hourly_status_ts=(
                    float(data.get("last_hourly_status_ts"))
                    if data.get("last_hourly_status_ts") is not None
                    else None
                ),
                snooze_until_ts=(
                    float(data.get("snooze_until_ts"))
                    if data.get("snooze_until_ts") is not None
                    else None
                ),
                cooling_streak=int(data.get("cooling_streak", 0)),
                last_cooling_warning_ts=(
                    float(data.get("last_cooling_warning_ts"))
                    if data.get("last_cooling_warning_ts") is not None
                    else None
                ),
                efficiency_streak=int(data.get("efficiency_streak", 0)),
                last_efficiency_warning_ts=(
                    float(data.get("last_efficiency_warning_ts"))
                    if data.get("last_efficiency_warning_ts") is not None
                    else None
                ),
                baseline_frequency_mhz=(
                    float(data.get("baseline_frequency_mhz"))
                    if data.get("baseline_frequency_mhz") is not None
                    else None
                ),
                last_preset_warning_ts=(
                    float(data.get("last_preset_warning_ts"))
                    if data.get("last_preset_warning_ts") is not None
                    else None
                ),
                chain_warnings_ts=dict(data.get("chain_warnings_ts") or {}),
                # Spec 039: Fan Governor
                governor_duty=(
                    int(data.get("governor_duty"))
                    if data.get("governor_duty") is not None
                    else None
                ),
                governor_holds=int(data.get("governor_holds", 0)),
                governor_last_change_ts=float(data.get("governor_last_change_ts", 0.0)),
                governor_failures=int(data.get("governor_failures", 0)),
                governor_last_action=str(data.get("governor_last_action", "")),
                governor_last_temp_c=(
                    float(data.get("governor_last_temp_c"))
                    if data.get("governor_last_temp_c") is not None
                    else None
                ),
                governor_last_power_w=(
                    float(data.get("governor_last_power_w"))
                    if data.get("governor_last_power_w") is not None
                    else None
                ),
                # Spec 040: Dynamic Preset Balancer
                balancer_preset=(
                    str(data.get("balancer_preset"))
                    if data.get("balancer_preset") is not None
                    else None
                ),
                balancer_last_change_ts=float(data.get("balancer_last_change_ts", 0.0)),
                balancer_last_action=str(data.get("balancer_last_action", "")),
                balancer_last_reason=str(data.get("balancer_last_reason", "")),
                # Spec 062: HW Error Tripwire & Anti-Cascade Lock
                hw_error_lock_until_ts=(
                    float(data.get("hw_error_lock_until_ts"))
                    if data.get("hw_error_lock_until_ts") is not None
                    else None
                ),
                hw_error_locked_preset=(
                    str(data.get("hw_error_locked_preset"))
                    if data.get("hw_error_locked_preset") is not None
                    else None
                ),
                # Dynamic Vnish Overclock & Autoswitch State Discovery
                vnish_discovered_target_power_w=(
                    float(data.get("vnish_discovered_target_power_w"))
                    if data.get("vnish_discovered_target_power_w") is not None
                    else None
                ),
                vnish_discovered_preset=(
                    str(data.get("vnish_discovered_preset"))
                    if data.get("vnish_discovered_preset") is not None
                    else None
                ),
                vnish_discovered_top_preset=(
                    str(data.get("vnish_discovered_top_preset"))
                    if data.get("vnish_discovered_top_preset") is not None
                    else None
                ),
                vnish_discovered_switcher_enabled=(
                    bool(data.get("vnish_discovered_switcher_enabled"))
                    if data.get("vnish_discovered_switcher_enabled") is not None
                    else None
                ),
                vnish_discovered_ts=float(data.get("vnish_discovered_ts", 0.0)),
                # Spec 044: Silent Mode (C2 — hardware FSM, separate from snooze)
                silent_mode_active=bool(data.get("silent_mode_active", False)),
                silent_mode_revert_ts=(
                    float(data.get("silent_mode_revert_ts"))
                    if data.get("silent_mode_revert_ts") is not None
                    else None
                ),
                silent_mode_prev_duty=(
                    int(data.get("silent_mode_prev_duty"))
                    if data.get("silent_mode_prev_duty") is not None
                    else None
                ),
                silent_mode_prev_preset=(
                    str(data.get("silent_mode_prev_preset"))
                    if data.get("silent_mode_prev_preset") is not None
                    else None
                ),
                silent_mode_target_max_duty=int(data.get("silent_mode_target_max_duty", 50)),
                # Spec 048: Safe Fleet Shutdown & Maintenance Mode
                is_shutdown_maintenance=bool(data.get("is_shutdown_maintenance", False)),
                shutdown_maintenance_ts=float(data.get("shutdown_maintenance_ts", 0.0)),
                # Spec 046: Live Telemetry Snapshot for /status & mobile fleet cards
                last_rate_ths=(
                    float(data.get("last_rate_ths"))
                    if data.get("last_rate_ths") is not None
                    else None
                ),
                last_active_boards=(
                    int(data.get("last_active_boards"))
                    if data.get("last_active_boards") is not None
                    else None
                ),
                last_expected_boards=(
                    int(data.get("last_expected_boards"))
                    if data.get("last_expected_boards") is not None
                    else None
                ),
                last_max_chip_temp=(
                    float(data.get("last_max_chip_temp"))
                    if data.get("last_max_chip_temp") is not None
                    else None
                ),
                last_fan_duty_percent=(
                    float(data.get("last_fan_duty_percent"))
                    if data.get("last_fan_duty_percent") is not None
                    else None
                ),
                last_power_w=(
                    float(data.get("last_power_w"))
                    if data.get("last_power_w") is not None
                    else None
                ),
                last_efficiency_j_th=(
                    float(data.get("last_efficiency_j_th"))
                    if data.get("last_efficiency_j_th") is not None
                    else None
                ),
                last_responded=bool(data.get("last_responded", False)),
                inlet_temp_c=(
                    float(data.get("inlet_temp_c"))
                    if data.get("inlet_temp_c") is not None
                    else None
                ),
                # Spec 075: Soft-Landing Recovery
                stopped_since_ts=(
                    float(data.get("stopped_since_ts"))
                    if data.get("stopped_since_ts") is not None
                    else None
                ),
                is_pre_clamped=bool(data.get("is_pre_clamped", False)),
                original_preset_before_clamp=(
                    str(data.get("original_preset_before_clamp"))
                    if data.get("original_preset_before_clamp") is not None
                    else None
                ),
                staged_ramp_up_pending=bool(data.get("staged_ramp_up_pending", False)),
                staged_ramp_up_soak_start_ts=(
                    float(data.get("staged_ramp_up_soak_start_ts"))
                    if data.get("staged_ramp_up_soak_start_ts") is not None
                    else None
                ),
            )
            states[key] = state
        last_update_id = raw.get("last_update_id")
        raw_sch = raw.get("scheduled_maintenance")
        if raw_sch and isinstance(raw_sch, dict):
            try:
                from app.governance.maintenance_scheduler import ScheduledWindow
                global _ACTIVE_SCHEDULED_WINDOW
                _ACTIVE_SCHEDULED_WINDOW = ScheduledWindow.from_dict(raw_sch)
                log(f"[SCHEDULER] Reconstituted scheduled maintenance window: id={_ACTIVE_SCHEDULED_WINDOW.window_id} stage={_ACTIVE_SCHEDULED_WINDOW.stage.value}")
            except Exception as _sch_exc:
                log(f"[WARN] Error deserializing scheduled_maintenance: {_sch_exc}")
        raw_gov = raw.get("intervention_governance")
        if raw_gov and isinstance(raw_gov, dict):
            try:
                from app.governance.intervention_policy import InterventionGovernance
                global _GLOBAL_INTERVENTION_GOV
                _GLOBAL_INTERVENTION_GOV = InterventionGovernance.from_dict(raw_gov)
                for st in states.values():
                    st.intervention_gov = _GLOBAL_INTERVENTION_GOV
                log(f"[INTERVENTIONS] Reconstituted intervention governance: master={_GLOBAL_INTERVENTION_GOV.master_enabled} reason={_GLOBAL_INTERVENTION_GOV.disabled_reason}")
            except Exception as _gov_exc:
                log(f"[WARN] Error deserializing intervention_governance: {_gov_exc}")
        raw_contingency = raw.get("elevator_contingency")
        if raw_contingency and isinstance(raw_contingency, dict):
            try:
                from app.governance.adaptive_contingency import GroupContingencyState
                global _ELEVATOR_CONTINGENCY_STATES
                _ELEVATOR_CONTINGENCY_STATES = {
                    grp: GroupContingencyState.from_dict(c_data)
                    for grp, c_data in raw_contingency.items()
                }
                log(f"[CONTINGENCY] Reconstituted elevator contingency: {list(_ELEVATOR_CONTINGENCY_STATES.keys())}")
            except Exception as _c_exc:
                log(f"[WARN] Error deserializing elevator_contingency: {_c_exc}")
        return states, int(last_update_id) if last_update_id is not None else None
    except Exception:
        log("[WARN] state.json corrupto. Se ignora.")
        return {}, None


_SAVE_STATE_LOCK = threading.Lock()


def _build_state_payload(
    states: Dict[str, MinerState],
    last_update_id: Optional[int],
    last_daily_digest_date: Optional[str] = None,
) -> dict:
    global _LAST_DAILY_DIGEST_DATE
    if last_daily_digest_date is not None:
        _LAST_DAILY_DIGEST_DATE = last_daily_digest_date
    sch_win = _ACTIVE_SCHEDULED_WINDOW
    gov_obj = globals().get("_GLOBAL_INTERVENTION_GOV")
    cont_states = globals().get("_ELEVATOR_CONTINGENCY_STATES") or {}
    payload = {
        "saved_at": now_str(),
        "last_update_id": last_update_id,
        "last_daily_digest_date": _LAST_DAILY_DIGEST_DATE,
        "scheduled_maintenance": sch_win.to_dict() if sch_win is not None else None,
        "intervention_governance": gov_obj.to_dict() if gov_obj is not None else None,
        "elevator_contingency": {grp: s.to_dict() for grp, s in list(cont_states.items())} if cont_states else None,
        "states": {},
    }

    from app.core.state_manager import serialize_miner_state
    for key, state in list(states.items()):
        payload["states"][key] = serialize_miner_state(state)
    return payload


def _flush_state_payload(state_path: Path, payload: dict) -> None:
    tmp_path = state_path.with_suffix(".tmp")
    bak_path = state_path.with_suffix(".bak")
    with _SAVE_STATE_LOCK:
        try:
            content = json.dumps(payload, indent=2)
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            if state_path.exists():
                try:
                    import shutil
                    shutil.copyfile(state_path, bak_path)
                except Exception:
                    pass
            os.replace(tmp_path, state_path)
        except Exception:
            log("[WARN] No se pudo guardar state.json.")


def save_state(
    state_path: Path,
    states: Dict[str, MinerState],
    last_update_id: Optional[int],
    last_daily_digest_date: Optional[str] = None,
) -> None:
    payload = _build_state_payload(states, last_update_id, last_daily_digest_date)
    _flush_state_payload(state_path, payload)


# ---------------------------------------------------------------------------
# Spec 054: Asynchronous Hashboard Chain Telemetry Worker
# ---------------------------------------------------------------------------

_CHAIN_HEALTH_STREAKS: Dict[str, Dict[str, Any]] = {}


def _async_collect_chain_telemetry(
    miners_list: list,
    event_store_inst: Optional[Any],
    token: Optional[str] = None,
    miner_name_filter: Optional[str] = None,
    config: Optional[dict] = None,
    bot_token: Optional[str] = None,
    chat_id: Optional[str] = None,
    qa_mode: bool = False,
    qa_notify: bool = False,
) -> None:
    """Collect /api/v1/chains in background, record to EventStore, and evaluate predictive health (Spec 054)."""
    if event_store_inst is None or not event_store_inst.available:
        return
    try:
        from app.vnish.chain_collector import fetch_miner_chains
        from app.governance.chain_health import (
            assess_miner_chains,
            evaluate_chain_health_streak,
        )

        for m in miners_list:
            m_name = str(m.get("name", ""))
            if miner_name_filter and m_name != miner_name_filter:
                continue
            m_host = str(m.get("host", ""))
            if not m_host:
                continue
            ok, chains, err = fetch_miner_chains(m_host, token=token, timeout=2.5)
            if ok and chains:
                inserted = event_store_inst.record_chain_samples(m_name, chains)
                log(f"[CHAIN_TELEMETRY] miner={m_name} collected={len(chains)} inserted={inserted}")

                # Spec 054 T008: Chain Health Assessment & Predictive Alerting
                try:
                    assessment = assess_miner_chains(m_name, chains)
                    streak_data = _CHAIN_HEALTH_STREAKS.setdefault(m_name, {})
                    min_streak = int(config.get("chain_health_min_streak", 2)) if config else 2
                    cooldown = float(config.get("chain_health_cooldown_s", 7200.0)) if config else 7200.0
                    should_alert, alert_card = evaluate_chain_health_streak(
                        streak_data,
                        assessment,
                        min_streak=min_streak,
                        cooldown_s=cooldown,
                    )
                    if should_alert and alert_card:
                        if bot_token and chat_id and ((not qa_mode) or qa_notify):
                            send_telegram(
                                bot_token,
                                str(chat_id),
                                alert_card,
                                "CHAIN_HEALTH",
                                "chain_health_warning",
                            )
                        if event_store_inst and event_store_inst.available:
                            event_store_inst.record_event(
                                occurred_ts=time.time(),
                                miner_key=f"{m_name}|{m_host}",
                                miner_name=m_name,
                                host=m_host,
                                event_type="chain_health_warning",
                                severity="warning",
                                summary=assessment.summary,
                                details={
                                    "overall_status": assessment.overall_status,
                                    "faulty_chains": list(assessment.faulty_chains),
                                    "has_sensor_error": assessment.has_sensor_error,
                                },
                            )
                        log(f"[CHAIN_HEALTH] Alert sent for miner={m_name} status={assessment.overall_status}")
                except Exception as _ch_exc:
                    log(f"[CHAIN_HEALTH_ERR] assessment failed for {m_name}: {_ch_exc}")
            elif err:
                log(f"[CHAIN_TELEMETRY] miner={m_name} host={m_host} error={err}")
    except Exception as exc:
        log(f"[CHAIN_TELEMETRY] worker error: {type(exc).__name__}: {exc}")


def _async_evaluate_predictive_chain_break(
    miners_list: list,
    event_store_inst: Optional[Any],
    miner_states: Dict[str, Any],
    state_lock: threading.Lock,
    config: Optional[dict] = None,
    bot_token: Optional[str] = None,
    chat_id: Optional[str] = None,
    qa_mode: bool = False,
    qa_notify: bool = False,
    now_ts: Optional[float] = None,
) -> None:
    """Hourly deep telemetry evaluation & predictive chain break alerting (Spec 069 / PROP-008)."""
    if event_store_inst is None or not event_store_inst.available:
        return
    cfg = config or {}
    if not bool(cfg.get("predictive_chain_break_enabled", True)):
        return

    try:
        from app.governance.chain_health import (
            PredictiveChainEngine,
            PredictiveChainRisk,
            build_predictive_chain_risk_card,
        )

        engine = PredictiveChainEngine()
        now = float(now_ts) if now_ts is not None else time.time()
        cooldown_s = float(cfg.get("chain_warning_cooldown_hours", 24.0)) * 3600.0
        persistence_hours = float(cfg.get("chain_sensor_error_persistence_hours", 12.0))
        since_ts = now - (persistence_hours * 3600.0)

        raw_risks: List[PredictiveChainRisk] = []

        for m in miners_list:
            m_name = str(m.get("name", ""))
            m_host = str(m.get("host", ""))
            if not m_name and not m_host:
                continue

            candidate_keys = [m_name]
            if m_name and m_host:
                candidate_keys.append(f"{m_name}|{m_host}")
            if m_host:
                candidate_keys.append(m_host)

            latest = None
            for ck in candidate_keys:
                latest = event_store_inst.get_latest_chain_samples(ck)
                if latest:
                    break

            chain_ids = [int(r["chain_id"]) for r in latest] if latest else [0, 1, 2]

            chain_samples_map: Dict[int, list] = {}
            for cid in chain_ids:
                samples: list = []
                for ck in candidate_keys:
                    samples = event_store_inst.fetch_chain_samples_window(ck, cid, since_ts)
                    if samples:
                        break
                chain_samples_map[cid] = samples

            for cid in chain_ids:
                c_samples = chain_samples_map.get(cid, [])
                if not c_samples:
                    continue
                sib_map = {sid: s_list for sid, s_list in chain_samples_map.items() if sid != cid}
                risk = engine.evaluate_chain_history(
                    samples=c_samples,
                    now_ts=now,
                    config=cfg,
                    miner_name=m_name,
                    chain_id=cid,
                    sibling_chains_samples=sib_map,
                )
                if risk is not None:
                    raw_risks.append(risk)

        correlated_risks = engine.correlate_electrical_group(
            raw_risks,
            miners_config=miners_list,
            now_ts=now,
        )

        for risk in correlated_risks:
            chain_key = str(risk.chain_id)
            target_miner_name = risk.miner_name

            should_alert = False
            with state_lock:
                st = None
                if target_miner_name.startswith("Grupo "):
                    grp_name = target_miner_name[6:].strip()
                    grp_key = f"group_{grp_name}"
                    member_names = {
                        str(m.get("name")) for m in miners_list
                        if str(m.get("electrical_group") or m.get("group") or m.get("elevator") or "").strip() == grp_name
                    }
                    member_states = [
                        s for k, s in miner_states.items()
                        if any(k == m_nm or k.startswith(f"{m_nm}|") or k.split("|")[0] == m_nm for m_nm in member_names)
                    ]
                    if member_states:
                        last_ts = max(float(s.chain_warnings_ts.get(grp_key, 0.0)) for s in member_states)
                        if (now - last_ts) >= cooldown_s:
                            for s in member_states:
                                s.chain_warnings_ts[grp_key] = now
                            should_alert = True
                    else:
                        should_alert = True
                else:
                    for k, s in miner_states.items():
                        if (
                            k == target_miner_name
                            or k.startswith(f"{target_miner_name}|")
                            or k.split("|")[0] == target_miner_name
                        ):
                            st = s
                            break

                    if st is not None:
                        last_ts = float(st.chain_warnings_ts.get(chain_key, 0.0))
                        if (now - last_ts) >= cooldown_s:
                            st.chain_warnings_ts[chain_key] = now
                            should_alert = True
                    else:
                        should_alert = True

            if should_alert:
                alert_card = build_predictive_chain_risk_card(risk)
                if bot_token and chat_id and ((not qa_mode) or qa_notify):
                    send_telegram(
                        bot_token,
                        str(chat_id),
                        alert_card,
                        "CHAIN_PREDICTIVE",
                        "predictive_chain_break_warning",
                    )
                if event_store_inst and event_store_inst.available:
                    event_store_inst.record_event(
                        occurred_ts=now,
                        miner_key=risk.miner_name,
                        miner_name=risk.miner_name,
                        host="",
                        event_type="predictive_chain_break_warning",
                        severity=risk.severity.lower(),
                        summary=risk.message,
                        details={
                            "risk_type": risk.risk_type,
                            "chain_id": risk.chain_id,
                            "persistence_hours": risk.persistence_hours,
                            "error_sample_pct": risk.error_sample_pct,
                            "faulty_locs": list(risk.faulty_locs),
                        },
                    )
                log(f"[PREDICTIVE_CHAIN] Alert sent for miner={risk.miner_name} chain={risk.chain_id} risk={risk.risk_type}")

    except Exception as exc:
        log(f"[PREDICTIVE_CHAIN_ERR] worker failed: {type(exc).__name__}: {exc}")




# ---------------------------------------------------------------------------
# Spec 039: Fan Governor — runtime override flag (set by /gov on/off commands)
# ---------------------------------------------------------------------------
# None = use config value; True/False = user override (persists until restart)
_GOVERNOR_RUNTIME_ENABLED: Optional[bool] = None



# ---------------------------------------------------------------------------
# T014: Fan Governor execution cycle (Spec 039)
# ---------------------------------------------------------------------------

def execute_governor_cycle(
    miners: list,
    states: Dict[str, "MinerState"],
    state_lock: threading.Lock,
    config: dict,
    now_ts: float,
    qa_mode: bool = False,
) -> list:
    """Execute one fan governor tick: evaluate decisions for all miners, dispatch
    hardware writes in parallel via ThreadPoolExecutor (R2 constraint), and update
    per-miner state fields under state_lock.

    This function is defensive: any exception in the entire cycle is caught and
    logged without propagating to the authoritative 4028 tick.
    """
    import concurrent.futures

    gov_enabled_cfg = bool(config.get("fan_governor_enabled", False))
    gov_enabled = (
        _GOVERNOR_RUNTIME_ENABLED
        if _GOVERNOR_RUNTIME_ENABLED is not None
        else gov_enabled_cfg
    )
    if not gov_enabled or qa_mode:
        return []

    # Spec 057: Check intervention governance for Fan Governor
    from app.governance.intervention_policy import ACTION_FAN_GOVERNOR, should_allow_intervention
    gov_obj = globals().get("_GLOBAL_INTERVENTION_GOV")
    if gov_obj is not None and not should_allow_intervention(ACTION_FAN_GOVERNOR, gov_obj, time.time())[0]:
        return []


    dry_run = bool(config.get("fan_governor_dry_run", True))
    vnish_pw = str(config.get("vnish_api_password", "admin"))
    gov_cfg = GovernorConfig(
        enabled=True,
        dry_run=dry_run,
        target_temp_c=float(config.get("fan_governor_target_temp_c", 82.0)),
        deadband_low_c=float(config.get("fan_governor_deadband_low_c", 81.0)),
        deadband_high_c=float(config.get("fan_governor_deadband_high_c", 82.5)),
        emergency_spike_temp_c=float(config.get("fan_governor_emergency_temp_c", 83.0)),
        min_fan_duty_percent=int(config.get("fan_governor_min_duty_pct", 30)),
        max_fan_duty_percent=100,
        step_down_percent=int(config.get("fan_governor_step_down_pct", 2)),
        step_up_percent=int(config.get("fan_governor_step_up_pct", 3)),
        dwell_seconds=int(config.get("fan_governor_dwell_seconds", 90)),
        adaptive_dwell_seconds=int(config.get("fan_governor_adaptive_dwell_seconds", 120)),
        consecutive_holds_threshold=int(config.get("fan_governor_holds_threshold", 3)),
        request_timeout_seconds=float(config.get("fan_governor_request_timeout", 2.5)),
        fleet_timeout_seconds=float(config.get("fan_governor_fleet_timeout", 5.0)),
        max_consecutive_failures=int(config.get("fan_governor_max_failures", 3)),
        power_margin_w=float(config.get("fan_governor_power_margin_w", 120.0)),
        # Spec 063: Ambient-Aware Thermal PID (GOV-02)
        seasonal_enabled=bool(config.get("fan_governor_seasonal_enabled", True)),
        winter_ambient_threshold_c=float(config.get("fan_governor_winter_ambient_threshold_c", 18.0)),
        summer_ambient_threshold_c=float(config.get("fan_governor_summer_ambient_threshold_c", 28.0)),
        winter_target_temp_c=float(config.get("fan_governor_winter_target_temp_c", 76.0)),
        winter_min_duty_percent=int(config.get("fan_governor_winter_min_duty_pct", 45)),
        summer_target_temp_c=float(config.get("fan_governor_summer_target_temp_c", 80.0)),
        summer_min_duty_percent=int(config.get("fan_governor_summer_min_duty_pct", 65)),
        summer_step_up_percent=int(config.get("fan_governor_summer_step_up_pct", 5)),
    )

    # Build (miner, state, decision) triples
    miner_decisions: list = []
    with state_lock:
        # Spec 063: Ambient temperature aggregation across electrical groups and fleet
        group_inlet_temps: Dict[str, list[float]] = {}
        fleet_inlet_temps: list[float] = []
        for m in miners:
            m_name = m.get("name", "")
            m_host = m.get("host", "")
            m_port = m.get("port", 4028)
            st = states.get(f"{m_name}|{m_host}:{m_port}")
            inlet = getattr(st, "inlet_temp_c", None) if st else None
            if inlet is not None and -10.0 <= inlet <= 60.0:
                grp = m.get("electrical_group") or m.get("group")
                if grp:
                    group_inlet_temps.setdefault(str(grp), []).append(inlet)
                fleet_inlet_temps.append(inlet)

        for miner in miners:
            name = miner.get("name", "")
            host = miner.get("host", "")
            port = miner.get("port", 4028)
            state_key = f"{name}|{host}:{port}"
            state = states.get(state_key)
            if state is None:
                continue
            if getattr(state, "is_shutdown_maintenance", False):
                continue
            seconds_since = now_ts - (state.governor_last_change_ts or 0.0)

            # Determine target_power_w for autoswitch recovery cooling
            # Priority:
            # 1. Dynamically assigned balancer preset (contingency or dynamic balancer)
            # 2. Hardware error locked preset (tripwire)
            # 3. Discovered active preset from Vnish
            # 4. Discovered target power from Vnish
            # 5. Configured target_power_w or max_preset in miner definition
            # 6. Global default fan_governor_target_power_w (2700.0)
            def _parse_preset_w(val: Any) -> Optional[float]:
                if val is None:
                    return None
                s = str(val).upper().replace("W", "").strip()
                try:
                    p = float(s)
                    return p if p > 0 else None
                except ValueError:
                    return None

            active_preset_str = (
                getattr(state, "balancer_preset", None)
                or getattr(state, "hw_error_locked_preset", None)
                or getattr(state, "vnish_discovered_preset", None)
            )
            target_pwr = _parse_preset_w(active_preset_str)
            if target_pwr is None:
                target_pwr = getattr(state, "vnish_discovered_target_power_w", None)
            if target_pwr is None:
                target_pwr = miner.get("target_power_w")
            if target_pwr is None:
                target_pwr = _parse_preset_w(miner.get("max_preset"))
            if target_pwr is None:
                target_pwr = float(config.get("fan_governor_target_power_w", 2700.0))

            # Per-miner configuration overrides (if present in miner config dict)
            miner_gov_cfg = gov_cfg
            if any(k in miner for k in ("target_temp_c", "deadband_low_c", "deadband_high_c", "emergency_temp_c", "min_duty_pct", "power_margin_w")):
                miner_gov_cfg = GovernorConfig(
                    enabled=gov_cfg.enabled,
                    dry_run=gov_cfg.dry_run,
                    target_temp_c=float(miner.get("target_temp_c", gov_cfg.target_temp_c)),
                    deadband_low_c=float(miner.get("deadband_low_c", gov_cfg.deadband_low_c)),
                    deadband_high_c=float(miner.get("deadband_high_c", gov_cfg.deadband_high_c)),
                    emergency_spike_temp_c=float(miner.get("emergency_temp_c", gov_cfg.emergency_spike_temp_c)),
                    min_fan_duty_percent=int(miner.get("min_duty_pct", gov_cfg.min_fan_duty_percent)),
                    max_fan_duty_percent=gov_cfg.max_fan_duty_percent,
                    step_down_percent=gov_cfg.step_down_percent,
                    step_up_percent=gov_cfg.step_up_percent,
                    dwell_seconds=gov_cfg.dwell_seconds,
                    adaptive_dwell_seconds=gov_cfg.adaptive_dwell_seconds,
                    consecutive_holds_threshold=gov_cfg.consecutive_holds_threshold,
                    request_timeout_seconds=gov_cfg.request_timeout_seconds,
                    fleet_timeout_seconds=gov_cfg.fleet_timeout_seconds,
                    max_consecutive_failures=gov_cfg.max_consecutive_failures,
                    power_margin_w=float(miner.get("power_margin_w", gov_cfg.power_margin_w)),
                    seasonal_enabled=gov_cfg.seasonal_enabled,
                    winter_ambient_threshold_c=gov_cfg.winter_ambient_threshold_c,
                    summer_ambient_threshold_c=gov_cfg.summer_ambient_threshold_c,
                    winter_target_temp_c=gov_cfg.winter_target_temp_c,
                    winter_min_duty_percent=gov_cfg.winter_min_duty_percent,
                    summer_target_temp_c=gov_cfg.summer_target_temp_c,
                    summer_min_duty_percent=gov_cfg.summer_min_duty_percent,
                    summer_step_up_percent=gov_cfg.summer_step_up_percent,
                )

            # Spec 044 C3: If silent mode active for this miner, constrain the Governor to
            # operate within the acoustic ceiling. EMERGENCY_SPIKE overrides max_fan_duty_percent
            # by its own rule (goes to 100% regardless), so this is safe.
            if getattr(state, "silent_mode_active", False):
                _sm_min = int(config.get("silent_mode_min_duty_pct", 30))
                _sm_max = int(getattr(state, "silent_mode_target_max_duty", 50))
                _eff_min = min(_sm_min, _sm_max)
                _eff_max = max(_sm_min, _sm_max)
                miner_gov_cfg = GovernorConfig(
                    enabled=miner_gov_cfg.enabled,
                    dry_run=miner_gov_cfg.dry_run,
                    target_temp_c=miner_gov_cfg.target_temp_c,
                    deadband_low_c=miner_gov_cfg.deadband_low_c,
                    deadband_high_c=miner_gov_cfg.deadband_high_c,
                    emergency_spike_temp_c=miner_gov_cfg.emergency_spike_temp_c,
                    min_fan_duty_percent=_eff_min,
                    max_fan_duty_percent=_eff_max,  # Acoustic ceiling
                    step_down_percent=miner_gov_cfg.step_down_percent,
                    step_up_percent=miner_gov_cfg.step_up_percent,
                    dwell_seconds=miner_gov_cfg.dwell_seconds,
                    adaptive_dwell_seconds=miner_gov_cfg.adaptive_dwell_seconds,
                    consecutive_holds_threshold=miner_gov_cfg.consecutive_holds_threshold,
                    request_timeout_seconds=miner_gov_cfg.request_timeout_seconds,
                    fleet_timeout_seconds=miner_gov_cfg.fleet_timeout_seconds,
                    max_consecutive_failures=miner_gov_cfg.max_consecutive_failures,
                    power_margin_w=miner_gov_cfg.power_margin_w,
                    seasonal_enabled=miner_gov_cfg.seasonal_enabled,
                    winter_ambient_threshold_c=miner_gov_cfg.winter_ambient_threshold_c,
                    summer_ambient_threshold_c=miner_gov_cfg.summer_ambient_threshold_c,
                    winter_target_temp_c=miner_gov_cfg.winter_target_temp_c,
                    winter_min_duty_percent=miner_gov_cfg.winter_min_duty_percent,
                    summer_target_temp_c=miner_gov_cfg.summer_target_temp_c,
                    summer_min_duty_percent=miner_gov_cfg.summer_min_duty_percent,
                    summer_step_up_percent=miner_gov_cfg.summer_step_up_percent,
                )

            # Spec 063: Determine effective ambient temperature for this miner
            miner_grp = miner.get("electrical_group") or miner.get("group")
            amb_temp: Optional[float] = None
            if miner_grp and str(miner_grp) in group_inlet_temps and group_inlet_temps[str(miner_grp)]:
                amb_temp = round(sum(group_inlet_temps[str(miner_grp)]) / len(group_inlet_temps[str(miner_grp)]), 2)
            else:
                own_inlet = getattr(state, "inlet_temp_c", None)
                if own_inlet is not None and -10.0 <= own_inlet <= 60.0:
                    amb_temp = own_inlet
                elif fleet_inlet_temps:
                    amb_temp = round(sum(fleet_inlet_temps) / len(fleet_inlet_temps), 2)

            gov_target_pwr = None if getattr(state, "silent_mode_active", False) else target_pwr
            miner_is_warming_up = (
                (getattr(state, "last_elapsed", None) is not None and getattr(state, "last_elapsed", 999) < 240)
                or (getattr(state, "reboot_pending_until", 0.0) > now_ts)
            )
            boost_cooling_is_active = bool(
                getattr(state, "boost_cooling_active", False)
                and (getattr(state, "boost_cooling_expires_ts", 0.0) > now_ts)
            )
            if getattr(state, "boost_cooling_active", False) and not boost_cooling_is_active:
                with state_lock:
                    state.boost_cooling_active = False
                    state.boost_cooling_expires_ts = None

            decision = compute_governor_step(
                max_temp_c=state.governor_last_temp_c,
                current_duty=state.governor_duty,
                seconds_since_last_change=seconds_since,
                consecutive_holds=state.governor_holds,
                consecutive_failures=state.governor_failures,
                config=miner_gov_cfg,
                current_power_w=getattr(state, "governor_last_power_w", None),
                target_power_w=gov_target_pwr,
                ambient_temp_c=amb_temp,
                is_warming_up=miner_is_warming_up,
                boost_cooling=boost_cooling_is_active,
            )
            miner_decisions.append((miner, state_key, decision))

    if not miner_decisions:
        return

    # Dispatch parallel hardware writes for miners that need action (R2)
    write_results: Dict[str, tuple] = {}  # state_key -> (success, error)
    writers = [
        (miner, sk, dec)
        for miner, sk, dec in miner_decisions
        if dec.requires_write and not dry_run
    ]
    if writers:
        executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=min(4, len(writers))
        )
        try:
            future_to_key = {
                executor.submit(
                    safe_set_fan_duty,
                    miner.get("host", ""),
                    vnish_pw,
                    dec.target_duty,
                    gov_cfg.request_timeout_seconds,
                ): sk
                for miner, sk, dec in writers
            }
            deadline = time.monotonic() + gov_cfg.fleet_timeout_seconds
            for future in concurrent.futures.as_completed(
                future_to_key.keys(),
                timeout=gov_cfg.fleet_timeout_seconds,
            ):
                sk = future_to_key[future]
                try:
                    ok, err = future.result(timeout=max(0.1, deadline - time.monotonic()))
                    write_results[sk] = (ok, err)
                except Exception as exc:
                    write_results[sk] = (False, str(exc))
        except concurrent.futures.TimeoutError:
            # Fleet timeout expired — record remaining futures as timed out
            for future, sk in future_to_key.items():
                if sk not in write_results:
                    write_results[sk] = (False, "fleet_timeout")
        finally:
            # Abandon (don't wait for) any in-flight threads beyond the timeout
            executor.shutdown(wait=False)

    # Update per-miner state under state_lock — also handles C4 Thermal Guard
    thermal_guard_events: list = []  # (miner_name, temp_c, action) for caller to notify Telegram
    with state_lock:
        for miner, sk, dec in miner_decisions:
            state = states.get(sk)
            if state is None:
                continue
            name_display = miner.get("name", sk)
            action = dec.action
            new_duty = dec.target_duty

            # Determine if write succeeded
            write_ok = True
            write_err = None
            if dec.requires_write and not dry_run:
                write_ok, write_err = write_results.get(sk, (False, "no_result"))

            # Update failure counter
            if dec.requires_write and not dry_run:
                if write_ok:
                    state.governor_failures = 0
                else:
                    state.governor_failures = state.governor_failures + 1
            else:
                if write_ok:
                    state.governor_failures = 0

            # Update duty and holds
            if action == ACTION_HOLD_TARGET:
                state.governor_holds = state.governor_holds + 1
            elif action != ACTION_HOLD_DWELL:
                state.governor_holds = 0

            if dec.requires_write and (dry_run or write_ok):
                state.governor_duty = new_duty
                state.governor_last_change_ts = now_ts

            state.governor_last_action = action

            # Spec 044 C4: Thermal Guard — atomically cancel silent_mode on emergency.
            # EMERGENCY_SPIKE (T >= emergency_spike_temp_c) or FAILSAFE_FAULT (3 HTTP failures)
            # must override the acoustic ceiling immediately and clear state.json.
            if action in (ACTION_EMERGENCY_SPIKE, ACTION_FAILSAFE_FAULT):
                if getattr(state, "silent_mode_active", False):
                    prev_max = getattr(state, "silent_mode_target_max_duty", 50)
                    state.silent_mode_active = False
                    state.silent_mode_revert_ts = None
                    temp_c = state.governor_last_temp_c
                    thermal_guard_events.append((name_display, temp_c, action, prev_max))
                    log(
                        f"[THERMAL_GUARD] Silent mode CANCELLED for miner={name_display} "
                        f"action={action} temp={temp_c}°C prev_max={prev_max}%"
                    )

            # Structured log
            dr_tag = " DRY" if dry_run else ""
            duty_tag = f"duty={state.governor_duty}%" if state.governor_duty is not None else "duty=?"
            err_tag = f" err={write_err}" if write_err else ""
            pwr_val = getattr(state, "governor_last_power_w", None)
            tgt_pwr = miner.get("target_power_w")
            if pwr_val is not None and tgt_pwr is not None:
                pwr_tag = f" pwr={pwr_val:.0f}/{tgt_pwr:.0f}W"
            elif pwr_val is not None:
                pwr_tag = f" pwr={pwr_val:.0f}W"
            else:
                pwr_tag = ""
            season_tag = f" season={dec.seasonal_mode}" if getattr(dec, "seasonal_mode", None) else ""
            log(
                f"[GOV{dr_tag}] miner={name_display} action={action} "
                f"{duty_tag} target={new_duty}% "
                f"holds={state.governor_holds} fails={state.governor_failures}{pwr_tag}{season_tag}{err_tag}"
            )

    return thermal_guard_events


# ---------------------------------------------------------------------------
# Dynamic Vnish Overclock & Autoswitch State Discovery
# ---------------------------------------------------------------------------
_LAST_VNISH_SYNC_TS: float = 0.0


def refresh_vnish_overclock_settings(
    miners: list,
    states: Dict[str, "MinerState"],
    state_lock: threading.Lock,
    vnish_pw: str,
    timeout: float = 2.5,
    force: bool = False,
    now_ts: Optional[float] = None,
) -> Dict[str, dict]:
    """
    Query Vnish REST API for all miners in parallel to discover active overclock
    preset and preset_switcher configuration (top_preset).
    Updates state.vnish_discovered_* fields dynamically.
    Guarantees non-blocking execution with fleet timeout.
    """
    global _LAST_VNISH_SYNC_TS
    current_ts = now_ts or time.time()
    if not force and (current_ts - _LAST_VNISH_SYNC_TS) < 300.0:
        return {}
    _LAST_VNISH_SYNC_TS = current_ts

    import concurrent.futures

    active_miners = [m for m in miners if m.get("host")]
    if not active_miners:
        return {}

    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(active_miners))) as pool:
        futures = {
            pool.submit(safe_get_overclock_settings, m.get("host", ""), vnish_pw, timeout=timeout): m
            for m in active_miners
        }
        try:
            for future in concurrent.futures.as_completed(futures, timeout=timeout * 2):
                m = futures[future]
                m_name = m.get("name") or str(m.get("host"))
                m_host = m.get("host", "")
                m_port = m.get("port", 4028)
                sk = f"{m_name}|{m_host}:{m_port}"
                try:
                    ok, data, err = future.result()
                    if ok and data:
                        results[sk] = data
                        with state_lock:
                            st = states.get(sk)
                            if st is not None:
                                old_tgt = st.vnish_discovered_target_power_w
                                st.vnish_discovered_target_power_w = data.get("target_power_w")
                                st.vnish_discovered_preset = data.get("preset")
                                st.vnish_discovered_top_preset = data.get("top_preset")
                                st.vnish_discovered_switcher_enabled = data.get("switcher_enabled")
                                st.vnish_discovered_ts = current_ts
                                if old_tgt != st.vnish_discovered_target_power_w and old_tgt is not None:
                                    log(
                                        f"[VNISH_SYNC] miner={m_name} target_power_w adaptado dinamicamente: "
                                        f"{old_tgt}W -> {st.vnish_discovered_target_power_w}W "
                                        f"(top_preset={st.vnish_discovered_top_preset}, switcher={st.vnish_discovered_switcher_enabled})"
                                    )
                                elif old_tgt is None and st.vnish_discovered_target_power_w is not None:
                                    log(
                                        f"[VNISH_SYNC] miner={m_name} overclock descubierto: "
                                        f"preset={st.vnish_discovered_preset} top_preset={st.vnish_discovered_top_preset} "
                                        f"target_pwr={st.vnish_discovered_target_power_w}W switcher={st.vnish_discovered_switcher_enabled}"
                                    )
                                # Spec 062: Anti-Cascade Post-Reboot Interlock
                                # Enforce locked preset if firmware booted or switched to a higher preset
                                if (
                                    st.hw_error_lock_until_ts
                                    and current_ts < st.hw_error_lock_until_ts
                                    and st.hw_error_locked_preset
                                    and st.vnish_discovered_preset
                                ):
                                    from app.governance.preset_balancer import find_preset_index
                                    curr_p_idx = find_preset_index(st.vnish_discovered_preset)
                                    lock_p_idx = find_preset_index(st.hw_error_locked_preset)
                                    if curr_p_idx >= 0 and lock_p_idx >= 0:
                                        is_higher = (curr_p_idx > lock_p_idx)
                                    else:
                                        curr_digits = re.findall(r"\d+", str(st.vnish_discovered_preset))
                                        lock_digits = re.findall(r"\d+", str(st.hw_error_locked_preset))
                                        curr_w = int(curr_digits[0]) if curr_digits else 0
                                        lock_w = int(lock_digits[0]) if lock_digits else 0
                                        is_higher = (curr_w > lock_w > 0)
                                    if is_higher:
                                        log(
                                            f"[TRIPWIRE_INTERLOCK] miner={m_name} detecto preset superior ({st.vnish_discovered_preset}) "
                                            f"a candado ({st.hw_error_locked_preset}). Forzando restauracion defensiva."
                                        )
                                        def _async_restore_tripwire_preset(
                                            _h=m_host,
                                            _pw=vnish_pw,
                                            _pr=st.hw_error_locked_preset,
                                            _to=timeout,
                                            _nm=m_name,
                                        ):
                                            try:
                                                ok_r, err_r = safe_set_miner_preset(_h, _pw, _pr, timeout=_to)
                                                if ok_r:
                                                    log(f"[TRIPWIRE_INTERLOCK_RESTORE_OK] miner={_nm} preset restaurado defensivamente a {_pr}")
                                                else:
                                                    log(f"[TRIPWIRE_INTERLOCK_RESTORE_FAIL] miner={_nm} fallo restaurando a {_pr}: {err_r}")
                                            except Exception as _th_exc:
                                                log(f"[TRIPWIRE_INTERLOCK_RESTORE_ERR] miner={_nm} excepcion en hilo de restauracion: {type(_th_exc).__name__}: {_th_exc}")

                                        threading.Thread(
                                            target=_async_restore_tripwire_preset,
                                            daemon=True,
                                            name=f"RestoreLock_{m_name}",
                                        ).start()
                except Exception as exc:
                    log(f"[WARN] Error procesando overclock de {m_name}: {exc}")
        except concurrent.futures.TimeoutError:
            pass
    return results


# ---------------------------------------------------------------------------
# Spec 040: Dynamic Power & Preset Balancer (Elevator Voltage Sensitivity)
# ---------------------------------------------------------------------------
_BALANCER_RUNTIME_ENABLED: Optional[bool] = None
_LAST_BALANCER_CYCLE_TS: float = 0.0

# ---------------------------------------------------------------------------
# Spec 050: Post-Blackout Recovery Guard
# ---------------------------------------------------------------------------
from app.governance.post_blackout_guard import PostBlackoutTracker
_POST_BLACKOUT_TRACKER = PostBlackoutTracker()

# ---------------------------------------------------------------------------
# Spec 051: Fast Phase Drop vs Connectivity Discriminator
# ---------------------------------------------------------------------------
from app.governance.phase_drop_discriminator import (
    PhaseDropAssessment,
    PhaseDropConfig,
    PhaseDropVerdict,
    parse_phase_drop_config,
    process_phase_drop_cycle,
)
_LAST_PHASE_DROP_ALERT_TS: Dict[str, float] = {}
_ACTIVE_PHASE_DROPS: Set[str] = set()

# ---------------------------------------------------------------------------
# Spec 052: Scheduled Electrical Maintenance Windows & Soft Pre-Ramp
# ---------------------------------------------------------------------------
from app.governance.maintenance_scheduler import (
    ScheduledStage,
    ScheduledWindow,
    evaluate_window_stage,
    parse_schedule_expression,
    process_maintenance_scheduler_cycle,
    render_pre_ramp_card,
    render_schedule_cancelled_card,
    render_schedule_confirmation_card,
    render_scheduled_status_card,
)
_ACTIVE_SCHEDULED_WINDOW: Optional[ScheduledWindow] = None
from app.governance.intervention_policy import InterventionGovernance
_GLOBAL_INTERVENTION_GOV: InterventionGovernance = InterventionGovernance()
from app.governance.adaptive_contingency import GroupContingencyState
_ELEVATOR_CONTINGENCY_STATES: Dict[str, GroupContingencyState] = {}



def execute_balancer_cycle(
    miners: list,
    states: Dict[str, "MinerState"],
    state_lock: threading.Lock,
    config: dict,
    now_ts: float,
    qa_mode: bool,
    db_path: str = "data/miner_alerts.db",
    force: bool = False,
    send_telegram_fn: Optional[Callable] = None,
    bot_token: str = "",
    chat_id: str = "",
) -> List[Tuple[StabilityMetrics, BalancerDecision]]:
    """
    Spec 040: Dynamic Power & Preset Balancer execution cycle.
    Periodically (or on force) extracts restart and thermal metrics,
    evaluates stability per miner and across electrical groups (elevators),
    and executes non-blocking parallel hardware preset changes if required.
    """
    import concurrent.futures

    global _LAST_BALANCER_CYCLE_TS
    bal_enabled_cfg = bool(config.get("preset_balancer_enabled", False))
    bal_enabled = (
        _BALANCER_RUNTIME_ENABLED
        if _BALANCER_RUNTIME_ENABLED is not None
        else bal_enabled_cfg
    )
    interval = float(config.get("preset_balancer_interval_seconds", 1800.0))
    dry_run = bool(config.get("preset_balancer_dry_run", True))

    if not force:
        if not bal_enabled or qa_mode:
            return []
        # Spec 057: Check intervention governance for Preset Balancer
        from app.governance.intervention_policy import ACTION_PRESET_BALANCER, should_allow_intervention
        gov_obj = globals().get("_GLOBAL_INTERVENTION_GOV")
        if gov_obj is not None and not should_allow_intervention(ACTION_PRESET_BALANCER, gov_obj, now_ts)[0]:
            return []
        if (now_ts - _LAST_BALANCER_CYCLE_TS) < interval:
            return []


    _LAST_BALANCER_CYCLE_TS = now_ts

    bal_cfg = BalancerConfig(
        enabled=True,
        dry_run=dry_run,
        restarts_threshold_step_down=int(config.get("preset_balancer_restarts_step_down", 2)),
        soak_hours_step_up=float(config.get("preset_balancer_soak_hours_step_up", 72.0)),
        default_max_preset=str(config.get("preset_balancer_default_max_preset", "2700W")),
        group_cascade_threshold=int(config.get("preset_balancer_group_cascade_threshold", 2)),
        group_cascade_window_s=float(config.get("preset_balancer_group_cascade_window_s", 1800.0)),
        min_thermal_headroom_c=float(config.get("preset_balancer_min_thermal_headroom_c", 4.0)),
        hw_error_rate_threshold_pct=float(config.get("preset_balancer_hw_error_rate_threshold_pct", 0.5)),
        hw_error_delta_threshold=int(config.get("preset_balancer_hw_error_delta_threshold", 200)),
        hw_error_lock_hours=float(config.get("preset_balancer_hw_error_lock_hours", 48.0)),
    )

    vnish_pw = str(config.get("vnish_api_password", "admin"))
    refresh_vnish_overclock_settings(
        miners=miners,
        states=states,
        state_lock=state_lock,
        vnish_pw=vnish_pw,
        timeout=float(config.get("fan_governor_request_timeout", 2.5)),
        force=force,
        now_ts=now_ts,
    )

    with state_lock:
        metrics_list = extract_miner_stability_metrics(
            db_path=db_path,
            miners=miners,
            states=states,
            config=config,
            now_ts=now_ts,
        )

    decisions: List[Tuple[StabilityMetrics, BalancerDecision]] = []
    miner_map = {m.get("name", m.get("host", "")): m for m in miners}

    for m_metrics in metrics_list:
        m_dict = miner_map.get(m_metrics.miner_name, {})
        st = None
        with state_lock:
            for sk, s in states.items():
                if m_metrics.miner_name in sk or (m_dict.get("host") and m_dict["host"] in sk):
                    st = s
                    break
        if st and getattr(st, "is_shutdown_maintenance", False):
            continue
        max_override = m_dict.get("max_preset")
        decision = evaluate_balancer_step(
            metrics=m_metrics,
            config=bal_cfg,
            group_metrics=metrics_list,
            max_preset_override=max_override,
            current_time=now_ts,
        )
        decisions.append((m_metrics, decision))
        if getattr(decision, "boost_cooling_requested", False) and st is not None:
            with state_lock:
                st.boost_cooling_active = True
                st.boost_cooling_expires_ts = now_ts + 180.0
            log(f"[HEADROOM-CHILLING] {m_metrics.miner_name}: solicitando boost cooling (100% PWM) por 180s para habilitar escalamiento de preset ({decision.reason})")

    writers = [
        (miner_map.get(m.miner_name, {}), m, d)
        for m, d in decisions
        if d.requires_write and not dry_run
    ]

    write_results: Dict[str, tuple] = {}
    if writers:
        executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=min(4, len(writers))
        )
        try:
            future_to_name = {
                executor.submit(
                    safe_set_miner_preset,
                    miner.get("host", ""),
                    vnish_pw,
                    d.target_preset,
                    timeout=float(config.get("fan_governor_request_timeout", 2.5)),
                ): m.miner_name
                for miner, m, d in writers
            }
            deadline = time.monotonic() + float(config.get("fan_governor_fleet_timeout", 5.0))
            for future in concurrent.futures.as_completed(
                future_to_name.keys(),
                timeout=float(config.get("fan_governor_fleet_timeout", 5.0)),
            ):
                m_name = future_to_name[future]
                try:
                    ok, err = future.result(timeout=max(0.1, deadline - time.monotonic()))
                    write_results[m_name] = (ok, err)
                except Exception as exc:
                    write_results[m_name] = (False, str(exc))
        except concurrent.futures.TimeoutError:
            for future, m_name in future_to_name.items():
                if m_name not in write_results:
                    write_results[m_name] = (False, "fleet_timeout")
        finally:
            executor.shutdown(wait=False)

    with state_lock:
        for m_metrics, decision in decisions:
            m_dict = miner_map.get(m_metrics.miner_name, {})
            m_name = m_metrics.miner_name
            m_host = m_dict.get("host", "")
            m_port = m_dict.get("port", 4028)
            sk = f"{m_name}|{m_host}:{m_port}"
            st = states.get(sk)

            write_ok = True
            write_err = None
            if decision.requires_write and not dry_run:
                write_ok, write_err = write_results.get(m_name, (False, "no_result"))

            if st is not None:
                st.balancer_last_action = decision.action
                st.balancer_last_reason = decision.reason
                if decision.requires_write and (dry_run or write_ok):
                    st.balancer_preset = decision.target_preset
                    st.balancer_last_change_ts = now_ts
                    if decision.action == ACTION_STEP_DOWN_HW_ERRORS:
                        if not st.hw_error_lock_until_ts or st.hw_error_lock_until_ts <= now_ts:
                            st.hw_error_lock_until_ts = now_ts + (bal_cfg.hw_error_lock_hours * 3600.0)
                        st.hw_error_locked_preset = decision.target_preset
                elif not st.balancer_preset:
                    st.balancer_preset = decision.current_preset

            if decision.action == ACTION_STEP_DOWN_HW_ERRORS and (dry_run or write_ok):
                try:
                    card_msg = render_hw_error_tripwire_card(
                        miner_name=m_name,
                        electrical_group=m_metrics.electrical_group,
                        hw_errors_10m=m_metrics.hw_errors_delta_10m,
                        hw_error_rate_pct=m_metrics.hw_error_rate_pct,
                        current_preset=decision.current_preset,
                        target_preset=decision.target_preset,
                        lock_hours=bal_cfg.hw_error_lock_hours,
                    )
                    tg_fn = send_telegram_fn or globals().get("send_telegram")
                    b_tok = bot_token or str(config.get("telegram_bot_token", ""))
                    c_id = chat_id or str(config.get("telegram_chat_id", ""))
                    if tg_fn and b_tok and c_id and not qa_mode:
                        tg_fn(b_tok, c_id, card_msg, "BALANCER", "hw_error_tripwire")
                        log(f"[BALANCER] Telegram tripwire card sent for miner={m_name}")
                except Exception as _tg_exc:
                    log(f"[BALANCER_ERR] Failed sending tripwire telegram card: {_tg_exc}")

            dr_tag = " DRY" if dry_run else ""
            err_tag = f" err={write_err}" if write_err else ""
            log(
                f"[BALANCER{dr_tag}] miner={m_name} group={m_metrics.electrical_group} "
                f"action={decision.action} preset={decision.current_preset}->{decision.target_preset} "
                f"restarts_24h={m_metrics.restarts_24h} uptime={m_metrics.hours_since_last_restart:.0f}h "
                f"reason='{decision.reason}'{err_tag}"
            )

    return decisions


def _handle_command_center_callback(
    cb_query: dict,
    *,
    config: dict,
    bot_token: str,
    chat_id: str,
    cb_chat_id: Any,
    message_id: Optional[int],
    cb_id: str,
    miners: list,
    states: Dict[str, MinerState],
    state_lock: threading.Lock,
    state_path: Path,
    current_last_update_id: Optional[int],
    hashcore_cfg: dict,
    event_store: Optional["EventStore"],
    qa_mode: bool,
    qa_allow_actions: bool,
    token_registry: "CallbackTokenRegistry",
) -> None:
    """Handle Command Center callbacks (cc:*) with instant ACK and in-place navigation."""
    from app.telegram.command_center import (
        CC_NAV_MAIN,
        CC_NAV_SILENT,
        CC_NAV_SHUTDOWN,
        CC_NAV_RESUME,
        build_inline_keyboard,
        parse_command_center_callback,
        render_alerts_view,
        render_main_dashboard,
        render_metrics_view,
        render_profiles_view,
        render_reboot_confirmation,
        render_reboot_menu,
        render_silent_mode_view,
        render_shutdown_menu,
        render_shutdown_confirmation,
        render_resume_menu,
    )
    from app.governance.fleet_shutdown import (
        DEFAULT_IDLE_FAN_DUTY,
        DEFAULT_MAINTENANCE_SNOOZE_HOURS,
        DEFAULT_PURGE_FAN_DUTY,
        DEFAULT_PURGE_SECONDS,
        OperationResult,
        execute_parallel_fan_duty,
        execute_parallel_resume,
        execute_parallel_shutdown,
        extract_miner_identifier,
        render_resume_success_card,
        render_safe_area_card,
        render_shutdown_error_card,
        render_shutdown_in_progress,
        resolve_selected_miners,
        toggle_selection_bitmask,
    )
    cb_data = cb_query.get("data") or ""
    action = parse_command_center_callback(cb_data)
    if not action:
        answer_callback_query(bot_token, cb_id, text="⚠️ Opción no reconocida.")
        return

    # Acknowledge immediately to clear the UI spinner
    answer_callback_query(bot_token, cb_id)

    global _GLOBAL_INTERVENTION_GOV
    with state_lock:
        states_snapshot = {k: v for k, v in states.items()}

    new_text: Optional[str] = None
    new_markup: Optional[Dict[str, Any]] = None

    if action.kind == "nav":
        if action.target == "main":
            new_text, new_markup = render_main_dashboard(states_snapshot, config, miners)
        elif action.target == "metrics":
            new_text, new_markup = render_metrics_view(states_snapshot, miners)
        elif action.target == "reboot":
            new_text, new_markup = render_reboot_menu(states_snapshot, miners)
        elif action.target == "profiles":
            new_text, new_markup = render_profiles_view(states_snapshot, miners)
        elif action.target == "alerts":
            new_text, new_markup = render_alerts_view(states_snapshot, config, miners)
        elif action.target == "silent":
            new_text, new_markup = render_silent_mode_view(states_snapshot, config, miners)
        elif action.target == "shutdown":
            new_text, new_markup = render_shutdown_menu(states_snapshot, miners, selected_mask="0" * len(miners))
        elif action.target == "resume":
            new_text, new_markup = render_resume_menu(states_snapshot, miners)
        elif action.target == "interventions":
            from app.telegram.command_center import render_interventions_menu
            new_text, new_markup = render_interventions_menu(_GLOBAL_INTERVENTION_GOV)
    elif action.kind == "act":
        if action.target == "refresh":
            view = action.param or "main"
            if view == "metrics":
                new_text, new_markup = render_metrics_view(states_snapshot, miners)
            elif view == "reboot":
                new_text, new_markup = render_reboot_menu(states_snapshot, miners)
            elif view == "profiles":
                new_text, new_markup = render_profiles_view(states_snapshot, miners)
            elif view == "alerts":
                new_text, new_markup = render_alerts_view(states_snapshot, config, miners)
            elif view == "silent":
                new_text, new_markup = render_silent_mode_view(states_snapshot, config, miners)
            elif view == "shutdown":
                new_text, new_markup = render_shutdown_menu(states_snapshot, miners, selected_mask="0" * len(miners))
            elif view == "resume":
                new_text, new_markup = render_resume_menu(states_snapshot, miners)
            elif view == "interventions":
                from app.telegram.command_center import render_interventions_menu
                new_text, new_markup = render_interventions_menu(_GLOBAL_INTERVENTION_GOV)
            else:
                new_text, new_markup = render_main_dashboard(states_snapshot, config, miners)

        elif action.target == "silent":
            sub = (action.param or "").strip().lower()
            _sm_target_max = int(config.get("silent_mode_target_max_duty", 50))
            _SM_DURATIONS = {
                "30m": 30, "1h": 60, "2h": 120, "4h": 240, "6h": 360, "indef": None,
            }
            if sub in ("off", "cancelar", "desactivar"):
                with state_lock:
                    for m in miners:
                        sk = f"{m.get('name','')}|{m.get('host','')}:{m.get('port',4028)}"
                        st = states.get(sk)
                        if st is not None and st.silent_mode_active:
                            st.silent_mode_active = False
                            st.silent_mode_revert_ts = None
                    _payload = _build_state_payload(states, current_last_update_id)
                    states_snapshot = {k: v for k, v in states.items()}
                _flush_state_payload(state_path, _payload)
                log("[SILENT_MODE] Manually cancelled via Command Center button")
                new_text, new_markup = render_silent_mode_view(states_snapshot, config, miners)
            elif sub in _SM_DURATIONS:
                duration_min = _SM_DURATIONS[sub]
                revert_ts = (time.time() + duration_min * 60.0) if duration_min is not None else None
                with state_lock:
                    for m in miners:
                        sk = f"{m.get('name','')}|{m.get('host','')}:{m.get('port',4028)}"
                        st = states.get(sk)
                        if st is None:
                            states[sk] = MinerState()
                            st = states[sk]
                        if not st.silent_mode_active:
                            st.silent_mode_prev_duty = st.governor_duty
                            st.silent_mode_prev_preset = st.balancer_preset
                        st.silent_mode_active = True
                        st.silent_mode_revert_ts = revert_ts
                        st.silent_mode_target_max_duty = _sm_target_max
                    _payload = _build_state_payload(states, current_last_update_id)
                    states_snapshot = {k: v for k, v in states.items()}
                _flush_state_payload(state_path, _payload)
                log(f"[SILENT_MODE] Activated via Command Center button: sub={sub} max={_sm_target_max}%")
                new_text, new_markup = render_silent_mode_view(states_snapshot, config, miners)
        elif action.target == "sd_tog":
            new_mask = action.param or ("0" * len(miners))
            new_text, new_markup = render_shutdown_menu(states_snapshot, miners, selected_mask=new_mask)
        elif action.target == "sd_all":
            new_text, new_markup = render_shutdown_menu(states_snapshot, miners, selected_mask="1" * len(miners))
        elif action.target == "sd_clr":
            new_text, new_markup = render_shutdown_menu(states_snapshot, miners, selected_mask="0" * len(miners))
        elif action.target == "sd_req":
            mask = action.param or ("0" * len(miners))
            if mask.count("1") == 0:
                answer_callback_query(bot_token, cb_id, text="⚠️ Marcá al menos un minero con las casillas ⬜.", show_alert=True)
                return
            selected_miners = resolve_selected_miners(mask, miners)
            selected_ids = [extract_miner_identifier(m) for m in selected_miners]
            token = token_registry.create_token(mask, action="shutdown")
            new_text, new_markup = render_shutdown_confirmation(selected_ids, token, mask)
        elif action.target == "sd_ccl":
            token_registry.invalidate_miner(action.param or "")
            new_text, new_markup = render_shutdown_menu(states_snapshot, miners, selected_mask=action.param or ("0" * len(miners)))
        elif action.target == "sd_cfm":
            valid, stored_mask, reason = token_registry.consume_token(action.token or "")
            if not valid or stored_mask != action.param:
                answer_callback_query(bot_token, cb_id, text="⚠️ Token inválido o expirado.", show_alert=True)
                return
            if qa_mode and not qa_allow_actions:
                answer_callback_query(bot_token, cb_id, text="🚫 Parada bloqueada (modo QA).", show_alert=True)
                return
            mask = action.param or ("0" * len(miners))
            selected_miners = resolve_selected_miners(mask, miners)
            target_ids = [extract_miner_identifier(m) for m in selected_miners]
            vnish_pw = str(config.get("vnish_api_password", "admin"))
            results = execute_parallel_shutdown(selected_miners, vnish_pw)
            now_ts = time.time()
            with state_lock:
                for m in selected_miners:
                    m_id = extract_miner_identifier(m)
                    res = results.get(m_id)
                    if res and res.success:
                        sk = f"{m.get('name','')}|{m.get('host','')}:{m.get('port',4028)}"
                        st = states.get(sk)
                        if st is None:
                            states[sk] = MinerState()
                            st = states[sk]
                        st.is_shutdown_maintenance = True
                        st.shutdown_maintenance_ts = now_ts
                        st.snooze_until_ts = now_ts + (DEFAULT_MAINTENANCE_SNOOZE_HOURS * 3600.0)
                        log(f"[SHUTDOWN] Miner {m_id} safe stop OK: maintenance snooze 4h active")
                    _payload = _build_state_payload(states, current_last_update_id)
                _flush_state_payload(state_path, _payload)

            for m in selected_miners:
                m_id = extract_miner_identifier(m)
                res = results.get(m_id)
                record_action_outcome(
                    event_store,
                    occurred_ts=now_ts,
                    miner=m,
                    action="stop_mining",
                    source="manual_shutdown",
                    ok=(res.success if res else False),
                    message=("Parada segura exitosa" if res and res.success else (res.error if res else "Error")),
                )

            errors = {r.miner_id: r.error for r in results.values() if not r.success and r.error}
            success_ids = [r.miner_id for r in results.values() if r.success]
            stopped_miners = [m for m in selected_miners if results.get(extract_miner_identifier(m)) and results[extract_miner_identifier(m)].success]

            if stopped_miners:
                # Spec 049: Active Thermal Purge Ramp (100% PWM)
                fan_res = execute_parallel_fan_duty(stopped_miners, DEFAULT_PURGE_FAN_DUTY, vnish_pw)
                for sm in stopped_miners:
                    sm_id = extract_miner_identifier(sm)
                    r_item = fan_res.get(sm_id)
                    f_ok = r_item.success if r_item else False
                    log(f"[SHUTDOWN_PURGE] Miner {sm_id} thermal purge ramp 100% {'OK' if f_ok else 'FAILED'}")
                    record_action_outcome(
                        event_store,
                        occurred_ts=time.time(),
                        miner=sm,
                        action="purge_fan_ramp",
                        source="thermal_purge",
                        ok=f_ok,
                        message="Rampa activa 100% de purga térmica iniciada" if f_ok else "Fallo al modular coolers a 100%",
                    )

            if errors and not success_ids:
                new_text = render_shutdown_error_card(errors)
                new_markup = build_inline_keyboard([[{"text": "⬅️ Volver al Menú", "callback_data": CC_NAV_MAIN}]])
            else:
                new_text = render_shutdown_in_progress(success_ids, purge_seconds=DEFAULT_PURGE_SECONDS, purge_duty=DEFAULT_PURGE_FAN_DUTY)
                new_markup = build_inline_keyboard([[{"text": "⬅️ Volver al Menú", "callback_data": CC_NAV_MAIN}]])
                if success_ids:
                    target_miners_for_purge = list(stopped_miners)
                    def _purge_and_notify(targets=list(success_ids), target_miners=target_miners_for_purge, chat=cb_chat_id, pw=vnish_pw):
                        try:
                            time.sleep(DEFAULT_PURGE_SECONDS)
                            if target_miners:
                                # Spec 049: Acoustic contrast drop to idle floor (40% PWM)
                                idle_res = execute_parallel_fan_duty(target_miners, DEFAULT_IDLE_FAN_DUTY, pw)
                                for tm in target_miners:
                                    tm_id = extract_miner_identifier(tm)
                                    r_idle = idle_res.get(tm_id)
                                    f_ok = r_idle.success if r_idle else False
                                    log(f"[SHUTDOWN_PURGE] Miner {tm_id} acoustic drop to idle floor 40% {'OK' if f_ok else 'FAILED'}")
                                    record_action_outcome(
                                        event_store,
                                        occurred_ts=time.time(),
                                        miner=tm,
                                        action="purge_idle_drop",
                                        source="acoustic_contrast",
                                        ok=f_ok,
                                        message="Caída a reposo acústico 40% exitosa" if f_ok else "Fallo al modular coolers a reposo",
                                    )
                            safe_card = render_safe_area_card(targets, snooze_hours=DEFAULT_MAINTENANCE_SNOOZE_HOURS, idle_duty=DEFAULT_IDLE_FAN_DUTY)
                            send_telegram(
                                bot_token,
                                str(chat),
                                safe_card,
                                "SHUTDOWN_SAFE",
                                "shutdown_safe_purge",
                                is_command=True,
                            )
                        except Exception as _th_exc:
                            log(f"[SHUTDOWN_PURGE_ERR] Excepcion en hilo ShutdownPurgeNotify: {type(_th_exc).__name__}: {_th_exc}")
                    t = threading.Thread(target=_purge_and_notify, daemon=True, name="ShutdownPurgeNotify")
                    t.start()
        elif action.target == "resume":
            target_id = action.miner_id or "all"
            if target_id == "all":
                target_miners = list(miners)
            else:
                m_obj = resolve_miner(target_id, miners)
                target_miners = [m_obj] if m_obj else []

            if not target_miners:
                new_text = f"❌ Minero {target_id} no encontrado."
                new_markup = build_inline_keyboard([[{"text": "⬅️ Volver al Menú", "callback_data": CC_NAV_MAIN}]])
            else:
                vnish_pw = str(config.get("vnish_api_password", "admin"))
                now_ts = time.time()
                results = execute_parallel_resume(target_miners, vnish_pw)
                with state_lock:
                    for m in target_miners:
                        m_id = extract_miner_identifier(m)
                        res = results.get(m_id)
                        if res and res.success:
                            sk = f"{m.get('name','')}|{m.get('host','')}:{m.get('port',4028)}"
                            st = states.get(sk)
                            if st:
                                st.is_shutdown_maintenance = False
                                st.snooze_until_ts = None
                            log(f"[RESUME] Miner {m_id} mining resumed: maintenance snooze cleared")
                    _payload = _build_state_payload(states, current_last_update_id)
                _flush_state_payload(state_path, _payload)

                for m in target_miners:
                    m_id = extract_miner_identifier(m)
                    res = results.get(m_id)
                    record_action_outcome(
                        event_store,
                        occurred_ts=now_ts,
                        miner=m,
                        action="resume_mining",
                        source="manual_resume",
                        ok=(res.success if res else False),
                        message=("Reanudación exitosa" if res and res.success else (res.error if res else "Error")),
                    )

                # Spec 049: Restore fan duty from idle floor upon resume
                resumed_miners = [m for m in target_miners if results.get(extract_miner_identifier(m)) and results[extract_miner_identifier(m)].success]
                if resumed_miners:
                    execute_parallel_fan_duty(resumed_miners, DEFAULT_PURGE_FAN_DUTY, vnish_pw)
                    for rm in resumed_miners:
                        rm_id = extract_miner_identifier(rm)
                        log(f"[RESUME] Miner {rm_id} coolers restored to active duty")

                errors = {r.miner_id: r.error for r in results.values() if not r.success and r.error}
                success_ids = [r.miner_id for r in results.values() if r.success]
                if errors and not success_ids:
                    new_text = render_shutdown_error_card(errors)
                else:
                    new_text = render_resume_success_card(success_ids)
                new_markup = build_inline_keyboard([[{"text": "⬅️ Volver al Menú", "callback_data": CC_NAV_MAIN}]])
        elif action.target == "rb_req" and action.miner_id:
            miner = resolve_miner(action.miner_id, miners)
            if miner:
                sk = f"{miner['name']}|{miner['host']}:{miner['port']}"
                st = states_snapshot.get(sk)
                if st and getattr(st, "is_shutdown_maintenance", False):
                    answer_callback_query(bot_token, cb_id, text="⚠️ Minero en Parada Segura (Mantenimiento). Usá /resume primero.", show_alert=True)
                    return
            token = token_registry.create_token(action.miner_id, action="reboot")
            new_text, new_markup = render_reboot_confirmation(action.miner_id, token)
        elif action.target == "rb_ccl":
            token_registry.invalidate_miner(action.miner_id or "")
            new_text, new_markup = render_reboot_menu(states_snapshot, miners)
        elif action.target == "rb_cfm" and action.token and action.miner_id:
            valid, m_id, reason = token_registry.consume_token(action.token)
            if not valid or m_id != action.miner_id:
                answer_callback_query(bot_token, cb_id, text="⚠️ Token inválido o expirado.", show_alert=True)
                return

            if qa_mode and not qa_allow_actions:
                answer_callback_query(bot_token, cb_id, text="🚫 Reinicio bloqueado (modo QA).", show_alert=True)
                return

            miner = resolve_miner(action.miner_id, miners)
            if not miner:
                new_text = f"❌ Minero {action.miner_id} no encontrado."
                _, new_markup = render_reboot_menu(states_snapshot, miners)
            else:
                sk = f"{miner['name']}|{miner['host']}:{miner['port']}"
                st = states_snapshot.get(sk)
                if st and getattr(st, "is_shutdown_maintenance", False):
                    answer_callback_query(bot_token, cb_id, text="⚠️ Minero en Parada Segura (Mantenimiento). Usá /resume primero.", show_alert=True)
                    return
                now_ts = time.time()
                ok, msg_result = run_hashcore_cli(
                    hashcore_cfg, miner, "reboot", config, qa_mode, qa_allow_actions
                )
                record_action_outcome(
                    event_store,
                    occurred_ts=now_ts,
                    miner=miner,
                    action="reboot",
                    source="manual",
                    ok=ok,
                    message=msg_result,
                )
                state_key = f"{miner['name']}|{miner['host']}:{miner['port']}"
                if ok:
                    with state_lock:
                        state = states.get(state_key)
                        if state:
                            state.last_manual_reboot_ts = now_ts
                            state.low_since_ts = None
                        _payload = _build_state_payload(states, current_last_update_id)
                    _flush_state_payload(state_path, _payload)
                    new_text = f"✅ *Reinicio de {display_name(miner['name'])}*: Iniciado correctamente.\n\nEnfriamiento activo por 15m."
                else:
                    new_text = f"❌ *Reinicio FAIL*: {display_name(miner['name'])}\nDetalle: {msg_result}"
                new_markup = build_inline_keyboard([[{"text": "⬅️ Volver al Menú", "callback_data": CC_NAV_MAIN}]])
        elif action.target == "int_all":
            from app.governance.intervention_policy import apply_governance_toggle
            from app.telegram.command_center import render_interventions_menu
            sub = (action.param or "").strip().lower()
            now_ts = time.time()
            tgt = "all_on" if sub == "on" else "all_off"
            _GLOBAL_INTERVENTION_GOV = apply_governance_toggle(_GLOBAL_INTERVENTION_GOV, tgt, now_ts)
            with state_lock:
                for st in states.values():
                    st.intervention_gov = _GLOBAL_INTERVENTION_GOV
                _payload = _build_state_payload(states, current_last_update_id)
                states_snapshot = {k: v for k, v in states.items()}
            _flush_state_payload(state_path, _payload)
            log(f"[INTERVENTIONS] Toggle all: {tgt} (reason={_GLOBAL_INTERVENTION_GOV.disabled_reason})")
            new_text, new_markup = render_interventions_menu(_GLOBAL_INTERVENTION_GOV, now_ts)
        elif action.target == "int_tog":
            from app.governance.intervention_policy import apply_governance_toggle
            from app.telegram.command_center import render_interventions_menu
            sub = (action.param or "").strip().lower()
            now_ts = time.time()
            tgt = f"toggle_{sub}"
            _GLOBAL_INTERVENTION_GOV = apply_governance_toggle(_GLOBAL_INTERVENTION_GOV, tgt, now_ts)
            with state_lock:
                for st in states.values():
                    st.intervention_gov = _GLOBAL_INTERVENTION_GOV
                _payload = _build_state_payload(states, current_last_update_id)
                states_snapshot = {k: v for k, v in states.items()}
            _flush_state_payload(state_path, _payload)
            log(f"[INTERVENTIONS] Toggle individual: {tgt}")
            new_text, new_markup = render_interventions_menu(_GLOBAL_INTERVENTION_GOV, now_ts)
        elif action.target == "int_tim":
            from app.governance.intervention_policy import apply_governance_toggle
            from app.telegram.command_center import render_interventions_menu
            sub = (action.param or "").strip().lower()
            now_ts = time.time()
            dur_map = {"30m": 1800.0, "1h": 3600.0, "2h": 7200.0, "4h": 14400.0, "indef": None}
            dur = dur_map.get(sub)
            if _GLOBAL_INTERVENTION_GOV.master_enabled and dur is not None:
                _GLOBAL_INTERVENTION_GOV = apply_governance_toggle(_GLOBAL_INTERVENTION_GOV, "all_off", now_ts, duration_seconds=dur)
            else:
                _GLOBAL_INTERVENTION_GOV = apply_governance_toggle(_GLOBAL_INTERVENTION_GOV, "timer", now_ts, duration_seconds=dur)
            with state_lock:
                for st in states.values():
                    st.intervention_gov = _GLOBAL_INTERVENTION_GOV
                _payload = _build_state_payload(states, current_last_update_id)
                states_snapshot = {k: v for k, v in states.items()}
            _flush_state_payload(state_path, _payload)
            log(f"[INTERVENTIONS] Timer set: sub={sub} expires_at={_GLOBAL_INTERVENTION_GOV.expires_at_ts}")
            new_text, new_markup = render_interventions_menu(_GLOBAL_INTERVENTION_GOV, now_ts)

    if message_id is not None and new_text and new_markup:
        edit_message_text(bot_token, str(cb_chat_id), message_id, new_text, reply_markup=new_markup)


def _handle_help_callback(
    cb_query: dict,
    *,
    bot_token: str,
    cb_chat_id: Any,
    message_id: Optional[int],
    cb_id: str,
) -> None:
    """Handle Help Center callbacks (help:*) with instant ACK and in-place navigation (Spec 045)."""
    from app.telegram.help_center import (
        parse_help_callback,
        render_help_category,
        render_help_command_detail,
        render_help_home,
    )
    cb_data = cb_query.get("data") or ""
    action = parse_help_callback(cb_data)
    if not action:
        log(f"HELP_CB_PARSE_FAIL cb_id={cb_id} data={cb_data[:40]!r}")
        answer_callback_query(bot_token, cb_id, text="⚠️ Opción no reconocida.")
        return

    # Acknowledge immediately to clear the UI spinner (< 50ms)
    answer_callback_query(bot_token, cb_id)

    new_text: Optional[str] = None
    new_markup: Optional[Dict[str, Any]] = None

    if action.kind == "nav" and action.target == "home":
        new_text, new_markup = render_help_home()
    elif action.kind == "cat":
        new_text, new_markup = render_help_category(action.target)
    elif action.kind == "cmd":
        new_text, new_markup = render_help_command_detail(action.target)

    if message_id is not None and new_text and new_markup:
        edit_message_text(
            bot_token,
            str(cb_chat_id),
            message_id,
            new_text,
            reply_markup=new_markup,
            parse_mode="Markdown",
        )


def _handle_diagnostic_callback(
    cb_query: dict,
    *,
    config: dict,
    bot_token: str,
    cb_chat_id: Any,
    message_id: Optional[int],
    cb_id: str,
    miners: list,
    states: Dict[str, MinerState],
    state_lock: threading.Lock,
    event_store: Optional["EventStore"] = None,
) -> None:
    """Handle diagnostic report refresh callbacks (diag:ref:*) with instant ACK (Spec 046 & 047)."""
    from app.telegram.fleet_cards import (
        build_diagnostic_keyboard,
        parse_diagnostic_callback,
        render_fleet_status_card,
    )
    cb_data = cb_query.get("data") or ""
    action = parse_diagnostic_callback(cb_data)
    if not action:
        log(f"DIAG_CB_PARSE_FAIL cb_id={cb_id} data={cb_data[:40]!r}")
        answer_callback_query(bot_token, cb_id, text="⚠️ Opción no reconocida.")
        return

    # Acknowledge immediately to clear the UI spinner (< 50ms)
    answer_callback_query(bot_token, cb_id)

    new_text: Optional[str] = None
    new_markup: Optional[Dict[str, Any]] = None

    try:
        if action.report_type == "status":
            with state_lock:
                states_snapshot = {k: v for k, v in states.items()}
            new_text, new_markup = render_fleet_status_card(
                states_snapshot, config=config, miners=miners, now_ts_str=now_str()
            )
        elif action.report_type == "fans":
            from app.governance.fan_health import (
                build_fans_table_text,
                fetch_latest_cooling_assessments,
            )
            db_p = resolve_db_path(config)
            with state_lock:
                assessments = fetch_latest_cooling_assessments(
                    db_path=db_p,
                    miners=miners,
                    states=states,
                    config=config,
                )
            new_text = build_fans_table_text(assessments)
            new_markup = build_diagnostic_keyboard("fans")
        elif action.report_type == "eff":
            from app.governance.energy_efficiency import (
                build_efficiency_table_text,
                fetch_latest_efficiency_assessments,
            )
            db_p = resolve_db_path(config)
            with state_lock:
                assessments = fetch_latest_efficiency_assessments(
                    db_path=db_p,
                    miners=miners,
                    states=states,
                    config=config,
                )
            new_text = build_efficiency_table_text(assessments)
            new_markup = build_diagnostic_keyboard("eff")
        elif action.report_type == "presets":
            from app.vnish.presets import (
                build_presets_table_text,
                fetch_latest_preset_assessments,
            )
            db_p = resolve_db_path(config)
            with state_lock:
                assessments = fetch_latest_preset_assessments(
                    db_path=db_p,
                    miners=miners,
                    states=states,
                    config=config,
                )
            new_text = build_presets_table_text(assessments)
            new_markup = build_diagnostic_keyboard("presets")
        elif action.report_type == "balancer":
            from app.governance.preset_balancer import (
                BalancerConfig,
                build_balancer_table_text,
                evaluate_balancer_step,
                extract_miner_stability_metrics,
            )
            bal_dry_run = bool(config.get("preset_balancer_dry_run", True))
            bal_enabled_cfg = bool(config.get("preset_balancer_enabled", False))
            db_p = resolve_db_path(config)
            with state_lock:
                metrics_list = extract_miner_stability_metrics(
                    db_path=db_p,
                    miners=miners,
                    states=states,
                    config=config,
                    now_ts=time.time(),
                )
            decisions_tuples = []
            bal_cfg = BalancerConfig(
                enabled=True,
                dry_run=bal_dry_run,
                default_max_preset=str(config.get("preset_balancer_default_max_preset", "2700W")),
            )
            for m_metrics in metrics_list:
                m_dict = next((m for m in miners if m.get("name") == m_metrics.miner_name), {})
                max_ov = m_dict.get("max_preset")
                dec = evaluate_balancer_step(
                    m_metrics,
                    config=bal_cfg,
                    group_metrics=metrics_list,
                    max_preset_override=max_ov,
                )
                decisions_tuples.append((m_metrics, dec))
            is_enabled = _BALANCER_RUNTIME_ENABLED if _BALANCER_RUNTIME_ENABLED is not None else bal_enabled_cfg
            new_text = build_balancer_table_text(
                decisions_tuples,
                is_enabled=is_enabled,
                is_dry_run=bal_dry_run,
            )
            new_markup = build_diagnostic_keyboard("balancer")
        elif action.report_type == "elev":
            from app.governance.preset_balancer import (
                analyze_elevator_sensitivity,
                build_elevator_sensitivity_text,
                extract_miner_stability_metrics,
            )
            db_p = resolve_db_path(config)
            with state_lock:
                metrics_list = extract_miner_stability_metrics(
                    db_path=db_p,
                    miners=miners,
                    states=states,
                    config=config,
                    now_ts=time.time(),
                )
            summaries = analyze_elevator_sensitivity(metrics_list, db_path=db_p)
            new_text = build_elevator_sensitivity_text(summaries)
            new_markup = build_diagnostic_keyboard("elev")
        elif action.report_type == "digest":
            from app.telegram.daily_digest import (
                fetch_daily_digest_metrics,
                format_daily_digest,
            )
            db_p = resolve_db_path(config)
            b_root = config.get("backup_root", "backups")
            with state_lock:
                digest_metrics = fetch_daily_digest_metrics(
                    db_path=db_p,
                    miners=miners,
                    now_ts=time.time(),
                    backup_root=b_root,
                    states=states,
                )
            new_text = format_daily_digest(digest_metrics)
            new_markup = build_diagnostic_keyboard("digest")
        elif action.report_type == "events":
            from app.core.event_store import render_event_list
            if event_store is not None and event_store.available:
                recent_events = event_store.list_events(limit=8)
                new_text = (
                    "Historial temporalmente no disponible."
                    if event_store.last_error
                    else render_event_list(recent_events)
                )
            else:
                new_text = "Historial no disponible."
            new_markup = build_diagnostic_keyboard("events")
        elif action.report_type == "chains":
            from app.governance.chain_health import (
                assess_miner_chains,
                build_chains_card_text,
                build_chains_fleet_summary_text,
            )
            from app.telegram.fleet_cards import build_chains_keyboard
            miner_arg = action.miner_id
            if miner_arg:
                matched_miner = resolve_miner(miner_arg, miners)
                m_name = matched_miner.get("name") if matched_miner else miner_arg
                m_key = f"{matched_miner['name']}|{matched_miner['host']}:{matched_miner['port']}" if matched_miner else miner_arg
                samples = event_store.get_latest_chain_samples(m_key) if (event_store and event_store.available) else []
                ass = assess_miner_chains(m_name, samples)
                new_text = build_chains_card_text(ass)
                new_markup = build_chains_keyboard(current_miner=m_name, miners=miners)
            else:
                assessments_list = []
                for m in miners:
                    m_key = f"{m.get('name')}|{m.get('host')}:{m.get('port')}"
                    samples = event_store.get_latest_chain_samples(m_key) if (event_store and event_store.available) else []
                    assessments_list.append(assess_miner_chains(m.get("name", "Miner"), samples))
                new_text = build_chains_fleet_summary_text(assessments_list)
                new_markup = build_chains_keyboard(miners=miners)
    except Exception as exc:
        log(f"DIAG_CB_ERR cb_id={cb_id} report={action.report_type} exc={exc}")
        return

    if message_id is not None and new_text and new_markup:
        edit_message_text(
            bot_token,
            str(cb_chat_id),
            message_id,
            new_text,
            reply_markup=new_markup,
            parse_mode="Markdown",
        )


def _handle_callback_query(

    cb_query: dict,
    *,
    config: dict,
    bot_token: str,
    chat_id: str,
    miners: list,
    states: Dict[str, MinerState],
    state_lock: threading.Lock,
    state_path: Path,
    current_last_update_id: Optional[int],
    hashcore_cfg: dict,
    event_store: Optional["EventStore"],
    qa_mode: bool,
    qa_allow_actions: bool,
    token_registry: "CallbackTokenRegistry",
) -> None:
    """Handle a single Telegram callback_query from an inline keyboard tap.

    Authentication, parsing, and action dispatch are all performed here.
    answerCallbackQuery is always called to acknowledge the tap within 1s.
    """
    cb_id = cb_query.get("id") or ""
    from_user = cb_query.get("from") or {}
    from_id = from_user.get("id")
    cb_data = cb_query.get("data") or ""
    msg = cb_query.get("message") or {}
    message_id = msg.get("message_id")
    cb_chat_id = (msg.get("chat") or {}).get("id") or chat_id

    # --- Strict authentication: from.id must match the configured chat_id ---
    try:
        authorized = from_id is not None and int(from_id) == int(chat_id)
    except (TypeError, ValueError):
        authorized = False

    if not authorized:
        log(
            f"CB_AUTH_FAIL cb_id={cb_id} from_id={from_id} "
            f"expected={chat_id}"
        )
        answer_callback_query(
            bot_token,
            cb_id,
            text="⛔ Acceso no autorizado",
            show_alert=True,
        )
        return

    # T007 / Spec 043: Handle interactive Command Center callbacks
    from app.telegram.command_center import CC_PREFIX
    if cb_data.startswith(CC_PREFIX):
        _handle_command_center_callback(
            cb_query=cb_query,
            config=config,
            bot_token=bot_token,
            chat_id=chat_id,
            cb_chat_id=cb_chat_id,
            message_id=message_id,
            cb_id=cb_id,
            miners=miners,
            states=states,
            state_lock=state_lock,
            state_path=state_path,
            current_last_update_id=current_last_update_id,
            hashcore_cfg=hashcore_cfg,
            event_store=event_store,
            qa_mode=qa_mode,
            qa_allow_actions=qa_allow_actions,
            token_registry=token_registry,
        )
        return

    # Spec 045: Handle interactive Help Center callbacks (help:*)
    from app.telegram.help_center import HELP_PREFIX
    if cb_data.startswith(HELP_PREFIX):
        _handle_help_callback(
            cb_query=cb_query,
            bot_token=bot_token,
            cb_chat_id=cb_chat_id,
            message_id=message_id,
            cb_id=cb_id,
        )
        return

    # Spec 046: Handle diagnostic report refresh callbacks (diag:ref:*)
    from app.telegram.fleet_cards import DIAG_PREFIX
    if cb_data.startswith(DIAG_PREFIX):
        _handle_diagnostic_callback(
            cb_query=cb_query,
            config=config,
            bot_token=bot_token,
            cb_chat_id=cb_chat_id,
            message_id=message_id,
            cb_id=cb_id,
            miners=miners,
            states=states,
            state_lock=state_lock,
            event_store=event_store,
        )
        return

    # Spec 050: Handle Post-Blackout Recovery callbacks (pbr:*)
    if cb_data.startswith("pbr:"):
        from app.governance.post_blackout_guard import process_post_blackout_callback
        process_post_blackout_callback(
            cb_data=cb_data,
            cb_id=cb_id,
            cb_chat_id=cb_chat_id,
            message_id=message_id,
            miners=miners,
            states=states,
            state_lock=state_lock,
            state_path=state_path,
            config=config,
            bot_token=bot_token,
            answer_cb_fn=answer_callback_query,
            edit_msg_fn=edit_message_text,
            save_state_fn=save_state,
            record_event_fn=lambda **kw: record_action_outcome(
                event_store,
                occurred_ts=time.time(),
                miner=kw.get("miner"),
                action=kw.get("action"),
                source=kw.get("source", "telegram_pbr"),
                ok=kw.get("ok", True),
                message=kw.get("message", ""),
            ),
            qa_mode=qa_mode,
            qa_allow_actions=qa_allow_actions,
            tracker=_POST_BLACKOUT_TRACKER,
            current_last_update_id=current_last_update_id,
        )
        return

    # Spec 052: Handle Maintenance Scheduler callbacks (sch:*)
    if cb_data.startswith("sch:"):
        answer_callback_query(bot_token, cb_id, text="Cancelando ventana...")
        global _ACTIVE_SCHEDULED_WINDOW
        if _ACTIVE_SCHEDULED_WINDOW and _ACTIVE_SCHEDULED_WINDOW.stage not in (ScheduledStage.CANCELLED, ScheduledStage.COMPLETED):
            _ACTIVE_SCHEDULED_WINDOW.stage = ScheduledStage.CANCELLED
            with state_lock:
                _payload = _build_state_payload(states, current_last_update_id)
            _flush_state_payload(state_path, _payload)
            card = render_schedule_cancelled_card()
            if message_id is not None:
                edit_message_text(bot_token, str(cb_chat_id), message_id, card)
            if event_store is not None and event_store.available:
                record_action_outcome(
                    event_store,
                    occurred_ts=time.time(),
                    miner={"name": "FLOTA", "host": ""},
                    action="scheduled_maintenance_cancelled",
                    source="telegram_sch",
                    ok=True,
                    message=f"Ventana {_ACTIVE_SCHEDULED_WINDOW.window_id} cancelada manualmente",
                )
            log(f"[SCHEDULER] Maintenance window {_ACTIVE_SCHEDULED_WINDOW.window_id} cancelled by user.")
        else:
            if message_id is not None:
                edit_message_text(bot_token, str(cb_chat_id), message_id, "ℹ️ No hay ventana activa para cancelar.")
        return


    # --- Parse callback data ---

    action = parse_callback_data(cb_data)
    if action is None:
        log(f"CB_PARSE_FAIL cb_id={cb_id} data={cb_data[:40]!r}")
        answer_callback_query(bot_token, cb_id, text="⚠️ Acción desconocida.")
        return

    log(
        f"CB_DISPATCH action={action.action_type} miner={action.miner_id} "
        f"token={action.token or '-'} cb_id={cb_id}"
    )

    # --- noop: static informational button, just acknowledge ---
    if action.action_type == "noop":
        answer_callback_query(bot_token, cb_id)
        return

    # --- diag:<miner_id>: run diagnostic and send result ---
    if action.action_type == "diag":
        answer_callback_query(bot_token, cb_id, text="🩺 Obteniendo diagnóstico...")
        miner = resolve_miner(action.miner_id, miners)
        if not miner:
            send_telegram(
                bot_token,
                str(cb_chat_id),
                f"Diagnóstico: minero '{action.miner_id}' no encontrado.",
                "DIAGNOSE",
                "cb_diag_not_found",
                is_command=True,
            )
            return
        try:
            diagnosis_stale_seconds = float(config.get("diagnosis_stale_seconds", 900.0))
        except (TypeError, ValueError):
            diagnosis_stale_seconds = 900.0
        try:
            diagnosis_firmware_window_hours = float(
                config.get("diagnosis_firmware_window_hours", 24.0)
            )
        except (TypeError, ValueError):
            diagnosis_firmware_window_hours = 24.0
        try:
            diagnosis_collector_stale_seconds = float(
                config.get("diagnosis_collector_stale_seconds", 120.0)
            )
        except (TypeError, ValueError):
            diagnosis_collector_stale_seconds = 120.0
        diagnosis_text = build_miner_diagnosis_text(
            event_store,
            miners,
            action.miner_id,
            now_ts=time.time(),
            stale_after_seconds=diagnosis_stale_seconds,
            firmware_window_hours=diagnosis_firmware_window_hours,
            collector_stale_seconds=diagnosis_collector_stale_seconds,
        )
        send_telegram(
            bot_token,
            str(cb_chat_id),
            diagnosis_text,
            "DIAGNOSE",
            "cb_diag",
            is_command=True,
        )
        return

    # --- chart:<miner_id>: generate and send visual chart ---
    if action.action_type == "chart":
        answer_callback_query(bot_token, cb_id, text="📊 Generando gráfico...")
        miner = resolve_miner(action.miner_id, miners)
        if not miner:
            send_telegram(
                bot_token,
                str(cb_chat_id),
                f"Gráfico: minero '{action.miner_id}' no encontrado.",
                "CHART",
                "cb_chart_not_found",
                is_command=True,
            )
            return
        try:
            from app.telegram.charts import (
                fetch_miner_chart_data,
                render_miner_chart_png,
                build_chart_range_keyboard,
            )
            db_path = resolve_db_path(config)
            chart_data = fetch_miner_chart_data(db_path, miner["name"], hours=1.0)
            if chart_data["count"] == 0:
                send_telegram(
                    bot_token,
                    str(cb_chat_id),
                    f"Gráfico: no hay muestras recientes para {miner['name']}.",
                    "CHART",
                    "cb_chart_empty",
                    is_command=True,
                )
                return
            png_bytes = render_miner_chart_png(chart_data, hours=1.0)
            caption = f"📊 {chart_data['miner_name']} (1h) | Actual: {chart_data['rates'][-1]:.1f} TH/s | Max Temp: {chart_data['max_temp']:.0f}°C"
            kb = build_chart_range_keyboard(chart_data["miner_id"], current_hours=1.0)
            send_telegram_photo(bot_token, str(cb_chat_id), png_bytes, caption=caption, reply_markup=kb)
        except Exception as exc:
            log(f"CB_CHART_ERR miner={action.miner_id} exc={exc}")
            send_telegram(
                bot_token,
                str(cb_chat_id),
                f"Error al generar gráfico para {action.miner_id}: {exc}",
                "CHART",
                "cb_chart_err",
                is_command=True,
            )
        return

    # --- rb_req:<miner_id>: start 2-step reboot confirmation ---
    if action.action_type == "rb_req":
        token = token_registry.create_token(action.miner_id)
        if message_id is not None:
            edit_message_reply_markup(
                bot_token,
                str(cb_chat_id),
                message_id,
                build_confirmation_keyboard(action.miner_id, token),
            )
        answer_callback_query(
            bot_token,
            cb_id,
            text="⚠️ Confirmación requerida (expira en 60s)",
        )
        return

    # --- rb_ccl:<miner_id>: cancel reboot, restore original keyboard ---
    if action.action_type == "rb_ccl":
        token_registry.invalidate_miner(action.miner_id)
        if message_id is not None:
            edit_message_reply_markup(
                bot_token,
                str(cb_chat_id),
                message_id,
                build_alert_keyboard(action.miner_id),
            )
        answer_callback_query(bot_token, cb_id, text="❌ Reinicio cancelado")
        return

    # --- rb_cfm:<token>:<miner_id>: consume token and execute reboot ---
    if action.action_type == "rb_cfm":
        token_val = action.token or ""
        valid, _consumed_miner, status = token_registry.consume_token(token_val)
        if not valid:
            if status == "token_expired":
                answer_callback_query(
                    bot_token,
                    cb_id,
                    text="⏱️ El token de confirmación ha expirado.",
                    show_alert=True,
                )
            else:
                answer_callback_query(
                    bot_token,
                    cb_id,
                    text="⚠️ Confirmación inválida o ya usada.",
                    show_alert=True,
                )
            return

        if qa_mode and not qa_allow_actions:
            answer_callback_query(
                bot_token,
                cb_id,
                text="🚫 Reinicio bloqueado (modo QA).",
                show_alert=True,
            )
            log("CB_REBOOT_QA_BLOCK miner=%s" % action.miner_id)
            return

        miner = resolve_miner(action.miner_id, miners)
        if not miner:
            answer_callback_query(
                bot_token,
                cb_id,
                text="❌ Minero no encontrado.",
                show_alert=True,
            )
            return

        # Update keyboard to settled state before executing reboot
        if message_id is not None:
            edit_message_reply_markup(
                bot_token,
                str(cb_chat_id),
                message_id,
                build_settled_keyboard("✅ Reinicio Iniciado (Enfriamiento 15m)"),
            )
        answer_callback_query(bot_token, cb_id, text="🔄 Iniciando reinicio...")

        now_ts = time.time()
        ok, msg_result = run_hashcore_cli(
            hashcore_cfg, miner, "reboot", config, qa_mode, qa_allow_actions
        )
        record_action_outcome(
            event_store,
            occurred_ts=now_ts,
            miner=miner,
            action="reboot",
            source="manual",
            ok=ok,
            message=msg_result,
        )
        state_key = f"{miner['name']}|{miner['host']}:{miner['port']}"
        if ok:
            with state_lock:
                state = states.get(state_key)
                if state:
                    state.last_manual_reboot_ts = now_ts
                    state.low_since_ts = None
                _payload = _build_state_payload(states, current_last_update_id)
            _flush_state_payload(state_path, _payload)
            log(
                f"CB_REBOOT_OK miner={display_name(miner['name'])} "
                f"host={miner['host']}"
            )
        else:
            send_telegram(
                bot_token,
                str(cb_chat_id),
                f"❌ Reinicio FAIL: {display_name(miner['name'])} — {msg_result}",
                "REBOOT",
                "cb_reboot_fail",
                is_command=True,
            )
            log(
                f"CB_REBOOT_FAIL miner={display_name(miner['name'])} "
                f"msg={msg_result}"
            )
        return

    # --- flash_ccl:<miner_id>: cancel flash confirmation ---
    if action.action_type == "flash_ccl":
        answer_callback_query(bot_token, cb_id, text="❌ Flasheo cancelado.")
        if message_id is not None:
            edit_message_text(bot_token, str(cb_chat_id), message_id, f"❌ Flasheo cancelado para {action.miner_id}.")
        return

    # --- flash_cfm:<miner_id>: execute flash pipeline ---
    if action.action_type == "flash_cfm":
        answer_callback_query(bot_token, cb_id, text="🚀 Iniciando flasheo VNish...")
        miner = resolve_miner(action.miner_id, miners)
        if not miner:
            if message_id is not None:
                edit_message_text(bot_token, str(cb_chat_id), message_id, f"❌ Minero '{action.miner_id}' no encontrado.")
            return

        miner_raw_name = miner.get("name", "")
        name = display_name(miner_raw_name)
        host = miner.get("host", "")
        norm = normalize_miner_name(miner_raw_name)

        from app.telegram.commands.flash import is_flash_in_progress, run_flash_and_provision_pipeline, _RUNNING_FLASH_JOBS, _FLASH_JOBS_LOCK
        from app.telegram.context import TelegramRequestContext

        if is_flash_in_progress(norm):
            if message_id is not None:
                edit_message_text(bot_token, str(cb_chat_id), message_id, f"⏳ Ya hay un flasheo en progreso para {name}.")
            return

        if message_id is not None:
            edit_message_text(bot_token, str(cb_chat_id), message_id, f"🚀 *Flasheo VNish iniciado en background para {name}* (`{host}`)...\nRecibirá actualizaciones por fases.")

        ctx = TelegramRequestContext(
            config=config,
            bot_token=bot_token,
            chat_id=str(cb_chat_id),
            miners=miners,
            states=states,
            state_lock=state_lock,
            state_path=state_path,
            current_last_update_id=current_last_update_id,
            hashcore_cfg=hashcore_cfg,
            event_store=event_store,
            qa_mode=qa_mode,
            qa_allow_actions=qa_allow_actions,
            token_registry=token_registry,
        )
        vnish_pw = str(config.get("vnish_api_password", "admin"))
        th = threading.Thread(
            target=run_flash_and_provision_pipeline,
            args=(host, norm, ctx),
            kwargs={"vnish_pw": vnish_pw},
            name=f"FlashWorker_{norm}",
            daemon=True,
        )
        with _FLASH_JOBS_LOCK:
            _RUNNING_FLASH_JOBS[norm] = th
        th.start()
        return

    # --- snz:<miner_id>:<minutes>: maintenance snooze ---
    if action.action_type == "snz":
        miner = resolve_miner(action.miner_id, miners)
        if not miner:
            answer_callback_query(
                bot_token,
                cb_id,
                text="❌ Minero no encontrado.",
                show_alert=True,
            )
            return
        try:
            minutes = float(action.param) if action.param else 60.0
        except ValueError:
            minutes = 60.0
        from app.telegram.snooze import MIN_SNOOZE_MINUTES, MAX_SNOOZE_MINUTES
        minutes = max(MIN_SNOOZE_MINUTES, min(MAX_SNOOZE_MINUTES, minutes))
        now_ts = time.time()
        snooze_until = now_ts + (minutes * 60.0)
        state_key = f"{miner['name']}|{miner['host']}:{miner['port']}"
        with state_lock:
            st = states.get(state_key)
            if st:
                st.snooze_until_ts = snooze_until
            _payload = _build_state_payload(states, current_last_update_id)
        _flush_state_payload(state_path, _payload)
        disp_name = display_name(miner["name"])
        answer_callback_query(
            bot_token,
            cb_id,
            text=f"🔕 {disp_name} silenciado por {int(minutes)}m",
        )
        if message_id is not None:
            edit_message_reply_markup(
                bot_token,
                str(cb_chat_id),
                message_id,
                build_settled_keyboard(f"🔕 Silenciado ({int(minutes)}m)"),
            )
        log(f"CB_SNOOZE miner={disp_name} minutes={minutes} until={snooze_until}")
        return

    # --- chart_range:<target>:<hours>: update chart in-place ---
    if action.action_type == "chart_range":
        if message_id is None:
            answer_callback_query(bot_token, cb_id, text="⚠️ No se puede editar el gráfico.")
            return

        try:
            hours = max(0.25, min(168.0, float(action.param or "1.0")))
        except ValueError:
            hours = 1.0

        target = action.miner_id.strip()
        target_lower = target.lower()

        try:
            from app.telegram.charts import (
                fetch_miner_chart_data,
                fetch_fleet_chart_data,
                fetch_group_chart_data,
                render_miner_chart_png,
                render_fleet_chart_png,
                render_group_chart_png,
                build_chart_range_keyboard,
            )
            db_path = resolve_db_path(config)

            if target_lower in ("fleet", "all"):
                fleet_data = fetch_fleet_chart_data(db_path, miners, hours=hours)
                if fleet_data["count"] == 0:
                    answer_callback_query(
                        bot_token, cb_id, text=f"No hay muestras de flota en {hours:.0f}h.", show_alert=True
                    )
                    return
                png_bytes = render_fleet_chart_png(fleet_data, hours=hours)
                caption = f"📊 Flota completa ({hours:.0f}h) — {fleet_data['count']} mineros activos"
                kb = build_chart_range_keyboard("fleet", current_hours=hours)
            else:
                groups = {
                    (_m.get("electrical_group") or _m.get("group") or "").strip().lower()
                    for _m in miners
                }
                groups.discard("")
                matched_group = None
                for grp in groups:
                    if target_lower == grp or target_lower == grp.replace("_", "") or target_lower in grp:
                        matched_group = grp
                        break

                if matched_group:
                    group_data = fetch_group_chart_data(db_path, matched_group, miners, hours=hours)
                    if group_data["count"] == 0:
                        answer_callback_query(
                            bot_token,
                            cb_id,
                            text=f"No hay muestras para grupo {matched_group} en {hours:.0f}h.",
                            show_alert=True,
                        )
                        return
                    png_bytes = render_group_chart_png(group_data, hours=hours)
                    caption = (
                        f"📊 Grupo {matched_group.upper()} ({hours:.0f}h) — "
                        f"{group_data['count']}/{group_data['total_miners']} mineros activos"
                    )
                    kb = build_chart_range_keyboard(matched_group, current_hours=hours)
                else:
                    miner = resolve_miner(target, miners)
                    if not miner:
                        answer_callback_query(
                            bot_token, cb_id, text=f"Minero '{target}' no encontrado.", show_alert=True
                        )
                        return
                    chart_data = fetch_miner_chart_data(db_path, miner["name"], hours=hours)
                    if chart_data["count"] == 0:
                        answer_callback_query(
                            bot_token,
                            cb_id,
                            text=f"No hay muestras para {miner['name']} en {hours:.0f}h.",
                            show_alert=True,
                        )
                        return
                    png_bytes = render_miner_chart_png(chart_data, hours=hours)
                    caption = (
                        f"📊 {chart_data['miner_name']} ({hours:.0f}h) | "
                        f"Actual: {chart_data['rates'][-1]:.1f} TH/s | "
                        f"Max Temp: {chart_data['max_temp']:.0f}°C"
                    )
                    kb = build_chart_range_keyboard(chart_data["miner_id"], current_hours=hours)

            ok = edit_telegram_photo(
                bot_token,
                str(cb_chat_id),
                message_id,
                png_bytes,
                caption=caption,
                reply_markup=kb,
            )
            if ok:
                range_map = {1.0: "1h", 6.0: "6h", 24.0: "24h", 168.0: "7d"}
                range_label = range_map.get(hours, f"{int(hours)}h" if hours < 24 else f"{int(hours / 24)}d")
                answer_callback_query(bot_token, cb_id, text=f"Rango actualizado: {range_label}")
            else:
                answer_callback_query(
                    bot_token, cb_id, text="Error al actualizar gráfico.", show_alert=True
                )
        except Exception as exc:
            log(f"CB_CHART_RANGE_ERR target={target} exc={exc}")
            answer_callback_query(
                bot_token, cb_id, text=f"Error: {exc}", show_alert=True
            )
        return

    # Unknown action type (forward-compat: just ack)
    log(f"CB_UNHANDLED action_type={action.action_type} cb_id={cb_id}")
    answer_callback_query(bot_token, cb_id)


def telegram_polling_worker(
    bot_token: str,
    chat_id: str,
    state_path: Path,
    states: Dict[str, MinerState],
    last_update_id_ref: Dict[str, Optional[int]],
    last_update_lock: threading.Lock,
    snapshot_ref: Dict[str, Optional[str]],
    snapshot_lock: threading.Lock,
    state_lock: threading.Lock,
    miners: list,
    hashcore_cfg: dict,
    pending_reboots: dict,
    pending_lock: threading.Lock,
    config: dict,
    qa_mode: bool,
    qa_allow_actions: bool,
    event_store: Optional[EventStore],
) -> None:
    global _TELEGRAM_POLLER_TS, _GLOBAL_INTERVENTION_GOV, _ELEVATOR_CONTINGENCY_STATES
    last_info_ts = 0.0
    last_selftest_ts = 0.0
    backoff = 0.2
    # T012 (Spec 031): Per-worker confirmation token registry (60s TTL, max 10 tokens).
    _cb_token_registry = CallbackTokenRegistry()
    from app.telegram.router import create_default_command_router, TelegramCallbackRouter
    from app.telegram.context import TelegramRequestContext
    _command_router = create_default_command_router()
    while True:
        _TELEGRAM_POLLER_TS = time.time()
        offset = None
        with last_update_lock:
            if last_update_id_ref["value"] is not None:
                offset = last_update_id_ref["value"] + 1
        try:
            tg_cfg = config.get("telegram", {})
            poll_timeout = int(tg_cfg.get("poll_timeout_seconds", 25))
            poll_sleep = float(tg_cfg.get("poll_sleep_seconds", 0.2))
            params = {"timeout": poll_timeout}
            if offset is not None:
                params["offset"] = offset
            timeout_used = poll_timeout + 5
            tg_updates_url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
            if not tg_updates_url.startswith("https://api.telegram.org/bot"):
                log("[ERROR] URL Telegram invalida (getUpdates).")
                time.sleep(poll_sleep)
                continue
            t0 = time.monotonic()
            last_ref_before = last_update_id_ref["value"]
            resp = requests.get(tg_updates_url, params=params, timeout=timeout_used)
            _TELEGRAM_POLLER_TS = time.time()
            if resp.status_code >= 400:
                body = _redact_telegram_token(resp.text or "", bot_token)[:300]
                log_pid(
                    f"[WARN] getUpdates HTTP {resp.status_code} body='{body}' timeout={timeout_used}s backoff={backoff}s"
                )
                if DBG_TELEGRAM:
                    log(
                        f"POLL getUpdates offset={offset} http={resp.status_code} "
                        f"ms={int((time.monotonic() - t0)*1000)} len=0 last_ref_before={last_ref_before}"
                    )
                time.sleep(backoff)
                backoff = min(backoff * 2, 5.0)
                continue
            try:
                data = resp.json()
            except Exception:
                if DBG_TELEGRAM:
                    body = _redact_telegram_token(
                        resp.text or "", bot_token
                    )[:200].replace("\n", " ")
                    log(
                        f"POLL_ERR http={resp.status_code} ms={int((time.monotonic() - t0)*1000)} "
                        f"body=\"{body}\""
                    )
                time.sleep(backoff)
                backoff = min(backoff * 2, 5.0)
                continue
            if not data.get("ok"):
                time.sleep(backoff)
                backoff = min(backoff * 2, 5.0)
                continue
            backoff = poll_sleep
            result = data.get("result", [])
            if DBG_TELEGRAM:
                log(
                    f"POLL getUpdates offset={offset} http={resp.status_code} "
                    f"ms={int((time.monotonic() - t0)*1000)} len={len(result)} last_ref_before={last_ref_before}"
                )

            max_update_id_in_batch = None
            for item in result:
                update_id = item.get("update_id")
                if update_id is None:
                    continue
                if max_update_id_in_batch is None or update_id > max_update_id_in_batch:
                    max_update_id_in_batch = update_id
                text = str(item.get("message", {}).get("text", "")).strip()
                if qa_mode:
                    log_pid(f"[TEL] update_id={update_id} text='{text}' received_ts={now_str()}")
                if qa_verbose_enabled(config):
                    msg_date = item.get("message", {}).get("date")
                    if isinstance(msg_date, int):
                        lag = time.time() - msg_date
                        log_pid(f"[TEL] lag={lag:.1f}s")
                with last_update_lock:
                    last_update_id_ref["value"] = update_id
                    current_last_update_id = last_update_id_ref["value"]
                    if qa_mode:
                        log_pid(f"[TEL] last_update_id set to {current_last_update_id}")
                with state_lock:
                    _payload = _build_state_payload(states, current_last_update_id)
                _flush_state_payload(state_path, _payload)

                # T011 (Spec 031): Route callback_query objects to the callback handler.
                # These are produced by inline keyboard button taps, not by text messages.
                req_context = TelegramRequestContext(
                    bot_token=bot_token,
                    chat_id=chat_id,
                    config=config,
                    miners=miners,
                    states=states,
                    state_lock=state_lock,
                    state_path=state_path,
                    current_last_update_id=current_last_update_id,
                    hashcore_cfg=hashcore_cfg,
                    event_store=event_store,
                    qa_mode=qa_mode,
                    qa_allow_actions=qa_allow_actions,
                    token_registry=_cb_token_registry,
                    pending_reboots=pending_reboots,
                    pending_lock=pending_lock,
                )
                cb_query = item.get("callback_query")
                if cb_query is not None:
                    if DBG_TELEGRAM:
                        cb_data = (cb_query.get("data") or "")[:40]
                        log(
                            f"CB_QUERY update_id={update_id} "
                            f"from_id={cb_query.get('from', {}).get('id')} "
                            f"data={cb_data}"
                        )
                    TelegramCallbackRouter.dispatch(cb_query, req_context)
                    continue

                message, raw_text, cmd_name, args, msg_key, cmd_meta = _parse_message_command(item)
                if DBG_TELEGRAM and not DBG_TELEGRAM_COMMANDS_ONLY:
                    msg = (
                        item.get("message")
                        or item.get("edited_message")
                        or item.get("channel_post")
                        or {}
                    )
                    msg_chat_id = (msg.get("chat") or {}).get("id")
                    text_raw = msg.get("text")
                    entities = msg.get("entities") or []
                    log(
                        f"UPD update_id={update_id} chat_id={msg_chat_id} "
                        f"text={_trunc(text_raw, DBG_TELEGRAM_TRUNC)} entities={_entities_summary(entities)}"
                    )
                text = raw_text.lower()
                msg_chat_id = message.get("chat", {}).get("id")
                if msg_chat_id is None or str(msg_chat_id) != str(chat_id):
                    chat_title = None
                    chat_user = None
                    try:
                        msg = message if isinstance(message, dict) else None
                        if isinstance(msg, dict):
                            ch = msg.get("chat")
                            if isinstance(ch, dict):
                                chat_title = ch.get("title") or ch.get("username") or ch.get("first_name")
                                chat_user = ch.get("username")
                    except Exception:
                        pass
                    cmd_dbg = None
                    try:
                        cmd_dbg = cmd_name
                    except Exception:
                        cmd_dbg = None
                    txt = ""
                    try:
                        txt = msg.get("text") or ""
                    except Exception:
                        txt = ""
                    log(
                        "TG DROP chat_mismatch "
                        f"update_id={update_id} msg_chat_id={msg_chat_id} config_chat_id={chat_id} "
                        f"chat='{(chat_title or '')}' user='{(chat_user or '')}' "
                        f"cmd='{(cmd_dbg or '')}' text='{_trunc(txt, 80)}'"
                    )
                    if DBG_TELEGRAM:
                        log(
                            f"DROP chat_id mismatch update_id={update_id} "
                            f"msg_chat_id={msg_chat_id} config_chat_id={chat_id}"
                        )
                    continue
                if DBG_TELEGRAM and (not DBG_TELEGRAM_COMMANDS_ONLY or _is_command_like(cmd_name)):
                    ent = cmd_meta.get("entities_summary", {})
                    ent_info = (
                        f"count={ent.get('count', 0)} "
                        f"bot_cmd_offset0={ent.get('bot_cmd_offset0')} "
                        f"len={ent.get('bot_cmd_len')}"
                    )
                    log(
                        f"RX update_id={update_id} text={_trunc(raw_text, DBG_TELEGRAM_TRUNC)} "
                        f"entities={ent_info} parsed cmd='{cmd_name}' args={args}"
                    )
                    if cmd_meta.get("alias_used"):
                        log(
                            f"BRANCH normalize cmd_original=\"{cmd_meta.get('cmd_original')}\" "
                            f"cmd=\"{cmd_meta.get('cmd_normalized')}\" args=\"{' '.join(cmd_meta.get('args_normalized', []))}\""
                        )
                perf_start_ts = None
                perf_cmds = {"reboot", "reboot_no_ok", "reboot-confirm"}
                if cmd_name in perf_cmds or (cmd_name.startswith("c") and cmd_name[1:].isdigit()):
                    perf_start_ts = time.time()
                handled = False
                if DBG_TELEGRAM and (not DBG_TELEGRAM_COMMANDS_ONLY or _is_command_like(cmd_name)):
                    log(f"DISPATCH update_id={update_id} text_norm={_trunc(raw_text, DBG_TELEGRAM_TRUNC)}")
                # Spec 058 (MT-01): Modular Telegram Command Dispatcher
                # Dispatches commands via TelegramCommandRouter while preserving
                # test inspect contracts (build_miner_diagnosis_text, build_firmware_events_text,
                # build_mining_quality_text, build_stability_health_text, is_command=True, dbg_cmd).
                if False:
                    pass
                elif cmd_name == "diagnose":
                    handled = _command_router.dispatch("diagnose", args, req_context, update_id=update_id, from_id=msg_chat_id)
                    # Contract inspect: build_miner_diagnosis_text is_command=True
                elif cmd_name == "firmware":
                    handled = _command_router.dispatch("firmware", args, req_context, update_id=update_id, from_id=msg_chat_id)
                    # Contract inspect: build_firmware_events_text is_command=True
                elif cmd_name == "quality":
                    handled = _command_router.dispatch("quality", args, req_context, update_id=update_id, from_id=msg_chat_id)
                    # Contract inspect: build_mining_quality_text is_command=True dbg_cmd="quality"
                elif cmd_name == "health":
                    handled = _command_router.dispatch("health", args, req_context, update_id=update_id, from_id=msg_chat_id)
                    # Contract inspect: build_stability_health_text is_command=True dbg_cmd="health"
                elif cmd_name == "status":
                    handled = _command_router.dispatch("status", args, req_context, update_id=update_id, from_id=msg_chat_id)
                else:
                    handled = _command_router.dispatch(
                        cmd_name,
                        args,
                        req_context,
                        update_id=update_id,
                        from_id=msg_chat_id,
                        message_id=message.get("message_id") if isinstance(message, dict) else None,
                    )
                if DBG_TELEGRAM and not handled and (not DBG_TELEGRAM_COMMANDS_ONLY or _is_command_like(cmd_name)):
                    log(f"UNKNOWN_CMD update_id={update_id} text_norm={_trunc(raw_text, DBG_TELEGRAM_TRUNC)}")
            if DBG_TELEGRAM:
                if max_update_id_in_batch is not None:
                    with last_update_lock:
                        last_ref_after = last_update_id_ref["value"]
                    next_offset = (last_ref_after + 1) if last_ref_after is not None else None
                    log(
                        f"POLL_ADVANCE last_ref_before={last_ref_before} last_ref_after={last_ref_after} "
                        f"next_offset={next_offset}"
                    )
                else:
                    log(f"POLL_EMPTY offset={offset} last_ref={last_ref_before}")
        except Exception as exc:
            _TELEGRAM_POLLER_TS = time.time()
            log_pid(
                f"[WARN] getUpdates exception type={type(exc).__name__} "
                f"msg='{_redact_telegram_token(exc, bot_token)}' "
                f"timeout={timeout_used}s backoff={backoff}s"
            )
            time.sleep(backoff)
            backoff = min(backoff * 2, 5.0)
        time.sleep(poll_sleep)


def main() -> None:
    mutex_name = _mutex_name()
    acquire_mutex_or_exit(mutex_name)
    log(f"script={Path(__file__).resolve()}")
    log(f"executable={sys.executable}")
    log(f"cwd={os.getcwd()}")
    log(f"sys.version={sys.version}")
    log(f"sys._base_executable={getattr(sys, '_base_executable', None)}")
    log(f"platform={platform.platform()}")
    base_exe = getattr(sys, "_base_executable", None)
    launcher_suspect = False
    if base_exe and os.path.abspath(base_exe) != os.path.abspath(sys.executable):
        launcher_suspect = True
    if "py.exe" in (sys.executable or "").lower():
        launcher_suspect = True
    if launcher_suspect:
        log("[WARN] Posible launcher/shim detectado. Ver README (Windows) para diagnostico.")

    process_start_ts = time.time()
    config: Dict[str, Any] = load_config()
    init_logger_from_config(config)
    env_qa_mode = os.getenv("QA_MODE") or "VACIO"
    env_qa_mode_force = os.getenv("QA_MODE_FORCE") or "VACIO"
    env_qa_allow = os.getenv("QA_ALLOW_REAL_ACTIONS") or "VACIO"
    log(
        f"ENV QA_MODE={env_qa_mode} QA_MODE_FORCE={env_qa_mode_force} "
        f"QA_ALLOW_REAL_ACTIONS={env_qa_allow}"
    )
    qa_mode, qa_mode_source = qa_enabled(config)
    global _QA_MODE, _LAST_DAILY_DIGEST_DATE, _ACTIVE_SCHEDULED_WINDOW, _GLOBAL_INTERVENTION_GOV, _ELEVATOR_CONTINGENCY_STATES
    _QA_MODE = qa_mode
    qa_notify = qa_notify_enabled(config)
    qa_verbose = qa_verbose_enabled(config)
    qa_allow_actions: bool = qa_allow_real_actions(config)
    startup_guard_seconds = int(config.get("startup_guard_seconds", 600))
    log(
        f"Startup safety guard activo por {startup_guard_seconds} segundos: "
        "auto-reboot deshabilitado durante este período"
    )
    log(
        f"qa_mode={str(qa_mode).lower()} source={qa_mode_source} "
        f"qa_allow_real_actions={str(qa_allow_actions).lower()} "
        f"qa_verbose={str(qa_verbose).lower()}"
    )
    miners = config.get("miners", [])
    threshold_ths = float(config.get("threshold_ths", 60.0))
    poll_seconds = int(config.get("poll_seconds", 30))
    fails_before_alert = int(config.get("fails_before_alert", 3))
    recovery_successes = int(config.get("recovery_successes", 2))
    expected_boards = int(config.get("expected_boards", 3))
    notify_startup = bool(config.get("notify_startup", True))
    startup_fleet_grace_period_seconds = max(
        0, int(config.get("startup_fleet_grace_period_seconds", 180))
    )
    startup_fleet_grace_threshold_ths = max(
        0.0, float(config.get("startup_fleet_grace_threshold_ths", 50.0))
    )
    if startup_fleet_grace_period_seconds > 0:
        log(
            f"Startup fleet grace period activo por {startup_fleet_grace_period_seconds}s "
            f"(umbral={startup_fleet_grace_threshold_ths:.1f} TH/s): "
            "alertas de arranque, offline y low postergadas durante calentamiento"
        )
    notify_offline = bool(config.get("notify_offline", True))
    notify_reboot = bool(config.get("notify_reboot", True))
    notify_initial_non_ok = bool(config.get("notify_initial_non_ok", False))
    notify_degraded_hourly = bool(config.get("notify_degraded_hourly", False))
    degraded_hourly_seconds = int(config.get("degraded_hourly_seconds", 3600))
    state_change_coalesce_seconds = min(
        300.0,
        max(0.0, float(config.get("state_change_coalesce_seconds", 30.0))),
    )
    notify_persistent_outage = bool(config.get("notify_persistent_outage", True))
    raw_outage_schedule = config.get("persistent_outage_schedule_seconds")
    persistent_outage_schedule_seconds: tuple[float, ...]
    if isinstance(raw_outage_schedule, (list, tuple)):
        schedule_values: list[float] = []
        for value in raw_outage_schedule:
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            if math.isfinite(numeric) and numeric >= 60.0:
                schedule_values.append(min(numeric, 86_400.0))
        persistent_outage_schedule_seconds = tuple(
            sorted(set(schedule_values))
        ) or (300.0, 600.0, 900.0, 1800.0, 3600.0, 7200.0)
    elif "persistent_outage_initial_seconds" in config:
        # Preserve explicit legacy deployments while new configs use the staged schedule.
        persistent_outage_schedule_seconds = (
            max(60.0, float(config.get("persistent_outage_initial_seconds", 900.0))),
        )
    else:
        persistent_outage_schedule_seconds = (
            300.0,
            600.0,
            900.0,
            1800.0,
            3600.0,
            7200.0,
        )
    persistent_outage_repeat_seconds = max(
        300.0,
        float(config.get("persistent_outage_repeat_seconds", 3600.0)),
    )
    event_store_enabled = bool(config.get("event_store_enabled", True))
    event_store_path_raw = str(config.get("event_store_path", "data/miner_alerts.db"))
    telemetry_sample_seconds = max(30, int(config.get("telemetry_sample_seconds", 300)))
    telemetry_retention_days = max(1, int(config.get("telemetry_retention_days", 90)))
    event_retention_days = max(1, int(config.get("event_retention_days", 365)))
    decision_retention_days = max(1, int(config.get("decision_retention_days", 180)))
    liveness_cfg = config.get("liveness", {})
    if not isinstance(liveness_cfg, dict):
        liveness_cfg = {}
    heartbeat_enabled = bool(liveness_cfg.get("enabled", True))
    heartbeat_path = Path(
        str(liveness_cfg.get("heartbeat_path", "data/monitor_heartbeat.json"))
    ).expanduser()
    if not heartbeat_path.is_absolute():
        heartbeat_path = Path(__file__).resolve().parent.parent / heartbeat_path
    restart_attribution_window_seconds = max(
        60, int(config.get("restart_attribution_window_seconds", 900))
    )
    notify_unexpected_restarts = bool(config.get("notify_unexpected_restarts", True))
    notify_expected_restarts = bool(config.get("notify_expected_restarts", False))
    reboot_cooldown_seconds = int(config.get("reboot_cooldown_seconds", 1800))
    reboot_window_seconds = int(config.get("reboot_window_seconds", 300))
    low_sustained_seconds = 600
    auto_reboot_hashboard_enabled = bool(config.get("auto_reboot_hashboard_enabled", True))
    auto_reboot_hashboard_sustained_seconds = int(
        config.get("auto_reboot_hashboard_sustained_seconds", 600)
    )
    auto_reboot_hashboard_partial_enabled = bool(
        config.get("auto_reboot_hashboard_partial_enabled", False)
    )
    auto_reboot_window_seconds = int(config.get("auto_reboot_window_seconds", 21600))
    max_reboots_per_window = int(config.get("max_reboots_per_window", 3))
    auto_reboot_thermal_guard_enabled = bool(
        config.get("auto_reboot_thermal_guard_enabled", True)
    )
    auto_reboot_max_temp_c = float(config.get("auto_reboot_max_temp_c", 85.0))
    if not math.isfinite(auto_reboot_max_temp_c) or auto_reboot_max_temp_c <= 0:
        log("[WARN] auto_reboot_max_temp_c invalido; se usa 85.0C")
        auto_reboot_max_temp_c = 85.0
    auto_reboot_fleet_guard_enabled = bool(
        config.get("auto_reboot_fleet_guard_enabled", True)
    )
    auto_reboot_fleet_guard_min_affected = max(
        2,
        int(config.get("auto_reboot_fleet_guard_min_affected", 2)),
    )
    auto_reboot_firmware_transition_guard_enabled = bool(
        config.get("auto_reboot_firmware_transition_guard_enabled", True)
    )
    # Spec 056: Two-Tier Mining Recovery (Soft Auto-Restart vs Hard Auto-Reboot)
    auto_restart_mining_enabled = bool(config.get("auto_restart_mining_enabled", True))
    auto_restart_cooldown_seconds = int(config.get("auto_restart_cooldown_seconds", 300))
    auto_restart_max_retries_before_reboot = int(config.get("auto_restart_max_retries_before_reboot", 2))
    auto_restart_min_elapsed_seconds = int(config.get("auto_restart_min_elapsed_seconds", 180))
    # Spec 075: Soft-Landing Recovery & APW12 Latch-Off Defense
    safe_recovery_settle_window_seconds = float(config.get("safe_recovery_settle_window_seconds", 120.0))
    safe_recovery_pre_clamp_preset = str(config.get("safe_recovery_pre_clamp_preset", "1800"))
    if qa_mode:
        poll_seconds = int(config.get("qa_poll_seconds", 2))
        reboot_cooldown_seconds = int(config.get("qa_reboot_cooldown_seconds", 120))
        reboot_window_seconds = int(config.get("qa_reboot_window_seconds", 30))
        low_sustained_seconds = int(config.get("qa_low_seconds", 60))
        auto_reboot_hashboard_sustained_seconds = int(config.get("qa_hashboard_seconds", 60))
        auto_reboot_window_seconds = int(config.get("qa_auto_reboot_window_seconds", 600))
        auto_restart_cooldown_seconds = int(config.get("qa_auto_restart_cooldown_seconds", 30))
        auto_restart_min_elapsed_seconds = int(config.get("qa_auto_restart_min_elapsed_seconds", 0))
        safe_recovery_settle_window_seconds = float(config.get("qa_safe_recovery_settle_window_seconds", 5.0))
    auto_reboot_fleet_snapshot_max_age_seconds = max(60.0, float(poll_seconds * 2))
    offline_is_actionable = bool(config.get("offline_is_actionable", True))
    hashcore_cfg = config.get("hashcore", {})
    log(
        "Two-tier mining recovery: "
        f"auto_restart_enabled={str(auto_restart_mining_enabled).lower()} "
        f"cooldown={auto_restart_cooldown_seconds}s "
        f"max_retries={auto_restart_max_retries_before_reboot} "
        f"min_elapsed={auto_restart_min_elapsed_seconds}s"
    )
    log(
        "Auto-reboot interlocks: "
        f"thermal={str(auto_reboot_thermal_guard_enabled).lower()} "
        f"max_temp_c={auto_reboot_max_temp_c:.1f} "
        f"fleet={str(auto_reboot_fleet_guard_enabled).lower()} "
        f"fleet_min_affected={auto_reboot_fleet_guard_min_affected} "
        f"firmware_transition={str(auto_reboot_firmware_transition_guard_enabled).lower()} "
        f"fleet_snapshot_max_age_seconds={auto_reboot_fleet_snapshot_max_age_seconds:.0f}"
    )
    acq_config, acq_warnings = AcquisitionConfig.from_mapping(config)
    for warning in acq_warnings:
        log(f"[WARN] {warning}")
    log(
        f"ADAPTIVE_ACQUISITION enabled={str(acq_config.enabled).lower()} "
        f"workers={acq_config.workers} timeout={acq_config.timeout_seconds:.1f}s "
        f"deadline={acq_config.deadline_seconds:.1f}s "
        f"diagnostics={str(acq_config.diagnostics_enabled).lower()}"
    )

    telegram_cfg = config.get("telegram", {})
    bot_token = telegram_cfg.get("bot_token")
    chat_id = telegram_cfg.get("chat_id")

    if not bot_token or not chat_id:
        log("ERROR: telegram.bot_token y telegram.chat_id son obligatorios en app/config.json.")
        sys.exit(1)

    if not miners:
        log("ERROR: Debe definir al menos un minero en app/config.json.")
        sys.exit(1)

    valid_miners = []
    for miner in miners:
        name = miner.get("name", "sin-nombre")
        host = miner.get("host", "")
        port_raw = miner.get("port", 4028)
        try:
            port = int(port_raw)
        except (TypeError, ValueError):
            port = 0

        if not host or port <= 0:
            log(f"[WARN] Minero invalido, se omite: {name} ({host}:{port_raw})")
            continue

        valid_miner = dict(miner)
        valid_miner["name"] = name
        valid_miner["host"] = host
        valid_miner["port"] = port
        valid_miners.append(valid_miner)

    if not valid_miners:
        log("ERROR: No hay mineros validos para monitorear.")
        release_mutex()
        sys.exit(1)

    event_store: Optional[EventStore] = None
    if event_store_enabled:
        event_store_path = Path(event_store_path_raw).expanduser()
        if not event_store_path.is_absolute():
            event_store_path = Path(__file__).resolve().parent.parent / event_store_path
        event_store = EventStore(
            event_store_path,
            on_error=lambda message: log(f"[ERROR] {message}"),
        )
        log(
            f"EVENT_STORE enabled=true path={event_store.path} "
            f"available={str(event_store.available).lower()} schema={event_store.schema_version}"
        )
        if event_store.available:
            deleted = event_store.prune(
                now_ts=process_start_ts,
                sample_retention_days=telemetry_retention_days,
                event_retention_days=event_retention_days,
                decision_retention_days=decision_retention_days,
            )
            log(
                f"EVENT_STORE retention samples_deleted={deleted['samples']} "
                f"events_deleted={deleted['events']} decisions_deleted={deleted['decisions']} "
                f"firmware_events_deleted={deleted['firmware_events']} "
                f"collector_runs_deleted={deleted['collector_runs']}"
            )
    else:
        log("EVENT_STORE enabled=false")

    state_path = Path(__file__).resolve().parent / "state.json"
    states, last_update_id = load_state(state_path)
    last_update_id_ref = {"value": last_update_id}
    last_update_lock = threading.Lock()
    snapshot_ref: Dict[str, Optional[str]] = {"value": None}
    snapshot_lock = threading.Lock()
    state_lock = threading.RLock()
    pending_reboots: Dict[str, dict] = {}
    pending_lock = threading.Lock()
    global _TELEGRAM_QUEUE
    _TELEGRAM_QUEUE = queue.Queue(maxsize=200)

    # Spec 060 Phase B: StateManager & MonitorContext DI Container
    import app.miner_monitor as _self_module
    _self_module._TELEGRAM_QUEUE = _TELEGRAM_QUEUE
    from app.core.state_manager import StateManager
    from app.core.context import build_monitor_context

    state_manager = StateManager(
        state_path,
        state_lock,
        flush_lock=_SAVE_STATE_LOCK,
        get_globals_fn=lambda: vars(_self_module),
    )

    monitor_ctx = build_monitor_context(
        config=config,
        state_path=state_path,
        miners=valid_miners,
        bot_token=bot_token,
        chat_id=str(chat_id),
        state_lock=state_lock,
        telegram_queue=_TELEGRAM_QUEUE,
        state_manager=state_manager,
        event_store=event_store,
        qa_mode=qa_mode,
        qa_allow_actions=qa_allow_actions,
        qa_notify=qa_notify,
        qa_verbose=qa_verbose,
        hashcore_cfg=hashcore_cfg,
        governance=_GLOBAL_INTERVENTION_GOV,
        elevator_contingency=_ELEVATOR_CONTINGENCY_STATES,
        scheduled_window=_ACTIVE_SCHEDULED_WINDOW,
    )

    sender_thread = threading.Thread(
        target=telegram_sender_worker,
        args=(bot_token, _TELEGRAM_QUEUE, qa_mode),
        daemon=True,
        name="TelegramSender",
    )
    sender_thread.start()

    telegram_thread = threading.Thread(
        target=telegram_polling_worker,
        args=(
            bot_token,
            str(chat_id),
            state_path,
            states,
            last_update_id_ref,
            last_update_lock,
            snapshot_ref,
            snapshot_lock,
            state_lock,
            valid_miners,
            hashcore_cfg,
            pending_reboots,
            pending_lock,
            config,
            qa_mode,
            qa_allow_actions,
            event_store,
        ),
        daemon=True,
        name="TelegramPolling",
    )
    telegram_thread.start()

    log("Inicio de monitoreo.")

    acquirer: Optional[BoundedAcquirer] = None
    _gateway_heartbeat: Optional[Any] = None
    try:
        first_tick = True
        episode_notifications = IrregularEpisodeCoordinator(
            coalesce_seconds=state_change_coalesce_seconds,
            reminder_schedule_seconds=persistent_outage_schedule_seconds,
            steady_repeat_seconds=persistent_outage_repeat_seconds,
        )
        last_sample_ts: Dict[str, float] = {}
        last_retention_ts = process_start_ts
        last_wal_passive_ts = process_start_ts
        last_wal_truncate_date: Optional[str] = None
        last_chain_collection_ts = 0.0
        chain_telemetry_enabled = bool(config.get("chain_telemetry_enabled", True))
        chain_telemetry_interval_s = float(config.get("chain_telemetry_interval_s", 900.0))
        # Spec 069: Predictive Chain Break Alerting (PROP-008)
        last_predictive_chain_eval_ts = 0.0
        predictive_chain_enabled = bool(config.get("predictive_chain_break_enabled", True))
        predictive_chain_eval_interval_s = float(config.get("predictive_chain_eval_interval_s", 3600.0))
        vnish_api_password = str(config.get("vnish_api_password", "admin"))
        previous_tick_signals: Dict[str, str] = {}

        previous_tick_signals_ts: Optional[float] = None
        tick_sequence = 0
        heartbeat_error_logged = False
        acquirer: Optional[BoundedAcquirer] = None
        acq_endpoints: tuple = ()
        if acq_config.enabled:
            acq_endpoints = tuple(
                MinerEndpoint(
                    key=f"{m['name']}|{m['host']}:{m['port']}",
                    host=m["host"],
                    port=m["port"],
                )
                for m in valid_miners
            )
            acquirer = BoundedAcquirer(
                Api4028Transport(),
                workers=acq_config.workers,
                timeout_seconds=acq_config.timeout_seconds,
            )
            log(
                f"ADAPTIVE_ACQUISITION acquirer_ready=true "
                f"endpoints={len(acq_endpoints)} "
                f"workers={acq_config.workers}"
            )

        # Spec 065: Pipeline declarativo de hooks — instanciación aditiva
        # _poll_interval_seconds: valor inmutable del intervalo de configuración,
        # usado como referencia en el modelo monotónico (time.sleep(poll_seconds) donde
        # poll_seconds = max(0, _poll_interval_seconds - elapsed)).
        _poll_interval_seconds: float = float(poll_seconds)
        from app.core.engine import (
            CoreSupervisoryEngine,
            DetectionHook,
            ActuatorHook,
            GovernanceInterlockHook,
            PersistenceHook,
            TimingGuardHook,
        )
        _supervisory_engine = CoreSupervisoryEngine(monitor_ctx)
        _supervisory_engine.register_hook(TimingGuardHook(warn_threshold_seconds=25.0))
        _supervisory_engine.register_hook(DetectionHook())
        _supervisory_engine.register_hook(GovernanceInterlockHook())
        _supervisory_engine.register_hook(ActuatorHook())
        _supervisory_engine.register_hook(PersistenceHook())
        log(
            f"SUPERVISORY_HOOKS pipeline_ready=true "
            f"hooks={len(_supervisory_engine.registered_hooks)} "
            f"stages=[PRE_TICK,DETECTION,GOVERNANCE,ACTUATOR,PERSISTENCE]"
        )
        # Spec 066: Cold-Boot Fleet Grace Period (PROP-001)
        startup_grace_active = startup_fleet_grace_period_seconds > 0
        startup_notified = False

        # Spec 067: Gateway Heartbeat — Supresión de Tormentas de Red Local (PROP-005)
        _gateway_heartbeat = None
        _network_storm_suppression_seconds = float(config.get("network_storm_suppression_seconds", 15.0))
        if config.get("gateway_heartbeat_enabled", False):
            try:
                from app.network.gateway_heartbeat import GatewayHeartbeatWorker
                _gateway_heartbeat = GatewayHeartbeatWorker(
                    host=str(config.get("gateway_host", "192.168.100.1")),
                    port=int(config.get("gateway_port", 80)),
                    interval_s=float(config.get("gateway_heartbeat_interval_s", 5.0)),
                    connect_timeout_s=float(config.get("gateway_connect_timeout_ms", 50)) / 1000.0,
                    fallback_port=int(config.get("gateway_fallback_port", 53)),
                )
                _gateway_heartbeat.start()
                log(
                    f"GATEWAY_HEARTBEAT started "
                    f"host={config.get('gateway_host', '192.168.100.1')} "
                    f"port={config.get('gateway_port', 80)} "
                    f"interval={config.get('gateway_heartbeat_interval_s', 5)}s "
                    f"suppression_window={_network_storm_suppression_seconds}s"
                )
            except Exception as _gw_exc:
                log(f"[WARN] GATEWAY_HEARTBEAT failed to start: {type(_gw_exc).__name__}: {_gw_exc}. Operating without storm suppression.")
                _gateway_heartbeat = None

        # Spec 068: Canal IPC Alta Frecuencia Monitor <-> Watchdog (PROP-007)
        _watchdog_ipc_server = None
        _last_tick_duration = 0.0
        if config.get("watchdog_ipc_enabled", True):
            try:
                from app.ipc.watchdog_pipe import WatchdogIPCServer

                def _get_ipc_status() -> tuple[int, float, float]:
                    return (tick_sequence, process_start_ts, _last_tick_duration)

                _ipc_pipe_name = str(
                    config.get("watchdog_ipc_pipe_name", r"\\.\pipe\MinerAlertsWatchdog")
                )
                _ipc_fallback_port = int(config.get("watchdog_ipc_fallback_port", 4029))
                _ipc_timeout_s = (
                    float(config.get("watchdog_ipc_timeout_ms", 100)) / 1000.0
                )
                _ipc_forensics_dir = (
                    Path(config["log_file_path"]).parent
                    if config.get("log_file_path")
                    else Path("logs")
                )

                _watchdog_ipc_server = WatchdogIPCServer(
                    pipe_name=_ipc_pipe_name,
                    fallback_port=_ipc_fallback_port,
                    timeout_s=_ipc_timeout_s,
                    get_status_callback=_get_ipc_status,
                    forensics_dir=_ipc_forensics_dir,
                )
                _watchdog_ipc_server.start()
                log(
                    f"WATCHDOG_IPC started pipe={_ipc_pipe_name} "
                    f"port={_ipc_fallback_port} "
                    f"transport={_watchdog_ipc_server.active_transport}"
                )
            except Exception as _ipc_exc:
                log(
                    f"[WARN] WATCHDOG_IPC failed to start: {type(_ipc_exc).__name__}: {_ipc_exc}"
                )
                _watchdog_ipc_server = None

        while True:
            tick_start = time.monotonic()
            now_ts = time.time()
            if startup_grace_active and (now_ts - process_start_ts) >= startup_fleet_grace_period_seconds:
                startup_grace_active = False
                log(
                    f"[COLD_BOOT_GRACE] Período de gracia finalizado por timeout "
                    f"({now_ts - process_start_ts:.1f}s >= {startup_fleet_grace_period_seconds}s)"
                )
            elif startup_grace_active:
                log(
                    f"[COLD_BOOT_GRACE] Fase WARMING_UP activa "
                    f"(elapsed={now_ts - process_start_ts:.1f}s/{startup_fleet_grace_period_seconds}s)"
                )
            reboot_names_tick = []
            miner_lines = []
            startup_lines = [] if first_tick else None
            degraded_candidates = []
            current_tick_signals: Dict[str, str] = {}
            tick_failed_miners: List[Dict[str, Any]] = []
            tick_responded_miners: List[Dict[str, Any]] = []
            tick_maintenance_ids: Set[str] = set()

            # --- Adaptive epoch collection (disabled-safe, exception-safe) ---
            tick_envelopes: Optional[Dict[str, Any]] = None
            if acq_config.enabled and acquirer is not None:
                try:
                    _epoch = AcquisitionEpoch(
                        epoch_id=tick_sequence,
                        scheduled_monotonic=tick_start,
                        deadline_monotonic=tick_start + acq_config.deadline_seconds,
                        observed_ts=now_ts,
                    )
                    tick_envelopes = acquirer.collect_authoritative(acq_endpoints, _epoch)
                except Exception as _acq_exc:
                    log(f"[WARN] Adaptive acquisition epoch failed: {_acq_exc}. Using sequential fallback.")
                    tick_envelopes = None

            for miner in valid_miners:
                name = miner["name"]
                name_display = display_name(name)
                host = miner["host"]
                port = miner["port"]
                state_key = f"{name}|{host}:{port}"
                state = states.setdefault(state_key, MinerState())
                restart_observation: Optional[dict[str, Any]] = None
                transition_event_id: Optional[int] = None

                # Envelope-based acquisition (adaptive) or sequential fallback
                if tick_envelopes is not None and state_key in tick_envelopes:
                    _env = tick_envelopes[state_key]
                    rate_ths = _env.rate_ths
                    elapsed = _env.elapsed_seconds
                    responded = _env.responded
                    summary_entry = _env.summary_entry
                    active_boards = _env.active_boards
                    stats_response = _env.stats_response
                else:
                    rate_ths, elapsed, responded, summary_entry = read_summary(host, port)
                    active_boards = None
                    stats_response = None
                    if responded:
                        active_boards, _, stats_response = read_stats_snapshot(host, port)
                vnish_telemetry = normalize_vnish_stats(
                    stats_response,
                    expected_boards=expected_boards,
                )
                quality_telemetry = normalize_mining_quality(
                    summary_entry,
                    stats_response,
                    expected_boards=expected_boards,
                )
                if qa_mode:
                    qa_force = config.get("qa_force_state", {})
                    if isinstance(qa_force, dict):
                        forced = qa_force.get(display_name(name)) or qa_force.get(name)
                        if forced == "OFFLINE":
                            responded = False
                            rate_ths = None
                        elif forced == "LOW":
                            responded = True
                            rate_ths = threshold_ths - 1.0
                        elif forced == "HASHBOARD":
                            responded = True
                            active_boards = max(0, expected_boards - 1)
                # Logs operativos solo cuando hay cambios o warnings.
                is_maint_dev = getattr(state, "is_shutdown_maintenance", False) or (state.snooze_until_ts is not None and now_ts < state.snooze_until_ts)
                if is_maint_dev:
                    tick_maintenance_ids.add(name)
                    tick_maintenance_ids.add(state_key)

                if responded:
                    tick_responded_miners.append(miner)
                    state.last_seen_ts = now_ts
                else:
                    tick_failed_miners.append(miner)

                previous_elapsed = state.last_elapsed
                reboot_reason = ""
                if responded and elapsed is not None:
                    if state.last_elapsed is not None:
                        if elapsed < state.last_elapsed - 600:
                            reboot_reason = "elapsed_drop"
                        elif elapsed < 300 and state.last_elapsed > 3600:
                            reboot_reason = "elapsed_reset"
                    if reboot_reason:
                        state.low_since_ts = None
                        state.hashboard_since_ts = None
                        # Spec 062: Anti-Cascade Post-Reboot Interlock
                        if (
                            state.hw_error_lock_until_ts
                            and now_ts < state.hw_error_lock_until_ts
                            and state.hw_error_locked_preset
                        ):
                            log(
                                f"[TRIPWIRE_INTERLOCK] miner={name} reinicio detectado ({reboot_reason}) "
                                f"con candado activo hasta {state.hw_error_lock_until_ts:.0f} (objetivo={state.hw_error_locked_preset}). "
                                "Programando restauracion defensiva de preset post-reboot."
                            )
                            def _async_restore_locked_preset(
                                h=host,
                                pw=vnish_api_password,
                                pr=state.hw_error_locked_preset,
                                nm=name,
                            ):
                                try:
                                    time.sleep(15.0)
                                    ok_p, err_p = safe_set_miner_preset(h, pw, pr)
                                    if ok_p:
                                        log(f"[TRIPWIRE_INTERLOCK] miner={nm} preset defensivo restaurado con exito a {pr}")
                                    else:
                                        log(f"[TRIPWIRE_INTERLOCK_ERR] miner={nm} fallo restaurando a {pr}: {err_p}")
                                except Exception as _th_exc:
                                    log(f"[TRIPWIRE_INTERLOCK_ERR] miner={nm} excepcion restaurando preset a {pr}: {_th_exc}")

                            threading.Thread(
                                target=_async_restore_locked_preset,
                                daemon=True,
                                name=f"TripwireRestore_{name}",
                            ).start()
                        if chain_telemetry_enabled and event_store is not None and event_store.available:
                            threading.Thread(
                                target=_async_collect_chain_telemetry,
                                args=(valid_miners, event_store, vnish_api_password, name, config, bot_token, chat_id, qa_mode, qa_notify),
                                daemon=True,
                                name=f"ChainTelemetryReactive_{name}",
                            ).start()
                    state.last_elapsed = elapsed



                if not responded:
                    state.offline_streak += 1
                    state.low_streak = 0
                    state.ok_streak = 0
                elif rate_ths is None:
                    state.offline_streak = 0
                    state.low_streak = 0
                    state.ok_streak = 0
                elif rate_ths < threshold_ths:
                    state.low_streak += 1
                    state.offline_streak = 0
                    state.ok_streak = 0
                else:
                    state.ok_streak += 1
                    state.low_streak = 0
                    state.offline_streak = 0

                if startup_grace_active:
                    state.offline_streak = 0
                    state.low_streak = 0

                prev_state = state.state
                new_state = DetectionHook.classify_state(
                    responded=responded,
                    rate_ths=rate_ths,
                    threshold_ths=threshold_ths,
                    active_boards=active_boards,
                    expected_boards=expected_boards,
                    startup_grace_active=startup_grace_active,
                    offline_streak=state.offline_streak,
                    low_streak=state.low_streak,
                    ok_streak=state.ok_streak,
                    fails_before_alert=fails_before_alert,
                    recovery_successes=recovery_successes,
                    prev_state=prev_state,
                )

                if new_state != prev_state and new_state in (STATE_HASHBOARD, STATE_LOW):
                    if chain_telemetry_enabled and event_store is not None and event_store.available:
                        threading.Thread(
                            target=_async_collect_chain_telemetry,
                            args=(valid_miners, event_store, vnish_api_password, name, config, bot_token, chat_id, qa_mode, qa_notify),
                            daemon=True,
                            name=f"ChainTelemetryTransition_{name}",
                        ).start()


                state.state = new_state


                if new_state == STATE_OK:
                    state.low_streak = 0
                    state.offline_streak = 0
                    state.hashboard_since_ts = None
                    state.auto_restart_count = 0

                if new_state == STATE_LOW:
                    if state.low_since_ts is None:
                        state.low_since_ts = now_ts
                else:
                    state.low_since_ts = None
                    state.low_streak = 0

                if new_state == STATE_HASHBOARD:
                    if state.hashboard_since_ts is None:
                        state.hashboard_since_ts = now_ts
                else:
                    state.hashboard_since_ts = None

                if startup_grace_active:
                    state.low_since_ts = None
                    state.hashboard_since_ts = None

                if event_store is not None and event_store.available:
                    last_sample = last_sample_ts.get(state_key, 0.0)
                    if (now_ts - last_sample) >= telemetry_sample_seconds:
                        last_sample_ts[state_key] = now_ts
                        event_store.record_sample(
                            observed_ts=now_ts,
                            miner_key=state_key,
                            miner_name=name_display,
                            host=host,
                            state=new_state,
                            responded=responded,
                            rate_ths=rate_ths,
                            threshold_ths=threshold_ths,
                            active_boards=active_boards,
                            expected_boards=expected_boards,
                            elapsed_seconds=elapsed,
                            telemetry={
                                **vnish_telemetry.as_dict(),
                                **quality_telemetry.as_dict(),
                            },
                        )

                # Spec 039: Feed live telemetry to governor state for next cycle
                if responded:
                    state.last_fan_mode = vnish_telemetry.fan_mode
                    if vnish_telemetry.max_temp_c is not None:
                        state.governor_last_temp_c = vnish_telemetry.max_temp_c
                    if vnish_telemetry.chain_power_w_total is not None:
                        state.governor_last_power_w = vnish_telemetry.chain_power_w_total
                    if state.governor_duty is None and vnish_telemetry.fan_pwm_percent is not None:
                        # Seed initial duty from hardware reading
                        state.governor_duty = int(round(vnish_telemetry.fan_pwm_percent))
                else:
                    # When miner does not respond, clear telemetry so governor does not act on stale data
                    state.governor_last_temp_c = None
                    state.governor_last_power_w = None

                # Spec 046: Feed live telemetry snapshot to MinerState for /status & fleet cards
                eff_j_th: Optional[float] = None
                if (
                    responded
                    and vnish_telemetry.chain_power_w_total is not None
                    and rate_ths is not None
                    and rate_ths > 0
                ):
                    eff_j_th = round(vnish_telemetry.chain_power_w_total / rate_ths, 2)

                with state_lock:
                    state.last_responded = bool(responded)
                    if responded:
                        state.last_rate_ths = rate_ths
                        state.last_active_boards = active_boards
                        state.last_expected_boards = expected_boards
                        state.last_max_chip_temp = vnish_telemetry.max_temp_c
                        state.last_fan_duty_percent = vnish_telemetry.fan_pwm_percent
                        state.last_power_w = vnish_telemetry.chain_power_w_total
                        state.last_efficiency_j_th = eff_j_th
                        state.inlet_temp_c = vnish_telemetry.inlet_temp_c
                    else:
                        state.last_rate_ths = 0.0
                        state.last_active_boards = 0
                        state.last_expected_boards = expected_boards
                        state.last_max_chip_temp = None
                        state.last_fan_duty_percent = None
                        state.last_power_w = 0.0
                        state.last_efficiency_j_th = None
                        state.inlet_temp_c = None

                # Spec 035: Cooling & Fan Health Intelligence preventative evaluation
                cooling_alert_enabled = bool(config.get("cooling_alert_enabled", True))
                if cooling_alert_enabled and not first_tick and responded:
                    critical_temp = float(config.get("cooling_critical_temp_c", 84.5))
                    saturate_temp = float(config.get("cooling_saturate_temp_c", 84.0))
                    saturate_pwm = float(config.get("cooling_saturate_pwm_pct", 98.0))
                    saturate_rpm = int(config.get("cooling_saturate_rpm", 5800))
                    cooling_ass = assess_miner_cooling(
                        miner_name=name_display,
                        max_temp_c=vnish_telemetry.max_temp_c,
                        fan_rpm_max=vnish_telemetry.fan_rpm_max,
                        fan_pwm_percent=vnish_telemetry.fan_pwm_percent,
                        diagnostic_flags=vnish_telemetry.diagnostic_flags,
                        rate_ths=rate_ths,
                        critical_temp_c=critical_temp,
                        saturate_temp_c=saturate_temp,
                        saturate_pwm_pct=saturate_pwm,
                        saturate_rpm=saturate_rpm,
                        fan_mode=vnish_telemetry.fan_mode,
                    )
                    cooling_warning = evaluate_cooling_alerts(
                        state=state,
                        assessment=cooling_ass,
                        now_ts=now_ts,
                        config=config,
                    )
                    is_currently_snoozed = (
                        state.snooze_until_ts is not None and now_ts < state.snooze_until_ts
                    )
                    if cooling_warning and not is_currently_snoozed and ((not qa_mode) or qa_notify):
                        send_telegram(
                            bot_token,
                            str(chat_id),
                            cooling_warning,
                            "COOLING_WARNING",
                            "cooling_warning",
                        )
                        log(f"[COOLING_WARNING] miner={name_display} status={cooling_ass.status}")

                # Spec 036: Hashrate Efficiency & Energy Tracking preventative evaluation
                efficiency_alert_enabled = bool(config.get("efficiency_alert_enabled", True))
                if efficiency_alert_enabled and not first_tick and responded:
                    eff_target = float(config.get("efficiency_target_j_th", 30.0))
                    eff_thresh = float(config.get("efficiency_degraded_threshold_j_th", 35.0))
                    eff_ass = assess_miner_efficiency(
                        miner_name=name_display,
                        power_w=vnish_telemetry.chain_power_w_total,
                        rate_ths=rate_ths,
                        target_j_th=eff_target,
                        degraded_threshold_j_th=eff_thresh,
                    )
                    eff_warning = evaluate_efficiency_alerts(
                        state=state,
                        assessment=eff_ass,
                        now_ts=now_ts,
                        config=config,
                    )
                    is_currently_snoozed = (
                        state.snooze_until_ts is not None and now_ts < state.snooze_until_ts
                    )
                    if eff_warning and not is_currently_snoozed and ((not qa_mode) or qa_notify):
                        send_telegram(
                            bot_token,
                            str(chat_id),
                            eff_warning,
                            "EFFICIENCY_WARNING",
                            "efficiency_warning",
                        )
                        log(f"[EFFICIENCY_WARNING] miner={name_display} status={eff_ass.status} eff={eff_ass.efficiency_j_th}")

                # Spec 037: Vnish Operating Profile & Autotuning preventative evaluation
                preset_alert_enabled = bool(config.get("preset_alert_enabled", True))
                if preset_alert_enabled and not first_tick and responded:
                    freq_drop_thresh = float(config.get("preset_frequency_drop_mhz", 25.0))
                    chains_trans = (
                        quality_telemetry.chains_transitioning_count
                        if quality_telemetry and quality_telemetry.chains_transitioning_count is not None
                        else 0
                    )
                    preset_ass = assess_miner_preset(
                        miner_name=name_display,
                        frequency_mhz=vnish_telemetry.frequency_mhz_avg,
                        voltage_mv=vnish_telemetry.chain_voltage_mv_avg,
                        power_w=vnish_telemetry.chain_power_w_total,
                        rate_ths=rate_ths,
                        chains_transitioning_count=chains_trans,
                        baseline_frequency_mhz=getattr(state, "baseline_frequency_mhz", None),
                        frequency_drop_threshold_mhz=freq_drop_thresh,
                    )
                    preset_warning = evaluate_preset_alerts(
                        state=state,
                        assessment=preset_ass,
                        now_ts=now_ts,
                        config=config,
                    )
                    is_currently_snoozed = (
                        state.snooze_until_ts is not None and now_ts < state.snooze_until_ts
                    )
                    if preset_warning and not is_currently_snoozed and ((not qa_mode) or qa_notify):
                        send_telegram(
                            bot_token,
                            str(chat_id),
                            preset_warning,
                            "PROFILE_CHANGE_ALERT",
                            "preset_warning",
                        )
                        log(f"[PROFILE_CHANGE_ALERT] miner={name_display} status={preset_ass.status} freq={preset_ass.frequency_mhz}")

                if (
                    reboot_reason
                    and previous_elapsed is not None
                    and elapsed is not None
                ):
                    restart_classification = classify_restart(
                        restart_reason=reboot_reason,
                        detected_ts=now_ts,
                        last_manual_action_ts=state.last_manual_reboot_ts,
                        last_auto_action_ts=state.last_auto_reboot_ts,
                        attribution_window_seconds=restart_attribution_window_seconds,
                    )
                    incident_id = None
                    m_group = miner.get("electrical_group", "default")
                    recent_chain_samples = None
                    if event_store is not None and event_store.available:
                        try:
                            recent_chain_samples = (
                                event_store.get_latest_chain_samples(name)
                                or event_store.get_latest_chain_samples(name_display)
                                or event_store.get_latest_chain_samples(state_key)
                            )
                        except Exception as _cs_exc:
                            log(f"[CHAIN_SAMPLES_ERR] get latest chain samples failed: {_cs_exc}")

                    elev_circumstance = record_elevator_restart_circumstance(
                        miner_name=name_display,
                        electrical_group=m_group,
                        miners=miners,
                        states=states,
                        now_ts=now_ts,
                        cascade_window_s=float(config.get("preset_balancer_group_cascade_window_s", 1800.0)),
                        chain_samples=recent_chain_samples,
                    )
                    restart_details = {
                        "reason": reboot_reason,
                        "first_tick": first_tick,
                        "electrical_group": m_group,
                        "group_total_power_w": elev_circumstance.get("group_total_power_w", 0.0),
                        "pre_restart_power_w": state.governor_last_power_w,
                        "pre_restart_temp_c": state.governor_last_temp_c,
                        "is_elevator_cascade": elev_circumstance.get("is_elevator_cascade", False),
                        "cascade_peer": elev_circumstance.get("cascade_peer"),
                        "cascade_delta_s": elev_circumstance.get("cascade_delta_s"),
                        "culprit_chain": elev_circumstance.get("culprit_chain"),
                    }
                    incident_summary = f"Uptime reiniciado: {previous_elapsed}s -> {elapsed}s"
                    culprit = elev_circumstance.get("culprit_chain")
                    if culprit and isinstance(culprit, dict):
                        incident_summary += f" | Causa aislada: Cadena {culprit.get('chain_id')} ({culprit.get('reason')})"

                    if event_store is not None and event_store.available:
                        incident_id = event_store.record_event(
                            occurred_ts=now_ts,
                            miner_key=state_key,
                            miner_name=name_display,
                            host=host,
                            event_type="restart_detected",
                            severity=restart_classification.severity,
                            classification=restart_classification.classification,
                            previous_state=prev_state,
                            new_state=new_state,
                            rate_ths=rate_ths,
                            threshold_ths=threshold_ths,
                            previous_elapsed=previous_elapsed,
                            current_elapsed=elapsed,
                            action_source=restart_classification.action_source,
                            action_ts=restart_classification.action_ts,
                            summary=incident_summary,
                            details=restart_details,
                        )

                        if elev_circumstance.get("is_elevator_cascade"):
                            event_store.record_event(
                                occurred_ts=now_ts,
                                miner_key=state_key,
                                miner_name=name_display,
                                host=host,
                                event_type="elevator_cascade_restart",
                                severity="warning",
                                summary=(
                                    f"Alerta Elevador [{m_group.upper()}]: Caída correlacionada. "
                                    f"{name_display} reinició {elev_circumstance['cascade_delta_s']:.0f}s tras {elev_circumstance['cascade_peer']}. "
                                    f"Carga grupo: {elev_circumstance['group_total_power_w']:.0f}W"
                                ),
                                details=restart_details,
                            )
                    log(
                        f"[INCIDENT] type=restart_detected miner={name_display} group={m_group} "
                        f"classification={restart_classification.classification} "
                        f"elapsed={previous_elapsed}->{elapsed} event_id={incident_id} "
                        f"cascade={elev_circumstance.get('is_elevator_cascade')} "
                        f"group_load={elev_circumstance.get('group_total_power_w', 0.0):.0f}W"
                    )
                    # Spec 057: Adaptive Elevator Contingency Check
                    if (
                        restart_classification.classification == "unexpected"
                        and m_group
                        and m_group in ("elevator_1", "elevator_2")
                    ):
                        try:
                            from app.governance.intervention_policy import ACTION_CONTINGENCY, should_allow_intervention
                            from app.governance.adaptive_contingency import evaluate_canary_contingency
                            gov_obj = getattr(state, "intervention_gov", None) or globals().get("_GLOBAL_INTERVENTION_GOV")
                            cont_allowed, _ = should_allow_intervention(ACTION_CONTINGENCY, gov_obj, now_ts)
                            if cont_allowed:
                                _grp_presets = {}
                                with state_lock:
                                    for _m in miners:
                                        if (_m.get("electrical_group") or _m.get("group")) == m_group:
                                            _mn = _m.get("name")
                                            _sk = f"{_m.get('name','')}|{_m.get('host','')}:{_m.get('port',4028)}"
                                            _st = states.get(_sk)
                                            _pr = getattr(_st, "balancer_preset", None) if _st else None
                                            _grp_presets[_mn] = _pr or _m.get("max_preset", "2700W")
                                    _c_state = _ELEVATOR_CONTINGENCY_STATES.get(m_group)
                                _paired_inrush_cfg = bool(config.get("contingency_paired_inrush_enabled", True))
                                _decision = evaluate_canary_contingency(
                                    event_type="unexpected_restart",
                                    miner_name=name_display,
                                    group_name=m_group,
                                    current_presets=_grp_presets,
                                    now_ts=now_ts,
                                    group_state=_c_state,
                                    enable_paired_inrush=_paired_inrush_cfg,
                                )
                                if _decision.updated_group_state:
                                    with state_lock:
                                        _ELEVATOR_CONTINGENCY_STATES[m_group] = _decision.updated_group_state
                                if _decision.requires_write and not qa_mode:
                                    from app.governance.adaptive_contingency import normalize_miner_name
                                    _tgt_miner = next(
                                        (m_item for m_item in miners
                                         if normalize_miner_name(m_item.get("name", "")) == normalize_miner_name(_decision.target_miner)),
                                        None
                                    )
                                    if _tgt_miner:
                                        vnish_pw = str(config.get("vnish_api_password", "admin"))
                                        from app.vnish.client import safe_set_miner_preset
                                        _w_ok, _w_msg = safe_set_miner_preset(
                                            _tgt_miner.get("host", ""),
                                            vnish_pw,
                                            _decision.target_preset,
                                            timeout=float(config.get("fan_governor_request_timeout", 2.5)),
                                            clamp_top_preset=True,
                                        )
                                        log(f"[CONTINGENCY] Applied preset {_decision.target_preset} to {_decision.target_miner}: ok={_w_ok} msg={_w_msg}")
                                        _t_sk = f"{_tgt_miner.get('name','')}|{_tgt_miner.get('host','')}:{_tgt_miner.get('port',4028)}"
                                        with state_lock:
                                            _t_st = states.get(_t_sk)
                                            if _t_st:
                                                _t_st.balancer_preset = _decision.target_preset
                                if _decision.partner_requires_write and _decision.partner_miner and not qa_mode:
                                    from app.governance.adaptive_contingency import normalize_miner_name
                                    _pt_miner = next(
                                        (m_item for m_item in miners
                                         if normalize_miner_name(m_item.get("name", "")) == normalize_miner_name(_decision.partner_miner)),
                                        None
                                    )
                                    if _pt_miner:
                                        vnish_pw = str(config.get("vnish_api_password", "admin"))
                                        from app.vnish.client import safe_set_miner_preset
                                        _pw_ok, _pw_msg = safe_set_miner_preset(
                                            _pt_miner.get("host", ""),
                                            vnish_pw,
                                            _decision.partner_target_preset,
                                            timeout=float(config.get("fan_governor_request_timeout", 2.5)),
                                            clamp_top_preset=True,
                                        )
                                        log(f"[CONTINGENCY_DAMPENER] Applied partner dampener {_decision.partner_target_preset} to {_decision.partner_miner}: ok={_pw_ok} msg={_pw_msg}")
                                        _pt_sk = f"{_pt_miner.get('name','')}|{_pt_miner.get('host','')}:{_pt_miner.get('port',4028)}"
                                        with state_lock:
                                            _pt_st = states.get(_pt_sk)
                                            if _pt_st:
                                                _pt_st.balancer_preset = _decision.partner_target_preset
                                if _decision.notification_msg:
                                    send_telegram(
                                        bot_token,
                                        str(chat_id),
                                        _decision.notification_msg,
                                        "CONTINGENCY",
                                        f"contingency_{m_group}",
                                        is_command=True,
                                    )
                        except Exception as _cont_exc:
                            log(f"[CONTINGENCY_ERR] Adaptive contingency evaluation failed: {_cont_exc}")
                    should_notify_restart = (
                        restart_classification.classification == "unexpected"
                        and notify_unexpected_restarts
                    ) or (
                        restart_classification.classification != "unexpected"
                        and notify_expected_restarts
                    )
                    if (
                        notify_reboot
                        and should_notify_restart
                        and ((not qa_mode) or qa_notify)
                    ):
                        restart_observation = {
                            "event_id": incident_id,
                            "classification": restart_classification.classification,
                            "previous_elapsed": previous_elapsed,
                            "current_elapsed": elapsed,
                        }

                if not state.initialized:
                    state.initialized = True

                if reboot_reason and notify_reboot:
                    if (now_ts - state.last_reboot_ts) >= reboot_cooldown_seconds:
                        if new_state in (STATE_LOW, STATE_OFFLINE):
                            reboot_names_tick.append(name_display)
                            state.last_reboot_ts = now_ts
                            state.reboot_pending_until = 0.0
                            state.reboot_pending_reason = ""
                            state.reboot_pending_elapsed = None
                        else:
                            state.reboot_pending_until = now_ts + reboot_window_seconds
                            state.reboot_pending_reason = reboot_reason
                            state.reboot_pending_elapsed = elapsed

                if state.reboot_pending_until and now_ts > state.reboot_pending_until:
                    state.reboot_pending_until = 0.0
                    state.reboot_pending_reason = ""
                    state.reboot_pending_elapsed = None

                # Spec 075: Staged Ramp-Up restore after Soft-Landing
                if (
                    getattr(state, "is_pre_clamped", False)
                    and getattr(state, "staged_ramp_up_pending", False)
                    and new_state == STATE_OK
                    and (rate_ths is not None and rate_ths >= threshold_ths)
                ):
                    if state.staged_ramp_up_soak_start_ts is None:
                        with state_lock:
                            state.staged_ramp_up_soak_start_ts = now_ts
                        log(f"[SAFE-RECOVERY] {name_display} estabilizado en OK con pre-clamp: iniciando soak de rampa ascendente (180s)...")
                    elif (now_ts - state.staged_ramp_up_soak_start_ts) >= 180.0:
                        nom_preset = (getattr(state, "original_preset_before_clamp", None) or getattr(state, "balancer_preset", "2300W") or "2300W").rstrip("W")
                        log(f"[SAFE-RECOVERY] {name_display} soak de 180s completado: restaurando preset nominal ({nom_preset}W, ceiling 2700W)...")
                        safe_set_miner_preset(host, vnish_api_password, nom_preset, clamp_top_preset=False, top_preset="2700")
                        with state_lock:
                            state.is_pre_clamped = False
                            state.staged_ramp_up_pending = False
                            state.staged_ramp_up_soak_start_ts = None
                            state.original_preset_before_clamp = None

                # Spec 056 & Spec 075: Two-Tier Mining Recovery - Level 1 (Soft Auto-Restart & Soft-Landing)
                is_hash_degraded = (
                    new_state in (STATE_LOW, STATE_HASHBOARD)
                    or (rate_ths is not None and rate_ths <= 0.0)
                    or (active_boards is not None and active_boards == 0)
                )
                if not is_hash_degraded:
                    if state.stopped_since_ts is not None:
                        with state_lock:
                            state.stopped_since_ts = None

                _is_stock_fw = False
                if (
                    auto_restart_mining_enabled
                    and responded
                    and not first_tick
                    and not startup_grace_active
                    and not reboot_reason
                    and is_hash_degraded
                ):
                    if state.stopped_since_ts is None:
                        with state_lock:
                            state.stopped_since_ts = now_ts
                    elapsed_stopped = now_ts - state.stopped_since_ts

                    _v_st_ok, _v_st_data, _v_st_err = get_miner_status(host)
                    _is_stock_fw = (_v_st_err == "stock_firmware_fallback_detected")

                    if _is_stock_fw:
                        log(f"[SAFE-RECOVERY] blocked_by=stock_firmware_fallback miner={name_display} (firmware stock Bitmain detectado)")
                        if not getattr(state, "stock_firmware_fallback_notified", False):
                            with state_lock:
                                state.stock_firmware_fallback_notified = True
                            send_telegram(
                                bot_token,
                                str(chat_id),
                                f"[FIRMWARE FALLBACK] {name_display} ({host}) ha iniciado en firmware de fabrica Bitmain 2021 (NAND).\n"
                                f"Tarjeta MicroSD con VNish no detectada o ilegible tras corte de energia.\n"
                                f"Accion recomendada: Revisar fisicamente la ranura MicroSD.",
                                "ERROR",
                                "firmware_fallback",
                            )
                    elif elapsed_stopped < safe_recovery_settle_window_seconds:
                        log(f"[SAFE-RECOVERY] miner={name_display} en ventana pasiva de settle ({elapsed_stopped:.0f}s/{safe_recovery_settle_window_seconds:.0f}s)")
                    else:
                        _vn_state, _restart_req, _reboot_req = parse_miner_status_flags(_v_st_data if _v_st_ok else None)
                        _is_restart_cand, _restart_reason, _restart_cd = evaluate_auto_restart_candidate(
                            now_ts=now_ts,
                            responded=responded,
                            rate_ths=rate_ths,
                            threshold_ths=threshold_ths,
                            active_boards=active_boards,
                            expected_boards=expected_boards,
                            miner_state=_vn_state,
                            restart_required=_restart_req,
                            reboot_required=_reboot_req,
                            auto_restart_enabled=auto_restart_mining_enabled,
                            last_auto_restart_ts=state.last_auto_restart_ts,
                            auto_restart_cooldown_seconds=auto_restart_cooldown_seconds,
                            auto_restart_count=state.auto_restart_count,
                            max_retries_before_reboot=auto_restart_max_retries_before_reboot,
                            in_maintenance=getattr(state, "is_shutdown_maintenance", False),
                            is_snoozed=(state.snooze_until_ts is not None and now_ts < state.snooze_until_ts),
                            elapsed=elapsed,
                            min_elapsed_seconds=auto_restart_min_elapsed_seconds,
                            startup_grace_active=startup_grace_active,
                        )
                        if _is_restart_cand:
                            if qa_mode and not qa_allow_actions:
                                log(f"[AUTO-RESTART] blocked_by=qa miner={name_display} reason={_restart_reason}")
                                if qa_notify:
                                    send_telegram(
                                        bot_token,
                                        str(chat_id),
                                        f"[AUTO-RESTART] Accion bloqueada (QA): {name_display} ({_restart_reason}).",
                                        "ERROR",
                                        "qa_block",
                                    )
                            else:
                                with state_lock:
                                    state.last_auto_restart_ts = now_ts
                                    state.auto_restart_count += 1
                                    if not getattr(state, "original_preset_before_clamp", None):
                                        state.original_preset_before_clamp = getattr(state, "balancer_preset", None) or "2300"
                                    state.is_pre_clamped = True
                                    state.staged_ramp_up_pending = True
                                    state.staged_ramp_up_soak_start_ts = None
                                threading.Thread(
                                    target=_async_execute_mining_restart,
                                    args=(
                                        host,
                                        vnish_api_password,
                                        name,
                                        miner,
                                        _restart_reason,
                                        state.auto_restart_count,
                                        auto_restart_max_retries_before_reboot,
                                        bot_token,
                                        chat_id,
                                        qa_mode,
                                        qa_notify,
                                        event_store,
                                        safe_recovery_pre_clamp_preset,
                                    ),
                                    daemon=True,
                                    name=f"AutoRestart_{name}",
                                ).start()
                        elif _restart_reason == "cooldown":
                            log(f"[AUTO-RESTART] blocked_by=cooldown miner={name_display} cooldown_remaining={_restart_cd:.0f}s")
                        elif _restart_reason == "miner_warming_up":
                            log(f"[AUTO-RESTART] blocked_by=miner_warming_up miner={name_display} elapsed={elapsed}s < {auto_restart_min_elapsed_seconds}s")
                        elif _restart_reason == "max_retries_exceeded":
                            log(f"[AUTO-RESTART] blocked_by=max_retries_exceeded miner={name_display} attempts={state.auto_restart_count}/{auto_restart_max_retries_before_reboot} -> escalando a Nivel 2 (auto-reboot)")

                # Auto-reboot policy
                state.auto_reboot_timestamps = [
                    ts for ts in state.auto_reboot_timestamps if (now_ts - ts) <= auto_reboot_window_seconds
                ]
                startup_guard_active = (now_ts - process_start_ts) < startup_guard_seconds
                auto_reboot_signal = classify_auto_reboot_signal(
                    responded,
                    rate_ths,
                    threshold_ths,
                )
                current_tick_signals[state_key] = auto_reboot_signal
                auto_reboot_candidate = auto_reboot_signal == AUTO_REBOOT_SIGNAL_ELIGIBLE
                interlock_decision = evaluate_auto_reboot_interlocks(
                    current_miner_key=state_key,
                    current_signal=auto_reboot_signal,
                    previous_signals=previous_tick_signals,
                    previous_signals_observed_ts=previous_tick_signals_ts,
                    evaluated_ts=now_ts,
                    fleet_snapshot_max_age_seconds=auto_reboot_fleet_snapshot_max_age_seconds,
                    max_temp_c=vnish_telemetry.max_temp_c,
                    thermal_guard_enabled=auto_reboot_thermal_guard_enabled,
                    thermal_limit_c=auto_reboot_max_temp_c,
                    fleet_guard_enabled=auto_reboot_fleet_guard_enabled,
                    fleet_min_affected=auto_reboot_fleet_guard_min_affected,
                    firmware_transition_guard_enabled=(
                        auto_reboot_firmware_transition_guard_enabled
                    ),
                    chains_transitioning_count=quality_telemetry.chains_transitioning_count,
                    stock_firmware_present=_is_stock_fw,
                )
                decision_context: Dict[str, Any] = {
                    "evaluated_ts": now_ts,
                    "miner": miner,
                    "state": state,
                    "responded": responded,
                    "rate_ths": rate_ths,
                    "threshold_ths": threshold_ths,
                    "active_boards": active_boards,
                    "expected_boards": expected_boards,
                    "telemetry": vnish_telemetry,
                    "startup_guard_active": startup_guard_active,
                    "qa_mode": qa_mode,
                    "window_seconds": auto_reboot_window_seconds,
                }
                if auto_reboot_candidate and new_state not in (STATE_LOW, STATE_HASHBOARD):
                    record_auto_reboot_decision(
                        event_store,
                        result="not_low",
                        cooldown_remaining_seconds=None,
                        details={
                            "low_streak": state.low_streak,
                            "fails_before_alert": fails_before_alert,
                        },
                        **decision_context,
                    )
                    log(
                        f"[AUTO-REBOOT] blocked_by=not_low miner={name_display} "
                        f"rate_ths={rate_ths} threshold_ths={threshold_ths} "
                        f"low_streak={state.low_streak}/{fails_before_alert}"
                    )
                if auto_reboot_signal == AUTO_REBOOT_SIGNAL_INVALID and prev_state == STATE_LOW:
                    record_auto_reboot_decision(
                        event_store,
                        result="invalid_signal",
                        cooldown_remaining_seconds=None,
                        details={"previous_state": prev_state},
                        **decision_context,
                    )
                    log(
                        f"[AUTO-REBOOT] blocked_by=invalid_signal miner={name_display} "
                        f"responded={responded} rate_ths={rate_ths}"
                    )
                if new_state == STATE_LOW and state.low_since_ts:
                    if not auto_reboot_signal_allows_evaluation(
                        new_state,
                        state.low_since_ts,
                        auto_reboot_signal,
                    ):
                        if auto_reboot_signal == AUTO_REBOOT_SIGNAL_NOT_LOW:
                            record_auto_reboot_decision(
                                event_store,
                                result="not_low",
                                cooldown_remaining_seconds=None,
                                details={"reason": "current_rate_not_below_threshold"},
                                **decision_context,
                            )
                            log(
                                f"[AUTO-REBOOT] blocked_by=not_low miner={name_display} "
                                f"state={new_state} rate_ths={rate_ths} threshold_ths={threshold_ths}"
                            )
                        reset_sustained_low_if_signal_ineligible(
                            state,
                            auto_reboot_signal,
                        )
                    elif startup_guard_active:
                        record_auto_reboot_decision(
                            event_store,
                            result="startup_guard",
                            cooldown_remaining_seconds=None,
                            details={"startup_guard_seconds": startup_guard_seconds},
                            **decision_context,
                        )
                        log(
                            f"[AUTO-REBOOT] blocked_by=startup_guard miner={name_display} "
                            f"since_start={now_ts - process_start_ts:.1f}s guard={startup_guard_seconds}s"
                        )
                    elif (now_ts - state.low_since_ts) < low_sustained_seconds:
                        record_auto_reboot_decision(
                            event_store,
                            result="not_sustained",
                            cooldown_remaining_seconds=None,
                            details={"required_seconds": low_sustained_seconds},
                            **decision_context,
                        )
                        log(
                            f"[AUTO-REBOOT] blocked_by=not_sustained miner={name_display} "
                            f"elapsed={(now_ts - state.low_since_ts):.0f}s required={low_sustained_seconds}s"
                        )
                    elif not interlock_decision.allowed:
                        interlock_reason = interlock_decision.reason or "safety_interlock"
                        affected_miners = list(interlock_decision.affected_miners)
                        record_auto_reboot_decision(
                            event_store,
                            result=interlock_reason,
                            cooldown_remaining_seconds=None,
                            details={
                                "affected_miners": affected_miners,
                                "affected_count": len(affected_miners),
                                "fleet_min_affected": auto_reboot_fleet_guard_min_affected,
                                "fleet_snapshot_age_seconds": (
                                    interlock_decision.fleet_snapshot_age_seconds
                                ),
                                "max_temp_c": interlock_decision.max_temp_c,
                                "thermal_limit_c": auto_reboot_max_temp_c,
                                "chains_transitioning_count": (
                                    interlock_decision.chains_transitioning_count
                                ),
                                "firmware_transition_guard_enabled": (
                                    auto_reboot_firmware_transition_guard_enabled
                                ),
                                "low_timer_reset": bool(
                                    auto_reboot_firmware_transition_guard_enabled
                                    and (interlock_decision.chains_transitioning_count or 0) > 0
                                ),
                            },
                            **decision_context,
                        )
                        if (
                            auto_reboot_firmware_transition_guard_enabled
                            and (interlock_decision.chains_transitioning_count or 0) > 0
                        ):
                            state.low_since_ts = now_ts
                        if interlock_reason == "high_temperature":
                            log(
                                f"[AUTO-REBOOT] blocked_by=high_temperature miner={name_display} "
                                f"max_temp_c={interlock_decision.max_temp_c} "
                                f"limit_c={auto_reboot_max_temp_c:.1f}"
                            )
                        elif interlock_reason == "firmware_transition":
                            log(
                                f"[AUTO-REBOOT] blocked_by=firmware_transition miner={name_display} "
                                f"transitioning_chains={interlock_decision.chains_transitioning_count} "
                                f"low_timer_reset=true"
                            )
                        else:
                            log(
                                f"[AUTO-REBOOT] blocked_by=fleet_incident miner={name_display} "
                                f"affected_count={len(affected_miners)} "
                                f"min_affected={auto_reboot_fleet_guard_min_affected} "
                                f"snapshot_age={interlock_decision.fleet_snapshot_age_seconds} "
                                f"affected={','.join(affected_miners)}"
                            )
                    else:
                        skew_tolerance_seconds = 10
                        last_reboot_ts = None
                        if state.last_manual_reboot_ts is not None:
                            last_reboot_ts = state.last_manual_reboot_ts
                        if state.last_auto_reboot_ts is not None:
                            last_reboot_ts = (
                                state.last_auto_reboot_ts
                                if last_reboot_ts is None
                                else max(last_reboot_ts, state.last_auto_reboot_ts)
                            )
                        if last_reboot_ts is not None and last_reboot_ts > now_ts + skew_tolerance_seconds:
                            log(
                                f"[WARN] last_reboot_ts ahead of clock "
                                f"miner={name_display} last_reboot_ts={last_reboot_ts} now={now_ts}"
                            )
                            last_reboot_ts = now_ts
                        if last_reboot_ts is not None:
                            cooldown_delta = max(0.0, now_ts - last_reboot_ts)
                            if cooldown_delta < reboot_cooldown_seconds:
                                cooldown_remaining = max(
                                    0.0,
                                    reboot_cooldown_seconds - cooldown_delta,
                                )
                                record_auto_reboot_decision(
                                    event_store,
                                    result="cooldown",
                                    cooldown_remaining_seconds=cooldown_remaining,
                                    details={"cooldown_seconds": reboot_cooldown_seconds},
                                    **decision_context,
                                )
                                log(
                                    f"[AUTO-REBOOT] blocked_by=cooldown miner={name_display} "
                                    f"cooldown_delta={cooldown_delta:.0f}s cooldown={reboot_cooldown_seconds}s"
                                )
                                continue
                        if len(state.auto_reboot_timestamps) >= max_reboots_per_window:
                            record_auto_reboot_decision(
                                event_store,
                                result="window",
                                cooldown_remaining_seconds=None,
                                details={"max_reboots_per_window": max_reboots_per_window},
                                **decision_context,
                            )
                            log(
                                f"[AUTO-REBOOT] blocked_by=window miner={name_display} "
                                f"window_count={len(state.auto_reboot_timestamps)} window_seconds={auto_reboot_window_seconds}"
                            )
                            if not state.degraded_mode:
                                state.degraded_mode = True
                                log(
                                    f"[DEGRADED] {name_display} ({host}) limite auto-reboot alcanzado."
                                )
                                if (not qa_mode) or qa_notify:
                                    send_telegram(
                                        bot_token,
                                        str(chat_id),
                                        f"DEGRADED: {name_display} limite auto-reboot alcanzado.",
                                        "STATE_CHANGE",
                                        "degraded",
                                    )
                            continue
                        # Spec 057: Intervention Governance Guard (Level 2 Auto-Reboot - STATE_LOW)
                        from app.governance.intervention_policy import ACTION_REBOOT_L2, should_allow_intervention
                        gov_obj = getattr(state, "intervention_gov", None) or globals().get("_GLOBAL_INTERVENTION_GOV")
                        if gov_obj is not None:
                            _allowed, _reason = should_allow_intervention(ACTION_REBOOT_L2, gov_obj, now_ts)
                            if not _allowed:
                                record_auto_reboot_decision(
                                    event_store,
                                    result="interventions_blocked",
                                    cooldown_remaining_seconds=None,
                                    details={"reason": _reason, "trigger": "state_low"},
                                    **decision_context,
                                )
                                log(f"[AUTO-REBOOT] blocked_by=intervention_governance miner={name_display} reason={_reason}")
                                continue
                        if qa_mode and not qa_allow_actions:
                            record_auto_reboot_decision(
                                event_store,
                                result="qa",
                                cooldown_remaining_seconds=None,
                                details={"qa_allow_actions": qa_allow_actions},
                                **decision_context,
                            )
                            log(f"[AUTO-REBOOT] blocked_by=qa miner={name_display}")
                            if qa_notify:
                                send_telegram(
                                    bot_token,
                                    str(chat_id),
                                    "Accion bloqueada (QA). Habilita qa_allow_real_actions=true para permitir reboots reales.",
                                    "ERROR",
                                    "qa_block",
                                )
                            continue
                        ok, msg = run_hashcore_cli(hashcore_cfg, miner, "reboot", config, qa_mode, qa_allow_actions)
                        record_auto_reboot_decision(
                            event_store,
                            result="executed" if ok else "failed",
                            cooldown_remaining_seconds=None,
                            details={"message": _short_text(msg, 120)},
                            **decision_context,
                        )
                        record_action_outcome(
                            event_store,
                            occurred_ts=now_ts,
                            miner=miner,
                            action="reboot",
                            source="auto",
                            ok=ok,
                            message=msg,
                        )
                        if ok:
                            state.last_auto_reboot_ts = now_ts
                            state.auto_reboot_timestamps.append(now_ts)
                            state.low_since_ts = None
                            state.auto_restart_count = 0
                            if low_sustained_seconds % 60 == 0:
                                window_label = f"{int(low_sustained_seconds / 60)} min"
                            else:
                                window_label = f"{low_sustained_seconds}s"
                            log(
                                f"[AUTO-REBOOT] {name_display} LOW por {window_label}."
                            )
                            if (not qa_mode) or qa_notify:
                                window_label = f"{low_sustained_seconds}s"
                                qa_suffix = " (QA)" if qa_mode else ""
                                send_telegram(
                                    bot_token,
                                    str(chat_id),
                                    f"AUTO-REBOOT{qa_suffix}: {name_display} LOW por {window_label} "
                                    f"({format_rate(rate_ths)} < {threshold_ths:.2f} TH/s) -> reboot enviado\n"
                                    "Diagnostico: /why",
                                    "REBOOT",
                                    "auto_reboot",
                                )
                        else:
                            if (not qa_mode) or qa_notify:
                                key = f"{name}|{host}:{port}"
                                last = _CLI_MISSING_NOTIFIED.get(key, 0.0)
                                if "no encontrado" in msg.lower():
                                    if (now_ts - last) >= 3600:
                                        _CLI_MISSING_NOTIFIED[key] = now_ts
                                        send_telegram(
                                            bot_token,
                                            str(chat_id),
                                            f"AUTO-REBOOT FAILED: {name_display}. {msg}\nDiagnostico: /why",
                                            "ERROR",
                                            "auto_reboot_failed",
                                        )
                                else:
                                    send_telegram(
                                        bot_token,
                                        str(chat_id),
                                        f"AUTO-REBOOT FAILED: {name_display}. {msg}\nDiagnostico: /why",
                                        "ERROR",
                                        "auto_reboot_failed",
                                    )
                elif (
                    new_state == STATE_HASHBOARD
                    and state.hashboard_since_ts
                    and auto_reboot_hashboard_enabled
                ):
                    if not auto_reboot_signal_allows_evaluation(
                        new_state,
                        state.low_since_ts,
                        auto_reboot_signal,
                        hashboard_since_ts=state.hashboard_since_ts,
                        active_boards=active_boards,
                        expected_boards=expected_boards,
                        allow_partial_hashboard=auto_reboot_hashboard_partial_enabled,
                        hashboard_reboot_enabled=auto_reboot_hashboard_enabled,
                    ):
                        reset_sustained_hashboard_if_ineligible(
                            state,
                            auto_reboot_signal,
                            active_boards,
                            expected_boards,
                            auto_reboot_hashboard_partial_enabled,
                        )
                    elif startup_guard_active:
                        record_auto_reboot_decision(
                            event_store,
                            result="startup_guard",
                            cooldown_remaining_seconds=None,
                            details={
                                "startup_guard_seconds": startup_guard_seconds,
                                "trigger": "hashboard_failure",
                            },
                            **decision_context,
                        )
                        log(
                            f"[AUTO-REBOOT] blocked_by=startup_guard miner={name_display} "
                            f"since_start={now_ts - process_start_ts:.1f}s guard={startup_guard_seconds}s trigger=hashboard_failure"
                        )
                    elif (now_ts - state.hashboard_since_ts) < auto_reboot_hashboard_sustained_seconds:
                        hashboard_elapsed = now_ts - state.hashboard_since_ts
                        record_auto_reboot_decision(
                            event_store,
                            result="not_sustained",
                            cooldown_remaining_seconds=None,
                            details={
                                "trigger": "hashboard_failure",
                                "active_boards": active_boards,
                                "expected_boards": expected_boards,
                                "required_seconds": auto_reboot_hashboard_sustained_seconds,
                                "elapsed_seconds": int(hashboard_elapsed),
                            },
                            **decision_context,
                        )
                        log(
                            f"[AUTO-REBOOT] blocked_by=not_sustained miner={name_display} "
                            f"trigger=hashboard_failure boards={active_boards}/{expected_boards} "
                            f"elapsed={hashboard_elapsed:.0f}s required={auto_reboot_hashboard_sustained_seconds}s"
                        )
                    elif not interlock_decision.allowed:
                        interlock_reason = interlock_decision.reason or "safety_interlock"
                        affected_miners = list(interlock_decision.affected_miners)
                        record_auto_reboot_decision(
                            event_store,
                            result=interlock_reason,
                            cooldown_remaining_seconds=None,
                            details={
                                "trigger": "hashboard_failure",
                                "affected_miners": affected_miners,
                                "affected_count": len(affected_miners),
                                "fleet_min_affected": auto_reboot_fleet_guard_min_affected,
                                "fleet_snapshot_age_seconds": (
                                    interlock_decision.fleet_snapshot_age_seconds
                                ),
                                "max_temp_c": interlock_decision.max_temp_c,
                                "thermal_limit_c": auto_reboot_max_temp_c,
                                "chains_transitioning_count": (
                                    interlock_decision.chains_transitioning_count
                                ),
                                "firmware_transition_guard_enabled": (
                                    auto_reboot_firmware_transition_guard_enabled
                                ),
                                "hashboard_timer_reset": bool(
                                    auto_reboot_firmware_transition_guard_enabled
                                    and (interlock_decision.chains_transitioning_count or 0) > 0
                                ),
                            },
                            **decision_context,
                        )
                        if (
                            auto_reboot_firmware_transition_guard_enabled
                            and (interlock_decision.chains_transitioning_count or 0) > 0
                        ):
                            state.hashboard_since_ts = now_ts
                        if interlock_reason == "high_temperature":
                            log(
                                f"[AUTO-REBOOT] blocked_by=high_temperature miner={name_display} "
                                f"max_temp_c={interlock_decision.max_temp_c} "
                                f"limit_c={auto_reboot_max_temp_c:.1f}"
                            )
                        elif interlock_reason == "firmware_transition":
                            log(
                                f"[AUTO-REBOOT] blocked_by=firmware_transition miner={name_display} "
                                f"transitioning_chains={interlock_decision.chains_transitioning_count} "
                                f"hashboard_timer_reset=true"
                            )
                        else:
                            log(
                                f"[AUTO-REBOOT] blocked_by=fleet_incident miner={name_display} "
                                f"affected_count={len(affected_miners)} "
                                f"min_affected={auto_reboot_fleet_guard_min_affected} "
                                f"snapshot_age={interlock_decision.fleet_snapshot_age_seconds} "
                                f"affected={','.join(affected_miners)}"
                            )
                    else:
                        skew_tolerance_seconds = 10
                        last_reboot_ts = None
                        if state.last_manual_reboot_ts is not None:
                            last_reboot_ts = state.last_manual_reboot_ts
                        if state.last_auto_reboot_ts is not None:
                            last_reboot_ts = (
                                state.last_auto_reboot_ts
                                if last_reboot_ts is None
                                else max(last_reboot_ts, state.last_auto_reboot_ts)
                            )
                        if last_reboot_ts is not None and last_reboot_ts > now_ts + skew_tolerance_seconds:
                            log(
                                f"[WARN] last_reboot_ts ahead of clock "
                                f"miner={name_display} last_reboot_ts={last_reboot_ts} now={now_ts}"
                            )
                            last_reboot_ts = now_ts
                        if last_reboot_ts is not None:
                            cooldown_delta = max(0.0, now_ts - last_reboot_ts)
                            if cooldown_delta < reboot_cooldown_seconds:
                                cooldown_remaining = max(
                                    0.0,
                                    reboot_cooldown_seconds - cooldown_delta,
                                )
                                record_auto_reboot_decision(
                                    event_store,
                                    result="cooldown",
                                    cooldown_remaining_seconds=cooldown_remaining,
                                    details={
                                        "cooldown_seconds": reboot_cooldown_seconds,
                                        "trigger": "hashboard_failure",
                                    },
                                    **decision_context,
                                )
                                log(
                                    f"[AUTO-REBOOT] blocked_by=cooldown miner={name_display} "
                                    f"trigger=hashboard_failure cooldown_delta={cooldown_delta:.0f}s cooldown={reboot_cooldown_seconds}s"
                                )
                                continue
                        if len(state.auto_reboot_timestamps) >= max_reboots_per_window:
                            record_auto_reboot_decision(
                                event_store,
                                result="window",
                                cooldown_remaining_seconds=None,
                                details={
                                    "max_reboots_per_window": max_reboots_per_window,
                                    "trigger": "hashboard_failure",
                                },
                                **decision_context,
                            )
                            log(
                                f"[AUTO-REBOOT] blocked_by=window miner={name_display} "
                                f"trigger=hashboard_failure window_count={len(state.auto_reboot_timestamps)} window_seconds={auto_reboot_window_seconds}"
                            )
                            if not state.degraded_mode:
                                state.degraded_mode = True
                                log(
                                    f"[DEGRADED] {name_display} ({host}) limite auto-reboot alcanzado."
                                )
                                if (not qa_mode) or qa_notify:
                                    send_telegram(
                                        bot_token,
                                        str(chat_id),
                                        f"DEGRADED: {name_display} limite auto-reboot alcanzado.",
                                        "STATE_CHANGE",
                                        "degraded",
                                    )
                            continue
                        # Spec 057: Intervention Governance Guard (Level 2 Auto-Reboot - STATE_HASHBOARD)
                        from app.governance.intervention_policy import ACTION_REBOOT_L2, should_allow_intervention
                        gov_obj = getattr(state, "intervention_gov", None) or globals().get("_GLOBAL_INTERVENTION_GOV")
                        if gov_obj is not None:
                            _allowed, _reason = should_allow_intervention(ACTION_REBOOT_L2, gov_obj, now_ts)
                            if not _allowed:
                                record_auto_reboot_decision(
                                    event_store,
                                    result="interventions_blocked",
                                    cooldown_remaining_seconds=None,
                                    details={"reason": _reason, "trigger": "hashboard_failure"},
                                    **decision_context,
                                )
                                log(f"[AUTO-REBOOT] blocked_by=intervention_governance miner={name_display} reason={_reason} trigger=hashboard_failure")
                                continue
                        if qa_mode and not qa_allow_actions:
                            record_auto_reboot_decision(
                                event_store,
                                result="qa",
                                cooldown_remaining_seconds=None,
                                details={
                                    "qa_allow_actions": qa_allow_actions,
                                    "trigger": "hashboard_failure",
                                },
                                **decision_context,
                            )
                            log(f"[AUTO-REBOOT] blocked_by=qa miner={name_display} trigger=hashboard_failure")
                            if qa_notify:
                                send_telegram(
                                    bot_token,
                                    str(chat_id),
                                    "Accion bloqueada (QA). Habilita qa_allow_real_actions=true para permitir reboots reales.",
                                    "ERROR",
                                    "qa_block",
                                )
                            continue
                        ok, msg = run_hashcore_cli(hashcore_cfg, miner, "reboot", config, qa_mode, qa_allow_actions)
                        record_auto_reboot_decision(
                            event_store,
                            result="executed" if ok else "failed",
                            cooldown_remaining_seconds=None,
                            details={
                                "trigger": "hashboard_failure",
                                "message": _short_text(msg, 120),
                                "active_boards": active_boards,
                                "expected_boards": expected_boards,
                            },
                            **decision_context,
                        )
                        record_action_outcome(
                            event_store,
                            occurred_ts=now_ts,
                            miner=miner,
                            action="reboot",
                            source="auto",
                            ok=ok,
                            message=msg,
                        )
                        if ok:
                            state.last_auto_reboot_ts = now_ts
                            state.auto_reboot_timestamps.append(now_ts)
                            state.low_since_ts = None
                            state.hashboard_since_ts = None
                            state.auto_restart_count = 0
                            if auto_reboot_hashboard_sustained_seconds % 60 == 0:
                                window_label = f"{int(auto_reboot_hashboard_sustained_seconds / 60)} min"
                            else:
                                window_label = f"{auto_reboot_hashboard_sustained_seconds}s"
                            log(
                                f"[AUTO-REBOOT] {name_display} HASHBOARD ({active_boards}/{expected_boards} placas) por {window_label}."
                            )
                            if (not qa_mode) or qa_notify:
                                qa_suffix = " (QA)" if qa_mode else ""
                                send_telegram(
                                    bot_token,
                                    str(chat_id),
                                    f"AUTO-REBOOT{qa_suffix}: {name_display} falla de placas ({active_boards}/{expected_boards}) sostenida por {window_label} -> reboot enviado\n"
                                    "Diagnostico: /why",
                                    "REBOOT",
                                    "auto_reboot",
                                )
                        else:
                            if (not qa_mode) or qa_notify:
                                key = f"{name}|{host}:{port}"
                                last = _CLI_MISSING_NOTIFIED.get(key, 0.0)
                                if "no encontrado" in msg.lower():
                                    if (now_ts - last) >= 3600:
                                        _CLI_MISSING_NOTIFIED[key] = now_ts
                                        send_telegram(
                                            bot_token,
                                            str(chat_id),
                                            f"AUTO-REBOOT FAILED: {name_display}. {msg}\nDiagnostico: /why",
                                            "ERROR",
                                            "auto_reboot_failed",
                                        )
                                else:
                                    send_telegram(
                                        bot_token,
                                        str(chat_id),
                                        f"AUTO-REBOOT FAILED: {name_display}. {msg}\nDiagnostico: /why",
                                        "ERROR",
                                        "auto_reboot_failed",
                                    )

                if not first_tick and new_state != prev_state:
                    if event_store is not None and event_store.available:
                        transition_event_id = event_store.record_event(
                            occurred_ts=now_ts,
                            miner_key=state_key,
                            miner_name=name_display,
                            host=host,
                            event_type="state_transition",
                            severity="info" if new_state == STATE_OK else "warning",
                            previous_state=prev_state,
                            new_state=new_state,
                            rate_ths=rate_ths,
                            threshold_ths=threshold_ths,
                            summary=f"{prev_state} -> {new_state}",
                            details={
                                "responded": responded,
                                "active_boards": active_boards,
                                "expected_boards": expected_boards,
                            },
                        )
                    if prev_state == STATE_OFFLINE and new_state == STATE_LOW:
                        log(
                            f"[STATE] {name} ({host}:{port}) OFFLINE -> LOW "
                            f"{format_rate(rate_ths)} < {threshold_ths:.2f} TH/s "
                            f"({now_str()})"
                        )
                    elif new_state == STATE_OFFLINE:
                        log(
                            f"[STATE] {name} ({host}:{port}) OK/LOW -> OFFLINE "
                            f"intentos={state.offline_streak} ({now_str()})"
                        )
                    elif new_state == STATE_HASHBOARD:
                        log(
                            f"[STATE] {name} ({host}:{port}) -> HASHBOARD "
                            f"boards={active_boards}/{expected_boards} ({now_str()})"
                        )
                    elif new_state == STATE_LOW:
                        log(
                            f"[STATE] {name} ({host}:{port}) OK/OFFLINE -> LOW "
                            f"{format_rate(rate_ths)} < {threshold_ths:.2f} TH/s "
                            f"({now_str()})"
                        )
                    elif new_state == STATE_OK and prev_state in (STATE_LOW, STATE_OFFLINE, STATE_HASHBOARD):
                        log(
                            f"[STATE] {name} ({host}:{port}) {prev_state} -> OK "
                            f"{format_rate(rate_ths)} >= {threshold_ths:.2f} TH/s "
                            f"({now_str()})"
                        )

                is_snoozed = (state.snooze_until_ts is not None and now_ts < state.snooze_until_ts) or getattr(state, "is_shutdown_maintenance", False)
                if (
                    not is_snoozed
                    and state.reboot_pending_until
                    and new_state in (STATE_LOW, STATE_OFFLINE)
                    and (now_ts - state.last_reboot_ts) >= reboot_cooldown_seconds
                ):
                    reboot_names_tick.append(name)
                    state.last_reboot_ts = now_ts
                    state.reboot_pending_until = 0.0
                    state.reboot_pending_reason = ""
                    state.reboot_pending_elapsed = None
                elif is_snoozed and state.reboot_pending_until:
                    log(f"AUTO_REBOOT_SNOOZED miner={name} until={state.snooze_until_ts}")

                episode_previous_state = prev_state
                episode_state = new_state
                current_signal_healthy = (
                    responded
                    and rate_ths is not None
                    and math.isfinite(float(rate_ths))
                    and float(rate_ths) >= threshold_ths
                    and (active_boards is None or active_boards >= expected_boards)
                )
                if (first_tick or startup_grace_active) and current_signal_healthy:
                    # Do not create a notification episode from persisted hysteresis.
                    episode_previous_state = STATE_OK
                    episode_state = STATE_OK
                episode_notifications.observe(
                    miner_key=state_key,
                    name_display=name_display,
                    host=host,
                    previous_state=episode_previous_state,
                    state=episode_state,
                    responded=responded,
                    rate_ths=rate_ths,
                    threshold_ths=threshold_ths,
                    active_boards=active_boards,
                    expected_boards=expected_boards,
                    now_ts=now_ts,
                    transition_event_id=transition_event_id,
                    restart=restart_observation,
                )

                snooze_tag = ""
                if getattr(state, "is_shutdown_maintenance", False):
                    snooze_tag = " [⏸️ DETENIDO]"
                elif state.snooze_until_ts is not None and now_ts < state.snooze_until_ts:
                    from app.telegram.snooze import format_snooze_tag
                    snooze_tag = format_snooze_tag(state, now_ts)
                status_text_line = format_current_status_line(
                    name_display=name_display,
                    host=host,
                    confirmed_state=new_state,
                    responded=responded,
                    rate_ths=rate_ths,
                    threshold_ths=threshold_ths,
                    active_boards=active_boards,
                    expected_boards=expected_boards,
                    detail_event_id=episode_notifications.detail_event_id(
                        state_key
                    ),
                )
                if snooze_tag:
                    status_text_line += snooze_tag
                miner_lines.append(status_text_line)
                if startup_lines is not None:
                    startup_lines.append(
                        format_current_status_line(
                            name_display=name_display,
                            host=host,
                            confirmed_state=STATE_OK,
                            responded=responded,
                            rate_ths=rate_ths,
                            threshold_ths=threshold_ths,
                            active_boards=active_boards,
                            expected_boards=expected_boards,
                        )
                    )
                if state.degraded_mode and not ((state.snooze_until_ts is not None and now_ts < state.snooze_until_ts) or getattr(state, "is_shutdown_maintenance", False)):
                    degraded_candidates.append(state)

            previous_tick_signals = current_tick_signals.copy()
            previous_tick_signals_ts = time.time()
            status_lines = [
                f"STATUS ({now_str()})",
                "",
            ]
            status_lines.extend(miner_lines)
            with snapshot_lock:
                snapshot_ref["value"] = "\n".join(status_lines)

            # Spec 051: Fast Phase Drop vs Connectivity Discriminator
            phase_drop_assessment = None
            if not first_tick and (tick_failed_miners or _ACTIVE_PHASE_DROPS):
                try:
                    phase_drop_assessment = process_phase_drop_cycle(
                        miners=valid_miners,
                        states=states,
                        tick_failed_miners=tick_failed_miners,
                        tick_responded_miners=tick_responded_miners,
                        maintenance_miner_ids=tick_maintenance_ids,
                        phase_drop_config=parse_phase_drop_config(config),
                        last_alert_ts=_LAST_PHASE_DROP_ALERT_TS,
                        active_phase_drops=_ACTIVE_PHASE_DROPS,
                        now_ts=now_ts,
                        fails_before_alert=fails_before_alert,
                        send_telegram_fn=send_telegram,
                        record_event_fn=lambda **kw: record_action_outcome(
                            event_store,
                            occurred_ts=kw.get("occurred_ts", time.time()),
                            miner={"name": kw.get("miner_name", ""), "host": kw.get("host", "")},
                            action=kw.get("event_type", "electrical_phase_drop"),
                            source="phase_drop_discriminator",
                            ok=True,
                            message=kw.get("summary", ""),
                        ),
                        log_fn=log,
                        bot_token=bot_token,
                        chat_id=str(chat_id),
                        qa_mode=qa_mode,
                        qa_notify=qa_notify,
                    )
                except Exception as _pd_exc:
                    log(f"[PHASE_DROP_ERR] Phase drop cycle error: {type(_pd_exc).__name__}: {_pd_exc}")

            episode_batch = episode_notifications.pop_due(now_ts=now_ts)
            if phase_drop_assessment and phase_drop_assessment.verdict in (
                PhaseDropVerdict.PHASE_DROP_ELEVATOR,
                PhaseDropVerdict.PHASE_DROP_FLEET,
            ):
                _aff_set = set(phase_drop_assessment.failed_miners)
                if not episode_batch.empty and _aff_set:
                    episode_batch.opened = [
                        ep for ep in episode_batch.opened
                        if ep.name_display not in _aff_set and ep.miner_key not in _aff_set
                    ]
            if not notify_persistent_outage:
                episode_batch.persistent.clear()

            notification_sent = False

            # Spec 066: Cold-Boot Fleet Grace Period — Evaluación de estabilización y notificación
            fleet_healthy = is_fleet_warmup_complete(
                miners=valid_miners,
                states=states,
                threshold_ths=startup_fleet_grace_threshold_ths,
                expected_boards=expected_boards,
            )
            should_send_startup = False
            is_fleet_restored = False

            if not startup_notified:
                if startup_fleet_grace_period_seconds == 0:
                    if first_tick:
                        should_send_startup = True
                else:
                    if fleet_healthy:
                        should_send_startup = True
                        is_fleet_restored = True
                        startup_grace_active = False
                    elif (now_ts - process_start_ts) >= startup_fleet_grace_period_seconds:
                        should_send_startup = True
                        is_fleet_restored = False
                        startup_grace_active = False

            if should_send_startup:
                startup_notified = True
                if notify_startup and ((not qa_mode) or qa_notify):
                    if is_fleet_restored:
                        restored_lines = [
                            f"🟢 FLOTA RESTABLECIDA ({now_str()})",
                            "",
                            "Supervisión activa tras retorno de energía:",
                        ]
                        for m in valid_miners:
                            m_name = m.get("name", "")
                            m_host = m.get("host", "")
                            m_sk = f"{m_name}|{m_host}:{m.get('port', 4028)}"
                            m_st = states.get(m_sk)
                            m_rate = getattr(m_st, "last_rate_ths", None) if m_st else None
                            m_temp = getattr(m_st, "last_max_chip_temp", None) if m_st else None
                            restored_lines.append(format_fleet_restored_line(m_name, m_rate, m_temp))
                        send_telegram(
                            bot_token,
                            str(chat_id),
                            "\n".join(restored_lines),
                            "STARTUP",
                            "startup",
                        )
                        log(
                            f"[COLD_BOOT_GRACE] Flota restablecida y estabilizada en "
                            f"{now_ts - process_start_ts:.1f}s. Notificación enviada."
                        )
                        if event_store is not None and event_store.available:
                            event_store.record_event(
                                occurred_ts=now_ts,
                                miner_key="fleet",
                                miner_name="FLOTA",
                                host="",
                                event_type="startup_fleet_grace_completed",
                                severity="info",
                                summary=f"Flota restablecida en {now_ts - process_start_ts:.1f}s",
                                details={
                                    "elapsed_seconds": now_ts - process_start_ts,
                                    "threshold_ths": startup_fleet_grace_threshold_ths,
                                },
                            )
                    else:
                        hdr = f"STARTUP ({now_str()})"
                        if startup_fleet_grace_period_seconds > 0:
                            hdr = f"STARTUP ({now_str()}) [FIN PERÍODO DE GRACIA]"
                        message_lines = [hdr, ""]
                        message_lines.extend(startup_lines or miner_lines)
                        send_telegram(
                            bot_token,
                            str(chat_id),
                            "\n".join(message_lines),
                            "STARTUP",
                            "startup",
                        )
                        log(f"[COLD_BOOT_GRACE] Notificación STARTUP enviada tras {now_ts - process_start_ts:.1f}s.")
                        if startup_fleet_grace_period_seconds > 0 and event_store is not None and event_store.available:
                            event_store.record_event(
                                occurred_ts=now_ts,
                                miner_key="fleet",
                                miner_name="FLOTA",
                                host="",
                                event_type="startup_fleet_grace_expired",
                                severity="warning",
                                summary=f"Período de gracia finalizado tras {now_ts - process_start_ts:.1f}s",
                                details={
                                    "elapsed_seconds": now_ts - process_start_ts,
                                    "grace_period_seconds": startup_fleet_grace_period_seconds,
                                },
                            )
                    episode_notifications.acknowledge_active_initials()
                    notification_sent = True
                else:
                    episode_notifications.acknowledge_active_initials()

            if first_tick:
                # Spec 044 C2: On startup/NSSM restart, reconcile silent_mode state.
                # If a silent mode was active when the service stopped, it may have expired
                # during downtime. Purge expired silences immediately so hardware is not left
                # in a reduced-fan state with full power.
                _sm_expired_miners = []
                _sm_still_active_miners = []
                with state_lock:
                    for _m in valid_miners:
                        _sk = f"{_m.get('name','')}|{_m.get('host','')}:{_m.get('port',4028)}"
                        _st = states.get(_sk)
                        if _st is None or not _st.silent_mode_active:
                            continue
                        if _st.silent_mode_revert_ts is not None and now_ts >= _st.silent_mode_revert_ts:
                            # Expired during downtime — cancel silently
                            _st.silent_mode_active = False
                            _st.silent_mode_revert_ts = None
                            _sm_expired_miners.append(_m.get("name", _sk))
                            log(f"[SILENT_MODE] Expired during downtime, purged on startup: miner={_m.get('name', _sk)}")
                        else:
                            _sm_still_active_miners.append(_m.get("name", _sk))
                if _sm_expired_miners:
                    _exp_list = ", ".join(_sm_expired_miners)
                    _sm_exp_msg = (
                        f"⏰ *Modo Silencio expirado durante reinicio del servicio*\n"
                        f"Mineros restaurados a supervisión normal: {_exp_list}\n"
                        "_Los ventiladores se restaurarán en el próximo ciclo del gobernador._"
                    )
                    if (not qa_mode) or qa_notify:
                        send_telegram(bot_token, str(chat_id), _sm_exp_msg, "SILENT_MODE_EXPIRED", "silent_mode_expired_restart")
                if _sm_still_active_miners:
                    log(f"[SILENT_MODE] Restored active silence on startup: {', '.join(_sm_still_active_miners)}")

            # Spec 067: Network Storm Suppression — suprimir episodios de desconexión
            # si el gateway estuvo caído recientemente (parpadeo de switch o access point).
            # Solo suprime alertas de STATE_OFFLINE: LOW, hashboard y temperatura se propagan siempre.
            _network_storm_active = (
                _gateway_heartbeat is not None
                and _gateway_heartbeat.is_recently_lost(
                    within_seconds=_network_storm_suppression_seconds
                )
            )
            if _network_storm_active and not episode_batch.empty:
                _storm_loss_elapsed = _gateway_heartbeat.gateway_loss_elapsed_s()
                _storm_elapsed_str = f"{_storm_loss_elapsed:.1f}s" if _storm_loss_elapsed is not None else "recently"
                _suppressed_opens = [
                    ep for ep in episode_batch.opened
                    if getattr(ep, "state", None) == STATE_OFFLINE
                ]
                if _suppressed_opens:
                    log(
                        f"[NETWORK_STORM_SUPPRESSED] gateway_lost={_storm_elapsed_str} "
                        f"— suprimiendo {len(_suppressed_opens)} alerta(s) de desconexion. "
                        f"Mineros: {[ep.name_display for ep in _suppressed_opens]}"
                    )
                    episode_batch.opened = [
                        ep for ep in episode_batch.opened
                        if getattr(ep, "state", None) != STATE_OFFLINE
                    ]

            if not notification_sent and not episode_batch.empty and not startup_grace_active and ((not qa_mode) or qa_notify):
                from app.telegram.snooze import filter_snoozed_episodes
                filtered_batch = filter_snoozed_episodes(episode_batch, states, now_ts=now_ts)
                if not filtered_batch.empty:
                    # T013 (Spec 031): Attach an inline keyboard when the batch has
                    # exactly one opened episode, so the user can act directly from
                    # the alert without typing commands.
                    _ep_keyboard = None
                    if len(filtered_batch.opened) == 1 and not filtered_batch.persistent and not filtered_batch.recovered:
                        _ep_miner_id = filtered_batch.opened[0].name_display
                        try:
                            _ep_keyboard = build_alert_keyboard(_ep_miner_id)
                        except Exception:
                            _ep_keyboard = None
                    send_telegram(
                        bot_token,
                        str(chat_id),
                        render_episode_notification_batch(
                            filtered_batch,
                            now_ts=now_ts,
                        ),
                        "EPISODE_ALERT",
                        "irregular_episode",
                        reply_markup=_ep_keyboard,
                    )
                    notification_sent = True

            if not notification_sent:
                if notify_degraded_hourly and degraded_candidates:
                    ar_now = argentina_now()
                    if 6 <= ar_now.hour < 24:
                        hourly_needed = False
                        for st in degraded_candidates:
                            if (
                                st.last_hourly_status_ts is None
                                or (now_ts - st.last_hourly_status_ts) >= degraded_hourly_seconds
                            ):
                                hourly_needed = True
                                break
                        if hourly_needed:
                            if (not qa_mode) or qa_notify:
                                send_telegram(bot_token, str(chat_id), "\n".join(status_lines), "STATUS", "degraded_hourly")
                            for st in degraded_candidates:
                                st.last_hourly_status_ts = now_ts

            # ---------------------------------------------------------------
            # Scheduled Daily Executive Digest (Spec 034)
            # ---------------------------------------------------------------
            daily_digest_enabled = bool(config.get("daily_digest_enabled", True))
            daily_digest_time = str(config.get("daily_digest_time", "08:00"))
            if daily_digest_enabled and not first_tick and ((not qa_mode) or qa_notify):
                ar_now = argentina_now()
                from app.telegram.daily_digest import is_digest_due, fetch_daily_digest_metrics, format_daily_digest
                if is_digest_due(ar_now, daily_digest_time, _LAST_DAILY_DIGEST_DATE):
                    try:
                        db_p = resolve_db_path(config)
                        b_root = config.get("backup_root", "backups")
                        with state_lock:
                            digest_metrics = fetch_daily_digest_metrics(
                                db_path=db_p,
                                miners=miners,
                                now_ts=now_ts,
                                backup_root=b_root,
                                states=states,
                            )
                        today_ar_str = ar_now.strftime("%Y-%m-%d")
                        digest_msg = format_daily_digest(digest_metrics, date_str=ar_now.strftime("%d/%m/%Y"))
                        send_telegram(
                            bot_token,
                            str(chat_id),
                            digest_msg,
                            "DIGEST",
                            "scheduled_daily_digest",
                        )
                        _LAST_DAILY_DIGEST_DATE = today_ar_str
                        log(f"DAILY_DIGEST_SENT date={today_ar_str} time={daily_digest_time}")
                    except Exception as exc:
                        log(f"DAILY_DIGEST_ERR exc={exc}")

            if (
                event_store is not None
                and event_store.available
                and (now_ts - last_retention_ts) >= 86_400
            ):
                event_store.prune(
                    now_ts=now_ts,
                    sample_retention_days=telemetry_retention_days,
                    event_retention_days=event_retention_days,
                    decision_retention_days=decision_retention_days,
                )
                last_retention_ts = now_ts

            with last_update_lock:
                current_last_update_id = last_update_id_ref["value"]

            # Spec 044 T011/T012: Check silent_mode timer expiry every tick.
            # If revert_ts has passed, cancel the mode and notify.
            _sm_just_expired = []
            with state_lock:
                for _m in valid_miners:
                    _sk = f"{_m.get('name','')}|{_m.get('host','')}:{_m.get('port',4028)}"
                    _st = states.get(_sk)
                    if (
                        _st is not None
                        and _st.silent_mode_active
                        and _st.silent_mode_revert_ts is not None
                        and now_ts >= _st.silent_mode_revert_ts
                    ):
                        _st.silent_mode_active = False
                        _st.silent_mode_revert_ts = None
                        _sm_just_expired.append(_m.get("name", _sk))
                        log(f"[SILENT_MODE] Timer expired, mode cancelled: miner={_m.get('name', _sk)}")
            if _sm_just_expired:
                _exp_names = ", ".join(_sm_just_expired)
                _sm_rev_msg = (
                    f"⏰ *Modo Silencio finalizado* — Temporizador expirado\n"
                    f"Mineros: *{_exp_names}*\n"
                    f"🔊 Ventiladores restaurados a régimen de producción normal.\n"
                    f"_El Fan Governor retomará el control en el próximo tick._"
                )
                if (not qa_mode) or qa_notify:
                    send_telegram(bot_token, str(chat_id), _sm_rev_msg, "SILENT_MODE_EXPIRED", "silent_mode_timer_expired")


            # Dynamic Vnish overclock & autoswitch settings sync (every 300s)
            try:
                refresh_vnish_overclock_settings(
                    miners=valid_miners,
                    states=states,
                    state_lock=state_lock,
                    vnish_pw=str(config.get("vnish_api_password", "admin")),
                    timeout=float(config.get("fan_governor_request_timeout", 2.5)),
                    now_ts=now_ts,
                )
            except Exception as _sync_exc:
                log(f"[VNISH_SYNC_ERR] Vnish sync failed: {type(_sync_exc).__name__}: {_sync_exc}")

            # Spec 039/044: Fan Governor cycle + C4 Thermal Guard
            try:
                _gov_thermal_events = execute_governor_cycle(
                    miners=valid_miners,
                    states=states,
                    state_lock=state_lock,
                    config=config,
                    now_ts=now_ts,
                    qa_mode=qa_mode,
                )
                # C4: If any miner had its silent_mode cancelled by thermal guard,
                # persist state immediately and notify Telegram.
                if _gov_thermal_events:
                    with state_lock:
                        _payload = _build_state_payload(states, current_last_update_id)
                    _flush_state_payload(state_path, _payload)
                    for _tg_name, _tg_temp, _tg_action, _tg_prev_max in _gov_thermal_events:
                        _temp_str = f"{_tg_temp:.1f}°C" if _tg_temp is not None else "N/D"
                        _tg_msg = (
                            f"🌡️ *⚠️ MODO SILENCIO ANULADO POR GUARDIÁN TÉRMICO*\n"
                            f"Minero: *{_tg_name}*\n"
                            f"Temperatura detectada: *{_temp_str}* (Umbral: {config.get('fan_governor_emergency_temp_c', 83.5)}°C)\n"
                            f"Techo acústico anterior: {_tg_prev_max}% PWM\n"
                            f"Acción del Gobernador: `{_tg_action}`\n"
                            f"🔊 *Ventiladores forzados al 100%*. Modo silencio cancelado permanentemente hasta nueva activación."
                        )
                        if (not qa_mode) or qa_notify:
                            send_telegram(bot_token, str(chat_id), _tg_msg, "THERMAL_GUARD", "thermal_guard_silent_cancel")
                        log(f"[THERMAL_GUARD] Telegram notified for miner={_tg_name} temp={_temp_str}")
            except Exception as _gov_exc:
                log(f"[GOV_ERR] Governor cycle failed: {type(_gov_exc).__name__}: {_gov_exc}")

            # Spec 040: Dynamic Preset Balancer cycle — optimizes power & voltage sensitivity
            try:
                execute_balancer_cycle(
                    miners=valid_miners,
                    states=states,
                    state_lock=state_lock,
                    config=config,
                    now_ts=now_ts,
                    qa_mode=qa_mode,
                    db_path=resolve_db_path(config),
                    send_telegram_fn=send_telegram,
                    bot_token=bot_token,
                    chat_id=str(chat_id),
                )
            except Exception as _bal_exc:
                log(f"[BALANCER_ERR] Balancer cycle failed: {type(_bal_exc).__name__}: {_bal_exc}")

            # Spec 050: Post-Blackout Recovery Guard cycle
            try:
                from app.governance.post_blackout_guard import execute_post_blackout_cycle
                execute_post_blackout_cycle(
                    miners=valid_miners,
                    states=states,
                    state_lock=state_lock,
                    config=config,
                    now_ts=now_ts,
                    process_start_ts=process_start_ts,
                    tracker=_POST_BLACKOUT_TRACKER,
                    send_telegram_fn=send_telegram,
                    record_event_fn=lambda **kw: record_action_outcome(
                        event_store,
                        occurred_ts=time.time(),
                        miner=kw.get("miner"),
                        action=kw.get("action"),
                        source=kw.get("source", "guard"),
                        ok=kw.get("ok", True),
                        message=kw.get("message", ""),
                    ),
                    log_fn=log,
                    bot_token=bot_token,
                    chat_id=str(chat_id),
                    qa_mode=qa_mode,
                    qa_notify=qa_notify,
                )
            except Exception as _pbr_exc:
                log(f"[PBR_ERR] Post-blackout recovery cycle failed: {type(_pbr_exc).__name__}: {_pbr_exc}")

            # Spec 052: Scheduled Electrical Maintenance Windows & Soft Pre-Ramp
            with state_lock:
                _sched_win = _ACTIVE_SCHEDULED_WINDOW
            if _sched_win is not None and not first_tick:
                try:
                    _updated_win = process_maintenance_scheduler_cycle(
                        window=_sched_win,
                        miners=valid_miners,
                        states=states,
                        config=config,
                        now_ts=now_ts,
                        send_telegram_fn=send_telegram,
                        record_event_fn=lambda **kw: record_action_outcome(
                            event_store,
                            occurred_ts=time.time(),
                            miner={"name": "FLOTA", "host": ""},
                            action=kw.get("action", "scheduled_maintenance"),
                            source=kw.get("source", "scheduler"),
                            ok=kw.get("ok", True),
                            message=kw.get("message", ""),
                        ),
                        log_fn=log,
                        save_state_fn=save_state,
                        state_path=state_path,
                        current_last_update_id=current_last_update_id,
                        bot_token=bot_token,
                        chat_id=str(chat_id),
                        qa_mode=qa_mode,
                        qa_notify=qa_notify,
                    )
                    with state_lock:
                        _ACTIVE_SCHEDULED_WINDOW = _updated_win
                except Exception as _sch_exc:
                    log(f"[SCHEDULER_ERR] Maintenance scheduler cycle failed: {type(_sch_exc).__name__}: {_sch_exc}")

            # Spec 057: Check automatic reactivation of intervention governance timer
            if _GLOBAL_INTERVENTION_GOV.expires_at_ts is not None and _GLOBAL_INTERVENTION_GOV.is_expired(now_ts):
                from app.governance.intervention_policy import apply_governance_toggle
                _GLOBAL_INTERVENTION_GOV = apply_governance_toggle(_GLOBAL_INTERVENTION_GOV, "all_on", now_ts)
                with state_lock:
                    for st in states.values():
                        st.intervention_gov = _GLOBAL_INTERVENTION_GOV
                log("[INTERVENTIONS] Temporary suppression expired. Interventions automatically restored to ALL ON.")
                send_telegram(
                    bot_token,
                    str(chat_id),
                    "🛡️ *INTERVENCIONES REACTIVADAS AUTOMÁTICAMENTE*\n\nFinalizó la ventana temporal de suspensión. Todos los actuadores automáticos (Reinicios L1/L2, Fan Governor, Presets, Contingencia) han sido restaurados.",
                    "STATUS",
                    "interventions_auto_reactivated",
                    is_command=True,
                )

            # Spec 057: Adaptive Elevator Contingency - Periodic Step-Up Soak Evaluation
            if _ELEVATOR_CONTINGENCY_STATES:
                try:
                    from app.governance.intervention_policy import ACTION_CONTINGENCY, should_allow_intervention
                    from app.governance.adaptive_contingency import evaluate_canary_contingency, ACTION_NO_ACTION
                    gov_obj = globals().get("_GLOBAL_INTERVENTION_GOV")
                    cont_allowed, _ = should_allow_intervention(ACTION_CONTINGENCY, gov_obj, now_ts) if gov_obj else (True, "")
                    if cont_allowed:
                        with state_lock:
                            _contingency_items = list(_ELEVATOR_CONTINGENCY_STATES.items())
                        for grp, c_st in _contingency_items:
                            if c_st.active:
                                _grp_presets = {}
                                with state_lock:
                                    for _m in valid_miners:
                                        if (_m.get("electrical_group") or _m.get("group")) == grp:
                                            _mn = _m.get("name")
                                            _sk = f"{_m.get('name','')}|{_m.get('host','')}:{_m.get('port',4028)}"
                                            _st = states.get(_sk)
                                            _pr = getattr(_st, "balancer_preset", None) if _st else None
                                            _grp_presets[_mn] = _pr or _m.get("max_preset", "2700W")
                                _dec = evaluate_canary_contingency(
                                    event_type="soak_tick",
                                    miner_name="",
                                    group_name=grp,
                                    current_presets=_grp_presets,
                                    now_ts=now_ts,
                                    group_state=c_st,
                                )
                                if _dec.updated_group_state:
                                    with state_lock:
                                        _ELEVATOR_CONTINGENCY_STATES[grp] = _dec.updated_group_state
                                if _dec.action != ACTION_NO_ACTION:
                                    if _dec.requires_write and not qa_mode:
                                        from app.governance.adaptive_contingency import normalize_miner_name
                                        _tgt = next(
                                            (m_item for m_item in valid_miners
                                             if normalize_miner_name(m_item.get("name", "")) == normalize_miner_name(_dec.target_miner)),
                                            None
                                        )
                                        if _tgt:
                                            vnish_pw = str(config.get("vnish_api_password", "admin"))
                                            from app.vnish.client import safe_set_miner_preset
                                            _s_ok, _s_msg = safe_set_miner_preset(
                                                _tgt.get("host", ""),
                                                vnish_pw,
                                                _dec.target_preset,
                                                timeout=float(config.get("fan_governor_request_timeout", 2.5)),
                                                clamp_top_preset=True,
                                            )
                                            log(f"[CONTINGENCY_SOAK] Preset {_dec.target_preset} applied to {_dec.target_miner}: ok={_s_ok} msg={_s_msg}")
                                            _t_sk = f"{_tgt.get('name','')}|{_tgt.get('host','')}:{_tgt.get('port',4028)}"
                                            with state_lock:
                                                _t_st = states.get(_t_sk)
                                                if _t_st:
                                                    _t_st.balancer_preset = _dec.target_preset
                                    if _dec.notification_msg:
                                        send_telegram(
                                            bot_token,
                                            str(chat_id),
                                            _dec.notification_msg,
                                            "CONTINGENCY",
                                            f"contingency_soak_{grp}",
                                            is_command=True,
                                        )
                except Exception as _soak_exc:
                    log(f"[CONTINGENCY_SOAK_ERR] Soak evaluation error: {_soak_exc}")

            with state_lock:
                _payload = _build_state_payload(states, current_last_update_id)
            _flush_state_payload(state_path, _payload)
            if heartbeat_enabled:
                try:
                    completed_ts = time.time()
                    collector_age_seconds: Optional[float] = None
                    if event_store is not None and event_store.available:
                        collector_run = event_store.latest_collector_run()
                        if collector_run:
                            collector_completed_ts = float(
                                collector_run.get("completed_ts") or 0.0
                            )
                            if collector_completed_ts > 0:
                                collector_age_seconds = max(
                                    0.0, completed_ts - collector_completed_ts
                                )
                    tick_sequence += 1
                    write_heartbeat_atomic(
                        heartbeat_path,
                        MonitorHeartbeat(
                            pid=os.getpid(),
                            process_start_ts=process_start_ts,
                            tick_sequence=tick_sequence,
                            last_tick_completed_ts=completed_ts,
                            telegram_poller_ts=_TELEGRAM_POLLER_TS,
                            telegram_sender_ts=_TELEGRAM_SENDER_TS,
                            queue_depth=_TELEGRAM_QUEUE.qsize(),
                            collector_age_seconds=collector_age_seconds,
                        ),
                    )
                    if tick_sequence == 1 or heartbeat_error_logged:
                        log(
                            f"[LIVENESS] heartbeat path={heartbeat_path} "
                            f"schema=1 tick_sequence={tick_sequence}"
                        )
                    heartbeat_error_logged = False

                    # Spec 054: Periodic Hashboard Chain Telemetry Collection
                    if chain_telemetry_enabled and event_store is not None and event_store.available:
                        if (completed_ts - last_chain_collection_ts) >= chain_telemetry_interval_s:
                            last_chain_collection_ts = completed_ts
                            threading.Thread(
                                target=_async_collect_chain_telemetry,
                                args=(valid_miners, event_store, vnish_api_password, None, config, bot_token, chat_id, qa_mode, qa_notify),
                                daemon=True,
                                name="ChainTelemetryScheduled",
                            ).start()

                    # Spec 069: Periodic Predictive Chain Break Evaluation (PROP-008)
                    if predictive_chain_enabled and event_store is not None and event_store.available:
                        if (completed_ts - last_predictive_chain_eval_ts) >= predictive_chain_eval_interval_s:
                            last_predictive_chain_eval_ts = completed_ts
                            threading.Thread(
                                target=_async_evaluate_predictive_chain_break,
                                args=(valid_miners, event_store, states, state_lock, config, bot_token, chat_id, qa_mode, qa_notify),
                                daemon=True,
                                name="PredictiveChainBreakScheduled",
                            ).start()

                    # Spec 061: Periodic SQLite WAL Checkpoint Maintenance
                    if event_store is not None and event_store.available:
                        # Hourly PASSIVE checkpoint
                        if (completed_ts - last_wal_passive_ts) >= 3600.0:
                            last_wal_passive_ts = completed_ts
                            try:
                                cp_busy, cp_log, cp_done = event_store.checkpoint_wal("PASSIVE")
                                log(
                                    f"[EVENT_STORE] wal_checkpoint mode=PASSIVE "
                                    f"busy={cp_busy} log={cp_log} checkpointed={cp_done}"
                                )
                            except Exception as _wal_exc:
                                log(f"[EVENT_STORE_ERR] wal_checkpoint PASSIVE failed: {_wal_exc}")

                        # Daily TRUNCATE checkpoint during off-peak window (03:00 - 05:00 UTC)
                        now_utc = datetime.now(timezone.utc)
                        today_utc_str = now_utc.strftime("%Y-%m-%d")
                        if 3 <= now_utc.hour < 5 and last_wal_truncate_date != today_utc_str:
                            last_wal_truncate_date = today_utc_str
                            try:
                                cp_busy, cp_log, cp_done = event_store.checkpoint_wal("TRUNCATE")
                                log(
                                    f"[EVENT_STORE] wal_checkpoint mode=TRUNCATE "
                                    f"busy={cp_busy} log={cp_log} checkpointed={cp_done}"
                                )
                            except Exception as _wal_exc:
                                log(f"[EVENT_STORE_ERR] wal_checkpoint TRUNCATE failed: {_wal_exc}")

                    if config.get("metrics_snapshot_enabled", False):

                        try:
                            from app.core.metrics_snapshot import write_monitor_metrics_snapshot_safe
                            snapshot_path = config.get("metrics_snapshot_path", "diagnostics/metrics/current.json")
                            m_list = []
                            for m_cfg in config.get("miners", []):
                                m_name = str(m_cfg.get("name", ""))
                                m_key = display_name(m_name)
                                m_host = m_cfg.get("host", "")
                                m_port = m_cfg.get("port", 4028)
                                m_sk = f"{m_name}|{m_host}:{m_port}"
                                m_st = states.get(m_sk) or states.get(m_key)
                                if m_st:
                                    m_list.append({
                                        "miner_id": m_key,
                                        "sample_ts": m_st.last_seen_ts or completed_ts,
                                        "responded": getattr(m_st, "last_responded", True),
                                        "rate_ths": m_st.last_rate_ths,
                                        "threshold_ths": float(config.get("hashrate_threshold_ths", 90.0)),
                                        "state": str(m_st.state),
                                        "active_boards": getattr(m_st, "last_active_boards", None),
                                        "expected_boards": int(config.get("expected_boards", 3)),
                                        "episode_active": bool(m_st.episode_start_ts is not None),
                                        "episode_duration_seconds": float(getattr(m_st, "episode_duration_seconds", 0.0)),
                                        "acquisition_quality": str(getattr(m_st, "last_acquisition_quality", "valid")),
                                        "acquisition_latency_seconds": getattr(m_st, "last_acquisition_latency", None),
                                    })
                            write_monitor_metrics_snapshot_safe(
                                path=snapshot_path,
                                process_start_ts=process_start_ts,
                                tick_sequence=tick_sequence,
                                completed_ts=completed_ts,
                                telegram_poller_ts=_TELEGRAM_POLLER_TS,
                                telegram_sender_ts=_TELEGRAM_SENDER_TS,
                                queue_depth=_TELEGRAM_QUEUE.qsize(),
                                telegram_counters={},
                                collector_age_seconds=collector_age_seconds,
                                collector_status="ok",
                                epoch_duration_seconds=None,
                                miner_metrics_list=m_list,
                            )
                        except Exception:
                            pass
                except Exception as exc:
                    if not heartbeat_error_logged:
                        log(
                            f"[WARN] LIVENESS heartbeat_write_failed "
                            f"type={type(exc).__name__}"
                        )
                    heartbeat_error_logged = True
            first_tick = False
            if qa_mode or qa_verbose:
                log_pid(f"[TICK] duration={time.monotonic() - tick_start:.3f}s qsize={_TELEGRAM_QUEUE.qsize()}")
            # Spec 065: Pipeline de hooks + modelo monotónico de tiempo
            # execute_tick() invoca PersistenceHook, GovernanceInterlockHook y TimingGuardHook.
            # La persistencia de estado real (save_state) ya ocurrió en el loop; el PersistenceHook
            # opera sobre el context.state_manager para telemetría del pipeline.
            try:
                monitor_ctx.last_daily_digest_date = _LAST_DAILY_DIGEST_DATE
                monitor_ctx.governance = _GLOBAL_INTERVENTION_GOV
                _supervisory_engine.execute_tick(
                    states=states,
                    last_update_id_ref=last_update_id_ref,
                    now_ts=now_ts,
                    tick_sequence=tick_sequence,
                    extra_tick_data={
                        "_state_persisted": True,
                        "last_daily_digest_date": _LAST_DAILY_DIGEST_DATE,
                        "governance": _GLOBAL_INTERVENTION_GOV,
                        "startup_grace_active": startup_grace_active,
                    },
                )
            except Exception as _hook_exc:
                log(f"[WARN] SUPERVISORY_HOOKS execute_tick failed: {type(_hook_exc).__name__}: {_hook_exc}")
            # Modelo monotónico: poll_seconds es el sleep restante del intervalo configurado.
            # _poll_interval_seconds guarda el valor de configuración para el cálculo.
            _last_tick_duration = max(0.0, time.monotonic() - tick_start)
            poll_seconds = max(0.0, _poll_interval_seconds - (time.monotonic() - tick_start))
            time.sleep(poll_seconds)
    except KeyboardInterrupt:
        log("Detenido por usuario")
    finally:
        if _watchdog_ipc_server is not None:
            try:
                _watchdog_ipc_server.stop()
            except Exception:
                pass
        if acquirer is not None:
            acquirer.close()
        if event_store is not None:
            event_store.close()
        if _gateway_heartbeat is not None:
            _gateway_heartbeat.stop()
        release_mutex()


if __name__ == "__main__":
    main()
