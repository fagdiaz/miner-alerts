import json
import socket
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

import requests

STATE_OK = "OK"
STATE_LOW = "LOW"
STATE_OFFLINE = "OFFLINE"


def log(msg: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}")


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


def load_config() -> dict:
    config_path = Path(__file__).resolve().parent / "config.json"
    if not config_path.exists():
        log("ERROR: No se encontro app/config.json. Copie app/config.example.json a app/config.json y complete los valores.")
        sys.exit(1)
    try:
        with config_path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        log(f"ERROR: Config invalido ({exc}). Corrija app/config.json.")
        sys.exit(1)
    except Exception as exc:
        log(f"ERROR: No se pudo leer app/config.json ({exc}).")
        sys.exit(1)


def read_summary(host: str, port: int, timeout: float = 5.0) -> Tuple[Optional[float], Optional[int], bool]:
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
        return None, None, False

    raw = b"".join(chunks).replace(b"\x00", b"")
    if not raw:
        return None, None, False

    try:
        resp = json.loads(raw.decode("utf-8", errors="ignore"))
        summary = resp.get("SUMMARY")
        if not summary:
            return None, None, False
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
        return rate_ths, elapsed, True
    except Exception as exc:
        log(f"[WARN] Error parseando respuesta de {host}:{port} ({exc})")
        return None, None, False


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


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def main() -> None:
    config = load_config()
    miners = config.get("miners", [])
    threshold_ths = float(config.get("threshold_ths", 60.0))
    poll_seconds = int(config.get("poll_seconds", 30))
    fails_before_alert = int(config.get("fails_before_alert", 3))
    recovery_successes = int(config.get("recovery_successes", 2))
    notify_startup = bool(config.get("notify_startup", True))
    notify_offline = bool(config.get("notify_offline", True))
    notify_reboot = bool(config.get("notify_reboot", True))
    notify_initial_non_ok = bool(config.get("notify_initial_non_ok", False))
    reboot_cooldown_seconds = int(config.get("reboot_cooldown_seconds", 1800))
    reboot_window_seconds = int(config.get("reboot_window_seconds", 300))
    offline_is_actionable = bool(config.get("offline_is_actionable", True))

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

    log("Inicio de monitoreo.")

    try:
        first_tick = True
        while True:
            now_ts = time.time()
            state_message_needed = False
            reboot_names_tick = []
            miner_lines = []
            for miner in valid_miners:
                name = miner["name"]
                host = miner["host"]
                port = miner["port"]
                state_key = f"{name}|{host}:{port}"
                state = states.setdefault(state_key, MinerState())

                rate_ths, elapsed, responded = read_summary(host, port)
                log(f"[INFO] {name} ({host}:{port}) => {format_rate(rate_ths)}")

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
                elif responded and rate_ths is not None and rate_ths < threshold_ths and state.low_streak >= fails_before_alert:
                    new_state = STATE_LOW
                elif responded and rate_ths is not None and rate_ths >= threshold_ths and state.ok_streak >= recovery_successes:
                    new_state = STATE_OK

                state.state = new_state

                if new_state == STATE_OK:
                    state.low_streak = 0
                    state.offline_streak = 0

                if not state.initialized:
                    state.initialized = True
                    if first_tick and (not notify_startup) and notify_initial_non_ok:
                        if new_state == STATE_LOW:
                            state_message_needed = True
                        elif new_state == STATE_OFFLINE and notify_offline and offline_is_actionable:
                            state_message_needed = True

                if reboot_reason and notify_reboot:
                    if (now_ts - state.last_reboot_ts) >= reboot_cooldown_seconds:
                        if new_state in (STATE_LOW, STATE_OFFLINE):
                            reboot_names_tick.append(name)
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
                    elif new_state == STATE_LOW:
                        log(
                            f"[STATE] {name} ({host}:{port}) OK/OFFLINE -> LOW "
                            f"{format_rate(rate_ths)} < {threshold_ths:.2f} TH/s "
                            f"({now_str()})"
                        )
                        state_message_needed = True
                    elif new_state == STATE_OK and prev_state in (STATE_LOW, STATE_OFFLINE):
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
                if new_state == STATE_LOW:
                    label = " [LOW]"
                elif new_state == STATE_OFFLINE:
                    label = " [OFFLINE]"
                miner_lines.append(
                    f"- {name} ({host}:{port}): {format_rate(rate_ths)}{label}"
                )

            if first_tick and notify_startup:
                message_lines = [
                    f"STARTUP ({now_str()})",
                    f"Threshold: {threshold_ths:.2f} TH/s",
                ]
                message_lines.extend(miner_lines)
                send_telegram(bot_token, str(chat_id), "\n".join(message_lines))
            elif state_message_needed:
                message_lines = [
                    f"STATE CHANGE ({now_str()})",
                    f"Threshold: {threshold_ths:.2f} TH/s",
                ]
                message_lines.extend(miner_lines)
                if reboot_names_tick:
                    message_lines.append(f"Reboots: {', '.join(reboot_names_tick)}")
                send_telegram(bot_token, str(chat_id), "\n".join(message_lines))

            first_tick = False
            time.sleep(poll_seconds)
    except KeyboardInterrupt:
        log("Detenido por usuario")


if __name__ == "__main__":
    main()
