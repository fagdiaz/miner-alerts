# Plan de Implementación — Spec 072: Unificación de Serialización de Estado & Desacoplamiento de Shims Redundantes (P2)

**ID**: 072  
**Rama**: `codex/022-adaptive-acquisition`  
**Estado**: Planificado  

---

## 1. Diseño Técnico

### 1.1 Unificación de Serialización en `StateManager`
- `StateManager._serialize_state(state)` es el método autoritativo que convierte una instancia de `MinerState` a un diccionario primitivo.
- Hacer que `_build_state_payload(states: Dict[str, MinerState]) -> Dict[str, Any]` en `app/miner_monitor.py` invoque directamente la serialización centralizada de `StateManager` o use `StateManager.serialize_state(state)` expuesto estáticamente/como función de módulo.

### 1.2 Helper `find_assessment_by_target` y `format_miner_key` en `app/telegram/command_center.py`
- Extraer la lógica de emparejamiento de mineros contra assessments en `app/telegram/command_center.py` (evitando crear módulos redundantes y previniendo importaciones circulares):
  ```python
  def find_assessment_by_target(assessments: Sequence[Any], target_id: str, miners: Optional[Any] = None) -> Optional[Any]:
      ...
  def format_miner_key(miner: Dict[str, Any]) -> str:
      ...
  ```
- Simplificar los manejadores de comandos de Telegram correspondientes (`diagnostics.py`, `fans.py`, `reboot.py`, `maintenance.py`).

### 1.3 Centralización de `_dicts`
- Unificar la utilidad de tuplas a dicts en `app/core/mining_quality.py` e importar limpiamente en `app/vnish/telemetry.py`.

---

## 2. Plan de Verificación & Testing

1. **Test de Paridad de Serialización (`tests/test_state_serialization_parity.py`)**:
   - Comparar exhaustivamente las claves y tipos del diccionario de `_build_state_payload` contra `serialize_miner_state()`.
2. **Test de Búsqueda de Assessment y Keys (`tests/test_find_assessment_by_target.py`)**:
   - Verificar resolución por ID corto, nombre completo, IP, y caso no encontrado.
   - Verificar formateo seguro de claves de estado de mineros con clave `ip` o `host`.
3. **Validación Global**:
   - $\ge 1110$ tests PASS (0 fallos, 0 regresiones).
   - `py_compile` en todos los archivos modificados.
