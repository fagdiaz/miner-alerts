"""Config Audit Tool — Validation of configuration files against reference schema (Spec 073).

Provides CLI and programmatic interfaces to validate `app/config.json` against
`app/config.example.json`, detecting missing keys, type mismatches, unknown keys,
and unconfigured placeholder credentials.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Tuple

PLACEHOLDER_SUBSTRINGS = (
    "PONER_TOKEN",
    "PONER_CHAT_ID",
    "CHANGE_ME",
    "YOUR_BOT_TOKEN",
    "YOUR_CHAT_ID",
)

CRITICAL_KEYS = {
    "telegram",
    "poll_seconds",
    "threshold_ths",
    "miners",
}


def _is_number(val: Any) -> bool:
    return isinstance(val, (int, float)) and not isinstance(val, bool)


def _check_types_compatible(ref_val: Any, tgt_val: Any, full_key: str = "") -> bool:
    if ref_val is None or tgt_val is None:
        return True
    if full_key.endswith("chat_id") and (isinstance(tgt_val, (str, int)) and not isinstance(tgt_val, bool)):
        return True
    if isinstance(ref_val, bool):
        return isinstance(tgt_val, bool)
    if _is_number(ref_val):
        return _is_number(tgt_val)
    if isinstance(ref_val, str):
        return isinstance(tgt_val, str)
    if isinstance(ref_val, list):
        return isinstance(tgt_val, list)
    if isinstance(ref_val, dict):
        return isinstance(tgt_val, dict)
    return True


def audit_config_dicts(
    reference: Dict[str, Any],
    target: Dict[str, Any],
    *,
    strict: bool = False,
    prefix: str = "",
) -> Tuple[bool, List[str], List[str]]:
    """Compare target config dictionary against reference schema.

    Returns:
        Tuple of (is_valid: bool, errors: list[str], warnings: list[str])
    """
    errors: List[str] = []
    warnings: List[str] = []

    # 1. Check keys present in reference
    for key, ref_val in reference.items():
        if key.startswith("_comment"):
            continue

        full_key = f"{prefix}.{key}" if prefix else key

        if key not in target:
            msg = f"Missing key: '{full_key}'"
            if strict or key in CRITICAL_KEYS:
                errors.append(msg)
            else:
                warnings.append(msg)
            continue

        tgt_val = target[key]

        # Type check
        if not _check_types_compatible(ref_val, tgt_val, full_key):
            errors.append(
                f"Type mismatch for '{full_key}': expected {type(ref_val).__name__}, "
                f"got {type(tgt_val).__name__}"
            )
            continue

        # Nested dict check
        if isinstance(ref_val, dict) and isinstance(tgt_val, dict):
            _, sub_errs, sub_warns = audit_config_dicts(
                ref_val, tgt_val, strict=strict, prefix=full_key
            )
            errors.extend(sub_errs)
            warnings.extend(sub_warns)

        # String placeholder check
        if isinstance(tgt_val, str):
            for ph in PLACEHOLDER_SUBSTRINGS:
                if ph in tgt_val:
                    warnings.append(
                        f"Placeholder credential detected in '{full_key}': '{tgt_val}'"
                    )

    # 2. Check for unknown keys in target
    for key in target.keys():
        if key.startswith("_comment"):
            continue
        if key not in reference:
            full_key = f"{prefix}.{key}" if prefix else key
            warnings.append(f"Unknown or undocumented key: '{full_key}'")

    # 3. Miners validation if present
    if "miners" in target and isinstance(target["miners"], list):
        if len(target["miners"]) == 0:
            warnings.append("Miners list is empty; no hardware targets configured")
        else:
            for idx, miner in enumerate(target["miners"]):
                if not isinstance(miner, dict):
                    errors.append(f"Miner at index {idx} must be a dictionary")
                    continue
                name = miner.get("name")
                host = miner.get("host") or miner.get("ip")
                if not name:
                    warnings.append(f"Miner at index {idx} is missing 'name'")
                if not host:
                    errors.append(f"Miner '{name or idx}' is missing 'host' or 'ip'")

    is_valid = len(errors) == 0
    return is_valid, errors, warnings


def audit_config_files(
    reference_path: Path,
    target_path: Path,
    *,
    strict: bool = False,
) -> Tuple[bool, List[str], List[str]]:
    """Load JSON files and perform audit comparison."""
    if not reference_path.exists():
        return False, [f"Reference configuration not found: {reference_path}"], []

    try:
        with open(reference_path, "r", encoding="utf-8") as f:
            ref_dict = json.load(f)
    except Exception as exc:
        return False, [f"Failed to read reference configuration: {exc}"], []

    if not target_path.exists():
        return False, [f"Target configuration file not found: {target_path}"], []

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            tgt_dict = json.load(f)
    except Exception as exc:
        return False, [f"Failed to parse target JSON file: {exc}"], []

    return audit_config_dicts(ref_dict, tgt_dict, strict=strict)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit miner-alerts config file against reference schema."
    )
    parser.add_argument(
        "--reference",
        "-r",
        type=Path,
        default=Path("app/config.example.json"),
        help="Path to reference schema (default: app/config.example.json)",
    )
    parser.add_argument(
        "--target",
        "-t",
        type=Path,
        default=Path("app/config.json"),
        help="Path to target configuration (default: app/config.json)",
    )
    parser.add_argument(
        "--strict",
        "-s",
        action="store_true",
        help="Treat missing optional keys as errors instead of warnings",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress warnings, only output errors",
    )

    args = parser.parse_args()

    ok, errors, warnings = audit_config_files(
        args.reference, args.target, strict=args.strict
    )

    if not args.quiet:
        for w in warnings:
            print(f"[WARN]  {w}")

    for e in errors:
        print(f"[ERROR] {e}")

    if ok:
        print(f"[OK]    Configuration audit PASSED ({len(warnings)} warnings)")
        return 0
    else:
        print(f"[FAIL]  Configuration audit FAILED with {len(errors)} error(s)")
        return 1


if __name__ == "__main__":
    sys.exit(main())
