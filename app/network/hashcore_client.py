from __future__ import annotations

import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Tuple

_LOGGER = logging.getLogger(__name__)
_NO_WINDOW_CREATION_FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _default_log(msg: str) -> None:
    _LOGGER.info(msg)


def qa_verbose_enabled(config: Mapping[str, Any]) -> bool:
    """Check if QA verbose logging is requested via environment or config."""
    env = os.getenv("QA_VERBOSE", "").strip().lower()
    if env in ("1", "true", "yes", "on"):
        return True
    if env in ("0", "false", "no", "off"):
        return False
    return bool(config.get("qa_verbose", False))


def get_hashcore_cli_path(hashcore_cfg: Mapping[str, Any]) -> str:
    """Resolve the executable/batch path for the Hashcore Toolkit CLI."""
    return str(hashcore_cfg.get("cli_bat_path") or hashcore_cfg.get("cli_path") or "")


# Backwards compatibility alias
_hashcore_cli_path = get_hashcore_cli_path


class HashcoreClient:
    """
    Client for interacting with the Hashcore Toolkit CLI.
    
    Encapsulates command construction, Windows windowless process execution,
    QA guardrails, and timeouts.
    """

    def __init__(
        self,
        hashcore_cfg: Mapping[str, Any],
        config: Optional[Mapping[str, Any]] = None,
        qa_mode: bool = False,
        qa_allow_actions: bool = False,
        runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
        log_fn: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.hashcore_cfg = dict(hashcore_cfg)
        self.config = dict(config or {})
        self.qa_mode = qa_mode
        self.qa_allow_actions = qa_allow_actions
        self.runner = runner
        self.log = log_fn or _default_log

    @property
    def cli_path(self) -> str:
        return get_hashcore_cli_path(self.hashcore_cfg)

    def is_enabled(self) -> bool:
        return bool(self.hashcore_cfg.get("enabled", True))

    def discover(self) -> None:
        """Run CLI discovery to inspect available command arguments."""
        run_hashcore_discovery(
            hashcore_cfg=self.hashcore_cfg,
            runner=self.runner,
            log_fn=self.log,
        )

    def reboot(
        self,
        miner: Mapping[str, Any],
        args_override: Optional[list] = None,
    ) -> Tuple[bool, str]:
        """Trigger a reboot action for the specified miner."""
        return self.execute(miner, action="reboot", args_override=args_override)

    def restart(
        self,
        miner: Mapping[str, Any],
        args_override: Optional[list] = None,
    ) -> Tuple[bool, str]:
        """Trigger a restart action for the specified miner."""
        return self.execute(miner, action="restart", args_override=args_override)

    def execute(
        self,
        miner: Mapping[str, Any],
        action: str,
        args_override: Optional[list] = None,
    ) -> Tuple[bool, str]:
        """Execute a general hardware action via Hashcore Toolkit CLI."""
        return run_hashcore_cli(
            hashcore_cfg=self.hashcore_cfg,
            miner=dict(miner),
            action=action,
            config=self.config,
            qa_mode=self.qa_mode,
            qa_allow_actions=self.qa_allow_actions,
            args_override=args_override,
            runner=self.runner,
            log_fn=self.log,
        )


def run_hashcore_discovery(
    hashcore_cfg: dict,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    log_fn: Optional[Callable[[str], None]] = None,
) -> None:
    """Discover available commands and arguments from Hashcore CLI."""
    log = log_fn or _default_log
    if not hashcore_cfg.get("enabled", True):
        return
    cli_path = get_hashcore_cli_path(hashcore_cfg)
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
            result = runner(
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
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    log_fn: Optional[Callable[[str], None]] = None,
) -> Tuple[bool, str]:
    """
    Execute an action on a miner using the Hashcore Toolkit CLI.
    
    Protects production by enforcing QA blocks unless qa_allow_actions=True.
    """
    log = log_fn or _default_log
    if not hashcore_cfg.get("enabled", True):
        return False, "Hashcore CLI deshabilitado en config."
    if qa_mode and not qa_allow_actions:
        log("[WARN] Accion bloqueada por QA (hashcore).")
        return False, "Accion bloqueada (QA). Habilita qa_allow_real_actions=true para permitir reboots reales."
    cli_path = get_hashcore_cli_path(hashcore_cfg)
    if not cli_path or not Path(cli_path).exists():
        return False, f"Hashcore CLI no encontrado: {cli_path or 'VACIO'}."
    if args_override is None:
        key = "reboot_args_template" if action == "reboot" else "restart_args_template"
        args_template = hashcore_cfg.get(key)
        if not isinstance(args_template, list) or not args_template:
            run_hashcore_discovery(hashcore_cfg, runner=runner, log_fn=log)
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
        result = runner(
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
                log(f"[HASHCORE] stdout: {result.stdout.strip()[:300]}")
        if result.returncode != 0:
            return False, f"Hashcore CLI fallo (code {result.returncode})."
        return True, "OK"
    except subprocess.TimeoutExpired:
        log(f"[HASHCORE] timeout ejecutando {action} para {miner['host']}")
        return False, "Timeout ejecutando Hashcore CLI (30s)."
    except Exception as exc:
        log(f"[HASHCORE] error inesperado ejecutando {action}: {exc}")
        return False, f"Hashcore CLI error: {exc}"
