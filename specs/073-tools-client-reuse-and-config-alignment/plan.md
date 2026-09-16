# Plan de Implementación — Spec 073: Reutilización de Clientes en Tools & Alineación de Configuración (P3)

**ID**: 073  
**Rama**: `codex/022-adaptive-acquisition`  
**Estado**: Planificado  

---

## 1. Diseño Técnico

### 1.1 Refactorización de Herramientas de Diagnóstico
- En `tools/miner_diagnostics.py`:
  - Reemplazar la función local `read_command` por una llamada a `app.network.cgminer_client.query_cgminer`.
  - Manejar excepciones de socket devolviendo la tupla `(parsed_dict, err_msg)`.
- En `tools/debug_4028.py`:
  - Usar `query_cgminer` para obtener la respuesta limpia y estructurada.

### 1.2 Auditor de Configuración `tools/audit_config.py`
- Crear script ejecutable con CLI:
  ```powershell
  python tools/audit_config.py --reference app/config.example.json --target app/config.json
  ```
- Salida estructurada con códigos de salida:
  - 0: Compatibilidad total o solo advertencias de claves opcionales faltantes.
  - 1: Errores de tipo o formato JSON inválido.

### 1.3 Consolidación de Fixtures de Testing
- Crear `tests/fixtures_compact_ux.py` con fábricas comunes de estados y muestras de telemetría.
- Importar en `tests/test_compact_format.py` y `tests/test_compact_ux.py`.

---

## 2. Plan de Verificación & Testing

1. **Test de Diagnósticos (`tests/test_miner_diagnostics_client.py`)**:
   - Simular respuestas de socket con mock y verificar que `tools/miner_diagnostics.py` procesa correctamente `summary`, `stats`, `pools`, `version`.
2. **Test de Auditor de Configuración (`tests/test_audit_config.py`)**:
   - Validar detección de tipos incompatibles y claves desconocidas.
3. **Validación Global**:
   - `py_compile` en `tools/miner_diagnostics.py`, `tools/debug_4028.py`, `tools/audit_config.py`.
   - $\ge 1079$ tests PASS.
