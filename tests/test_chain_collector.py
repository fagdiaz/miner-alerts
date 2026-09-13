"""Unit tests for Vnish Hashboard Chain Telemetry and Collector (Spec 054)."""

import json
import unittest
from unittest.mock import MagicMock, patch

import requests

from app.vnish.chains import ChainSensor, ChainTelemetry
from app.vnish.chain_collector import fetch_fleet_chains, fetch_miner_chains


class ChainSensorTests(unittest.TestCase):
    def test_healthy_sensor(self):
        s = ChainSensor(state="measure", board_temp=47.0, chip_temp=62.0, loc=28)
        self.assertTrue(s.is_healthy)
        d = s.to_dict()
        self.assertEqual(d["state"], "measure")
        self.assertEqual(d["board"], 47.0)
        self.assertEqual(d["chip"], 62.0)
        self.assertEqual(d["loc"], 28)

        reconstructed = ChainSensor.from_dict(d)
        self.assertEqual(reconstructed.state, "measure")
        self.assertEqual(reconstructed.board_temp, 47.0)
        self.assertEqual(reconstructed.chip_temp, 62.0)
        self.assertEqual(reconstructed.loc, 28)

    def test_error_sensor(self):
        s = ChainSensor(state="error", board_temp=39.0, chip_temp=54.0, loc=28)
        self.assertFalse(s.is_healthy)
        self.assertEqual(s.loc, 28)

    def test_sensor_with_missing_fields(self):
        s = ChainSensor.from_dict({})
        self.assertEqual(s.state, "unknown")
        self.assertIsNone(s.board_temp)
        self.assertIsNone(s.chip_temp)
        self.assertIsNone(s.loc)
        self.assertFalse(s.is_healthy)


class ChainTelemetryTests(unittest.TestCase):
    def setUp(self):
        self.healthy_api_dict = {
            "id": 1,
            "status": {"state": "mining"},
            "hr_realtime": 33000.0,
            "hr_nominal": 33000.0,
            "freq": 520.0,
            "sensors": [
                {"state": "measure", "board": 47, "chip": 62, "loc": 28},
                {"state": "measure", "board": 38, "chip": 53, "loc": 99},
                {"state": "measure", "board": 57, "chip": 72, "loc": 66},
                {"state": "measure", "board": 56, "chip": 71, "loc": 61},
            ],
            "chips": [
                {"id": 1, "hr": 260.0, "freq": 515, "errs": 0, "throttled": False},
                {"id": 2, "hr": 260.0, "freq": 515, "errs": 0, "throttled": False},
                {"id": 3, "hr": 260.0, "freq": 515, "errs": 0, "throttled": False},
            ],
        }

        self.faulty_api_dict = {
            "id": 2,
            "status": {"state": "mining"},
            "hr_realtime": 28000.0,
            "hr_nominal": 33000.0,
            "freq": 510.0,
            "sensors": [
                {"state": "error", "board": 39, "chip": 54, "loc": 28},
                {"state": "measure", "board": 40, "chip": 55, "loc": 99},
            ],
            "chips": [
                {"id": 1, "hr": 220.0, "freq": 510, "errs": 5, "throttled": True},
                {"id": 2, "hr": 250.0, "freq": 510, "errs": 0, "throttled": False},
            ],
        }

    def test_from_api_dict_healthy(self):
        t = ChainTelemetry.from_api_dict(self.healthy_api_dict)
        self.assertEqual(t.chain_id, 1)
        self.assertEqual(t.state, "mining")
        self.assertEqual(t.hr_realtime_mhs, 33000.0)
        self.assertEqual(t.hr_nominal_mhs, 33000.0)
        self.assertEqual(t.hr_deficit_pct, 0.0)
        self.assertEqual(len(t.sensors), 4)
        self.assertEqual(t.sensors_error_count, 0)
        self.assertEqual(t.chips_total, 3)
        self.assertEqual(t.chips_error_count, 0)
        self.assertEqual(t.chips_throttled_count, 0)
        self.assertEqual(t.chips_hw_errors_total, 0)
        self.assertEqual(t.max_chip_temp, 72.0)
        self.assertEqual(t.max_board_temp, 57.0)
        self.assertTrue(t.is_healthy)

    def test_from_api_dict_faulty(self):
        t = ChainTelemetry.from_api_dict(self.faulty_api_dict)
        self.assertEqual(t.chain_id, 2)
        self.assertEqual(t.sensors_error_count, 1)
        self.assertEqual(t.chips_total, 2)
        self.assertEqual(t.chips_error_count, 1)
        self.assertEqual(t.chips_throttled_count, 1)
        self.assertEqual(t.chips_hw_errors_total, 5)
        self.assertAlmostEqual(t.hr_deficit_pct, 15.15, places=1)
        self.assertFalse(t.is_healthy)

    def test_to_dict_and_sensors_json(self):
        t = ChainTelemetry.from_api_dict(self.healthy_api_dict)
        d = t.to_dict()
        self.assertEqual(d["chain_id"], 1)
        self.assertEqual(d["sensors_error_count"], 0)
        self.assertEqual(d["max_chip_temp"], 72.0)

        s_json = t.sensors_json()
        parsed = json.loads(s_json)
        self.assertEqual(len(parsed), 4)
        self.assertEqual(parsed[0]["loc"], 28)


class ChainCollectorClientTests(unittest.TestCase):
    @patch("requests.get")
    def test_fetch_miner_chains_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {
                "id": 1,
                "status": {"state": "mining"},
                "hr_realtime": 33000.0,
                "hr_nominal": 33000.0,
                "freq": 520.0,
                "sensors": [{"state": "measure", "board": 45, "chip": 60, "loc": 28}],
                "chips": [],
            }
        ]
        mock_get.return_value = mock_resp

        ok, chains, err = fetch_miner_chains("192.168.100.23", token="test-token")
        self.assertTrue(ok)
        self.assertIsNone(err)
        self.assertEqual(len(chains), 1)
        self.assertEqual(chains[0].chain_id, 1)
        self.assertEqual(chains[0].sensors[0].loc, 28)

    @patch("requests.get")
    def test_fetch_miner_chains_unauthorized(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_get.return_value = mock_resp

        ok, chains, err = fetch_miner_chains("192.168.100.23")
        self.assertFalse(ok)
        self.assertEqual(chains, [])
        self.assertEqual(err, "unauthorized_invalid_token")

    @patch("requests.get")
    def test_fetch_miner_chains_timeout(self, mock_get):
        mock_get.side_effect = requests.exceptions.Timeout("Connection timed out")

        ok, chains, err = fetch_miner_chains("192.168.100.23")
        self.assertFalse(ok)
        self.assertEqual(chains, [])
        self.assertEqual(err, "connection_timeout")

    @patch("requests.get")
    def test_fetch_miner_chains_connection_error(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError("Offline")

        ok, chains, err = fetch_miner_chains("192.168.100.23")
        self.assertFalse(ok)
        self.assertEqual(chains, [])
        self.assertEqual(err, "connection_refused_or_offline")

    @patch("requests.get")
    def test_fetch_miner_chains_invalid_format(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"error": "not a list"}
        mock_get.return_value = mock_resp

        ok, chains, err = fetch_miner_chains("192.168.100.23")
        self.assertFalse(ok)
        self.assertEqual(chains, [])
        self.assertIn("invalid_response_format", err)

    @patch("app.vnish.chain_collector.fetch_miner_chains")
    def test_fetch_fleet_chains(self, mock_fetch):
        mock_fetch.side_effect = lambda host, **kwargs: (
            True,
            [ChainTelemetry(chain_id=1, state="mining", hr_realtime_mhs=33000, hr_nominal_mhs=33000, freq_mhz_avg=500)],
            None,
        )

        miners_map = {
            "m23": "192.168.100.23",
            "m24": "192.168.100.24",
        }
        results = fetch_fleet_chains(miners_map)
        self.assertEqual(len(results), 2)
        self.assertTrue(results["m23"][0])
        self.assertTrue(results["m24"][0])
        self.assertEqual(len(results["m23"][1]), 1)


if __name__ == "__main__":
    unittest.main()
