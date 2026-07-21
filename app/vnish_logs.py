from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional


ALLOWED_LOG_TABS = frozenset(("status", "miner", "autotune", "system"))

_LINE_RE = re.compile(
    r"^\[(?P<timestamp>[^\]]{1,32})\]\s+"
    r"(?P<level>ERROR|WARN(?:ING)?|INFO|DEBUG):\s*(?P<message>.*)$",
    re.IGNORECASE,
)
_CHAIN_RE = re.compile(r"\bchain\s*\[?(\d+)\]?", re.IGNORECASE)


@dataclass(frozen=True)
class VnishLogEvent:
    collected_ts: float
    source_ts_text: str
    source_tab: str
    source_fingerprint: str
    category: str
    severity: str
    code: str
    summary: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "collected_ts": self.collected_ts,
            "source_ts_text": self.source_ts_text,
            "source_tab": self.source_tab,
            "source_fingerprint": self.source_fingerprint,
            "category": self.category,
            "severity": self.severity,
            "code": self.code,
            "summary": self.summary,
        }


def _chain_suffix(message: str) -> str:
    match = _CHAIN_RE.search(message)
    return f" (cadena {match.group(1)})" if match else ""


def _classified(message: str) -> Optional[tuple[str, str, str, str]]:
    lowered = message.lower()
    chain = _chain_suffix(message)

    if "autotune fail" in lowered or "auto-tuning fail" in lowered:
        return "transition", "warning", "firmware_autotune_failed", f"Autotune fallo{chain}"
    if "initializing" in lowered:
        return "transition", "info", "firmware_initializing", "Firmware inicializando"
    if "auto-tuning" in lowered or "autotune" in lowered or "begin tuning" in lowered:
        return "transition", "info", "firmware_autotune", f"Autotune en progreso{chain}"
    if "cooling down" in lowered:
        return "transition", "info", "firmware_cooling", "Firmware en enfriamiento controlado"
    if "start mining" in lowered or "mining started" in lowered:
        return "transition", "info", "firmware_mining_started", "Firmware inicio minado"

    if "restarting" in lowered and "chain break" in lowered:
        return "restart", "warning", "watchdog_chain_restart", f"Reinicio interno por corte de cadena{chain}"
    if "watchdog" in lowered and ("restart" in lowered or "reboot" in lowered):
        return "restart", "warning", "watchdog_restart", "Watchdog reinicio el proceso de minado"
    if "restart bmminer" in lowered or "bmminer not running" in lowered:
        return "restart", "warning", "miner_process_restart", "Firmware reinicio el proceso de minado"
    if "fatal error" in lowered and "reboot" in lowered:
        return "restart", "critical", "firmware_fatal_reboot", "Firmware reinicio por error fatal"
    if "mining stopped" in lowered:
        return "restart", "warning", "miner_stopped", "Proceso de minado detenido"

    if "domain voltage abnormal" in lowered or "domain voltage unstable" in lowered:
        return "chain", "critical", "chain_voltage_abnormal", f"Voltaje interno de cadena anormal{chain}"
    if "chain break" in lowered:
        return "chain", "critical", "chain_break", f"Corte de cadena detectado{chain}"
    if "crc error" in lowered:
        return "chain", "warning", "chain_crc_error", f"Errores CRC en cadena{chain}"
    if "find 0 asic" in lowered or "find asic 0" in lowered:
        return "chain", "critical", "chain_zero_asics", f"Cadena sin ASIC detectados{chain}"
    if "only find" in lowered and "asic" in lowered:
        return "chain", "critical", "chain_partial_asics", f"Cadena con ASIC incompletos{chain}"
    if "hashboard missing" in lowered or ("chain" in lowered and "is missing" in lowered):
        return "chain", "critical", "chain_missing", f"Hashboard/cadena ausente{chain}"

    if "power lost" in lowered:
        return "power", "critical", "power_loss", "Firmware detecto perdida de alimentacion"
    if "psu error" in lowered:
        return "power", "critical", "psu_error", "Firmware reporto error de PSU"
    if "power low" in lowered or "voltage too low" in lowered:
        return "power", "critical", "power_voltage_low", "Firmware reporto alimentacion baja"
    if "voltage too high" in lowered:
        return "power", "critical", "power_voltage_high", "Firmware reporto alimentacion alta"
    if "power limit reached" in lowered or "limited power mode" in lowered:
        return "power", "warning", "power_limited", "Firmware limito potencia"

    if "temp too high" in lowered or "overheat" in lowered or "critical temp" in lowered:
        return "thermal", "critical", "thermal_protection", "Proteccion termica activada"
    if "fan lost" in lowered or "some fan lost" in lowered:
        return "fan", "critical", "fan_lost", "Firmware detecto perdida de ventilador"

    if "pools not specif" in lowered or "failed to parse pools" in lowered or "need to specify at least one pool" in lowered:
        return "pool_network", "critical", "pool_configuration_invalid", "Configuracion de pools invalida o ausente"
    if "authentication failed" in lowered and "stratum" in lowered:
        return "pool_network", "critical", "pool_authentication_failed", "Autenticacion con pool fallida"
    if "no active pool" in lowered or "pool 0 slow" in lowered or "pool failed" in lowered:
        return "pool_network", "warning", "pool_unavailable", "Pool no disponible"
    if "dns resolve failed" in lowered:
        return "pool_network", "warning", "dns_failure", "Resolucion DNS fallida"
    if "socket connect failed" in lowered or "stratum connection interrupted" in lowered:
        return "pool_network", "warning", "pool_connection_failure", "Conexion con pool interrumpida"

    return None


def parse_vnish_log_text(
    text: Any,
    *,
    source_tab: str,
    collected_ts: float,
    max_lines: int = 5_000,
    max_events: int = 1_000,
) -> list[VnishLogEvent]:
    """Parse recognized evidence without retaining source lines or arbitrary payloads."""
    if not isinstance(text, str) or source_tab not in ALLOWED_LOG_TABS:
        return []
    safe_lines = max(1, min(int(max_lines), 20_000))
    safe_events = max(1, min(int(max_events), 5_000))
    events: list[VnishLogEvent] = []
    for index, raw_line in enumerate(text.splitlines()):
        if index >= safe_lines or len(events) >= safe_events:
            break
        line = raw_line.strip()
        if not line or len(line) > 4_096:
            continue
        match = _LINE_RE.match(line)
        if not match:
            continue
        classified = _classified(match.group("message"))
        if classified is None:
            continue
        category, severity, code, summary = classified
        fingerprint = hashlib.sha256(
            f"{source_tab}\0{line}".encode("utf-8", errors="replace")
        ).hexdigest()
        events.append(
            VnishLogEvent(
                collected_ts=float(collected_ts),
                source_ts_text=match.group("timestamp")[:32],
                source_tab=source_tab,
                source_fingerprint=fingerprint,
                category=category,
                severity=severity,
                code=code,
                summary=summary[:160],
            )
        )
    return events


def render_firmware_events(
    rows: Iterable[Mapping[str, Any]],
    *,
    title: str = "FIRMWARE EVENTS",
    limit: int = 10,
) -> str:
    safe_limit = max(1, min(int(limit), 20))
    lines = [title]
    rendered = 0
    for row in rows:
        if rendered >= safe_limit:
            break
        timestamp = str(row.get("source_ts_text") or "sin-fecha")[:32]
        miner = str(row.get("miner_name") or row.get("miner_key") or "N/A")[:40]
        severity = str(row.get("severity") or "info").upper()[:10]
        code = str(row.get("code") or "firmware_event")[:48]
        summary = str(row.get("summary") or "Evento Vnish")[:160]
        lines.append(f"{timestamp} | {miner} {severity} {code}")
        lines.append(summary)
        rendered += 1
    if rendered == 0:
        lines.append("Sin evidencia Vnish normalizada. Ejecute el colector read-only.")
    return "\n".join(lines)
