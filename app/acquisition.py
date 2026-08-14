from __future__ import annotations

import math
import json
import socket
import threading
import time
from collections import Counter, deque
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Iterable, Mapping, Optional, Protocol, Sequence


class Authority(str, Enum):
    AUTHORITATIVE = "authoritative"
    DIAGNOSTIC = "diagnostic"


class Quality(str, Enum):
    VALID = "valid"
    PARTIAL = "partial"
    INVALID = "invalid"
    TIMEOUT = "timeout"
    ERROR = "error"
    LATE = "late"


class TransportStatus(str, Enum):
    SUCCESS = "success"
    EMPTY = "empty"
    INVALID_JSON = "invalid_json"
    TIMEOUT = "timeout"
    ERROR = "error"


@dataclass(frozen=True)
class AcquisitionConfig:
    enabled: bool = False
    workers: int = 2
    timeout_seconds: float = 5.0
    deadline_seconds: float = 12.0
    diagnostics_enabled: bool = False
    diagnostic_interval_seconds: float = 10.0

    @classmethod
    def from_mapping(
        cls,
        config: Mapping[str, Any],
    ) -> tuple[AcquisitionConfig, tuple[str, ...]]:
        warnings: list[str] = []

        enabled = _bool_config(
            config,
            "adaptive_acquisition_enabled",
            False,
            warnings,
        )
        workers = _int_config(
            config,
            "adaptive_acquisition_workers",
            2,
            1,
            4,
            warnings,
        )
        timeout_seconds = _float_config(
            config,
            "adaptive_acquisition_timeout_seconds",
            5.0,
            1.0,
            10.0,
            warnings,
        )
        deadline_seconds = _float_config(
            config,
            "adaptive_acquisition_deadline_seconds",
            12.0,
            timeout_seconds,
            30.0,
            warnings,
        )
        diagnostics_requested = _bool_config(
            config,
            "adaptive_diagnostics_enabled",
            False,
            warnings,
        )
        diagnostic_interval_seconds = _float_config(
            config,
            "adaptive_diagnostic_interval_seconds",
            10.0,
            5.0,
            60.0,
            warnings,
        )
        return (
            cls(
                enabled=enabled,
                workers=workers,
                timeout_seconds=timeout_seconds,
                deadline_seconds=deadline_seconds,
                diagnostics_enabled=enabled and diagnostics_requested,
                diagnostic_interval_seconds=diagnostic_interval_seconds,
            ),
            tuple(warnings),
        )


def _invalid_config(key: str, warnings: list[str]) -> None:
    warnings.append(f"invalid_config key={key} default_applied=true")


def _bool_config(
    config: Mapping[str, Any],
    key: str,
    default: bool,
    warnings: list[str],
) -> bool:
    if key not in config:
        return default
    value = config.get(key)
    if type(value) is bool:
        return value
    _invalid_config(key, warnings)
    return default


def _int_config(
    config: Mapping[str, Any],
    key: str,
    default: int,
    minimum: int,
    maximum: int,
    warnings: list[str],
) -> int:
    if key not in config:
        return default
    value = config.get(key)
    if type(value) is int and minimum <= value <= maximum:
        return value
    _invalid_config(key, warnings)
    return default


def _float_config(
    config: Mapping[str, Any],
    key: str,
    default: float,
    minimum: float,
    maximum: float,
    warnings: list[str],
) -> float:
    if key not in config:
        return default
    value = config.get(key)
    if (
        type(value) in (int, float)
        and math.isfinite(float(value))
        and minimum <= float(value) <= maximum
    ):
        return float(value)
    _invalid_config(key, warnings)
    return default


@dataclass(frozen=True)
class MinerEndpoint:
    key: str
    host: str
    port: int


@dataclass(frozen=True)
class TransportOutcome:
    status: TransportStatus
    payload: Optional[dict[str, Any]] = None
    completed_monotonic: float = 0.0
    latency_ms: float = 0.0


class TransportAdapter(Protocol):
    def __call__(
        self,
        endpoint: MinerEndpoint,
        command: str,
        timeout_seconds: float,
    ) -> TransportOutcome: ...


class Api4028Transport:
    _PAYLOADS = {
        "summary": b'{"command":"summary"}\n',
        "stats": b'{"command":"stats"}\n',
    }

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock

    def __call__(
        self,
        endpoint: MinerEndpoint,
        command: str,
        timeout_seconds: float,
    ) -> TransportOutcome:
        if command not in self._PAYLOADS:
            raise ValueError("unsupported scheduled API 4028 command")
        started = self._clock()
        try:
            with socket.create_connection(
                (endpoint.host, endpoint.port),
                timeout=timeout_seconds,
            ) as sock:
                sock.sendall(self._PAYLOADS[command])
                chunks: list[bytes] = []
                while True:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    chunks.append(chunk)
        except (TimeoutError, socket.timeout):
            return self._result(TransportStatus.TIMEOUT, started)
        except OSError:
            return self._result(TransportStatus.ERROR, started)
        except Exception:
            return self._result(TransportStatus.ERROR, started)

        raw = b"".join(chunks).replace(b"\x00", b"")
        if not raw:
            return self._result(TransportStatus.EMPTY, started)
        try:
            payload = json.loads(raw.decode("utf-8", errors="ignore"))
        except (UnicodeError, json.JSONDecodeError, TypeError, ValueError):
            return self._result(TransportStatus.INVALID_JSON, started)
        if not isinstance(payload, dict):
            return self._result(TransportStatus.INVALID_JSON, started)
        return self._result(TransportStatus.SUCCESS, started, payload)

    def _result(
        self,
        status: TransportStatus,
        started: float,
        payload: Optional[dict[str, Any]] = None,
    ) -> TransportOutcome:
        completed = self._clock()
        return TransportOutcome(
            status=status,
            payload=payload,
            completed_monotonic=completed,
            latency_ms=max(0.0, (completed - started) * 1000.0),
        )


@dataclass(frozen=True)
class AcquisitionEpoch:
    epoch_id: int
    scheduled_monotonic: float
    deadline_monotonic: float
    observed_ts: float


@dataclass(frozen=True)
class MinerSampleEnvelope:
    miner_key: str
    authority: Authority
    epoch_id: int
    observed_ts: float
    completed_monotonic: float
    latency_ms: float
    responded: bool
    rate_ths: Optional[float]
    elapsed_seconds: Optional[int]
    active_boards: Optional[int]
    quality: Quality
    reason_code: str
    summary_entry: Optional[dict[str, Any]]
    stats_response: Optional[dict[str, Any]]
    summary_requests: int
    stats_requests: int
    source: str = "api4028"


@dataclass(frozen=True)
class InFlightLease:
    lease_id: int
    miner_key: str
    authority: Authority
    epoch_id: int
    acquired_monotonic: float
    deadline_monotonic: float


class InFlightRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._leases: dict[str, InFlightLease] = {}
        self._next_id = 1

    def acquire(
        self,
        miner_key: str,
        authority: Authority,
        epoch_id: int,
        acquired_monotonic: float,
        deadline_monotonic: float,
    ) -> Optional[InFlightLease]:
        with self._lock:
            if miner_key in self._leases:
                return None
            lease = InFlightLease(
                lease_id=self._next_id,
                miner_key=miner_key,
                authority=authority,
                epoch_id=epoch_id,
                acquired_monotonic=acquired_monotonic,
                deadline_monotonic=deadline_monotonic,
            )
            self._next_id += 1
            self._leases[miner_key] = lease
            return lease

    def release(self, lease: Optional[InFlightLease]) -> bool:
        if lease is None:
            return False
        with self._lock:
            if self._leases.get(lease.miner_key) != lease:
                return False
            del self._leases[lease.miner_key]
            return True

    def is_owned(self, miner_key: str) -> bool:
        with self._lock:
            return miner_key in self._leases


class EpochScheduler:
    def __init__(self, period_seconds: float) -> None:
        if not math.isfinite(period_seconds) or period_seconds <= 0:
            raise ValueError("period_seconds must be finite and positive")
        self.period_seconds = float(period_seconds)
        self.last_epoch_id = 0
        self.last_scheduled_monotonic: Optional[float] = None
        self.skipped_epoch_count = 0

    def next_epoch(
        self,
        now_monotonic: float,
        observed_ts: float,
        deadline_seconds: float,
    ) -> Optional[AcquisitionEpoch]:
        if self.last_scheduled_monotonic is not None:
            elapsed = max(0.0, now_monotonic - self.last_scheduled_monotonic)
            if elapsed < self.period_seconds:
                return None
            elapsed_periods = max(1, int(elapsed // self.period_seconds))
            self.skipped_epoch_count += max(0, elapsed_periods - 1)
        self.last_epoch_id += 1
        self.last_scheduled_monotonic = now_monotonic
        return AcquisitionEpoch(
            epoch_id=self.last_epoch_id,
            scheduled_monotonic=now_monotonic,
            deadline_monotonic=now_monotonic + deadline_seconds,
            observed_ts=observed_ts,
        )


@dataclass(frozen=True)
class PollHealthSnapshot:
    consecutive_timeouts: int
    last_success_ts: Optional[float]
    latency_window: tuple[float, ...]
    in_flight: int
    last_epoch_duration_ms: float
    last_epoch_completed_count: int
    last_epoch_quality_counts: Mapping[str, int]
    last_epoch_summary_requests: int
    last_epoch_stats_requests: int
    skipped_epoch_count: int
    fleet_reason_code: str


class PollHealth:
    def __init__(self, latency_window_size: int = 32) -> None:
        if latency_window_size < 1:
            raise ValueError("latency_window_size must be positive")
        self._lock = threading.Lock()
        self._latencies: deque[float] = deque(maxlen=latency_window_size)
        self._consecutive_timeouts = 0
        self._last_success_ts: Optional[float] = None
        self._last_epoch_duration_ms = 0.0
        self._last_epoch_completed_count = 0
        self._last_epoch_quality_counts: dict[str, int] = {}
        self._last_epoch_summary_requests = 0
        self._last_epoch_stats_requests = 0
        self._skipped_epoch_count = 0
        self._fleet_reason_code = "none"
        self._in_flight_provider: Callable[[], int] = lambda: 0

    def bind_in_flight_provider(self, provider: Callable[[], int]) -> None:
        self._in_flight_provider = provider

    def set_skipped_epoch_count(self, count: int) -> None:
        with self._lock:
            self._skipped_epoch_count = max(0, int(count))

    def record_epoch(
        self,
        epoch: AcquisitionEpoch,
        envelopes: Sequence[MinerSampleEnvelope],
    ) -> None:
        quality_counts = Counter(item.quality.value for item in envelopes)
        transport_failures = {
            "transport_timeout",
            "transport_error",
        }
        all_transport_failed = bool(envelopes) and all(
            item.reason_code in transport_failures for item in envelopes
        )
        valid_observation_times = [
            item.observed_ts for item in envelopes if item.quality is Quality.VALID
        ]
        latest_completion = max(
            (item.completed_monotonic for item in envelopes),
            default=epoch.scheduled_monotonic,
        )
        with self._lock:
            for item in envelopes:
                if math.isfinite(item.latency_ms):
                    self._latencies.append(max(0.0, item.latency_ms))
            if quality_counts.get(Quality.TIMEOUT.value, 0):
                self._consecutive_timeouts += 1
            else:
                self._consecutive_timeouts = 0
            if valid_observation_times:
                self._last_success_ts = max(valid_observation_times)
            self._last_epoch_duration_ms = max(
                0.0,
                (latest_completion - epoch.scheduled_monotonic) * 1000.0,
            )
            self._last_epoch_completed_count = len(envelopes)
            self._last_epoch_quality_counts = dict(quality_counts)
            self._last_epoch_summary_requests = sum(
                item.summary_requests for item in envelopes
            )
            self._last_epoch_stats_requests = sum(
                item.stats_requests for item in envelopes
            )
            self._fleet_reason_code = (
                "fleet_transport_failure" if all_transport_failed else "none"
            )

    def snapshot(self) -> PollHealthSnapshot:
        with self._lock:
            return PollHealthSnapshot(
                consecutive_timeouts=self._consecutive_timeouts,
                last_success_ts=self._last_success_ts,
                latency_window=tuple(self._latencies),
                in_flight=max(0, int(self._in_flight_provider())),
                last_epoch_duration_ms=self._last_epoch_duration_ms,
                last_epoch_completed_count=self._last_epoch_completed_count,
                last_epoch_quality_counts=dict(self._last_epoch_quality_counts),
                last_epoch_summary_requests=self._last_epoch_summary_requests,
                last_epoch_stats_requests=self._last_epoch_stats_requests,
                skipped_epoch_count=self._skipped_epoch_count,
                fleet_reason_code=self._fleet_reason_code,
            )


@dataclass(frozen=True)
class _SubmittedRequest:
    endpoint: MinerEndpoint
    lease: InFlightLease
    future: Future[MinerSampleEnvelope]


class BoundedAcquirer:
    def __init__(
        self,
        transport: TransportAdapter,
        *,
        workers: int,
        timeout_seconds: float,
        leases: Optional[InFlightRegistry] = None,
        poll_health: Optional[PollHealth] = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not 1 <= workers <= 4:
            raise ValueError("workers must be between 1 and 4")
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be finite and positive")
        self._transport = transport
        self._timeout_seconds = float(timeout_seconds)
        self._clock = clock
        self._leases = leases or InFlightRegistry()
        self._poll_health = poll_health or PollHealth()
        self._executor = ThreadPoolExecutor(
            max_workers=workers,
            thread_name_prefix="miner-acquisition",
        )
        self._closed = False
        self._active_lock = threading.Lock()
        self._active_workers = 0
        self._poll_health.bind_in_flight_provider(self._in_flight_count)

    @property
    def poll_health(self) -> PollHealth:
        return self._poll_health

    def _in_flight_count(self) -> int:
        with self._active_lock:
            return self._active_workers

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._executor.shutdown(wait=True, cancel_futures=True)

    def collect_authoritative(
        self,
        miners: Iterable[MinerEndpoint],
        epoch: AcquisitionEpoch,
    ) -> dict[str, MinerSampleEnvelope]:
        ordered = tuple(miners)
        result = self._collect(
            ordered,
            authority=Authority.AUTHORITATIVE,
            epoch_id=epoch.epoch_id,
            scheduled_monotonic=epoch.scheduled_monotonic,
            deadline_monotonic=epoch.deadline_monotonic,
            observed_ts=epoch.observed_ts,
            include_stats=True,
        )
        self._poll_health.record_epoch(epoch, tuple(result.values()))
        return result

    def collect_diagnostic(
        self,
        miners: Iterable[MinerEndpoint],
        *,
        diagnostic_id: int,
        observed_ts: float,
        deadline_monotonic: float,
    ) -> dict[str, MinerSampleEnvelope]:
        return self._collect(
            tuple(miners),
            authority=Authority.DIAGNOSTIC,
            epoch_id=diagnostic_id,
            scheduled_monotonic=self._clock(),
            deadline_monotonic=deadline_monotonic,
            observed_ts=observed_ts,
            include_stats=False,
        )

    def _collect(
        self,
        miners: Sequence[MinerEndpoint],
        *,
        authority: Authority,
        epoch_id: int,
        scheduled_monotonic: float,
        deadline_monotonic: float,
        observed_ts: float,
        include_stats: bool,
    ) -> dict[str, MinerSampleEnvelope]:
        if self._closed:
            raise RuntimeError("acquirer is closed")
        keys = [miner.key for miner in miners]
        if len(keys) != len(set(keys)):
            raise ValueError("miner keys must be unique")

        envelopes: dict[str, MinerSampleEnvelope] = {}
        submitted: dict[Future[MinerSampleEnvelope], _SubmittedRequest] = {}
        acquired_at = self._clock()
        for endpoint in miners:
            lease = self._leases.acquire(
                endpoint.key,
                authority,
                epoch_id,
                acquired_at,
                deadline_monotonic,
            )
            if lease is None:
                envelopes[endpoint.key] = _base_envelope(
                    endpoint.key,
                    authority,
                    epoch_id,
                    observed_ts,
                    acquired_at,
                    quality=Quality.ERROR,
                    reason_code="scheduled_overlap",
                )
                continue
            future = self._executor.submit(
                self._acquire_one,
                endpoint,
                lease,
                observed_ts,
                deadline_monotonic,
                include_stats,
            )
            submitted[future] = _SubmittedRequest(endpoint, lease, future)

        wait_seconds = max(0.0, deadline_monotonic - self._clock())
        done, not_done = wait(tuple(submitted), timeout=wait_seconds)
        for future in done:
            request = submitted[future]
            try:
                envelopes[request.endpoint.key] = future.result()
            except Exception:
                envelopes[request.endpoint.key] = _base_envelope(
                    request.endpoint.key,
                    authority,
                    epoch_id,
                    observed_ts,
                    self._clock(),
                    quality=Quality.ERROR,
                    reason_code="transport_error",
                    summary_requests=1,
                )

        for future in not_done:
            request = submitted[future]
            running = future.running()
            if future.cancel():
                self._leases.release(request.lease)
                running = False
            envelopes[request.endpoint.key] = _base_envelope(
                request.endpoint.key,
                authority,
                epoch_id,
                observed_ts,
                deadline_monotonic,
                quality=Quality.LATE,
                reason_code="epoch_deadline_exceeded",
                latency_ms=max(
                    0.0,
                    (deadline_monotonic - scheduled_monotonic) * 1000.0,
                ),
                summary_requests=1 if running else 0,
            )

        return {miner.key: envelopes[miner.key] for miner in miners}

    def _acquire_one(
        self,
        endpoint: MinerEndpoint,
        lease: InFlightLease,
        observed_ts: float,
        deadline_monotonic: float,
        include_stats: bool,
    ) -> MinerSampleEnvelope:
        with self._active_lock:
            self._active_workers += 1
        try:
            if self._clock() >= deadline_monotonic:
                return _base_envelope(
                    endpoint.key,
                    lease.authority,
                    lease.epoch_id,
                    observed_ts,
                    self._clock(),
                    quality=Quality.LATE,
                    reason_code="epoch_deadline_exceeded",
                )
            summary = self._safe_transport(endpoint, "summary")
            envelope = _normalize_summary(
                endpoint.key,
                lease.authority,
                lease.epoch_id,
                observed_ts,
                summary,
            )
            if envelope.completed_monotonic > deadline_monotonic:
                return _as_late(envelope)
            if envelope.quality is not Quality.VALID or not include_stats:
                return envelope

            stats = self._safe_transport(endpoint, "stats")
            envelope = _with_stats(envelope, stats)
            if envelope.completed_monotonic > deadline_monotonic:
                return _as_late(envelope)
            return envelope
        finally:
            self._leases.release(lease)
            with self._active_lock:
                self._active_workers -= 1

    def _safe_transport(
        self,
        endpoint: MinerEndpoint,
        command: str,
    ) -> TransportOutcome:
        started = self._clock()
        try:
            result = self._transport(endpoint, command, self._timeout_seconds)
            if not isinstance(result, TransportOutcome):
                raise TypeError("transport must return TransportOutcome")
            return result
        except Exception:
            completed = self._clock()
            return TransportOutcome(
                status=TransportStatus.ERROR,
                payload=None,
                completed_monotonic=completed,
                latency_ms=max(0.0, (completed - started) * 1000.0),
            )


def _base_envelope(
    miner_key: str,
    authority: Authority,
    epoch_id: int,
    observed_ts: float,
    completed_monotonic: float,
    *,
    quality: Quality,
    reason_code: str,
    latency_ms: float = 0.0,
    responded: bool = False,
    rate_ths: Optional[float] = None,
    elapsed_seconds: Optional[int] = None,
    active_boards: Optional[int] = None,
    summary_entry: Optional[dict[str, Any]] = None,
    stats_response: Optional[dict[str, Any]] = None,
    summary_requests: int = 0,
    stats_requests: int = 0,
) -> MinerSampleEnvelope:
    return MinerSampleEnvelope(
        miner_key=miner_key,
        authority=authority,
        epoch_id=epoch_id,
        observed_ts=observed_ts,
        completed_monotonic=completed_monotonic,
        latency_ms=max(0.0, latency_ms),
        responded=responded,
        rate_ths=rate_ths,
        elapsed_seconds=elapsed_seconds,
        active_boards=active_boards,
        quality=quality,
        reason_code=reason_code,
        summary_entry=summary_entry,
        stats_response=stats_response,
        summary_requests=summary_requests,
        stats_requests=stats_requests,
    )


def _normalize_summary(
    miner_key: str,
    authority: Authority,
    epoch_id: int,
    observed_ts: float,
    outcome: TransportOutcome,
) -> MinerSampleEnvelope:
    status_reason = {
        TransportStatus.EMPTY: (Quality.INVALID, "empty_payload"),
        TransportStatus.INVALID_JSON: (Quality.INVALID, "invalid_json"),
        TransportStatus.TIMEOUT: (Quality.TIMEOUT, "transport_timeout"),
        TransportStatus.ERROR: (Quality.ERROR, "transport_error"),
    }
    if outcome.status is not TransportStatus.SUCCESS:
        quality, reason = status_reason.get(
            outcome.status,
            (Quality.ERROR, "transport_error"),
        )
        return _base_envelope(
            miner_key,
            authority,
            epoch_id,
            observed_ts,
            outcome.completed_monotonic,
            quality=quality,
            reason_code=reason,
            latency_ms=outcome.latency_ms,
            summary_requests=1,
        )

    payload = outcome.payload
    if not isinstance(payload, dict):
        return _base_envelope(
            miner_key,
            authority,
            epoch_id,
            observed_ts,
            outcome.completed_monotonic,
            quality=Quality.INVALID,
            reason_code="empty_payload",
            latency_ms=outcome.latency_ms,
            summary_requests=1,
        )
    summary = payload.get("SUMMARY")
    entry = summary[0] if isinstance(summary, list) and summary else None
    if not isinstance(entry, dict):
        return _base_envelope(
            miner_key,
            authority,
            epoch_id,
            observed_ts,
            outcome.completed_monotonic,
            quality=Quality.INVALID,
            reason_code="summary_missing",
            latency_ms=outcome.latency_ms,
            responded=True,
            summary_requests=1,
        )

    rate_ths = _extract_rate_ths(entry)
    elapsed_seconds = _optional_int(entry.get("Elapsed"))
    if rate_ths is None:
        return _base_envelope(
            miner_key,
            authority,
            epoch_id,
            observed_ts,
            outcome.completed_monotonic,
            quality=Quality.INVALID,
            reason_code="rate_invalid",
            latency_ms=outcome.latency_ms,
            responded=True,
            elapsed_seconds=elapsed_seconds,
            summary_entry=entry,
            summary_requests=1,
        )
    return _base_envelope(
        miner_key,
        authority,
        epoch_id,
        observed_ts,
        outcome.completed_monotonic,
        quality=Quality.VALID,
        reason_code="ok",
        latency_ms=outcome.latency_ms,
        responded=True,
        rate_ths=rate_ths,
        elapsed_seconds=elapsed_seconds,
        summary_entry=entry,
        summary_requests=1,
    )


def _with_stats(
    envelope: MinerSampleEnvelope,
    outcome: TransportOutcome,
) -> MinerSampleEnvelope:
    active_boards: Optional[int] = None
    payload = outcome.payload if outcome.status is TransportStatus.SUCCESS else None
    if isinstance(payload, dict):
        stats = payload.get("STATS")
        entries = stats if isinstance(stats, list) else [stats]
        for entry in entries:
            if isinstance(entry, dict):
                active_boards = _count_active_boards(entry)
                if active_boards is not None:
                    break
    quality = Quality.VALID if active_boards is not None else Quality.PARTIAL
    reason_code = "ok" if active_boards is not None else "stats_missing"
    return MinerSampleEnvelope(
        miner_key=envelope.miner_key,
        authority=envelope.authority,
        epoch_id=envelope.epoch_id,
        observed_ts=envelope.observed_ts,
        completed_monotonic=max(
            envelope.completed_monotonic,
            outcome.completed_monotonic,
        ),
        latency_ms=envelope.latency_ms + max(0.0, outcome.latency_ms),
        responded=envelope.responded,
        rate_ths=envelope.rate_ths,
        elapsed_seconds=envelope.elapsed_seconds,
        active_boards=active_boards,
        quality=quality,
        reason_code=reason_code,
        summary_entry=envelope.summary_entry,
        stats_response=payload,
        summary_requests=envelope.summary_requests,
        stats_requests=1,
        source=envelope.source,
    )


def _as_late(envelope: MinerSampleEnvelope) -> MinerSampleEnvelope:
    return MinerSampleEnvelope(
        miner_key=envelope.miner_key,
        authority=envelope.authority,
        epoch_id=envelope.epoch_id,
        observed_ts=envelope.observed_ts,
        completed_monotonic=envelope.completed_monotonic,
        latency_ms=envelope.latency_ms,
        responded=envelope.responded,
        rate_ths=envelope.rate_ths,
        elapsed_seconds=envelope.elapsed_seconds,
        active_boards=envelope.active_boards,
        quality=Quality.LATE,
        reason_code="epoch_deadline_exceeded",
        summary_entry=envelope.summary_entry,
        stats_response=envelope.stats_response,
        summary_requests=envelope.summary_requests,
        stats_requests=envelope.stats_requests,
        source=envelope.source,
    )


def _extract_rate_ths(entry: Mapping[str, Any]) -> Optional[float]:
    for key, divisor in (
        ("GHS 5s", 1_000.0),
        ("GHS av", 1_000.0),
        ("MHS 5s", 1_000_000.0),
        ("MHS av", 1_000_000.0),
    ):
        if key not in entry:
            continue
        try:
            value = float(entry[key]) / divisor
        except (TypeError, ValueError, OverflowError):
            continue
        if math.isfinite(value):
            return value
    return None


def _optional_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _count_active_boards(stats_entry: Mapping[str, Any]) -> Optional[int]:
    chain_acn = stats_entry.get("chain_acn")
    if isinstance(chain_acn, list):
        return sum(
            1
            for value in chain_acn
            if isinstance(value, (int, float)) and value > 0
        )
    count = 0
    found = False
    for index in range(10):
        for key, is_status in (
            (f"chain_acn{index}", False),
            (f"chain{index}_asicnum", False),
            (f"chain{index}_alive", False),
            (f"chain{index}_status", True),
        ):
            if key not in stats_entry:
                continue
            found = True
            value = stats_entry.get(key)
            if is_status:
                if str(value).lower() in ("alive", "o", "ok"):
                    count += 1
            else:
                try:
                    if int(value) > 0:
                        count += 1
                except (TypeError, ValueError, OverflowError):
                    pass
            break
    return count if found else None


def dispatch_authoritative(
    envelopes: Iterable[MinerSampleEnvelope],
    consumer: Callable[[MinerSampleEnvelope], Any],
) -> int:
    applied = 0
    for envelope in envelopes:
        if envelope.authority is not Authority.AUTHORITATIVE:
            continue
        if envelope.quality is Quality.LATE:
            continue
        consumer(envelope)
        applied += 1
    return applied
