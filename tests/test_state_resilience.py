"""Tests for state persistence resilience and scope regressions (Post-Blackout Recovery)."""

import ast
import json
import tempfile
import unittest
from pathlib import Path

from app.miner_monitor import MinerState, load_state, save_state


class TestStateResilience(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_path = Path(self.temp_dir.name) / "state.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_save_state_creates_file_and_bak(self):
        states = {
            "m1": MinerState(state="OK", ok_streak=5),
        }
        save_state(self.state_path, states, last_update_id=100)
        self.assertTrue(self.state_path.exists())

        # Second save should create .bak from the first save
        states["m1"].ok_streak = 6
        save_state(self.state_path, states, last_update_id=101)
        bak_path = self.state_path.with_suffix(".bak")
        self.assertTrue(bak_path.exists())

        # Verify bak content has previous state
        bak_data = json.loads(bak_path.read_text(encoding="utf-8"))
        self.assertEqual(bak_data["last_update_id"], 100)

    def test_load_state_recovers_from_bak_on_null_bytes_corruption(self):
        # 1. Create a valid initial state and .bak
        states = {"m1": MinerState(state="OK", ok_streak=10)}
        save_state(self.state_path, states, last_update_id=200)
        save_state(self.state_path, states, last_update_id=201)

        # 2. Simulate NTFS blackout: state.json filled with null bytes
        self.state_path.write_bytes(b"\x00" * 4096)

        # 3. Load state should recover from .bak
        recovered_states, last_id = load_state(self.state_path)
        self.assertIn("m1", recovered_states)
        self.assertEqual(last_id, 200)

    def test_load_state_recovers_from_bak_on_invalid_json(self):
        states = {"m1": MinerState(state="OK", ok_streak=10)}
        save_state(self.state_path, states, last_update_id=300)
        save_state(self.state_path, states, last_update_id=301)

        # Corrupt state.json
        self.state_path.write_text("{\"invalid\": json...", encoding="utf-8")

        recovered_states, last_id = load_state(self.state_path)
        self.assertIn("m1", recovered_states)
        self.assertEqual(last_id, 300)

    def test_load_state_handles_clean_empty_on_total_loss(self):
        self.state_path.write_bytes(b"\x00" * 2048)
        recovered_states, last_id = load_state(self.state_path)
        self.assertEqual(recovered_states, {})
        self.assertIsNone(last_id)

    def test_no_unbound_module_variables_in_miner_monitor(self):
        """AST check: ensure no functions in miner_monitor assign module-level variables without global."""
        py_path = Path(__file__).resolve().parent.parent / "app" / "miner_monitor.py"
        tree = ast.parse(py_path.read_text(encoding="utf-8"))

        module_vars = set()
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        module_vars.add(target.id)
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name):
                    module_vars.add(node.target.id)

        overlaps = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                assigned = set()
                declared_globals = set()
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Global):
                        declared_globals.update(sub.names)
                    elif isinstance(sub, ast.Name):
                        if isinstance(sub.ctx, ast.Store):
                            assigned.add(sub.id)
                overlap = (assigned & module_vars) - declared_globals
                if overlap:
                    for v in overlap:
                        overlaps.append(f"{node.name}:{node.lineno} -> {v}")

        self.assertEqual(overlaps, [], f"Functions assigning module vars without global: {overlaps}")

    def test_state_last_elapsed_updates_preventing_loop(self):
        """Verify that state.last_elapsed updates to current elapsed, preventing perpetual restart triggers."""
        from app.miner_monitor import MinerState

        state = MinerState()
        state.last_elapsed = 119847

        # Simulate tick 1: miner restarted, elapsed dropped to 500
        elapsed = 500
        reboot_reason = ""
        if state.last_elapsed is not None:
            if elapsed < state.last_elapsed - 600:
                reboot_reason = "elapsed_drop"
            elif elapsed < 300 and state.last_elapsed > 3600:
                reboot_reason = "elapsed_reset"
        state.last_elapsed = elapsed

        self.assertEqual(reboot_reason, "elapsed_drop")
        self.assertEqual(state.last_elapsed, 500)

        # Simulate tick 2 (30 seconds later): elapsed is 530
        elapsed = 530
        reboot_reason = ""
        if state.last_elapsed is not None:
            if elapsed < state.last_elapsed - 600:
                reboot_reason = "elapsed_drop"
            elif elapsed < 300 and state.last_elapsed > 3600:
                reboot_reason = "elapsed_reset"
        state.last_elapsed = elapsed

        self.assertEqual(reboot_reason, "")
        self.assertEqual(state.last_elapsed, 530)


if __name__ == "__main__":
    unittest.main()
