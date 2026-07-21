import unittest
from pathlib import Path


class VnishSchedulerTests(unittest.TestCase):
    def test_scheduler_is_non_overlapping_no_console_and_read_only(self) -> None:
        source = Path("tools/install_vnish_collector_task.ps1").read_text(
            encoding="utf-8"
        )

        self.assertIn("SupportsShouldProcess", source)
        self.assertIn("MultipleInstances IgnoreNew", source)
        self.assertIn("LogonType Interactive", source)
        self.assertIn("RunLevel Limited", source)
        self.assertIn("ExecutionTimeLimit", source)
        self.assertIn("-WorkingDirectory $repoRoot", source)
        self.assertIn("[int]$IntervalMinutes = 30", source)
        self.assertIn("pythonw.exe", source)
        self.assertIn("vnish_log_collector.py", source)
        self.assertIn("--config", source)
        self.assertNotIn("Get-Command powershell.exe", source)
        self.assertNotIn("-WindowStyle", source)
        self.assertNotIn("Highest", source)
        self.assertNotIn("Register-ScheduledJob", source)

    def test_runner_invokes_only_bounded_collector(self) -> None:
        source = Path("tools/run_vnish_collector.ps1").read_text(encoding="utf-8")

        self.assertIn("vnish_log_collector.py", source)
        self.assertIn("--max-bytes", source)
        self.assertIn("--max-events", source)
        self.assertIn('[string]$RepoRoot = ""', source)
        self.assertIn("[string]::IsNullOrWhiteSpace($RepoRoot)", source)
        self.assertNotIn(
            "[string]$RepoRoot = (Split-Path -Parent $PSScriptRoot)", source
        )
        self.assertNotIn("miner_monitor.py", source)
        self.assertNotIn("Hashcore", source)
        self.assertNotIn("reboot", source.lower())


if __name__ == "__main__":
    unittest.main()
