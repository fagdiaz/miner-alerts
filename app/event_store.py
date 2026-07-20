import json
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional


SCHEMA_VERSION = 1


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
                    elapsed_seconds INTEGER
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
                """
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
    ) -> bool:
        connection = self._connection
        if connection is None:
            return False
        try:
            with self._lock, connection:
                connection.execute(
                    """
                    INSERT INTO telemetry_samples (
                        observed_ts, miner_key, miner_name, host, state, responded,
                        rate_ths, threshold_ths, active_boards, expected_boards,
                        elapsed_seconds
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    ),
                )
            self._last_error = None
            return True
        except sqlite3.Error as exc:
            self._report_error("record_sample", exc)
            return False

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

    def prune(
        self,
        *,
        now_ts: float,
        sample_retention_days: int,
        event_retention_days: int,
    ) -> Dict[str, int]:
        connection = self._connection
        if connection is None:
            return {"samples": 0, "events": 0}
        sample_cutoff = float(now_ts) - max(1, int(sample_retention_days)) * 86_400
        event_cutoff = float(now_ts) - max(1, int(event_retention_days)) * 86_400
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
            self._last_error = None
            return {
                "samples": max(0, int(sample_cursor.rowcount)),
                "events": max(0, int(event_cursor.rowcount)),
            }
        except sqlite3.Error as exc:
            self._report_error("prune", exc)
            return {"samples": 0, "events": 0}

    def count_rows(self, table_name: str) -> int:
        if table_name not in ("telemetry_samples", "operational_events"):
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
        lines.append(f"#{event['id']} {occurred} {miner_name} {_event_label(event)}")
    lines.extend(["", "Detalle: /event <id>"])
    return "\n".join(lines)


def render_event_detail(event: Optional[Dict[str, Any]]) -> str:
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
    return "\n".join(lines)
