import inspect
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import app.miner_monitor as monitor
from app.event_store import EventStore
from app.vnish_logs import parse_vnish_log_text, render_firmware_events
from tools import vnish_log_collector as collector
from tools.vnish_log_collector import CollectionResult, collect_vnish_tab


SAMPLE_LOG = """[2025/09/01 00:26:20] INFO: Initializing [Antminer S19j Pro BeagleBone (1.2.6)]
[2025/09/01 00:26:34] INFO: Auto-tuning
[2025/09/08 08:51:59] INFO: Restarting (1 of 3) - Chain break detected
[2025/09/08 08:52:00] ERROR: domain voltage abnormal chain 2
[2025/09/08 08:52:01] ERROR: power lost, reboot
[2025/09/08 08:52:02] ERROR: temp too high, reboot
[2025/09/08 08:52:03] ERROR: Failed to parse pools /base.c:5813/
[2025/09/08 08:52:04] ERROR: stratum authentication failed user=private.worker
[2025/09/08 08:52:05] DEBUG: unrelated internal detail
"""


class _FakeWebSocket:
    def __init__(self, messages: list[str]) -> None:
        self.messages = iter(messages)
        self.timeout = None
        self.closed = False

    def settimeout(self, timeout: float) -> None:
        self.timeout = timeout

    def recv(self) -> str:
        try:
            return next(self.messages)
        except StopIteration as exc:
            raise TimeoutError("idle") from exc

    def close(self) -> None:
        self.closed = True


class VnishLogTests(unittest.TestCase):
    def test_parser_classifies_known_evidence_and_ignores_unknown(self) -> None:
        events = parse_vnish_log_text(SAMPLE_LOG, source_tab="status", collected_ts=10_000.0)
        by_code = {event.code: event for event in events}

        self.assertEqual("transition", by_code["firmware_initializing"].category)
        self.assertEqual("info", by_code["firmware_autotune"].severity)
        self.assertEqual("restart", by_code["watchdog_chain_restart"].category)
        self.assertEqual("warning", by_code["watchdog_chain_restart"].severity)
        self.assertEqual("critical", by_code["chain_voltage_abnormal"].severity)
        self.assertEqual("power", by_code["power_loss"].category)
        self.assertEqual("thermal", by_code["thermal_protection"].category)
        self.assertEqual("pool_network", by_code["pool_configuration_invalid"].category)
        self.assertEqual("pool_authentication_failed", by_code["pool_authentication_failed"].code)
        self.assertEqual(8, len(events))

    def test_persistable_event_never_contains_raw_or_sensitive_text(self) -> None:
        event = next(
            event
            for event in parse_vnish_log_text(
                SAMPLE_LOG, source_tab="status", collected_ts=10_000.0
            )
            if event.code == "pool_authentication_failed"
        )
        payload = event.as_dict()

        self.assertEqual(64, len(event.source_fingerprint))
        self.assertNotIn("raw", payload)
        self.assertNotIn("private.worker", str(payload))
        self.assertNotIn("/base.c", str(payload))
        self.assertLessEqual(len(event.summary), 160)

    def test_parser_is_pure_bounded_and_action_free(self) -> None:
        source = inspect.getsource(parse_vnish_log_text)
        for forbidden in (
            "socket",
            "websocket",
            "requests",
            "subprocess",
            "run_hashcore_cli",
            "send_telegram",
            "open(",
        ):
            self.assertNotIn(forbidden, source)

        payload = SAMPLE_LOG * 5_000
        events = parse_vnish_log_text(
            payload,
            source_tab="status",
            collected_ts=10_000.0,
            max_lines=100,
            max_events=25,
        )
        self.assertLessEqual(len(events), 25)

    def test_collector_is_bounded_and_uses_only_confirmed_websocket_path(self) -> None:
        fake = _FakeWebSocket([SAMPLE_LOG[:200], SAMPLE_LOG[200:]])
        calls: list[tuple[str, float]] = []

        def connect(url: str, timeout: float):
            calls.append((url, timeout))
            return fake

        result = collect_vnish_tab(
            "10.0.0.23",
            "status",
            connect_timeout=2.0,
            idle_timeout=0.5,
            max_bytes=65_536,
            connect_fn=connect,
        )

        self.assertEqual([("ws://10.0.0.23/api/v1/logs-ws/status", 2.0)], calls)
        self.assertTrue(result.ok)
        self.assertGreater(result.bytes_received, 0)
        self.assertLessEqual(result.bytes_received, 65_536)
        self.assertTrue(fake.closed)

    def test_collector_continues_after_one_unreachable_miner(self) -> None:
        config = {
            "miners": [
                {"name": "23", "host": "h23", "port": 4028},
                {"name": "24", "host": "h24", "port": 4028},
            ]
        }
        results = [
            CollectionResult(False, "h23", "status", 0, error="TimeoutError"),
            CollectionResult(True, "h24", "status", len(SAMPLE_LOG), text=SAMPLE_LOG),
        ]
        output = io.StringIO()
        with patch.object(collector, "_load_config", return_value=config), patch.object(
            collector, "collect_vnish_tab", side_effect=results
        ), redirect_stdout(output):
            exit_code = collector.main(
                ["--config", "unused.json", "--dry-run", "--tabs", "status"]
            )

        self.assertEqual(1, exit_code)
        rendered = output.getvalue()
        self.assertIn("miner=23 tab=status ok=false", rendered)
        self.assertIn("miner=24 tab=status ok=true", rendered)

    def test_firmware_command_reads_sqlite_only_and_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = EventStore(Path(temp_dir) / "firmware.db")
            try:
                for event in parse_vnish_log_text(
                    SAMPLE_LOG, source_tab="status", collected_ts=10_000.0
                ):
                    store.record_firmware_event(
                        collected_ts=event.collected_ts,
                        source_ts_text=event.source_ts_text,
                        miner_key="S19JPRO-23|h23:4028",
                        miner_name="23",
                        host="h23",
                        source_tab=event.source_tab,
                        source_fingerprint=event.source_fingerprint,
                        category=event.category,
                        severity=event.severity,
                        code=event.code,
                        summary=event.summary,
                    )
                miners = [{"name": "S19JPRO-23", "host": "h23", "port": 4028}]
                rendered = monitor.build_firmware_events_text(store, miners, "23")
                empty = monitor.build_firmware_events_text(store, miners, "99")
            finally:
                store.close()

        self.assertIn("FIRMWARE EVENTS", rendered)
        self.assertIn("watchdog_chain_restart", rendered)
        self.assertLessEqual(len(rendered.splitlines()), 14)
        self.assertEqual("Miner no encontrado.", empty)

        names = {entry["name"] for entry in monitor._COMMANDS}
        self.assertIn("firmware", names)
        worker_source = inspect.getsource(monitor.telegram_polling_worker)
        branch = worker_source.split('elif cmd_name == "firmware":', 1)[1].split(
            'elif cmd_name == "quality":', 1
        )[0]
        self.assertIn("build_firmware_events_text", branch)
        self.assertIn("is_command=True", branch)
        for forbidden in ("read_summary", "read_stats", "websocket", "run_hashcore_cli"):
            self.assertNotIn(forbidden, branch)

    def test_renderer_is_compact(self) -> None:
        rows = [
            {
                "source_ts_text": "2025/09/08 08:51:59",
                "miner_name": "23",
                "severity": "warning",
                "code": "watchdog_chain_restart",
                "summary": "Reinicio interno por corte de cadena",
            }
        ]
        rendered = render_firmware_events(rows, title="FIRMWARE EVENTS")
        self.assertIn("23 WARNING watchdog_chain_restart", rendered)
        self.assertLessEqual(len(rendered.splitlines()), 4)


if __name__ == "__main__":
    unittest.main()
