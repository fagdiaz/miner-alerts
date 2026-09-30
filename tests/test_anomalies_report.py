"""Unit tests for 24h anomalies unpacking (Option 1: 1 row per anomaly, Option 2: detailed with description).

Validates:
1. EventStore.list_anomalies_24h query logic (timestamp window, severity filtering, miner filtering).
2. render_anomalies_compact (Option 1: strictly 1 row per anomaly, mobile width <= 32).
3. render_anomalies_detailed (Option 2: full description and culprit chain, mobile width <= 32).
4. Inline keyboards and callback routing (build_anomalies_keyboard, build_diagnostic_keyboard, parse_diagnostic_callback).
5. Telegram command handling (AnomaliesCommand, EventsCommand 24h delegation, HelpCenter registration).
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from app.core.event_store import (
    EventStore,
    render_anomalies_compact,
    render_anomalies_detailed,
)
from app.telegram.commands.diagnostics import (
    AnomaliesCommand,
    EventsCommand,
)
from app.telegram.context import TelegramRequestContext
from app.telegram.fleet_cards import (
    build_anomalies_keyboard,
    build_diagnostic_keyboard,
    parse_diagnostic_callback,
)
from app.telegram.help_center import lookup_command, visible_line_width


class TestAnomaliesReport(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_anomalies.db"
        self.store = EventStore(self.db_path)
        self.now = 1750000000.0

    def tearDown(self):
        if hasattr(self, "store") and self.store:
            self.store.close()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_list_anomalies_24h_filtering(self):
        # 1. Old event (> 24h)
        self.store.record_event(
            occurred_ts=self.now - 90000.0,
            miner_key="M23|192.168.100.23:4028",
            miner_name="S19JPRO-23",
            host="192.168.100.23",
            event_type="restart_detected",
            severity="warning",
            summary="Reinicio viejo",
        )
        # 2. Info event within 24h (should be excluded)
        self.store.record_event(
            occurred_ts=self.now - 3600.0,
            miner_key="M23|192.168.100.23:4028",
            miner_name="S19JPRO-23",
            host="192.168.100.23",
            event_type="profile_change",
            severity="info",
            summary="Cambio a 2700W",
        )
        # 3. Warning event within 24h (included)
        id_warn = self.store.record_event(
            occurred_ts=self.now - 1800.0,
            miner_key="M23|192.168.100.23:4028",
            miner_name="S19JPRO-23",
            host="192.168.100.23",
            event_type="restart_detected",
            severity="warning",
            summary="Reinicio no programado",
            previous_elapsed=5000.0,
            current_elapsed=15.0,
        )
        # 4. Critical event within 24h for M25 (included)
        id_crit = self.store.record_event(
            occurred_ts=self.now - 600.0,
            miner_key="M25|192.168.100.25:4028",
            miner_name="S19JPRO-25",
            host="192.168.100.25",
            event_type="chain_health_warning",
            severity="critical",
            summary="Falla de sensor en placa 2",
            details={"culprit_chain": {"chain_id": 2, "reason": "Sensor 0 I2C CRC"}},
        )

        # Query all anomalies
        anomalies = self.store.list_anomalies_24h(now_ts=self.now)
        self.assertEqual(len(anomalies), 2)
        # Newest first
        self.assertEqual(anomalies[0]["id"], id_crit)
        self.assertEqual(anomalies[1]["id"], id_warn)

        # Query filtered by miner
        m23_anomalies = self.store.list_anomalies_24h(now_ts=self.now, miner_key="M23|192.168.100.23:4028")
        self.assertEqual(len(m23_anomalies), 1)
        self.assertEqual(m23_anomalies[0]["id"], id_warn)

    def test_render_anomalies_compact_option_1(self):
        # Empty case
        empty_text = render_anomalies_compact([], now_ts=self.now)
        self.assertIn("Cero anomalías", empty_text)

        # Populate events
        events = [
            {
                "id": 1,
                "occurred_ts": self.now - 7200.0,
                "miner_name": "S19JPRO-23",
                "miner_key": "M23",
                "event_type": "restart_detected",
                "severity": "warning",
                "summary": "Reinicio inesperado",
                "previous_elapsed": 8400,
                "current_elapsed": 12,
            },
            {
                "id": 2,
                "occurred_ts": self.now - 3600.0,
                "miner_name": "S19JPRO-25",
                "miner_key": "M25",
                "event_type": "chain_health_warning",
                "severity": "critical",
                "summary": "Sensor I2C error: Placa 2",
            },
        ]
        text = render_anomalies_compact(events, now_ts=self.now)
        lines = text.split("\n")

        # Mobile width compliance
        for line in lines:
            w = visible_line_width(line)
            self.assertLessEqual(w, 32, f"Line exceeds 32 chars: '{line}' ({w})")

        # Verify Option 1 format: exactly 1 line per anomaly starting with •
        bullet_lines = [l for l in lines if l.startswith("• ")]
        self.assertEqual(len(bullet_lines), 2)
        self.assertIn("M23", bullet_lines[0])
        self.assertIn("Reinicio", bullet_lines[0])
        self.assertIn("M25", bullet_lines[1])
        self.assertIn("Placa 2", bullet_lines[1])

        self.assertIn("Total: 2 anomalías en 24h", text)
        self.assertIn("/anomalias detalle", text)

    def test_render_anomalies_detailed_option_2(self):
        # Empty case
        empty_text = render_anomalies_detailed([], now_ts=self.now)
        self.assertIn("Cero anomalías", empty_text)

        events = [
            {
                "id": 42,
                "occurred_ts": self.now - 1200.0,
                "miner_name": "S19JPRO-25",
                "miner_key": "M25",
                "event_type": "chain_health_warning",
                "severity": "critical",
                "summary": "Alerta crítica de sensor CRC fallido",
                "details_json": json.dumps({"culprit_chain": {"chain_id": 1, "reason": "CRC error"}}),
            }
        ]
        text = render_anomalies_detailed(events, now_ts=self.now)
        lines = text.split("\n")

        # Mobile width compliance
        for line in lines:
            w = visible_line_width(line)
            self.assertLessEqual(w, 32, f"Line exceeds 32 chars: '{line}' ({w})")

        # Verify Option 2 format: contains /e42 link and detailed culprit explanation
        self.assertIn("/e42", text)
        self.assertIn("CRITICAL", text)
        self.assertIn("Alerta crítica", text)
        self.assertIn("Placa: Cadena 1", text)
        self.assertIn("Total: 1 anomalía en 24h", text)

    def test_keyboards_and_callbacks(self):
        # 1. Digest keyboard includes both options
        digest_kb = build_diagnostic_keyboard("digest")
        buttons = [btn for row in digest_kb["inline_keyboard"] for btn in row]
        callbacks = [btn["callback_data"] for btn in buttons]
        self.assertIn("diag:ref:anom_comp", callbacks)
        self.assertIn("diag:ref:anom_desc", callbacks)

        # 2. Anomalies keyboard toggle behavior
        compact_kb = build_anomalies_keyboard("compact")
        compact_btns = [btn for row in compact_kb["inline_keyboard"] for btn in row]
        self.assertTrue(any(btn["text"] == "🔍 Ver Detalle" and btn["callback_data"] == "diag:ref:anom_desc" for btn in compact_btns))

        detailed_kb = build_anomalies_keyboard("detailed")
        detailed_btns = [btn for row in detailed_kb["inline_keyboard"] for btn in row]
        self.assertTrue(any(btn["text"] == "📋 Ver 1 Fila" and btn["callback_data"] == "diag:ref:anom_comp" for btn in detailed_btns))

        # 3. Callback parsing
        cb_action1 = parse_diagnostic_callback("diag:ref:anom_comp")
        self.assertIsNotNone(cb_action1)
        self.assertEqual(cb_action1.report_type, "anom_comp")

        cb_action2 = parse_diagnostic_callback("diag:ref:anom_desc")
        self.assertIsNotNone(cb_action2)
        self.assertEqual(cb_action2.report_type, "anom_desc")

    def test_anomalies_command_dispatch(self):
        miners = [
            {"name": "S19JPRO-23", "host": "192.168.100.23", "port": 4028},
            {"name": "S19JPRO-25", "host": "192.168.100.25", "port": 4028},
        ]
        context = MagicMock(spec=TelegramRequestContext)
        context.event_store = self.store
        context.miners = miners
        context.config = {}

        # 1. Default invocation (compact 1 row)
        cmd = AnomaliesCommand()
        res = cmd.handle(context, args=[])
        self.assertTrue(res)
        context.send_message.assert_called()
        call_args = context.send_message.call_args[0]
        self.assertIn("ANOMALÍAS 24H (1 FILA)", call_args[0])

        # 2. Detailed invocation
        cmd.handle(context, args=["detalle"])
        call_args = context.send_message.call_args[0]
        self.assertIn("ANOMALÍAS 24H (DETALLE)", call_args[0])

        # 3. Delegation from /events 24h
        events_cmd = EventsCommand()
        events_cmd.handle(context, args=["24h"])
        call_args = context.send_message.call_args[0]
        self.assertIn("ANOMALÍAS 24H (1 FILA)", call_args[0])

    def test_help_center_registration(self):
        cmd_def = lookup_command("anomalias")
        self.assertIsNotNone(cmd_def)
        self.assertEqual(cmd_def.name, "anomalias")
        self.assertEqual(cmd_def.category, "diag")
        self.assertIn("anomalies", cmd_def.aliases)


if __name__ == "__main__":
    unittest.main()
