import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

from app.event_store import (
    EventStore,
    render_event_detail,
    render_event_list,
    render_reboot_decision,
)


class EventStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "miner_alerts.db"
        self.errors: list[str] = []
        self.store = EventStore(self.db_path, on_error=self.errors.append)

    def tearDown(self) -> None:
        self.store.close()
        self.temp_dir.cleanup()

    def test_initializes_schema_and_persists_after_reopen(self) -> None:
        event_id = self.store.record_event(
            occurred_ts=1_000.0,
            miner_key="S19JPRO-23|10.0.0.23:4028",
            miner_name="23",
            host="10.0.0.23",
            event_type="restart_detected",
            severity="critical",
            classification="unexpected",
            summary="Reinicio inesperado",
            previous_elapsed=80_000,
            current_elapsed=120,
        )
        self.assertIsNotNone(event_id)
        self.store.close()

        reopened = EventStore(self.db_path, on_error=self.errors.append)
        try:
            event = reopened.get_event(int(event_id or 0))
            self.assertIsNotNone(event)
            self.assertEqual("unexpected", event["classification"])
            self.assertEqual(80_000, event["previous_elapsed"])
        finally:
            reopened.close()

    def test_records_and_filters_samples(self) -> None:
        ok = self.store.record_sample(
            observed_ts=2_000.0,
            miner_key="m23",
            miner_name="23",
            host="10.0.0.23",
            state="OK",
            responded=True,
            rate_ths=99.2,
            threshold_ths=60.0,
            active_boards=3,
            expected_boards=3,
            elapsed_seconds=50_000,
        )

        self.assertTrue(ok)
        self.assertEqual(1, self.store.count_rows("telemetry_samples"))

    def test_records_normalized_telemetry_and_reboot_decision(self) -> None:
        telemetry = {
            "max_temp_c": 78.0,
            "chain_voltage_mv_avg": 12825.0,
            "chain_power_w_total": 2698.0,
            "frequency_mhz_avg": 515.976,
            "hw_errors_total": 22,
            "fan_rpm_max": 6000,
            "fan_pwm_percent": 100.0,
            "diagnostic_flags": ["hw_errors_present"],
        }
        self.store.record_sample(
            observed_ts=2_000.0,
            miner_key="m23",
            miner_name="23",
            host="h23",
            state="LOW",
            responded=True,
            rate_ths=50.0,
            threshold_ths=60.0,
            active_boards=3,
            expected_boards=3,
            elapsed_seconds=50_000,
            telemetry=telemetry,
        )
        decision_id = self.store.record_reboot_decision(
            evaluated_ts=2_001.0,
            miner_key="m23",
            miner_name="23",
            host="h23",
            result="cooldown",
            state="LOW",
            responded=True,
            rate_ths=50.0,
            threshold_ths=60.0,
            low_elapsed_seconds=700.0,
            active_boards=3,
            expected_boards=3,
            startup_guard_active=False,
            qa_mode=False,
            cooldown_remaining_seconds=120.0,
            window_count=1,
            window_seconds=21_600,
            telemetry=telemetry,
        )

        samples = self.store.list_samples(miner_key="m23")
        decision = self.store.latest_reboot_decision(miner_key="m23")

        self.assertIsNotNone(decision_id)
        self.assertEqual(12825.0, samples[0]["chain_voltage_mv_avg"])
        self.assertEqual("cooldown", decision["result"])
        self.assertEqual(120.0, decision["cooldown_remaining_seconds"])
        rendered = render_reboot_decision(decision)
        self.assertIn("Resultado: cooldown", rendered)
        self.assertIn("no es voltaje AC", rendered)

    def test_renders_fleet_and_thermal_interlock_evidence(self) -> None:
        base = {
            "evaluated_ts": 2_001.0,
            "miner_key": "m23",
            "miner_name": "23",
            "result": "fleet_incident",
            "state": "LOW",
            "rate_ths": 50.0,
            "threshold_ths": 60.0,
            "low_elapsed_seconds": 700.0,
            "active_boards": 3,
            "expected_boards": 3,
            "max_temp_c": 78.0,
            "details_json": (
                '{"affected_count":2,"affected_miners":["m23","m24"],'
                '"fleet_min_affected":2,"fleet_snapshot_age_seconds":31.0}'
            ),
        }

        fleet_rendered = render_reboot_decision(base)
        self.assertIn("Resultado: fleet_incident", fleet_rendered)
        self.assertIn("Flota afectada: 2 (minimo 2)", fleet_rendered)
        self.assertIn("Evidencia compartida: m23, m24", fleet_rendered)
        self.assertIn("Antiguedad snapshot: 31s", fleet_rendered)

        thermal = dict(base)
        thermal["result"] = "high_temperature"
        thermal["max_temp_c"] = 86.5
        thermal["details_json"] = '{"max_temp_c":86.5,"thermal_limit_c":85.0}'
        thermal_rendered = render_reboot_decision(thermal)
        self.assertIn("Resultado: high_temperature", thermal_rendered)
        self.assertIn("Bloqueo termico: 86.5C / limite 85.0C", thermal_rendered)

    def test_migrates_schema_v1_without_losing_rows(self) -> None:
        legacy_path = Path(self.temp_dir.name) / "legacy.db"
        connection = sqlite3.connect(legacy_path)
        connection.executescript(
            """
            CREATE TABLE telemetry_samples (
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
            INSERT INTO telemetry_samples (
                observed_ts, miner_key, miner_name, host, state, responded,
                rate_ths, threshold_ths, active_boards, expected_boards, elapsed_seconds
            ) VALUES (1000, 'm23', '23', 'h23', 'OK', 1, 99, 60, 3, 3, 50000);
            PRAGMA user_version=1;
            """
        )
        connection.commit()
        connection.close()

        migrated = EventStore(legacy_path, on_error=self.errors.append)
        try:
            self.assertTrue(migrated.available)
            self.assertEqual(2, migrated.schema_version)
            self.assertEqual(1, migrated.count_rows("telemetry_samples"))
            sample = migrated.list_samples(limit=1)[0]
            self.assertIn("chain_voltage_mv_avg", sample)
            self.assertIsNone(sample["chain_voltage_mv_avg"])
            self.assertEqual(0, migrated.count_rows("reboot_decisions"))
        finally:
            migrated.close()

    def test_list_events_is_newest_first_and_filterable(self) -> None:
        self.store.record_event(
            occurred_ts=1_000.0,
            miner_key="m23",
            miner_name="23",
            host="h23",
            event_type="state_transition",
            severity="warning",
            summary="OK -> LOW",
        )
        second_id = self.store.record_event(
            occurred_ts=2_000.0,
            miner_key="m24",
            miner_name="24",
            host="h24",
            event_type="restart_detected",
            severity="critical",
            classification="unexpected",
            summary="Reinicio inesperado",
        )

        all_events = self.store.list_events(limit=8)
        filtered = self.store.list_events(limit=8, miner_key="m23")

        self.assertEqual(second_id, all_events[0]["id"])
        self.assertEqual(["m23"], [event["miner_key"] for event in filtered])

    def test_retention_prunes_only_expired_rows(self) -> None:
        day = 86_400
        now = 100 * day
        for observed_ts in (now - 91 * day, now - 89 * day):
            self.store.record_sample(
                observed_ts=float(observed_ts),
                miner_key="m23",
                miner_name="23",
                host="h23",
                state="OK",
                responded=True,
                rate_ths=100.0,
                threshold_ths=60.0,
                active_boards=3,
                expected_boards=3,
                elapsed_seconds=10_000,
            )
        for occurred_ts in (now - 366 * day, now - 364 * day):
            self.store.record_event(
                occurred_ts=float(occurred_ts),
                miner_key="m23",
                miner_name="23",
                host="h23",
                event_type="state_transition",
                severity="info",
                summary="event",
            )

        deleted = self.store.prune(
            now_ts=float(now),
            sample_retention_days=90,
            event_retention_days=365,
        )

        self.assertEqual({"samples": 1, "events": 1, "decisions": 0}, deleted)
        self.assertEqual(1, self.store.count_rows("telemetry_samples"))
        self.assertEqual(1, self.store.count_rows("operational_events"))

    def test_threaded_writes_are_serialized(self) -> None:
        def write_event(index: int) -> None:
            self.store.record_event(
                occurred_ts=float(index),
                miner_key="m23",
                miner_name="23",
                host="h23",
                event_type="state_transition",
                severity="info",
                summary=f"event {index}",
            )

        threads = [threading.Thread(target=write_event, args=(index,)) for index in range(20)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(20, self.store.count_rows("operational_events"))
        self.assertEqual([], self.errors)

    def test_failed_store_is_safe(self) -> None:
        failed = EventStore(Path(self.temp_dir.name), on_error=self.errors.append)
        try:
            self.assertFalse(failed.available)
            self.assertIsNone(
                failed.record_event(
                    occurred_ts=1.0,
                    event_type="state_transition",
                    severity="info",
                    summary="ignored",
                )
            )
            self.assertTrue(self.errors)
        finally:
            failed.close()

    def test_renderers_are_compact_and_deterministic(self) -> None:
        event_id = self.store.record_event(
            occurred_ts=1_720_000_000.0,
            miner_key="m23",
            miner_name="23",
            host="h23",
            event_type="restart_detected",
            severity="critical",
            classification="unexpected",
            summary="Reinicio inesperado",
            previous_elapsed=80_000,
            current_elapsed=120,
            new_state="OK",
            rate_ths=99.2,
            threshold_ths=60.0,
        )
        event = self.store.get_event(int(event_id or 0))

        listing = render_event_list([event] if event else [])
        detail = render_event_detail(event)

        self.assertIn(f"#{event_id}", listing)
        self.assertIn("REINICIO INESPERADO", listing)
        self.assertIn("INCIDENTE", detail)
        self.assertIn("80000s -> 120s", detail)
        self.assertIn("Clasificacion: inesperado", detail)


if __name__ == "__main__":
    unittest.main()
