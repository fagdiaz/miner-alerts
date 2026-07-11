# Historial de Desarrollo y Cambios - Miner Alerts

Este archivo registra las specs y cambios completados que tienen respaldo en el codigo, la documentacion o evidencia operativa vigente, en orden cronologico inverso.
La entrada mas reciente debe agregarse inmediatamente debajo de este bloque.

---

## [2026-07-11] - Spec 004: Diagnostics Baseline Sweet Spot

* **Objetivo**: Convertir snapshots read-only en una linea base por minero para identificar variacion normal, evidencia de Vnish y seniales que deben observarse antes de cambiar politicas de reboot.
* **Resultado**:
  - Se agrego `tools/diagnostics_baseline.py` como analizador standalone de `snapshot.json`.
  - El analizador acepta un archivo o directorio, agrega muestras por minero y genera `baseline.md` + `baseline.json`.
  - El reporte incluye muestra, confianza, banda TH/s, boards, banda de temperatura maxima, `chain_vol`, `chain_consumption`, frecuencia y hardware errors.
  - La confianza queda `low` con una sola muestra para evitar conclusiones prematuras.
  - La documentacion incorpora el comando operativo para construir baseline desde `diagnostics/latest/snapshot.json`.
  - Se documento una estrategia de adopcion tecnologica para Docker, FastAPI, SQLite/DuckDB, Prometheus/Grafana y dashboards read-only.
* **Validaciones ejecutadas**:
  - `& ".\\.venv\\Scripts\\python.exe" -m py_compile tools\\diagnostics_baseline.py tools\\miner_diagnostics.py app\\miner_monitor.py`: PASS.
  - `& ".\\.venv\\Scripts\\python.exe" tools\\diagnostics_baseline.py --input diagnostics\\latest\\snapshot.json --out diagnostics\\baseline`: PASS.
  - `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force; & ".agents\\skills\\speckit-qa\\scripts\\preflight.ps1" -RunBuilds`: PASS.
* **Estado**:
  - Implementado y validado con el snapshot real de Spec 003. El baseline actual tiene confianza baja por contar con una sola muestra; se requieren multiples snapshots para convertirlo en politica.
* **Archivos principales**:
  - `tools/diagnostics_baseline.py`
  - `docs/speckit/RUNBOOK.md`
  - `docs/speckit/ROADMAP.md`
  - `docs/speckit/MINER_DIAGNOSTICS.md`
  - `docs/speckit/TECHNOLOGY_STRATEGY.md`
  - `specs/004-diagnostics-baseline-sweet-spot/*`

## [2026-07-11] - Spec 003: Read-Only Miner Diagnostics

* **Objetivo**: Agregar una herramienta read-only para recolectar evidencia de mineros antes de cambiar politicas de alertas, auto-reboot o UX operativa, manteniendo intacto el monitor en produccion.
* **Resultado**:
  - Se agrego `tools/miner_diagnostics.py` como colector standalone para API 4028 (`summary`, `stats`, `pools`, `version`).
  - El colector genera `summary.md` y `snapshot.json` sanitizados, con redaccion de usuarios de pool y sin exponer secretos de Telegram.
  - Se agrego `--dry-run` para validar config sin llamadas de red.
  - Se agrego `Dockerfile.diagnostics` para ejecutar solo el colector de diagnostico, sin dockerizar el monitor principal ni Hashcore Toolkit.
  - Se detectaron campos Vnish utiles para correlacion: `chain_vol`, `chain_consumption`, `freq_avg`, `chain_rate`, `chain_hw`, temperaturas chip/PCB y estado de pools.
  - `.gitignore` y `.dockerignore` cubren config real, state, logs, diagnostics, caches, envs y secretos.
* **Validaciones ejecutadas**:
  - `& ".\\.venv\\Scripts\\python.exe" -m py_compile app\\miner_monitor.py tools\\miner_diagnostics.py`: PASS.
  - `& ".\\.venv\\Scripts\\python.exe" tools\\miner_diagnostics.py --config app\\config.example.json --out diagnostics\\dry-run --dry-run`: PASS.
  - `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force; & ".agents\\skills\\speckit-qa\\scripts\\preflight.ps1" -RunBuilds`: PASS.
  - `git diff --check`: PASS.
  - Snapshot read-only contra `app/config.json`: PASS, 4/4 mineros respondieron por API 4028.
* **Estado**:
  - Implementado y validado localmente con dry-run y snapshot real read-only. Queda como siguiente paso construir baseline/sweet spot con multiples snapshots antes de tocar politica de reboot.
* **Archivos principales**:
  - `tools/miner_diagnostics.py`
  - `Dockerfile.diagnostics`
  - `.dockerignore`
  - `.gitignore`
  - `docs/speckit/RUNBOOK.md`
  - `docs/speckit/ROADMAP.md`
  - `docs/speckit/MINER_DIAGNOSTICS.md`
  - `specs/003-read-only-miner-diagnostics/*`
