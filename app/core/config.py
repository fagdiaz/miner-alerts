"""Configuration and Operational Logging (Spec 091).

Encapsulates configuration JSON loading, QA mode discovery, database path
resolution, and rotating logger initialization.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

_LOGGER: Optional[logging.Logger] = None
_GLOBAL_LOADED_CONFIG: Optional[Dict[str, Any]] = None
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def log(msg: str) -> None:
    """Authoritative monitor log output with timestamping and rotating file sink."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    if _LOGGER:
        _LOGGER.info(line)
    else:
        print(line, flush=True)


def log_pid(msg: str) -> None:
    """Log formatted message prefixed by current process PID."""
    log(f"PID={os.getpid()} {msg}")


def init_logger_from_config(config: dict) -> None:
    """Initialize rotating file logger according to config settings."""
    global _LOGGER
    log_file_path = str(config.get("log_file_path", "") or "").strip()
    if not log_file_path:
        return
    log_path = Path(log_file_path)
    if not log_path.is_absolute():
        log_path = _REPO_ROOT / log_path
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


def load_config() -> Dict[str, Any]:
    """Load configuration from environment variable or default app/config.json."""
    global _GLOBAL_LOADED_CONFIG
    config_env = os.getenv("MINER_ALERTS_CONFIG") or os.getenv("CONFIG_PATH")
    if config_env:
        config_path = Path(config_env).expanduser()
    else:
        config_path = Path(__file__).resolve().parent.parent / "config.json"
    config_path = config_path.resolve()

    exists = config_path.exists()
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
        _GLOBAL_LOADED_CONFIG = config
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
        p = _REPO_ROOT / p
    return str(p)


def qa_enabled(config: Mapping[str, Any]) -> Tuple[bool, str]:
    """Check QA mode enablement with override precedence."""
    force_env = os.getenv("QA_MODE_FORCE", "").strip().lower()
    if force_env in ("1", "true", "yes", "on"):
        env = os.getenv("QA_MODE", "").strip().lower()
        if env in ("1", "true", "yes", "on"):
            return True, "env-forced"
        if env in ("0", "false", "no", "off"):
            return False, "env-forced"
    return bool(config.get("qa_mode", False)), "config"


def qa_notify_enabled(config: Mapping[str, Any]) -> bool:
    """Check if QA mode allows sending notifications."""
    env = os.getenv("QA_NOTIFY", "").strip().lower()
    if env in ("1", "true", "yes", "on"):
        return True
    if env in ("0", "false", "no", "off"):
        return False
    return bool(config.get("qa_notify", False))


def qa_allow_real_actions(config: Mapping[str, Any]) -> bool:
    """Check if QA mode allows real actions on physical hardware."""
    env = os.getenv("QA_ALLOW_REAL_ACTIONS", "").strip().lower()
    if env in ("1", "true", "yes", "on"):
        return True
    if env in ("0", "false", "no", "off"):
        return False
    return bool(config.get("qa_allow_real_actions", False))


def qa_verbose_enabled(config: Mapping[str, Any]) -> bool:
    """Check if verbose QA output is enabled."""
    env = os.getenv("QA_VERBOSE", "").strip().lower()
    if env in ("1", "true", "yes", "on"):
        return True
    if env in ("0", "false", "no", "off"):
        return False
    return bool(config.get("qa_verbose", False))


import re


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

