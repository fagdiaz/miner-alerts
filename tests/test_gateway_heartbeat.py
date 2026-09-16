import unittest
from unittest.mock import patch, MagicMock
import time

from app.network.gateway_heartbeat import GatewayHeartbeatWorker


class TestGatewayHeartbeatWorker(unittest.TestCase):
    def test_init_defaults(self):
        worker = GatewayHeartbeatWorker(host="192.168.100.1", port=80, interval_s=5.0)
        self.assertTrue(worker.gateway_online)
        self.assertIsNone(worker.last_gateway_loss_ts)
        self.assertEqual(worker.consecutive_failures, 0)
        self.assertFalse(worker.is_recently_lost(15.0))
        self.assertIsNone(worker.gateway_loss_elapsed_s())

    def test_is_recently_lost_when_offline(self):
        worker = GatewayHeartbeatWorker()
        worker.gateway_online = False
        self.assertTrue(worker.is_recently_lost(15.0))

    def test_is_recently_lost_transient_recovery(self):
        worker = GatewayHeartbeatWorker()
        worker.gateway_online = True
        now = time.monotonic()
        # Loss was 5 seconds ago (within 15s window)
        worker.last_gateway_loss_ts = now - 5.0
        self.assertTrue(worker.is_recently_lost(15.0))

        # Loss was 20 seconds ago (outside 15s window)
        worker.last_gateway_loss_ts = now - 20.0
        self.assertFalse(worker.is_recently_lost(15.0))

    def test_gateway_loss_elapsed_s(self):
        worker = GatewayHeartbeatWorker()
        worker.gateway_online = False
        now = time.monotonic()
        worker.last_gateway_loss_ts = now - 4.5
        elapsed = worker.gateway_loss_elapsed_s()
        self.assertIsNotNone(elapsed)
        self.assertAlmostEqual(elapsed, 4.5, delta=0.5)

    @patch("socket.create_connection")
    def test_try_connect_success_and_cleanup(self, mock_create):
        mock_sock = MagicMock()
        mock_create.return_value = mock_sock

        worker = GatewayHeartbeatWorker(host="10.0.0.1", port=80, connect_timeout_s=0.05)
        result = worker._try_connect("10.0.0.1", 80)

        self.assertTrue(result)
        mock_create.assert_called_once_with(("10.0.0.1", 80), timeout=0.05)
        mock_sock.close.assert_called_once()

    @patch("socket.create_connection")
    def test_try_connect_oserror_closes_socket(self, mock_create):
        mock_create.side_effect = OSError("Connection refused")

        worker = GatewayHeartbeatWorker(host="10.0.0.1", port=80)
        result = worker._try_connect("10.0.0.1", 80)

        self.assertFalse(result)

    @patch.object(GatewayHeartbeatWorker, "_try_connect")
    def test_probe_fallback(self, mock_try_connect):
        worker = GatewayHeartbeatWorker(host="10.0.0.1", port=80, fallback_port=53)
        
        # Primary fails, fallback succeeds
        mock_try_connect.side_effect = [False, True]
        self.assertTrue(worker._probe())
        self.assertEqual(mock_try_connect.call_count, 2)

        # Both fail
        mock_try_connect.reset_mock()
        mock_try_connect.side_effect = [False, False]
        self.assertFalse(worker._probe())
        self.assertEqual(mock_try_connect.call_count, 2)


if __name__ == "__main__":
    unittest.main()
