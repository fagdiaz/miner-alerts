import json
import socket
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import requests


def log(msg: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}")


@dataclass
class MinerState:
    low_streak: int = 0
    offline_streak: int = 0
    ok_streak: int = 0
    is_low: bool = False
    is_offline: bool = False
    last_alert_ts: float = 0.0


def load_config() -> dict:
    config_path = Path(__file__).resolve().parent / "config.json"
    if not config_path.exists():
        log("ERROR: No se encontró app/config.json. Copie app/config.example.json a app/config.json y complete los valores.")
        sys.exit(1)
    try:
        with config_path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        log(f"ERROR: Config inválido ({exc}). Corrija app/config.json.")
        sys.exit(1)
    except Exception as exc:
        log(f"ERROR: No se pudo leer app/config.json ({exc}).")
        sys.exit(1)


def read_hashrate_ths(host: str, port: int, timeout: float = 5.0) -> Optional[float]:
    payload = b'{"command":"summary"}'
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
        resp = json.loads(raw.decode("utf-8", errors="ignore"))
        summary = resp.get("SUMMARY")
        if not summary:
            return None
        first = summary[0]
        # Prioridad: GHS 5s -> GHS av -> MHS 5s -> MHS av
        candidates = [
            ("GHS 5s", 1_000),
            ("GHS av", 1_000),
            ("MHS 5s", 1_000_000),
            ("MHS av", 1_000_000),
        ]
        for key, divisor in candidates:
            if key in first:
                try:
                    return float(first[key]) / divisor
                except (TypeError, ValueError):
                    continue
        return None
    except Exception as exc:
        log(f"[WARN] Error parseando respuesta de {host}:{port} ({exc})")
        return None


def send_telegram(bot_token: str, chat_id: str, message: str) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code >= 400:
            log(f"[WARN] Telegram retorno {resp.status_code}: {resp.text}")
    except Exception as exc:
        log(f"[WARN] No se pudo enviar mensaje a Telegram ({exc})")


def format_rate(rate: Optional[float]) -> str:
    return f"{rate:.2f} TH/s" if rate is not None else "N/A"


def main() -> None:
    config = load_config()
    miners = config.get("miners", [])
    threshold_ths = float(config.get("threshold_ths", 60.0))
    poll_seconds = int(config.get("poll_seconds", 30))
    fails_before_alert = int(config.get("fails_before_alert", 3))
    recovery_successes = int(config.get("recovery_successes", 2))
    alert_cooldown_seconds = int(config.get("alert_cooldown_seconds", 900))

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
        sys.exit(1)

    states: Dict[str, MinerState] = {}

    startup_message_lines = [
        "Monitor mineros iniciado",
        f"Threshold: {threshold_ths:.2f} TH/s",
        "Miners:",
    ]
    for miner in valid_miners:
        name = miner["name"]
        host = miner["host"]
        port = miner["port"]
        startup_message_lines.append(f"- {name} ({host}:{port})")

    send_telegram(bot_token, str(chat_id), "\n".join(startup_message_lines))
    log("Inicio de monitoreo.")

    try:
        while True:
            now_ts = time.time()
            for miner in valid_miners:
                name = miner["name"]
                host = miner["host"]
                port = miner["port"]
                state_key = f"{name}|{host}:{port}"
                state = states.setdefault(state_key, MinerState())

                rate_ths = read_hashrate_ths(host, port)
                log(f"[INFO] {name} ({host}:{port}) => {format_rate(rate_ths)}")

                if rate_ths is None:
                    state.offline_streak += 1
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

                if (
                    rate_ths is None
                    and not state.is_offline
                    and state.offline_streak >= fails_before_alert
                    and (now_ts - state.last_alert_ts) >= alert_cooldown_seconds
                ):
                    msg = (
                        f"[OFFLINE] {name} ({host}) SIN RESPUESTA del API 4028 "
                        f"({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})"
                    )
                    log(msg)
                    send_telegram(bot_token, str(chat_id), msg)
                    state.is_offline = True
                    state.last_alert_ts = time.time()

                if (
                    rate_ths is not None
                    and rate_ths < threshold_ths
                    and not state.is_low
                    and state.low_streak >= fails_before_alert
                    and (now_ts - state.last_alert_ts) >= alert_cooldown_seconds
                ):
                    msg = (
                        f"[LOW HASHRATE] {name} ({host}) bajo threshold "
                        f"{format_rate(rate_ths)} < {threshold_ths:.2f} TH/s "
                        f"({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})"
                    )
                    log(msg)
                    send_telegram(bot_token, str(chat_id), msg)
                    state.is_low = True
                    state.last_alert_ts = time.time()

                if state.is_low or state.is_offline:
                    if rate_ths is not None and rate_ths >= threshold_ths and state.ok_streak >= recovery_successes:
                        msg = (
                            f"[RECOVERED] {name} ({host}) "
                            f"{format_rate(rate_ths)} >= {threshold_ths:.2f} TH/s "
                            f"({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})"
                        )
                        log(msg)
                        send_telegram(bot_token, str(chat_id), msg)
                        state.is_low = False
                        state.is_offline = False
                        state.low_streak = 0
                        state.offline_streak = 0
                        state.ok_streak = 0

            time.sleep(poll_seconds)
    except KeyboardInterrupt:
        log("Detenido por usuario")


if __name__ == "__main__":
    main()
