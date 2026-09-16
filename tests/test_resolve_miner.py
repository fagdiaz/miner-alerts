"""Unit tests for miner resolution helper (resolve_miner)."""

from __future__ import annotations

import unittest

from app.miner_monitor import resolve_miner


class TestResolveMiner(unittest.TestCase):
    def setUp(self) -> None:
        self.miners = [
            {"name": "S19JPRO-23", "host": "192.168.100.23", "port": 4028},
            {"name": "S19JPRO-24", "host": "192.168.100.24", "port": 4028},
            {"name": "M50-10", "ip": "192.168.100.10", "port": 4028},
        ]

    def test_resolve_by_exact_name(self) -> None:
        m = resolve_miner("S19JPRO-23", self.miners)
        self.assertIsNotNone(m)
        self.assertEqual(m["name"], "S19JPRO-23")

    def test_resolve_by_lowercase_name(self) -> None:
        m = resolve_miner("s19jpro-23", self.miners)
        self.assertIsNotNone(m)
        self.assertEqual(m["name"], "S19JPRO-23")

    def test_resolve_by_display_suffix(self) -> None:
        m = resolve_miner("23", self.miners)
        self.assertIsNotNone(m)
        self.assertEqual(m["name"], "S19JPRO-23")

    def test_resolve_by_ip_host(self) -> None:
        m = resolve_miner("192.168.100.24", self.miners)
        self.assertIsNotNone(m)
        self.assertEqual(m["name"], "S19JPRO-24")

    def test_resolve_by_ip_fallback(self) -> None:
        m = resolve_miner("192.168.100.10", self.miners)
        self.assertIsNotNone(m)
        self.assertEqual(m["name"], "M50-10")

    def test_resolve_nonexistent_returns_none(self) -> None:
        m = resolve_miner("999", self.miners)
        self.assertIsNone(m)


if __name__ == "__main__":
    unittest.main()
