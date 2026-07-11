# Quickstart: Miner Alerts Speckit

## Read Active Context

```powershell
Get-Content .specify\\feature.json
Get-Content .specify\\memory\\constitution.md
Get-Content specs\\001-miner-alerts-quality-hardening\\tasks.md
```

## Validate Python

```powershell
& ".\\.venv\\Scripts\\python.exe" -m py_compile app\\miner_monitor.py
```

## Review Current Work

```powershell
git status
git diff --stat
git diff
```

## Telegram QA Mode

```powershell
$env:DBG_TELEGRAM="1"
$env:DBG_TELEGRAM_COMMANDS_ONLY="1"
& ".\\.venv\\Scripts\\python.exe" app\\miner_monitor.py
```

## Evidence

Record executed checks in `evidence.md` before marking tasks complete.
