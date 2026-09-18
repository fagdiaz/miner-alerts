#!/usr/bin/env python3
"""
tools/backup_miner_profiles.py
==============================
Respaldo y Restauración de Perfiles de Sintonización y Configuración de Mineros ASIC.

Permite:
1. Exportar y almacenar los perfiles dorados de sintonización (/api/v1/settings,
   incluyendo matrices de chips afinados, presets y pools) en data/miner_profiles/.
2. Restaurar instantáneamente la configuración completa sobre cualquier minero
   reinstalado desde cero en NAND con Hashcore Toolkit, evitando demoras de auto-tuning.
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

import requests

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.vnish.client import unlock_miner, lock_miner

PROFILES_DIR = ROOT_DIR / "data" / "miner_profiles"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("backup_miner_profiles")


def load_config() -> dict:
    config_path = ROOT_DIR / "app" / "config.json"
    if not config_path.exists():
        config_path = ROOT_DIR / "app" / "config.example.json"
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def backup_miner_profile(host: str, miner_name: str, password: str = "admin") -> Tuple[bool, Optional[str]]:
    """Extrae /api/v1/settings del minero y lo guarda en data/miner_profiles/<name>.json."""
    ok, token, err = unlock_miner(host, password, timeout=4.0)
    if not ok:
        return False, f"Fallo al autenticar en {host}: {err}"

    try:
        url = f"http://{host}/api/v1/settings"
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(url, headers=headers, timeout=5.0)
        if resp.status_code != 200:
            return False, f"HTTP status {resp.status_code} desde {url}"

        data = resp.json()
        PROFILES_DIR.mkdir(parents=True, exist_ok=True)
        file_path = PROFILES_DIR / f"{miner_name}.json"

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        # Analizar datos del perfil
        oc = data.get("miner", {}).get("overclock", {})
        preset = oc.get("preset", "N/A")
        chains = oc.get("chains", [])
        tuned_chips = sum(len([x for x in c.get("chips", []) if x != 0]) for c in chains)
        logger.info(
            "Respaldo exitoso: %s (%s) -> %s [Preset=%s, Chips Afinadas=%d]",
            miner_name, host, file_path.name, preset, tuned_chips
        )
        return True, None
    except Exception as exc:
        return False, f"Error al respaldar {host}: {exc}"
    finally:
        lock_miner(host, token, timeout=2.0)


def restore_miner_profile(miner_name: str, target_host: str, password: str = "admin") -> Tuple[bool, Optional[str]]:
    """Inyecta un perfil guardado en data/miner_profiles/<name>.json hacia el minero destino."""
    file_path = PROFILES_DIR / f"{miner_name}.json"
    if not file_path.exists():
        return False, f"No existe el archivo de perfil: {file_path}"

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Solo enviamos el bloque 'miner' que contiene cooling, overclock, misc y pools
    miner_payload = {"miner": data.get("miner", {})}
    if not miner_payload["miner"]:
        return False, "El archivo de perfil no contiene la sección 'miner'"

    ok, token, err = unlock_miner(target_host, password, timeout=4.0)
    if not ok:
        return False, f"Fallo al autenticar en {target_host}: {err}"

    try:
        url = f"http://{target_host}/api/v1/settings"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        resp = requests.post(url, headers=headers, json=miner_payload, timeout=8.0)
        if resp.status_code == 200:
            logger.info("Restauración exitosa del perfil '%s' en %s", miner_name, target_host)
            return True, None
        return False, f"Fallo HTTP {resp.status_code}: {resp.text}"
    except Exception as exc:
        return False, f"Error al restaurar en {target_host}: {exc}"
    finally:
        lock_miner(target_host, token, timeout=2.0)


def backup_all() -> None:
    cfg = load_config()
    pw = cfg.get("vnish_api_password", "admin")
    miners = cfg.get("miners", [])
    logger.info("Iniciando respaldo de perfiles para %d mineros...", len(miners))
    successes = 0
    for m in miners:
        name = m.get("name", "")
        host = m.get("host", "")
        if not host:
            continue
        ok, err = backup_miner_profile(host, name, pw)
        if ok:
            successes += 1
        else:
            logger.warning("Fallo al respaldar %s: %s", name, err)
    logger.info("Respaldo completado: %d/%d mineros respaldados.", successes, len(miners))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "restore":
        if len(sys.argv) < 4:
            print("Uso: python tools/backup_miner_profiles.py restore <miner_name> <target_host>")
            sys.exit(1)
        m_name = sys.argv[2]
        t_host = sys.argv[3]
        cfg = load_config()
        pw = cfg.get("vnish_api_password", "admin")
        ok, err = restore_miner_profile(m_name, t_host, pw)
        if ok:
            print(f"EXITO: Perfil {m_name} restaurado en {t_host}")
        else:
            print(f"ERROR: {err}")
            sys.exit(1)
    else:
        backup_all()
