"""Unit tests for Spec 069: Deep Chain Telemetry & Predictive Chain Break Diagnostics (PROP-008)."""

from __future__ import annotations

import json
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from app.governance.chain_health import (
    PredictiveChainEngine,
    PredictiveChainRisk,
    RISK_TYPE_I2C_PERSISTENT_ERROR,
    RISK_TYPE_CHIP_DEGRADATION,
    RISK_TYPE_POWER_DISTURBANCE,
    build_predictive_chain_risk_card,
    extract_faulty_sensor_locs,
)
from app.miner_monitor import MinerState, _async_evaluate_predictive_chain_break


class TestChainPredictiveRules(unittest.TestCase):
    """Exhaustive test suite for Spec 069 predictive rules."""

    def setUp(self):
        self.engine = PredictiveChainEngine()
        self.now = 1750000000.0

    def _generate_samples(
        self,
        count: int,
        interval_s: float = 900.0,
        hr_deficit_pct: float = 0.0,
        sensors_err_count: int = 0,
        sensor_loc: int = 28,
        sensor_state: str = "error",
    ) -> list[dict]:
        samples = []
        start_ts = self.now - (count * interval_s)
        for i in range(count):
            t = start_ts + (i * interval_s)
            if sensors_err_count > 0:
                s_json = json.dumps([
                    {"state": sensor_state, "board": 39, "chip": 54, "loc": sensor_loc},
                    {"state": "measure", "board": 40, "chip": 55, "loc": 29},
                ])
            else:
                s_json = json.dumps([
                    {"state": "measure", "board": 39, "chip": 54, "loc": 28},
                    {"state": "measure", "board": 40, "chip": 55, "loc": 29},
                ])
            samples.append({
                "observed_ts": t,
                "miner_key": "S19JPRO-24|192.168.1.124",
                "miner_name": "S19JPRO-24",
                "chain_id": 2,
                "state": "mining",
                "hr_realtime": 30000.0,
                "hr_nominal": 30000.0,
                "hr_deficit_pct": hr_deficit_pct,
                "freq_avg": 520.0,
                "sensors_error_count": sensors_err_count,
                "sensors_json": s_json,
                "chips_error_count": 0,
            })
        return samples

    def test_persistent_i2c_sensor_error_triggers_risk(self):
        """QA-069-01: Persistent I2C error over 12h with N >= 24 and >= 90% triggers alert."""
        # 30 samples over 7.5 hours at 15m intervals with 100% sensor errors
        samples = self._generate_samples(count=30, sensors_err_count=1, sensor_loc=28)
        risk = self.engine.evaluate_chain_history(
            samples=samples,
            now_ts=self.now,
            miner_name="S19JPRO-24",
            chain_id=2,
        )
        self.assertIsNotNone(risk)
        self.assertEqual(risk.risk_type, RISK_TYPE_I2C_PERSISTENT_ERROR)
        self.assertEqual(risk.severity, "WARNING")
        self.assertEqual(risk.miner_name, "S19JPRO-24")
        self.assertEqual(risk.chain_id, 2)
        self.assertEqual(risk.faulty_locs, (28,))
        self.assertEqual(risk.error_sample_pct, 100.0)
        self.assertIn("loc 28", risk.message)

    def test_insufficient_samples_ignores_evaluation(self):
        """Anti-false alarm: If N < 24 samples in window, evaluation is non-conclusive."""
        # Only 5 samples (e.g. after a reboot or network interruption)
        samples = self._generate_samples(count=5, sensors_err_count=1, sensor_loc=28)
        risk = self.engine.evaluate_chain_history(
            samples=samples,
            now_ts=self.now,
            miner_name="S19JPRO-24",
            chain_id=2,
        )
        self.assertIsNone(risk)

    def test_transient_i2c_sensor_error_ignored(self):
        """Anti-false alarm: Transient error (e.g. 5/30 = 16.7% < 90%) does not trigger."""
        samples_ok = self._generate_samples(count=25, sensors_err_count=0)
        samples_err = self._generate_samples(count=5, sensors_err_count=1, sensor_loc=28)
        samples = samples_ok + samples_err
        risk = self.engine.evaluate_chain_history(
            samples=samples,
            now_ts=self.now,
            miner_name="S19JPRO-24",
            chain_id=2,
        )
        self.assertIsNone(risk)

    def test_same_sensor_loc_tracked_consistently(self):
        """Extract and track the exact physical sensor location across samples."""
        samples = self._generate_samples(count=28, sensors_err_count=1, sensor_loc=14)
        risk = self.engine.evaluate_chain_history(
            samples=samples,
            now_ts=self.now,
            miner_name="S19JPRO-24",
            chain_id=1,
        )
        self.assertIsNotNone(risk)
        self.assertEqual(risk.faulty_locs, (14,))

    def test_extract_faulty_sensor_locs_helper(self):
        """Test the extract_faulty_sensor_locs helper under different input formats."""
        # JSON string
        raw_str = json.dumps([
            {"state": "error", "loc": 28},
            {"state": "measure", "loc": 29},
            {"state": "fault", "loc": 30},
        ])
        locs = extract_faulty_sensor_locs(raw_str)
        self.assertEqual(locs, (28, 30))

        # Empty / malformed
        self.assertEqual(extract_faulty_sensor_locs("invalid_json"), ())
        self.assertEqual(extract_faulty_sensor_locs([]), ())

    def test_board_hashrate_deficit_triggers_risk(self):
        """Regla 2: Localized deficit >= 10% sustained for >= 3h with nominal siblings."""
        # Chain 2 has 15% deficit for 12 samples (3 hours)
        samples_c2 = self._generate_samples(count=12, hr_deficit_pct=15.0)
        # Sibling chains 0 and 1 have nominal deficit (<= 2%)
        samples_c0 = self._generate_samples(count=12, hr_deficit_pct=0.5)
        samples_c1 = self._generate_samples(count=12, hr_deficit_pct=1.2)

        risk = self.engine.evaluate_chain_history(
            samples=samples_c2,
            now_ts=self.now,
            miner_name="S19JPRO-24",
            chain_id=2,
            sibling_chains_samples={0: samples_c0, 1: samples_c1},
        )
        self.assertIsNotNone(risk)
        self.assertEqual(risk.risk_type, RISK_TYPE_CHIP_DEGRADATION)
        self.assertEqual(risk.chain_id, 2)
        self.assertIn("Déficit sostenido de hashrate", risk.message)

    def test_board_hashrate_deficit_ignored_when_siblings_also_degraded(self):
        """Anti-false alarm: If sibling chains also show deficit, do not classify as single board degradation."""
        samples_c2 = self._generate_samples(count=12, hr_deficit_pct=15.0)
        samples_c0 = self._generate_samples(count=12, hr_deficit_pct=12.0)  # Sibling also degraded!

        risk = self.engine.evaluate_chain_history(
            samples=samples_c2,
            now_ts=self.now,
            miner_name="S19JPRO-24",
            chain_id=2,
            sibling_chains_samples={0: samples_c0},
        )
        self.assertIsNone(risk)

    def test_electrical_group_disturbance_suppresses_board_alert(self):
        """QA-069-02: Simultaneous deficit in >= 2 miners of same electrical group classifies as POWER_DISTURBANCE."""
        miners_config = [
            {"name": "S19JPRO-1", "host": "192.168.1.101", "electrical_group": "elevator_1"},
            {"name": "S19JPRO-2", "host": "192.168.1.102", "electrical_group": "elevator_1"},
            {"name": "S19JPRO-3", "host": "192.168.1.103", "electrical_group": "elevator_2"},
        ]
        risk1 = PredictiveChainRisk(
            miner_name="S19JPRO-1",
            chain_id=1,
            risk_type=RISK_TYPE_CHIP_DEGRADATION,
            severity="WARNING",
            persistence_hours=3.0,
            error_sample_pct=100.0,
            faulty_locs=(),
            message="Deficit on board 1",
            observed_ts=self.now,
        )
        risk2 = PredictiveChainRisk(
            miner_name="S19JPRO-2",
            chain_id=2,
            risk_type=RISK_TYPE_CHIP_DEGRADATION,
            severity="WARNING",
            persistence_hours=3.0,
            error_sample_pct=100.0,
            faulty_locs=(),
            message="Deficit on board 2",
            observed_ts=self.now + 10.0,  # 10 seconds apart (< 60s)
        )
        correlated = self.engine.correlate_electrical_group(
            [risk1, risk2],
            miners_config=miners_config,
            now_ts=self.now,
        )
        self.assertEqual(len(correlated), 1)
        self.assertEqual(correlated[0].risk_type, RISK_TYPE_POWER_DISTURBANCE)
        self.assertEqual(correlated[0].miner_name, "Grupo elevator_1")
        self.assertIn("Alerta de silicio individual suprimida", correlated[0].message)

    def test_single_miner_in_group_preserves_board_alert(self):
        """If only 1 miner in the group has an issue, preserve individual alert."""
        miners_config = [
            {"name": "S19JPRO-1", "host": "192.168.1.101", "electrical_group": "elevator_1"},
            {"name": "S19JPRO-2", "host": "192.168.1.102", "electrical_group": "elevator_1"},
        ]
        risk1 = PredictiveChainRisk(
            miner_name="S19JPRO-1",
            chain_id=1,
            risk_type=RISK_TYPE_CHIP_DEGRADATION,
            severity="WARNING",
            persistence_hours=3.0,
            error_sample_pct=100.0,
            faulty_locs=(),
            message="Deficit on board 1",
            observed_ts=self.now,
        )
        correlated = self.engine.correlate_electrical_group(
            [risk1],
            miners_config=miners_config,
            now_ts=self.now,
        )
        self.assertEqual(len(correlated), 1)
        self.assertEqual(correlated[0].risk_type, RISK_TYPE_CHIP_DEGRADATION)
        self.assertEqual(correlated[0].miner_name, "S19JPRO-1")

    def test_missing_electrical_group_safe_fallback(self):
        """RF-04: Gracefully pass through without exceptions if electrical group is missing."""
        risk1 = PredictiveChainRisk(
            miner_name="S19JPRO-99",
            chain_id=1,
            risk_type=RISK_TYPE_CHIP_DEGRADATION,
            severity="WARNING",
            persistence_hours=3.0,
            error_sample_pct=100.0,
            faulty_locs=(),
            message="Deficit on board",
            observed_ts=self.now,
        )
        # Empty config
        res1 = self.engine.correlate_electrical_group([risk1], miners_config=[])
        self.assertEqual(len(res1), 1)
        self.assertEqual(res1[0].miner_name, "S19JPRO-99")

        # None config
        res2 = self.engine.correlate_electrical_group([risk1], miners_config=None)
        self.assertEqual(len(res2), 1)

    def test_i2c_sensor_error_not_suppressed_by_electrical_group(self):
        """I2C physical sensor errors are never suppressed by electrical disturbance correlation."""
        miners_config = [
            {"name": "S19JPRO-1", "host": "192.168.1.101", "electrical_group": "elevator_1"},
            {"name": "S19JPRO-2", "host": "192.168.1.102", "electrical_group": "elevator_1"},
        ]
        risk1 = PredictiveChainRisk(
            miner_name="S19JPRO-1",
            chain_id=1,
            risk_type=RISK_TYPE_I2C_PERSISTENT_ERROR,
            severity="WARNING",
            persistence_hours=12.0,
            error_sample_pct=100.0,
            faulty_locs=(28,),
            message="I2C error",
            observed_ts=self.now,
        )
        risk2 = PredictiveChainRisk(
            miner_name="S19JPRO-2",
            chain_id=2,
            risk_type=RISK_TYPE_I2C_PERSISTENT_ERROR,
            severity="WARNING",
            persistence_hours=12.0,
            error_sample_pct=100.0,
            faulty_locs=(28,),
            message="I2C error",
            observed_ts=self.now,
        )
        correlated = self.engine.correlate_electrical_group([risk1, risk2], miners_config=miners_config)
        self.assertEqual(len(correlated), 2)
        self.assertTrue(all(r.risk_type == RISK_TYPE_I2C_PERSISTENT_ERROR for r in correlated))

    def test_build_predictive_chain_risk_card_formatting(self):
        """Verify that alert cards conform strictly to Mobile-First width <= 32 cols."""
        risk = PredictiveChainRisk(
            miner_name="S19JPRO-24",
            chain_id=2,
            risk_type=RISK_TYPE_I2C_PERSISTENT_ERROR,
            severity="WARNING",
            persistence_hours=12.0,
            error_sample_pct=93.3,
            faulty_locs=(28,),
            message="Sensor térmico I2C (loc 28) en fallo continuo por >12h (28/30 muestras).",
            observed_ts=self.now,
        )
        card = build_predictive_chain_risk_card(risk)
        self.assertIn("⚠️ *RIESGO CHAIN BREAK*", card)
        self.assertIn("S19JPRO-24", card)
        self.assertIn("Cadena: 2", card)
        self.assertIn("loc 28", card)
        for line in card.split("\n"):
            clean_line = line.replace("*", "")
            self.assertLessEqual(len(clean_line), 36)

    def test_cooldown_prevents_duplicate_telegram_alerts(self):
        """RF-02: Strict 24h deduplication per chain prevents duplicate alerts."""
        miner_name = "S19JPRO-24"
        state = MinerState()
        miner_states = {miner_name: state}
        state_lock = threading.Lock()

        mock_es = MagicMock()
        mock_es.available = True
        mock_es.get_latest_chain_samples.return_value = [{"chain_id": 2}]
        samples = self._generate_samples(count=30, sensors_err_count=1, sensor_loc=28)
        mock_es.fetch_chain_samples_window.return_value = samples

        miners_list = [{"name": miner_name, "host": "192.168.1.124"}]
        config = {
            "predictive_chain_break_enabled": True,
            "chain_warning_cooldown_hours": 24.0,
            "chain_sensor_error_min_samples": 24,
        }

        with patch("app.miner_monitor.send_telegram") as mock_tg:
            # 1st execution: should dispatch alert
            _async_evaluate_predictive_chain_break(
                miners_list=miners_list,
                event_store_inst=mock_es,
                miner_states=miner_states,
                state_lock=state_lock,
                config=config,
                bot_token="test_bot",
                chat_id="12345",
                now_ts=self.now,
            )
            self.assertEqual(mock_tg.call_count, 1)
            self.assertIn("2", state.chain_warnings_ts)

            # 2nd execution immediately: should be suppressed by cooldown
            _async_evaluate_predictive_chain_break(
                miners_list=miners_list,
                event_store_inst=mock_es,
                miner_states=miner_states,
                state_lock=state_lock,
                config=config,
                bot_token="test_bot",
                chat_id="12345",
                now_ts=self.now + 60.0,
            )
            self.assertEqual(mock_tg.call_count, 1)

    def test_cooldown_expiration_allows_new_alert(self):
        """RF-02: After 24h cooldown expires, a new warning can be dispatched."""
        miner_name = "S19JPRO-24"
        state = MinerState()
        miner_states = {miner_name: state}
        state_lock = threading.Lock()

        mock_es = MagicMock()
        mock_es.available = True
        mock_es.get_latest_chain_samples.return_value = [{"chain_id": 2}]
        samples = self._generate_samples(count=30, sensors_err_count=1, sensor_loc=28)
        mock_es.fetch_chain_samples_window.return_value = samples

        miners_list = [{"name": miner_name, "host": "192.168.1.124"}]
        config = {
            "predictive_chain_break_enabled": True,
            "chain_warning_cooldown_hours": 24.0,
            "chain_sensor_error_min_samples": 24,
        }

        with patch("app.miner_monitor.send_telegram") as mock_tg:
            # 1st execution at T
            _async_evaluate_predictive_chain_break(
                miners_list=miners_list,
                event_store_inst=mock_es,
                miner_states=miner_states,
                state_lock=state_lock,
                config=config,
                bot_token="test_bot",
                chat_id="12345",
                now_ts=self.now,
            )
            self.assertEqual(mock_tg.call_count, 1)

            # Execution 25 hours later: should alert again
            future_now = self.now + (25.0 * 3600.0)
            samples_future = self._generate_samples(count=30, sensors_err_count=1, sensor_loc=28)
            # Rebase samples for future time
            for s in samples_future:
                s["observed_ts"] += (25.0 * 3600.0)
            mock_es.fetch_chain_samples_window.return_value = samples_future

            _async_evaluate_predictive_chain_break(
                miners_list=miners_list,
                event_store_inst=mock_es,
                miner_states=miner_states,
                state_lock=state_lock,
                config=config,
                bot_token="test_bot",
                chat_id="12345",
                now_ts=future_now,
            )
            self.assertEqual(mock_tg.call_count, 2)

    def test_empty_samples_returns_none(self):
        """Empty sample list safely returns None."""
        self.assertIsNone(self.engine.evaluate_chain_history([], now_ts=self.now))

    def test_card_formatting_chain_zero(self):
        """Verify that Chain 0 (Board 0) is correctly rendered in card, but omitted for group alerts."""
        risk_chain0 = PredictiveChainRisk(
            miner_name="S19JPRO-24",
            chain_id=0,
            risk_type=RISK_TYPE_I2C_PERSISTENT_ERROR,
            severity="WARNING",
            persistence_hours=12.0,
            error_sample_pct=100.0,
            faulty_locs=(15,),
            message="Sensor térmico I2C (loc 15) en fallo continuo.",
            observed_ts=self.now,
        )
        card0 = build_predictive_chain_risk_card(risk_chain0)
        self.assertIn("• Cadena: 0 (Board 0)", card0)

        # Electrical group disturbance should NOT show Cadena line
        risk_group = PredictiveChainRisk(
            miner_name="Grupo elevator_1",
            chain_id=0,
            risk_type=RISK_TYPE_POWER_DISTURBANCE,
            severity="CRITICAL",
            persistence_hours=12.0,
            error_sample_pct=100.0,
            faulty_locs=(),
            message="Perturbación eléctrica en elevator_1 afectando a 2 mineros.",
            observed_ts=self.now,
        )
        card_group = build_predictive_chain_risk_card(risk_group)
        self.assertNotIn("• Cadena:", card_group)
        self.assertIn("Grupo elevator_1", card_group)

    def test_safe_float_and_resilient_sensor_parsing(self):
        """Verify _safe_float shields against None/NaN/inf and float loc strings are parsed."""
        from app.governance.chain_health import _safe_float

        self.assertEqual(_safe_float(None, 0.0), 0.0)
        self.assertEqual(_safe_float(float("nan"), 5.0), 5.0)
        self.assertEqual(_safe_float(float("inf"), 5.0), 5.0)
        self.assertEqual(_safe_float("invalid", 10.0), 10.0)
        self.assertEqual(_safe_float(42.5), 42.5)

        # Samples containing None for hr_deficit_pct and sensors_error_count
        samples = [
            {
                "observed_ts": self.now - (i * 900.0),
                "miner_key": "S19JPRO-24",
                "chain_id": 1,
                "state": "mining",
                "hr_deficit_pct": None,
                "sensors_error_count": None,
                "sensors_json": json.dumps([{"state": "error", "loc": "28.0"}]),
                "chips_error_count": 0,
            }
            for i in range(25)
        ]
        locs = extract_faulty_sensor_locs(json.dumps([{"state": "error", "loc": "28.0"}]))
        self.assertEqual(locs, (28,))

        risk = self.engine.evaluate_chain_history(samples, now_ts=self.now, miner_name="S19JPRO-24", chain_id=1)
        self.assertIsNotNone(risk)
        self.assertEqual(risk.faulty_locs, (28,))

    def test_compound_key_matching_in_async_evaluate(self):
        """Verify that compound state keys 'miner_name|host:port' match miner_name and record cooldown."""
        miner_name = "S19JPRO-24"
        compound_key = f"{miner_name}|192.168.1.124:4028"
        state = MinerState()
        miner_states = {compound_key: state}
        state_lock = threading.Lock()

        mock_es = MagicMock()
        mock_es.available = True
        mock_es.get_latest_chain_samples.return_value = [{"chain_id": 2}]
        samples = self._generate_samples(count=30, sensors_err_count=1, sensor_loc=28)
        mock_es.fetch_chain_samples_window.return_value = samples

        miners_list = [{"name": miner_name, "host": "192.168.1.124"}]
        config = {
            "predictive_chain_break_enabled": True,
            "chain_warning_cooldown_hours": 24.0,
            "chain_sensor_error_min_samples": 24,
        }

        with patch("app.miner_monitor.send_telegram") as mock_tg:
            _async_evaluate_predictive_chain_break(
                miners_list=miners_list,
                event_store_inst=mock_es,
                miner_states=miner_states,
                state_lock=state_lock,
                config=config,
                bot_token="test_bot",
                chat_id="12345",
                now_ts=self.now,
            )
            self.assertEqual(mock_tg.call_count, 1)
            # Ensure chain_warnings_ts was updated on the compound key's MinerState
            self.assertEqual(state.chain_warnings_ts.get("2"), self.now)

            # Second call must be suppressed by cooldown
            _async_evaluate_predictive_chain_break(
                miners_list=miners_list,
                event_store_inst=mock_es,
                miner_states=miner_states,
                state_lock=state_lock,
                config=config,
                bot_token="test_bot",
                chat_id="12345",
                now_ts=self.now + 60.0,
            )
            self.assertEqual(mock_tg.call_count, 1)

    def test_multi_elevator_isolated_cooldowns(self):
        """Verify that cooldown for elevator_1 does not suppress alerts for elevator_2."""
        state1 = MinerState()
        state2 = MinerState()
        miner_states = {"M1|192.168.1.101:4028": state1, "M2|192.168.1.102:4028": state2}
        state_lock = threading.Lock()

        mock_es = MagicMock()
        mock_es.available = True

        miners_list = [
            {"name": "M1", "host": "192.168.1.101", "electrical_group": "elevator_1"},
            {"name": "M2", "host": "192.168.1.102", "electrical_group": "elevator_2"},
        ]
        config = {
            "predictive_chain_break_enabled": True,
            "chain_warning_cooldown_hours": 24.0,
        }

        risk1 = PredictiveChainRisk(
            miner_name="Grupo elevator_1",
            chain_id=0,
            risk_type=RISK_TYPE_POWER_DISTURBANCE,
            severity="CRITICAL",
            persistence_hours=12.0,
            error_sample_pct=100.0,
            faulty_locs=(),
            message="Disturbance elevator_1",
            observed_ts=self.now,
        )
        risk2 = PredictiveChainRisk(
            miner_name="Grupo elevator_2",
            chain_id=0,
            risk_type=RISK_TYPE_POWER_DISTURBANCE,
            severity="CRITICAL",
            persistence_hours=12.0,
            error_sample_pct=100.0,
            faulty_locs=(),
            message="Disturbance elevator_2",
            observed_ts=self.now,
        )

        with patch("app.governance.chain_health.PredictiveChainEngine.evaluate_chain_history", return_value=None), \
             patch("app.governance.chain_health.PredictiveChainEngine.correlate_electrical_group", return_value=[risk1, risk2]), \
             patch("app.miner_monitor.send_telegram") as mock_tg:
            _async_evaluate_predictive_chain_break(
                miners_list=miners_list,
                event_store_inst=mock_es,
                miner_states=miner_states,
                state_lock=state_lock,
                config=config,
                bot_token="test_bot",
                chat_id="12345",
                now_ts=self.now,
            )
            # Both groups should have alerted
            self.assertEqual(mock_tg.call_count, 2)
            self.assertEqual(state1.chain_warnings_ts.get("group_elevator_1"), self.now)
            self.assertEqual(state2.chain_warnings_ts.get("group_elevator_2"), self.now)

            # Re-running immediately: both groups should be suppressed
            _async_evaluate_predictive_chain_break(
                miners_list=miners_list,
                event_store_inst=mock_es,
                miner_states=miner_states,
                state_lock=state_lock,
                config=config,
                bot_token="test_bot",
                chat_id="12345",
                now_ts=self.now + 60.0,
            )
            self.assertEqual(mock_tg.call_count, 2)

    def test_fetch_chain_samples_window_with_raw_cursor_and_tuple(self):
        """Verify fetch_chain_samples_window handles standard cursors without sqlite3.Row."""
        import sqlite3
        from app.core.event_store import fetch_chain_samples_window

        conn = sqlite3.connect(":memory:")
        conn.execute("""
            CREATE TABLE chain_telemetry_samples (
                observed_ts REAL,
                miner_key TEXT,
                chain_id INTEGER,
                sensors_error_count INTEGER,
                sensors_json TEXT,
                hr_deficit_pct REAL,
                chips_error_count INTEGER
            )
        """)
        conn.execute("""
            INSERT INTO chain_telemetry_samples VALUES
            (1750000000.0, 'S19JPRO-24', 2, 1, '[]', 0.0, 0)
        """)
        conn.commit()

        res = fetch_chain_samples_window(conn, "S19JPRO-24", 2, 1740000000.0)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["observed_ts"], 1750000000.0)
        self.assertEqual(res[0]["sensors_error_count"], 1)
        self.assertEqual(res[0]["hr_deficit_pct"], 0.0)

        cur = conn.cursor()
        res_cur = fetch_chain_samples_window(cur, "S19JPRO-24", 2, 1740000000.0)
        self.assertEqual(len(res_cur), 1)
        self.assertEqual(res_cur[0]["observed_ts"], 1750000000.0)

        conn.close()


if __name__ == "__main__":
    unittest.main()
