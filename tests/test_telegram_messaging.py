import ast
import queue
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app import miner_monitor
from app.telegram_messages import (
    TELEGRAM_TEXT_LIMIT,
    classify_delivery,
    normalize_telegram_text,
    split_telegram_message,
)


class TelegramTextContractTests(unittest.TestCase):
    def test_long_message_splits_below_limit_without_content_loss(self) -> None:
        source = "\n\n".join(
            f"Evento {index}: " + ("evidencia " * 40).strip()
            for index in range(40)
        )

        parts = split_telegram_message(source)

        self.assertGreater(len(parts), 1)
        self.assertTrue(all(len(part) <= TELEGRAM_TEXT_LIMIT for part in parts))
        rebuilt = "".join(part.split("\n\n", 1)[1] for part in parts)
        self.assertEqual(normalize_telegram_text(source), rebuilt)

    def test_normalization_removes_nul_and_keeps_readable_spacing(self) -> None:
        self.assertEqual("uno\n\ndos", normalize_telegram_text("uno\x00  \r\n\r\n\r\ndos  "))

    def test_delivery_class_prioritizes_commands_and_action_failures(self) -> None:
        self.assertEqual("command", classify_delivery("STATUS", is_command=True))
        self.assertEqual("critical", classify_delivery("ERROR", is_command=False))
        self.assertEqual("notification", classify_delivery("EPISODE_ALERT", is_command=False))
        self.assertEqual("informational", classify_delivery("STARTUP", is_command=False))


class TelegramHelpContractTests(unittest.TestCase):
    def test_help_lists_official_click_safe_actions(self) -> None:
        rendered = miner_monitor.render_help_index()

        self.assertIn("/rb<ID>", rendered)
        self.assertIn("/reboot_no_ok", rendered)
        self.assertIn("/c<code>", rendered)
        self.assertNotIn("/reboot-no-ok", rendered)
        self.assertNotIn("Ã", rendered)
        self.assertNotIn("ð", rendered)

    def test_help_detail_documents_bulk_preview_without_promoting_legacy(self) -> None:
        rendered = miner_monitor.render_help_detail("reboot_no_ok")

        self.assertIn("/reboot_no_ok", rendered)
        self.assertIn("confirm", rendered.lower())
        self.assertIn("Que hace:", rendered)
        self.assertNotIn("reboot-no-ok", rendered)


class TelegramQueueAdmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_queue = miner_monitor._TELEGRAM_QUEUE
        self.original_session = miner_monitor._HTTP_SESSION

    def tearDown(self) -> None:
        miner_monitor._TELEGRAM_QUEUE = self.original_queue
        miner_monitor._HTTP_SESSION = self.original_session

    def test_command_uses_bounded_direct_send_when_queue_is_full(self) -> None:
        outbound = queue.Queue(maxsize=1)
        outbound.put(("occupied",))
        response = Mock(status_code=200, text="ok")
        session = Mock()
        session.post.return_value = response
        miner_monitor._TELEGRAM_QUEUE = outbound
        miner_monitor._HTTP_SESSION = session

        miner_monitor.send_telegram(
            "token",
            "chat",
            "respuesta",
            "STATUS",
            is_command=True,
            dbg_update_id=42,
            dbg_cmd="status",
        )

        session.post.assert_called_once()
        self.assertEqual((1.5, 4.0), session.post.call_args.kwargs["timeout"])
        self.assertEqual(1, outbound.qsize())

    def test_normal_queue_preserves_ordered_message_parts(self) -> None:
        outbound = queue.Queue(maxsize=4)
        miner_monitor._TELEGRAM_QUEUE = outbound
        source = "x" * (TELEGRAM_TEXT_LIMIT + 500)

        miner_monitor.send_telegram(
            "token", "chat", source, "EVENTS", is_command=True
        )

        items = [outbound.get_nowait(), outbound.get_nowait()]
        self.assertEqual([1, 2], [item[12] for item in items])
        self.assertEqual([2, 2], [item[13] for item in items])
        self.assertTrue(all(len(item[2]) <= TELEGRAM_TEXT_LIMIT for item in items))
        rebuilt = "".join(item[2].split("\n\n", 1)[1] for item in items)
        self.assertEqual(source, rebuilt)

    def test_low_priority_notification_is_rejected_instead_of_evicting_queue(self) -> None:
        outbound = queue.Queue(maxsize=1)
        outbound.put(("occupied",))
        miner_monitor._TELEGRAM_QUEUE = outbound

        with patch("app.miner_monitor.log") as logger:
            miner_monitor.send_telegram(
                "token", "chat", "inicio", "STARTUP", is_command=False
            )

        self.assertEqual(1, outbound.qsize())
        self.assertTrue(
            any("TG QUEUE_DROP" in str(call.args[0]) for call in logger.call_args_list)
        )

    def test_critical_notification_cannot_evict_a_queued_command(self) -> None:
        outbound = queue.Queue(maxsize=1)
        queued_command = ("command-already-admitted",)
        outbound.put(queued_command)
        miner_monitor._TELEGRAM_QUEUE = outbound

        with patch("app.miner_monitor.log") as logger:
            miner_monitor.send_telegram(
                "token", "chat", "fallo automatico", "ERROR", is_command=False
            )

        self.assertIs(queued_command, outbound.get_nowait())
        self.assertTrue(
            any(
                "TG QUEUE_DROP class=critical" in str(call.args[0])
                for call in logger.call_args_list
            )
        )


class TelegramCommandWiringTests(unittest.TestCase):
    def test_command_branches_never_enqueue_deduplicable_replies(self) -> None:
        source = Path("app/miner_monitor.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        parents: dict[ast.AST, ast.AST] = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parents[child] = parent

        command_calls: list[ast.Call] = []
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "send_telegram"
            ):
                continue
            ancestor = parents.get(node)
            while ancestor is not None:
                if isinstance(ancestor, ast.If) and "cmd_name" in ast.unparse(ancestor.test):
                    command_calls.append(node)
                    break
                ancestor = parents.get(ancestor)

        self.assertGreater(len(command_calls), 30)
        missing = []
        for call in command_calls:
            keywords = {keyword.arg: keyword.value for keyword in call.keywords}
            value = keywords.get("is_command")
            if not (isinstance(value, ast.Constant) and value.value is True):
                missing.append(call.lineno)
        self.assertEqual([], missing)

    def test_automatic_notifications_remain_outside_command_delivery(self) -> None:
        source = Path("app/miner_monitor.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        automatic_types = {"STARTUP", "EPISODE_ALERT", "STATE_CHANGE"}
        found = set()
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "send_telegram"
                and len(node.args) >= 4
                and isinstance(node.args[3], ast.Constant)
                and node.args[3].value in automatic_types
            ):
                continue
            found.add(node.args[3].value)
            keywords = {keyword.arg: keyword.value for keyword in node.keywords}
            self.assertNotIn("is_command", keywords)
        self.assertTrue({"STARTUP", "EPISODE_ALERT"}.issubset(found))


if __name__ == "__main__":
    unittest.main()
