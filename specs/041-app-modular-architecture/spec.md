# Spec 041: Arquitectura Modular y Reorganización de Dominios en `app/`

## Estado y Metadatos
- **ID**: `041-app-modular-architecture`
- **Prioridad**: P2 (Mantenibilidad Arquitectónica, Claridad Estructural y Cero Regresiones)
- **Estado**: ESPECIFICACIÓN APROBADA (Lista para Planificación e Implementación Iterativa)
- **Fecha**: 2026-09-08
- **Autor**: Antigravity (Gemini 3.8 Flash High - Pair Programming con Operador)
- **Dependencias**: Specs 001-040 (Línea base V3.1 con 587 tests pasando).

---

## 1. Contexto y Justificación

### 1.1 El Crecimiento Orgánico del Paquete `app/`
A lo largo de las 40 especificaciones desarrolladas en Miner Alerts (desde el endurecimiento inicial V1 hasta los gobernadores dinámicos V3.1), el paquete `app/` fue incorporando nuevos módulos especializados de forma continua. Actualmente, contiene **22 archivos `.py` en una única carpeta plana**:

```text
app/
├── miner_monitor.py          # Orquestador y entrypoint principal (317 KB)
├── acquisition.py            # Adquisición API 4028 y timeouts
├── alert_episodes.py         # Máquina de estados de episodios de alerta
├── daily_digest.py           # Reporte ejecutivo diario consolidado
├── energy_efficiency.py      # Telemetría y cálculo J/TH
├── event_store.py            # Almacén forense SQLite v5
├── evidence_fusion.py        # Motor de fusión multi-fuente (/diagnose)
├── fan_governor.py           # Gobernador térmico y modulación de ventiladores
├── fan_health.py             # Detección temprana de fallas mecánicas de coolers
├── liveness.py               # Watchdog y heartbeat
├── metrics_snapshot.py       # Snapshot para Prometheus exporter
├── mining_quality.py         # Análisis de shares rechazados y hardware errors
├── preset_balancer.py        # Balanceador de presets y sensibilidad de elevadores
├── reboot_safety.py          # Guardrails y límites de autorreinicio
├── restart_intelligence.py   # Clasificación de causas de reinicio
├── stability_profile.py      # Baselines estables y perfiles de minero
├── telegram_callbacks.py     # Despachador de botones inline 1-tap
├── telegram_charts.py        # Generación in-memory de gráficos PNG (/chart)
├── telegram_messages.py      # Mensajería y chunking de Telegram
├── telegram_snooze.py        # Modo mantenimiento temporal (/snooze)
├── vnish_client.py           # Cliente HTTP/REST autenticado para Vnish API
├── vnish_logs.py             # Parser y normalizador de logs de firmware
├── vnish_presets.py          # Detección de frecuencias, perfiles y autotuning
└── vnish_telemetry.py        # Telemetría complementaria de firmware
```

### 1.2 El Problema
Tener todos los módulos en la raíz de `app/`:
1. Dificulta la navegación visual y el onboarding rápido en el repositorio.
2. Mezcla responsabilidades dispares (comunicación con Telegram, llamadas REST a Vnish, algoritmos térmicos, y almacenamiento SQLite en el mismo nivel).
3. Incrementa el riesgo de acoplamiento accidental entre subsistemas independientes.

### 1.3 El Desafío Crítico: Cero Regresiones
Existen **587 tests automatizados** y múltiples herramientas (`tools/`) que importan directamente desde `app.<modulo>` (ej. `from app.fan_governor import FanGovernor`). Una reorganización precipitada o masiva rompería importaciones en cascada y pondría en riesgo la estabilidad del servicio en producción.

Por tanto, el operador exige un enfoque **cuidadoso, iterativo y con las fases necesarias**, garantizando:
- 100% de retrocompatibilidad mediante **fachadas / shims de re-exportación** (*Deprecation Facade Pattern*).
- Validación de que los 587 tests pasen en cada paso.
- Migración gradual organizada en 4 subpaquetes de dominio natural.

---

## 2. Diseño de la Arquitectura Objetivo

La estructura final mantendrá el punto de entrada y archivos locales en la raíz de `app/`, agrupando los módulos especializados en 4 dominios cohesivos:

```text
app/
├── miner_monitor.py              # Entry point y orquestador del loop de producción
├── config.example.json           # Plantilla de configuración
├── config.json                   # Configuración local de producción (no versionada)
├── state.json                    # Estado persistente del monitor (no versionado)
│
├── telegram/                     # DOMINIO 1: Bot, interfaz de usuario y gráficos
│   ├── __init__.py               # Re-exports unificados del dominio
│   ├── callbacks.py              # Inline keyboards y botones interactivos (antes telegram_callbacks.py)
│   ├── charts.py                 # Gráficos PNG en memoria (antes telegram_charts.py)
│   ├── messages.py               # Formateo y envío seguro (antes telegram_messages.py)
│   ├── snooze.py                 # Silenciamiento temporal (antes telegram_snooze.py)
│   └── daily_digest.py           # Reporte diario ejecutivo (antes daily_digest.py)
│
├── vnish/                        # DOMINIO 2: Integración con Firmware Vnish
│   ├── __init__.py               # Re-exports unificados del dominio
│   ├── client.py                 # Cliente REST autenticado (antes vnish_client.py)
│   ├── presets.py                # Frecuencias y autotuning (antes vnish_presets.py)
│   ├── logs.py                   # Parser de logs de firmware (antes vnish_logs.py)
│   └── telemetry.py              # Envoltorios de telemetría (antes vnish_telemetry.py)
│
├── governance/                   # DOMINIO 3: Control Térmico, Potencia y Salud Física
│   ├── __init__.py               # Re-exports unificados del dominio
│   ├── fan_governor.py           # Modulación inteligente de coolers (antes fan_governor.py)
│   ├── preset_balancer.py        # Balanceador de presets y elevadores (antes preset_balancer.py)
│   ├── fan_health.py             # Detección temprana de fallas mecánicas (antes fan_health.py)
│   └── energy_efficiency.py      # Supervisión de ratio J/TH (antes energy_efficiency.py)
│
├── core/                         # DOMINIO 4: Núcleo, Adquisición y Almacenamiento
│   ├── __init__.py               # Re-exports unificados del dominio
│   ├── acquisition.py            # API 4028 y timeouts aislados
│   ├── event_store.py            # Base de datos SQLite EventStore v5
│   ├── alert_episodes.py         # Máquina de estados de incidentes
│   ├── evidence_fusion.py        # Motor forense /diagnose
│   ├── liveness.py               # Heartbeat y estado de salud
│   ├── metrics_snapshot.py       # Exposición Prometheus
│   ├── mining_quality.py         # Control de shares y hardware errors
│   ├── reboot_safety.py          # Políticas de seguridad de autorreinicio
│   ├── restart_intelligence.py   # Clasificación de causas de reboot
│   └── stability_profile.py      # Baselines estables
│
└── [shims retrocompatibles]      # Archivos puente en app/ que garantizan cero roturas
```

---

## 3. Protocolo de Shims Retrocompatibles (Garantía Cero Rotura)

Para cada archivo que se mueva a un subpaquete, se mantendrá un archivo shim en `app/` con el nombre original. Por ejemplo, `app/fan_governor.py` contendrá:

```python
"""Shim de retrocompatibilidad para app.governance.fan_governor.

Este archivo preserva las importaciones existentes de tests, scripts
y herramientas externas mientras se completa la transición.
"""
from app.governance.fan_governor import *  # noqa: F401, F403
```

### Beneficios del Protocolo de Shims:
1. **Ningún test falla**: Cualquier suite o test unitario que invoque `from app.fan_governor import FanGovernor` sigue funcionando sin modificación.
2. **Ningún tool falla**: Herramientas auxiliares (`tools/miner_diagnostics.py`, `tools/metrics_exporter.py`, etc.) siguen funcionando intactas.
3. **El servicio de producción no se interrumpe**: NSSM no sufrirá errores de importación al recargar módulos.

---

## 4. Fases de Implementación Iterativa

El trabajo se estructurará en **6 iteraciones controladas**:

| Iteración | Alcance | Tareas Clave | Criterio de Pase |
|---|---|---|---|
| **Iteración 1** | Planificación, Blueprint y Checklist | Generar `plan.md`, `tasks.md`, `checklists/requirements.md` y mapa de dependencias. | Aprobación de arquitectura. |
| **Iteración 2** | Dominio Telegram (`app/telegram/`) | Mover `telegram_*.py` y `daily_digest.py` a `app/telegram/`. Crear `__init__.py` y shims en `app/`. | 587 tests PASS. Commit feature-scoped. |
| **Iteración 3** | Dominio Vnish (`app/vnish/`) | Mover `vnish_*.py` a `app/vnish/`. Crear `__init__.py` y shims en `app/`. | 587 tests PASS. Commit feature-scoped. |
| **Iteración 4** | Dominio Governance (`app/governance/`) | Mover `fan_governor.py`, `preset_balancer.py`, `fan_health.py`, `energy_efficiency.py`. Crear shims. | 587 tests PASS. Commit feature-scoped. |
| **Iteración 5** | Dominio Core (`app/core/`) | Mover módulos de adquisición, persistencia y liveness a `app/core/`. Crear shims. | 587 tests PASS. Commit feature-scoped. |
| **Iteración 6** | Modernización Progresiva de Imports y Cierre | Actualizar imports internos en `app/miner_monitor.py` y `tools/`. Ejecutar release audit y actualizar bitácoras. | 587 tests PASS + Release Audit PASS. |

---

## 5. Criterios de Éxito Medibles

- **SC-001**: 100% de los 587 tests automatizados existentes continúan pasando sin fallos ni errores tras cada una de las 6 iteraciones.
- **SC-002**: La sintaxis de todos los archivos (`py_compile`) se valida sin errores en cada iteración.
- **SC-003**: `tools/release_audit.py --check-only` valida exitosamente el digest de payload de release.
- **SC-004**: Los 4 subdirectorios (`app/telegram/`, `app/vnish/`, `app/governance/`, `app/core/`) cuentan con `__init__.py` documentados y re-exportaciones canónicas.
- **SC-005**: El servicio Windows `MinerAlerts` opera de forma continua sin caídas por importaciones circulares o módulos faltantes.
