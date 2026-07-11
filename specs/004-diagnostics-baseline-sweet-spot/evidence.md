# Evidence: Diagnostics Baseline Sweet Spot

## Local Validation

Passed:

```powershell
& ".\\.venv\\Scripts\\python.exe" -m py_compile tools\\diagnostics_baseline.py tools\\miner_diagnostics.py app\\miner_monitor.py
& ".\\.venv\\Scripts\\python.exe" tools\\diagnostics_baseline.py --input diagnostics\\latest\\snapshot.json --out diagnostics\\baseline
```

Observed output:

```text
Wrote baseline: F:\02-ASIC - mineros\miner-alerts\diagnostics\baseline
```

Generated files:

- `diagnostics/baseline/baseline.md`
- `diagnostics/baseline/baseline.json`

Baseline summary from one snapshot:

| Miner | Samples | Confidence | TH/s Avg | Boards | Max Temp C | Chain Vol Avg | Consumption Avg | HW Total |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| S19JPRO-23 | 1 | low | 100.707 | 3 | 78.0 | 12825.0 | 899.333 | 22.0 |
| S19JPRO-24 | 1 | low | 99.174 | 3 | 81.0 | 13225.0 | 899.333 | 0.0 |
| S19JPRO-25 | 1 | low | 92.851 | 3 | 72.0 | 12440.0 | 833.0 | 0.0 |
| S19JPRO-26 | 1 | low | 101.265 | 3 | 75.0 | 12940.0 | 899.667 | 0.0 |

Interpretation:

- Confidence is intentionally low because only one snapshot exists.
- This is enough to prove extraction and reporting, not enough to change reboot policy.
- Multiple snapshots across stable and alert periods are required before policy changes.

Preflight passed:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force; & ".agents\\skills\\speckit-qa\\scripts\\preflight.ps1" -RunBuilds
```

Observed result:

```text
Status=PASS
FeatureDir=specs/004-diagnostics-baseline-sweet-spot
git-diff-check=PASS
```
