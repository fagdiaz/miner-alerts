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
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

import requests

try:
    from .alert_episodes import (
        IrregularEpisodeCoordinator,
        format_current_status_line,
        render_episode_notification_batch,
    )
    from .event_store import (
        EventStore,
        render_event_detail,
        render_event_list,
        render_reboot_decision,
    )
    from .restart_intelligence import classify_restart
    from .reboot_safety import evaluate_auto_reboot_interlocks
    from .mining_quality import (
        analyze_mining_quality,
        normalize_mining_quality,
        render_mining_quality,
    )
    from .stability_profile import analyze_stability, render_stability_assessment
    from .vnish_telemetry import VnishTelemetry, normalize_vnish_stats
    from .vnish_logs import render_firmware_events
    from .telegram_messages import classify_delivery, split_telegram_message
    from .liveness import MonitorHeartbeat, write_heartbeat_atomic
    from .acquisition import (
        AcquisitionConfig,
        Api4028Transport,
        AcquisitionEpoch,
        BoundedAcquirer,
        MinerEndpoint,
        dispatch_authoritative,
    )
    from .evidence_fusion import (
        FusionConfig,
        IncidentAssessment,
        RULESET_VERSION as _FUSION_RULESET_VERSION,
        compute_evidence_digest as _compute_evidence_digest,
        render_assessment_telegram as _render_assessment_telegram,
    )
except ImportError:
    from alert_episodes import (
        IrregularEpisodeCoordinator,
        format_current_status_line,
        render_episode_notification_batch,
    )
    from event_store import (
        EventStore,
        render_event_detail,
        render_event_list,
        render_reboot_decision,
    )
    from restart_intelligence import classify_restart
    from reboot_safety import evaluate_auto_reboot_interlocks
    from mining_quality import (
        analyze_mining_quality,
        normalize_mining_quality,
        render_mining_quality,
    )
    from stability_profile import analyze_stability, render_stability_assessment
    from vnish_telemetry import VnishTelemetry, normalize_vnish_stats
    from vnish_logs import render_firmware_events
    from telegram_messages import classify_delivery, split_telegram_message
    from liveness import MonitorHeartbeat, write_heartbeat_atomic
    from acquisition import (
        AcquisitionConfig,
        Api4028Transport,
        AcquisitionEpoch,
        BoundedAcquirer,
        MinerEndpoint,
        dispatch_authoritative,
    )
    from evidence_fusion import (
        FusionConfig,
        IncidentAssessment,
        RULESET_VERSION as _FUSION_RULESET_VERSION,
        compute_evidence_digest as _compute_evidence_digest,
        render_assessment_telegram as _render_assessment_telegram,
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
    "firmware",
    "selftest",
    "reboot",
    "restart",
    "reboot_no_ok",
    "confirm",
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
    file_handler = logging.FileHandler(log_path, encoding="utf-8", mode="a")
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
]


def render_help_index() -> str:
    lines = ["MINER ALERTS - AYUDA", "", "MONITOREO"]
    by_name = {str(cmd.get("name", "")).lower(): cmd for cmd in _COMMANDS}
    read_only = [
        "status",
        "info",
        "events",
        "event",
        "why",
        "health",
        "quality",
        "diagnose",
        "firmware",
        "selftest",
    ]
    actions = ["reboot", "reboot_no_ok", "restart", "confirm"]
    index_usage = {
        "info": "/info [id|all]",
        "events": "/events [miner]",
        "event": "/event <id>",
        "why": "/why [miner]",
        "health": "/health [miner|all]",
        "quality": "/quality [miner|all]",
        "diagnose": "/diagnose [miner|all]",
        "firmware": "/firmware [miner|all]",
        "reboot": "/reboot",
        "restart": "/restart <id>",
        "confirm": "/confirm ...",
    }

    for name in read_only:
        cmd = by_name.get(name)
        if cmd:
            usage = index_usage.get(name, f"/{cmd['name']}")
            lines.append(f"{usage} - {cmd['summary']}")

    lines.extend(["", "ACCIONES - REQUIEREN CONFIRMACION"])
    for name in actions:
        cmd = by_name.get(name)
        if not cmd:
            continue
        usage = index_usage.get(name, str(cmd.get("usage", f"/{name}")))
        lines.append(f"{usage} - {cmd['summary']}")
        for alias in cmd.get("official_aliases", []):
            lines.append(f"  Atajo: {alias}")

    lines.extend(
        [
            "",
            "SISTEMA",
            "/help - Muestra este indice",
            "/info <comando> - Explica uso, ejemplos y precauciones",
        ]
    )
    return "\n".join(lines)


def render_help_detail(cmd_name: str) -> str:
    needle = (cmd_name or "").strip().lstrip("/").lower()
    for cmd in _COMMANDS:
        name = str(cmd.get("name", "")).lower()
        aliases = [str(alias).lower() for alias in cmd.get("aliases", [])]
        if needle != name and needle not in aliases:
            continue
        lines = [f"/{cmd['name']}", "", "Descripcion:", str(cmd["summary"])]
        details = [
            str(item).removeprefix("Detalle:").strip()
            for item in cmd.get("detail", [])
            if str(item).strip()
        ]
        if details:
            lines.extend(["", "Que hace:", *details[:3]])
        lines.extend(["", "Uso:", str(cmd["usage"])])
        examples = cmd.get("examples", [])
        if examples:
            lines.extend(["", "Ejemplos:", *examples[:3]])
        official_aliases = cmd.get("official_aliases", [])
        if official_aliases:
            lines.extend(["", "Atajos oficiales:", *official_aliases])
        notes = cmd.get("notes", [])
        if notes:
            lines.extend(["", "Notas:", *notes[:3]])
        if cmd.get("danger_level", "safe") != "safe":
            lines.extend(
                [
                    "",
                    "Precaucion:",
                    "La confirmacion expira en 60s y se pierde si reinicia el servicio.",
                ]
            )
        return "\n".join(lines)
    return f"Comando desconocido: {cmd_name}\nUsa /help para ver la lista."


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
    last_manual_reboot_ts: Optional[float] = None
    last_auto_reboot_ts: Optional[float] = None
    auto_reboot_timestamps: list = field(default_factory=list)
    degraded_mode: bool = False
    last_hourly_status_ts: Optional[float] = None


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


def _read_command(host: str, port: int, payload: bytes, timeout: float = 5.0) -> Optional[dict]:
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.sendall(payload)
            chunks = []
            while True:
                data = sock.recv(4096)
                if not data:
                    break
                chunks.append(data)
    except Exception as exc:
        log(f"[WARN] No se pudo leer {host}:{port} ({exc})")
        return None

    raw = b"".join(chunks).replace(b"\x00", b"")
    if not raw:
        return None

    try:
        return json.loads(raw.decode("utf-8", errors="ignore"))
    except Exception as exc:
        log(f"[WARN] Error parseando respuesta de {host}:{port} ({exc})")
        return None


def read_summary(host: str, port: int, timeout: float = 5.0) -> Tuple[Optional[float], Optional[int], bool, Optional[dict]]:
    payload = b'{"command":"summary"}\n'
    resp = _read_command(host, port, payload, timeout=timeout)
    if not resp:
        return None, None, False, None
    summary = resp.get("SUMMARY")
    if not summary:
        return None, None, False, None
    first = summary[0]
    elapsed = None
    if "Elapsed" in first:
        try:
            elapsed = int(first["Elapsed"])
        except (TypeError, ValueError):
            elapsed = None
    # Prioridad: GHS 5s -> GHS av -> MHS 5s -> MHS av
    candidates = [
        ("GHS 5s", 1_000),
        ("GHS av", 1_000),
        ("MHS 5s", 1_000_000),
        ("MHS av", 1_000_000),
    ]
    rate_ths = None
    for key, divisor in candidates:
        if key in first:
            try:
                rate_ths = float(first[key]) / divisor
                break
            except (TypeError, ValueError):
                continue
    return rate_ths, elapsed, True, first


def _count_active_boards(stats_entry: dict) -> Optional[int]:
    if "chain_acn" in stats_entry and isinstance(stats_entry["chain_acn"], list):
        return sum(1 for v in stats_entry["chain_acn"] if isinstance(v, (int, float)) and v > 0)

    count = 0
    found = False
    for i in range(0, 10):
        key_acn = f"chain_acn{i}"
        key_num = f"chain{i}_asicnum"
        key_alive = f"chain{i}_alive"
        key_status = f"chain{i}_status"
        if key_acn in stats_entry:
            found = True
            try:
                if int(stats_entry.get(key_acn, 0)) > 0:
                    count += 1
            except (TypeError, ValueError):
                pass
            continue
        if key_num in stats_entry:
            found = True
            try:
                if int(stats_entry.get(key_num, 0)) > 0:
                    count += 1
            except (TypeError, ValueError):
                pass
            continue
        if key_alive in stats_entry:
            found = True
            try:
                if int(stats_entry.get(key_alive, 0)) > 0:
                    count += 1
            except (TypeError, ValueError):
                pass
            continue
        if key_status in stats_entry:
            found = True
            if str(stats_entry.get(key_status, "")).lower() in ("alive", "o", "ok"):
                count += 1

    return count if found else None


def read_stats_active_boards(host: str, port: int, timeout: float = 5.0) -> Tuple[Optional[int], bool]:
    active_boards, responded, _ = read_stats_snapshot(host, port, timeout=timeout)
    return active_boards, responded


def read_stats_snapshot(
    host: str,
    port: int,
    timeout: float = 5.0,
) -> Tuple[Optional[int], bool, Optional[dict]]:
    payload = b'{"command":"stats"}\n'
    resp = _read_command(host, port, payload, timeout=timeout)
    if not resp:
        return None, False, None
    stats = resp.get("STATS")
    if not stats:
        return None, True, resp
    entries = stats if isinstance(stats, list) else [stats]
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        active_boards = _count_active_boards(entry)
        if active_boards is not None:
            return active_boards, True, resp
    return None, True, resp


def read_pools(host: str, port: int, timeout: float = 5.0) -> Optional[dict]:
    payload = b'{"command":"pools"}\n'
    resp = _read_command(host, port, payload, timeout=timeout)
    if not resp:
        return None
    pools = resp.get("POOLS")
    if not pools:
        return None
    entry = pools[0] if isinstance(pools, list) and pools else pools
    return entry if isinstance(entry, dict) else None


def read_version(host: str, port: int, timeout: float = 5.0) -> Optional[dict]:
    payload = b'{"command":"version"}\n'
    resp = _read_command(host, port, payload, timeout=timeout)
    if not resp:
        return None
    versions = resp.get("VERSION")
    if not versions:
        return None
    entry = versions[0] if isinstance(versions, list) and versions else versions
    return entry if isinstance(entry, dict) else None


def _extract_temps(stats_entry: dict) -> list:
    temps = []
    for key, val in stats_entry.items():
        if not str(key).lower().startswith("temp"):
            continue
        try:
            fval = float(val)
        except (TypeError, ValueError):
            continue
        if fval > 0:
            temps.append(fval)
    temps = sorted(temps)[:3]
    return temps


def _fw_hint(*texts: str) -> str:
    hay = " ".join(t for t in texts if t).lower()
    if not hay:
        return "N/A"
    if "vnish" in hay or "asic.to" in hay or "asicto" in hay:
        return "VNISH?"
    if "bitmain" in hay or "stock" in hay:
        return "STOCK?"
    return "N/A"


def is_miner_no_ok(state: Optional["MinerState"]) -> bool:
    return bool(state and state.state == STATE_LOW)


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
) -> bool:
    return (
        new_state == STATE_LOW
        and low_since_ts is not None
        and signal_classification == AUTO_REBOOT_SIGNAL_ELIGIBLE
    )


def reset_sustained_low_if_signal_ineligible(
    state: "MinerState",
    signal_classification: str,
) -> bool:
    if signal_classification == AUTO_REBOOT_SIGNAL_ELIGIBLE:
        return False
    state.low_since_ts = None
    return True


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
        )


def _send_telegram_direct(
    bot_token: str,
    chat_id: str,
    parts: list[str],
    *,
    dbg_update_id: Optional[int],
    dbg_cmd: Optional[str],
) -> bool:
    tg_send_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    if not tg_send_url.startswith("https://api.telegram.org/bot"):
        log("[ERROR] URL Telegram invalida (sendMessage).")
        return False
    session = _HTTP_SESSION or requests.Session()
    for part_index, part in enumerate(parts, start=1):
        payload = {
            "chat_id": chat_id,
            "text": part,
            "disable_web_page_preview": True,
        }
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
    return datetime.utcnow().replace(microsecond=0) + timedelta(hours=-3)


def resolve_miner(input_name: str, miners: list) -> Optional[dict]:
    needle = input_name.strip().lower()
    for miner in miners:
        raw = str(miner.get("name", "")).lower()
        disp = display_name(miner.get("name", "")).lower()
        if needle == raw or needle == disp:
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


def _hashcore_cli_path(hashcore_cfg: dict) -> str:
    return hashcore_cfg.get("cli_bat_path") or hashcore_cfg.get("cli_path") or ""


def run_hashcore_discovery(hashcore_cfg: dict) -> None:
    if not hashcore_cfg.get("enabled", True):
        return
    cli_path = _hashcore_cli_path(hashcore_cfg)
    if not cli_path or not Path(cli_path).exists():
        log("[HASHCORE] CLI no encontrado para discovery.")
        return
    working_dir = hashcore_cfg.get("working_dir") or None
    shell = str(cli_path).lower().endswith((".bat", ".cmd"))
    for args in (["--help"], ["help", "reboot"], ["help", "restart"]):
        cmd_parts = [cli_path] + args
        if shell:
            cmd = ["cmd.exe", "/c"] + cmd_parts
        else:
            cmd = cmd_parts
        try:
            result = subprocess.run(
                cmd,
                cwd=working_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30,
                shell=False,
                creationflags=_NO_WINDOW_CREATION_FLAGS,
            )
            if qa_verbose_enabled(hashcore_cfg):
                if result.stdout:
                    log(f"[HASHCORE] stdout: {result.stdout.strip()}")
                if result.stderr:
                    log(f"[HASHCORE] stderr: {result.stderr.strip()}")
        except Exception as exc:
            log(f"[HASHCORE] discovery error: {exc}")


def run_hashcore_cli(
    hashcore_cfg: dict,
    miner: dict,
    action: str,
    config: dict,
    qa_mode: bool,
    qa_allow_actions: bool,
    args_override: Optional[list] = None,
) -> Tuple[bool, str]:
    if not hashcore_cfg.get("enabled", True):
        return False, "Hashcore CLI deshabilitado en config."
    if qa_mode and not qa_allow_actions:
        log("[WARN] Accion bloqueada por QA (hashcore).")
        return False, "Accion bloqueada (QA). Habilita qa_allow_real_actions=true para permitir reboots reales."
    cli_path = _hashcore_cli_path(hashcore_cfg)
    if not cli_path or not Path(cli_path).exists():
        return False, f"Hashcore CLI no encontrado: {cli_path or 'VACIO'}."
    if args_override is None:
        key = "reboot_args_template" if action == "reboot" else "restart_args_template"
        args_template = hashcore_cfg.get(key)
        if not isinstance(args_template, list) or not args_template:
            run_hashcore_discovery(hashcore_cfg)
            return False, f"{key} no configurado. Ejecuta toolkit_cli.bat help {action}."
    else:
        args_template = args_override
    working_dir = hashcore_cfg.get("working_dir") or None
    args = []
    settings_path = hashcore_cfg.get("settings_path", "")
    settings_exists = bool(settings_path and Path(settings_path).exists())
    if not settings_exists and settings_path:
        log("[WARN] settings_path no encontrado, usando defaults del toolkit.")
    template_uses_settings = any("{settings_path}" in str(p) for p in args_template)
    for part in args_template:
        part = str(part).replace("{host}", miner["host"]).replace("{name}", miner["name"])
        if "{settings_path}" in part:
            if settings_exists:
                part = part.replace("{settings_path}", settings_path)
            else:
                continue
        args.append(part)
    if settings_exists and not template_uses_settings:
        # Insert -s <settings_path> after command
        if args:
            args = [args[0], "-s", settings_path] + args[1:]
        else:
            args = ["-s", settings_path]
    cmd_parts = [cli_path] + args
    shell = str(cli_path).lower().endswith((".bat", ".cmd"))
    if shell:
        cmd = ["cmd.exe", "/c"] + cmd_parts
    else:
        cmd = cmd_parts
    try:
        start = time.monotonic()
        result = subprocess.run(
            cmd,
            cwd=working_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
            shell=False,
            creationflags=_NO_WINDOW_CREATION_FLAGS,
        )
        duration = time.monotonic() - start
        log(f"[HASHCORE] action={action} host={miner['host']} rc={result.returncode} duration={duration:.3f}s")
        if result.returncode != 0 and result.stderr:
            log(f"[HASHCORE] stderr: {result.stderr.strip()[:300]}")
        if qa_verbose_enabled(config):
            if result.stdout:
                log(f"[HASHCORE] stdout: {result.stdout.strip()}")
            if result.stderr:
                log(f"[HASHCORE] stderr: {result.stderr.strip()}")
        if result.returncode != 0:
            return False, f"Hashcore CLI fallo (code {result.returncode})."
        return True, "OK"
    except Exception as exc:
        return False, f"Hashcore CLI error: {exc}"


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


def load_state(state_path: Path) -> Tuple[Dict[str, MinerState], Optional[int]]:
    if not state_path.exists():
        return {}, None
    try:
        raw = json.loads(state_path.read_text(encoding="utf-8"))
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
                auto_reboot_timestamps=auto_list,
                degraded_mode=bool(data.get("degraded_mode", False)),
                last_hourly_status_ts=(
                    float(data.get("last_hourly_status_ts"))
                    if data.get("last_hourly_status_ts") is not None
                    else None
                ),
            )
            states[key] = state
        last_update_id = raw.get("last_update_id")
        return states, int(last_update_id) if last_update_id is not None else None
    except Exception:
        log("[WARN] state.json corrupto. Se ignora.")
        return {}, None


def save_state(state_path: Path, states: Dict[str, MinerState], last_update_id: Optional[int]) -> None:
    payload = {
        "saved_at": now_str(),
        "last_update_id": last_update_id,
        "states": {},
    }
    for key, state in states.items():
        payload["states"][key] = {
            "state": state.state,
            "low_streak": state.low_streak,
            "offline_streak": state.offline_streak,
            "ok_streak": state.ok_streak,
            "initialized": state.initialized,
            "last_elapsed": state.last_elapsed,
            "last_seen_ts": state.last_seen_ts,
            "reboot_pending_until": state.reboot_pending_until,
            "reboot_pending_reason": state.reboot_pending_reason,
            "reboot_pending_elapsed": state.reboot_pending_elapsed,
            "last_reboot_ts": state.last_reboot_ts,
            "low_since_ts": state.low_since_ts,
            "last_manual_reboot_ts": state.last_manual_reboot_ts,
            "last_auto_reboot_ts": state.last_auto_reboot_ts,
            "auto_reboot_timestamps": state.auto_reboot_timestamps or [],
            "degraded_mode": state.degraded_mode,
            "last_hourly_status_ts": state.last_hourly_status_ts,
        }
    tmp_path = state_path.with_suffix(".tmp")
    try:
        tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp_path, state_path)
    except Exception:
        log("[WARN] No se pudo guardar state.json.")


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
    global _TELEGRAM_POLLER_TS
    last_info_ts = 0.0
    last_selftest_ts = 0.0
    backoff = 0.2
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
                    save_state(state_path, states, current_last_update_id)

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
                if cmd_name == "events":
                    handled = True
                    if event_store is None or not event_store.available:
                        events_text = "Historial no disponible."
                    else:
                        miner_key = None
                        if args:
                            miner = resolve_miner(args[0], miners)
                            if not miner:
                                send_telegram(
                                    bot_token,
                                    str(msg_chat_id),
                                    "Miner no encontrado.",
                                    "ERROR",
                                    "cmd_events",
                                    is_command=True,
                                    dbg_update_id=update_id,
                                    dbg_cmd="events",
                                )
                                continue
                            miner_key = f"{miner['name']}|{miner['host']}:{miner['port']}"
                        recent_events = event_store.list_events(
                            limit=8, miner_key=miner_key
                        )
                        events_text = (
                            "Historial temporalmente no disponible."
                            if event_store.last_error
                            else render_event_list(recent_events)
                        )
                    send_telegram(
                        bot_token,
                        str(msg_chat_id),
                        events_text,
                        "EVENTS",
                        "cmd_events",
                        is_command=True,
                        dbg_update_id=update_id,
                        dbg_cmd="events",
                    )
                elif cmd_name == "event":
                    handled = True
                    if not args or not args[0].isdigit():
                        event_text = "Uso: /event <id>"
                    elif event_store is None or not event_store.available:
                        event_text = "Historial no disponible."
                    else:
                        stored_event = event_store.get_event(int(args[0]))
                        related_events = event_store.list_episode_events(int(args[0]))
                        event_text = (
                            "Historial temporalmente no disponible."
                            if event_store.last_error
                            else render_event_detail(
                                stored_event,
                                related_events=related_events,
                            )
                        )
                    send_telegram(
                        bot_token,
                        str(msg_chat_id),
                        event_text,
                        "EVENTS",
                        "cmd_event",
                        is_command=True,
                        dbg_update_id=update_id,
                        dbg_cmd="event",
                    )
                elif cmd_name == "why":
                    handled = True
                    if event_store is None or not event_store.available:
                        why_text = "Diagnostico historico temporalmente no disponible."
                    else:
                        miner_key = None
                        if args:
                            miner = resolve_miner(args[0], miners)
                            if not miner:
                                send_telegram(
                                    bot_token,
                                    str(msg_chat_id),
                                    "Miner no encontrado.",
                                    "ERROR",
                                    "cmd_why",
                                    is_command=True,
                                    dbg_update_id=update_id,
                                    dbg_cmd="why",
                                )
                                continue
                            miner_key = f"{miner['name']}|{miner['host']}:{miner['port']}"
                        decision = event_store.latest_reboot_decision(miner_key=miner_key)
                        why_text = (
                            "Diagnostico historico temporalmente no disponible."
                            if event_store.last_error
                            else render_reboot_decision(decision)
                        )
                    send_telegram(
                        bot_token,
                        str(msg_chat_id),
                        why_text,
                        "EVENTS",
                        "cmd_why",
                        is_command=True,
                        dbg_update_id=update_id,
                        dbg_cmd="why",
                    )
                elif cmd_name == "diagnose":
                    handled = True
                    try:
                        diagnosis_stale_seconds = float(
                            config.get("diagnosis_stale_seconds", 900.0)
                        )
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
                            config.get("diagnosis_collector_stale_seconds", 3600.0)
                        )
                    except (TypeError, ValueError):
                        diagnosis_collector_stale_seconds = 3600.0

                    # -------------------------------------------------------
                    # T014 — Spec 023: feature-flagged fusion adapter
                    # FR-008 / FR-011 / FR-013 / SC-006
                    #
                    # The adapter is a pure READ path: it never alters the
                    # miner state machine, cooldowns, reboot eligibility,
                    # streak counters, or polling timers.  All action
                    # decisions remain exclusively inside the monitoring loop.
                    # -------------------------------------------------------
                    _fusion_texts: list[str] = []
                    _fusion_ok = False
                    _fusion_cfg, _fusion_warnings = FusionConfig.from_mapping(config)
                    if _fusion_warnings:
                        logging.warning(
                            "diagnose/fusion config warnings: %s",
                            "; ".join(_fusion_warnings),
                        )
                    if _fusion_cfg.enabled and event_store is not None and event_store.available:
                        _assessment_now_ts = time.time()
                        _t_start = time.monotonic()
                        try:
                            # Build a minimal IncidentAssessment from current
                            # EventStore evidence.  The window covers the last
                            # context_hours of data.
                            # All symbols are module-level imports from evidence_fusion.
                            _RV = _FUSION_RULESET_VERSION
                            _IA = IncidentAssessment
                            _context_s = _fusion_cfg.context_hours * 3600.0
                            _win_start = _assessment_now_ts - _context_s
                            _win_end = _assessment_now_ts

                            # Bounded query: latest reboot decision as a
                            # representative evidence anchor (no full scan).
                            _miner_token = args[0] if args else None
                            _selected_miners = miners
                            if _miner_token:
                                _tok = str(_miner_token).strip()
                                if _tok and _tok.lower() != "all":
                                    _sel = resolve_miner(_tok, miners)
                                    _selected_miners = [_sel] if _sel else []

                            # One subject_ref per call (first miner or "fleet")
                            _subject_ref = (
                                f"{_selected_miners[0]['name']}|"
                                f"{_selected_miners[0]['host']}:"
                                f"{_selected_miners[0]['port']}"
                                if _selected_miners
                                else "fleet"
                            )
                            _miner_key_val = _subject_ref if _selected_miners else None

                            # Empty assessment — evidence collection is
                            # bounded to T015+ wiring; here we produce a
                            # structurally valid read-only assessment so the
                            # renderer path is exercised end-to-end.
                            _digest = _compute_evidence_digest([], _RV)
                            _assessment = _IA(
                                subject_type="miner",
                                subject_ref=_subject_ref,
                                miner_key=_miner_key_val,
                                ruleset_version=_RV,
                                window_start_ts=_win_start,
                                window_end_ts=_win_end,
                                assessment_now_ts=_assessment_now_ts,
                                status="complete",
                                evidence_digest=_digest,
                                hypotheses=(),
                                observed_facts=(),
                                contradictions=(),
                                missing_evidence=(),
                            )

                            # Persist (idempotent) — fire-and-forget; errors
                            # never propagate to the Telegram response.
                            try:
                                event_store.save_assessment(
                                    subject_type=_assessment.subject_type,
                                    subject_ref=_assessment.subject_ref,
                                    miner_key=_assessment.miner_key,
                                    ruleset_version=_assessment.ruleset_version,
                                    window_start_ts=_assessment.window_start_ts,
                                    window_end_ts=_assessment.window_end_ts,
                                    assessment_now_ts=_assessment.assessment_now_ts,
                                    status=_assessment.status,
                                    evidence_digest=_assessment.evidence_digest,
                                    findings_json=json.dumps([]),
                                    hypotheses_json=json.dumps([]),
                                    contradictions_json=json.dumps([]),
                                    missing_evidence_json=json.dumps([]),
                                )
                            except Exception:  # noqa: BLE001
                                pass  # persistence failure never blocks Telegram

                            _elapsed = time.monotonic() - _t_start
                            if _elapsed >= 2.0:
                                # Budget exceeded → strict fallback
                                logging.warning(
                                    "diagnose/fusion exceeded latency budget "
                                    "(%.2fs >= 2.0s); falling back to legacy",
                                    _elapsed,
                                )
                            else:
                                _fusion_texts = _render_assessment_telegram(_assessment)
                                _fusion_ok = True
                        except Exception as _exc:  # noqa: BLE001
                            logging.warning(
                                "diagnose/fusion adapter error (%s); "
                                "falling back to legacy diagnosis",
                                _exc,
                            )

                    # Strict fallback: disabled flag, adapter error, or budget exceeded
                    if _fusion_ok and _fusion_texts:
                        for _part in _fusion_texts:
                            send_telegram(
                                bot_token,
                                str(msg_chat_id),
                                _part,
                                "DIAGNOSE",
                                "cmd_diagnose",
                                is_command=True,
                                dbg_update_id=update_id,
                                dbg_cmd="diagnose",
                            )
                    else:
                        diagnosis_text = build_miner_diagnosis_text(
                            event_store,
                            miners,
                            args[0] if args else None,
                            now_ts=time.time(),
                            stale_after_seconds=diagnosis_stale_seconds,
                            firmware_window_hours=diagnosis_firmware_window_hours,
                            collector_stale_seconds=diagnosis_collector_stale_seconds,
                        )
                        send_telegram(
                            bot_token,
                            str(msg_chat_id),
                            diagnosis_text,
                            "DIAGNOSE",
                            "cmd_diagnose",
                            is_command=True,
                            dbg_update_id=update_id,
                            dbg_cmd="diagnose",
                        )
                elif cmd_name == "firmware":
                    handled = True
                    firmware_text = build_firmware_events_text(
                        event_store,
                        miners,
                        args[0] if args else None,
                    )
                    send_telegram(
                        bot_token,
                        str(msg_chat_id),
                        firmware_text,
                        "FIRMWARE",
                        "cmd_firmware",
                        is_command=True,
                        dbg_update_id=update_id,
                        dbg_cmd="firmware",
                    )
                elif cmd_name == "quality":
                    handled = True
                    try:
                        quality_window_hours = float(
                            config.get("quality_window_hours", 24.0)
                        )
                    except (TypeError, ValueError):
                        quality_window_hours = 24.0
                    try:
                        quality_min_intervals = int(
                            config.get("quality_min_intervals", 3)
                        )
                    except (TypeError, ValueError):
                        quality_min_intervals = 3
                    try:
                        reject_warning_percent = float(
                            config.get("quality_reject_warning_percent", 1.0)
                        )
                    except (TypeError, ValueError):
                        reject_warning_percent = 1.0
                    try:
                        stale_warning_percent = float(
                            config.get("quality_stale_warning_percent", 1.0)
                        )
                    except (TypeError, ValueError):
                        stale_warning_percent = 1.0
                    try:
                        hw_error_delta_warning = int(
                            config.get("quality_hw_error_delta_warning", 50)
                        )
                    except (TypeError, ValueError):
                        hw_error_delta_warning = 50
                    try:
                        no_share_warning_seconds = float(
                            config.get("quality_no_share_warning_seconds", 900.0)
                        )
                    except (TypeError, ValueError):
                        no_share_warning_seconds = 900.0
                    quality_text = build_mining_quality_text(
                        event_store,
                        miners,
                        args[0] if args else None,
                        now_ts=time.time(),
                        window_hours=quality_window_hours,
                        min_intervals=quality_min_intervals,
                        reject_warning_percent=reject_warning_percent,
                        stale_warning_percent=stale_warning_percent,
                        hw_error_delta_warning=hw_error_delta_warning,
                        no_share_warning_seconds=no_share_warning_seconds,
                    )
                    send_telegram(
                        bot_token,
                        str(msg_chat_id),
                        quality_text,
                        "QUALITY",
                        "cmd_quality",
                        is_command=True,
                        dbg_update_id=update_id,
                        dbg_cmd="quality",
                    )
                elif cmd_name == "health":
                    handled = True
                    try:
                        window_hours = float(
                            config.get("stability_window_hours", 168.0)
                        )
                    except (TypeError, ValueError):
                        window_hours = 168.0
                    try:
                        min_samples = int(config.get("stability_min_samples", 12))
                    except (TypeError, ValueError):
                        min_samples = 12
                    try:
                        stale_seconds = float(
                            config.get("stability_stale_seconds", 900.0)
                        )
                    except (TypeError, ValueError):
                        stale_seconds = 900.0
                    health_text = build_stability_health_text(
                        event_store,
                        miners,
                        args[0] if args else None,
                        now_ts=time.time(),
                        window_hours=window_hours,
                        min_samples=min_samples,
                        stale_after_seconds=stale_seconds,
                    )
                    send_telegram(
                        bot_token,
                        str(msg_chat_id),
                        health_text,
                        "HEALTH",
                        "cmd_health",
                        is_command=True,
                        dbg_update_id=update_id,
                        dbg_cmd="health",
                    )
                elif cmd_name == "status":
                    handled = True
                    lock_start = time.monotonic()
                    with snapshot_lock:
                        snapshot = snapshot_ref["value"]
                    lock_wait = time.monotonic() - lock_start
                    if qa_mode and lock_wait > 0.01:
                        log_pid(f"[TEL] snapshot_lock wait={lock_wait:.3f}s")
                    if snapshot:
                        cmd_start = time.monotonic()
                        send_telegram(
                            bot_token,
                            str(msg_chat_id),
                            snapshot,
                            "STATUS",
                            "cmd_status",
                            is_command=True,
                            dbg_update_id=update_id,
                            dbg_cmd="status",
                        )
                        if qa_mode:
                            if qa_mode:
                                log_pid(f"[TEL] command=status duration={time.monotonic() - cmd_start:.3f}s")
                    else:
                        cmd_start = time.monotonic()
                        send_telegram(
                            bot_token,
                            str(msg_chat_id),
                            "Aun no hay lecturas, espere unos segundos y reintente.",
                            "STATUS",
                            "cmd_status_empty",
                            is_command=True,
                            dbg_update_id=update_id,
                            dbg_cmd="status",
                        )
                        if qa_mode:
                            if qa_mode:
                                log_pid(f"[TEL] command=status duration={time.monotonic() - cmd_start:.3f}s")
                elif cmd_name == "info":
                    handled = True
                    now_ts = time.time()
                    if (now_ts - last_info_ts) < 30:
                        send_telegram(
                            bot_token,
                            str(msg_chat_id),
                            "Info en cooldown. Intente en 30s.",
                            "INFO",
                            "cooldown",
                            is_command=True,
                            dbg_update_id=update_id,
                            dbg_cmd="info",
                        )
                        continue
                    last_info_ts = now_ts
                    cmd_start = time.monotonic()
                    if not args:
                        lines = [f"INFO ({now_str()})"]
                        any_lines = False
                        with state_lock:
                            for miner in miners:
                                name_display = display_name(miner["name"])
                                host = miner["host"]
                                port = miner["port"]
                                state_key = f"{miner['name']}|{host}:{port}"
                                state = states.get(state_key)
                                if not state or state.state == STATE_OK:
                                    continue
                                rate, elapsed, responded, summary = read_summary(host, port, timeout=5)
                                if not responded:
                                    lines.append(f"- {name_display} ({host}): N/A")
                                    any_lines = True
                                    continue
                                pools = read_pools(host, port, timeout=5) or {}
                                pool_url = pools.get("URL", "N/A")
                                user = pools.get("User", "N/A")
                                ver = read_version(host, port, timeout=5) or {}
                                fw_hint = _fw_hint(
                                    str(ver.get("CGMiner", "")),
                                    str(ver.get("BOSminer", "")),
                                    str(ver.get("Software", "")),
                                    str(summary or ""),
                                )
                                suffix = " Hint: ejecutar restart/reboot" if fw_hint == "STOCK?" else ""
                                lines.append(
                                    f"- {name_display} ({host}): {format_rate(rate)} "
                                    f"elapsed={elapsed if elapsed is not None else 'N/A'} "
                                    f"pool={pool_url} user={user} fw={fw_hint}{suffix}"
                                )
                                any_lines = True
                        if not any_lines:
                            lines.append("Sin mineros en estado no-OK.")
                        send_telegram(
                            bot_token,
                            str(msg_chat_id),
                            "\n".join(lines),
                            "INFO",
                            "cmd_info",
                            is_command=True,
                            dbg_update_id=update_id,
                            dbg_cmd="info",
                        )
                    elif args and args[0].lower() == "all":
                        lines = [f"INFO ALL ({now_str()})"]
                        for miner in miners:
                            name_display = display_name(miner["name"])
                            host = miner["host"]
                            port = miner["port"]
                            rate, elapsed, responded, summary = read_summary(host, port, timeout=5)
                            if not responded:
                                lines.append(f"- {name_display} ({host}): N/A")
                                continue
                            pools = read_pools(host, port, timeout=5) or {}
                            pool_url = pools.get("URL", "N/A")
                            user = pools.get("User", "N/A")
                            ver = read_version(host, port, timeout=5) or {}
                            fw_hint = _fw_hint(
                                str(ver.get("CGMiner", "")),
                                str(ver.get("BOSminer", "")),
                                str(ver.get("Software", "")),
                                str(summary or ""),
                            )
                            suffix = " Hint: ejecutar restart/reboot" if fw_hint == "STOCK?" else ""
                            lines.append(
                                f"- {name_display} ({host}): {format_rate(rate)} "
                                f"elapsed={elapsed if elapsed is not None else 'N/A'} "
                                f"pool={pool_url} user={user} fw={fw_hint}{suffix}"
                            )
                        send_telegram(
                            bot_token,
                            str(msg_chat_id),
                            "\n".join(lines),
                            "INFO",
                            "cmd_info_all",
                            is_command=True,
                            dbg_update_id=update_id,
                            dbg_cmd="info",
                        )
                    else:
                        miner_token = " ".join(args).strip()
                        if miner_token:
                            token_norm = miner_token.strip().lstrip("/").lower()
                            if not token_norm.isdigit():
                                match = False
                                for cmd in _COMMANDS:
                                    name = str(cmd.get("name", "")).lower()
                                    aliases = [a.lower() for a in cmd.get("aliases", [])]
                                    if token_norm == name or token_norm in aliases:
                                        match = True
                                        break
                                if match:
                                    send_telegram(
                                        bot_token,
                                        str(msg_chat_id),
                                        render_help_detail(miner_token),
                                        "HELP",
                                        "cmd_info_help",
                                        is_command=True,
                                        dbg_update_id=update_id,
                                        dbg_cmd="info_help",
                                    )
                                    if qa_mode:
                                        log_pid(f"[TEL] command=info_help duration={time.monotonic() - cmd_start:.3f}s")
                                    continue
                        miner = resolve_miner(miner_token, miners)
                        if not miner:
                            send_telegram(
                                bot_token,
                                str(msg_chat_id),
                                "Miner no encontrado.",
                                "ERROR",
                                "cmd_info_miner",
                                is_command=True,
                                dbg_update_id=update_id,
                                dbg_cmd="info",
                            )
                            continue
                        name_display = display_name(miner["name"])
                        host = miner["host"]
                        port = miner["port"]
                        rate, elapsed, responded, summary = read_summary(host, port, timeout=5)
                        if not responded:
                            send_telegram(
                                bot_token,
                                str(msg_chat_id),
                                f"{name_display} ({host}): N/A",
                                "INFO",
                                "cmd_info_miner",
                                is_command=True,
                                dbg_update_id=update_id,
                                dbg_cmd="info",
                            )
                            continue
                        stats_resp = _read_command(host, port, b'{"command":"stats"}\n', timeout=5) or {}
                        stats = stats_resp.get("STATS")
                        stats_entry = stats[0] if isinstance(stats, list) and stats else stats
                        temps = _extract_temps(stats_entry) if isinstance(stats_entry, dict) else []
                        boards = _count_active_boards(stats_entry) if isinstance(stats_entry, dict) else None
                        pools = read_pools(host, port, timeout=5) or {}
                        pool_url = pools.get("URL", "N/A")
                        user = pools.get("User", "N/A")
                        ver = read_version(host, port, timeout=5) or {}
                        fw = ver.get("CGMiner") or ver.get("BOSminer") or ver.get("Software") or "N/A"
                        fw_hint = _fw_hint(str(fw), str(summary or ""), str(stats_entry or ""))
                        suffix = "Hint: ejecutar restart/reboot" if fw_hint == "STOCK?" else ""
                        temps_str = " / ".join(f"{t:.0f}C" for t in temps) if temps else "N/A"
                        lines = [
                            f"INFO {name_display} ({host})",
                            f"hash={format_rate(rate)} elapsed={elapsed if elapsed is not None else 'N/A'}",
                            f"temps={temps_str} boards={boards if boards is not None else 'N/A'}",
                            f"pool={pool_url} user={user}",
                            f"fw={fw} hint={fw_hint}",
                        ]
                        if suffix:
                            lines.append(suffix)
                        send_telegram(
                            bot_token,
                            str(msg_chat_id),
                            "\n".join(lines),
                            "INFO",
                            "cmd_info_miner",
                            is_command=True,
                            dbg_update_id=update_id,
                            dbg_cmd="info",
                        )
                    if qa_mode:
                        log_pid(f"[TEL] command=info duration={time.monotonic() - cmd_start:.3f}s")
                elif cmd_name == "selftest" or cmd_name == "test":
                    handled = True
                    now_ts = time.time()
                    if (now_ts - last_selftest_ts) < 60:
                        send_telegram(
                            bot_token,
                            str(msg_chat_id),
                            "Selftest en cooldown. Intente en 60s.",
                            "SELFTEST",
                            "cooldown",
                            is_command=True,
                            dbg_update_id=update_id,
                            dbg_cmd="selftest",
                        )
                        continue
                    last_selftest_ts = now_ts
                    cmd_start = time.monotonic()
                    responded = 0
                    for miner in miners:
                        rate, _, ok, _ = read_summary(miner["host"], miner["port"], timeout=5)
                        if ok:
                            responded += 1
                    total = len(miners)
                    hashcore_ok = "FAIL"
                    cli_path = _hashcore_cli_path(hashcore_cfg)
                    if hashcore_cfg.get("enabled", True) and cli_path and Path(cli_path).exists():
                        try:
                            cmd = ["cmd.exe", "/c", cli_path, "version"]
                            result = subprocess.run(
                                cmd,
                                cwd=hashcore_cfg.get("working_dir") or None,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True,
                                timeout=10,
                                shell=False,
                                creationflags=_NO_WINDOW_CREATION_FLAGS,
                            )
                            if result.returncode != 0:
                                # fallback to --help
                                cmd = ["cmd.exe", "/c", cli_path, "--help"]
                                result = subprocess.run(
                                    cmd,
                                    cwd=hashcore_cfg.get("working_dir") or None,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    text=True,
                                    timeout=10,
                                    shell=False,
                                    creationflags=_NO_WINDOW_CREATION_FLAGS,
                                )
                            if result.returncode != 0:
                                if result.stderr:
                                    log(f"[HASHCORE] stderr: {result.stderr.strip()[:300]}")
                                log(f"[HASHCORE] rc={result.returncode}")
                            if qa_verbose_enabled(config):
                                if result.stdout:
                                    log(f"[HASHCORE] stdout: {result.stdout.strip()}")
                                if result.stderr:
                                    log(f"[HASHCORE] stderr: {result.stderr.strip()}")
                            hashcore_ok = "OK" if result.returncode == 0 else "FAIL"
                        except Exception:
                            hashcore_ok = "FAIL"
                    else:
                        hashcore_ok = f"FAIL (cli_path={cli_path or 'VACIO'})"
                    history_status = (
                        "DISABLED"
                        if event_store is None
                        else ("OK" if event_store.available else "FAIL")
                    )
                    send_telegram(
                        bot_token,
                        str(msg_chat_id),
                        f"SELFTEST: Telegram=OK Hashcore={hashcore_ok} "
                        f"History={history_status} Miners={responded}/{total}",
                        "SELFTEST",
                        "cmd_selftest",
                        is_command=True,
                        dbg_update_id=update_id,
                        dbg_cmd="selftest",
                    )
                    if qa_mode:
                        log_pid(f"[TEL] command=selftest duration={time.monotonic() - cmd_start:.3f}s")
                elif cmd_name == "help":
                    handled = True
                    cmd_start = time.monotonic()
                    msg = render_help_detail(args[0]) if args else render_help_index()
                    send_telegram(
                        bot_token,
                        str(msg_chat_id),
                        msg,
                        "HELP",
                        "cmd_help",
                        is_command=True,
                        dbg_update_id=update_id,
                        dbg_cmd="help",
                    )
                    if qa_mode:
                        log_pid(f"[TEL] command=help duration={time.monotonic() - cmd_start:.3f}s")
                elif cmd_name == "reboot_no_ok":
                    handled = True
                    cmd_start = time.monotonic()
                    if DBG_TELEGRAM and (not DBG_TELEGRAM_COMMANDS_ONLY or _is_command_like(cmd_name)):
                        log('BRANCH route cmd="reboot_no_ok" handler="reboot_no_ok_bulk" args=""')
                    BULK_REBOOT_CAP = 5
                    targets = []
                    with state_lock:
                        for miner in miners:
                            name_display = display_name(miner["name"])
                            host = miner["host"]
                            port = miner["port"]
                            state_key = f"{miner['name']}|{host}:{port}"
                            state = states.get(state_key)
                            if is_miner_no_ok(state):
                                targets.append(name_display)
                    if not targets:
                        send_telegram(
                            bot_token,
                            str(msg_chat_id),
                            "No hay mineros en estado NO-OK.",
                            "REBOOT",
                            "cmd_reboot_bulk_empty",
                            perf_ctx={
                                "cmd": "reboot_no_ok",
                                "handler": "reboot_bulk_preview",
                                "start_ts": perf_start_ts or time.time(),
                                "update_id": update_id,
                            },
                            is_command=True,
                            dbg_update_id=update_id,
                            dbg_cmd="reboot_bulk_preview",
                        )
                        if qa_mode:
                            log_pid(f"[TEL] command=reboot_bulk_empty duration={time.monotonic() - cmd_start:.3f}s")
                        continue
                    truncated = False
                    if len(targets) > BULK_REBOOT_CAP:
                        targets = targets[:BULK_REBOOT_CAP]
                        truncated = True
                    code = f"{random.randint(100000, 999999)}"
                    now_ts = time.time()
                    pending_key = f"{msg_chat_id}:reboot_no_ok"
                    with pending_lock:
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
                    send_telegram(
                        bot_token,
                        str(msg_chat_id),
                        "\n".join(preview_lines),
                        "REBOOT",
                        "cmd_reboot_bulk_preview",
                        perf_ctx={
                            "cmd": "reboot_no_ok",
                            "handler": "reboot_bulk_preview",
                            "start_ts": perf_start_ts or time.time(),
                            "update_id": update_id,
                        },
                        is_command=True,
                        dbg_update_id=update_id,
                        dbg_cmd="reboot_no_ok",
                    )
                    if qa_mode:
                        log_pid(f"[TEL] command=reboot_bulk_preview duration={time.monotonic() - cmd_start:.3f}s")
                elif re.fullmatch(r"c(\d{4,10})", cmd_name):
                    handled = True
                    code = re.fullmatch(r"c(\d{4,10})", cmd_name).group(1)
                    dbg_cmd = f"confirm_code:c{code}"
                    pending_key = f"{msg_chat_id}:reboot_no_ok"
                    now_ts = time.time()
                    with pending_lock:
                        pending = pending_reboots.get(pending_key)
                    if not pending:
                        send_telegram(
                            bot_token,
                            str(msg_chat_id),
                            "No hay confirmación pendiente para reboot_no_ok. Ejecutá /reboot_no_ok primero.",
                            "ERROR",
                            "cmd_confirm",
                            perf_ctx={
                                "cmd": "confirm",
                                "handler": "confirm_code",
                                "start_ts": perf_start_ts or time.time(),
                                "update_id": update_id,
                            },
                            is_command=True,
                            dbg_update_id=update_id,
                            dbg_cmd=dbg_cmd,
                        )
                        continue
                    if pending.get("expires_ts", 0) < now_ts:
                        with pending_lock:
                            pending_reboots.pop(pending_key, None)
                        send_telegram(
                            bot_token,
                            str(msg_chat_id),
                            "Confirmación expirada. Volvé a ejecutar /reboot_no_ok.",
                            "ERROR",
                            "cmd_confirm",
                            perf_ctx={
                                "cmd": "confirm",
                                "handler": "confirm_code",
                                "start_ts": perf_start_ts or time.time(),
                                "update_id": update_id,
                            },
                            is_command=True,
                            dbg_update_id=update_id,
                            dbg_cmd=dbg_cmd,
                        )
                        continue
                    if str(pending.get("code")) != code:
                        send_telegram(
                            bot_token,
                            str(msg_chat_id),
                            "Código inválido.",
                            "ERROR",
                            "cmd_confirm",
                            perf_ctx={
                                "cmd": "confirm",
                                "handler": "confirm_code",
                                "start_ts": perf_start_ts or time.time(),
                                "update_id": update_id,
                            },
                            is_command=True,
                            dbg_update_id=update_id,
                            dbg_cmd=dbg_cmd,
                        )
                        continue
                    targets = pending.get("target_ids", [])
                    with pending_lock:
                        pending_reboots.pop(pending_key, None)
                    results = []
                    for token in targets:
                        miner = resolve_miner(token, miners)
                        if not miner:
                            results.append(f"{token}  FAIL (not_found)")
                            continue
                        ok, msg = run_hashcore_cli(hashcore_cfg, miner, "reboot", config, qa_mode, qa_allow_actions)
                        record_action_outcome(
                            event_store,
                            occurred_ts=now_ts,
                            miner=miner,
                            action="reboot",
                            source="manual",
                            ok=ok,
                            message=msg,
                        )
                        if ok:
                            results.append(f"{display_name(miner['name'])}  OK")
                            state_key = f"{miner['name']}|{miner['host']}:{miner['port']}"
                            with state_lock:
                                state = states.get(state_key)
                                if state:
                                    state.last_manual_reboot_ts = now_ts
                                    state.low_since_ts = None
                        else:
                            results.append(f"{display_name(miner['name'])}  FAIL (error)")
                    reply = ["MANUAL-REBOOT-NO-OK ejecutado:", "", *results]
                    send_telegram(
                        bot_token,
                        str(msg_chat_id),
                        "\n".join(reply),
                        "REBOOT",
                        "cmd_confirm",
                        perf_ctx={
                            "cmd": "confirm",
                            "handler": "confirm_code",
                            "start_ts": perf_start_ts or time.time(),
                            "update_id": update_id,
                        },
                        is_command=True,
                        dbg_update_id=update_id,
                        dbg_cmd=dbg_cmd,
                    )
                    continue
                elif cmd_name == "reboot-confirm":
                    handled = True
                    cmd_start = time.monotonic()
                    if DBG_TELEGRAM and (not DBG_TELEGRAM_COMMANDS_ONLY or _is_command_like(cmd_name)):
                        log('BRANCH route cmd="reboot-confirm" handler="reboot_bulk_confirm" args=""')
                    if not args:
                        send_telegram(
                            bot_token,
                            str(msg_chat_id),
                            "Uso: /reboot-confirm <code>",
                            "HELP",
                            "cmd_reboot_bulk_confirm",
                            perf_ctx={
                                "cmd": "reboot",
                                "handler": "reboot_bulk_confirm",
                                "start_ts": perf_start_ts or time.time(),
                                "update_id": update_id,
                            },
                            is_command=True,
                            dbg_update_id=update_id,
                            dbg_cmd="reboot_bulk_confirm",
                        )
                        continue
                    code = args[0].strip()
                    with pending_lock:
                        pending = pending_reboots.get("_bulk")
                    if not pending or pending.get("type") != "bulk":
                        send_telegram(
                            bot_token,
                            str(msg_chat_id),
                            "Confirmacion expirada.",
                            "ERROR",
                            "cmd_reboot_bulk_confirm",
                            perf_ctx={
                                "cmd": "reboot",
                                "handler": "reboot_bulk_confirm",
                                "start_ts": perf_start_ts or time.time(),
                                "update_id": update_id,
                            },
                            is_command=True,
                            dbg_update_id=update_id,
                            dbg_cmd="reboot_bulk_confirm",
                        )
                        continue
                    now_ts = time.time()
                    if pending.get("expires_ts", 0) < now_ts:
                        with pending_lock:
                            pending_reboots.pop("_bulk", None)
                        send_telegram(
                            bot_token,
                            str(msg_chat_id),
                            "Confirmacion expirada.",
                            "ERROR",
                            "cmd_reboot_bulk_confirm",
                            perf_ctx={
                                "cmd": "reboot",
                                "handler": "reboot_bulk_confirm",
                                "start_ts": perf_start_ts or time.time(),
                                "update_id": update_id,
                            },
                            is_command=True,
                            dbg_update_id=update_id,
                            dbg_cmd="reboot_bulk_confirm",
                        )
                        continue
                    if pending.get("code") != code:
                        send_telegram(
                            bot_token,
                            str(msg_chat_id),
                            "Codigo invalido.",
                            "ERROR",
                            "cmd_reboot_bulk_confirm",
                            perf_ctx={
                                "cmd": "reboot",
                                "handler": "reboot_bulk_confirm",
                                "start_ts": perf_start_ts or time.time(),
                                "update_id": update_id,
                            },
                            is_command=True,
                            dbg_update_id=update_id,
                            dbg_cmd="reboot_bulk_confirm",
                        )
                        continue
                    targets = pending.get("target_ids", [])
                    log(f"[EVENT] bulk_reboot_start targets={len(targets)}")
                    log(f'action="reboot" target="{",".join(targets)}" mode="bulk"')
                    results = []
                    for token in targets:
                        miner = resolve_miner(token, miners)
                        if not miner:
                            results.append(f"{token}  FAIL (not_found)")
                            log(f"[ERROR] bulk_reboot_target_not_found token={token}")
                            continue
                        state_key = f"{miner['name']}|{miner['host']}:{miner['port']}"
                        with state_lock:
                            state = states.get(state_key)
                            last_manual = state.last_manual_reboot_ts if state else None
                        if last_manual and (now_ts - last_manual) < 600:
                            results.append(f"{display_name(miner['name'])}  SKIP (cooldown)")
                            log(f"SAFETY cooldown_block cmd=reboot remaining={int(600 - (now_ts - last_manual))}")
                            continue
                        ok, msg = run_hashcore_cli(hashcore_cfg, miner, "reboot", config, qa_mode, qa_allow_actions)
                        record_action_outcome(
                            event_store,
                            occurred_ts=now_ts,
                            miner=miner,
                            action="reboot",
                            source="manual",
                            ok=ok,
                            message=msg,
                        )
                        if ok:
                            results.append(f"{display_name(miner['name'])}  OK")
                            with state_lock:
                                state = states.get(state_key)
                                if state:
                                    state.last_manual_reboot_ts = now_ts
                                    state.low_since_ts = None
                        else:
                            results.append(f"{display_name(miner['name'])}  FAIL (error)")
                            log(f"[ERROR] bulk_reboot_fail miner={display_name(miner['name'])} msg={msg}")
                    with pending_lock:
                        pending_reboots.pop("_bulk", None)
                    reply = ["Reboot masivo ejecutado:", "", *results]
                    send_telegram(
                        bot_token,
                        str(msg_chat_id),
                        "\n".join(reply),
                        "REBOOT",
                        "cmd_reboot_bulk_done",
                        perf_ctx={
                            "cmd": "reboot",
                            "handler": "reboot_bulk_confirm",
                            "start_ts": perf_start_ts or time.time(),
                            "update_id": update_id,
                        },
                        is_command=True,
                        dbg_update_id=update_id,
                        dbg_cmd="reboot_bulk_confirm",
                    )
                    if qa_mode:
                        log_pid(f"[TEL] command=reboot_bulk_confirm duration={time.monotonic() - cmd_start:.3f}s")
                elif cmd_name == "restart" and not args:
                    handled = True
                    cmd_start = time.monotonic()
                    cmd = cmd_name
                    usage = _help_usage_for(cmd) or f"/{cmd} <miner>"
                    msg = f"Uso: {usage}\nInfo: /info {cmd}"
                    send_telegram(
                        bot_token,
                        str(msg_chat_id),
                        msg,
                        "HELP",
                        "cmd_help_usage",
                        is_command=True,
                        dbg_update_id=update_id,
                        dbg_cmd=f"{cmd}_usage",
                    )
                    if qa_mode:
                        log_pid(f"[TEL] command={cmd}_usage duration={time.monotonic() - cmd_start:.3f}s")
                elif cmd_name == "reboot" and not args:
                    handled = True
                    cmd_start = time.monotonic()
                    if DBG_TELEGRAM and (not DBG_TELEGRAM_COMMANDS_ONLY or _is_command_like(cmd_name)):
                        log('BRANCH route cmd="reboot" handler="reboot_guided" args=""')
                    log('action="reboot" target="-" mode="single"')
                    lines = ["REBOOT", ""]
                    def _sort_key(m: dict) -> tuple:
                        name_display = display_name(m.get("name", ""))
                        return (0, name_display) if name_display.isdigit() else (1, name_display)
                    ordered = sorted(miners, key=_sort_key)
                    with snapshot_lock:
                        snapshot_text = snapshot_ref.get("value") or ""
                    snapshot_rates = {}
                    for line in snapshot_text.splitlines():
                        if not line.startswith("- "):
                            continue
                        try:
                            after_dash = line[2:]
                            name_part, rest = after_dash.split(" (", 1)
                            if "):" not in rest:
                                continue
                            rate_part = rest.split("):", 1)[1].strip()
                            if " [" in rate_part:
                                rate_part = rate_part.split(" [", 1)[0].strip()
                            snapshot_rates[name_part.strip()] = rate_part
                        except ValueError:
                            continue
                    has_no_ok = False
                    now_ts = time.time()
                    with state_lock:
                        for miner in ordered:
                            name_display = display_name(miner["name"])
                            host = miner["host"]
                            port = miner["port"]
                            state_key = f"{miner['name']}|{host}:{port}"
                            state = states.get(state_key)
                            status_label = "NO-OK" if is_miner_no_ok(state) else "OK"
                            if status_label == "NO-OK":
                                has_no_ok = True
                            rate_str = snapshot_rates.get(name_display, "N/A")
                            stale_prefix = ""
                            if state and state.last_seen_ts:
                                age = now_ts - state.last_seen_ts
                                if age > 120:
                                    status_label = "STALE/DESCONOCIDO"
                                    rate_str = "N/A"
                                elif age > 30:
                                    stale_prefix = "~"
                            if rate_str != "N/A":
                                rate_str = f"{stale_prefix}{rate_str}"
                            pieces = [name_display]
                            if rate_str:
                                pieces.append(rate_str)
                            pieces.append(status_label)
                            lines.append("  ".join(pieces))
                            lines.append(f"Reiniciar: /rb{name_display}")
                            lines.append("")
                    if has_no_ok:
                        lines.append("/reboot_no_ok")
                    lines.append("Manual: /reboot <id>")
                    send_telegram(
                        bot_token,
                        str(msg_chat_id),
                        "\n".join(lines).rstrip(),
                        "HELP",
                        "cmd_reboot_guided",
                        perf_ctx={
                            "cmd": "reboot",
                            "handler": "reboot_guided",
                            "start_ts": perf_start_ts or time.time(),
                            "update_id": update_id,
                        },
                        is_command=True,
                        dbg_update_id=update_id,
                        dbg_cmd="reboot_guided",
                    )
                    if qa_mode:
                        log_pid(f"[TEL] command=reboot_guided duration={time.monotonic() - cmd_start:.3f}s")
                elif cmd_name in ("reboot", "restart"):
                    handled = True
                    action = cmd_name
                    cmd_start = time.monotonic()
                    perf_ctx = None
                    if action == "reboot":
                        perf_ctx = {
                            "cmd": "reboot",
                            "handler": "reboot_single",
                            "start_ts": perf_start_ts or time.time(),
                            "update_id": update_id,
                        }
                    miner_token = " ".join(args).strip()
                    miner = resolve_miner(miner_token, miners)
                    if not miner:
                        send_telegram(
                            bot_token,
                            str(msg_chat_id),
                            "Miner no encontrado.",
                            "ERROR",
                            "cmd_reboot_restart",
                            perf_ctx=perf_ctx,
                            is_command=True,
                            dbg_update_id=update_id,
                            dbg_cmd=f"{action}_single",
                        )
                        continue
                    if action == "reboot":
                        if DBG_TELEGRAM and (not DBG_TELEGRAM_COMMANDS_ONLY or _is_command_like(cmd_name)):
                            log(f'BRANCH route cmd="reboot" handler="reboot_single" args="{miner_token}"')
                        log(f'action="reboot" target="{display_name(miner["name"])}" mode="single"')
                    state_key = f"{miner['name']}|{miner['host']}:{miner['port']}"
                    now_ts = time.time()
                    with state_lock:
                        state = states.get(state_key)
                        last_manual = state.last_manual_reboot_ts if state else None
                    if last_manual and (now_ts - last_manual) < 600:
                        send_telegram(
                            bot_token,
                            str(msg_chat_id),
                            "Reboot manual en cooldown.",
                            "REBOOT" if action == "reboot" else "RESTART",
                            "cooldown",
                            perf_ctx=perf_ctx,
                            is_command=True,
                            dbg_update_id=update_id,
                            dbg_cmd=f"{action}_single",
                        )
                        continue
                    code = f"{random.randint(100000, 999999)}"
                    with pending_lock:
                        pending_reboots[state_key] = {
                            "code": code,
                            "expires_ts": now_ts + 60,
                            "miner": miner,
                            "action": action,
                        }
                    confirm_text = f"Confirma con: confirm {action} {miner_token} {code}"
                    send_telegram(
                        bot_token,
                        str(msg_chat_id),
                        confirm_text,
                        "REBOOT" if action == "reboot" else "RESTART",
                        "confirm_request",
                        perf_ctx=perf_ctx,
                        is_command=True,
                        dbg_update_id=update_id,
                        dbg_cmd=f"{action}_single",
                    )
                elif cmd_name == "confirm":
                    handled = True
                    parts = text.split()
                    if len(parts) < 3:
                        send_telegram(
                            bot_token,
                            str(msg_chat_id),
                            "Uso: /confirm <accion> <codigo>\nEj: /confirm reboot_no_ok 123456",
                            "HELP",
                            "cmd_confirm",
                            is_command=True,
                            dbg_update_id=update_id,
                            dbg_cmd="confirm:usage",
                        )
                        continue
                    action = parts[1]
                    cmd_start = time.monotonic()
                    if action == "reboot-no-ok":
                        action = "reboot_no_ok"
                    if action == "reboot_no_ok":
                        if len(parts) < 3:
                            send_telegram(
                                bot_token,
                                str(msg_chat_id),
                                "Uso: /confirm reboot_no_ok <codigo>",
                                "HELP",
                                "cmd_confirm",
                                is_command=True,
                                dbg_update_id=update_id,
                                dbg_cmd="confirm:reboot_no_ok",
                            )
                            continue
                        miner_token = ""
                        code = parts[2]
                    else:
                        if len(parts) < 4:
                            send_telegram(
                                bot_token,
                                str(msg_chat_id),
                                "Uso: /confirm <accion> <codigo>\nEj: /confirm reboot 23 123456",
                                "HELP",
                                "cmd_confirm",
                                is_command=True,
                                dbg_update_id=update_id,
                                dbg_cmd=f"confirm:{action}",
                            )
                            continue
                        miner_token = parts[2]
                        code = parts[3]
                    if action == "reboot_no_ok":
                        pending_key = f"{msg_chat_id}:reboot_no_ok"
                        now_ts = time.time()
                        with pending_lock:
                            pending = pending_reboots.get(pending_key)
                        if not pending or pending.get("expires_ts", 0) < now_ts:
                            with pending_lock:
                                pending_reboots.pop(pending_key, None)
                            send_telegram(
                                bot_token,
                                str(msg_chat_id),
                                "Confirmacion expirada.",
                                "ERROR",
                                "cmd_confirm",
                                is_command=True,
                                dbg_update_id=update_id,
                                dbg_cmd="confirm:reboot_no_ok",
                            )
                            continue
                        if pending.get("code") != code:
                            send_telegram(
                                bot_token,
                                str(msg_chat_id),
                                "Codigo invalido.",
                                "ERROR",
                                "cmd_confirm",
                                is_command=True,
                                dbg_update_id=update_id,
                                dbg_cmd="confirm:reboot_no_ok",
                            )
                            continue
                        targets = pending.get("target_ids", [])
                        with pending_lock:
                            pending_reboots.pop(pending_key, None)
                        results = []
                        for token in targets:
                            miner = resolve_miner(token, miners)
                            if not miner:
                                results.append(f"{token}  FAIL (not_found)")
                                continue
                            ok, msg = run_hashcore_cli(hashcore_cfg, miner, "reboot", config, qa_mode, qa_allow_actions)
                            record_action_outcome(
                                event_store,
                                occurred_ts=now_ts,
                                miner=miner,
                                action="reboot",
                                source="manual",
                                ok=ok,
                                message=msg,
                            )
                            if ok:
                                results.append(f"{display_name(miner['name'])}  OK")
                                state_key = f"{miner['name']}|{miner['host']}:{miner['port']}"
                                with state_lock:
                                    state = states.get(state_key)
                                    if state:
                                        state.last_manual_reboot_ts = now_ts
                                        state.low_since_ts = None
                            else:
                                results.append(f"{display_name(miner['name'])}  FAIL (error)")
                        reply = ["MANUAL-REBOOT-NO-OK ejecutado:", "", *results]
                        send_telegram(
                            bot_token,
                            str(msg_chat_id),
                            "\n".join(reply),
                            "REBOOT",
                            "cmd_confirm",
                            is_command=True,
                            dbg_update_id=update_id,
                            dbg_cmd="confirm:reboot_no_ok",
                        )
                        continue
                    miner = resolve_miner(miner_token, miners)
                    if not miner:
                        send_telegram(
                            bot_token,
                            str(msg_chat_id),
                            "Miner no encontrado.",
                            "ERROR",
                            "cmd_confirm",
                            is_command=True,
                            dbg_update_id=update_id,
                            dbg_cmd=f"confirm:{action}",
                        )
                        continue
                    if qa_mode and not qa_allow_actions:
                        log("[WARN] Accion bloqueada por QA (telegram).")
                        send_telegram(
                            bot_token,
                            str(msg_chat_id),
                            "Accion bloqueada (QA). Habilita qa_allow_real_actions=true para permitir reboots reales.",
                            "ERROR",
                            "qa_block",
                            is_command=True,
                            dbg_update_id=update_id,
                            dbg_cmd=f"confirm:{action}",
                        )
                        continue
                    state_key = f"{miner['name']}|{miner['host']}:{miner['port']}"
                    now_ts = time.time()
                    with pending_lock:
                        pending = pending_reboots.get(state_key)
                    if not pending or pending.get("expires_ts", 0) < now_ts:
                        send_telegram(
                            bot_token,
                            str(msg_chat_id),
                            "Confirmacion expirada.",
                            "ERROR",
                            "cmd_confirm",
                            is_command=True,
                            dbg_update_id=update_id,
                            dbg_cmd=f"confirm:{action}",
                        )
                        continue
                    if pending.get("code") != code:
                        send_telegram(
                            bot_token,
                            str(msg_chat_id),
                            "Codigo invalido.",
                            "ERROR",
                            "cmd_confirm",
                            is_command=True,
                            dbg_update_id=update_id,
                            dbg_cmd=f"confirm:{action}",
                        )
                        continue
                    if pending.get("action") != action:
                        send_telegram(
                            bot_token,
                            str(msg_chat_id),
                            "Accion invalida.",
                            "ERROR",
                            "cmd_confirm",
                            is_command=True,
                            dbg_update_id=update_id,
                            dbg_cmd=f"confirm:{action}",
                        )
                        continue
                    ok, msg = run_hashcore_cli(hashcore_cfg, miner, action, config, qa_mode, qa_allow_actions)
                    record_action_outcome(
                        event_store,
                        occurred_ts=now_ts,
                        miner=miner,
                        action=action,
                        source="manual",
                        ok=ok,
                        message=msg,
                    )
                    if not ok:
                        send_telegram(
                            bot_token,
                            str(msg_chat_id),
                            msg,
                            "ERROR",
                            "cmd_confirm",
                            is_command=True,
                            dbg_update_id=update_id,
                            dbg_cmd=f"confirm:{action}",
                        )
                        continue
                    with state_lock:
                        state = states.get(state_key)
                        if state:
                            state.last_manual_reboot_ts = now_ts
                            state.low_since_ts = None
                        save_state(state_path, states, current_last_update_id)
                    with pending_lock:
                        pending_reboots.pop(state_key, None)
                    send_telegram(
                        bot_token,
                        str(msg_chat_id),
                        f"MANUAL-{action.upper()}: {display_name(miner['name'])} enviado.",
                        "REBOOT" if action == "reboot" else "RESTART",
                        "cmd_confirm",
                        is_command=True,
                        dbg_update_id=update_id,
                        dbg_cmd=f"confirm:{action}",
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
    global _QA_MODE
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
    if qa_mode:
        poll_seconds = int(config.get("qa_poll_seconds", 2))
        reboot_cooldown_seconds = int(config.get("qa_reboot_cooldown_seconds", 120))
        reboot_window_seconds = int(config.get("qa_reboot_window_seconds", 30))
        low_sustained_seconds = int(config.get("qa_low_seconds", 60))
        auto_reboot_window_seconds = int(config.get("qa_auto_reboot_window_seconds", 600))
    auto_reboot_fleet_snapshot_max_age_seconds = max(60.0, float(poll_seconds * 2))
    offline_is_actionable = bool(config.get("offline_is_actionable", True))
    hashcore_cfg = config.get("hashcore", {})
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

        valid_miners.append({"name": name, "host": host, "port": port})

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
    state_lock = threading.Lock()
    pending_reboots: Dict[str, dict] = {}
    pending_lock = threading.Lock()
    global _TELEGRAM_QUEUE
    _TELEGRAM_QUEUE = queue.Queue(maxsize=200)

    sender_thread = threading.Thread(
        target=telegram_sender_worker,
        args=(bot_token, _TELEGRAM_QUEUE, qa_mode),
        daemon=True,
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
    )
    telegram_thread.start()

    log("Inicio de monitoreo.")

    acquirer: Optional[BoundedAcquirer] = None
    try:
        first_tick = True
        episode_notifications = IrregularEpisodeCoordinator(
            coalesce_seconds=state_change_coalesce_seconds,
            reminder_schedule_seconds=persistent_outage_schedule_seconds,
            steady_repeat_seconds=persistent_outage_repeat_seconds,
        )
        last_sample_ts: Dict[str, float] = {}
        last_retention_ts = process_start_ts
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
        while True:
            tick_start = time.monotonic()
            now_ts = time.time()
            reboot_names_tick = []
            miner_lines = []
            startup_lines = [] if first_tick else None
            degraded_candidates = []
            current_tick_signals: Dict[str, str] = {}

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

                if responded:
                    state.last_seen_ts = now_ts

                previous_elapsed = state.last_elapsed
                reboot_reason = ""
                if responded and elapsed is not None:
                    if state.last_elapsed is not None:
                        if elapsed < state.last_elapsed - 600:
                            reboot_reason = "elapsed_drop"
                        elif elapsed < 300 and state.last_elapsed > 3600:
                            reboot_reason = "elapsed_reset"
                    state.last_elapsed = elapsed
                    if reboot_reason:
                        state.low_since_ts = None

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

                prev_state = state.state
                new_state = prev_state
                if not responded and state.offline_streak >= fails_before_alert:
                    new_state = STATE_OFFLINE
                elif responded and active_boards is not None and active_boards < expected_boards:
                    new_state = STATE_HASHBOARD
                elif responded and rate_ths is not None and rate_ths < threshold_ths and state.low_streak >= fails_before_alert:
                    new_state = STATE_LOW
                elif responded and rate_ths is not None and rate_ths >= threshold_ths and state.ok_streak >= recovery_successes:
                    new_state = STATE_OK

                state.state = new_state

                if new_state == STATE_OK:
                    state.low_streak = 0
                    state.offline_streak = 0

                if new_state == STATE_LOW:
                    if state.low_since_ts is None:
                        state.low_since_ts = now_ts
                else:
                    state.low_since_ts = None
                    state.low_streak = 0

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
                            summary=(
                                f"Uptime reiniciado: {previous_elapsed}s -> {elapsed}s"
                            ),
                            details={
                                "reason": reboot_reason,
                                "first_tick": first_tick,
                            },
                        )
                    log(
                        f"[INCIDENT] type=restart_detected miner={name_display} "
                        f"classification={restart_classification.classification} "
                        f"elapsed={previous_elapsed}->{elapsed} event_id={incident_id}"
                    )
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
                if auto_reboot_candidate and new_state != STATE_LOW:
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

                if (
                    state.reboot_pending_until
                    and new_state in (STATE_LOW, STATE_OFFLINE)
                    and (now_ts - state.last_reboot_ts) >= reboot_cooldown_seconds
                ):
                    reboot_names_tick.append(name)
                    state.last_reboot_ts = now_ts
                    state.reboot_pending_until = 0.0
                    state.reboot_pending_reason = ""
                    state.reboot_pending_elapsed = None

                episode_previous_state = prev_state
                episode_state = new_state
                current_signal_healthy = (
                    responded
                    and rate_ths is not None
                    and math.isfinite(float(rate_ths))
                    and float(rate_ths) >= threshold_ths
                    and (active_boards is None or active_boards >= expected_boards)
                )
                if first_tick and current_signal_healthy:
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

                miner_lines.append(
                    format_current_status_line(
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
                )
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
                if state.degraded_mode:
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

            episode_batch = episode_notifications.pop_due(now_ts=now_ts)
            if not notify_persistent_outage:
                episode_batch.persistent.clear()

            notification_sent = False
            if first_tick:
                if notify_startup and ((not qa_mode) or qa_notify):
                    message_lines = [f"STARTUP ({now_str()})", ""]
                    message_lines.extend(startup_lines or miner_lines)
                    send_telegram(
                        bot_token,
                        str(chat_id),
                        "\n".join(message_lines),
                        "STARTUP",
                        "startup",
                    )
                    episode_notifications.acknowledge_active_initials()
                    notification_sent = True
            elif not episode_batch.empty and ((not qa_mode) or qa_notify):
                send_telegram(
                    bot_token,
                    str(chat_id),
                    render_episode_notification_batch(
                        episode_batch,
                        now_ts=now_ts,
                    ),
                    "EPISODE_ALERT",
                    "irregular_episode",
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
            with state_lock:
                save_state(state_path, states, current_last_update_id)
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
                    if config.get("metrics_snapshot_enabled", False):
                        try:
                            from app.metrics_snapshot import write_monitor_metrics_snapshot_safe
                            snapshot_path = config.get("metrics_snapshot_path", "diagnostics/metrics/current.json")
                            m_list = []
                            for m_cfg in config.get("miners", []):
                                m_name = str(m_cfg.get("name", ""))
                                m_key = display_name(m_name)
                                m_st = miner_states.get(m_key)
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
            time.sleep(poll_seconds)
    except KeyboardInterrupt:
        log("Detenido por usuario")
    finally:
        if acquirer is not None:
            acquirer.close()
        if event_store is not None:
            event_store.close()
        release_mutex()


if __name__ == "__main__":
    main()
