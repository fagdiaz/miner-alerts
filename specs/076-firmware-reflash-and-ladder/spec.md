# Feature Specification: Spec 076 — Reinstalación Autónoma de Firmware VNish en NAND y Calibración de Escalera de Hardware S19j Pro

**Feature Branch**: `076-firmware-reflash-and-ladder`  
**Created**: 2026-09-18  
**Status**: Draft / Under Review  
**Proposal Reference**: [PROP-011](file:///F:/02-ASIC%20-%20mineros/miner-alerts/docs/proposals/PROP-011-autonomous-firmware-reflash-and-hardware-ladder.md)  
**Input**: User instruction: "la idea es que nuestro sistema lo detecte y pueda instalar el firm de ser necesario. otro punto, teniamos el 23 a 1800w no ser por que. fijate de arreglarlo. documenta un nuevo plan para todo esto de ser necesario y lo vamos trabajando como antes, puliendo hasta auditarlo, corregirlo y llevar a cabo el plan de specs para finalizar implementando"

---

## 1. User Scenarios & Testing *(mandatory)*

### User Story 1 — Calibración 1:1 de la Escalera de Hardware S19j Pro (Priority: P1)

Como operador de la granja, necesito que el sistema conozca con exactitud los peldaños de potencia reales soportados por el silicio y el firmware VNish 1.2.6 en los Antminer S19j Pro, para que las transiciones de contingencia (Spec 074) y optimización de potencia (Spec 062/075) jamás sean rechazadas con `HTTP 400 Bad Request` ni dejen a un minero atrapado en un peldaño desconocido como ocurrió con el Minero 23 en 1800W.

**Why this priority**:
El Minero 23 quedó confinado a 1800W durante horas porque `DEFAULT_PRESET_LADDER` contenía peldaños teóricos (`2100W`) y omitía peldaños de hardware reales (`1800W`). Al no reconocer 1800W, el Balancer abortaba con error y no lo escalaba a 2300W. Además, cualquier desescalada hacia 2100W era rechazada por el ASIC (`HTTP 400`).

**Independent Test**:
Puede probarse de forma unitaria e independiente mediante pruebas deterministas que verifiquen:
1. `find_previous_preset_tier("2300W")` devuelve `"2150W"` (y no `"2100W"`).
2. `find_preset_index("1800W")` encuentra el índice válido `1`.
3. `find_next_preset_tier("1800W")` devuelve `"1850W"`.
4. La escalera completa contiene exactamente los 9 peldaños reportados por el ASIC: `1740W, 1800W, 1850W, 2000W, 2150W, 2300W, 2500W, 2700W, 2970W`.

**Acceptance Scenarios**:
1. **Given** un minero operando a 2300W y una orden de desescalada de contingencia, **When** el calculador selecciona el peldaño inferior, **Then** devuelve `2150W` y la llamada a VNish API es exitosa (HTTP 200).
2. **Given** un minero operando a 1800W tras un reinicio o apagón, **When** el Balancer evalúa su estabilidad, **Then** reconoce el peldaño `1800W` dentro de la escalera y propone el ascenso a `1850W` / `2000W` / `2300W` según corresponda.

---

### User Story 2 — Módulo Autónomo de Flasheo de Firmware (`FirmwareFlasher`) (Priority: P1)

Como sistema supervisor y operador, necesito una utilidad en Python capaz de cargar el instalador de firmware VNish (`C:\asicto\asicto-s19jpro-bb-nand-v1.2.6-install.tar.gz`) directamente sobre un minero que ha revertido al firmware stock de Bitmain, utilizando el endpoint estándar HTTP Digest de Bitmain `/cgi-bin/upgrade.cgi`, sin necesidad de abrir la interfaz gráfica manual de Hashcore Toolkit.

**Why this priority**:
Tras un apagón o corrupción de sector de arranque, mineros como el Minero 24 caen al firmware de fábrica de Bitmain de 2021. Al no arrancar VNish, las placas se desactivan (`ERROR_SOC_INIT`) y el minero queda inoperativo hasta que alguien use una PC local. El flasheo programático desatendido elimina esta dependencia humana.

**Independent Test**:
Puede probarse de manera aislada contra un servidor HTTP mock que replique el desafío HTTP Digest `antMiner Configuration` (`root:root`) y el endpoint `/cgi-bin/upgrade.cgi`, verificando el envío correcto en formato multipart/form-data, tiempos de espera, streaming y manejo de excepciones.

**Acceptance Scenarios**:
1. **Given** un minero en IP `192.168.100.24` con servidor web Bitmain en puerto 80, **When** se invoca `FirmwareFlasher.flash_bitmain_nand("192.168.100.24", package_path)`, **Then** se autentica con HTTP Digest, transmite el archivo `tar.gz`, recibe HTTP 200 y retorna `(True, "Flasheo completado con éxito")`.
2. **Given** un minero que ya está corriendo VNish (puerto 80 retorna API VNish y no Bitmain lighttpd), **When** se intenta flashear, **Then** la operación aborta con error de seguridad `ABORTED_NOT_STOCK_BITMAIN` para evitar sobreescritura accidental.

---

### User Story 3 — Comando Telegram `/flash_vnish` con Confirmación en Dos Pasos (Priority: P2)

Como operador remoto en Telegram, necesito poder ordenar la reinstalación del firmware sobre un minero específico mediante `/flash_vnish <miner>`, recibiendo una solicitud de confirmación con botón inline y recibiendo el reporte del avance en tiempo real.

**Why this priority**:
Permite al operador resolver remotamente una caída de firmware desde su teléfono celular inmediatamente después de que el bot reporte `stock_firmware_fallback_detected`.

**Independent Test**:
Se prueba enviando `/flash_vnish 24` con mocks del dispatcher de Telegram, comprobando que emite la confirmación requerida y solo ejecuta el subproceso en segundo plano tras recibir `confirm_flash_24` o `/flash_vnish 24 CONFIRM`.

**Acceptance Scenarios**:
1. **Given** el bot de Telegram en ejecución, **When** el usuario envía `/flash_vnish 24`, **Then** responde con un mensaje de advertencia y botón de confirmación `[⚠️ Confirmar Flasheo VNish en Minero 24]`.
2. **Given** la confirmación recibida, **When** se dispara el worker en background, **Then** notifica periódicamente: carga iniciada, subida completada, reinicio de NAND en curso.

---

### User Story 4 — Pipeline de Auto-Aprovisionamiento Post-Flasheo (Priority: P2)

Como operador, necesito que una vez que el minero complete el flasheo de NAND y reinicie en VNish 1.2.6, el sistema automáticamente detecte su primer booteo, inyecte las pools de Binance correspondientes, configure los presets 2300W/2700W y cargue la matriz guardada de los 378 chips afinados desde `data/miner_profiles/`, dejando al minero hasheando a ~90 TH/s sin requerir configuración manual.

**Why this priority**:
Un minero recién flasheado bootea con pools vacías/de fábrica y sin tuning, requiriendo 30-45 minutos de auto-tuning desde cero o configuración manual. Inyectar el perfil dorado guardado le permite minar inmediatamente a máxima eficiencia.

**Independent Test**:
Se prueba invocando el orquestador de aprovisionamiento contra un minero mockeado en estado default, verificando la secuencia: unlock -> configure pools -> set preset 2300 -> restore chip offsets -> restart mining.

**Acceptance Scenarios**:
1. **Given** un minero recién flasheado que responde en `/api/v1/info`, **When** se ejecuta el auto-aprovisionamiento, **Then** sus pools coinciden con las pools de producción, su preset es 2300W y sus 378 chips cargan las frecuencias/voltajes del perfil dorado.

---

## 2. Edge Cases & Safety Invariants

1. **Protección contra Flasheo Erróneo**: Jamás flashear un minero que esté minando normalmente o que responda a la API de VNish. La herramienta debe validar explícitamente el encabezado HTTP / respuesta de Bitmain (`antMiner Configuration` o `lighttpd/1.4.32`) antes de emitir el payload de upgrade.
2. **Timeout de Subida Prolongado**: El paquete de instalación pesa ~56 MB. A través de la red local, la transferencia puede demorar entre 15 y 45 segundos, y la descompresión/escritura en NAND en el BeagleBone Black puede demorar hasta 60 segundos. El timeout de socket debe ser holgado (mínimo 120s) y jamás bloquear el bucle principal del monitor ni el worker de Telegram.
3. **Ausencia de Archivo Local**: Si `C:\asicto\asicto-s19jpro-bb-nand-v1.2.6-install.tar.gz` no existe en el disco, la operación debe fallar limpiamente con un mensaje descriptivo sin lanzar un crash no controlado.
4. **Falla Eléctrica durante Flasheo**: Si se corta la energía durante la escritura de la NAND, el BeagleBone Black caerá a modo booteo SD. El sistema debe reportar el fallo de conexión y mantener la alerta.

---

## 3. Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE definir la constante `DEFAULT_PRESET_LADDER` en `app/governance/preset_balancer.py` y `app/governance/adaptive_contingency.py` con los 9 peldaños reales de hardware de VNish 1.2.6 para Antminer S19j Pro:
  `1740W (65 TH)`, `1800W (70 TH)`, `1850W (76 TH)`, `2000W (80 TH)`, `2150W (83 TH)`, `2300W (87 TH)`, `2500W (92 TH)`, `2700W (96 TH)`, `2970W (100 TH)`.
- **FR-002**: El sistema DEBE actualizar `DEFAULT_MIN_PRESET_FLOOR` a `"2150W"` (reemplazando el valor inexistente en hardware `"2100W"`).
- **FR-003**: El módulo `app/network/firmware_flasher.py` DEBE proveer la función `flash_bitmain_nand(host, package_path, username='root', password='root')` que realice la carga HTTP Digest a `/cgi-bin/upgrade.cgi`.
- **FR-004**: `firmware_flasher.py` DEBE verificar antes del flasheo que el objetivo es un firmware stock de Bitmain verificando el realm de autenticación Digest o banner HTTP.
- **FR-005**: El comando Telegram `/flash_vnish <miner>` DEBE exigir confirmación interactiva en 2 pasos para prevenir ejecuciones accidentales.
- **FR-006**: La rutina de flasheo DEBE ejecutarse en un hilo desacoplado (`threading.Thread`) para no bloquear el servicio ni los comandos de Telegram.
- **FR-007**: El sistema DEBE disponer de una rutina `provision_miner_from_golden_profile(host, miner_name)` que inyecte pools, presets y chip offsets desde `data/miner_profiles/{miner_name}.json`.
- **FR-008**: Si un minero entra en estado `stock_firmware_fallback_detected` durante el monitoreo continuo, el bot de Telegram DEBE incluir un botón o comando sugerido para disparar `/flash_vnish`.

---

## 4. Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Cero errores `HTTP 400 Bad Request` por selección de presets inexistentes en transiciones de contingencia o balanceo.
- **SC-002**: Minero en 1800W es reconocido correctamente en la escalera (índice 1) y es elegible para ascensos o descensos según corresponda.
- **SC-003**: El módulo `FirmwareFlasher` es capaz de subir el paquete `.tar.gz` a un minero con firmware Bitmain stock y completar la llamada en $< 90$ segundos.
- **SC-004**: El aprovisionamiento post-flasheo restaura las pools de minado y los 378 chips afinados en $< 15$ segundos tras el booteo de VNish.
- **SC-005**: La suite de pruebas de regresión pasa al 100% ($\ge 1245$ tests PASS, 0 fallos, 0 regresiones).
