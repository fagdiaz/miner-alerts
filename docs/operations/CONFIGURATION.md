# Configuración y datos locales

> Tipo: referencia operativa · Revisión: 2026-11-16.

## Archivos y autoridad

| Archivo | Responsabilidad |
|---|---|
| [app/config.example.json](../../app/config.example.json) | Referencia pública de claves y ejemplos; no es la configuración real |
| `app/config.json` | Parámetros y credenciales del host; excluido de Git |
| `app/state.json` | Continuidad operativa; no editar con el servicio activo |
| `data/miner_alerts.db` | Historial SQLite y decisiones; no sustituye el estado actual |
| `data/monitor_heartbeat.json` | Vida del monitor, timestamps y profundidad de cola |
| `data/miner_profiles/` | Perfiles locales de recuperación; pueden contener datos privados |

El arranque registra `CONFIG path=...` y un hash del archivo leído. La ruta puede
seleccionarse mediante `MINER_ALERTS_CONFIG` o `CONFIG_PATH`. Consultar
[app/core/config.py](../../app/core/config.py) para la resolución exacta.

## Modo QA

La config selecciona `qa_mode`. `QA_MODE` solo sustituye ese valor cuando
`QA_MODE_FORCE` lo habilita. Las acciones QA se controlan además por
`QA_ALLOW_REAL_ACTIONS` o `qa_allow_real_actions`. Validar el modo efectivo en logs;
no asumir que una variable suelta cambió el proceso del servicio.

## Grupos principales

| Grupo | Claves o referencia | Qué revisar |
|---|---|---|
| Adquisición | `poll_seconds`, `threshold_ths`, `expected_boards` | Unidad, frescura y procedencia de las muestras |
| Transiciones | `fails_before_alert`, `recovery_successes` | Histeresis de estados y cierre de episodios |
| Telegram | `telegram`, dedupe/coalescing, recordatorios | Cola, entrega y respuestas a comandos |
| Intervenciones | Startup, cooldowns, ventanas, retries | QA y permisos antes de actuar |
| VNish y potencia | Presets, grupos eléctricos y switcher | Techo individual, banda nativa y perfil de recuperación |
| Protección térmica | `emergency_thermal_*` | Downstep, pausa, reanudación y asentamiento |
| Liveness | `liveness` | Heartbeat, watchdog y leases de mantenimiento |
| Backup | `backup` | Roots disjuntos, frescura, lock y duración del job |
| Diagnóstico | Ventanas, límites y colección de firmware | Origen y edad de la evidencia |

Los nombres y defaults detallados se leen del ejemplo y del código. No se mantienen
copias de todos los valores en cada manual; las políticas locales se identifican en
un [corte fechado](PRODUCTION_BASELINE.md).

## Aplicación de cambios

El monitor lee código y configuración al arrancar. Un cambio validado de configuración
local requiere recarga controlada para que el proceso lo use. Verificar hash y PID,
no solo que el archivo se guardó. Los perfiles de recuperación y los ajustes reales
VNish deben coincidir cuando se cambie una política de hardware.

Una edición documental no requiere recarga. Cambiar defaults de ejemplo tampoco
actualiza automáticamente app/config.json. No modificar el estado ni restaurar un
perfil viejo para resolver una discrepancia sin revisar sus efectos.

## Secretos y conservación

No incluir tokens, chat_ids reales, contraseñas, workers o volcados completos de
configuración en Git, capturas de documentación o conversaciones. Mantener evidencias
locales fuera del catálogo público. Si se expuso un token en un log antiguo, tratarlo
como un incidente de credenciales y rotarlo antes de difundir ese log.
