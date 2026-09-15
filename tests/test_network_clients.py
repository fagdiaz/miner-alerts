from __future__ import annotations

import json
import subprocess
import unittest
from unittest.mock import MagicMock, patch

from app.network import (
    CGMinerClient,
    HashcoreClient,
    VnishClient,
    count_active_boards,
    extract_temps,
    fw_hint,
    get_hashcore_cli_path,
    query_cgminer,
    read_pools,
    read_stats_active_boards,
    read_stats_snapshot,
    read_summary,
    read_version,
    run_hashcore_cli,
    run_hashcore_discovery,
)


class CGMinerClientTests(unittest.TestCase):
    """Unit tests for TCP 4028 CGMiner client and parser functions."""

    def test_query_cgminer_successful_json(self) -> None:
        fake_payload = json.dumps({"STATUS": [{"STATUS": "S"}], "SUMMARY": [{"GHS 5s": 95000.0, "Elapsed": 3600}]})
        fake_bytes = (fake_payload + "\x00").encode("utf-8")

        mock_sock = MagicMock()
        mock_sock.recv.side_effect = [fake_bytes, b""]

        with patch("socket.create_connection") as mock_conn:
            mock_conn.return_value.__enter__.return_value = mock_sock
            result = query_cgminer("192.168.1.100", 4028, command="summary")

        self.assertIsNotNone(result)
        self.assertIn("SUMMARY", result)

    def test_query_cgminer_connection_timeout(self) -> None:
        with patch("socket.create_connection", side_effect=TimeoutError("Connection timed out")):
            result = query_cgminer("192.168.1.100", 4028, command="summary")
        self.assertIsNone(result)

    def test_query_cgminer_invalid_json(self) -> None:
        mock_sock = MagicMock()
        mock_sock.recv.side_effect = [b"NOT_A_JSON\n", b""]

        with patch("socket.create_connection") as mock_conn:
            mock_conn.return_value.__enter__.return_value = mock_sock
            result = query_cgminer("192.168.1.100", 4028, command="summary")
        self.assertIsNone(result)

    def test_read_summary_parses_ghs_and_elapsed(self) -> None:
        fake_response = {
            "SUMMARY": [{"GHS 5s": 104500.0, "Elapsed": 7200}],
        }
        with patch("app.network.cgminer_client.query_cgminer", return_value=fake_response):
            rate_ths, elapsed, responded, raw = read_summary("192.168.1.100", 4028)

        self.assertTrue(responded)
        self.assertEqual(104.5, rate_ths)
        self.assertEqual(7200, elapsed)
        self.assertEqual(fake_response["SUMMARY"][0], raw)

    def test_read_summary_parses_mhs_fallback(self) -> None:
        fake_response = {
            "SUMMARY": [{"MHS av": 98000000.0}],
        }
        with patch("app.network.cgminer_client.query_cgminer", return_value=fake_response):
            rate_ths, elapsed, responded, _ = read_summary("192.168.1.100", 4028)

        self.assertTrue(responded)
        self.assertEqual(98.0, rate_ths)
        self.assertIsNone(elapsed)

    def test_count_active_boards_list_format(self) -> None:
        entry = {"chain_acn": [126, 126, 0]}
        self.assertEqual(2, count_active_boards(entry))

    def test_count_active_boards_legacy_keys(self) -> None:
        entry = {
            "chain_acn0": 126,
            "chain_acn1": 0,
            "chain2_asicnum": 126,
            "chain3_alive": 1,
            "chain4_status": "alive",
        }
        # 0: >0, 1: 0, 2: >0, 3: >0, 4: alive -> total 4 active
        self.assertEqual(4, count_active_boards(entry))

    def test_read_stats_snapshot(self) -> None:
        fake_response = {
            "STATS": [
                {"STATUS": "S"},
                {"chain_acn": [126, 126, 126]},
            ]
        }
        with patch("app.network.cgminer_client.query_cgminer", return_value=fake_response):
            active_boards, responded, raw = read_stats_snapshot("192.168.1.100", 4028)

        self.assertTrue(responded)
        self.assertEqual(3, active_boards)
        self.assertEqual(fake_response, raw)

    def test_read_pools_and_version(self) -> None:
        fake_pools = {"POOLS": [{"URL": "stratum+tcp://pool.braiins.com:3333"}]}
        fake_version = {"VERSION": [{"CGMiner": "4.11.1", "API": "3.7"}]}

        with patch("app.network.cgminer_client.query_cgminer", side_effect=[fake_pools, fake_version]):
            pool = read_pools("192.168.1.100", 4028)
            ver = read_version("192.168.1.100", 4028)

        self.assertEqual("stratum+tcp://pool.braiins.com:3333", pool.get("URL"))
        self.assertEqual("4.11.1", ver.get("CGMiner"))

    def test_extract_temps_and_fw_hint(self) -> None:
        stats = {"temp1": 65.5, "temp2": 68.0, "temp3": 62.0, "temp_chip": 75.0, "fan1": 4200}
        temps = extract_temps(stats)
        self.assertEqual([62.0, 65.5, 68.0], temps)

        self.assertEqual("VNISH?", fw_hint("Antminer S19 with vnish 1.2.0"))
        self.assertEqual("STOCK?", fw_hint("Bitmain official stock firmware"))
        self.assertEqual("N/A", fw_hint(""))

    def test_cgminer_client_class(self) -> None:
        client = CGMinerClient("192.168.1.50", port=4028, default_timeout=3.0)
        with patch("app.network.cgminer_client.query_cgminer", return_value={"SUMMARY": [{"GHS 5s": 100000}]}):
            rate, _, ok, _ = client.summary()
            self.assertTrue(ok)
            self.assertEqual(100.0, rate)


class HashcoreClientTests(unittest.TestCase):
    """Unit tests for Hashcore Toolkit CLI hardware client."""

    def test_get_hashcore_cli_path(self) -> None:
        cfg = {"cli_bat_path": "C:/toolkit/run.bat"}
        self.assertEqual("C:/toolkit/run.bat", get_hashcore_cli_path(cfg))

        cfg2 = {"cli_path": "C:/toolkit/run.exe"}
        self.assertEqual("C:/toolkit/run.exe", get_hashcore_cli_path(cfg2))

    def test_qa_guard_blocks_actions_when_disallowed(self) -> None:
        mock_runner = MagicMock()
        ok, msg = run_hashcore_cli(
            hashcore_cfg={"enabled": True, "cli_path": "C:/fake/cli.bat"},
            miner={"name": "S19-23", "host": "192.168.1.23"},
            action="reboot",
            config={},
            qa_mode=True,
            qa_allow_actions=False,
            runner=mock_runner,
        )
        self.assertFalse(ok)
        self.assertIn("bloqueada", msg.lower())
        mock_runner.assert_not_called()

    def test_hashcore_client_class_reboot_success(self) -> None:
        mock_runner = MagicMock()
        mock_runner.return_value = subprocess.CompletedProcess(
            args=["C:/fake/cli.bat", "reboot"],
            returncode=0,
            stdout="Reboot executed",
            stderr="",
        )

        with patch("pathlib.Path.exists", return_value=True):
            client = HashcoreClient(
                hashcore_cfg={
                    "enabled": True,
                    "cli_path": "C:/fake/cli.bat",
                    "reboot_args_template": ["reboot", "{host}"],
                },
                config={"qa_verbose": True},
                qa_mode=False,
                qa_allow_actions=True,
                runner=mock_runner,
            )
            ok, msg = client.reboot({"name": "S19-23", "host": "192.168.1.23"})

        self.assertTrue(ok)
        self.assertEqual("OK", msg)
        mock_runner.assert_called_once()
        called_cmd = mock_runner.call_args[0][0]
        self.assertIn("192.168.1.23", called_cmd)

    def test_hashcore_subprocess_timeout(self) -> None:
        mock_runner = MagicMock(side_effect=subprocess.TimeoutExpired(cmd="cli.bat", timeout=30))
        with patch("pathlib.Path.exists", return_value=True):
            ok, msg = run_hashcore_cli(
                hashcore_cfg={
                    "enabled": True,
                    "cli_path": "C:/fake/cli.bat",
                    "reboot_args_template": ["reboot", "{host}"],
                },
                miner={"name": "S19-23", "host": "192.168.1.23"},
                action="reboot",
                config={},
                qa_mode=False,
                qa_allow_actions=True,
                runner=mock_runner,
            )
        self.assertFalse(ok)
        self.assertIn("timeout", msg.lower())


class VnishClientTests(unittest.TestCase):
    """Unit tests for Vnish REST API client."""

    @patch("app.network.vnish_client.unlock_miner")
    @patch("app.network.vnish_client.lock_miner")
    def test_vnish_client_context_manager(self, mock_lock: MagicMock, mock_unlock: MagicMock) -> None:
        mock_unlock.return_value = (True, "mock_bearer_token", None)
        mock_lock.return_value = True

        client = VnishClient("192.168.1.23", "secret_pass")
        with client:
            self.assertEqual("mock_bearer_token", client.token)

        mock_unlock.assert_called_once()
        mock_lock.assert_called_once()
        self.assertIsNone(client.token)

    @patch("app.network.vnish_client.safe_set_fan_duty")
    def test_vnish_client_set_fan_duty(self, mock_set_duty: MagicMock) -> None:
        mock_set_duty.return_value = (True, None)
        client = VnishClient("192.168.1.23", "secret_pass")
        ok, err = client.set_fan_duty(75)

        self.assertTrue(ok)
        self.assertIsNone(err)
        mock_set_duty.assert_called_once_with(
            host="192.168.1.23",
            password="secret_pass",
            fan_duty=75,
            timeout=2.5,
            session=client._session,
        )

    @patch("app.network.vnish_client.safe_restart_mining")
    def test_vnish_client_restart_mining(self, mock_restart: MagicMock) -> None:
        mock_restart.return_value = (True, None)
        client = VnishClient("192.168.1.23", "secret_pass")
        ok, err = client.restart_mining()

        self.assertTrue(ok)
        self.assertIsNone(err)
        mock_restart.assert_called_once_with(
            host="192.168.1.23",
            password="secret_pass",
            timeout=2.5,
            session=client._session,
        )


if __name__ == "__main__":
    unittest.main()
