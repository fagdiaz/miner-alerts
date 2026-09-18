"""Miner Provisioner Module (Spec 076).

Handles automated and transactional provisioning of ASIC miners post-boot or
post-firmware reflash. Injects Binance pools, nominal overclock presets,
voltage/frequency targets, and individual chip tuning matrices from golden profiles
stored in `data/miner_profiles/{miner_name}.json`.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests

from app.governance.adaptive_contingency import normalize_miner_name
from app.vnish.client import lock_miner, restart_mining, unlock_miner

_LOGGER = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_PROFILES_DIR = REPO_ROOT / "data" / "miner_profiles"


def find_profile_path(miner_name: str, profiles_dir: Optional[Path | str] = None) -> Optional[Path]:
    """Resolve the JSON profile file for a given miner name."""
    p_dir = Path(profiles_dir) if profiles_dir else DEFAULT_PROFILES_DIR
    if not p_dir.exists():
        return None

    norm = normalize_miner_name(miner_name)
    candidates = [
        p_dir / f"{miner_name}.json",
        p_dir / f"{norm}.json",
        p_dir / f"S19JPRO-{miner_name}.json",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def provision_miner_from_profile(
    host: str,
    miner_name: str,
    password: str = "admin",
    profiles_dir: Optional[Path | str] = None,
    timeout: float = 10.0,
    restart_after: bool = True,
) -> Tuple[bool, str]:
    """Inject saved golden profile into target miner via VNish REST API.
    
    Restores:
    - Binance mining pools and worker configuration
    - Overclock preset and top_preset ceiling
    - Dynamic fan cooling targets and minimum duties
    - 378 individual chip tuning frequency/voltage offsets
    
    Args:
        host: Target miner IP address.
        miner_name: Canonical name or identifier (e.g. '24', 'S19JPRO-24').
        password: Admin password for VNish API (default 'admin').
        profiles_dir: Custom directory for profile files.
        timeout: Socket timeout for API operations.
        restart_after: If True, restarts mining process after applying settings.
        
    Returns:
        Tuple[bool, str]: (Success status, descriptive message)
    """
    profile_path = find_profile_path(miner_name, profiles_dir)
    if not profile_path or not profile_path.is_file():
        msg = f"ERROR_PROFILE_NOT_FOUND: No se encontró perfil de configuración para '{miner_name}' en {DEFAULT_PROFILES_DIR}"
        _LOGGER.error("[MINER_PROVISIONER] %s", msg)
        return False, msg

    try:
        with open(profile_path, "r", encoding="utf-8") as f:
            profile_data = json.load(f)
    except Exception as exc:
        msg = f"ERROR_PROFILE_CORRUPT: Fallo al leer {profile_path.name}: {exc}"
        _LOGGER.error("[MINER_PROVISIONER] %s", msg)
        return False, msg

    miner_block = profile_data.get("miner", {})
    if not miner_block:
        msg = f"ERROR_INVALID_PROFILE: El archivo {profile_path.name} no contiene el bloque 'miner'"
        _LOGGER.error("[MINER_PROVISIONER] %s", msg)
        return False, msg

    # Authenticate with VNish API
    ok, token, err = unlock_miner(host, password, timeout=min(5.0, timeout))
    if not ok or not token:
        msg = f"ERROR_UNLOCK_FAILED: No se pudo autenticar en {host}: {err}"
        _LOGGER.error("[MINER_PROVISIONER] %s", msg)
        return False, msg

    try:
        url = f"http://{host}/api/v1/settings"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        payload = {"miner": miner_block}

        _LOGGER.info("[MINER_PROVISIONER] Inyectando perfil '%s' en %s...", profile_path.name, host)
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
        if resp.status_code != 200:
            msg = f"ERROR_HTTP_{resp.status_code}: Error inyectando configuración en {host}: {resp.text[:200]}"
            _LOGGER.error("[MINER_PROVISIONER] %s", msg)
            return False, msg

        _LOGGER.info("[MINER_PROVISIONER] Perfil '%s' aplicado exitosamente en %s", profile_path.name, host)

        if restart_after:
            r_ok, r_err = restart_mining(host, token, timeout=min(5.0, timeout))
            if not r_ok:
                _LOGGER.warning("[MINER_PROVISIONER] Configuración aplicada pero reinicio de minería falló en %s: %s", host, r_err)

        msg = f"PROVISION_SUCCESS: Perfil '{profile_path.name}' restaurado con éxito en {host}"
        return True, msg

    except requests.exceptions.Timeout:
        msg = f"TIMEOUT: Tiempo de espera agotado al conectar con {host} para aprovisionamiento"
        _LOGGER.error("[MINER_PROVISIONER] %s", msg)
        return False, msg
    except Exception as exc:
        msg = f"ERROR_UNEXPECTED: {type(exc).__name__}: {exc}"
        _LOGGER.exception("[MINER_PROVISIONER] %s", msg)
        return False, msg
    finally:
        lock_miner(host, token, timeout=2.0)
