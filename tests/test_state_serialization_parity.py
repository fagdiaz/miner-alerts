import unittest
from app.miner_monitor import MinerState, _build_state_payload
from app.core.state_manager import serialize_miner_state


class TestStateSerializationParity(unittest.TestCase):
    def test_serialize_miner_state_field_completeness(self):
        st = MinerState(state="OK", low_streak=0, offline_streak=0, ok_streak=5)
        st.governor_duty = 60
        st.balancer_preset = "2500W"
        st.last_rate_ths = 95.5
        st.last_power_w = 2700

        serialized = serialize_miner_state(st)
        self.assertIsInstance(serialized, dict)
        self.assertEqual(serialized["state"], "OK")
        self.assertEqual(serialized["ok_streak"], 5)
        self.assertEqual(serialized["governor_duty"], 60)
        self.assertEqual(serialized["balancer_preset"], "2500W")
        self.assertEqual(serialized["last_rate_ths"], 95.5)
        self.assertEqual(serialized["last_power_w"], 2700)

        # Build state payload round-trip check
        payload = _build_state_payload({"miner_1": st}, last_update_id=100)
        self.assertIn("states", payload)
        self.assertIn("miner_1", payload["states"])
        self.assertEqual(payload["states"]["miner_1"], serialized)


if __name__ == "__main__":
    unittest.main()
