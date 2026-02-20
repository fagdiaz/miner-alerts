import json
import os
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
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

import requests

STATE_OK = "OK"
STATE_LOW = "LOW"
STATE_OFFLINE = "OFFLINE"
STATE_HASHBOARD = "HASHBOARD"

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


def log(msg: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    if _LOGGER:
        _LOGGER.info(line)
    else:
        print(line)


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
        "usage": "help | help <comando>",
        "short": "Muestra la lista de comandos o el detalle de uno.",
        "detail_sections": [
            ("Que hace", "Muestra ayuda general o detallada de un comando."),
            ("Cuando usarlo", "Cuando no recordas la sintaxis o el efecto de un comando."),
            ("Como se usa", "help  /  help reboot"),
            ("Advertencias", "Ninguna."),
            ("Ejemplo", "help reboot"),
        ],
        "dangerous": False,
        "enabled": True,
    },
    {
        "name": "status",
        "usage": "status",
        "short": "Devuelve el snapshot actual de todos los mineros.",
        "detail_sections": [
            ("Que hace", "Responde con el estado actual (hashrate y etiquetas)."),
            ("Cuando usarlo", "Para ver el estado general sin esperar un cambio."),
            ("Como se usa", "status"),
            ("Advertencias", "Ninguna."),
            ("Ejemplo", "status"),
        ],
        "dangerous": False,
        "enabled": True,
    },
    {
        "name": "info",
        "usage": "info | info all | info <miner>",
        "short": "Detalle de mineros (no OK o todos).",
        "detail_sections": [
            ("Que hace", "Muestra info resumida del/los mineros."),
            ("Cuando usarlo", "Para diagnosticar un minero puntual o los no-OK."),
            ("Como se usa", "info  /  info all  /  info 23"),
            ("Advertencias", "Depende del firmware para algunos campos."),
            ("Ejemplo", "info 23"),
        ],
        "dangerous": False,
        "enabled": True,
    },
    {
        "name": "selftest",
        "usage": "selftest | test",
        "short": "Chequeo rapido de Telegram/Hashcore/mineros.",
        "detail_sections": [
            ("Que hace", "Valida conectividad y reporte basico."),
            ("Cuando usarlo", "Tras cambios de red o config."),
            ("Como se usa", "selftest"),
            ("Advertencias", "Puede tardar unos segundos."),
            ("Ejemplo", "selftest"),
        ],
        "dangerous": False,
        "enabled": True,
    },
    {
        "name": "reboot",
        "usage": "reboot <miner>",
        "short": "Solicita reboot manual (requiere confirmacion).",
        "detail_sections": [
            ("Que hace", "Genera un codigo y pide confirmacion."),
            ("Cuando usarlo", "Cuando un minero no recupera por si solo."),
            ("Como se usa", "reboot 23"),
            ("Advertencias", "TTL 60s; si el script reinicia, el pending se pierde."),
            ("Ejemplo", "confirm reboot 23 123456"),
        ],
        "dangerous": True,
        "enabled": True,
    },
    {
        "name": "restart",
        "usage": "restart <miner>",
        "short": "Solicita restart manual (requiere confirmacion).",
        "detail_sections": [
            ("Que hace", "Genera un codigo y pide confirmacion."),
            ("Cuando usarlo", "Para reiniciar servicios del minero."),
            ("Como se usa", "restart 23"),
            ("Advertencias", "TTL 60s; si el script reinicia, el pending se pierde."),
            ("Ejemplo", "confirm restart 23 123456"),
        ],
        "dangerous": True,
        "enabled": True,
    },
    {
        "name": "confirm",
        "usage": "confirm reboot <miner> <code> | confirm restart <miner> <code>",
        "short": "Confirma una accion pendiente.",
        "detail_sections": [
            ("Que hace", "Ejecuta el reboot/restart pendiente con codigo."),
            ("Cuando usarlo", "Tras recibir el codigo de confirmacion."),
            ("Como se usa", "confirm reboot 23 123456"),
            ("Advertencias", "TTL 60s; si expira, reemitir reboot/restart."),
            ("Ejemplo", "confirm restart 23 123456"),
        ],
        "dangerous": True,
        "enabled": True,
    },
]


def render_help_index() -> str:
    lines = ["Comandos disponibles:"]
    for cmd in _COMMANDS:
        if not cmd.get("enabled", True):
            continue
        flag = " (peligroso)" if cmd.get("dangerous") else ""
        lines.append(f"- `{cmd['usage']}`{flag}: {cmd['short']}")
    lines.append("")
    lines.append("Usa: help <comando>")
    return "\n".join(lines)


def render_help_detail(cmd_name: str) -> str:
    needle = (cmd_name or "").strip().lower()
    for cmd in _COMMANDS:
        if not cmd.get("enabled", True):
            continue
        if str(cmd.get("name", "")).lower() == needle:
            lines = [
                f"`{cmd['name']}`",
                f"Uso: `{cmd['usage']}`",
                "",
            ]
            for title, body in cmd.get("detail_sections", []):
                lines.append(f"*{title}*")
                lines.append(body)
                lines.append("")
            return "\n".join(lines)
    return f"Comando desconocido: {cmd_name}. Escribi help para ver la lista."


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
        key_num = f"chain{i}_asicnum"
        key_alive = f"chain{i}_alive"
        key_status = f"chain{i}_status"
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
    payload = b'{"command":"stats"}\n'
    resp = _read_command(host, port, payload, timeout=timeout)
    if not resp:
        return None, False
    stats = resp.get("STATS")
    if not stats:
        return None, True
    entry = stats[0] if isinstance(stats, list) and stats else stats
    if not isinstance(entry, dict):
        return None, True
    return _count_active_boards(entry), True


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


def send_telegram(bot_token: str, chat_id: str, message: str, msg_type: str, reason: str = "") -> None:
    if _TELEGRAM_QUEUE is None:
        return
    if not msg_type:
        msg_type = "ERROR"
    with _TELEGRAM_QUEUE_LOCK:
        now_ts = time.time()
        _LAST_ENQUEUED[msg_type] = now_ts
        if _TELEGRAM_QUEUE.full():
            try:
                _TELEGRAM_QUEUE.get_nowait()
                log("[WARN] Cola Telegram llena, descartando mensaje mas viejo.")
            except Exception:
                pass
        _TELEGRAM_QUEUE.put((now_ts, chat_id, message, msg_type, reason))
        _LAST_SENT_META["type"] = msg_type
        _LAST_SENT_META["ts"] = now_str()
        if _QA_MODE:
            log_pid(f"[QA] enqueue type={msg_type} reason={reason} qsize={_TELEGRAM_QUEUE.qsize()}")


def telegram_sender_worker(bot_token: str, q: queue.Queue, qa_mode: bool) -> None:
    session = requests.Session()
    tg_send_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    if not tg_send_url.startswith("https://api.telegram.org/bot"):
        log("[ERROR] URL Telegram invalida (sendMessage).")
        return
    while True:
        try:
            enqueue_ts, chat_id, message, msg_type, _reason = q.get()
            with _TELEGRAM_QUEUE_LOCK:
                last_ts = _LAST_ENQUEUED.get(msg_type, 0.0)
            window = _COALESCE_WINDOWS.get(msg_type)
            if window and enqueue_ts < last_ts and (last_ts - enqueue_ts) <= window:
                continue
            msg_hash = hashlib.sha256(message.encode("utf-8", errors="ignore")).hexdigest()
            last_hash = _LAST_SENT_HASH.get(msg_type)
            last_sent = _LAST_SENT_TS.get(msg_type, 0.0)
            if msg_type == "STATE_CHANGE" and last_hash == msg_hash:
                continue
            if last_hash == msg_hash and (time.time() - last_sent) < 60:
                continue
            payload = {
                "chat_id": chat_id,
                "text": message,
                "disable_web_page_preview": True,
            }
            start = time.monotonic()
            resp = session.post(tg_send_url, json=payload, timeout=(3, 15))
            duration = time.monotonic() - start
            if qa_mode:
                log_pid(
                    f"[TEL] sendMessage duration={duration:.3f}s status={resp.status_code} "
                    f"qsize={q.qsize()} msg_type={msg_type}"
                )
            if resp.status_code >= 400:
                log(f"[WARN] Telegram retorno {resp.status_code}: {resp.text}")
            _LAST_SENT_HASH[msg_type] = msg_hash
            _LAST_SENT_TS[msg_type] = time.time()
        except Exception as exc:
            log(f"[WARN] No se pudo enviar mensaje a Telegram ({exc})")
            time.sleep(2)


def format_rate(rate: Optional[float]) -> str:
    return f"{rate:.2f} TH/s" if rate is not None else "N/A"


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
) -> None:
    last_info_ts = 0.0
    last_selftest_ts = 0.0
    backoff = 0.2
    while True:
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
            resp = requests.get(tg_updates_url, params=params, timeout=timeout_used)
            if resp.status_code >= 400:
                body = (resp.text or "")[:300]
                log_pid(
                    f"[WARN] getUpdates HTTP {resp.status_code} body='{body}' timeout={timeout_used}s backoff={backoff}s"
                )
                time.sleep(backoff)
                backoff = min(backoff * 2, 5.0)
                continue
            data = resp.json()
            if not data.get("ok"):
                time.sleep(backoff)
                backoff = min(backoff * 2, 5.0)
                continue
            backoff = poll_sleep

            for item in data.get("result", []):
                update_id = item.get("update_id")
                if update_id is None:
                    continue
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

                message = item.get("message", {})
                text = str(message.get("text", "")).strip().lower()
                msg_chat_id = message.get("chat", {}).get("id")
                if msg_chat_id is None or str(msg_chat_id) != str(chat_id):
                    continue
                if text == "status":
                    lock_start = time.monotonic()
                    with snapshot_lock:
                        snapshot = snapshot_ref["value"]
                    lock_wait = time.monotonic() - lock_start
                    if qa_mode and lock_wait > 0.01:
                        log_pid(f"[TEL] snapshot_lock wait={lock_wait:.3f}s")
                    if snapshot:
                        cmd_start = time.monotonic()
                        send_telegram(bot_token, str(msg_chat_id), snapshot, "STATUS", "cmd_status")
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
                        )
                        if qa_mode:
                            if qa_mode:
                                log_pid(f"[TEL] command=status duration={time.monotonic() - cmd_start:.3f}s")
                elif text == "info" or text.startswith("info "):
                    now_ts = time.time()
                    if (now_ts - last_info_ts) < 30:
                        send_telegram(bot_token, str(msg_chat_id), "Info en cooldown. Intente en 30s.", "INFO", "cooldown")
                        continue
                    last_info_ts = now_ts
                    cmd_start = time.monotonic()
                    if text == "info":
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
                        send_telegram(bot_token, str(msg_chat_id), "\n".join(lines), "INFO", "cmd_info")
                    elif text == "info all":
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
                        send_telegram(bot_token, str(msg_chat_id), "\n".join(lines), "INFO", "cmd_info_all")
                    else:
                        miner_token = text.split(" ", 1)[1].strip()
                        miner = resolve_miner(miner_token, miners)
                        if not miner:
                            send_telegram(bot_token, str(msg_chat_id), "Miner no encontrado.", "ERROR", "cmd_info_miner")
                            continue
                        name_display = display_name(miner["name"])
                        host = miner["host"]
                        port = miner["port"]
                        rate, elapsed, responded, summary = read_summary(host, port, timeout=5)
                        if not responded:
                            send_telegram(bot_token, str(msg_chat_id), f"{name_display} ({host}): N/A", "INFO", "cmd_info_miner")
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
                        send_telegram(bot_token, str(msg_chat_id), "\n".join(lines), "INFO", "cmd_info_miner")
                    if qa_mode:
                        log_pid(f"[TEL] command=info duration={time.monotonic() - cmd_start:.3f}s")
                elif text == "selftest" or text == "test":
                    now_ts = time.time()
                    if (now_ts - last_selftest_ts) < 60:
                        send_telegram(bot_token, str(msg_chat_id), "Selftest en cooldown. Intente en 60s.", "SELFTEST", "cooldown")
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
                    send_telegram(
                        bot_token,
                        str(msg_chat_id),
                        f"SELFTEST: Telegram=OK Hashcore={hashcore_ok} Miners={responded}/{total}",
                        "SELFTEST",
                        "cmd_selftest",
                    )
                    if qa_mode:
                        log_pid(f"[TEL] command=selftest duration={time.monotonic() - cmd_start:.3f}s")
                elif text == "help" or text.startswith("help "):
                    cmd_start = time.monotonic()
                    parts = text.split()
                    if len(parts) >= 2:
                        msg = render_help_detail(parts[1])
                    else:
                        msg = render_help_index()
                    send_telegram(
                        bot_token,
                        str(msg_chat_id),
                        msg,
                        "HELP",
                        "cmd_help",
                    )
                    if qa_mode:
                        log_pid(f"[TEL] command=help duration={time.monotonic() - cmd_start:.3f}s")
                elif text.startswith("reboot ") or text.startswith("restart "):
                    action = "reboot" if text.startswith("reboot ") else "restart"
                    cmd_start = time.monotonic()
                    miner_token = text.split(" ", 1)[1].strip()
                    miner = resolve_miner(miner_token, miners)
                    if not miner:
                        send_telegram(bot_token, str(msg_chat_id), "Miner no encontrado.", "ERROR", "cmd_reboot_restart")
                        continue
                    if qa_mode and not qa_allow_actions:
                        log("[WARN] Accion bloqueada por QA (telegram).")
                        send_telegram(
                            bot_token,
                            str(msg_chat_id),
                            "Accion bloqueada (QA). Habilita qa_allow_real_actions=true para permitir reboots reales.",
                            "ERROR",
                            "qa_block",
                        )
                        continue
                    state_key = f"{miner['name']}|{miner['host']}:{miner['port']}"
                    now_ts = time.time()
                    with state_lock:
                        state = states.get(state_key)
                        last_manual = state.last_manual_reboot_ts if state else None
                    if last_manual and (now_ts - last_manual) < 600:
                        send_telegram(bot_token, str(msg_chat_id), "Reboot manual en cooldown.", "REBOOT" if action == "reboot" else "RESTART", "cooldown")
                        continue
                    code = f"{random.randint(100000, 999999)}"
                    with pending_lock:
                        pending_reboots[state_key] = {
                            "code": code,
                            "expires_ts": now_ts + 60,
                            "miner": miner,
                            "action": action,
                        }
                    send_telegram(
                        bot_token,
                        str(msg_chat_id),
                        f"Confirma con: confirm {action} {miner_token} {code}",
                        "REBOOT" if action == "reboot" else "RESTART",
                        "confirm_request",
                    )
                    if qa_mode:
                        log_pid(f"[TEL] command={action} duration={time.monotonic() - cmd_start:.3f}s")
                elif text.startswith("confirm reboot ") or text.startswith("confirm restart "):
                    parts = text.split()
                    if len(parts) < 4:
                        continue
                    action = parts[1]
                    cmd_start = time.monotonic()
                    miner_token = parts[2]
                    code = parts[3]
                    miner = resolve_miner(miner_token, miners)
                    if not miner:
                        send_telegram(bot_token, str(msg_chat_id), "Miner no encontrado.", "ERROR", "cmd_confirm")
                        continue
                    if qa_mode and not qa_allow_actions:
                        log("[WARN] Accion bloqueada por QA (telegram).")
                        send_telegram(
                            bot_token,
                            str(msg_chat_id),
                            "Accion bloqueada (QA). Habilita qa_allow_real_actions=true para permitir reboots reales.",
                            "ERROR",
                            "qa_block",
                        )
                        continue
                    state_key = f"{miner['name']}|{miner['host']}:{miner['port']}"
                    now_ts = time.time()
                    with pending_lock:
                        pending = pending_reboots.get(state_key)
                    if not pending or pending.get("expires_ts", 0) < now_ts:
                        send_telegram(bot_token, str(msg_chat_id), "Confirmacion expirada.", "ERROR", "cmd_confirm")
                        continue
                    if pending.get("code") != code:
                        send_telegram(bot_token, str(msg_chat_id), "Codigo invalido.", "ERROR", "cmd_confirm")
                        continue
                    if pending.get("action") != action:
                        send_telegram(bot_token, str(msg_chat_id), "Accion invalida.", "ERROR", "cmd_confirm")
                        continue
                    ok, msg = run_hashcore_cli(hashcore_cfg, miner, action, config, qa_mode, qa_allow_actions)
                    if not ok:
                        send_telegram(bot_token, str(msg_chat_id), msg, "ERROR", "cmd_confirm")
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
                    )
                    if qa_mode:
                        log_pid(f"[TEL] command=confirm_{action} duration={time.monotonic() - cmd_start:.3f}s")
        except Exception as exc:
            log_pid(
                f"[WARN] getUpdates exception type={type(exc).__name__} msg='{exc}' timeout={timeout_used}s backoff={backoff}s"
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
    reboot_cooldown_seconds = int(config.get("reboot_cooldown_seconds", 1800))
    reboot_window_seconds = int(config.get("reboot_window_seconds", 300))
    low_sustained_seconds = 600
    auto_reboot_window_seconds = int(config.get("auto_reboot_window_seconds", 21600))
    max_reboots_per_window = int(config.get("max_reboots_per_window", 3))
    if qa_mode:
        poll_seconds = int(config.get("qa_poll_seconds", 2))
        reboot_cooldown_seconds = int(config.get("qa_reboot_cooldown_seconds", 120))
        reboot_window_seconds = int(config.get("qa_reboot_window_seconds", 30))
        low_sustained_seconds = int(config.get("qa_low_seconds", 60))
        auto_reboot_window_seconds = int(config.get("qa_auto_reboot_window_seconds", 600))
    offline_is_actionable = bool(config.get("offline_is_actionable", True))
    hashcore_cfg = config.get("hashcore", {})

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
        ),
        daemon=True,
    )
    telegram_thread.start()

    log("Inicio de monitoreo.")

    try:
        first_tick = True
        while True:
            tick_start = time.monotonic()
            now_ts = time.time()
            state_message_needed = False
            reboot_names_tick = []
            miner_lines = []
            startup_lines = [] if first_tick else None
            degraded_candidates = []
            for miner in valid_miners:
                name = miner["name"]
                name_display = display_name(name)
                host = miner["host"]
                port = miner["port"]
                state_key = f"{name}|{host}:{port}"
                state = states.setdefault(state_key, MinerState())

                rate_ths, elapsed, responded, _ = read_summary(host, port)
                active_boards = None
                if responded:
                    active_boards, _ = read_stats_active_boards(host, port)
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

                if not state.initialized:
                    state.initialized = True
                    if first_tick and (not notify_startup) and notify_initial_non_ok:
                        if new_state == STATE_HASHBOARD:
                            state_message_needed = True
                        elif new_state == STATE_LOW:
                            state_message_needed = True
                        elif new_state == STATE_OFFLINE and notify_offline and offline_is_actionable:
                            state_message_needed = True

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
                auto_reboot_candidate = responded and rate_ths is not None and rate_ths < threshold_ths
                if auto_reboot_candidate and new_state != STATE_LOW:
                    log(
                        f"[AUTO-REBOOT] blocked_by=not_low miner={name_display} "
                        f"rate_ths={rate_ths} threshold_ths={threshold_ths} "
                        f"low_streak={state.low_streak}/{fails_before_alert}"
                    )
                if (not responded or rate_ths is None) and prev_state == STATE_LOW:
                    log(
                        f"[AUTO-REBOOT] blocked_by=invalid_signal miner={name_display} "
                        f"responded={responded} rate_ths={rate_ths}"
                    )
                if new_state == STATE_LOW and state.low_since_ts:
                    if startup_guard_active:
                        log(
                            f"[AUTO-REBOOT] blocked_by=startup_guard miner={name_display} "
                            f"since_start={now_ts - process_start_ts:.1f}s guard={startup_guard_seconds}s"
                        )
                    elif (now_ts - state.low_since_ts) < low_sustained_seconds:
                        log(
                            f"[AUTO-REBOOT] blocked_by=not_sustained miner={name_display} "
                            f"elapsed={(now_ts - state.low_since_ts):.0f}s required={low_sustained_seconds}s"
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
                                log(
                                    f"[AUTO-REBOOT] blocked_by=cooldown miner={name_display} "
                                    f"cooldown_delta={cooldown_delta:.0f}s cooldown={reboot_cooldown_seconds}s"
                                )
                                continue
                        if len(state.auto_reboot_timestamps) >= max_reboots_per_window:
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
                                    f"({format_rate(rate_ths)} < {threshold_ths:.2f} TH/s) -> reboot enviado",
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
                                            f"AUTO-REBOOT FAILED: {name_display}. {msg}",
                                            "ERROR",
                                            "auto_reboot_failed",
                                        )
                                else:
                                    send_telegram(
                                        bot_token,
                                        str(chat_id),
                                        f"AUTO-REBOOT FAILED: {name_display}. {msg}",
                                        "ERROR",
                                        "auto_reboot_failed",
                                    )

                if not first_tick and new_state != prev_state:
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
                        if notify_offline and offline_is_actionable:
                            state_message_needed = True
                    elif new_state == STATE_HASHBOARD:
                        log(
                            f"[STATE] {name} ({host}:{port}) -> HASHBOARD "
                            f"boards={active_boards}/{expected_boards} ({now_str()})"
                        )
                        state_message_needed = True
                    elif new_state == STATE_LOW:
                        log(
                            f"[STATE] {name} ({host}:{port}) OK/OFFLINE -> LOW "
                            f"{format_rate(rate_ths)} < {threshold_ths:.2f} TH/s "
                            f"({now_str()})"
                        )
                        state_message_needed = True
                    elif new_state == STATE_OK and prev_state in (STATE_LOW, STATE_OFFLINE, STATE_HASHBOARD):
                        log(
                            f"[STATE] {name} ({host}:{port}) {prev_state} -> OK "
                            f"{format_rate(rate_ths)} >= {threshold_ths:.2f} TH/s "
                            f"({now_str()})"
                        )
                        state_message_needed = True

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

                label = ""
                if new_state == STATE_HASHBOARD:
                    label = " [HASHBOARD]"
                elif new_state == STATE_LOW:
                    label = " [LOW]"
                elif new_state == STATE_OFFLINE:
                    label = " [OFFLINE]"
                miner_lines.append(
                    f"- {name_display} ({host}): {format_rate(rate_ths)}{label}"
                )
                if startup_lines is not None:
                    if not responded:
                        startup_label = " [OFFLINE]"
                    elif rate_ths is not None and rate_ths < threshold_ths:
                        startup_label = " [LOW]"
                    else:
                        startup_label = " [OK]"
                    startup_lines.append(
                        f"- {name_display} ({host}): {format_rate(rate_ths)}{startup_label}"
                    )
                if state.degraded_mode:
                    degraded_candidates.append(state)

            status_lines = [
                f"STATUS ({now_str()})",
                "",
            ]
            status_lines.extend(miner_lines)
            with snapshot_lock:
                snapshot_ref["value"] = "\n".join(status_lines)

            if first_tick and notify_startup:
                message_lines = [
                    f"STARTUP ({now_str()})",
                    "",
                ]
                message_lines.extend(startup_lines or miner_lines)
                if (not qa_mode) or qa_notify:
                    send_telegram(bot_token, str(chat_id), "\n".join(message_lines), "STARTUP", "startup")
            elif state_message_needed:
                message_lines = [
                    f"STATE CHANGE ({now_str()})",
                    "",
                ]
                message_lines.extend(miner_lines)
                if reboot_names_tick:
                    message_lines.append(f"Reboots: {', '.join(reboot_names_tick)}")
                if (not qa_mode) or qa_notify:
                    send_telegram(bot_token, str(chat_id), "\n".join(message_lines), "STATE_CHANGE", "state_change")
            else:
                if degraded_candidates:
                    ar_now = argentina_now()
                    if 6 <= ar_now.hour < 24:
                        hourly_needed = False
                        for st in degraded_candidates:
                            if st.last_hourly_status_ts is None or (now_ts - st.last_hourly_status_ts) >= 3600:
                                hourly_needed = True
                                break
                        if hourly_needed:
                            if (not qa_mode) or qa_notify:
                                send_telegram(bot_token, str(chat_id), "\n".join(status_lines), "STATUS", "degraded_hourly")
                            for st in degraded_candidates:
                                st.last_hourly_status_ts = now_ts

            with last_update_lock:
                current_last_update_id = last_update_id_ref["value"]
            with state_lock:
                save_state(state_path, states, current_last_update_id)
            first_tick = False
            if qa_mode or qa_verbose:
                log_pid(f"[TICK] duration={time.monotonic() - tick_start:.3f}s qsize={_TELEGRAM_QUEUE.qsize()}")
            time.sleep(poll_seconds)
    except KeyboardInterrupt:
        log("Detenido por usuario")
    finally:
        release_mutex()


if __name__ == "__main__":
    main()
