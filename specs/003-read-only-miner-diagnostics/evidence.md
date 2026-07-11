# Evidence: Read-Only Miner Diagnostics

## Local Validation

Passed:

```powershell
& ".\\.venv\\Scripts\\python.exe" -m py_compile app\\miner_monitor.py tools\\miner_diagnostics.py
& ".\\.venv\\Scripts\\python.exe" tools\\miner_diagnostics.py --config app\\config.example.json --out diagnostics\\dry-run --dry-run
```

Observed dry-run output:

```text
Wrote diagnostics: F:\02-ASIC - mineros\miner-alerts\diagnostics\dry-run
```

Generated files:

- `diagnostics/dry-run/summary.md`
- `diagnostics/dry-run/snapshot.json`

`diagnostics/` is ignored by git.

Preflight passed:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force; & ".agents\\skills\\speckit-qa\\scripts\\preflight.ps1" -RunBuilds
```

Observed result:

```text
Status=PASS
FeatureDir=specs/003-read-only-miner-diagnostics
git-diff-check=PASS
```

## Production Evidence

Read-only snapshot completed against local `app/config.json` after allowing TCP
4028 from the Codex sandbox:

```powershell
& ".\\.venv\\Scripts\\python.exe" tools\\miner_diagnostics.py --config app\\config.json --out diagnostics\\latest --timeout 3
```

Observed output:

```text
Wrote diagnostics: F:\02-ASIC - mineros\miner-alerts\diagnostics\latest
```

Snapshot path:

- `diagnostics/latest/summary.md`
- `diagnostics/latest/snapshot.json`

Miner count: 4.

Observed summary:

| Miner | Status | TH/s | Boards | Power Fields | Observation |
| --- | --- | ---: | ---: | ---: | --- |
| S19JPRO-23 | RESPONDED | 100.707 | 3 | 6 | Healthy snapshot; use for baseline. |
| S19JPRO-24 | RESPONDED | 99.174 | 3 | 6 | Healthy snapshot; use for baseline. |
| S19JPRO-25 | RESPONDED | 92.851 | 3 | 6 | Healthy snapshot; lower but above threshold. |
| S19JPRO-26 | RESPONDED | 101.265 | 3 | 6 | Healthy snapshot; use for baseline. |

Candidate Vnish/power fields found:

- `chain_consumption1..3`
- `chain_vol1..3`
- `freq_avg1..3`
- `chain_rate1..3`
- `chain_hw1..3`
- chip/PCB temperature fields

Reboot policy observations:

- No miner was below the configured `threshold_ths=60.0` during the snapshot.
- All miners reported 3 active boards through Vnish-style `chain_acn1..3`.
- Power telemetry is firmware-exposed board/chain telemetry, not confirmed AC input voltage.
- Next quick win: convert repeated snapshots into a baseline/sweet-spot profile before changing reboot policy.
