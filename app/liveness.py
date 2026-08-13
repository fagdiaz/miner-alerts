from __future__ import annotations

import json
import math
import os
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Optional, Sequence


HEARTBEAT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class MonitorHeartbeat:
    pid: int
    process_start_ts: float
    tick_sequence: int
    last_tick_completed_ts: float
    telegram_poller_ts: Optional[float]
    telegram_sender_ts: Optional[float]
    queue_depth: int
    collector_age_seconds: Optional[float]
    schema_version: int = HEARTBEAT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MonitorHeartbeat":
        if int(payload.get("schema_version", -1)) != HEARTBEAT_SCHEMA_VERSION:
            raise ValueError("heartbeat_schema_unsupported")
        pid = _non_negative_int(payload.get("pid"), "pid")
        if pid <= 0:
            raise ValueError("heartbeat_malformed")
        return cls(
            pid=pid,
            process_start_ts=_finite_float(payload.get("process_start_ts")),
            tick_sequence=_non_negative_int(payload.get("tick_sequence"), "tick_sequence"),
            last_tick_completed_ts=_finite_float(payload.get("last_tick_completed_ts")),
            telegram_poller_ts=_optional_finite_float(payload.get("telegram_poller_ts")),
            telegram_sender_ts=_optional_finite_float(payload.get("telegram_sender_ts")),
            queue_depth=_non_negative_int(payload.get("queue_depth"), "queue_depth"),
            collector_age_seconds=_optional_non_negative_float(
                payload.get("collector_age_seconds")
            ),
        )


@dataclass(frozen=True)
class MaintenanceLease:
    expires_ts: float
    reason: str

    def active(self, now_ts: float) -> bool:
        return math.isfinite(self.expires_ts) and now_ts <= self.expires_ts


@dataclass(frozen=True)
class LivenessAssessment:
    healthy: bool
    reason_codes: tuple[str, ...]
    evidence: dict[str, Any]
    suppressed: bool = False


@dataclass(frozen=True)
class WatchdogIncidentState:
    is_open: bool = False
    reason_codes: tuple[str, ...] = ()
    opened_ts: Optional[float] = None
    last_seen_ts: Optional[float] = None
    last_notified_ts: Optional[float] = None
    notification_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["reason_codes"] = list(self.reason_codes)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "WatchdogIncidentState":
        return cls(
            is_open=bool(payload.get("is_open", False)),
            reason_codes=tuple(str(item) for item in payload.get("reason_codes", [])),
            opened_ts=_optional_finite_float(payload.get("opened_ts")),
            last_seen_ts=_optional_finite_float(payload.get("last_seen_ts")),
            last_notified_ts=_optional_finite_float(payload.get("last_notified_ts")),
            notification_count=_non_negative_int(
                payload.get("notification_count", 0), "notification_count"
            ),
        )


def write_heartbeat_atomic(path: Path, heartbeat: MonitorHeartbeat) -> None:
    _write_json_atomic(path, heartbeat.to_dict())


def load_heartbeat(path: Path) -> tuple[Optional[MonitorHeartbeat], Optional[str]]:
    if not path.exists():
        return None, "heartbeat_missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, dict):
            return None, "heartbeat_malformed"
        return MonitorHeartbeat.from_dict(payload), None
    except ValueError as exc:
        code = str(exc)
        if code == "heartbeat_schema_unsupported":
            return None, code
        return None, "heartbeat_malformed"
    except (OSError, TypeError, json.JSONDecodeError):
        return None, "heartbeat_malformed"


def assess_liveness(
    *,
    now_ts: float,
    heartbeat: Optional[MonitorHeartbeat],
    service_state: str,
    process_alive: bool,
    heartbeat_error: Optional[str] = None,
    tick_stale_seconds: float = 120.0,
    worker_stale_seconds: float = 120.0,
    collector_stale_seconds: float = 3600.0,
    clock_skew_tolerance_seconds: float = 5.0,
    maintenance: Optional[MaintenanceLease] = None,
) -> LivenessAssessment:
    reasons: list[str] = []
    evidence: dict[str, Any] = {
        "service_state": str(service_state or "unknown").lower(),
        "process_alive": bool(process_alive),
    }
    if evidence["service_state"] != "running":
        reasons.append("service_stopped")
    if not process_alive:
        reasons.append("process_missing")
    if heartbeat is None:
        reasons.append(heartbeat_error or "heartbeat_missing")
    else:
        timestamps = (
            heartbeat.process_start_ts,
            heartbeat.last_tick_completed_ts,
            heartbeat.telegram_poller_ts,
            heartbeat.telegram_sender_ts,
        )
        if any(
            value is not None and value > now_ts + clock_skew_tolerance_seconds
            for value in timestamps
        ):
            reasons.append("clock_skew")
        tick_age = max(0.0, now_ts - heartbeat.last_tick_completed_ts)
        poller_age = _age(now_ts, heartbeat.telegram_poller_ts)
        sender_age = _age(now_ts, heartbeat.telegram_sender_ts)
        collector_age = heartbeat.collector_age_seconds
        if collector_age is not None:
            collector_age += tick_age
        evidence.update(
            {
                "heartbeat_pid": heartbeat.pid,
                "tick_sequence": heartbeat.tick_sequence,
                "tick_age_seconds": tick_age,
                "telegram_poller_age_seconds": poller_age,
                "telegram_sender_age_seconds": sender_age,
                "collector_age_seconds": collector_age,
                "queue_depth": heartbeat.queue_depth,
            }
        )
        if tick_age > tick_stale_seconds:
            reasons.append("tick_stale")
        if poller_age is None or poller_age > worker_stale_seconds:
            reasons.append("telegram_poller_stale")
        if sender_age is None or sender_age > worker_stale_seconds:
            reasons.append("telegram_sender_stale")
        if collector_age is not None and collector_age > collector_stale_seconds:
            reasons.append("collector_stale")

    unique_reasons = tuple(dict.fromkeys(reasons))
    suppressed = bool(maintenance and maintenance.active(now_ts) and unique_reasons)
    if suppressed and maintenance is not None:
        evidence["maintenance_expires_ts"] = maintenance.expires_ts
        evidence["maintenance_reason"] = maintenance.reason[:120]
    return LivenessAssessment(
        healthy=not unique_reasons,
        reason_codes=unique_reasons,
        evidence=evidence,
        suppressed=suppressed,
    )


def decide_notification(
    assessment: LivenessAssessment,
    state: WatchdogIncidentState,
    *,
    now_ts: float,
    reminder_schedule_seconds: Sequence[int] = (300, 900, 3600),
) -> tuple[str, WatchdogIncidentState]:
    if assessment.suppressed:
        return "none", state
    if assessment.healthy:
        if state.is_open:
            return "recovery", WatchdogIncidentState()
        return "none", state

    reasons = assessment.reason_codes
    if not state.is_open:
        return "open", WatchdogIncidentState(
            is_open=True,
            reason_codes=reasons,
            opened_ts=now_ts,
            last_seen_ts=now_ts,
            last_notified_ts=now_ts,
            notification_count=1,
        )
    if reasons != state.reason_codes:
        return "update", replace(
            state,
            reason_codes=reasons,
            last_seen_ts=now_ts,
            last_notified_ts=now_ts,
            notification_count=state.notification_count + 1,
        )

    schedule = tuple(max(1, int(value)) for value in reminder_schedule_seconds) or (3600,)
    index = min(max(state.notification_count - 1, 0), len(schedule) - 1)
    elapsed = now_ts - float(state.last_notified_ts or state.opened_ts or now_ts)
    updated = replace(state, last_seen_ts=now_ts)
    if elapsed >= schedule[index]:
        return "reminder", replace(
            updated,
            last_notified_ts=now_ts,
            notification_count=state.notification_count + 1,
        )
    return "none", updated


def render_liveness_assessment(
    assessment: LivenessAssessment,
    *,
    event: str,
) -> str:
    if event == "recovery":
        return "MONITOR RECUPERADO\n\nTicks y workers volvieron a estar activos."
    title = "MONITOR SIN PROGRESO" if not assessment.healthy else "MONITOR OK"
    lines = [title, "", f"Motivos: {', '.join(assessment.reason_codes) or 'ninguno'}"]
    evidence = assessment.evidence
    for key, label in (
        ("service_state", "Servicio"),
        ("tick_age_seconds", "Último tick"),
        ("telegram_poller_age_seconds", "Telegram poller"),
        ("telegram_sender_age_seconds", "Telegram sender"),
        ("collector_age_seconds", "Collector"),
        ("queue_depth", "Cola"),
    ):
        value = evidence.get(key)
        if value is None:
            continue
        suffix = "s" if key.endswith("_seconds") else ""
        rendered = int(value) if isinstance(value, (int, float)) else value
        lines.append(f"{label}: {rendered}{suffix}")
    return "\n".join(lines)


def load_incident_state(path: Path) -> WatchdogIncidentState:
    if not path.exists():
        return WatchdogIncidentState()
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(payload, dict):
            return WatchdogIncidentState.from_dict(payload)
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        pass
    return WatchdogIncidentState()


def write_incident_state(path: Path, state: WatchdogIncidentState) -> None:
    _write_json_atomic(path, state.to_dict())


def load_maintenance_lease(path: Path) -> Optional[MaintenanceLease]:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(payload, dict):
            return MaintenanceLease(
                expires_ts=_finite_float(payload.get("expires_ts")),
                reason=str(payload.get("reason") or "maintenance")[:120],
            )
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return None
    return None


def write_maintenance_lease(path: Path, lease: MaintenanceLease) -> None:
    _write_json_atomic(path, asdict(lease))


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        with temp_path.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass


def _finite_float(value: Any) -> float:
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError("heartbeat_malformed")
    return numeric


def _optional_finite_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    return _finite_float(value)


def _optional_non_negative_float(value: Any) -> Optional[float]:
    numeric = _optional_finite_float(value)
    if numeric is not None and numeric < 0:
        raise ValueError("heartbeat_malformed")
    return numeric


def _non_negative_int(value: Any, _field: str) -> int:
    numeric = int(value)
    if numeric < 0:
        raise ValueError("heartbeat_malformed")
    return numeric


def _age(now_ts: float, timestamp: Optional[float]) -> Optional[float]:
    if timestamp is None:
        return None
    return max(0.0, now_ts - timestamp)
