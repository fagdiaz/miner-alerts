"""System, Time, Process and Mutex Utilities (Spec 091).

Encapsulates OS-level Windows mutex primitives, subprocess execution
without console window popups, Hashcore CLI invocation, and timezone-aware
datetime helpers.
"""

from __future__ import annotations

import ctypes
import logging
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Tuple

logger = logging.getLogger("miner-alerts")

_MUTEX_HANDLE: Optional[int] = None
_NO_WINDOW_CREATION_FLAGS: int = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def now_str() -> str:
    """Return local timestamp string in YYYY-MM-DD HH:MM:SS format."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def argentina_now() -> datetime:
    """Return current wall-clock datetime in Argentina time (UTC-3)."""
    return datetime.now(timezone.utc).replace(tzinfo=None).replace(microsecond=0) + timedelta(hours=-3)


def _execute_subprocess_no_window(cmd: Any, **kwargs: Any) -> subprocess.CompletedProcess:
    """Windows subprocess execution ensuring no console window is spawned."""
    kwargs.pop("creationflags", None)
    return subprocess.run(cmd, creationflags=_NO_WINDOW_CREATION_FLAGS, **kwargs)


def _hashcore_cli_path(hashcore_cfg: dict) -> str:
    """Return path to Hashcore CLI wrapper executable."""
    from app.network.hashcore_client import get_hashcore_cli_path
    return get_hashcore_cli_path(hashcore_cfg)


def run_hashcore_discovery(hashcore_cfg: dict) -> None:
    """Run Hashcore CLI discovery to locate all ASIC miners on subnet."""
    from app.network.hashcore_client import run_hashcore_discovery as _net_run_hashcore_discovery

    _net_run_hashcore_discovery(
        hashcore_cfg=hashcore_cfg,
        runner=_execute_subprocess_no_window,
        log_fn=logger.info,
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
    """Execute Hashcore CLI action with subprocess isolation."""
    from app.network.hashcore_client import run_hashcore_cli as _net_run_hashcore_cli

    return _net_run_hashcore_cli(
        hashcore_cfg=hashcore_cfg,
        miner=miner,
        action=action,
        config=config,
        qa_mode=qa_mode,
        qa_allow_actions=qa_allow_actions,
        args_override=args_override,
        runner=_execute_subprocess_no_window,
        log_fn=logger.info,
    )


def _mutex_name() -> str:
    """Return the global Windows mutex name for single-instance enforcement."""
    return r"Global\MinerAlertsMonitor_fagdiaz"


def acquire_mutex_or_exit(mutex_name: str) -> int:
    """Acquire named Windows mutex or exit process immediately if another instance runs."""
    global _MUTEX_HANDLE
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.CreateMutexW(None, True, mutex_name)
    if not handle:
        logger.error("ERROR: No se pudo crear el mutex.")
        sys.exit(1)
    last_error = ctypes.get_last_error()
    if last_error == 183:  # ERROR_ALREADY_EXISTS
        logger.warning(
            "PID=%d PPID=%d mutex=%s last_error=%d acquired=False",
            os.getpid(),
            os.getppid(),
            mutex_name,
            last_error,
        )
        logger.warning("Ya hay otra instancia del monitor corriendo (mutex). Saliendo.")
        kernel32.CloseHandle(handle)
        sys.exit(0)
    logger.info(
        "PID=%d PPID=%d mutex=%s last_error=%d acquired=True",
        os.getpid(),
        os.getppid(),
        mutex_name,
        last_error,
    )
    _MUTEX_HANDLE = handle
    return last_error


def release_mutex() -> None:
    """Release and close the named Windows mutex handle."""
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
