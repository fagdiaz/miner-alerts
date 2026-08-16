import json
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Mapping, Optional


SCHEMA_VERSION = 6


_TELEMETRY_COLUMNS = {
    "max_temp_c": "REAL",
    "chain_voltage_mv_avg": "REAL",
    "chain_power_w_total": "REAL",
    "frequency_mhz_avg": "REAL",
    "hw_errors_total": "INTEGER",
    "fan_rpm_max": "INTEGER",
    "fan_pwm_percent": "REAL",
    "diagnostic_flags_json": "TEXT NOT NULL DEFAULT '[]'",
    "accepted_shares_total": "INTEGER",
    "rejected_shares_total": "INTEGER",
    "stale_shares_total": "INTEGER",
    "chain_fault_count": "INTEGER",
    "chains_not_mining_count": "INTEGER",
    "chains_transitioning_count": "INTEGER",
    "quality_flags_json": "TEXT NOT NULL DEFAULT '[]'",
    # Spec 022 acquisition quality provenance (optional, may be NULL for legacy rows)
    "acquisition_authority": "TEXT",
    "acquisition_reason_code": "TEXT",
}

_FIRMWARE_EVENT_COLUMNS = {
    "source_ts_epoch": "REAL",
    "source_clock": "TEXT NOT NULL DEFAULT 'unparsed'",
}


class EventStore:
    def __init__(
        self,
        db_path: Path,
        *,
        on_error: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.path = Path(db_path).resolve()
        self._on_error = on_error
        self._lock = threading.RLock()
        self._connection: Optional[sqlite3.Connection] = None
        self._last_error: Optional[str] = None
        self._last_error_log_ts: Dict[str, float] = {}
        self._initialize()

    @property
    def available(self) -> bool:
        return self._connection is not None

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    @property
    def schema_version(self) -> int:
        connection = self._connection
        if connection is None:
            return 0
        with self._lock:
            row = connection.execute("PRAGMA user_version").fetchone()
        return int(row[0]) if row else 0

    def _report_error(self, operation: str, exc: BaseException) -> None:
        message = f"EVENT_STORE operation={operation} error={type(exc).__name__}:{exc}"
        self._last_error = message
        now = time.monotonic()
        last_log = self._last_error_log_ts.get(operation)
        if self._on_error and (last_log is None or (now - last_log) >= 60.0):
            self._last_error_log_ts[operation] = now
            self._on_error(message)

    def _initialize(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(
                str(self.path),
                timeout=5.0,
                check_same_thread=False,
            )
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
            connection.execute("PRAGMA busy_timeout=5000")
            connection.execute("PRAGMA foreign_keys=ON")
            self._connection = connection
            self._create_schema()
            self._last_error = None
        except (OSError, sqlite3.Error) as exc:
            self._connection = None
            self._report_error("initialize", exc)

    def _create_schema(self) -> None:
        connection = self._connection
        if connection is None:
            return
        with self._lock, connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS telemetry_samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    observed_ts REAL NOT NULL,
                    miner_key TEXT NOT NULL,
                    miner_name TEXT NOT NULL,
                    host TEXT NOT NULL,
                    state TEXT NOT NULL,
                    responded INTEGER NOT NULL,
                    rate_ths REAL,
                    threshold_ths REAL NOT NULL,
                    active_boards INTEGER,
                    expected_boards INTEGER NOT NULL,
                    elapsed_seconds INTEGER,
                    max_temp_c REAL,
                    chain_voltage_mv_avg REAL,
                    chain_power_w_total REAL,
                    frequency_mhz_avg REAL,
                    hw_errors_total INTEGER,
                    fan_rpm_max INTEGER,
                    fan_pwm_percent REAL,
                    diagnostic_flags_json TEXT NOT NULL DEFAULT '[]',
                    accepted_shares_total INTEGER,
                    rejected_shares_total INTEGER,
                    stale_shares_total INTEGER,
                    chain_fault_count INTEGER,
                    chains_not_mining_count INTEGER,
                    chains_transitioning_count INTEGER,
                    quality_flags_json TEXT NOT NULL DEFAULT '[]'
                );

                CREATE INDEX IF NOT EXISTS ix_samples_miner_time
                    ON telemetry_samples(miner_key, observed_ts DESC);
                CREATE INDEX IF NOT EXISTS ix_samples_time
                    ON telemetry_samples(observed_ts);

                CREATE TABLE IF NOT EXISTS operational_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    occurred_ts REAL NOT NULL,
                    miner_key TEXT,
                    miner_name TEXT,
                    host TEXT,
                    event_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    classification TEXT,
                    previous_state TEXT,
                    new_state TEXT,
                    rate_ths REAL,
                    threshold_ths REAL,
                    previous_elapsed INTEGER,
                    current_elapsed INTEGER,
                    action_source TEXT,
                    action_ts REAL,
                    summary TEXT NOT NULL,
                    details_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE INDEX IF NOT EXISTS ix_events_time
                    ON operational_events(occurred_ts DESC);
                CREATE INDEX IF NOT EXISTS ix_events_miner_time
                    ON operational_events(miner_key, occurred_ts DESC);
                CREATE INDEX IF NOT EXISTS ix_events_type_time
                    ON operational_events(event_type, occurred_ts DESC);

                CREATE TABLE IF NOT EXISTS reboot_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    evaluated_ts REAL NOT NULL,
                    miner_key TEXT NOT NULL,
                    miner_name TEXT NOT NULL,
                    host TEXT NOT NULL,
                    result TEXT NOT NULL,
                    state TEXT NOT NULL,
                    responded INTEGER NOT NULL,
                    rate_ths REAL,
                    threshold_ths REAL NOT NULL,
                    low_elapsed_seconds REAL,
                    active_boards INTEGER,
                    expected_boards INTEGER NOT NULL,
                    max_temp_c REAL,
                    chain_voltage_mv_avg REAL,
                    chain_power_w_total REAL,
                    frequency_mhz_avg REAL,
                    hw_errors_total INTEGER,
                    fan_rpm_max INTEGER,
                    fan_pwm_percent REAL,
                    diagnostic_flags_json TEXT NOT NULL DEFAULT '[]',
                    startup_guard_active INTEGER NOT NULL,
                    qa_mode INTEGER NOT NULL,
                    cooldown_remaining_seconds REAL,
                    window_count INTEGER NOT NULL,
                    window_seconds INTEGER NOT NULL,
                    details_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE INDEX IF NOT EXISTS ix_decisions_miner_time
                    ON reboot_decisions(miner_key, evaluated_ts DESC);
                CREATE INDEX IF NOT EXISTS ix_decisions_time
                    ON reboot_decisions(evaluated_ts DESC);
                CREATE INDEX IF NOT EXISTS ix_decisions_result_time
                    ON reboot_decisions(result, evaluated_ts DESC);

                CREATE TABLE IF NOT EXISTS firmware_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    collected_ts REAL NOT NULL,
                    source_ts_text TEXT NOT NULL,
                    source_ts_epoch REAL,
                    source_clock TEXT NOT NULL DEFAULT 'unparsed',
                    miner_key TEXT NOT NULL,
                    miner_name TEXT NOT NULL,
                    host TEXT NOT NULL,
                    source_tab TEXT NOT NULL,
                    source_fingerprint TEXT NOT NULL,
                    category TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    code TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    UNIQUE(miner_key, source_tab, source_fingerprint)
                );

                CREATE INDEX IF NOT EXISTS ix_firmware_events_collected
                    ON firmware_events(collected_ts DESC);
                CREATE INDEX IF NOT EXISTS ix_firmware_events_miner_source_time
                    ON firmware_events(miner_key, source_tab, source_ts_text DESC);
                CREATE INDEX IF NOT EXISTS ix_firmware_events_category_time
                    ON firmware_events(category, collected_ts DESC);

                CREATE TABLE IF NOT EXISTS collector_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_ts REAL NOT NULL,
                    completed_ts REAL NOT NULL,
                    status TEXT NOT NULL,
                    attempted INTEGER NOT NULL,
                    succeeded INTEGER NOT NULL,
                    failed INTEGER NOT NULL,
                    events_parsed INTEGER NOT NULL,
                    events_inserted INTEGER NOT NULL,
                    events_duplicate INTEGER NOT NULL,
                    events_failed INTEGER NOT NULL,
                    truncated_streams INTEGER NOT NULL,
                    summary TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS ix_collector_runs_completed
                    ON collector_runs(completed_ts DESC);
                """
            )
            existing_columns = {
                str(row[1])
                for row in connection.execute("PRAGMA table_info(telemetry_samples)").fetchall()
            }
            for column_name, column_type in _TELEMETRY_COLUMNS.items():
                if column_name not in existing_columns:
                    connection.execute(
                        f"ALTER TABLE telemetry_samples ADD COLUMN {column_name} {column_type}"
                    )
            firmware_columns = {
                str(row[1])
                for row in connection.execute("PRAGMA table_info(firmware_events)").fetchall()
            }
            for column_name, column_type in _FIRMWARE_EVENT_COLUMNS.items():
                if column_name not in firmware_columns:
                    connection.execute(
                        f"ALTER TABLE firmware_events ADD COLUMN {column_name} {column_type}"
                    )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS ix_firmware_events_source_epoch "
                "ON firmware_events(source_ts_epoch DESC)"
            )
            connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")

    def record_sample(
        self,
        *,
        observed_ts: float,
        miner_key: str,
        miner_name: str,
        host: str,
        state: str,
        responded: bool,
        rate_ths: Optional[float],
        threshold_ths: float,
        active_boards: Optional[int],
        expected_boards: int,
        elapsed_seconds: Optional[int],
        telemetry: Optional[Mapping[str, Any]] = None,
    ) -> bool:
        connection = self._connection
        if connection is None:
            return False
        try:
            normalized = telemetry or {}
            flags_json = json.dumps(
                list(normalized.get("diagnostic_flags") or []),
                ensure_ascii=True,
                separators=(",", ":"),
            )
            quality_flags_json = json.dumps(
                list(normalized.get("quality_flags") or []),
                ensure_ascii=True,
                separators=(",", ":"),
            )
            # Spec 022 acquisition quality: sanitize to str or None
            raw_authority = normalized.get("acquisition_authority")
            acq_authority = str(raw_authority) if raw_authority is not None else None
            raw_reason = normalized.get("acquisition_reason_code")
            acq_reason_code = str(raw_reason) if raw_reason is not None else None
            with self._lock, connection:
                connection.execute(
                    """
                    INSERT INTO telemetry_samples (
                        observed_ts, miner_key, miner_name, host, state, responded,
                        rate_ths, threshold_ths, active_boards, expected_boards,
                        elapsed_seconds, max_temp_c, chain_voltage_mv_avg,
                        chain_power_w_total, frequency_mhz_avg, hw_errors_total,
                        fan_rpm_max, fan_pwm_percent, diagnostic_flags_json,
                        accepted_shares_total, rejected_shares_total,
                        stale_shares_total, chain_fault_count,
                        chains_not_mining_count, chains_transitioning_count,
                        quality_flags_json,
                        acquisition_authority, acquisition_reason_code
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        float(observed_ts),
                        miner_key,
                        miner_name,
                        host,
                        state,
                        1 if responded else 0,
                        rate_ths,
                        float(threshold_ths),
                        active_boards,
                        int(expected_boards),
                        elapsed_seconds,
                        normalized.get("max_temp_c"),
                        normalized.get("chain_voltage_mv_avg"),
                        normalized.get("chain_power_w_total"),
                        normalized.get("frequency_mhz_avg"),
                        normalized.get("hw_errors_total"),
                        normalized.get("fan_rpm_max"),
                        normalized.get("fan_pwm_percent"),
                        flags_json,
                        normalized.get("accepted_shares_total"),
                        normalized.get("rejected_shares_total"),
                        normalized.get("stale_shares_total"),
                        normalized.get("chain_fault_count"),
                        normalized.get("chains_not_mining_count"),
                        normalized.get("chains_transitioning_count"),
                        quality_flags_json,
                        acq_authority,
                        acq_reason_code,
                    ),
                )
            self._last_error = None
            return True
        except (TypeError, ValueError, sqlite3.Error) as exc:
            self._report_error("record_sample", exc)
            return False

    def record_reboot_decision(
        self,
        *,
        evaluated_ts: float,
        miner_key: str,
        miner_name: str,
        host: str,
        result: str,
        state: str,
        responded: bool,
        rate_ths: Optional[float],
        threshold_ths: float,
        low_elapsed_seconds: Optional[float],
        active_boards: Optional[int],
        expected_boards: int,
        startup_guard_active: bool,
        qa_mode: bool,
        cooldown_remaining_seconds: Optional[float],
        window_count: int,
        window_seconds: int,
        telemetry: Optional[Mapping[str, Any]] = None,
        details: Optional[Mapping[str, Any]] = None,
    ) -> Optional[int]:
        connection = self._connection
        if connection is None:
            return None
        normalized = telemetry or {}
        try:
            flags_json = json.dumps(
                list(normalized.get("diagnostic_flags") or []),
                ensure_ascii=True,
                separators=(",", ":"),
            )
            details_json = json.dumps(
                dict(details or {}),
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            )
            with self._lock, connection:
                cursor = connection.execute(
                    """
                    INSERT INTO reboot_decisions (
                        evaluated_ts, miner_key, miner_name, host, result, state,
                        responded, rate_ths, threshold_ths, low_elapsed_seconds,
                        active_boards, expected_boards, max_temp_c,
                        chain_voltage_mv_avg, chain_power_w_total,
                        frequency_mhz_avg, hw_errors_total, fan_rpm_max,
                        fan_pwm_percent, diagnostic_flags_json,
                        startup_guard_active, qa_mode, cooldown_remaining_seconds,
                        window_count, window_seconds, details_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        float(evaluated_ts),
                        miner_key,
                        miner_name,
                        host,
                        result,
                        state,
                        1 if responded else 0,
                        rate_ths,
                        float(threshold_ths),
                        low_elapsed_seconds,
                        active_boards,
                        int(expected_boards),
                        normalized.get("max_temp_c"),
                        normalized.get("chain_voltage_mv_avg"),
                        normalized.get("chain_power_w_total"),
                        normalized.get("frequency_mhz_avg"),
                        normalized.get("hw_errors_total"),
                        normalized.get("fan_rpm_max"),
                        normalized.get("fan_pwm_percent"),
                        flags_json,
                        1 if startup_guard_active else 0,
                        1 if qa_mode else 0,
                        cooldown_remaining_seconds,
                        int(window_count),
                        int(window_seconds),
                        details_json,
                    ),
                )
                self._last_error = None
                return int(cursor.lastrowid)
        except (TypeError, ValueError, sqlite3.Error) as exc:
            self._report_error("record_reboot_decision", exc)
            return None

    def record_event(
        self,
        *,
        occurred_ts: float,
        event_type: str,
        severity: str,
        summary: str,
        miner_key: Optional[str] = None,
        miner_name: Optional[str] = None,
        host: Optional[str] = None,
        classification: Optional[str] = None,
        previous_state: Optional[str] = None,
        new_state: Optional[str] = None,
        rate_ths: Optional[float] = None,
        threshold_ths: Optional[float] = None,
        previous_elapsed: Optional[int] = None,
        current_elapsed: Optional[int] = None,
        action_source: Optional[str] = None,
        action_ts: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Optional[int]:
        connection = self._connection
        if connection is None:
            return None
        try:
            details_json = json.dumps(
                details or {},
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            )
            with self._lock, connection:
                cursor = connection.execute(
                    """
                    INSERT INTO operational_events (
                        occurred_ts, miner_key, miner_name, host, event_type,
                        severity, classification, previous_state, new_state,
                        rate_ths, threshold_ths, previous_elapsed, current_elapsed,
                        action_source, action_ts, summary, details_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        float(occurred_ts),
                        miner_key,
                        miner_name,
                        host,
                        event_type,
                        severity,
                        classification,
                        previous_state,
                        new_state,
                        rate_ths,
                        threshold_ths,
                        previous_elapsed,
                        current_elapsed,
                        action_source,
                        action_ts,
                        summary,
                        details_json,
                    ),
                )
                self._last_error = None
                return int(cursor.lastrowid)
        except (TypeError, ValueError, sqlite3.Error) as exc:
            self._report_error("record_event", exc)
            return None

    def list_events(
        self,
        *,
        limit: int = 8,
        miner_key: Optional[str] = None,
    ) -> list[Dict[str, Any]]:
        connection = self._connection
        if connection is None:
            return []
        safe_limit = max(1, min(int(limit), 50))
        try:
            with self._lock:
                if miner_key:
                    rows = connection.execute(
                        """
                        SELECT * FROM operational_events
                        WHERE miner_key = ?
                        ORDER BY occurred_ts DESC, id DESC
                        LIMIT ?
                        """,
                        (miner_key, safe_limit),
                    ).fetchall()
                else:
                    rows = connection.execute(
                        """
                        SELECT * FROM operational_events
                        ORDER BY occurred_ts DESC, id DESC
                        LIMIT ?
                        """,
                        (safe_limit,),
                    ).fetchall()
            self._last_error = None
            return [dict(row) for row in rows]
        except sqlite3.Error as exc:
            self._report_error("list_events", exc)
            return []

    def get_event(self, event_id: int) -> Optional[Dict[str, Any]]:
        connection = self._connection
        if connection is None:
            return None
        try:
            with self._lock:
                row = connection.execute(
                    "SELECT * FROM operational_events WHERE id = ?",
                    (int(event_id),),
                ).fetchone()
            self._last_error = None
            return dict(row) if row else None
        except (TypeError, ValueError, sqlite3.Error) as exc:
            self._report_error("get_event", exc)
            return None

    def list_episode_events(
        self,
        event_id: int,
        *,
        max_window_seconds: float = 21_600.0,
        limit: int = 50,
    ) -> list[Dict[str, Any]]:
        connection = self._connection
        if connection is None:
            return []
        safe_window = max(300.0, min(float(max_window_seconds), 86_400.0))
        safe_limit = max(1, min(int(limit), 100))
        try:
            with self._lock:
                anchor = connection.execute(
                    "SELECT * FROM operational_events WHERE id = ?",
                    (int(event_id),),
                ).fetchone()
                if anchor is None:
                    return []
                anchor_ts = float(anchor["occurred_ts"])
                start_ts = anchor_ts - safe_window
                end_ts = min(time.time(), anchor_ts + safe_window)
                miner_key = anchor["miner_key"]
                if miner_key:
                    start_row = connection.execute(
                        """
                        SELECT occurred_ts FROM operational_events
                        WHERE miner_key = ?
                          AND event_type = 'state_transition'
                          AND previous_state = 'OK'
                          AND new_state IN ('LOW', 'OFFLINE', 'HASHBOARD')
                          AND occurred_ts <= ?
                          AND occurred_ts >= ?
                        ORDER BY occurred_ts DESC, id DESC
                        LIMIT 1
                        """,
                        (miner_key, anchor_ts, start_ts),
                    ).fetchone()
                    if start_row is not None:
                        start_ts = float(start_row["occurred_ts"])
                    end_row = connection.execute(
                        """
                        SELECT occurred_ts FROM operational_events
                        WHERE miner_key = ?
                          AND event_type = 'state_transition'
                          AND new_state = 'OK'
                          AND occurred_ts >= ?
                          AND occurred_ts <= ?
                        ORDER BY occurred_ts ASC, id ASC
                        LIMIT 1
                        """,
                        (miner_key, anchor_ts, anchor_ts + safe_window),
                    ).fetchone()
                    if end_row is not None:
                        end_ts = float(end_row["occurred_ts"])
                rows = connection.execute(
                    """
                    SELECT * FROM operational_events
                    WHERE occurred_ts >= ? AND occurred_ts <= ?
                      AND (
                        event_type IN ('state_transition', 'restart_detected')
                        OR event_type LIKE '%_reboot_%'
                        OR event_type LIKE '%_restart_%'
                      )
                    ORDER BY occurred_ts ASC, id ASC
                    LIMIT ?
                    """,
                    (start_ts, end_ts, safe_limit),
                ).fetchall()
            self._last_error = None
            return [dict(row) for row in rows]
        except (TypeError, ValueError, sqlite3.Error) as exc:
            self._report_error("list_episode_events", exc)
            return []

    def record_firmware_event(
        self,
        *,
        collected_ts: float,
        source_ts_text: str,
        source_ts_epoch: Optional[float] = None,
        source_clock: str = "unparsed",
        miner_key: str,
        miner_name: str,
        host: str,
        source_tab: str,
        source_fingerprint: str,
        category: str,
        severity: str,
        code: str,
        summary: str,
    ) -> Optional[int]:
        connection = self._connection
        if connection is None:
            return None
        try:
            safe_fingerprint = str(source_fingerprint).strip().lower()
            if len(safe_fingerprint) != 64 or any(
                character not in "0123456789abcdef" for character in safe_fingerprint
            ):
                raise ValueError("source_fingerprint must be a SHA-256 hex digest")
            safe_clock = str(source_clock).strip().lower()
            if safe_clock not in ("system_local", "fixed_utc_offset", "unparsed"):
                safe_clock = "unparsed"
            safe_source_epoch = (
                None if source_ts_epoch is None else float(source_ts_epoch)
            )
            with self._lock, connection:
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO firmware_events (
                        collected_ts, source_ts_text, source_ts_epoch, source_clock,
                        miner_key, miner_name, host,
                        source_tab, source_fingerprint, category, severity, code,
                        summary
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        float(collected_ts),
                        str(source_ts_text)[:32],
                        safe_source_epoch,
                        safe_clock,
                        str(miner_key)[:200],
                        str(miner_name)[:80],
                        str(host)[:255],
                        str(source_tab)[:20],
                        safe_fingerprint,
                        str(category)[:40],
                        str(severity)[:20],
                        str(code)[:64],
                        str(summary)[:160],
                    ),
                )
                if not cursor.rowcount and safe_source_epoch is not None:
                    connection.execute(
                        """
                        UPDATE firmware_events
                        SET source_ts_epoch = COALESCE(source_ts_epoch, ?),
                            source_clock = CASE
                                WHEN source_ts_epoch IS NULL THEN ?
                                ELSE source_clock
                            END
                        WHERE miner_key = ? AND source_tab = ? AND source_fingerprint = ?
                        """,
                        (
                            safe_source_epoch,
                            safe_clock,
                            str(miner_key)[:200],
                            str(source_tab)[:20],
                            safe_fingerprint,
                        ),
                    )
                self._last_error = None
                return int(cursor.lastrowid) if cursor.rowcount else 0
        except (TypeError, ValueError, sqlite3.Error) as exc:
            self._report_error("record_firmware_event", exc)
            return None

    def list_firmware_events(
        self,
        *,
        limit: int = 20,
        miner_key: Optional[str] = None,
        since_ts: Optional[float] = None,
        source_since_ts: Optional[float] = None,
        severities: Optional[Iterable[str]] = None,
    ) -> list[Dict[str, Any]]:
        connection = self._connection
        if connection is None:
            return []
        safe_limit = max(1, min(int(limit), 1_000))
        clauses: list[str] = []
        params: list[Any] = []
        if miner_key:
            clauses.append("miner_key = ?")
            params.append(str(miner_key))
        if since_ts is not None:
            clauses.append("collected_ts >= ?")
            params.append(float(since_ts))
        if source_since_ts is not None:
            clauses.append("source_ts_epoch >= ?")
            params.append(float(source_since_ts))
        normalized_severities = tuple(
            str(value).lower() for value in (severities or ()) if str(value).strip()
        )
        if normalized_severities:
            placeholders = ",".join("?" for _ in normalized_severities)
            clauses.append(f"severity IN ({placeholders})")
            params.extend(normalized_severities)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(safe_limit)
        try:
            with self._lock:
                rows = connection.execute(
                    f"""
                    SELECT * FROM firmware_events
                    {where}
                    ORDER BY source_ts_text DESC, collected_ts DESC, id DESC
                    LIMIT ?
                    """,
                    params,
                ).fetchall()
            self._last_error = None
            return [dict(row) for row in rows]
        except (TypeError, ValueError, sqlite3.Error) as exc:
            self._report_error("list_firmware_events", exc)
            return []

    def record_collector_run(
        self,
        *,
        started_ts: float,
        completed_ts: float,
        status: str,
        attempted: int,
        succeeded: int,
        failed: int,
        events_parsed: int,
        events_inserted: int,
        events_duplicate: int,
        events_failed: int,
        truncated_streams: int,
        summary: str,
    ) -> Optional[int]:
        connection = self._connection
        if connection is None:
            return None
        safe_status = str(status).strip().lower()
        if safe_status not in ("ok", "partial", "failed"):
            safe_status = "failed"
        try:
            with self._lock, connection:
                cursor = connection.execute(
                    """
                    INSERT INTO collector_runs (
                        started_ts, completed_ts, status, attempted, succeeded,
                        failed, events_parsed, events_inserted, events_duplicate,
                        events_failed, truncated_streams, summary
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        float(started_ts),
                        float(completed_ts),
                        safe_status,
                        max(0, int(attempted)),
                        max(0, int(succeeded)),
                        max(0, int(failed)),
                        max(0, int(events_parsed)),
                        max(0, int(events_inserted)),
                        max(0, int(events_duplicate)),
                        max(0, int(events_failed)),
                        max(0, int(truncated_streams)),
                        str(summary)[:200],
                    ),
                )
            self._last_error = None
            return int(cursor.lastrowid)
        except (TypeError, ValueError, sqlite3.Error) as exc:
            self._report_error("record_collector_run", exc)
            return None

    def list_collector_runs(self, *, limit: int = 20) -> list[Dict[str, Any]]:
        connection = self._connection
        if connection is None:
            return []
        safe_limit = max(1, min(int(limit), 1_000))
        try:
            with self._lock:
                rows = connection.execute(
                    """
                    SELECT * FROM collector_runs
                    ORDER BY completed_ts DESC, id DESC
                    LIMIT ?
                    """,
                    (safe_limit,),
                ).fetchall()
            self._last_error = None
            return [dict(row) for row in rows]
        except (TypeError, ValueError, sqlite3.Error) as exc:
            self._report_error("list_collector_runs", exc)
            return []

    def latest_collector_run(self) -> Optional[Dict[str, Any]]:
        rows = self.list_collector_runs(limit=1)
        return rows[0] if rows else None

    def list_samples(
        self,
        *,
        miner_key: Optional[str] = None,
        since_ts: Optional[float] = None,
        limit: int = 10_000,
    ) -> list[Dict[str, Any]]:
        connection = self._connection
        if connection is None:
            return []
        safe_limit = max(1, min(int(limit), 100_000))
        clauses: list[str] = []
        params: list[Any] = []
        if miner_key:
            clauses.append("miner_key = ?")
            params.append(miner_key)
        if since_ts is not None:
            clauses.append("observed_ts >= ?")
            params.append(float(since_ts))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(safe_limit)
        try:
            with self._lock:
                rows = connection.execute(
                    f"""
                    SELECT * FROM telemetry_samples
                    {where}
                    ORDER BY observed_ts DESC, id DESC
                    LIMIT ?
                    """,
                    params,
                ).fetchall()
            self._last_error = None
            return [dict(row) for row in rows]
        except (TypeError, ValueError, sqlite3.Error) as exc:
            self._report_error("list_samples", exc)
            return []

    def list_reboot_decisions(
        self,
        *,
        limit: int = 20,
        miner_key: Optional[str] = None,
        since_ts: Optional[float] = None,
    ) -> list[Dict[str, Any]]:
        connection = self._connection
        if connection is None:
            return []
        safe_limit = max(1, min(int(limit), 10_000))
        clauses: list[str] = []
        params: list[Any] = []
        if miner_key:
            clauses.append("miner_key = ?")
            params.append(miner_key)
        if since_ts is not None:
            clauses.append("evaluated_ts >= ?")
            params.append(float(since_ts))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(safe_limit)
        try:
            with self._lock:
                rows = connection.execute(
                    f"""
                    SELECT * FROM reboot_decisions
                    {where}
                    ORDER BY evaluated_ts DESC, id DESC
                    LIMIT ?
                    """,
                    params,
                ).fetchall()
            self._last_error = None
            return [dict(row) for row in rows]
        except (TypeError, ValueError, sqlite3.Error) as exc:
            self._report_error("list_reboot_decisions", exc)
            return []

    def latest_reboot_decision(
        self,
        *,
        miner_key: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        decisions = self.list_reboot_decisions(limit=1, miner_key=miner_key)
        return decisions[0] if decisions else None

    def prune(
        self,
        *,
        now_ts: float,
        sample_retention_days: int,
        event_retention_days: int,
        decision_retention_days: Optional[int] = None,
    ) -> Dict[str, int]:
        connection = self._connection
        if connection is None:
            return {
                "samples": 0,
                "events": 0,
                "decisions": 0,
                "firmware_events": 0,
                "collector_runs": 0,
            }
        sample_cutoff = float(now_ts) - max(1, int(sample_retention_days)) * 86_400
        event_cutoff = float(now_ts) - max(1, int(event_retention_days)) * 86_400
        decision_days = event_retention_days if decision_retention_days is None else decision_retention_days
        decision_cutoff = float(now_ts) - max(1, int(decision_days)) * 86_400
        try:
            with self._lock, connection:
                sample_cursor = connection.execute(
                    "DELETE FROM telemetry_samples WHERE observed_ts < ?",
                    (sample_cutoff,),
                )
                event_cursor = connection.execute(
                    "DELETE FROM operational_events WHERE occurred_ts < ?",
                    (event_cutoff,),
                )
                decision_cursor = connection.execute(
                    "DELETE FROM reboot_decisions WHERE evaluated_ts < ?",
                    (decision_cutoff,),
                )
                firmware_cursor = connection.execute(
                    "DELETE FROM firmware_events WHERE collected_ts < ?",
                    (event_cutoff,),
                )
                collector_cursor = connection.execute(
                    "DELETE FROM collector_runs WHERE completed_ts < ?",
                    (event_cutoff,),
                )
            self._last_error = None
            return {
                "samples": max(0, int(sample_cursor.rowcount)),
                "events": max(0, int(event_cursor.rowcount)),
                "decisions": max(0, int(decision_cursor.rowcount)),
                "firmware_events": max(0, int(firmware_cursor.rowcount)),
                "collector_runs": max(0, int(collector_cursor.rowcount)),
            }
        except sqlite3.Error as exc:
            self._report_error("prune", exc)
            return {
                "samples": 0,
                "events": 0,
                "decisions": 0,
                "firmware_events": 0,
                "collector_runs": 0,
            }

    def count_rows(self, table_name: str) -> int:
        if table_name not in (
            "telemetry_samples",
            "operational_events",
            "reboot_decisions",
            "firmware_events",
            "collector_runs",
        ):
            raise ValueError("Unsupported table")
        connection = self._connection
        if connection is None:
            return 0
        with self._lock:
            row = connection.execute(f"SELECT COUNT(*) AS count FROM {table_name}").fetchone()
        return int(row["count"])

    def close(self) -> None:
        connection = self._connection
        self._connection = None
        if connection is not None:
            with self._lock:
                connection.close()


def _event_label(event: Dict[str, Any]) -> str:
    event_type = str(event.get("event_type") or "event")
    classification = str(event.get("classification") or "")
    if event_type == "restart_detected":
        if classification == "unexpected":
            return "REINICIO INESPERADO"
        if classification == "expected_manual":
            return "REINICIO ESPERADO (MANUAL)"
        if classification == "expected_auto":
            return "REINICIO ESPERADO (AUTO)"
        return "REINICIO DETECTADO"
    if event_type == "state_transition":
        previous_state = event.get("previous_state") or "?"
        new_state = event.get("new_state") or "?"
        return f"{previous_state} -> {new_state}"
    if event_type == "auto_reboot_success":
        return "AUTO-REBOOT ENVIADO"
    if event_type == "auto_reboot_failed":
        return "AUTO-REBOOT FALLIDO"
    return str(event.get("summary") or event_type).upper()


def render_event_list(events: list[Dict[str, Any]]) -> str:
    if not events:
        return "No hay eventos registrados."
    lines = ["EVENTOS RECIENTES", ""]
    for event in events:
        occurred = datetime.fromtimestamp(float(event["occurred_ts"])).strftime("%d/%m %H:%M")
        miner_name = str(event.get("miner_name") or "sistema")
        lines.append(f"/e{event['id']} {occurred} {miner_name} {_event_label(event)}")
    lines.extend(["", "Manual: /event <id>"])
    return "\n".join(lines)


def render_event_detail(
    event: Optional[Dict[str, Any]],
    *,
    related_events: Optional[list[Dict[str, Any]]] = None,
) -> str:
    if not event:
        return "Evento no encontrado."
    occurred = datetime.fromtimestamp(float(event["occurred_ts"])).strftime("%d/%m/%Y %H:%M:%S")
    lines = [
        f"INCIDENTE #{event['id']}",
        "",
        f"Miner: {event.get('miner_name') or 'sistema'}",
        f"Tipo: {_event_label(event).lower()}",
    ]
    classification = event.get("classification")
    if classification:
        classification_label = {
            "unexpected": "inesperado",
            "expected_manual": "esperado manual",
            "expected_auto": "esperado automatico",
        }.get(str(classification), str(classification))
        lines.append(f"Clasificacion: {classification_label}")
    previous_elapsed = event.get("previous_elapsed")
    current_elapsed = event.get("current_elapsed")
    if previous_elapsed is not None and current_elapsed is not None:
        lines.append(f"Evidencia uptime: {previous_elapsed}s -> {current_elapsed}s")
    new_state = event.get("new_state")
    rate_ths = event.get("rate_ths")
    if new_state or rate_ths is not None:
        signal = f"{float(rate_ths):.2f} TH/s" if rate_ths is not None else "N/A"
        lines.append(f"Estado: {new_state or 'N/A'} | {signal}")
    action_source = event.get("action_source")
    if action_source:
        lines.append(f"Accion relacionada: {action_source}")
    summary = str(event.get("summary") or "").strip()
    if summary:
        lines.append(f"Resumen: {summary}")
    lines.append(f"Fecha: {occurred}")
    if related_events:
        lines.extend(["", "EPISODIO RELACIONADO"])
        for related in related_events:
            related_time = datetime.fromtimestamp(
                float(related["occurred_ts"])
            ).strftime("%H:%M:%S")
            related_miner = str(related.get("miner_name") or "sistema")
            related_line = (
                f"- {related_time} {related_miner} {_event_label(related)}"
            )
            previous_elapsed = related.get("previous_elapsed")
            current_elapsed = related.get("current_elapsed")
            if previous_elapsed is not None and current_elapsed is not None:
                related_line += f" | uptime {previous_elapsed}s -> {current_elapsed}s"
            lines.append(related_line)
    return "\n".join(lines)


def render_reboot_decision(decision: Optional[Dict[str, Any]]) -> str:
    if not decision:
        return "No hay decisiones de auto-reboot registradas."
    evaluated = datetime.fromtimestamp(float(decision["evaluated_ts"])).strftime("%d/%m/%Y %H:%M:%S")
    result = str(decision.get("result") or "unknown")
    rate = decision.get("rate_ths")
    threshold = decision.get("threshold_ths")
    rate_label = f"{float(rate):.2f} TH/s" if rate is not None else "N/A"
    threshold_label = f"{float(threshold):.2f} TH/s" if threshold is not None else "N/A"
    lines = [
        "DIAGNOSTICO AUTO-REBOOT",
        "",
        f"Miner: {decision.get('miner_name') or decision.get('miner_key')}",
        f"Resultado: {result}",
        f"Estado: {decision.get('state') or 'N/A'} | {rate_label} / umbral {threshold_label}",
    ]
    low_elapsed = decision.get("low_elapsed_seconds")
    if low_elapsed is not None:
        lines.append(f"LOW sostenido: {float(low_elapsed):.0f}s")
    active_boards = decision.get("active_boards")
    expected_boards = decision.get("expected_boards")
    if active_boards is not None or expected_boards is not None:
        lines.append(f"Boards: {active_boards if active_boards is not None else 'N/A'}/{expected_boards}")
    max_temp = decision.get("max_temp_c")
    frequency = decision.get("frequency_mhz_avg")
    hw_errors = decision.get("hw_errors_total")
    if max_temp is not None or frequency is not None or hw_errors is not None:
        lines.append(
            "Vnish: temp={temp} freq={freq} hw={hw}".format(
                temp=f"{float(max_temp):.1f}C" if max_temp is not None else "N/A",
                freq=f"{float(frequency):.1f}MHz" if frequency is not None else "N/A",
                hw=hw_errors if hw_errors is not None else "N/A",
            )
        )
    voltage = decision.get("chain_voltage_mv_avg")
    power = decision.get("chain_power_w_total")
    if voltage is not None or power is not None:
        lines.append(
            "Cadena: voltaje={voltage} consumo={power} (no es voltaje AC)".format(
                voltage=f"{float(voltage):.0f}mV" if voltage is not None else "N/A",
                power=f"{float(power):.0f}W" if power is not None else "N/A",
            )
        )
    cooldown = decision.get("cooldown_remaining_seconds")
    if cooldown is not None:
        lines.append(f"Cooldown restante: {float(cooldown):.0f}s")
    if result == "window":
        lines.append(
            f"Ventana: {decision.get('window_count', 0)} en {decision.get('window_seconds', 0)}s"
        )
    details: Dict[str, Any] = {}
    details_raw = decision.get("details_json")
    if isinstance(details_raw, str) and details_raw:
        try:
            parsed_details = json.loads(details_raw)
            if isinstance(parsed_details, dict):
                details = parsed_details
        except (TypeError, ValueError, json.JSONDecodeError):
            details = {}
    if result == "fleet_incident":
        affected = details.get("affected_miners")
        affected_labels = ", ".join(str(item) for item in affected) if isinstance(affected, list) else "N/A"
        lines.append(
            f"Flota afectada: {details.get('affected_count', 'N/A')} "
            f"(minimo {details.get('fleet_min_affected', 'N/A')})"
        )
        lines.append(f"Evidencia compartida: {affected_labels}")
        snapshot_age = details.get("fleet_snapshot_age_seconds")
        if snapshot_age is not None:
            lines.append(f"Antiguedad snapshot: {float(snapshot_age):.0f}s")
    elif result == "high_temperature":
        observed_temp = details.get("max_temp_c", max_temp)
        limit_temp = details.get("thermal_limit_c")
        observed_label = f"{float(observed_temp):.1f}C" if observed_temp is not None else "N/A"
        limit_label = f"{float(limit_temp):.1f}C" if limit_temp is not None else "N/A"
        lines.append(f"Bloqueo termico: {observed_label} / limite {limit_label}")
    elif result == "firmware_transition":
        lines.append(
            f"Cadenas en transicion: {details.get('chains_transitioning_count', 'N/A')}"
        )
        lines.append("Observacion segura: LOW debe sostenerse nuevamente tras la transicion.")
    lines.append(f"Fecha: {evaluated}")
    return "\n".join(lines)
