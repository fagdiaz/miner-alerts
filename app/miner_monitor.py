import json
import os
import socket
import sys
import threading
import time
import ctypes
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

import requests

STATE_OK = "OK"
STATE_LOW = "LOW"
STATE_OFFLINE = "OFFLINE"
STATE_HASHBOARD = "HASHBOARD"

_MUTEX_HANDLE: Optional[int] = None


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


def _read_command(host: str, port: int, payload: bytes, timeout: float = 5.0) -> Optional[dict]:
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
        return json.loads(raw.decode("utf-8", errors="ignore"))
    except Exception as exc:
        log(f"[WARN] Error parseando respuesta de {host}:{port} ({exc})")
        return None


def read_summary(host: str, port: int, timeout: float = 5.0) -> Tuple[Optional[float], Optional[int], bool]:
    payload = b'{"command":"summary"}\n'
    resp = _read_command(host, port, payload, timeout=timeout)
    if not resp:
        return None, None, False
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


def _count_active_boards(stats_entry: dict) -> Optional[int]:
    if "chain_acn" in stats_entry and isinstance(stats_entry["chain_acn"], list):
        return sum(1 for v in stats_entry["chain_acn"] if isinstance(v, (int, float)) and v > 0)

    count = 0
    found = False
    for i in range(0, 10):
        key_num = f"chain{i}_asicnum"
        key_alive = f"chain{i}_alive"
        key_status = f"chain{i}_status"
        if key_num in stats_entry:
            found = True
            try:
                if int(stats_entry.get(key_num, 0)) > 0:
                    count += 1
            except (TypeError, ValueError):
                pass
            continue
        if key_alive in stats_entry:
            found = True
            try:
                if int(stats_entry.get(key_alive, 0)) > 0:
                    count += 1
            except (TypeError, ValueError):
                pass
            continue
        if key_status in stats_entry:
            found = True
            if str(stats_entry.get(key_status, "")).lower() in ("alive", "o", "ok"):
                count += 1

    return count if found else None


def read_stats_active_boards(host: str, port: int, timeout: float = 5.0) -> Tuple[Optional[int], bool]:
    payload = b'{"command":"stats"}\n'
    resp = _read_command(host, port, payload, timeout=timeout)
    if not resp:
        return None, False
    stats = resp.get("STATS")
    if not stats:
        return None, True
    entry = stats[0] if isinstance(stats, list) and stats else stats
    if not isinstance(entry, dict):
        return None, True
    return _count_active_boards(entry), True


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


def _mutex_name() -> str:
    return r"Global\MinerAlertsMonitor_fagdiaz"


def acquire_mutex_or_exit(mutex_name: str) -> int:
    global _MUTEX_HANDLE
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.CreateMutexW(None, True, mutex_name)
    if not handle:
        log("ERROR: No se pudo crear el mutex.")
        sys.exit(1)
    last_error = ctypes.get_last_error()
    log(f"PID={os.getpid()} PPID={os.getppid()} mutex={mutex_name} last_error={last_error}")
    if last_error == 183:
        log("Ya hay otra instancia del monitor corriendo (mutex). Saliendo.")
        kernel32.CloseHandle(handle)
        sys.exit(0)
    _MUTEX_HANDLE = handle
    return last_error


def release_mutex() -> None:
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


def load_state(state_path: Path) -> Tuple[Dict[str, MinerState], Optional[int]]:
    if not state_path.exists():
        return {}, None
    try:
        raw = json.loads(state_path.read_text(encoding="utf-8"))
        saved_at = raw.get("saved_at")
        if saved_at:
            saved_dt = datetime.strptime(saved_at, "%Y-%m-%d %H:%M:%S")
            if (datetime.now() - saved_dt).total_seconds() > 48 * 3600:
                log("[WARN] state.json esta stale (>48h). Se ignora.")
                return {}, None
        states = {}
        raw_states = raw.get("states", {})
        for key, data in raw_states.items():
            state = MinerState(
                low_streak=int(data.get("low_streak", 0)),
                offline_streak=int(data.get("offline_streak", 0)),
                ok_streak=int(data.get("ok_streak", 0)),
                state=str(data.get("state", STATE_OK)),
                initialized=bool(data.get("initialized", False)),
                last_elapsed=data.get("last_elapsed"),
                last_seen_ts=float(data.get("last_seen_ts", 0.0)),
                reboot_pending_until=float(data.get("reboot_pending_until", 0.0)),
                reboot_pending_reason=str(data.get("reboot_pending_reason", "")),
                reboot_pending_elapsed=data.get("reboot_pending_elapsed"),
                last_reboot_ts=float(data.get("last_reboot_ts", 0.0)),
            )
            states[key] = state
        last_update_id = raw.get("last_update_id")
        return states, int(last_update_id) if last_update_id is not None else None
    except Exception:
        log("[WARN] state.json corrupto. Se ignora.")
        return {}, None


def save_state(state_path: Path, states: Dict[str, MinerState], last_update_id: Optional[int]) -> None:
    payload = {
        "saved_at": now_str(),
        "last_update_id": last_update_id,
        "states": {},
    }
    for key, state in states.items():
        payload["states"][key] = {
            "state": state.state,
            "low_streak": state.low_streak,
            "offline_streak": state.offline_streak,
            "ok_streak": state.ok_streak,
            "initialized": state.initialized,
            "last_elapsed": state.last_elapsed,
            "last_seen_ts": state.last_seen_ts,
            "reboot_pending_until": state.reboot_pending_until,
            "reboot_pending_reason": state.reboot_pending_reason,
            "reboot_pending_elapsed": state.reboot_pending_elapsed,
            "last_reboot_ts": state.last_reboot_ts,
        }
    tmp_path = state_path.with_suffix(".tmp")
    try:
        tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp_path, state_path)
    except Exception:
        log("[WARN] No se pudo guardar state.json.")


def telegram_polling_worker(
    bot_token: str,
    chat_id: str,
    state_path: Path,
    states: Dict[str, MinerState],
    last_update_id_ref: Dict[str, Optional[int]],
    last_update_lock: threading.Lock,
    snapshot_ref: Dict[str, Optional[str]],
    snapshot_lock: threading.Lock,
    state_lock: threading.Lock,
) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    while True:
        offset = None
        with last_update_lock:
            if last_update_id_ref["value"] is not None:
                offset = last_update_id_ref["value"] + 1
        try:
            params = {"timeout": 25}
            if offset is not None:
                params["offset"] = offset
            resp = requests.get(url, params=params, timeout=30)
            data = resp.json()
            if not data.get("ok"):
                time.sleep(5)
                continue

            for item in data.get("result", []):
                update_id = item.get("update_id")
                if update_id is None:
                    continue
                with last_update_lock:
                    last_update_id_ref["value"] = update_id
                    current_last_update_id = last_update_id_ref["value"]
                with state_lock:
                    save_state(state_path, states, current_last_update_id)

                message = item.get("message", {})
                text = str(message.get("text", "")).strip().lower()
                msg_chat_id = message.get("chat", {}).get("id")
                if msg_chat_id is None or str(msg_chat_id) != str(chat_id):
                    continue
                if text == "status":
                    with snapshot_lock:
                        snapshot = snapshot_ref["value"]
                    if snapshot:
                        send_telegram(bot_token, str(msg_chat_id), snapshot)
                    else:
                        send_telegram(
                            bot_token,
                            str(msg_chat_id),
                            "Aun no hay lecturas, espere unos segundos y reintente.",
                        )
        except Exception:
            log("[WARN] No se pudo consultar getUpdates.")
            time.sleep(5)


def main() -> None:
    mutex_name = _mutex_name()
    acquire_mutex_or_exit(mutex_name)
    log(f"script={Path(__file__).resolve()}")

    config = load_config()
    miners = config.get("miners", [])
    threshold_ths = float(config.get("threshold_ths", 60.0))
    poll_seconds = int(config.get("poll_seconds", 30))
    fails_before_alert = int(config.get("fails_before_alert", 3))
    recovery_successes = int(config.get("recovery_successes", 2))
    expected_boards = int(config.get("expected_boards", 3))
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
        release_mutex()
        sys.exit(1)

    state_path = Path(__file__).resolve().parent / "state.json"
    states, last_update_id = load_state(state_path)
    last_update_id_ref = {"value": last_update_id}
    last_update_lock = threading.Lock()
    snapshot_ref: Dict[str, Optional[str]] = {"value": None}
    snapshot_lock = threading.Lock()
    state_lock = threading.Lock()

    telegram_thread = threading.Thread(
        target=telegram_polling_worker,
        args=(
            bot_token,
            str(chat_id),
            state_path,
            states,
            last_update_id_ref,
            last_update_lock,
            snapshot_ref,
            snapshot_lock,
            state_lock,
        ),
        daemon=True,
    )
    telegram_thread.start()

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
                active_boards = None
                if responded:
                    active_boards, _ = read_stats_active_boards(host, port)
                # Logs operativos solo cuando hay cambios o warnings.

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
                elif responded and active_boards is not None and active_boards < expected_boards:
                    new_state = STATE_HASHBOARD
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
                        if new_state == STATE_HASHBOARD:
                            state_message_needed = True
                        elif new_state == STATE_LOW:
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
                    elif new_state == STATE_HASHBOARD:
                        log(
                            f"[STATE] {name} ({host}:{port}) -> HASHBOARD "
                            f"boards={active_boards}/{expected_boards} ({now_str()})"
                        )
                        state_message_needed = True
                    elif new_state == STATE_LOW:
                        log(
                            f"[STATE] {name} ({host}:{port}) OK/OFFLINE -> LOW "
                            f"{format_rate(rate_ths)} < {threshold_ths:.2f} TH/s "
                            f"({now_str()})"
                        )
                        state_message_needed = True
                    elif new_state == STATE_OK and prev_state in (STATE_LOW, STATE_OFFLINE, STATE_HASHBOARD):
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
                if new_state == STATE_HASHBOARD:
                    label = " [HASHBOARD]"
                elif new_state == STATE_LOW:
                    label = " [LOW]"
                elif new_state == STATE_OFFLINE:
                    label = " [OFFLINE]"
                miner_lines.append(
                    f"- {name} ({host}:{port}): {format_rate(rate_ths)}{label}"
                )

            status_lines = [
                f"STATUS ({now_str()})",
                f"Threshold: {threshold_ths:.2f} TH/s",
            ]
            status_lines.extend(miner_lines)
            with snapshot_lock:
                snapshot_ref["value"] = "\n".join(status_lines)

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

            with last_update_lock:
                current_last_update_id = last_update_id_ref["value"]
            with state_lock:
                save_state(state_path, states, current_last_update_id)
            first_tick = False
            time.sleep(poll_seconds)
    except KeyboardInterrupt:
        log("Detenido por usuario")
    finally:
        release_mutex()


if __name__ == "__main__":
    main()
