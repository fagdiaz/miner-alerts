# Observabilidad y liveness

> Tipo: referencia operativa · Revisión: 2026-11-16.

## Monitor y watchdog

El monitor publica heartbeat con PID y timestamps de tick, poller y sender. El watchdog
es un proceso independiente que revisa vida del monitor y SCM, notifica según su política
y participa en la supervisión de recuperación del servicio. No es un actor sobre mineros.

```powershell
& .\.venv\Scripts\python.exe tools\monitor_watchdog.py --config app\config.json --no-notify
Get-Content -LiteralPath .\data\monitor_heartbeat.json
Get-Content -LiteralPath .\logs\watchdog.log -Tail 10
```

La consulta no sustituye la verificación de salud de ASICs. El lease de mantenimiento
para una recarga planificada se explica en el [runbook](RUNBOOK.md).

## Métricas

[tools/metrics_exporter.py](../../tools/metrics_exporter.py) consume un snapshot
sanitizado; el path por defecto del contrato es `diagnostics/metrics/current.json`.
No acepta `--config`. Ejemplo de consulta puntual sin abrir un listener:

```powershell
& .\.venv\Scripts\python.exe tools\metrics_exporter.py --snapshot-path diagnostics\metrics\current.json --dry-run
```

Para un listener local expresamente habilitado:

```powershell
& .\.venv\Scripts\python.exe tools\metrics_exporter.py --host 127.0.0.1 --port 9100 --snapshot-path diagnostics\metrics\current.json
```

La frescura del snapshot debe demostrarse: un servidor HTTP accesible no asegura datos
actuales. [metrics_sync.py](../../tools/metrics_sync.py) es un productor auxiliar que
escribe snapshots; su presencia no demuestra ejecución continua ni integración automática.

## Dashboard estático

Lectura de SQLite y escritura de HTML local, sin controles de hardware:

```powershell
& .\.venv\Scripts\python.exe tools\operations_dashboard.py --db data\miner_alerts.db --out diagnostics\dashboard\index.html --hours 24
```

Regenerar la vista para actualizarla y revisar antigüedad de datos. No exponer archivos
privados ni montar configuración/credenciales en un contenedor de reportes.

## Stack Docker opcional: estado no certificado por esta revisión

El manifiesto real es [docker-compose.observability.yml](../../docker-compose.observability.yml).
No existe la antigua ruta observability/docker-compose.metrics.yml usada por manuales previos.

La inspección estática encuentra dos límites concretos que requieren una tarea de
infraestructura antes de promoverlo como una instalación operativa:

- [Dockerfile.metrics](../../Dockerfile.metrics) todavía intenta copiar app/metrics_snapshot.py,
  mientras el módulo actual es app/core/metrics_snapshot.py. El build no se ejecutó aquí.
- El manifiesto publica Prometheus en 127.0.0.1:9090, pero Grafana usa 3000:3000 y
  credenciales iniciales admin/admin. No afirmar que todo el stack está ligado a loopback.

Esta normalización no cambió Dockerfile, manifiestos, puertos o servicios. La corrección
y activación de infraestructura requieren su propia validación. No se presenta un comando
up como prueba de que ese despliegue funciona actualmente.
