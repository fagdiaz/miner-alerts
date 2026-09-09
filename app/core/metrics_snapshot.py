"""Metrics snapshot model, validation, and atomic file production (Spec 025).

Exposes sanitized, bounded, read-only operational metrics snapshots for
consumption by Prometheus exporters and Grafana dashboards.
Invariants:
- Zero secrets, zero IP addresses or credentials in snapshots.
- Bounded cardinality: 23 global series + 20 per configured miner (max 103 for 4 miners).
- Strict finite numbers: NaN and Infinity are prohibited.
- Enums validated against explicit allowed sets.
- Atomic write via temporary file and atomic directory replacement.
- Read-only: no monitor action imports, no mutation endpoints.
"""

from __future__ import annotations

import dataclasses
import json
import math
import os
import re
import secrets
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

SNAPSHOT_SCHEMA_VERSION = 1
DEFAULT_SNAPSHOT_PATH = "diagnostics/metrics/current.json"
DEFAULT_STALE_SECONDS = 60

VALID_MINER_STATES: Set[str] = {"OK", "LOW", "OFFLINE", "HASHBOARD", "UNKNOWN"}
VALID_ACQ_QUALITIES: Set[str] = {"valid", "partial", "invalid", "timeout", "error", "late"}
VALID_COLLECTOR_STATUSES: Set[str] = {"ok", "partial", "failed", "stale"}
VALID_TELEGRAM_OUTCOMES: Set[str] = {"enqueued", "sent", "error", "dropped", "bypass", "fallback"}

# Prohibit IPs, domains, secrets in miner IDs or tags
IP_REGEX = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def _is_finite_number(val: Any) -> bool:
    if isinstance(val, (int, float)):
        return not (math.isnan(val) or math.isinf(val))
    return False


@dataclass(frozen=True)
class MonitorMetrics:
    process_start_ts: float
    tick_sequence: int
    last_tick_completed_ts: float
    telegram_poller_ts: Optional[float]
    telegram_sender_ts: Optional[float]
    queue_depth: int


@dataclass(frozen=True)
class MinerMetrics:
    miner_id: str
    sample_ts: float
    responded: bool
    rate_ths: Optional[float]
    threshold_ths: float
    state: str
    active_boards: Optional[int]
    expected_boards: int
    episode_active: bool
    episode_duration_seconds: float
    acquisition_quality: str
    acquisition_latency_seconds: Optional[float]


@dataclass(frozen=True)
class TelegramMetrics:
    enqueued_total: int
    sent_total: int
    send_error_total: int
    dropped_total: int
    bypass_total: int
    fallback_total: int


@dataclass(frozen=True)
class CollectorMetrics:
    status: str
    age_seconds: Optional[float]


@dataclass(frozen=True)
class AcquisitionMetrics:
    epoch_duration_seconds: Optional[float]


@dataclass(frozen=True)
class MetricsSnapshot:
    schema_version: int
    generated_ts: float
    monitor: MonitorMetrics
    miners: List[MinerMetrics]
    telegram: TelegramMetrics
    collector: CollectorMetrics
    acquisition: AcquisitionMetrics

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generated_ts": self.generated_ts,
            "monitor": asdict(self.monitor),
            "miners": [asdict(m) for m in self.miners],
            "telegram": asdict(self.telegram),
            "collector": asdict(self.collector),
            "acquisition": asdict(self.acquisition),
        }


def validate_snapshot_data(data: Dict[str, Any]) -> Tuple[bool, Optional[MetricsSnapshot], str]:
    """Validates raw dict against Snapshot Schema v1.

    Returns (is_valid, parsed_snapshot_or_none, reason_string).
    """
    if not isinstance(data, dict):
        return False, None, "payload_not_dict"

    if data.get("schema_version") != SNAPSHOT_SCHEMA_VERSION:
        return False, None, f"unsupported_schema_version: {data.get('schema_version')}"

    gen_ts = data.get("generated_ts")
    if not _is_finite_number(gen_ts) or gen_ts <= 0:
        return False, None, "invalid_generated_ts"

    # Monitor
    mon_raw = data.get("monitor")
    if not isinstance(mon_raw, dict):
        return False, None, "monitor_not_dict"
    for key in ("process_start_ts", "tick_sequence", "last_tick_completed_ts", "queue_depth"):
        if not _is_finite_number(mon_raw.get(key)):
            return False, None, f"monitor_invalid_{key}"

    monitor = MonitorMetrics(
        process_start_ts=float(mon_raw["process_start_ts"]),
        tick_sequence=int(mon_raw["tick_sequence"]),
        last_tick_completed_ts=float(mon_raw["last_tick_completed_ts"]),
        telegram_poller_ts=float(mon_raw["telegram_poller_ts"]) if _is_finite_number(mon_raw.get("telegram_poller_ts")) else None,
        telegram_sender_ts=float(mon_raw["telegram_sender_ts"]) if _is_finite_number(mon_raw.get("telegram_sender_ts")) else None,
        queue_depth=max(0, int(mon_raw["queue_depth"])),
    )

    # Telegram
    tg_raw = data.get("telegram")
    if not isinstance(tg_raw, dict):
        return False, None, "telegram_not_dict"
    for key in ("enqueued_total", "sent_total", "send_error_total", "dropped_total", "bypass_total", "fallback_total"):
        if not _is_finite_number(tg_raw.get(key)) or tg_raw.get(key) < 0:
            return False, None, f"telegram_invalid_{key}"

    telegram = TelegramMetrics(
        enqueued_total=int(tg_raw["enqueued_total"]),
        sent_total=int(tg_raw["sent_total"]),
        send_error_total=int(tg_raw["send_error_total"]),
        dropped_total=int(tg_raw["dropped_total"]),
        bypass_total=int(tg_raw["bypass_total"]),
        fallback_total=int(tg_raw["fallback_total"]),
    )

    # Collector
    coll_raw = data.get("collector")
    if not isinstance(coll_raw, dict):
        return False, None, "collector_not_dict"
    coll_status = coll_raw.get("status")
    if coll_status not in VALID_COLLECTOR_STATUSES:
        return False, None, f"collector_invalid_status: {coll_status}"
    coll_age = coll_raw.get("age_seconds")
    if coll_age is not None and not _is_finite_number(coll_age):
        return False, None, "collector_invalid_age"

    collector = CollectorMetrics(
        status=coll_status,
        age_seconds=float(coll_age) if coll_age is not None else None,
    )

    # Acquisition
    acq_raw = data.get("acquisition")
    if not isinstance(acq_raw, dict):
        return False, None, "acquisition_not_dict"
    epoch_dur = acq_raw.get("epoch_duration_seconds")
    if epoch_dur is not None and not _is_finite_number(epoch_dur):
        return False, None, "acquisition_invalid_epoch_duration"

    acquisition = AcquisitionMetrics(
        epoch_duration_seconds=float(epoch_dur) if epoch_dur is not None else None
    )

    # Miners
    miners_raw = data.get("miners")
    if not isinstance(miners_raw, list):
        return False, None, "miners_not_list"

    miners: List[MinerMetrics] = []
    seen_miner_ids: Set[str] = set()

    for i, m_raw in enumerate(miners_raw):
        if not isinstance(m_raw, dict):
            return False, None, f"miner_{i}_not_dict"

        mid = str(m_raw.get("miner_id", "")).strip()
        if not mid or IP_REGEX.search(mid) or mid in seen_miner_ids:
            return False, None, f"miner_{i}_invalid_id: {mid}"
        seen_miner_ids.add(mid)

        if not _is_finite_number(m_raw.get("sample_ts")):
            return False, None, f"miner_{mid}_invalid_sample_ts"

        state = m_raw.get("state")
        if state not in VALID_MINER_STATES:
            return False, None, f"miner_{mid}_invalid_state: {state}"

        quality = m_raw.get("acquisition_quality", "valid")
        if quality not in VALID_ACQ_QUALITIES:
            return False, None, f"miner_{mid}_invalid_quality: {quality}"

        rate = m_raw.get("rate_ths")
        if rate is not None and not _is_finite_number(rate):
            return False, None, f"miner_{mid}_invalid_rate"

        thresh = m_raw.get("threshold_ths")
        if not _is_finite_number(thresh):
            return False, None, f"miner_{mid}_invalid_threshold"

        active_b = m_raw.get("active_boards")
        if active_b is not None and not isinstance(active_b, int):
            return False, None, f"miner_{mid}_invalid_active_boards"

        exp_b = m_raw.get("expected_boards")
        if not isinstance(exp_b, int) or exp_b <= 0:
            return False, None, f"miner_{mid}_invalid_expected_boards"

        ep_dur = m_raw.get("episode_duration_seconds", 0.0)
        if not _is_finite_number(ep_dur):
            return False, None, f"miner_{mid}_invalid_episode_duration"

        latency = m_raw.get("acquisition_latency_seconds")
        if latency is not None and not _is_finite_number(latency):
            return False, None, f"miner_{mid}_invalid_latency"

        miners.append(
            MinerMetrics(
                miner_id=mid,
                sample_ts=float(m_raw["sample_ts"]),
                responded=bool(m_raw.get("responded", False)),
                rate_ths=float(rate) if rate is not None else None,
                threshold_ths=float(thresh),
                state=state,
                active_boards=active_b,
                expected_boards=exp_b,
                episode_active=bool(m_raw.get("episode_active", False)),
                episode_duration_seconds=float(ep_dur),
                acquisition_quality=quality,
                acquisition_latency_seconds=float(latency) if latency is not None else None,
            )
        )

    parsed = MetricsSnapshot(
        schema_version=SNAPSHOT_SCHEMA_VERSION,
        generated_ts=float(gen_ts),
        monitor=monitor,
        miners=miners,
        telegram=telegram,
        collector=collector,
        acquisition=acquisition,
    )
    return True, parsed, "ok"


def write_metrics_snapshot_atomic(path: str | Path, snapshot: MetricsSnapshot | Dict[str, Any]) -> bool:
    """Atomically writes a validated metrics snapshot to the target JSON file.

    Uses temporary file in the same directory and atomic rename/replace.
    Never leaves partial or corrupt files.
    """
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    if isinstance(snapshot, MetricsSnapshot):
        data = snapshot.to_dict()
    else:
        is_val, parsed, reason = validate_snapshot_data(snapshot)
        if not is_val or parsed is None:
            return False
        data = parsed.to_dict()

    content = json.dumps(data, indent=2, sort_keys=True)

    # Write to temp file in target's parent directory
    tmp_path = target.parent / f".current.json.tmp.{secrets.token_hex(4)}"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())

        tmp_path.replace(target)
        return True
    except Exception:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        return False


def load_metrics_snapshot(
    path: str | Path, max_age_seconds: float = DEFAULT_STALE_SECONDS
) -> Tuple[bool, Optional[MetricsSnapshot], float, str]:
    """Loads and validates a metrics snapshot from disk.

    Returns (is_fresh_and_valid, parsed_snapshot_or_none, age_seconds, reason_code).
    If file is missing, corrupt, or older than max_age_seconds, returns is_fresh_and_valid = False.
    """
    target = Path(path)
    if not target.exists():
        return False, None, -1.0, "snapshot_missing"

    try:
        content = target.read_text(encoding="utf-8")
        raw = json.loads(content)
    except Exception as exc:
        return False, None, -1.0, f"parse_error: {exc}"

    is_valid, parsed, reason = validate_snapshot_data(raw)
    if not is_valid or parsed is None:
        return False, None, -1.0, reason

    now = time.time()
    age = max(0.0, now - parsed.generated_ts)

    if age > max_age_seconds:
        return False, parsed, age, f"snapshot_stale: age {age:.1f}s > {max_age_seconds:.1f}s"

    return True, parsed, age, "ok"


def write_monitor_metrics_snapshot_safe(
    path: str | Path,
    process_start_ts: float,
    tick_sequence: int,
    completed_ts: float,
    telegram_poller_ts: Optional[float],
    telegram_sender_ts: Optional[float],
    queue_depth: int,
    telegram_counters: Dict[str, int],
    collector_age_seconds: Optional[float],
    collector_status: str,
    epoch_duration_seconds: Optional[float],
    miner_metrics_list: List[Dict[str, Any]],
) -> bool:
    """Safely constructs and atomically writes a snapshot from monitor state."""
    try:
        miners: List[MinerMetrics] = []
        for m in miner_metrics_list:
            miners.append(
                MinerMetrics(
                    miner_id=str(m.get("miner_id", "")),
                    sample_ts=float(m.get("sample_ts", completed_ts)),
                    responded=bool(m.get("responded", False)),
                    rate_ths=float(m["rate_ths"]) if m.get("rate_ths") is not None else None,
                    threshold_ths=float(m.get("threshold_ths", 0.0)),
                    state=str(m.get("state", "UNKNOWN")),
                    active_boards=int(m["active_boards"]) if m.get("active_boards") is not None else None,
                    expected_boards=int(m.get("expected_boards", 3)),
                    episode_active=bool(m.get("episode_active", False)),
                    episode_duration_seconds=float(m.get("episode_duration_seconds", 0.0)),
                    acquisition_quality=str(m.get("acquisition_quality", "valid")),
                    acquisition_latency_seconds=float(m["acquisition_latency_seconds"]) if m.get("acquisition_latency_seconds") is not None else None,
                )
            )

        snapshot = MetricsSnapshot(
            schema_version=SNAPSHOT_SCHEMA_VERSION,
            generated_ts=completed_ts,
            monitor=MonitorMetrics(
                process_start_ts=process_start_ts,
                tick_sequence=tick_sequence,
                last_tick_completed_ts=completed_ts,
                telegram_poller_ts=telegram_poller_ts,
                telegram_sender_ts=telegram_sender_ts,
                queue_depth=queue_depth,
            ),
            miners=miners,
            telegram=TelegramMetrics(
                enqueued_total=int(telegram_counters.get("enqueued", 0)),
                sent_total=int(telegram_counters.get("sent", 0)),
                send_error_total=int(telegram_counters.get("error", 0)),
                dropped_total=int(telegram_counters.get("dropped", 0)),
                bypass_total=int(telegram_counters.get("bypass", 0)),
                fallback_total=int(telegram_counters.get("fallback", 0)),
            ),
            collector=CollectorMetrics(
                status=collector_status,
                age_seconds=collector_age_seconds,
            ),
            acquisition=AcquisitionMetrics(
                epoch_duration_seconds=epoch_duration_seconds,
            ),
        )
        return write_metrics_snapshot_atomic(path, snapshot)
    except Exception:
        return False

