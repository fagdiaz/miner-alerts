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

## [2026-07-11] - Spec 002: Miner Diagnostics And Interface Roadmap

* **Objetivo**: Definir el roadmap tecnico para evolucionar Miner Alerts mas alla de alertas Telegram, cubriendo diagnostico antes de reboot, Hashcore Toolkit, Vnish, power telemetry e interfaz read-only.
* **Resultado**:
  - Se documento un roadmap por prioridades P0-P7 para reducir falsas alertas, evitar reboots innecesarios y mejorar observabilidad.
  - Se definio que Telegram permanece como superficie principal de acciones, mientras cualquier interfaz nueva debe empezar read-only.
  - Se documento una estrategia para Hashcore Toolkit: inventariar capacidades read-only vs acciones antes de integrar nuevos comandos.
  - Se definio una matriz de diagnostico para Vnish/S19j Pro: hash, boards, temperaturas, pool state, firmware hints, voltage/frequency/power fields y eventos de firmware.
  - Se aclaro que voltaje AC/input no debe inferirse automaticamente desde firmware salvo evidencia explicita; se deben considerar PDU/UPS/smart meter si hace falta.
* **Validaciones ejecutadas**:
  - Revision documental de `docs/speckit/ROADMAP.md`, `INTERFACE_STRATEGY.md`, `MINER_DIAGNOSTICS.md` y `HASHCORE_TOOLKIT_STRATEGY.md`: PASS.
  - No se realizaron cambios runtime en esta spec.
* **Estado**:
  - Roadmap y arquitectura de evolucion documentados. La implementacion real de diagnostico quedo iniciada posteriormente en Specs 003 y 004.
* **Archivos principales**:
  - `docs/speckit/ROADMAP.md`
  - `docs/speckit/INTERFACE_STRATEGY.md`
  - `docs/speckit/MINER_DIAGNOSTICS.md`
  - `docs/speckit/HASHCORE_TOOLKIT_STRATEGY.md`
  - `specs/002-miner-diagnostics-interface-roadmap/*`

## [2026-07-11] - Spec 001: Miner Alerts Quality Hardening

* **Objetivo**: Instalar una forma de trabajo Speckit para Miner Alerts, con foco en quick wins seguros: falsas alertas, seguridad de auto-reboot, confiabilidad Telegram, logs, hygiene de release y compatibilidad Windows/Hashcore.
* **Resultado**:
  - Se instalo `.specify/` desde el scaffold local probado en OneITB23.
  - Se instalaron skills Speckit bajo `.agents/skills/`, incluyendo `speckit-qa` adaptado a Miner Alerts.
  - Se creo la constitucion del proyecto en `.specify/memory/constitution.md` con reglas de seguridad: no secretos, no reboots sin evidencia, Telegram con confirmaciones y validacion Windows.
  - Se agrego `AGENTS.md` como instrucciones operativas para futuros agentes/Codex.
  - Se creo la base documental en `docs/speckit/` y specs iniciales para ordenar auditorias e implementaciones.
* **Validaciones ejecutadas**:
  - `& ".\\.venv\\Scripts\\python.exe" -m py_compile app\\miner_monitor.py`: PASS.
  - Verificacion de que la instalacion Speckit no cambiaba runtime del monitor: PASS.
* **Estado**:
  - Bootstrap Speckit completado. Las auditorias runtime y quick wins derivados quedaron como backlog y fueron desarrollados parcialmente en specs posteriores.
* **Archivos principales**:
  - `.specify/*`
  - `.agents/skills/*`
  - `.agents/skills/speckit-qa/*`
  - `AGENTS.md`
  - `docs/speckit/*`
  - `specs/001-miner-alerts-quality-hardening/*`
