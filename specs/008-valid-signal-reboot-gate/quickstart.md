# Quickstart: Valid Signal Gate Validation

```powershell
& ".\\.venv\\Scripts\\python.exe" -m py_compile app\\miner_monitor.py
& ".\\.venv\\Scripts\\python.exe" -m unittest discover -s tests -v
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
& ".agents\\skills\\speckit-qa\\scripts\\preflight.ps1" -RunBuilds
```

Do not run a second monitor process while the Windows service is active. Runtime
QA and service restart are deferred to the explicit end-of-day release step.
