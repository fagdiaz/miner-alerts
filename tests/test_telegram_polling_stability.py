import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MONITOR_PATH = ROOT / "app" / "miner_monitor.py"


class TelegramPollingStabilityTests(unittest.TestCase):
    def test_poll_empty_branch_has_no_command_local_references(self) -> None:
        source = MONITOR_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        poll_empty_call = None
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            first_arg = node.args[0]
            if (
                isinstance(first_arg, ast.JoinedStr)
                and "POLL_EMPTY" in ast.unparse(first_arg)
            ):
                poll_empty_call = node
                break

        self.assertIsNotNone(poll_empty_call, "POLL_EMPTY diagnostic not found")
        parent_if = next(
            (
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.If)
                and poll_empty_call in list(ast.walk(node))
                and "max_update_id_in_batch" in ast.unparse(node.test)
            ),
            None,
        )
        self.assertIsNotNone(parent_if, "POLL_EMPTY batch branch not found")
        idle_source = "\n".join(
            ast.unparse(statement) for statement in parent_if.orelse
        )
        self.assertNotIn("action", idle_source)
        self.assertNotIn("cmd_start", idle_source)


if __name__ == "__main__":
    unittest.main()
