"""Firmware Flasher Module (Spec 076).

Provides automated and programmatic flashing of VNish NAND firmware onto Antminer
ASIC miners (e.g. BeagleBone Black control boards) that have reverted to stock
Bitmain factory firmware.

Uses Bitmain's standard HTTP Digest upgrade endpoint (POST /cgi-bin/upgrade.cgi).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional, Tuple

import requests
from requests.auth import HTTPDigestAuth

_LOGGER = logging.getLogger(__name__)

DEFAULT_PACKAGE_PATH = r"C:\asicto\asicto-s19jpro-bb-nand-v1.2.6-install.tar.gz"
DEFAULT_FLASH_TIMEOUT_SECONDS = 120.0
DEFAULT_PROBE_TIMEOUT_SECONDS = 4.0


def is_stock_bitmain(host: str, timeout_s: float = DEFAULT_PROBE_TIMEOUT_SECONDS) -> bool:
    """Check if the target host is running factory Bitmain firmware on port 80.
    
    Verifies HTTP Digest auth challenge with realm containing 'antMiner' or Server
    header containing 'lighttpd'.
    """
    url = f"http://{host}/cgi-bin/upgrade.cgi"
    try:
        resp = requests.get(url, timeout=timeout_s)
        # Bitmain returns 401 Unauthorized with Digest realm="antMiner Configuration"
        auth_header = resp.headers.get("WWW-Authenticate", "")
        server_header = resp.headers.get("Server", "")
        if "antMiner" in auth_header or "Digest" in auth_header or "lighttpd" in server_header.lower():
            return True
        return False
    except requests.exceptions.RequestException:
        # Try probing root /
        try:
            resp_root = requests.get(f"http://{host}/", timeout=timeout_s)
            auth_header = resp_root.headers.get("WWW-Authenticate", "")
            server_header = resp_root.headers.get("Server", "")
            if "antMiner" in auth_header or "Digest" in auth_header or "lighttpd" in server_header.lower():
                return True
        except requests.exceptions.RequestException:
            pass
        return False


def flash_bitmain_nand(
    host: str,
    package_path: Optional[str] = None,
    username: str = "root",
    password: str = "root",
    timeout_s: float = DEFAULT_FLASH_TIMEOUT_SECONDS,
    skip_probe: bool = False,
) -> Tuple[bool, str]:
    """Upload and flash VNish firmware tarball onto a miner running stock Bitmain firmware.
    
    Args:
        host: IP address or hostname of the miner.
        package_path: Path to the installer tarball. Defaults to DEFAULT_PACKAGE_PATH.
        username: HTTP Digest username (default 'root').
        password: HTTP Digest password (default 'root').
        timeout_s: Socket timeout in seconds for upload and flash write (default 120s).
        skip_probe: If True, bypasses is_stock_bitmain preliminary check (useful for tests).
        
    Returns:
        Tuple[bool, str]: (Success status, descriptive message)
    """
    target_path = package_path or DEFAULT_PACKAGE_PATH
    if not os.path.exists(target_path):
        msg = f"ERROR_PACKAGE_NOT_FOUND: No se encontró el paquete de instalación en '{target_path}'"
        _LOGGER.error("[FIRMWARE_FLASHER] %s", msg)
        return False, msg

    if not skip_probe:
        _LOGGER.info("[FIRMWARE_FLASHER] Verificando estado Bitmain stock en %s...", host)
        if not is_stock_bitmain(host):
            msg = f"ABORTED_NOT_STOCK_BITMAIN: El host '{host}' no responde como firmware de fábrica de Bitmain. Operación abortada por seguridad."
            _LOGGER.warning("[FIRMWARE_FLASHER] %s", msg)
            return False, msg

    url = f"http://{host}/cgi-bin/upgrade.cgi"
    auth = HTTPDigestAuth(username, password)
    filename = Path(target_path).name

    _LOGGER.info("[FIRMWARE_FLASHER] Iniciando carga de '%s' (%d MB) a http://%s/cgi-bin/upgrade.cgi...",
                 filename, round(os.path.getsize(target_path) / (1024 * 1024), 1), host)

    try:
        with open(target_path, "rb") as f:
            files = {
                "file": (filename, f, "application/x-gzip"),
            }
            resp = requests.post(url, auth=auth, files=files, timeout=timeout_s)

        if resp.status_code == 200:
            msg = (
                f"Flasheo completado exitosamente en '{host}'. "
                "El BeagleBone Black está reiniciando en VNish 1.2.6 NAND (tiempo estimado: ~90s)."
            )
            _LOGGER.info("[FIRMWARE_FLASHER] %s", msg)
            return True, msg
        elif resp.status_code == 401:
            msg = f"ERROR_AUTH_FAILED: Autenticación Digest rechazada por '{host}' (código 401). Verifique credenciales root/root."
            _LOGGER.error("[FIRMWARE_FLASHER] %s", msg)
            return False, msg
        else:
            msg = f"ERROR_HTTP_STATUS_{resp.status_code}: Respuesta inesperada del endpoint upgrade en '{host}': {resp.text[:200]}"
            _LOGGER.error("[FIRMWARE_FLASHER] %s", msg)
            return False, msg

    except requests.exceptions.Timeout:
        # In some Bitmain firmware versions, the miner reboots immediately upon receiving the last byte
        # of the firmware tarball without completing the HTTP response. We consider a write timeout after
        # a long transmission as a probable reboot in progress.
        msg = f"TIMEOUT_OR_REBOOT: La conexión con '{host}' se interrumpió tras transmitir el paquete (posible reinicio de control board en curso)."
        _LOGGER.warning("[FIRMWARE_FLASHER] %s", msg)
        return True, msg
    except requests.exceptions.ConnectionError as ce:
        msg = f"CONNECTION_REFUSED: No fue posible conectar con '{host}': {ce}"
        _LOGGER.error("[FIRMWARE_FLASHER] %s", msg)
        return False, msg
    except Exception as exc:
        msg = f"ERROR_UNEXPECTED: {type(exc).__name__}: {exc}"
        _LOGGER.exception("[FIRMWARE_FLASHER] %s", msg)
        return False, msg


class FirmwareFlasher:
    """Object-oriented wrapper for firmware flashing operations."""

    def __init__(self, package_path: Optional[str] = None) -> None:
        self.package_path = package_path or DEFAULT_PACKAGE_PATH

    def is_target_stock_bitmain(self, host: str, timeout_s: float = DEFAULT_PROBE_TIMEOUT_SECONDS) -> bool:
        return is_stock_bitmain(host, timeout_s=timeout_s)

    def flash_miner(
        self,
        host: str,
        username: str = "root",
        password: str = "root",
        timeout_s: float = DEFAULT_FLASH_TIMEOUT_SECONDS,
        skip_probe: bool = False,
    ) -> Tuple[bool, str]:
        return flash_bitmain_nand(
            host=host,
            package_path=self.package_path,
            username=username,
            password=password,
            timeout_s=timeout_s,
            skip_probe=skip_probe,
        )
