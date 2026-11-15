"""Autonomous Stock Firmware Recovery Handler (Spec 093).

Supervises miners that have accidentally reverted to factory Bitmain firmware
after power cuts or dirty shutdowns.

Recovery ladder:
1. First attempt: Safe HTTP Digest reboot to /cgi-bin/reboot.cgi (BeagleBone Black dual-boot NAND switch).
2. Second attempt (if reboot fails to recover VNish): Automatic reflash of VNish 1.2.6
   using FirmwareFlasher (C:\\asicto\\asicto-s19jpro-bb-nand-v1.2.6-install.tar.gz)
   and auto-restoration of golden profile from data/miner_profiles/{miner_name}.json.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Set, Tuple

import requests
from requests.auth import HTTPDigestAuth

from app.network.firmware_flasher import (
    DEFAULT_PACKAGE_PATH,
    flash_bitmain_nand,
    is_stock_bitmain,
)
from tools.backup_miner_profiles import restore_miner_profile

_LOGGER = logging.getLogger(__name__)

# State tracking across ticks
_RECOVERY_LOCK = threading.Lock()
_RECOVERY_ATTEMPTS: Dict[str, int] = {}
_LAST_RECOVERY_TS: Dict[str, float] = {}
_ACTIVE_RECOVERY_HOSTS: Set[str] = set()

DEFAULT_REBOOT_COOLDOWN_SECONDS = 180.0
DEFAULT_FLASH_COOLDOWN_SECONDS = 300.0


def stock_recovery_candidate(active_boards: Optional[int], stock_fallback: bool,
                             expected_boards: int = 3) -> bool:
    """Missing telemetry is not evidence of stock firmware or broken boards."""
    return bool(stock_fallback) or (
        active_boards is not None and 0 <= active_boards < expected_boards)


def reboot_stock_bitmain(
    host: str,
    username: str = "root",
    password: str = "root",
    timeout_s: float = 5.0,
) -> Tuple[bool, str]:
    """Issues an authenticated HTTP Digest reboot request to factory Bitmain firmware."""
    url = f"http://{host}/cgi-bin/reboot.cgi"
    auth = HTTPDigestAuth(username, password)
    try:
        resp = requests.post(url, auth=auth, timeout=timeout_s)
        if resp.status_code == 200:
            return True, "Reboot HTTP 200 aceptado por Bitmain stock"
        return False, f"HTTP status {resp.status_code}: {resp.text[:100]}"
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
        # Bitmain boards often drop the socket immediately upon reboot
        return True, "Reinicio aceptado (socket cerrado por hardware)"
    except Exception as exc:
        return False, f"Excepción en reboot: {type(exc).__name__}: {exc}"


def handle_stock_firmware_recovery(
    host: str,
    miner_name: str,
    config: Dict[str, Any],
    bot_token: Optional[str] = None,
    chat_id: Optional[str] = None,
    send_telegram_fn: Optional[Callable[..., Any]] = None,
    qa_mode: bool = False,
    qa_notify: bool = False,
    now_ts: Optional[float] = None,
    package_path: Optional[str] = None,
) -> Tuple[bool, str]:
    """Evaluates and triggers appropriate recovery step for a miner in stock firmware.
    
    Returns (action_taken, status_description).
    """
    if qa_mode:
        return False, "blocked_by_qa"
    current_ts = now_ts or time.time()
    auto_recovery_enabled = bool(config.get("stock_firmware_auto_recovery_enabled", True))
    if not auto_recovery_enabled:
        return False, "Auto-recuperación de firmware desactivada en config"

    with _RECOVERY_LOCK:
        if host in _ACTIVE_RECOVERY_HOSTS:
            return False, f"Recuperación ya en curso para {host}"

        attempts = _RECOVERY_ATTEMPTS.get(host, 0)
        last_ts = _LAST_RECOVERY_TS.get(host, 0.0)

        # Step 1: First attempt -> Send Bitmain reboot
        if attempts == 0:
            if (current_ts - last_ts) < DEFAULT_REBOOT_COOLDOWN_SECONDS:
                return False, f"En cooldown de reboot ({current_ts - last_ts:.0f}s < {DEFAULT_REBOOT_COOLDOWN_SECONDS}s)"

            _ACTIVE_RECOVERY_HOSTS.add(host)
            _RECOVERY_ATTEMPTS[host] = 1
            _LAST_RECOVERY_TS[host] = current_ts

            def _async_reboot():
                try:
                    if send_telegram_fn and bot_token and chat_id and ((not qa_mode) or qa_notify):
                        send_telegram_fn(
                            bot_token,
                            str(chat_id),
                            f"⚠️ *FIRMWARE STOCK EN {miner_name}*\n\n"
                            f"Host: `{host}`\n"
                            "El equipo revirtió a Bitmain factory. Ejecutando reinicio de NAND...",
                            "WARNING",
                            f"stock_reboot_{miner_name}",
                        )
                    _LOGGER.info("[FIRMWARE_RECOVERY] Disparando reinicio Bitmain stock en %s (%s)...", miner_name, host)
                    ok, msg = reboot_stock_bitmain(host)
                    _LOGGER.info("[FIRMWARE_RECOVERY] Resultado reinicio %s: ok=%s msg=%s", miner_name, ok, msg)
                finally:
                    with _RECOVERY_LOCK:
                        _ACTIVE_RECOVERY_HOSTS.discard(host)

            threading.Thread(target=_async_reboot, daemon=True, name=f"StockReboot_{miner_name}").start()
            return True, f"Iniciado reinicio Bitmain stock para {miner_name}"

        # Step 2: Second attempt -> Flash VNish NAND package + restore golden profile
        elif attempts == 1:
            if not bool(config.get("stock_firmware_reflash_enabled", True)):
                return False, "Reflash automático desactivado en config"
            if (current_ts - last_ts) < DEFAULT_FLASH_COOLDOWN_SECONDS:
                return False, f"Esperando resultado de reboot ({current_ts - last_ts:.0f}s < {DEFAULT_FLASH_COOLDOWN_SECONDS}s)"

            # Verify if still in stock Bitmain
            if not is_stock_bitmain(host):
                # Recovered on its own or after reboot!
                _LOGGER.info("[FIRMWARE_RECOVERY] %s ya no reporta firmware Bitmain stock. Recuperación exitosa.", miner_name)
                _RECOVERY_ATTEMPTS[host] = 0
                return False, f"{miner_name} recuperó VNish tras el reinicio"

            _ACTIVE_RECOVERY_HOSTS.add(host)
            _RECOVERY_ATTEMPTS[host] = 2
            _LAST_RECOVERY_TS[host] = current_ts

            tarball = package_path or config.get("vnish_nand_package_path") or DEFAULT_PACKAGE_PATH

            def _async_flash_and_restore():
                try:
                    if send_telegram_fn and bot_token and chat_id and ((not qa_mode) or qa_notify):
                        send_telegram_fn(
                            bot_token,
                            str(chat_id),
                            f"🚨 *REFLASH VNISH 1.2.6 EN {miner_name}*\n\n"
                            f"Host: `{host}`\n"
                            "El reinicio no recuperó VNish. Flasheando NAND desde instalador local y restaurando perfil...",
                            "ERROR",
                            f"stock_reflash_{miner_name}",
                        )
                    _LOGGER.info("[FIRMWARE_RECOVERY] Flasheando paquete %s en %s...", tarball, host)
                    ok_flash, msg_flash = flash_bitmain_nand(host, package_path=tarball, timeout_s=180.0)
                    _LOGGER.info("[FIRMWARE_RECOVERY] Flasheo en %s: ok=%s (%s)", host, ok_flash, msg_flash)

                    if ok_flash:
                        # Wait 90 seconds for NAND boot
                        time.sleep(90.0)
                        # Inject golden profile
                        pw = config.get("vnish_api_password", "admin")
                        ok_prof, msg_prof = restore_miner_profile(miner_name, host, password=pw)
                        _LOGGER.info("[FIRMWARE_RECOVERY] Restauración de perfil en %s: ok=%s (%s)", host, ok_prof, msg_prof)

                        if send_telegram_fn and bot_token and chat_id and ((not qa_mode) or qa_notify):
                            send_telegram_fn(
                                bot_token,
                                str(chat_id),
                                f"✅ *VNISH RESTABLECIDO EN {miner_name}*\n\n"
                                f"Firmware 1.2.6 reinstalado y perfil dorado inyectado exitosamente.",
                                "STATUS",
                                f"stock_restored_{miner_name}",
                            )
                        with _RECOVERY_LOCK:
                            _RECOVERY_ATTEMPTS[host] = 0
                except Exception as exc:
                    _LOGGER.exception("[FIRMWARE_RECOVERY] Error crítico durante reflash de %s: %s", host, exc)
                finally:
                    with _RECOVERY_LOCK:
                        _ACTIVE_RECOVERY_HOSTS.discard(host)

            threading.Thread(target=_async_flash_and_restore, daemon=True, name=f"StockFlash_{miner_name}").start()
            return True, f"Iniciado flasheo de VNish 1.2.6 para {miner_name}"

        else:
            return False, f"Límite de intentos de auto-recuperación alcanzado para {miner_name}"


def reset_stock_recovery_state(host: Optional[str] = None) -> None:
    """Helper for testing and manual resets."""
    with _RECOVERY_LOCK:
        if host:
            _RECOVERY_ATTEMPTS.pop(host, None)
            _LAST_RECOVERY_TS.pop(host, None)
            _ACTIVE_RECOVERY_HOSTS.discard(host)
        else:
            _RECOVERY_ATTEMPTS.clear()
            _LAST_RECOVERY_TS.clear()
            _ACTIVE_RECOVERY_HOSTS.clear()
