# Informe de Auditoría Post-Corte de Luz: Estado del Proyecto y Comparativa Código vs Documentación

**Fecha y Hora**: 2026-10-08 14:05 UTC-3  
**Rama**: `codex/022-adaptive-acquisition` (Sincronizada con `origin`)  
**Último Commit**: `f8dea18 fix(pipeline): align record_auto_reboot_decision signature and handle kwargs defensively`  
**Estado General**: **OPERATIVO / ESTABILIZADO (V6.0)** con un **hallazgo correctivo puntual detectado en runtime**.

---

## 1. Resumen Ejecutivo de la Comparativa

| Área Evaluada | Estado Documentado (`docs/`) | Estado Real en Código / Runtime | Veredicto |
| :--- | :--- | :--- | :--- |
| **Monolito (`miner_monitor.py`)** | $\le 450$ LOC objetivo; 324 LOC reportadas | **324 líneas exactas** | **100% Coincidente** ✅ |
| **Pipeline Declarativo de Hooks** | 7 etapas ordenadas en `app/core/pipeline.py` | Implementado y operando en `app/core/engine.py` | **100% Coincidente** ✅ |
| **Árbol de Trabajo Git** | Clean post-Spec 091 | `working tree clean`, sin cambios pendientes ni archivos untracked | **100% Coincidente** ✅ |
| **Suite de Regresión** | 1528 tests PASS, 75 subtests PASS | **1528 passed, 75 subtests passed** (41.12s, 0 errores, 0 fallos) | **100% Coincidente** ✅ |
| **Servicio Windows (`MinerAlerts`)** | NSSM en ejecución continua | Proceso `nssm.exe` (PID 4848) y subprocesos `python.exe` activos desde las 13:16:19 | **100% Coincidente** ✅ |
| **Recuperación tras el Corte** | Fase `WARMING_UP` con avance normal | `logs/out.log` muestra avance (0.5s -> 30.5s -> ... -> 150.5s / 180s) | **100% Coincidente** ✅ |
| **Registros de Excepciones** | Sin excepciones en régimen estacionario | 1 excepción latente detectada a las 13:16:30 durante el primer tick de reinicio post-corte | **Acción requerida** ⚠️ |

---

## 2. Detalle de la Comparativa Código vs Documentación

### A. Estructura y Modularización del Monolito
* **Objetivo de Spec 091**: Disolver el bucle procedural de `main()` en [`app/miner_monitor.py`](../../app/miner_monitor.py) sustituyéndolo por [`CoreSupervisoryEngine`](../../app/core/engine.py).
* **Verificación**: 
  - `(Get-Content app\miner_monitor.py).Count` arroja exactamente **324 líneas** (de las >9.000 líneas históricas y 6.646 pre-Spec 091).
  - Los shims de re-exportación se encuentran en su lugar, manteniendo intactos los contratos públicos y de herramientas.
  - La arquitectura de 7 hooks (`PRE_TICK`, `ACQUISITION`, `DETECTION`, `GOVERNANCE`, `ACTUATOR`, `PERSISTENCE`, `POST_TICK`) está cableada y activa.

### B. Estado de Git y Persistencia
* No se perdieron cambios durante el corte de luz: el árbol de trabajo estaba limpio y los últimos commits fueron empujados al repositorio remoto (`origin/codex/022-adaptive-acquisition`).
* Los 5 commits de la secuencia de cierre figuran aplicados en el log local y remoto:
  1. `25f448f feat(hardware): decouple chain telemetry and diagnostic formatters (Spec 089)`
  2. `780404f test(invariants): modernize test contracts to black-box behavioral simulation (Spec 090)`
  3. `cb9438a feat(spec-091): core daemon hookification and monolith dissolution (v6.0 release)`
  4. `49bcc86 fix(core): implement active detection and actuation hooks in supervisory pipeline`
  5. `f8dea18 fix(pipeline): align record_auto_reboot_decision signature and handle kwargs defensively`

---

## 3. Hallazgo Crítico en Runtime Post-Corte Eléctrico

Al inspeccionar [`logs/err.log`](../../logs/err.log) tras el reinicio del sistema (13:16:30), se detectó que el evento del corte de luz provocó que los mineros fueran detectados como recién arrancados (`unexpected_restart` / `is_first_seen_restart`). Al entrar en esa rama específica de código, se disparó la siguiente excepción:

```text
hook=detection stage=DETECTION error=ImportError: cannot import name 'record_elevator_restart_circumstance' from 'app.governance.adaptive_contingency' (F:\02-ASIC - mineros\miner-alerts\app\governance\adaptive_contingency.py)
```

### Causa Raíz
En [`app/core/engine.py:1244`](../../app/core/engine.py):
```python
from app.governance.adaptive_contingency import record_elevator_restart_circumstance
```
Sin embargo, `record_elevator_restart_circumstance` reside canónicamente en [`app/governance/preset_balancer.py:779`](../../app/governance/preset_balancer.py) y está re-exportada en [`app/governance/__init__.py:184`](../../app/governance/__init__.py). No existe en `app.governance.adaptive_contingency`.

### Comportamiento del Sistema y Mitigación Inmediata
1. **El servicio no crasheó**: Gracias a la contención defensiva por etapa de [`app/core/engine.py:execute_tick()`](../../app/core/engine.py), la excepción fue atrapada en la etapa `DETECTION` y el monitor continuó ejecutándose normalmente.
2. **Impacto**: En el tick donde se detectó el reinicio de los mineros, no se pudo calcular ni registrar la circunstancia de carga eléctrica del elevador (`elev_circumstance`).
3. **Solución**:
   - Cambiar la importación en [`app/core/engine.py:1244`](../../app/core/engine.py) a `from app.governance.preset_balancer import record_elevator_restart_circumstance`.
   - Agregar un re-export defensivo en [`app/governance/adaptive_contingency.py`](../../app/governance/adaptive_contingency.py) para máxima compatibilidad retroactiva.
   - Añadir una prueba unitaria que ejecute esa rama específica para evitar regresiones futuras.
   - Reiniciar el servicio `MinerAlerts` para cargar el módulo limpio.

---

## 4. Estado de la Flota en Producción

Según [`logs/out.log`](../../logs/out.log) (últimos ticks 13:46:29):
* **S19JPRO-23** (Elevador 1): `HOLD_STABLE` en 2300W (0 reinicios).
* **S19JPRO-24** (Elevador 1): `STEP_DOWN_RESTARTS` a 2150W (protección por inestabilidad eléctrica tras el corte).
* **S19JPRO-25** (Elevador 2): `HOLD_STABLE` en 2500W.
* **S19JPRO-26** (Elevador 2): `HOLD_STABLE` en 2300W.
* **Deadlocks**: 0 en toda la flota.
* **Período de Gracia (`WARMING_UP`)**: Completado limpiamente sin bloqueos.
