# Diagnóstico basado en evidencia

> Tipo: procedimiento y modelo de evidencia · Revisión: 2026-11-16.

## Fuentes y límites

| Fuente | Uso | Límite |
|---|---|---|
| API 4028 summary/stats | TH/s, uptime, placas, temperatura y señal actual | Una muestra aislada no determina la causa histórica |
| APIHTTP de VNish | Estado nativo y flags antes de posibles intervenciones | Frescura, timeouts y diferencias de firmware |
| LogsWS de VNish | Línea temporal de chainbreak, autotune y cambios nativos | Colector acotado; no sustituye la muestra de salud |
| SQLite | Eventos, telemetría, decisiones y correlación | Histórico; no autoriza por sí solo reinicios |
| PDU/UPS/medición técnica | EvidenciaAC independiente cuando exista | Actualmente no se identificó una fuenteAC integrada |
| Hashcore | Actuaciones explícitas y confirmadas | No es el transporte de supervisión continua |

Contar placas desconocidas como desconocidas, no como cero. Diferenciar ausencia,
antigüedad, invalidez y degradación. Toda conclusión identifica origen, timestamp y cobertura.

## Exportar un snapshot

Sin consultar mineros; escribe archivos en diagnostics/:

```powershell
& .\.venv\Scripts\python.exe tools\miner_diagnostics.py --config app\config.example.json --out diagnostics\dry-run --dry-run
```

Consulta de solo lectura a equipos, con configuración local:

```powershell
& .\.venv\Scripts\python.exe tools\miner_diagnostics.py --config app\config.json --out diagnostics\latest
```

Genera summary.md y snapshot.json sanitizado. No modifica state.json ni llama a Hashcore.
No compartir archivos sin revisar su contenido y la política de datos del host.

## Comparar snapshots e incidentes

```powershell
& .\.venv\Scripts\python.exe tools\diagnostics_baseline.py --input diagnostics\latest\snapshot.json --out diagnostics\baseline
& .\.venv\Scripts\python.exe tools\incident_report.py --db data\miner_alerts.db --hours 24 --format markdown --out diagnostics\incident-24h.md
```

La primera herramienta describe condiciones observadas; no activa un sweetspot ni
un preset. La segunda consume histórico local. No omitir tiempos sin producción
cuando se compare disponibilidad o TH efectivos.

## Firmware y correlación

Validar parsing sin persistencia, con una conexión acotada de lectura:

```powershell
& .\.venv\Scripts\python.exe tools\vnish_log_collector.py --config app\config.json --dry-run --tabs status --idle-timeout 1 --max-bytes 262144
```

`--dry-run` del colector de firmware sí puede contactar mineros; significa no persistir.
No confundirlo con el dry-run sin red de miner_diagnostics.py. La ejecución normal
persiste eventos normalizados en SQLite. El colectorWS es independiente del monitor y
mantiene límites por stream; no genera un canal de actuación.

Consultar `/events`, `/event <id>`, `/why`, `/firmware` y `/diagnose` para reconstruir
el episodio. Separar acción propuesta, acción exitosa registrada y reinicio observado.

## Conclusiones

- **Observado:** dato directo con origen, hora y ventana.
- **Inferido:** hipótesis compatible con varios hechos; explicitar incertidumbre.
- **Desconocido:** falta información o medición independiente.

Ante LOW, revisar señal, placas, temperatura, pool y estado nativo. Ante temperatura
baja después de un reinicio, considerar la recuperación a tier reducido. Ante fallas
simultáneas, conservar datos del grupo sin concluir automáticamente una falla de calle.
Los procedimientos previos se preservan como [histórico](../archive/documentation-20261116/docs/speckit/MINER_DIAGNOSTICS.md).
