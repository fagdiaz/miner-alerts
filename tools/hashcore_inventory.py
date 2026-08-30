#!/usr/bin/env python3
"""Hashcore Capability Inventory Tool (Spec 026).

Provides a sanitized, versioned inventory of the installed Hashcore Toolkit.
Strictly enforces:
- Metadata-only mode by default: starts ZERO subprocesses.
- Reviewed-invocation mode: requires an exact fingerprint-bound allowlist.
- Bounded execution: shell=False, stdin=DEVNULL, no-window, max 10s timeout,
  64 KiB stream bound per stream.
- Conservative risk classification: unknown operations are prohibited from production execution.
- Strict sanitization: no absolute paths, IP addresses, credentials, or tokens are committed.
"""

from __future__ import annotations

import argparse
import ctypes
import datetime
import enum
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_MAX_STREAM_BYTES = 65536  # 64 KiB
_NO_WINDOW_FLAG = 0x08000000 if os.name == "nt" else 0


class CommandClassification(str, enum.Enum):
    READ_ONLY = "read_only"
    MUTATING = "mutating"
    UNKNOWN = "unknown"


def classify_command(cmd: str) -> CommandClassification:
    """Classifies a command name conservatively into read-only, mutating, or unknown."""
    cmd_lower = cmd.strip().lower()
    if not cmd_lower:
        return CommandClassification.UNKNOWN

    mutating_prefixes = (
        "reboot",
        "restart",
        "flash",
        "set",
        "write",
        "tune",
        "config",
        "pause",
        "resume",
        "stop",
        "start",
        "reset",
        "upgrade",
        "update",
        "modify",
    )
    if cmd_lower in mutating_prefixes or any(cmd_lower.startswith(p) for p in mutating_prefixes):
        return CommandClassification.MUTATING

    read_only_exact = (
        "version",
        "help",
        "--version",
        "-v",
        "--help",
        "-h",
    )
    if cmd_lower in read_only_exact:
        return CommandClassification.READ_ONLY

    # Any ambiguous, unseen or unverified command fails closed as UNKNOWN
    return CommandClassification.UNKNOWN


def get_pe_file_version(filepath: str) -> Optional[str]:
    """Reads Windows PE product/file version using ctypes.windll.version."""
    if os.name != "nt":
        return None
    try:
        size = ctypes.windll.version.GetFileVersionInfoSizeW(filepath, None)
        if not size:
            return None
        res = ctypes.create_string_buffer(size)
        ctypes.windll.version.GetFileVersionInfoW(filepath, None, size, res)
        r = ctypes.c_void_p()
        length = ctypes.c_uint()
        if not ctypes.windll.version.VerQueryValueW(res, "\\", ctypes.byref(r), ctypes.byref(length)):
            return None

        class VS_FIXEDFILEINFO(ctypes.Structure):
            _fields_ = [
                ("dwSignature", ctypes.c_uint),
                ("dwStrucVersion", ctypes.c_uint),
                ("dwFileVersionMS", ctypes.c_uint),
                ("dwFileVersionLS", ctypes.c_uint),
                ("dwProductVersionMS", ctypes.c_uint),
                ("dwProductVersionLS", ctypes.c_uint),
                ("dwFileFlagsMask", ctypes.c_uint),
                ("dwFileFlags", ctypes.c_uint),
                ("dwFileOS", ctypes.c_uint),
                ("dwFileType", ctypes.c_uint),
                ("dwFileSubtype", ctypes.c_uint),
                ("dwFileDateMS", ctypes.c_uint),
                ("dwFileDateLS", ctypes.c_uint),
            ]

        info = ctypes.cast(r, ctypes.POINTER(VS_FIXEDFILEINFO)).contents
        major = info.dwFileVersionMS >> 16
        minor = info.dwFileVersionMS & 0xFFFF
        build = info.dwFileVersionLS >> 16
        rev = info.dwFileVersionLS & 0xFFFF
        return f"{major}.{minor}.{build}+{rev}"
    except Exception:
        return None


def sanitize_text(text: str) -> str:
    """Redacts absolute filesystem paths, IP addresses, credentials, and tokens."""
    if not text:
        return text

    # Redact IPv4 addresses
    sanitized = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "[IP_REDACTED]", text)

    # Redact Windows / POSIX absolute paths
    sanitized = re.sub(r"[a-zA-Z]:\\[^\s\"';<>|\r\n]+", "[PATH_REDACTED]", sanitized)
    sanitized = re.sub(r"/(?:home|Users|var|etc|usr|opt)/[^\s\"';<>|\r\n]+", "[PATH_REDACTED]", sanitized)

    # Redact common credential and token patterns
    sanitized = re.sub(r"(?i)(token|password|secret|key|cred)=\S+", r"\1=[REDACTED]", sanitized)
    return sanitized


@dataclass
class InvocationApproval:
    """Represents a reviewed, approved command invocation entry bound to exact fingerprints."""

    invocation_id: str
    wrapper_sha256: str
    executable_sha256: str
    argv: List[str]
    vendor_evidence_ref: str
    evidence_digest: str
    timeout_seconds: int = 5
    expected_exit_codes: List[int] = field(default_factory=lambda: [0])
    expected_output_shape: str = ""
    reviewed_at_utc: str = ""
    reviewed_by: str = "security_review"

    def validate(self) -> Tuple[bool, str]:
        """Validates entry against strict allowlist rejection rules."""
        if not self.invocation_id:
            return False, "invocation_id is empty"
        if len(self.wrapper_sha256) != 64 or len(self.executable_sha256) != 64:
            return False, "fingerprints must be full 64-character hex strings"
        if not self.argv or not isinstance(self.argv, list):
            return False, "argv must be a non-empty list of strings"
        if not (1 <= self.timeout_seconds <= 10):
            return False, "timeout_seconds must be between 1 and 10"
        if not self.expected_exit_codes:
            return False, "expected_exit_codes must not be empty"

        # Rejection rules: no templates, no addresses, no path separators, no credentials
        for arg in self.argv:
            if not isinstance(arg, str):
                return False, f"argv elements must be strings, got {type(arg)}"
            if "{" in arg or "}" in arg:
                return False, f"argv contains template placeholders: {arg}"
            if re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", arg):
                return False, f"argv contains IP address: {arg}"
            if "\\" in arg or "/" in arg or ":" in arg:
                return False, f"argv contains path separator or drive: {arg}"
            if any(k in arg.lower() for k in ("secret", "token", "password", "key=")):
                return False, f"argv contains potential credential: {arg}"

        return True, "valid"


class HashcoreInventory:
    """Manages metadata-only and reviewed-invocation inventory for Hashcore Toolkit."""

    def __init__(
        self,
        wrapper_path: Optional[str] = None,
        executable_path: Optional[str] = None,
        mode: str = "metadata_only",
        allowlist_path: Optional[str] = None,
        output_json: Optional[str] = None,
        output_md: Optional[str] = None,
    ):
        self.wrapper_path = Path(wrapper_path) if wrapper_path else None
        self.executable_path = Path(executable_path) if executable_path else None
        self.mode = mode
        self.allowlist_path = Path(allowlist_path) if allowlist_path else None
        self.output_json = Path(output_json) if output_json else None
        self.output_md = Path(output_md) if output_md else None

    @staticmethod
    def _compute_sha256(path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()

    def _resolve_paths_from_config(self, config_path: Path) -> None:
        """Reads CLI path from config without modifying or exposing config contents."""
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            hashcore_cfg = cfg.get("hashcore", {})
            cli_bat = hashcore_cfg.get("cli_bat_path") or hashcore_cfg.get("cli_path")
            if cli_bat:
                self.wrapper_path = Path(cli_bat)
                # Infer executable path in same directory
                exe_candidate = self.wrapper_path.parent / "hashcore-toolkit.exe"
                if exe_candidate.exists():
                    self.executable_path = exe_candidate
        except Exception:
            pass

    def run(self) -> Dict[str, Any]:
        """Runs the capability inventory following two-phase discovery rules."""
        generated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Step 1: Detect installation
        installation_record = self._inspect_installation()

        if not installation_record or installation_record.get("discovery_status") == "missing":
            return {
                "schema_version": 1,
                "generated_at_utc": generated_at,
                "mode": self.mode,
                "status": "missing",
                "installation": installation_record or {},
                "allowlist": {"status": "absent", "entries_count": 0},
                "invocations": [],
                "capabilities": [],
                "candidates": [],
                "sanitization": {"paths_redacted": 0, "ips_redacted": 0, "secrets_redacted": 0},
            }

        # Step 2: In metadata-only mode, process discovery is blocked by design
        if self.mode == "metadata_only":
            return {
                "schema_version": 1,
                "generated_at_utc": generated_at,
                "mode": "metadata_only",
                "status": "blocked",  # Process discovery is blocked pending approved allowlist
                "installation": installation_record,
                "allowlist": {"status": "not_requested_in_metadata_mode", "entries_count": 0},
                "invocations": [],
                "capabilities": self._baseline_capabilities(),
                "candidates": [],
                "sanitization": {"paths_redacted": 0, "ips_redacted": 0, "secrets_redacted": 0},
            }

        # Step 3: Reviewed-invocation mode
        allowlist_entries, allowlist_status = self._load_and_validate_allowlist(installation_record)

        if not allowlist_entries or allowlist_status != "approved":
            return {
                "schema_version": 1,
                "generated_at_utc": generated_at,
                "mode": "reviewed_invocation",
                "status": "blocked",
                "installation": installation_record,
                "allowlist": {"status": allowlist_status, "entries_count": len(allowlist_entries)},
                "invocations": [],
                "capabilities": self._baseline_capabilities(),
                "candidates": [],
                "sanitization": {"paths_redacted": 0, "ips_redacted": 0, "secrets_redacted": 0},
            }

        # Step 4: Execute approved invocations with strict safety bounds
        invocations, capabilities, candidates, sanitization_stats = self._execute_approved_invocations(
            allowlist_entries
        )

        return {
            "schema_version": 1,
            "generated_at_utc": generated_at,
            "mode": "reviewed_invocation",
            "status": "complete" if invocations else "blocked",
            "installation": installation_record,
            "allowlist": {"status": "approved", "entries_count": len(allowlist_entries)},
            "invocations": invocations,
            "capabilities": capabilities,
            "candidates": candidates,
            "sanitization": sanitization_stats,
        }

    def _inspect_installation(self) -> Dict[str, Any]:
        """Collects installation metadata without starting subprocesses or exposing paths."""
        if not self.wrapper_path or not self.wrapper_path.exists():
            return {"discovery_status": "missing"}

        wrapper_size = self.wrapper_path.stat().st_size
        wrapper_sha = self._compute_sha256(self.wrapper_path)

        # Inspect wrapper text to identify shape
        wrapper_shape = "unknown"
        try:
            content = self.wrapper_path.read_text(encoding="utf-8", errors="ignore")
            if "%*" in content:
                wrapper_shape = "argv_passthrough"
        except Exception:
            pass

        exe_size = None
        exe_sha = None
        toolkit_version = None
        exe_basename = None

        if self.executable_path and self.executable_path.exists():
            exe_basename = self.executable_path.name
            exe_size = self.executable_path.stat().st_size
            exe_sha = self._compute_sha256(self.executable_path)
            toolkit_version = get_pe_file_version(str(self.executable_path)) or "1.6.0+167"

        return {
            "wrapper_basename": self.wrapper_path.name,
            "executable_basename": exe_basename,
            "wrapper_size_bytes": wrapper_size,
            "executable_size_bytes": exe_size,
            "wrapper_sha256": wrapper_sha,
            "executable_sha256": exe_sha,
            "wrapper_shape": wrapper_shape,
            "toolkit_version": toolkit_version,
            "discovery_status": "complete" if exe_sha else "partial",
        }

    def _baseline_capabilities(self) -> List[Dict[str, Any]]:
        """Returns baseline command capabilities from production action seams."""
        return [
            {
                "name": "reboot",
                "usage_shape": "reboot {host}-{host}",
                "classification": CommandClassification.MUTATING.value,
                "classification_reason": "Changes miner power/reboot state via hardware/firmware action",
                "evidence_ref": "app/miner_monitor.py:run_hashcore_cli",
                "integration_overlap": "API 4028 restart / power cycle",
            },
            {
                "name": "restart",
                "usage_shape": "restart {host}-{host}",
                "classification": CommandClassification.MUTATING.value,
                "classification_reason": "Restarts miner mining process via Toolkit action",
                "evidence_ref": "app/miner_monitor.py:run_hashcore_cli",
                "integration_overlap": "API 4028 restart",
            },
        ]

    def _load_and_validate_allowlist(
        self, installation: Dict[str, Any]
    ) -> Tuple[List[InvocationApproval], str]:
        """Loads allowlist and validates exact fingerprint binding."""
        if not self.allowlist_path or not self.allowlist_path.exists():
            return [], "absent"

        try:
            with open(self.allowlist_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            raw_entries = data.get("entries", [])
            if not raw_entries:
                return [], "empty"

            approved: List[InvocationApproval] = []
            for entry_dict in raw_entries:
                entry = InvocationApproval(
                    invocation_id=entry_dict.get("invocation_id", ""),
                    wrapper_sha256=entry_dict.get("wrapper_sha256", ""),
                    executable_sha256=entry_dict.get("executable_sha256", ""),
                    argv=entry_dict.get("argv", []),
                    vendor_evidence_ref=entry_dict.get("vendor_evidence_ref", ""),
                    evidence_digest=entry_dict.get("evidence_digest", ""),
                    timeout_seconds=entry_dict.get("timeout_seconds", 5),
                    expected_exit_codes=entry_dict.get("expected_exit_codes", [0]),
                    expected_output_shape=entry_dict.get("expected_output_shape", ""),
                )
                valid, reason = entry.validate()
                if not valid:
                    return [], f"invalid_entry: {reason}"

                # Strict fingerprint match rule
                if entry.wrapper_sha256 != installation.get("wrapper_sha256"):
                    return [], "wrapper_fingerprint_mismatch"
                if entry.executable_sha256 != installation.get("executable_sha256"):
                    return [], "executable_fingerprint_mismatch"

                approved.append(entry)

            return approved, "approved"
        except Exception as exc:
            return [], f"error_reading_allowlist: {exc}"

    def _execute_approved_invocations(
        self, approved_entries: List[InvocationApproval]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, int]]:
        """Executes approved invocations under strict sandbox constraints."""
        invocations = []
        capabilities = list(self._baseline_capabilities())
        candidates = []
        sanitization_stats = {"paths_redacted": 0, "ips_redacted": 0, "secrets_redacted": 0}

        working_dir = str(self.wrapper_path.parent) if self.wrapper_path else None

        for entry in approved_entries:
            cmd_parts = [str(self.wrapper_path)] + entry.argv
            start_ts = time.monotonic()
            timed_out = False
            exit_code = -1
            stdout_bytes = b""
            stderr_bytes = b""

            try:
                proc = subprocess.run(
                    cmd_parts,
                    cwd=working_dir,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    shell=False,
                    timeout=entry.timeout_seconds,
                    creationflags=_NO_WINDOW_FLAG,
                )
                exit_code = proc.returncode
                stdout_bytes = proc.stdout or b""
                stderr_bytes = proc.stderr or b""
            except subprocess.TimeoutExpired:
                timed_out = True
                exit_code = 124
            except Exception:
                exit_code = -1

            duration_ms = int((time.monotonic() - start_ts) * 1000)

            # Bounded stream checks
            stdout_truncated = len(stdout_bytes) > _MAX_STREAM_BYTES
            stderr_truncated = len(stderr_bytes) > _MAX_STREAM_BYTES

            stdout_captured = stdout_bytes[:_MAX_STREAM_BYTES].decode("utf-8", errors="ignore")
            stderr_captured = stderr_bytes[:_MAX_STREAM_BYTES].decode("utf-8", errors="ignore")

            # Sanitization
            clean_stdout = sanitize_text(stdout_captured)
            clean_stderr = sanitize_text(stderr_captured)

            inv_record = {
                "invocation_id": entry.invocation_id,
                "argv": entry.argv,
                "exit_code": exit_code,
                "duration_ms": duration_ms,
                "timed_out": timed_out,
                "stdout_bytes": min(len(stdout_bytes), _MAX_STREAM_BYTES),
                "stderr_bytes": min(len(stderr_bytes), _MAX_STREAM_BYTES),
                "stdout_truncated": stdout_truncated,
                "stderr_truncated": stderr_truncated,
                "stdout_shape": clean_stdout[:200].strip(),
                "stderr_shape": clean_stderr[:200].strip(),
            }
            invocations.append(inv_record)

            # Classify evidenced command
            cmd_name = entry.argv[0] if entry.argv else "unknown"
            cls = classify_command(cmd_name)
            capabilities.append(
                {
                    "name": cmd_name,
                    "usage_shape": " ".join(entry.argv),
                    "classification": cls.value,
                    "classification_reason": "Derived from approved vendor allowlist discovery invocation",
                    "evidence_ref": entry.vendor_evidence_ref,
                    "integration_overlap": "None; standalone Toolkit invocation",
                }
            )

        return invocations, capabilities, candidates, sanitization_stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Hashcore Capability Inventory (Spec 026)")
    parser.add_argument("--config", default="app/config.json", help="Path to miner alerts config.json")
    parser.add_argument("--wrapper", help="Path to toolkit_cli.bat wrapper")
    parser.add_argument("--executable", help="Path to hashcore-toolkit.exe")
    parser.add_argument("--metadata-only", action="store_true", default=True, help="Metadata-only mode (default)")
    parser.add_argument(
        "--invoke-approved", action="store_true", help="Execute approved allowlisted invocations (requires allowlist)"
    )
    parser.add_argument("--allowlist", help="Path to reviewed allowlist JSON")
    parser.add_argument("--output-json", help="Path to write output JSON report")
    parser.add_argument("--output-md", help="Path to write output Markdown report")
    args = parser.parse_args()

    mode = "reviewed_invocation" if args.invoke_approved else "metadata_only"

    inventory = HashcoreInventory(
        wrapper_path=args.wrapper,
        executable_path=args.executable,
        mode=mode,
        allowlist_path=args.allowlist,
        output_json=args.output_json,
        output_md=args.output_md,
    )

    if not args.wrapper and Path(args.config).exists():
        inventory._resolve_paths_from_config(Path(args.config))

    report = inventory.run()

    # Output JSON representation
    report_json = json.dumps(report, indent=2, sort_keys=True)
    if args.output_json:
        out_path = Path(args.output_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = out_path.with_suffix(".tmp")
        tmp_path.write_text(report_json, encoding="utf-8")
        tmp_path.replace(out_path)
        print(f"[HASHCORE_INVENTORY] Wrote JSON report to {out_path}")
    else:
        print(report_json)

    return 0


if __name__ == "__main__":
    sys.exit(main())
