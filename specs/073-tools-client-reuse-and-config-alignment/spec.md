# Spec 073: Reutilización de Clientes en Tools & Alineación de Configuración (P3)

**ID**: 073  
**Rama**: `codex/022-adaptive-acquisition`  
**Prioridad**: P3 (Baja / Deuda Técnica & Mantenibilidad)  
**Estado**: Planificado  

---

## 1. Problema y Contexto

Durante la auditoría exhaustiva del repositorio se identificaron oportunidades de mejora en herramientas de soporte y pruebas:

1. **Reimplementación de Sockets en Herramientas**:
   - `tools/miner_diagnostics.py` y `tools/debug_4028.py` implementan su propia lógica ad-hoc de apertura de sockets TCP en el puerto 4028 con manejo manual de timeouts y stripping de bytes nulos (`\x00`).
   - La librería oficial `app.network.cgminer_client` ya implementa `query_cgminer` y `CGMinerClient` de forma testeada, robusta y tolerante.

2. **Divergencia entre `config.example.json` y Esquema de Producción**:
   - `app/config.example.json` contiene más de 160 claves documentadas de todas las especificaciones implementadas. Sin embargo, no existe una herramienta automatizada que verifique que las claves declaradas en `config.example.json` respeten los tipos esperados y detecte claves huérfanas o redundantes.
   - Es necesario un script `tools/audit_config.py` que audite cualquier archivo de configuración contra el esquema de referencia.

3. **Fixtures Duplicadas en Tests de Formato Compacto**:
   - `tests/test_compact_format.py` y `tests/test_compact_ux.py` replican diccionarios de estado de mineros y datos de telemetría de prueba muy similares.

---

## 2. Requerimientos Funcionales & Invariantes

- **RF-001**: `tools/miner_diagnostics.py` debe reutilizar `app.network.cgminer_client.query_cgminer` para todas las consultas CGMiner al puerto 4028, manteniendo intacta su interfaz CLI y generación de archivos JSON de evidencia.
- **RF-002**: `tools/debug_4028.py` debe ser refactorizado o delegar en `app.network.cgminer_client.query_cgminer` manteniendo su capacidad de diagnóstico rápido.
- **RF-003**: Crear `tools/audit_config.py` que compare dos configuraciones JSON (ej. `app/config.example.json` contra una configuración local) y reporte:
  * Claves presentes en el ejemplo pero ausentes localmente (con sus valores por defecto).
  * Claves desconocidas presentes localmente que no existan en el ejemplo.
  * Discrepancias de tipo (ej. entero vs cadena vs booleano).
- **RF-004**: Consolidar datos de prueba comunes en un módulo auxiliar `tests/fixtures_compact_ux.py` para evitar duplicación entre tests compactos.
- **RF-005**: Preservación total de los 37 contratos `inspect.getsource(main)` y no-regresión de la suite global ($\ge 1079$ tests PASS).
