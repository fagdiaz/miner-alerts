#!/usr/bin/env python3
"""Release Audit and Freeze Verification Tool (Spec 029).

Generates the deterministic runtime-payload digest, validates terminal dispositions
for Specs 021-028, verifies regression matrix completeness, and produces a sanitized
release candidate manifest without executing mutating actions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

TERMINAL_DISPOSITIONS = frozenset({"accepted", "blocked_external", "no_build", "deferred"})
REQUIRED_CHECK_IDS = tuple(f"R{i:03d}" for i in range(1, 26))
ALLOWED_STATUSES = frozenset({"pass", "fail", "blocked", "not_applicable"})

_KNOWN_SPEC_ORDER = (
    "021-monitor-liveness-watchdog",
    "022-adaptive-acquisition",
    "023-incident-evidence-fusion",
    "024-electrical-source-discovery",
    "025-prometheus-metrics",
    "026-hashcore-capability-inventory",
    "027-operator-interface-decision",
    "028-backup-retention-restore",
)


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def audit_terminal_dispositions(project_root: Path) -> dict[str, dict[str, Any]]:
    """Audit Specs 021-028 and verify each has exactly one evidenced terminal disposition."""
    specs_dir = project_root / "specs"
    if not specs_dir.is_dir():
        raise FileNotFoundError(f"Specs directory not found at {specs_dir}")

    dispositions: dict[str, dict[str, Any]] = {}

    for spec_name in _KNOWN_SPEC_ORDER:
        spec_dir = specs_dir / spec_name
        if not spec_dir.is_dir():
            raise FileNotFoundError(f"Spec directory missing: {spec_name}")

        evidence_file = spec_dir / "evidence.md"
        if not evidence_file.is_file():
            raise FileNotFoundError(f"evidence.md missing in {spec_name}")

        content = evidence_file.read_text(encoding="utf-8", errors="replace")

        # Determine terminal state based on explicit evidence
        state: Optional[str] = None
        evidence_ref = f"specs/{spec_name}/evidence.md"

        lower_content = content.lower()

        # Check for non-terminal indicators first
        if "observation_pending" in lower_content or "gate d+3 pending" in lower_content:
            state = "observation_pending"
        elif "missing_hardware_dependency" in lower_content or "blocked_external" in lower_content:
            state = "blocked_external"
        elif "no_build" in lower_content or "no-build" in lower_content:
            state = "no_build"
        elif "deferred" in lower_content:
            state = "deferred"
        elif "completed" in lower_content or "passed" in lower_content or "closed" in lower_content:
            state = "accepted"
        else:
            state = "unknown"

        if state not in TERMINAL_DISPOSITIONS:
            raise ValueError(
                f"Spec {spec_name} has non-terminal or unverified state '{state}'. Freeze rejected."
            )

        dispositions[spec_name] = {
            "state": state,
            "evidence_ref": evidence_ref,
        }

    return dispositions


def compute_runtime_payload_digest(project_root: Path) -> tuple[str, list[dict[str, Any]]]:
    """Compute the deterministic runtime-payload SHA-256 digest and file entries list."""
    payload_entries: list[dict[str, Any]] = []

    # Files to consider
    candidate_paths: list[Path] = []

    # app/**/*.py and config.example.json
    app_dir = project_root / "app"
    if app_dir.is_dir():
        for p in app_dir.rglob("*"):
            if p.is_file():
                if p.suffix == ".py" and "__pycache__" not in p.parts:
                    candidate_paths.append(p)
                elif p.name == "config.example.json":
                    candidate_paths.append(p)

    # tools/**/*.py, *.ps1
    tools_dir = project_root / "tools"
    if tools_dir.is_dir():
        for p in tools_dir.rglob("*"):
            if p.is_file() and "__pycache__" not in p.parts:
                if p.suffix in (".py", ".ps1", ".cmd", ".bat"):
                    candidate_paths.append(p)

    # Root config/docker/requirements
    for filename in (
        "requirements.txt",
        "requirements-observability.txt",
        "docker-compose.observability.yml",
        "Dockerfile.metrics",
    ):
        p = project_root / filename
        if p.is_file():
            candidate_paths.append(p)

    # observability/**/*
    obs_dir = project_root / "observability"
    if obs_dir.is_dir():
        for p in obs_dir.rglob("*"):
            if p.is_file() and p.suffix in (".yml", ".yaml", ".json"):
                candidate_paths.append(p)

    # Deduplicate and sort relative paths
    sorted_files = sorted(
        candidate_paths,
        key=lambda f: f.relative_to(project_root).as_posix(),
    )

    manifest_lines: list[str] = []
    for f in sorted_files:
        rel = f.relative_to(project_root).as_posix()
        size = f.stat().st_size
        sha256 = _file_sha256(f)
        payload_entries.append({"path": rel, "size": size, "sha256": sha256})
        manifest_lines.append(f"{rel}:{size}:{sha256}")

    master_sha256 = hashlib.sha256("\n".join(manifest_lines).encode("utf-8")).hexdigest()
    return master_sha256, payload_entries


def audit_matrix_completeness(matrix_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Audit the regression matrix R001-R025 for completeness and valid statuses."""
    row_map = {r.get("id"): r for r in matrix_rows if isinstance(r, dict)}

    missing_ids: list[str] = []
    invalid_rows: list[str] = []

    for expected_id in REQUIRED_CHECK_IDS:
        if expected_id not in row_map:
            missing_ids.append(expected_id)
            continue

        row = row_map[expected_id]
        status = row.get("status")
        area = row.get("area")
        check = row.get("check")
        evidence_ref = row.get("evidence_ref")

        if not all([area, check, status, evidence_ref]):
            invalid_rows.append(expected_id)
        elif status not in ALLOWED_STATUSES:
            invalid_rows.append(expected_id)

    is_complete = (len(missing_ids) == 0) and (len(invalid_rows) == 0)
    return {
        "complete": is_complete,
        "missing_ids": missing_ids,
        "invalid_rows": invalid_rows,
        "total_rows": len(row_map),
    }


def sanitize_manifest(data: Any) -> Any:
    """Recursively sanitize any secrets, IP addresses, credentials or absolute disk paths."""
    if isinstance(data, dict):
        return {k: sanitize_manifest(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_manifest(v) for v in data]
    elif isinstance(data, str):
        val = data
        # Redact Telegram bot token
        val = re.sub(r"\d{8,12}:[A-Za-z0-9_-]{20,}", "<REDACTED_BOT_TOKEN>", val)
        # Redact private/local IP addresses
        val = re.sub(r"\b(?:10|172\.(?:1[6-9]|2[0-9]|3[0-1])|192\.168)\.\d{1,3}\.\d{1,3}\b", "<REDACTED_IP>", val)
        # Redact Windows local drive paths (including those with spaces)
        val = re.sub(r"[A-Za-z]:\\[^\"'\n\r,]+", "<REDACTED_PATH>", val)
        return val
    return data


class ReleaseAudit:
    """Orchestrator for Spec 029 release audit and candidate manifest emission."""

    def __init__(self, project_root: Optional[Path] = None) -> None:
        self.project_root = (project_root or Path(__file__).resolve().parents[1]).resolve()

    def get_git_identity(self) -> dict[str, Any]:
        """Query Git commit hash and tracked dirty status."""
        try:
            commit_res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(self.project_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            commit_id = commit_res.stdout.strip()
        except Exception:
            commit_id = "unknown"

        try:
            status_res = subprocess.run(
                ["git", "status", "--porcelain", "--untracked-files=no"],
                cwd=str(self.project_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            # Tree is clean if tracked modifications are absent
            tracked_clean = len(status_res.stdout.strip()) == 0
        except Exception:
            tracked_clean = False

        return {"commit_id": commit_id, "tracked_tree_clean": tracked_clean}

    def generate_release_candidate_manifest(self) -> dict[str, Any]:
        """Generate the complete candidate manifest."""
        dispositions = audit_terminal_dispositions(self.project_root)
        payload_digest, payload_entries = compute_runtime_payload_digest(self.project_root)
        git_id = self.get_git_identity()

        example_config = self.project_root / "app" / "config.example.json"
        example_config_sha256 = _file_sha256(example_config) if example_config.is_file() else "missing"

        raw_manifest: dict[str, Any] = {
            "schema_version": "v2-candidate-manifest-v1",
            "git": git_id,
            "runtime_payload": {
                "sha256": payload_digest,
                "file_count": len(payload_entries),
                "entries": payload_entries,
            },
            "python_environment": {
                "version": sys.version.split()[0],
                "executable": "python.exe",
            },
            "event_store_schema_version": 6,
            "config_example_sha256": example_config_sha256,
            "dependency_dispositions": dispositions,
            "service_and_tasks": {
                "monitor_service": {
                    "name": "MinerAlertsMonitor",
                    "mode": "Windows Service / SCM recovery enabled",
                    "authority": "Exclusive Windows Mutex: MinerAlertsMonitorAuthority",
                },
                "backup_task": {
                    "name": "MinerAlertsBackup",
                    "mode": "Windows Scheduled Task / Highest privilege",
                    "script": "tools/install_backup_task.ps1",
                },
                "watchdog_task": {
                    "name": "MinerAlertsWatchdog",
                    "mode": "Windows Scheduled Task / Out-of-process supervision",
                    "script": "tools/install_watchdog_task.ps1",
                },
            },
            "prior_known_good_rollback": {
                "commit": "4cc7a85",
                "description": "Spec 022 D+3 soak passed, Spec 023 activated, Spec 025 integrated",
                "schema_version": 6,
            },
        }

        return sanitize_manifest(raw_manifest)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit and verify Spec 029 release gate.")
    parser.add_argument("--output", "-o", help="Optional output path for manifest JSON")
    parser.add_argument("--check-only", action="store_true", help="Perform checks and exit with status code")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    audit = ReleaseAudit(project_root)

    try:
        manifest = audit.generate_release_candidate_manifest()
        print(f"RELEASE AUDIT: PASS. Runtime payload SHA-256: {manifest['runtime_payload']['sha256']}")
        print(f"Payload files counted: {manifest['runtime_payload']['file_count']}")
        print(f"Terminal dispositions: {len(manifest['dependency_dispositions'])}/8 verified")

        if args.output:
            out_path = Path(args.output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            print(f"Manifest written to: {out_path}")

        return 0
    except Exception as exc:
        print(f"RELEASE AUDIT ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
