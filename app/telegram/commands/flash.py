"""Telegram Command Handler: /flash_vnish (Spec 076).

Provides remote, autonomous re-flashing of VNish 1.2.6 firmware onto BeagleBone Black
NAND when a miner reverts to stock Bitmain factory firmware.
Features 2-step safety verification (via inline keyboard or text CONFIRM), dedicated
background worker execution, and real-time step-by-step progress notifications.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
import urllib.request
import json

from app.governance.adaptive_contingency import normalize_miner_name
from app.governance.miner_provisioner import provision_miner_from_profile
from app.network.firmware_flasher import DEFAULT_PACKAGE_PATH, flash_bitmain_nand, is_stock_bitmain
from app.telegram.callbacks import build_callback_data
from app.telegram.commands.base import BaseCommandHandler
from app.telegram.context import TelegramRequestContext

logger = logging.getLogger("miner-alerts")

# Track running flash jobs to prevent concurrent flashes on the same miner
_RUNNING_FLASH_JOBS: Dict[str, threading.Thread] = {}
_FLASH_JOBS_LOCK = threading.Lock()


def is_flash_in_progress(miner_name: str) -> bool:
    norm = normalize_miner_name(miner_name)
    with _FLASH_JOBS_LOCK:
        th = _RUNNING_FLASH_JOBS.get(norm)
        return th is not None and th.is_alive()


def run_flash_and_provision_pipeline(
    host: str,
    miner_name: str,
    context: TelegramRequestContext,
    package_path: Optional[str] = None,
    vnish_pw: str = "admin",
) -> None:
    """Background worker pipeline executing probe, flash, boot-wait, and provisioning."""
    if vnish_pw == "admin" and context and context.config:
        vnish_pw = str(context.config.get("vnish_api_password", "admin"))
    norm = normalize_miner_name(miner_name)

    def _notify(text: str, msg_type: str = "INFO") -> None:
        try:
            context.send_message(text, msg_type=msg_type)
        except Exception as exc:
            logger.error("[FLASH_PIPELINE] Error enviando notificación: %s", exc)

    try:
        # Step 1: Probe Bitmain stock status
        _notify(
            f"🛠️ *[1/4] Flasheo VNish ({norm})*\n"
            f"Verificando estado Bitmain de fábrica en `{host}`...",
            msg_type="STATUS",
        )
        if not is_stock_bitmain(host):
            _notify(
                f"⚠️ *[ABORTADO] Flasheo VNish ({norm})*\n"
                f"El minero en `{host}` no responde como firmware de fábrica de Bitmain.\n"
                "Para evitar sobreescribir un minero activo, el flasheo fue abortado.",
                msg_type="WARNING",
            )
            return

        # Step 2: Upload firmware tarball to /cgi-bin/upgrade.cgi
        _notify(
            f"📦 *[2/4] Flasheo VNish ({norm})*\n"
            f"Subiendo tarball instalador a `{host}:80/cgi-bin/upgrade.cgi` (56 MB)...",
            msg_type="STATUS",
        )
        flash_ok, flash_msg = flash_bitmain_nand(host, package_path=package_path)
        if not flash_ok:
            _notify(
                f"❌ *[FALLO] Flasheo VNish ({norm})*\n"
                f"Error durante la carga del firmware en `{host}`:\n`{flash_msg}`",
                msg_type="ERROR",
            )
            return

        # Step 3: Wait for VNish to boot into NAND
        _notify(
            f"⏳ *[3/4] Flasheo VNish ({norm})*\n"
            f"Firmware recibido por el ASIC. Esperando reinicio de BeagleBone Black en VNish 1.2.6 (aprox 60-90s)...",
            msg_type="STATUS",
        )
        deadline = time.time() + 150.0
        booted = False
        while time.time() < deadline:
            time.sleep(10.0)
            try:
                # Probe VNish API endpoint
                url = f"http://{host}/api/v1/info"
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=3.0) as resp:
                    if resp.status == 200:
                        booted = True
                        break
            except Exception:
                continue

        if not booted:
            _notify(
                f"⚠️ *[TIEMPO AGOTADO] Flasheo VNish ({norm})*\n"
                f"El minero en `{host}` no respondió a la API de VNish tras 150s.\n"
                "Verifique si la placa sigue reiniciando o requiere intervención física.",
                msg_type="WARNING",
            )
            return

        # Step 4: Auto-provisioning from golden profile
        _notify(
            f"⚙️ *[4/4] Flasheo VNish ({norm})*\n"
            f"VNish 1.2.6 en línea. Inyectando pools de Binance, preset nominal 2300W y matriz de 378 chips afinados...",
            msg_type="STATUS",
        )
        prov_ok, prov_msg = provision_miner_from_profile(host, norm, password=vnish_pw, restart_after=True)
        if not prov_ok:
            _notify(
                f"⚠️ *[APROVISIONAMIENTO PARCIAL] Flasheo VNish ({norm})*\n"
                f"Firmware flasheado pero falló la restauración automática:\n`{prov_msg}`\n"
                f"Ejecute `/status {norm}` o revise los pools manualmente.",
                msg_type="WARNING",
            )
            return

        # Success!
        _notify(
            f"✅ *[FLASHEO & APROVISIONAMIENTO EXITOSO] ({norm})*\n"
            f"El minero `{norm}` ({host}) ha sido recuperado a VNish 1.2.6 NAND con sus pools y chips afinados restaurados.\n"
            f"Minando activamente a plena potencia.",
            msg_type="SUCCESS",
        )

    except Exception as exc:
        logger.exception("[FLASH_PIPELINE] Excepción no controlada en pipeline de %s: %s", norm, exc)
        _notify(
            f"❌ *[ERROR CRÍTICO] Flasheo VNish ({norm})*\n`{type(exc).__name__}: {exc}`",
            msg_type="ERROR",
        )
    finally:
        with _FLASH_JOBS_LOCK:
            _RUNNING_FLASH_JOBS.pop(norm, None)


class FlashVnishCommand(BaseCommandHandler):
    name = "flash_vnish"
    aliases = ["flash", "flashear", "instalar_firmware"]
    description = "Reinstalación remota autónoma de firmware VNish 1.2.6 en NAND y aprovisionamiento post-booteo."

    def handle(
        self,
        context: TelegramRequestContext,
        args: List[str],
        update_id: Optional[int] = None,
        from_id: Optional[Any] = None,
        message_id: Optional[int] = None,
        cmd_name: str = "",
    ) -> bool:
        from app.miner_monitor import resolve_miner, display_name

        if not args:
            lines = [
                "╔══════════════════════════════════════════╗",
                "║       FLASHEO REMOTO VNISH 1.2.6 NAND    ║",
                "╚══════════════════════════════════════════╝",
                "",
                "Reinstala VNish 1.2.6 sobre un minero que cayó al firmware de fábrica Bitmain.",
                "Uso:",
                "  `/flash_vnish <nombre_o_ip>`",
                "  `/flash_vnish <nombre_o_ip> CONFIRM`",
                "",
                "Ejemplos:",
                "  `/flash_vnish 24`",
                "  `/flash_vnish 192.168.100.24 CONFIRM`",
            ]
            context.send_message("\n".join(lines), msg_type="INFO", dedup_key="cmd_flash_help")
            return True

        target_token = args[0].strip()
        miner = resolve_miner(target_token, context.miners)
        if not miner:
            context.send_message(
                f"⚠️ Minero '{target_token}' no encontrado en la configuración.\n"
                f"Uso: `/flash_vnish <nombre_o_ip>`",
                msg_type="WARNING",
                dedup_key="cmd_flash_not_found",
            )
            return True

        miner_raw_name = miner.get("name", "")
        name = display_name(miner_raw_name)
        host = miner.get("host", "")
        norm = normalize_miner_name(miner_raw_name)

        if is_flash_in_progress(norm):
            context.send_message(
                f"⏳ Ya existe un flasheo en progreso para *{name}* (`{host}`).\n"
                "Por favor espere a que finalice el proceso actual.",
                msg_type="WARNING",
                dedup_key=f"cmd_flash_running_{norm}",
            )
            return True

        # Check for 2-step confirmation
        is_confirmed = len(args) > 1 and args[1].strip().upper() == "CONFIRM"

        if not is_confirmed:
            # Generate inline confirmation
            token = context.token_registry.create_token(norm, "flash") if context.token_registry else "direct"
            confirm_data = build_callback_data("flash_cfm", norm, token=token)
            cancel_data = build_callback_data("flash_ccl", norm)

            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": f"⚠️ Confirmar Flasheo en {name}", "callback_data": confirm_data},
                    ],
                    [
                        {"text": "❌ Cancelar", "callback_data": cancel_data},
                    ],
                ]
            }

            msg_text = (
                f"⚠️ *CONFIRMACIÓN DE FLASHEO DE FIRMWARE*\n\n"
                f"Está a punto de reinstalar VNish 1.2.6 en la NAND de:\n"
                f"• Minero: *{name}*\n"
                f"• IP: `{host}`\n"
                f"• Archivo: `{DEFAULT_PACKAGE_PATH}`\n\n"
                f"Esta operación dura ~2-3 minutos y reiniciará la control board.\n"
                f"Presione el botón inferior o escriba:\n"
                f"`/flash_vnish {target_token} CONFIRM`"
            )
            context.send_message(
                msg_text,
                msg_type="WARNING",
                reply_markup=keyboard,
                dedup_key=f"cmd_flash_confirm_{norm}",
            )
            return True

        # Confirmed: Launch background worker
        vnish_pw = str(context.config.get("vnish_api_password", "admin"))
        th = threading.Thread(
            target=run_flash_and_provision_pipeline,
            args=(host, norm, context),
            kwargs={"vnish_pw": vnish_pw},
            name=f"FlashWorker_{norm}",
            daemon=True,
        )
        with _FLASH_JOBS_LOCK:
            _RUNNING_FLASH_JOBS[norm] = th
        th.start()

        context.send_message(
            f"🚀 *Flasheo iniciado en segundo plano para {name}* (`{host}`).\n"
            "Recibirá reportes de avance por fases en este chat.",
            msg_type="INFO",
            dedup_key=f"cmd_flash_dispatched_{norm}",
        )
        return True
