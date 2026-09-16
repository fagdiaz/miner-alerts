from dataclasses import dataclass
import unittest

from app.telegram.command_center import find_assessment_by_target, format_miner_key


@dataclass
class DummyAssessment:
    miner_name: str
    data: str = "ok"


class TestFindAssessmentByTarget(unittest.TestCase):
    def setUp(self):
        self.miners = [
            {"name": "S19JPRO-23", "host": "192.168.1.23", "port": 4028},
            {"name": "S19JPRO-24", "host": "192.168.1.24", "port": 4028},
            {"name": "S19JPRO-25", "host": "192.168.1.25", "port": 4028},
        ]
        self.assessments = [
            DummyAssessment(miner_name="S19JPRO-23"),
            DummyAssessment(miner_name="S19JPRO-24"),
            DummyAssessment(miner_name="S19JPRO-25"),
        ]

    def test_find_by_exact_name(self):
        res = find_assessment_by_target(self.assessments, "S19JPRO-23", self.miners)
        self.assertIsNotNone(res)
        self.assertEqual(res.miner_name, "S19JPRO-23")

    def test_find_by_short_id(self):
        res = find_assessment_by_target(self.assessments, "24", self.miners)
        self.assertIsNotNone(res)
        self.assertEqual(res.miner_name, "S19JPRO-24")

    def test_find_by_ip(self):
        res = find_assessment_by_target(self.assessments, "192.168.1.25", self.miners)
        self.assertIsNotNone(res)
        self.assertEqual(res.miner_name, "S19JPRO-25")

    def test_find_all_returns_none(self):
        res = find_assessment_by_target(self.assessments, "all", self.miners)
        self.assertIsNone(res)

    def test_find_nonexistent_returns_none(self):
        res = find_assessment_by_target(self.assessments, "999", self.miners)
        self.assertIsNone(res)

    def test_format_miner_key_standard(self):
        key = format_miner_key({"name": "S19JPRO-23", "host": "192.168.1.23", "port": 4028})
        self.assertEqual(key, "S19JPRO-23|192.168.1.23:4028")

    def test_format_miner_key_ip_and_default_port(self):
        key = format_miner_key({"name": "M50", "ip": "10.0.0.1"})
        self.assertEqual(key, "M50|10.0.0.1:4028")

    def test_format_miner_key_empty(self):
        key = format_miner_key({})
        self.assertEqual(key, "unknown|no-host:4028")


if __name__ == "__main__":
    unittest.main()
