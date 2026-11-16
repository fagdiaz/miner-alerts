# Miner Alerts

Supervisión de mineros ASIC en Windows, con telemetría API 4028, historial SQLite,
control de intervenciones y operación remota por Telegram. El firmware VNish y el
monitor comparten protecciones térmicas; los diagnósticos se conservan como evidencia.

## Documentación

- [Centro documental](docs/README.md): navegación por operación, arquitectura y desarrollo.
- [Operación diaria](docs/operations/RUNBOOK.md): consultas, incidentes y recarga controlada.
- [Instalación](docs/operations/INSTALLATION.md) y [configuración](docs/operations/CONFIGURATION.md).
- [Comandos Telegram](docs/operations/TELEGRAM.md).
- [Arquitectura](docs/architecture/SYSTEM_OVERVIEW.md).
- [Estado documentado](docs/operations/PRODUCTION_BASELINE.md): corte fechado, sin promesa de salud en vivo.
- [Backlog](docs/speckit/ROADMAP.md), [programa](docs/speckit/SPEC_PROGRAM.md) y [ventanas de entrega](docs/speckit/DELIVERY_PLAN.md).
- [Desarrollo y validación](docs/development/WORKFLOW.md).
- [Bitácora completa](docs/audit/DEVELOPMENT_LOG.md) e [índice cronológico](docs/audit/DEVELOPMENT_LOG_INDEX.md).

## Inicio en un entorno nuevo

Desde la raíz del checkout, crear un virtualenv e instalar las dependencias de
[requirements.txt](requirements.txt). Preparar el archivo local de configuración
siguiendo la guía de instalación antes de iniciar un monitor.

```powershell
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Una instancia ya instalada como servicio `MinerAlerts` se opera mediante NSSM/SCM.
Consultar su estado antes de lanzar procesos manuales. Los comandos anteriores son
instrucciones de instalación, no un paso necesario para una revisión documental.

## Fuentes y datos locales

- Reglas de trabajo: [AGENTS.md](AGENTS.md) y [constitución](.specify/memory/constitution.md).
- Feature activa: [.specify/feature.json](.specify/feature.json).
- Esquema de configuración pública: [app/config.example.json](app/config.example.json).
- Configuración y estado reales: `app/config.json` y `app/state.json`, locales y fuera de Git.
- Evidencias, backups y credenciales no se publican como documentación del proyecto.

La presencia de un procedimiento o una tarea marcada no certifica su ejecución.
Todo resultado de producción debe indicar fecha, ventana observada y evidencia.
