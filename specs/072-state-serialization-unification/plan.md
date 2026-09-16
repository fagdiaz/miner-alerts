# Plan de Implementación — Spec 072: Unificación de Serialización de Estado & Desacoplamiento de Shims Redundantes (P2)

**ID**: 072  
**Rama**: `codex/022-adaptive-acquisition`  
**Estado**: Planificado  

---

## 1. Diseño Técnico

### 1.1 Unificación de Serialización en `StateManager`
- `StateManager._serialize_state(state)` es el método autoritativo que convierte una instancia de `MinerState` a un diccionario primitivo.
- Hacer que `_build_state_payload(states: Dict[str, MinerState]) -> Dict[str, Any]` en `app/miner_monitor.py` invoque directamente la serialización centralizada de `StateManager` o use `StateManager.serialize_state(state)` expuesto estáticamente/como función de módulo.

### 1.2 Helper `find_assessment_by_target` en `app/telegram/common.py` o módulo compartido
- Extraer la lógica de emparejamiento de mineros contra assessments:
  ```python
  def find_assessment_by_target(assessments: Sequence[Any], target_id: str) -> Optional[Any]:
      ...
  ```
- Simplificar los manejadores de comandos de Telegram correspondientes.

### 1.3 Centralización de `_dicts`
- Unificar la utilidad de tuplas a dicts en `app/core/helpers.py` o `app/core/mining_quality.py`.

---

## 2. Plan de Verificación & Testing

1. **Test de Paridad de Serialización (`tests/test_state_serialization_parity.py`)**:
   - Comparar byte a byte la salida de `_build_state_payload` antes y después de la delegación.
2. **Test de Búsqueda de Assessment (`tests/test_assessment_resolver.py`)**:
   - Verificar resolución por ID corto, nombre completo, IP, y caso no encontrado.
3. **Validación Global**:
   - $\ge 1079$ tests PASS.
   - `py_compile` en todos los archivos modificados.
