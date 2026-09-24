import unittest
from unittest.mock import MagicMock, patch
import requests

from app.vnish.client import (
    DEFAULT_HTTP_TIMEOUT,
    get_miner_status,
    parse_miner_status_flags,
    restart_mining,
    safe_restart_mining,
)


class TestTwoTierRecoveryClient(unittest.TestCase):
    """Spec 056 - Iteration 1: Unit tests for Vnish status flags and mining restart client."""

    def test_parse_miner_status_flags_normal(self) -> None:
        raw = {
            "miner_state": "mining",
            "miner_state_time": 42758,
            "find_miner": False,
            "restart_required": False,
            "reboot_required": False,
            "unlocked": False,
        }
        st, restart_req, reboot_req = parse_miner_status_flags(raw)
        self.assertEqual(st, "mining")
        self.assertFalse(restart_req)
        self.assertFalse(reboot_req)

    def test_parse_miner_status_flags_restart_required(self) -> None:
        raw = {
            "miner_state": "stopped",
            "miner_state_time": 120,
            "restart_required": True,
            "reboot_required": False,
        }
        st, restart_req, reboot_req = parse_miner_status_flags(raw)
        self.assertEqual(st, "stopped")
        self.assertTrue(restart_req)
        self.assertFalse(reboot_req)

    def test_parse_miner_status_flags_reboot_required(self) -> None:
        raw = {
            "miner_state": "stopped",
            "miner_state_time": 300,
            "restart_required": False,
            "reboot_required": True,
        }
        st, restart_req, reboot_req = parse_miner_status_flags(raw)
        self.assertEqual(st, "stopped")
        self.assertFalse(restart_req)
        self.assertTrue(reboot_req)

    def test_parse_miner_status_flags_invalid_or_none(self) -> None:
        self.assertEqual(parse_miner_status_flags(None), ("", False, False))
        self.assertEqual(parse_miner_status_flags({}), ("", False, False))
        self.assertEqual(parse_miner_status_flags("invalid"), ("", False, False))

    @patch("requests.post")
    def test_restart_mining_success_first_endpoint(self, mock_post: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        ok, err = restart_mining("192.168.100.23", "test_token")
        self.assertTrue(ok)
        self.assertIsNone(err)
        mock_post.assert_called_once_with(
            "http://192.168.100.23/api/v1/mining/restart",
            headers={"Authorization": "Bearer test_token"},
            timeout=DEFAULT_HTTP_TIMEOUT,
        )

    @patch("requests.post")
    def test_restart_mining_fallback_to_start(self, mock_post: MagicMock) -> None:
        resp_fail = MagicMock()
        resp_fail.status_code = 404
        resp_ok = MagicMock()
        resp_ok.status_code = 200
        mock_post.side_effect = [resp_fail, resp_ok]

        ok, err = restart_mining("192.168.100.23", "test_token")
        self.assertTrue(ok)
        self.assertIsNone(err)
        self.assertEqual(mock_post.call_count, 2)

    @patch("requests.post")
    def test_restart_mining_timeout(self, mock_post: MagicMock) -> None:
        mock_post.side_effect = requests.exceptions.Timeout()
        ok, err = restart_mining("192.168.100.23", "test_token")
        self.assertFalse(ok)
        self.assertEqual(err, "connection_timeout")

    @patch("app.vnish.client.unlock_miner")
    @patch("app.vnish.client.restart_mining")
    @patch("app.vnish.client.lock_miner")
    def test_safe_restart_mining_transactional(
        self,
        mock_lock: MagicMock,
        mock_restart: MagicMock,
        mock_unlock: MagicMock,
    ) -> None:
        mock_unlock.return_value = (True, "token_123", None)
        mock_restart.return_value = (True, None)

        ok, err = safe_restart_mining("192.168.100.23", "secret")
        self.assertTrue(ok)
        self.assertIsNone(err)

        mock_unlock.assert_called_once_with("192.168.100.23", "secret", timeout=DEFAULT_HTTP_TIMEOUT)
        mock_restart.assert_called_once_with("192.168.100.23", "token_123", timeout=DEFAULT_HTTP_TIMEOUT)
        mock_lock.assert_called_once_with("192.168.100.23", "token_123", timeout=DEFAULT_HTTP_TIMEOUT)

    @patch("app.vnish.client.unlock_miner")
    @patch("app.vnish.client.restart_mining")
    @patch("app.vnish.client.lock_miner")
    def test_safe_restart_mining_unlock_fail_skips_restart(
        self,
        mock_lock: MagicMock,
        mock_restart: MagicMock,
        mock_unlock: MagicMock,
    ) -> None:
        mock_unlock.return_value = (False, None, "unauthorized")

        ok, err = safe_restart_mining("192.168.100.23", "wrong_pass")
        self.assertFalse(ok)
        self.assertIn("unlock_failed", err)

        mock_restart.assert_not_called()
        mock_lock.assert_not_called()

    @patch("requests.get")
    def test_get_miner_status_success(self, mock_get: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "miner_state": "mining",
            "restart_required": False,
            "reboot_required": False,
        }
        mock_get.return_value = mock_resp

        ok, data, err = get_miner_status("192.168.100.23")
        self.assertTrue(ok)
        self.assertIsNone(err)
        self.assertEqual(data["miner_state"], "mining")
        self.assertFalse(data["restart_required"])


from app.miner_monitor import (
    MinerState,
    _async_execute_mining_restart,
    evaluate_auto_restart_candidate,
    load_state,
    save_state,
)


class TestEvaluateAutoRestartCandidate(unittest.TestCase):
    """Spec 056 - Iteration 2: Unit tests for Level 1 soft auto-restart candidate evaluation."""

    def test_normal_mining_returns_not_needed(self) -> None:
        cand, reason, cd = evaluate_auto_restart_candidate(
            now_ts=1000.0,
            responded=True,
            rate_ths=88.5,
            threshold_ths=60.0,
            active_boards=3,
            expected_boards=3,
            miner_state="mining",
            restart_required=False,
            reboot_required=False,
            auto_restart_enabled=True,
            last_auto_restart_ts=None,
            auto_restart_cooldown_seconds=300.0,
            auto_restart_count=0,
            max_retries_before_reboot=2,
        )
        self.assertFalse(cand)
        self.assertEqual(reason, "not_needed")
        self.assertIsNone(cd)

    def test_stopped_state_triggers_restart(self) -> None:
        cand, reason, cd = evaluate_auto_restart_candidate(
            now_ts=1000.0,
            responded=True,
            rate_ths=0.0,
            threshold_ths=60.0,
            active_boards=0,
            expected_boards=3,
            miner_state="stopped",
            restart_required=False,
            reboot_required=False,
            auto_restart_enabled=True,
            last_auto_restart_ts=None,
            auto_restart_cooldown_seconds=300.0,
            auto_restart_count=0,
            max_retries_before_reboot=2,
        )
        self.assertTrue(cand)
        self.assertEqual(reason, "stopped_state")
        self.assertIsNone(cd)

    def test_restart_required_flag_triggers_restart(self) -> None:
        cand, reason, cd = evaluate_auto_restart_candidate(
            now_ts=1000.0,
            responded=True,
            rate_ths=70.0,
            threshold_ths=60.0,
            active_boards=3,
            expected_boards=3,
            miner_state="mining",
            restart_required=True,
            reboot_required=False,
            auto_restart_enabled=True,
            last_auto_restart_ts=None,
            auto_restart_cooldown_seconds=300.0,
            auto_restart_count=0,
            max_retries_before_reboot=2,
        )
        self.assertTrue(cand)
        self.assertEqual(reason, "restart_required_flag")
        self.assertIsNone(cd)

    def test_zero_hashrate_triggers_restart(self) -> None:
        cand, reason, cd = evaluate_auto_restart_candidate(
            now_ts=1000.0,
            responded=True,
            rate_ths=0.0,
            threshold_ths=60.0,
            active_boards=3,
            expected_boards=3,
            miner_state="mining",
            restart_required=False,
            reboot_required=False,
            auto_restart_enabled=True,
            last_auto_restart_ts=None,
            auto_restart_cooldown_seconds=300.0,
            auto_restart_count=0,
            max_retries_before_reboot=2,
        )
        self.assertTrue(cand)
        self.assertEqual(reason, "zero_hashrate")
        self.assertIsNone(cd)

    def test_zero_boards_triggers_restart(self) -> None:
        cand, reason, cd = evaluate_auto_restart_candidate(
            now_ts=1000.0,
            responded=True,
            rate_ths=None,
            threshold_ths=60.0,
            active_boards=0,
            expected_boards=3,
            miner_state="mining",
            restart_required=False,
            reboot_required=False,
            auto_restart_enabled=True,
            last_auto_restart_ts=None,
            auto_restart_cooldown_seconds=300.0,
            auto_restart_count=0,
            max_retries_before_reboot=2,
        )
        self.assertTrue(cand)
        self.assertEqual(reason, "zero_boards")
        self.assertIsNone(cd)

    def test_transient_starting_state_blocked(self) -> None:
        for state in ("starting", "init", "initializing", "benchmarking"):
            cand, reason, cd = evaluate_auto_restart_candidate(
                now_ts=1000.0,
                responded=True,
                rate_ths=0.0,
                threshold_ths=60.0,
                active_boards=0,
                expected_boards=3,
                miner_state=state,
                restart_required=False,
                reboot_required=False,
                auto_restart_enabled=True,
                last_auto_restart_ts=None,
                auto_restart_cooldown_seconds=300.0,
                auto_restart_count=0,
                max_retries_before_reboot=2,
            )
            self.assertFalse(cand, f"State {state} should be blocked")
            self.assertEqual(reason, "transient_starting")

    def test_hardware_reboot_required_blocked_from_soft_restart(self) -> None:
        cand, reason, cd = evaluate_auto_restart_candidate(
            now_ts=1000.0,
            responded=True,
            rate_ths=0.0,
            threshold_ths=60.0,
            active_boards=0,
            expected_boards=3,
            miner_state="stopped",
            restart_required=True,
            reboot_required=True,
            auto_restart_enabled=True,
            last_auto_restart_ts=None,
            auto_restart_cooldown_seconds=300.0,
            auto_restart_count=0,
            max_retries_before_reboot=2,
        )
        self.assertFalse(cand)
        self.assertEqual(reason, "hardware_reboot_required")

    def test_cooldown_enforced(self) -> None:
        cand, reason, cd = evaluate_auto_restart_candidate(
            now_ts=1100.0,
            responded=True,
            rate_ths=0.0,
            threshold_ths=60.0,
            active_boards=0,
            expected_boards=3,
            miner_state="stopped",
            restart_required=False,
            reboot_required=False,
            auto_restart_enabled=True,
            last_auto_restart_ts=1000.0,
            auto_restart_cooldown_seconds=300.0,
            auto_restart_count=1,
            max_retries_before_reboot=2,
        )
        self.assertFalse(cand)
        self.assertEqual(reason, "cooldown")
        self.assertAlmostEqual(cd, 200.0)

    def test_max_retries_exceeded_blocks_soft_restart(self) -> None:
        cand, reason, cd = evaluate_auto_restart_candidate(
            now_ts=1500.0,
            responded=True,
            rate_ths=0.0,
            threshold_ths=60.0,
            active_boards=0,
            expected_boards=3,
            miner_state="stopped",
            restart_required=False,
            reboot_required=False,
            auto_restart_enabled=True,
            last_auto_restart_ts=1000.0,
            auto_restart_cooldown_seconds=300.0,
            auto_restart_count=2,
            max_retries_before_reboot=2,
        )
        self.assertFalse(cand)
        self.assertEqual(reason, "max_retries_exceeded")

    def test_miner_warming_up_blocked_by_elapsed(self) -> None:
        cand, reason, cd = evaluate_auto_restart_candidate(
            now_ts=1000.0,
            responded=True,
            rate_ths=0.0,
            threshold_ths=60.0,
            active_boards=0,
            expected_boards=3,
            miner_state="stopped",
            restart_required=False,
            reboot_required=False,
            auto_restart_enabled=True,
            last_auto_restart_ts=None,
            auto_restart_cooldown_seconds=300.0,
            auto_restart_count=0,
            max_retries_before_reboot=2,
            elapsed=30,
            min_elapsed_seconds=180,
        )
        self.assertFalse(cand)
        self.assertEqual(reason, "miner_warming_up")
        self.assertIsNone(cd)

    def test_startup_grace_active_blocks_soft_restart(self) -> None:
        cand, reason, cd = evaluate_auto_restart_candidate(
            now_ts=1000.0,
            responded=True,
            rate_ths=0.0,
            threshold_ths=60.0,
            active_boards=0,
            expected_boards=3,
            miner_state="stopped",
            restart_required=False,
            reboot_required=False,
            auto_restart_enabled=True,
            last_auto_restart_ts=None,
            auto_restart_cooldown_seconds=300.0,
            auto_restart_count=0,
            max_retries_before_reboot=2,
            startup_grace_active=True,
        )
        self.assertFalse(cand)
        self.assertEqual(reason, "startup_grace_active")
        self.assertIsNone(cd)

    def test_unresponsive_or_disabled(self) -> None:
        cand, reason, _ = evaluate_auto_restart_candidate(
            now_ts=1000.0,
            responded=False,
            rate_ths=0.0,
            threshold_ths=60.0,
            active_boards=0,
            expected_boards=3,
            miner_state="stopped",
            restart_required=False,
            reboot_required=False,
            auto_restart_enabled=True,
            last_auto_restart_ts=None,
            auto_restart_cooldown_seconds=300.0,
            auto_restart_count=0,
            max_retries_before_reboot=2,
        )
        self.assertFalse(cand)
        self.assertEqual(reason, "unresponsive")

        cand, reason, _ = evaluate_auto_restart_candidate(
            now_ts=1000.0,
            responded=True,
            rate_ths=0.0,
            threshold_ths=60.0,
            active_boards=0,
            expected_boards=3,
            miner_state="stopped",
            restart_required=False,
            reboot_required=False,
            auto_restart_enabled=False,
            last_auto_restart_ts=None,
            auto_restart_cooldown_seconds=300.0,
            auto_restart_count=0,
            max_retries_before_reboot=2,
        )
        self.assertFalse(cand)
        self.assertEqual(reason, "disabled")

    def test_maintenance_or_snooze_blocks(self) -> None:
        cand, reason, _ = evaluate_auto_restart_candidate(
            now_ts=1000.0,
            responded=True,
            rate_ths=0.0,
            threshold_ths=60.0,
            active_boards=0,
            expected_boards=3,
            miner_state="stopped",
            restart_required=False,
            reboot_required=False,
            auto_restart_enabled=True,
            last_auto_restart_ts=None,
            auto_restart_cooldown_seconds=300.0,
            auto_restart_count=0,
            max_retries_before_reboot=2,
            in_maintenance=True,
        )
        self.assertFalse(cand)
        self.assertEqual(reason, "maintenance_or_snoozed")

        cand, reason, _ = evaluate_auto_restart_candidate(
            now_ts=1000.0,
            responded=True,
            rate_ths=0.0,
            threshold_ths=60.0,
            active_boards=0,
            expected_boards=3,
            miner_state="stopped",
            restart_required=False,
            reboot_required=False,
            auto_restart_enabled=True,
            last_auto_restart_ts=None,
            auto_restart_cooldown_seconds=300.0,
            auto_restart_count=0,
            max_retries_before_reboot=2,
            is_snoozed=True,
        )
        self.assertFalse(cand)
        self.assertEqual(reason, "maintenance_or_snoozed")


class TestMinerStateSoftRestartPersistence(unittest.TestCase):
    """Spec 056 - Iteration 2: Unit tests for MinerState soft restart fields and round-trip."""

    def test_miner_state_defaults(self) -> None:
        st = MinerState()
        self.assertIsNone(st.last_auto_restart_ts)
        self.assertEqual(st.auto_restart_count, 0)

    def test_state_serialization_roundtrip(self) -> None:
        import tempfile
        from pathlib import Path
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            st = MinerState(
                last_auto_restart_ts=1726000000.0,
                auto_restart_count=2,
            )
            states = {"192.168.100.23:4028": st}
            save_state(state_file, states, 123)

            loaded_states, last_upd = load_state(state_file)
            self.assertEqual(last_upd, 123)
            self.assertIn("192.168.100.23:4028", loaded_states)
            loaded_st = loaded_states["192.168.100.23:4028"]
            self.assertEqual(loaded_st.last_auto_restart_ts, 1726000000.0)
            self.assertEqual(loaded_st.auto_restart_count, 2)


class TestTwoTierEscalationLifecycle(unittest.TestCase):
    """Spec 056 - Iteration 3: Tests verifying Level 1 precedence, retry exhaustion, and Level 2 escalation."""

    def test_level_1_precedes_level_2(self) -> None:
        """Level 1 soft restart triggers immediately when degraded, while Level 2 is held by sustained window."""
        now_ts = 1000.0
        hashboard_since_ts = 1000.0  # just entered STATE_HASHBOARD
        auto_reboot_hashboard_sustained_seconds = 600.0

        # Level 1 check
        cand_l1, reason_l1, _ = evaluate_auto_restart_candidate(
            now_ts=now_ts,
            responded=True,
            rate_ths=0.0,
            threshold_ths=60.0,
            active_boards=0,
            expected_boards=3,
            miner_state="stopped",
            restart_required=False,
            reboot_required=False,
            auto_restart_enabled=True,
            last_auto_restart_ts=None,
            auto_restart_cooldown_seconds=300.0,
            auto_restart_count=0,
            max_retries_before_reboot=2,
        )
        self.assertTrue(cand_l1)
        self.assertEqual(reason_l1, "stopped_state")

        # Level 2 check: elapsed is 0s < 600s -> held
        elapsed_l2 = now_ts - hashboard_since_ts
        self.assertLess(elapsed_l2, auto_reboot_hashboard_sustained_seconds)

    def test_level_2_escalation_after_retries_exhausted(self) -> None:
        """After Level 1 max retries (2) and 600s sustained window, Level 1 yields and Level 2 qualifies."""
        now_ts = 1700.0
        hashboard_since_ts = 1000.0  # 700s elapsed (> 600s)
        auto_reboot_hashboard_sustained_seconds = 600.0

        # Level 1 check: retries exhausted
        cand_l1, reason_l1, _ = evaluate_auto_restart_candidate(
            now_ts=now_ts,
            responded=True,
            rate_ths=0.0,
            threshold_ths=60.0,
            active_boards=0,
            expected_boards=3,
            miner_state="stopped",
            restart_required=False,
            reboot_required=False,
            auto_restart_enabled=True,
            last_auto_restart_ts=1350.0,
            auto_restart_cooldown_seconds=300.0,
            auto_restart_count=2,
            max_retries_before_reboot=2,
        )
        self.assertFalse(cand_l1)
        self.assertEqual(reason_l1, "max_retries_exceeded")

        # Level 2 check: sustained window met
        elapsed_l2 = now_ts - hashboard_since_ts
        self.assertGreaterEqual(elapsed_l2, auto_reboot_hashboard_sustained_seconds)

    @patch("app.miner_monitor.safe_set_miner_preset", return_value=(True, None))
    @patch("app.miner_monitor.safe_restart_mining")
    @patch("app.miner_monitor.send_telegram")
    @patch("app.miner_monitor.record_action_outcome")
    def test_async_execute_mining_restart_success(
        self,
        mock_record: MagicMock,
        mock_tg: MagicMock,
        mock_restart: MagicMock,
        mock_set_preset: MagicMock,
    ) -> None:
        mock_restart.return_value = (True, None)
        miner = {"name": "S19JPRO-23", "host": "192.0.2.23", "port": 4028, "max_hardware_preset": "2700W"}

        _async_execute_mining_restart(
            host="192.0.2.23",
            password="admin",
            miner_name="S19JPRO-23",
            miner_dict=miner,
            trigger_reason="stopped_state",
            attempt=1,
            max_attempts=2,
            bot_token="fake_token",
            chat_id="12345",
            qa_mode=False,
            qa_notify=False,
            event_store=None,
        )

        mock_set_preset.assert_called_once()
        mock_restart.assert_called_once_with("192.0.2.23", "admin")
        mock_tg.assert_called_once()
        self.assertIn("Nivel 1", mock_tg.call_args[0][2])
        self.assertIn("23", mock_tg.call_args[0][2])
        mock_record.assert_called_once()
        self.assertTrue(mock_record.call_args[1]["ok"])

    @patch("app.miner_monitor.safe_set_miner_preset", return_value=(True, None))
    @patch("app.miner_monitor.safe_restart_mining")
    @patch("app.miner_monitor.send_telegram")
    @patch("app.miner_monitor.record_action_outcome")
    def test_async_execute_mining_restart_failure(
        self,
        mock_record: MagicMock,
        mock_tg: MagicMock,
        mock_restart: MagicMock,
        mock_set_preset: MagicMock,
    ) -> None:
        mock_restart.return_value = (False, "unlock_failed: timeout")
        miner = {"name": "S19JPRO-23", "host": "192.0.2.23", "port": 4028, "max_hardware_preset": "2700W"}

        _async_execute_mining_restart(
            host="192.0.2.23",
            password="admin",
            miner_name="S19JPRO-23",
            miner_dict=miner,
            trigger_reason="stopped_state",
            attempt=1,
            max_attempts=2,
            bot_token="fake_token",
            chat_id="12345",
            qa_mode=False,
            qa_notify=False,
            event_store=None,
        )

        mock_set_preset.assert_called_once()
        mock_restart.assert_called_once_with("192.0.2.23", "admin")
        mock_tg.assert_called_once()
        self.assertIn("AUTO-RESTART FAILED", mock_tg.call_args[0][2])
        mock_record.assert_called_once()
        self.assertFalse(mock_record.call_args[1]["ok"])


if __name__ == "__main__":
    unittest.main()


