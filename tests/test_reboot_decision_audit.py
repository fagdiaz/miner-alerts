import tempfile
import unittest
from pathlib import Path

from app.event_store import EventStore
from app.miner_monitor import MinerState, record_auto_reboot_decision
from app.vnish_telemetry import VnishTelemetry


class RebootDecisionAuditTests(unittest.TestCase):
    def test_all_policy_results_are_persistable_without_action(self) -> None:
        results = (
            "not_low",
            "invalid_signal",
            "startup_guard",
            "not_sustained",
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


if __name__ == "__main__":
    unittest.main()
