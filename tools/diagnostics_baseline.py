#!/usr/bin/env python3
"""
Build a read-only sweet-spot baseline from diagnostics snapshots.

This tool consumes outputs from tools/miner_diagnostics.py. It does not contact
miners, call Hashcore Toolkit, or modify app/state.json.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_snapshot(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid snapshot JSON {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"Snapshot root is not an object: {path}")
    data["_source_path"] = str(path)
    return data


def find_snapshots(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    if not input_path.exists():
        raise SystemExit(f"Input path not found: {input_path}")
    return sorted(path for path in input_path.rglob("snapshot.json") if path.is_file())


def numeric(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def candidate_numbers(candidate_fields: dict[str, Any], token: str) -> list[float]:
    values: list[float] = []
    token_lower = token.lower()
    for key, value in candidate_fields.items():
        if token_lower not in str(key).lower():
            continue
        num = numeric(value)
        if num is not None:
            values.append(num)
    return values


def confidence(sample_count: int) -> str:
    if sample_count >= 12:
        return "high"
    if sample_count >= 4:
        return "medium"
    return "low"


def avg(values: list[float]) -> float | None:
    return round(statistics.fmean(values), 3) if values else None


def minmax(values: list[float]) -> tuple[float | None, float | None]:
    return (round(min(values), 3), round(max(values), 3)) if values else (None, None)


def mode_or_none(values: list[int]) -> int | None:
    if not values:
        return None
    return Counter(values).most_common(1)[0][0]


def aggregate(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for snapshot in snapshots:
        for miner in snapshot.get("miners", []):
            if isinstance(miner, dict):
                key = str(miner.get("id") or miner.get("name") or miner.get("host") or "unknown")
                grouped[key].append(miner)

    miners: list[dict[str, Any]] = []
    for miner_id, samples in sorted(grouped.items()):
        rates = [value for value in (numeric(sample.get("rate_ths")) for sample in samples) if value is not None]
        boards = [
            int(value)
            for value in (numeric(sample.get("active_boards")) for sample in samples)
            if value is not None
        ]
        max_temps: list[float] = []
        chain_vol: list[float] = []
        chain_consumption: list[float] = []
        freq_avg: list[float] = []
        chain_hw: list[float] = []
        responded_count = 0
        hosts = []
        names = []

        for sample in samples:
            if sample.get("responded"):
                responded_count += 1
            if sample.get("host"):
                hosts.append(str(sample.get("host")))
            if sample.get("name"):
                names.append(str(sample.get("name")))
            temps = [numeric(value) for value in sample.get("temperatures_c", [])]
            temps = [value for value in temps if value is not None]
            if temps:
                max_temps.append(max(temps))
            fields = sample.get("candidate_fields") if isinstance(sample.get("candidate_fields"), dict) else {}
            chain_vol.extend(candidate_numbers(fields, "chain_vol"))
            chain_consumption.extend(candidate_numbers(fields, "chain_consumption"))
            freq_avg.extend(candidate_numbers(fields, "freq_avg"))
            chain_hw.extend(candidate_numbers(fields, "chain_hw"))

        rate_min, rate_max = minmax(rates)
        temp_min, temp_max = minmax(max_temps)
        miners.append(
            {
                "id": miner_id,
                "name": names[-1] if names else miner_id,
                "host": hosts[-1] if hosts else "",
                "samples": len(samples),
                "confidence": confidence(len(samples)),
                "responded_ratio": round(responded_count / len(samples), 3) if samples else 0,
                "rate_ths_avg": avg(rates),
                "rate_ths_min": rate_min,
                "rate_ths_max": rate_max,
                "boards_mode": mode_or_none(boards),
                "max_temp_c_min": temp_min,
                "max_temp_c_max": temp_max,
                "chain_vol_avg": avg(chain_vol),
                "chain_consumption_avg": avg(chain_consumption),
                "freq_avg": avg(freq_avg),
                "chain_hw_total": round(sum(chain_hw), 3) if chain_hw else 0,
                "operator_note": operator_note(len(samples), rates, boards, max_temps),
            }
        )

    return {
        "generated_at": utc_now_iso(),
        "snapshot_count": len(snapshots),
        "miners": miners,
    }


def operator_note(sample_count: int, rates: list[float], boards: list[int], max_temps: list[float]) -> str:
    if sample_count < 4:
        return "baseline confidence low; capture more snapshots before policy changes"
    if boards and min(boards) < max(boards):
        return "board count varied across samples; investigate before reboot policy changes"
    if max_temps and max(max_temps) >= 85:
        return "temperature peak high; investigate cooling before reboot policy changes"
    if rates and min(rates) < statistics.fmean(rates) * 0.8:
        return "hashrate variance high; correlate with pools, Vnish and power telemetry"
    return "stable baseline candidate; continue collecting evidence"


def write_outputs(report: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "baseline.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Miner Sweet-Spot Baseline",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Snapshot count: {report['snapshot_count']}",
        "",
        "| Miner | Samples | Confidence | TH/s Avg | TH/s Band | Boards | Max Temp Band | Chain Vol Avg | Consumption Avg | HW Total | Note |",
        "| --- | ---: | --- | ---: | --- | ---: | --- | ---: | ---: | ---: | --- |",
    ]
    for miner in report["miners"]:
        rate_band = f"{miner['rate_ths_min']} - {miner['rate_ths_max']}" if miner["rate_ths_min"] is not None else "N/A"
        temp_band = f"{miner['max_temp_c_min']} - {miner['max_temp_c_max']}" if miner["max_temp_c_min"] is not None else "N/A"
        lines.append(
            "| {name} | {samples} | {confidence} | {rate_avg} | {rate_band} | {boards} | {temp_band} | {vol} | {cons} | {hw} | {note} |".format(
                name=miner["name"],
                samples=miner["samples"],
                confidence=miner["confidence"],
                rate_avg=miner["rate_ths_avg"] if miner["rate_ths_avg"] is not None else "N/A",
                rate_band=rate_band,
                boards=miner["boards_mode"] if miner["boards_mode"] is not None else "N/A",
                temp_band=temp_band,
                vol=miner["chain_vol_avg"] if miner["chain_vol_avg"] is not None else "N/A",
                cons=miner["chain_consumption_avg"] if miner["chain_consumption_avg"] is not None else "N/A",
                hw=miner["chain_hw_total"],
                note=miner["operator_note"],
            )
        )
    lines.extend(
        [
            "",
            "## Policy",
            "",
            "- This baseline is descriptive evidence only.",
            "- Do not change auto-reboot policy from low-confidence samples.",
            "- AC input voltage is not inferred from chain voltage or consumption fields.",
        ]
    )
    (out_dir / "baseline.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a read-only diagnostics baseline")
    parser.add_argument("--input", default="diagnostics", help="Snapshot file or directory containing snapshot.json files")
    parser.add_argument("--out", default="diagnostics/baseline", help="Output directory")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    paths = find_snapshots(Path(args.input).resolve())
    if not paths:
        raise SystemExit(f"No snapshot.json files found under {args.input}")
    report = aggregate([load_snapshot(path) for path in paths])
    out_dir = Path(args.out).resolve()
    write_outputs(report, out_dir)
    print(f"Wrote baseline: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
