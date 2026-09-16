# Spec 072: Unificación de Serialización de Estado & Desacoplamiento de Shims Redundantes (P2)

**ID**: 072  
**Rama**: `codex/022-adaptive-acquisition`  
**Prioridad**: P2 (Mantenibilidad & DRY)  
**Estado**: Implementado & Verificado  

---

## 1. Problema y Contexto

Durante la auditoría integral del repositorio `miner-alerts` se detectaron las siguientes duplicaciones y deudas técnicas de mantenibilidad:

1. **Duplicación de Serialización de MinerState**:
   - `app/miner_monitor.py:734` (`_build_state_payload()`) replica un diccionario con ~45 campos de `MinerState`.
   - `app/core/state_manager.py:270` (`_serialize_state()`) serializa exactamente los mismos ~45 campos.
   - Cualquier agregado o modificación a `MinerState` requiere cambios paralelos en ambos archivos, con riesgo de divergencia silenciosa.

2. **Resolución Repetitiva de Minero en Comandos Telegram**:
   - En 5 comandos (`/cooling`, `/efficiency`, `/profile`, `/governance`, `/preset`), existe una lógica idéntica de 15 líneas para buscar y emparejar el minero especificado por el usuario contra las evaluaciones de telemetría.
   - Debe extraerse a un helper unificado `find_assessment_by_target(assessments, target_miner)`.

3. **Duplicación de Generador `_dicts()`**:
   - Mismo helper de conveniencia para convertir tuplas de columnas en diccionarios definido repetidamente. Debe centralizarse en `app/core/mining_quality.py`.

4. **Limpieza de Shims Redundantes**:
   - Eliminación de wrappers obsoletos y alineación de importaciones directas.

---

## 2. Requerimientos Funcionales & Invariantes

- **RF-001**: La serialización en `_build_state_payload()` debe delegar estrictamente en `StateManager._serialize_state()`, garantizando idéntico formato JSON en `state.json`.
- **RF-002**: `find_assessment_by_target()` debe ser compatible con coincidencias por nombre exacto, IP/host o identificador corto (ej. `23` -> `S19JPRO-23`).
- **RF-003**: Preservación total de los 37 contratos `inspect.getsource(main)`.
- **RF-004**: Regresión total $\ge 1079$ tests PASS sin roturas.
