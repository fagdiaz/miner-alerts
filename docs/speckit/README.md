# Miner Alerts — Speckit Guide

Esta carpeta centraliza el marco documental y operativo para mejoras estructuradas en Miner Alerts.
Permite planificar, validar y auditar cambios seguros en producción: reducción de falsas alarmas, alta disponibilidad, seguridad de autorreinicios, diagnóstico forense, experiencia de operador en Telegram y gobernanza térmica/energética.

---

## Mapa Documental (Document Map)

### 1. Documentación Operativa Viva (Living Operational Docs)

| Documento | Propósito Principal |
|---|---|
| [`ROADMAP.md`](ROADMAP.md) | **Backlog maestro de trabajo**, cola de entregas, matriz de riesgos y estado de ejecución de specs (Specs 001 a 073 completadas). |
| [`RUNBOOK.md`](RUNBOOK.md) | **Manual de operaciones y procedimientos**: catálogo completo de comandos Telegram, simulacros de contingencia, hot backup/restore y recuperación de caídas. |
| [`SPEC_PROGRAM.md`](SPEC_PROGRAM.md) | **Marco programático**: secuencia formal de especificaciones, límites arquitectónicos, clases de riesgo y Criterio de Finalización (DoD). |
| [`DELIVERY_PLAN.md`](DELIVERY_PLAN.md) | **Calendario de entrega y estabilización**: ventanas de implementación, periodos de observación (soak) y control de cambios. |
| [`MINER_DIAGNOSTICS.md`](MINER_DIAGNOSTICS.md) | **Manual de herramientas de diagnóstico**: contrato de adquisición y modelo de evidencia de `tools/miner_diagnostics.py`. |
| [`TECHNOLOGY_STRATEGY.md`](TECHNOLOGY_STRATEGY.md) | **Estrategia tecnológica y arquitectura**: reglas de adopción para polling vs WebSockets, SQLite WAL v5, Prometheus/Grafana, Docker, MQTT y Named Pipes. |
| [`rfcs/README.md`](rfcs/README.md) | **Directorio de RFCs**: propuestas de diseño arquitectónico y de experiencia de usuario antes de su traducción a specs. |

### 2. Documentos Históricos y Decisiones Cerradas ([`archive/`](archive/README.md))

Documentos estratégicos puntuales y planes de acción cerrados que alcanzaron su objetivo terminal:
- [`archive/HASHCORE_TOOLKIT_STRATEGY.md`](archive/HASHCORE_TOOLKIT_STRATEGY.md): Inventario inicial de capacidades Hashcore (Spec 026).
- [`archive/INTERFACE_STRATEGY.md`](archive/INTERFACE_STRATEGY.md): Evaluación de interfaz web / FastAPI (Spec 027; decisión formal `no_build`).
- [`archive/V3_EXPANSION_PLAN.md`](archive/V3_EXPANSION_PLAN.md): Plan de expansión Telegram Max y V3 (Specs 031 a 038).
- [`archive/plans/`](archive/README.md): Planes de acción cerrados de modularización V5, horizonte V5.1 y saneamiento de repositorio (Specs 056 a 073).

### 3. Registro Maestro de Cambios y Auditoría

- **La Joya del Proyecto**: [`../audit/DEVELOPMENT_LOG.md`](../audit/DEVELOPMENT_LOG.md).
  Historial cronológico inverso (newest-first) inmutable de cada spec, release, benchmark y auditoría técnica ejecutada.

---

## Flujo de Trabajo (Workflow)

1. **Especificación**: Formalizar el requerimiento en `specs/<number>-<name>/spec.md`.
2. **Planificación**: Definir la arquitectura en `plan.md`.
3. **Desglose**: Crear tareas atómicas y ordenadas por dependencias en `tasks.md`.
4. **Implementación acotada**: Modificar código respetando los límites del spec y la Constitución.
5. **Evidencia y Validación**: Registrar comandos, salidas de prueba y telemetría real en `evidence.md`.
6. **Bitácora**: Añadir la entrada más reciente en `docs/audit/DEVELOPMENT_LOG.md`.
7. **Sincronización de Roadmap**: Actualizar `docs/speckit/ROADMAP.md` al completar el ciclo.

---

## Estado Actual del Sistema

- **Versión Certificada**: Release V5.1.0 (`specs/069-chain-telemetry-break-prediction`).
- **Capacidades V5.1 en Producción**:
  - Arquitectura desacoplada Clean Core (`app/core/`, `app/governance/`, `app/network/`, `app/interfaces/`, `app/ipc/`).
  - Pool SQLite WAL concurrente con lecturas de series temporales $< 15\text{ ms}$ y retención acotada.
  - Canal IPC de alta frecuencia Watchdog ↔ Monitor mediante Named Pipes (`\\.\pipe\MinerAlertsWatchdog`).
  - Diagnóstico predictivo de fallos de cadena (PROP-008 / Spec 069) con correlación eléctrica por elevador.
  - UX móvil compacta vertical ($\le 32$ columnas) y Centro de Control Táctil interactivo.
- **Estado de Specs**: 73 de 73 especificaciones completadas (100%).
- **Línea Base de Pruebas**: **1204/1204 tests PASS** (0 fallos, 0 errores, 0 regresiones).
- **Liveness en Producción**: Servicio Windows NT `MinerAlerts` activo bajo supervisión continua con cero spam en Telegram.

---

## Comandos y Validación Estándar

Ejecutar en PowerShell con el entorno virtual activo:

```powershell
# 1. Validación de sintaxis
& ".\.venv\Scripts\python.exe" -m py_compile app\miner_monitor.py
& ".\.venv\Scripts\python.exe" -m py_compile tools\miner_diagnostics.py

# 2. Suite de tests completa (unit, deterministic, integration)
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py"

# 3. Auditoría de congelamiento y release
& ".\.venv\Scripts\python.exe" tools\release_audit.py --check-only

# 4. Inspección de cambios
git status
git diff
```

Para validación controlada de comandos Telegram sin emitir a chats reales:
```powershell
$env:DBG_TELEGRAM="1"
$env:DBG_TELEGRAM_COMMANDS_ONLY="1"
```

---

## Reglas Críticas de Seguridad

1. **Archivos Locales**: Jamás versionar ni commitear `app/config.json`, `app/state.json`, tokens bot, chat IDs o dumps de producción.
2. **Autorreinicios**: Prohibido alterar la lógica de auto-reboot sin evidencia empírica en logs y aprobación explícita.
3. **Confirmación 2 Pasos**: Todas las acciones mutantes (`/reboot`, `/restart`, autotune o gobernador manual) requieren confirmación con código temporal (TTL 60s) o botón interactivo inline.
4. **Verificación Real**: La compilación sintáctica (`py_compile`) es obligatoria pero insuficiente; toda modificación requiere tests automatizados y verificación en runtime.
5. **Reinicio de Servicio**: Tras modificaciones en `app/miner_monitor.py` o módulos dependientes, reiniciar el servicio `MinerAlerts` para aplicar los cambios en caliente. Cambios exclusivos de documentación `.md` no requieren reinicio de proceso.
