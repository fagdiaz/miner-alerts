# Feature Specification: Spec 059 — Network Protocols & Hardware Clients Extraction (MT-02)

**Feature Directory**: `specs/059-network-protocols-hardware-clients`  
**Created**: 2026-09-15  
**Status**: Draft  
**Initiative**: MT-02 (Horizonte V5.0 — Modularización Arquitectónica)  
**Input**: Extraer la comunicación de socket crudo TCP 4028 (protocolo CGMiner/Telnet JSON), los clientes de integración de hardware (Hashcore Toolkit CLI) y consolidar la interfaz cliente HTTP REST de Vnish fuera de `app/miner_monitor.py` en una arquitectura de clientes tipados y desacoplados bajo `app/network/` (`cgminer_client.py`, `hashcore_client.py`, `vnish_client.py`), con 100% de compatibilidad hacia atrás mediante fachadas, cero regresiones y preservando la suite completa de 910 tests.

---

## User Scenarios & Testing

### User Story 1 - Cliente Tipado y Robusto de Socket CGMiner 4028 (Priority: P1)

Como desarrollador del sistema de monitoreo, deseo que todas las consultas de bajo nivel por socket TCP 4028 (`summary`, `stats`, `pools`, `version`, conteo de placas hashboard y extracción térmica) estén encapsuladas en `app/network/cgminer_client.py`, con timeouts estrictos, reintentos defensivos, eliminación de bytes nulos (`\x00`), manejo de codificación UTF-8 resiliente y objetos de respuesta tipados, de modo que el bucle de monitoreo nunca se cuelgue por sockets colgados o JSONs corruptos.

**Why this priority**: La comunicación TCP 4028 es la arteria de datos vital de la que depende toda la telemetría, detección de incidentes y cálculo de hashrate de la flota ASIC.

**Independent Test**: Realizar llamadas unitarias a `query_cgminer`, `read_summary`, `read_stats_snapshot`, `read_stats_active_boards`, `read_pools`, `read_version` con mocks de socket simulando respuestas válidas, timeouts de conexión, respuestas truncadas y bytes nulos, verificando retorno determinista sin fugas de sockets.

**Acceptance Scenarios**:
1. **Given** un minero respondiendo en el puerto 4028, **When** se invoca `read_summary(host, port)`, **Then** se devuelve `(rate_ths, elapsed, responded=True, summary_dict)` parseado correctamente.
2. **Given** un minero que no responde o corta la conexión abruptamente, **When** se invoca `query_cgminer` o `read_summary`, **Then** se captura la excepción internamente y se retorna `(None, None, False, None)` sin lanzar excepciones no controladas.
3. **Given** una respuesta de stats con formatos heterogéneos de placas (`chain_acn`, `chain{i}_asicnum`, `chain{i}_alive`), **When** se ejecuta `count_active_boards(stats_entry)`, **Then** se calcula con precisión el número de placas activas.

---

### User Story 2 - Cliente Desacoplado de Hashcore Toolkit CLI (Priority: P1)

Como operador de la granja minera, deseo que la invocación y control del CLI de Hashcore Toolkit para reinicios (`run_hashcore_cli`), descubrimientos (`run_hashcore_discovery`) y resolución de rutas ejecutables esté encapsulada en `app/network/hashcore_client.py`, respetando estrictamente los guardarraíles de QA (`qa_mode`, `qa_allow_actions`), creación de procesos sin ventana en Windows y medición de latencia.

**Why this priority**: Hashcore es el actuador de hardware principal para reboots reales de los mineros. Cualquier error en el paso de argumentos o flags de subprocess en Windows puede bloquear el servicio o realizar acciones no deseadas.

**Independent Test**: Ejecutar pruebas unitarias de `run_hashcore_cli` en modo QA bloqueado, modo permitido y con comandos simulados, verificando la construcción precisa de argumentos y el manejo de subprocess timeouts.

**Acceptance Scenarios**:
1. **Given** el sistema en `qa_mode=True` y `qa_allow_actions=False`, **When** se invoca `run_hashcore_cli` para un reinicio, **Then** la acción es bloqueada de inmediato, retornando `(False, msg)` y emitiendo un log de advertencia sin llamar a subprocess.
2. **Given** una ruta válida de Toolkit CLI y `qa_allow_actions=True`, **When** se invoca `run_hashcore_cli`, **Then** se ejecuta el comando con `creationflags` sin ventana en Windows, registrando tiempo de ejecución y capturando stdout/stderr.

---

### User Story 3 - Cliente Formal y Tipado para la API REST de Vnish (Priority: P2)

Como mantenedor del sistema, deseo una interfaz unificada `VnishClient` en `app/network/vnish_client.py` que proporcione una abstracción orientada a objetos sobre las llamadas REST de Vnish (`/api/v1/unlock`, `/api/v1/lock`, `/api/v1/settings`, `/api/v1/fans`, `/api/v1/mining/restart`, `/api/v1/overclock`), asegurando aislamiento de timeouts de 2.5s y manejo de sesiones HTTP persistentes.

**Why this priority**: Centraliza y estandariza la interacción con el firmware Vnish en la capa de red del proyecto, reutilizando y exponiendo de forma coherente los módulos ya desarrollados en `app/vnish`.

**Independent Test**: Invocar métodos de `VnishClient` con un mock de `requests.Session` y verificar que maneja timeouts, errores 401/500 y enmascaramiento de contraseñas.

**Acceptance Scenarios**:
1. **Given** un host Vnish y credenciales, **When** se inicializa `VnishClient(host, password)`, **Then** provee métodos limpios como `.set_fan_duty()`, `.restart_mining()`, `.get_overclock_settings()`, encapsulando la gestión de tokens bearer y timeouts.

---

## Functional Requirements

1. **FR-01 (Módulo CGMiner Client)**:
   - Crear `app/network/cgminer_client.py`.
   - Implementar `CGMinerClient` y funciones standalone: `query_cgminer`, `read_summary`, `read_stats_snapshot`, `read_stats_active_boards`, `read_pools`, `read_version`.
   - Implementar helpers puros: `count_active_boards`, `extract_temps`, `fw_hint`.
   - Garantizar timeout configurable por socket (default 5.0s), eliminación de bytes nulos y parseo JSON tolerante a fallos.

2. **FR-02 (Módulo Hashcore Client)**:
   - Crear `app/network/hashcore_client.py`.
   - Implementar `HashcoreClient` y funciones standalone: `run_hashcore_cli`, `run_hashcore_discovery`, `get_hashcore_cli_path`.
   - Garantizar el uso de `_NO_WINDOW_CREATION_FLAGS` en Windows (`CREATE_NO_WINDOW = 0x08000000`).
   - Respetar los flags de seguridad QA (`qa_mode`, `qa_allow_actions`).

3. **FR-03 (Módulo Vnish Client)**:
   - Crear `app/network/vnish_client.py`.
   - Implementar `VnishClient` exponiendo la API tipada para control y telemetría de Vnish.
   - Re-exportar funciones primitivas de `app.vnish.client` para mantener interoperabilidad completa.

4. **FR-04 (Fachada y Retrocompatibilidad en miner_monitor.py)**:
   - Re-exportar desde `app/miner_monitor.py`:
     * `read_summary`, `read_stats_snapshot`, `read_stats_active_boards`, `read_pools`, `read_version`
     * `_count_active_boards`, `_extract_temps`, `_fw_hint`, `_read_command`
     * `run_hashcore_cli`, `run_hashcore_discovery`, `_hashcore_cli_path`
   - Mantener intactas las firmas, argumentos por defecto y contratos de inspección para preservar el 100% de la suite de tests existente.

5. **FR-05 (Paquete app.network)**:
   - Crear `app/network/__init__.py` exponiendo todas las clases y funciones públicas de la capa de red.

---

## Non-Functional Requirements & Invariants

- **NFR-01 (Zero Regresiones)**: Los 910 tests existentes deben continuar pasando sin error ni modificación de sus aserciones.
- **NFR-02 (Zero Lock Contention)**: Ninguna llamada de red (socket 4028, REST Vnish, Hashcore subprocess) debe realizarse reteniendo `state_lock` o locks de sincronización.
- **NFR-03 (Windows Compatibility)**: Todos los comandos de subprocess y sockets deben operar de forma nativa en Windows PowerShell y servicio de fondo sin abrir consolas CMD flotantes (`CREATE_NO_WINDOW`).
- **NFR-04 (Sanitización de Secretos)**: No loguear contraseñas de Vnish ni tokens en texto plano (usar `mask_secret`).
