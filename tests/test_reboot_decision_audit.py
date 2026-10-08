import tempfile
import unittest
from pathlib import Path

from app.core.event_store import EventStore
from app.miner_monitor import MinerState, record_auto_reboot_decision
from app.vnish.telemetry import VnishTelemetry


class RebootDecisionAuditTests(unittest.TestCase):
    def test_all_policy_results_are_persistable_without_action(self) -> None:
        results = (
            "not_low",
            "invalid_signal",
            "startup_guard",
            "not_sustained",
            "firmware_transition",
            "cooldown",
            "window",
            "qa",
            "executed",
            "failed",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            store = EventStore(Path(temp_dir) / "events.db")
            try:
                state = MinerState(state="LOW", low_since_ts=900.0)
                miner = {"name": "S19JPRO-23", "host": "h23", "port": 4028}
                for index, result in enumerate(results):
                    record_auto_reboot_decision(
                        store,
                        evaluated_ts=1_000.0 + index,
                        miner=miner,
                        state=state,
                        result=result,
                        responded=True,
                        rate_ths=50.0,
                        threshold_ths=60.0,
                        active_boards=3,
                        expected_boards=3,
                        telemetry=VnishTelemetry(),
                        startup_guard_active=False,
                        qa_mode=True,
                        cooldown_remaining_seconds=None,
                        window_seconds=21_600,
                    )
                stored = store.list_reboot_decisions(limit=20, miner_key="S19JPRO-23|h23:4028")
            finally:
                store.close()

        self.assertEqual(set(results), {row["result"] for row in stored})
        self.assertTrue(all(row["qa_mode"] == 1 for row in stored))

    def test_record_auto_reboot_decision_flexible_kwargs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = EventStore(Path(temp_dir) / "events.db")
            try:
                state = MinerState(state="LOW", low_since_ts=800.0)
                miner = {"name": "S19JPRO-24", "host": "192.168.1.24", "port": 4028}
                # Call with all explicit kwargs including low_elapsed_seconds, window_count and extra
                record_auto_reboot_decision(
                    store,
                    evaluated_ts=1000.0,
                    miner=miner,
                    state=state,
                    result="low_hashrate",
                    responded=True,
                    rate_ths=45.0,
                    threshold_ths=60.0,
                    low_elapsed_seconds=200.0,
                    active_boards=2,
                    expected_boards=3,
                    startup_guard_active=False,
                    qa_mode=False,
                    cooldown_remaining_seconds=None,
                    window_count=1,
                    window_seconds=21600,
                    telemetry=VnishTelemetry(),
                    details={"signal": "low_hashrate"},
                    future_unknown_kwarg=True,
                )
                stored = store.list_reboot_decisions(limit=5, miner_key="S19JPRO-24|192.168.1.24:4028")
                self.assertEqual(len(stored), 1)
                self.assertEqual(stored[0]["result"], "low_hashrate")
                self.assertEqual(stored[0]["low_elapsed_seconds"], 200.0)
                self.assertEqual(stored[0]["window_count"], 1)
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
