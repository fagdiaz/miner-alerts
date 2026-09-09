"""Unit tests for Telegram Mobile Help Center & Categorized Navigation (Spec 045).

Verifies canonical registry, aliases resolution, callback grammar and 64-byte limit,
mobile visible line width <= 32 cols, message length < 3600 chars, hostile Markdown
escaping, and zero I/O deterministic execution.
"""

from __future__ import annotations

import unittest
from typing import Any, Dict, List

from app.telegram.help_center import (
    HELP_CATEGORIES,
    HELP_COMMANDS,
    HELP_NAV_HOME,
    HELP_PREFIX,
    MAX_CALLBACK_BYTES,
    MAX_INTERACTIVE_VIEW_CHARS,
    CommandDefinition,
    HelpAction,
    HelpCategory,
    escape_markdown,
    lookup_command,
    parse_help_callback,
    render_help_category,
    render_help_command_detail,
    render_help_home,
    render_legacy_help_detail,
    render_legacy_help_index,
    strip_markdown,
    visible_line_width,
    wrap_mobile_lines,
)


class TestHelpCenterRegistry(unittest.TestCase):
    """Test canonical command catalog and categories integrity."""

    def test_catalog_not_empty(self):
        self.assertGreaterEqual(len(HELP_COMMANDS), 28)
        self.assertEqual(len(HELP_CATEGORIES), 5)

    def test_all_categories_valid(self):
        expected_cats = {"mon", "thm", "pwr", "ctrl", "diag"}
        self.assertEqual(set(HELP_CATEGORIES.keys()), expected_cats)

        for cat_id, cat in HELP_CATEGORIES.items():
            self.assertEqual(cat.id, cat_id)
            self.assertTrue(cat.title)
            self.assertTrue(cat.icon)
            self.assertTrue(cat.description)
            self.assertTrue(cat.command_names)
            for cmd_name in cat.command_names:
                self.assertIn(
                    cmd_name,
                    HELP_COMMANDS,
                    f"Command '{cmd_name}' in category '{cat_id}' not found in HELP_COMMANDS",
                )

    def test_all_commands_belong_to_valid_category(self):
        for cmd_name, cmd in HELP_COMMANDS.items():
            self.assertEqual(cmd.name, cmd_name)
            self.assertIn(
                cmd.category,
                HELP_CATEGORIES,
                f"Command '{cmd_name}' has invalid category '{cmd.category}'",
            )
            self.assertIn(
                cmd_name,
                HELP_CATEGORIES[cmd.category].command_names,
                f"Command '{cmd_name}' not listed in its category '{cmd.category}'",
            )
            self.assertTrue(cmd.summary)
            self.assertTrue(cmd.usage)
            self.assertTrue(cmd.detail)
            self.assertTrue(cmd.examples)
            self.assertIn(cmd.danger_level, ("safe", "danger"))

    def test_danger_commands_classified_correctly(self):
        danger_cmds = {"reboot", "reboot_no_ok", "restart", "confirm"}
        for cmd_name in danger_cmds:
            self.assertEqual(
                HELP_COMMANDS[cmd_name].danger_level,
                "danger",
                f"Command '{cmd_name}' must have danger_level='danger'",
            )

        safe_sample = {"status", "fans", "efficiency", "silent", "menu", "events", "diagnose"}
        for cmd_name in safe_sample:
            self.assertEqual(
                HELP_COMMANDS[cmd_name].danger_level,
                "safe",
                f"Command '{cmd_name}' must have danger_level='safe'",
            )

    def test_critical_dispatcher_commands_present(self):
        """Verify commands from miner_monitor.py dispatcher are strictly covered."""
        required = [
            "menu",
            "silent",
            "status",
            "info",
            "chart",
            "digest",
            "fans",
            "governor",
            "efficiency",
            "presets",
            "balancer",
            "elevadores",
            "snooze",
            "unsnooze",
            "snoozed",
            "reboot",
            "reboot_no_ok",
            "restart",
            "confirm",
            "events",
            "event",
            "why",
            "diagnose",
            "health",
            "quality",
            "firmware",
            "selftest",
            "help",
        ]
        for req in required:
            self.assertIn(req, HELP_COMMANDS, f"Missing required command '{req}' in catalog")


class TestHelpCenterLookupAndAliases(unittest.TestCase):
    """Test resolution of canonical names, aliases, slashes, and case insensitivity."""

    def test_canonical_lookup(self):
        cmd = lookup_command("silent")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.name, "silent")

        cmd_slash = lookup_command("/silent")
        self.assertIsNotNone(cmd_slash)
        self.assertEqual(cmd_slash.name, "silent")

        cmd_upper = lookup_command("SILENT")
        self.assertIsNotNone(cmd_upper)
        self.assertEqual(cmd_upper.name, "silent")

    def test_silent_aliases(self):
        for alias in ("silencio", "modo_silencio", "/silencio", "/modo_silencio"):
            cmd = lookup_command(alias)
            self.assertIsNotNone(cmd, f"Failed resolving alias '{alias}'")
            self.assertEqual(cmd.name, "silent")

    def test_menu_aliases(self):
        for alias in ("start", "panel", "/start", "/panel", "MENU"):
            cmd = lookup_command(alias)
            self.assertIsNotNone(cmd, f"Failed resolving alias '{alias}'")
            self.assertEqual(cmd.name, "menu")

    def test_thermal_and_power_aliases(self):
        self.assertEqual(lookup_command("gov").name, "governor")
        self.assertEqual(lookup_command("governor").name, "governor")
        self.assertEqual(lookup_command("fan").name, "fans")
        self.assertEqual(lookup_command("eff").name, "efficiency")
        self.assertEqual(lookup_command("preset").name, "presets")
        self.assertEqual(lookup_command("profile").name, "presets")
        self.assertEqual(lookup_command("bal").name, "balancer")
        self.assertEqual(lookup_command("power").name, "balancer")
        self.assertEqual(lookup_command("elev").name, "elevadores")
        self.assertEqual(lookup_command("sensibilidad").name, "elevadores")
        self.assertEqual(lookup_command("elevators").name, "elevadores")

    def test_system_and_diagnostic_aliases(self):
        self.assertEqual(lookup_command("summary").name, "digest")
        self.assertEqual(lookup_command("test").name, "selftest")

    def test_unknown_or_invalid_lookup(self):
        self.assertIsNone(lookup_command("unknown_command_xyz"))
        self.assertIsNone(lookup_command(""))
        self.assertIsNone(lookup_command(None))
        self.assertIsNone(lookup_command("///"))


class TestHelpCenterCallbacks(unittest.TestCase):
    """Test callback_data parsing, strict grammar, and 64-byte UTF-8 limit."""

    def test_parse_valid_nav_home(self):
        action = parse_help_callback("help:nav:home")
        self.assertIsNotNone(action)
        self.assertEqual(action.kind, "nav")
        self.assertEqual(action.target, "home")

    def test_parse_valid_categories(self):
        for cat_id in HELP_CATEGORIES:
            cb_data = f"help:cat:{cat_id}"
            action = parse_help_callback(cb_data)
            self.assertIsNotNone(action, f"Failed parsing valid callback '{cb_data}'")
            self.assertEqual(action.kind, "cat")
            self.assertEqual(action.target, cat_id)

    def test_parse_valid_commands(self):
        action = parse_help_callback("help:cmd:silent")
        self.assertIsNotNone(action)
        self.assertEqual(action.kind, "cmd")
        self.assertEqual(action.target, "silent")

        # Resolves through alias
        action_alias = parse_help_callback("help:cmd:silencio")
        self.assertIsNotNone(action_alias)
        self.assertEqual(action_alias.kind, "cmd")
        self.assertEqual(action_alias.target, "silent")

    def test_parse_invalid_grammar(self):
        invalid_queries = [
            "",
            None,
            "help:",
            "help:nav",
            "help:cat",
            "help:cmd",
            "help:unknown:extra",
            "help:nav:other",
            "help:cat:invalid_cat",
            "help:cmd:nonexistent_cmd",
            "help:nav:home:extra_field",
            "cc:nav:main",
            "rb:cfm:123",
        ]
        for query in invalid_queries:
            self.assertIsNone(parse_help_callback(query), f"Expected None for '{query}'")

    def test_callback_payload_byte_limit(self):
        # 64 bytes is the maximum allowed by Telegram API
        valid_at_limit = "help:cmd:" + "a" * (MAX_CALLBACK_BYTES - len("help:cmd:"))
        self.assertEqual(len(valid_at_limit.encode("utf-8")), MAX_CALLBACK_BYTES)
        # Even if command doesn't exist, parser checks byte limit before grammar

        exceeding_by_1 = "help:cmd:" + "a" * (MAX_CALLBACK_BYTES - len("help:cmd:") + 1)
        self.assertGreater(len(exceeding_by_1.encode("utf-8")), MAX_CALLBACK_BYTES)
        self.assertIsNone(parse_help_callback(exceeding_by_1))

        # Multibyte UTF-8 characters
        unicode_heavy = "help:cmd:" + "🔥" * 20  # 4 bytes per emoji = 80 bytes
        self.assertGreater(len(unicode_heavy.encode("utf-8")), MAX_CALLBACK_BYTES)
        self.assertIsNone(parse_help_callback(unicode_heavy))

    def test_all_rendered_buttons_under_64_bytes(self):
        """Verify every callback_data in every rendered keyboard is <= 64 bytes."""
        # 1. Home
        _, kb_home = render_help_home()
        self._check_keyboard_callbacks(kb_home)

        # 2. All Categories
        for cat_id in HELP_CATEGORIES:
            _, kb_cat = render_help_category(cat_id)
            self._check_keyboard_callbacks(kb_cat)

        # 3. All Commands
        for cmd_name in HELP_COMMANDS:
            _, kb_cmd = render_help_command_detail(cmd_name)
            self._check_keyboard_callbacks(kb_cmd)

    def _check_keyboard_callbacks(self, markup: Dict[str, Any]):
        rows = markup.get("inline_keyboard", [])
        for row in rows:
            for btn in row:
                cb = btn.get("callback_data", "")
                self.assertTrue(cb, "Button missing callback_data")
                byte_len = len(cb.encode("utf-8"))
                self.assertLessEqual(
                    byte_len,
                    MAX_CALLBACK_BYTES,
                    f"Button callback '{cb}' exceeds {MAX_CALLBACK_BYTES} bytes ({byte_len} bytes)",
                )


class TestHelpCenterFormattingAndLimits(unittest.TestCase):
    """Test mobile line width limits (C1), message size < 3600 (C4), and Markdown handling."""

    def test_strip_markdown(self):
        text = "*Negrita* y _cursiva_ con `código` y [enlace]"
        expected = "Negrita y cursiva con código y enlace"
        self.assertEqual(strip_markdown(text), expected)

        escaped = r"\*asterisco\* y \_guion\_"
        self.assertEqual(strip_markdown(escaped), "*asterisco* y _guion_")

    def test_visible_line_width(self):
        line = "• *Monitoreo*: Telemetría"
        # visible text is "• Monitoreo: Telemetría" (23 characters)
        self.assertEqual(visible_line_width(line), len("• Monitoreo: Telemetría"))

    def test_escape_markdown(self):
        hostile = "S19JPRO_23*TEMP`FAIL[ERR]"
        escaped = escape_markdown(hostile)
        self.assertEqual(escaped, r"S19JPRO\_23\*TEMP\`FAIL\[ERR]")

        # Do not double-escape
        already_escaped = r"S19JPRO\_23"
        self.assertEqual(escape_markdown(already_escaped), r"S19JPRO\_23")

    def test_home_view_bounds(self):
        text, markup = render_help_home()
        self.assertLess(len(text), MAX_INTERACTIVE_VIEW_CHARS)
        self.assertIn("inline_keyboard", markup)

        # Check line widths of text
        for line in text.splitlines():
            v_width = visible_line_width(line)
            self.assertLessEqual(
                v_width,
                32,
                f"Line '{line}' exceeds 32 visible columns ({v_width} cols)",
            )

    def test_category_views_bounds(self):
        for cat_id in HELP_CATEGORIES:
            text, markup = render_help_category(cat_id)
            self.assertLess(
                len(text),
                MAX_INTERACTIVE_VIEW_CHARS,
                f"Category '{cat_id}' view exceeds {MAX_INTERACTIVE_VIEW_CHARS} characters",
            )
            self.assertIn("inline_keyboard", markup)

            for line in text.splitlines():
                v_width = visible_line_width(line)
                self.assertLessEqual(
                    v_width,
                    32,
                    f"Category '{cat_id}' line '{line}' exceeds 32 visible columns ({v_width} cols)",
                )

    def test_command_detail_views_bounds(self):
        for cmd_name in HELP_COMMANDS:
            text, markup = render_help_command_detail(cmd_name)
            self.assertLess(
                len(text),
                MAX_INTERACTIVE_VIEW_CHARS,
                f"Command '{cmd_name}' detail view exceeds {MAX_INTERACTIVE_VIEW_CHARS} characters",
            )
            self.assertIn("inline_keyboard", markup)

            for line in text.splitlines():
                v_width = visible_line_width(line)
                self.assertLessEqual(
                    v_width,
                    32,
                    f"Command '{cmd_name}' line '{line}' exceeds 32 visible columns ({v_width} cols)",
                )

    def test_unknown_category_fallback(self):
        text, markup = render_help_category("invalid_cat_id")
        home_text, home_markup = render_help_home()
        self.assertEqual(text, home_text)
        self.assertEqual(markup, home_markup)

    def test_unknown_command_detail(self):
        text, markup = render_help_command_detail("nonexistent")
        self.assertIn("COMANDO DESCONOCIDO", text)
        self.assertIn("nonexistent", text)
        self.assertIn("inline_keyboard", markup)

    def test_wrap_mobile_lines(self):
        long_text = "Esta es una explicación extensa que debe dividirse limpiamente sin exceder el límite."
        wrapped = wrap_mobile_lines(long_text, width=32)
        for line in wrapped:
            self.assertLessEqual(visible_line_width(line), 32)
        rejoined = " ".join(wrapped)
        self.assertEqual(rejoined, long_text)


class TestHelpCenterLegacyRenderers(unittest.TestCase):
    """Test backwards-compatible text fallbacks."""

    def test_legacy_help_index(self):
        index = render_legacy_help_index()
        self.assertIn("MINER ALERTS - AYUDA", index)
        self.assertIn("/silent", index)
        self.assertIn("/menu", index)
        self.assertIn("/status", index)
        self.assertIn("/fans", index)

    def test_legacy_help_detail_known(self):
        detail = render_legacy_help_detail("silent")
        self.assertIn("/silent", detail)
        self.assertIn("silencio", detail)

    def test_legacy_help_detail_unknown(self):
        detail = render_legacy_help_detail("xyz_not_real")
        self.assertIn("desconocido", detail.lower())

    def test_miner_monitor_help_delegation(self):
        from app.miner_monitor import render_help_index as mm_index, render_help_detail as mm_detail, CMD_WHITELIST
        idx = mm_index()
        self.assertIn("/silent", idx)
        self.assertIn("/menu", idx)

        det = mm_detail("menu")
        self.assertIn("/menu", det)
        self.assertIn("start", det)

        # Verify CMD_WHITELIST completeness
        self.assertIn("menu", CMD_WHITELIST)
        self.assertIn("silent", CMD_WHITELIST)
        self.assertIn("start", CMD_WHITELIST)
        self.assertIn("panel", CMD_WHITELIST)
        self.assertIn("silencio", CMD_WHITELIST)


if __name__ == "__main__":
    unittest.main()
