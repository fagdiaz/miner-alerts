# Propuesta de Mejora Técnica: PROP-011
# Detección, Reinstalación Autónoma de Firmware VNish en NAND y Calibración de Escalera de Hardware S19j Pro

- **Fecha de Creación**: 2026-09-18
- **Estado**: Propuesta Formal / Base para Especificación 076
- **Prioridad**: P1 (Alta Resiliencia Operativa)
- **Autor**: Antigravity Assistant & Operator Engineering
- **Línea Base**: Release V5.1.0 + Spec 074 + Spec 075 (1236 tests PASS)

---

## 1. Resumen Ejecutivo y Motivación

En la jornada del 18/09/2026 se registraron dos incidentes de configuración y arranque en la flota:
1. **Minero 24**: Tras el apagón general de las 11:52 hs, perdió el arranque de VNish y cayó a la memoria NAND de fábrica de Bitmain (junio 2021). Debido a una discrepancia de modelos de placa (`BHB42601` en firmware vs `BHB42621` en hardware), las hashboards fueron desenergizadas (`ERROR_SOC_INIT`). La recuperación requirió intervención manual con la interfaz gráfica de Hashcore Toolkit para flashear `C:\asicto\asicto-s19jpro-bb-nand-v1.2.6-install.tar.gz`, seguido de un error de configuración de pools (`Failed to parse miner configuration 1002`) resuelto por inyección REST API.
2. **Minero 23**: Quedó atrapado en 1800W durante varias horas. El análisis determinó que la escalera de presets en `DEFAULT_PRESET_LADDER` contenía valores teóricos (`2100W`), inexistentes en el firmware VNish para S19j Pro (el preset real es `2150W`), provocando rechazos `HTTP 400 Bad Request` y bloqueos en el Balancer (`Preset actual '1800' desconocido en la escalera`).

La presente propuesta (`PROP-011`) diseña la solución definitiva para ambos problemas:
1. **Calibración 1:1 de la Escalera de Hardware S19j Pro**: Alinear `DEFAULT_PRESET_LADDER` con los presets reales del ASIC reportados por `/api/v1/autotune/presets`.
2. **Pipeline Autónomo de Flasheo y Aprovisionamiento**: Dotar a `miner-alerts` de la capacidad de detectar el fallback a stock Bitmain, cargar el firmware VNish 1.2.6 automáticamente o vía comando Telegram `/flash_vnish <miner>`, esperar el booteo e inyectar el perfil dorado de configuración y chips afinados sin intervención humana.

---

## 2. Diagnóstico Técnico Detallado

### 2.1 Descalibración de la Escalera de Presets en Software vs Hardware

En `app/governance/preset_balancer.py` y `app/governance/adaptive_contingency.py`, la escalera estaba hardcodeada como:
```python
DEFAULT_PRESET_LADDER = (
    "1600W", "1740W", "1900W", "2100W", "2300W", "2500W", "2700W", "2800W"
)
```

Sin embargo, la consulta autoritativa a la API de VNish 1.2.6 (`GET /api/v1/autotune/presets`) en los mineros S19j Pro arroja la escalera real del silicio:
```
1740 | 1740 watt ~ 65 TH | status: tuned
1800 | 1800 watt ~ 70 TH | status: tuned  <-- Faltaba en DEFAULT_PRESET_LADDER
1850 | 1850 watt ~ 76 TH | status: tuned
2000 | 2000 watt ~ 80 TH | status: tuned
2150 | 2150 watt ~ 83 TH | status: tuned  <-- El software pedía 2100W (HTTP 400)
2300 | 2300 watt ~ 87 TH | status: tuned
2500 | 2500 watt ~ 92 TH | status: tuned
2700 | 2700 watt ~ 96 TH | status: tuned
2970 | 2970 watt ~ 100 TH | status: tuned <-- El software pedía 2800W
```

**Consecuencias observadas**:
- Cuando el Balancer intentaba evaluar un minero en 1800W, abortaba con `reason="Preset actual '1800' desconocido en la escalera"`.
- Cuando la Contingencia de Elevador (Spec 074) intentaba bajar a 2100W, VNish rechazaba la orden con `http_status_400`.

### 2.2 Flasheo Manual vs Flasheo Autónomo de Firmware

Actualmente, cuando un minero cae a stock Bitmain:
1. `unlock_miner()` detecta `stock_firmware_fallback_detected` e inhibe reboots (Spec 075).
2. El sistema notifica por Telegram solicitando acción física.
3. El operador debe acceder a la PC, abrir Hashcore Toolkit GUI, escanear la red, seleccionar el archivo `.tar.gz` y esperar el flasheo.
4. Luego del flasheo, debe configurar los pools manualmente o correr el script de restauración.

**Capacidades del Firmware Bitmain**:
- El servidor web `lighttpd/1.4.32` en puerto 80 del firmware stock de Bitmain dispone del endpoint estándar:
  `POST /cgi-bin/upgrade.cgi` (autenticación HTTP Digest `root:root`, carga de archivo multipart `upgrade.tar.gz`).
- Al recibir el paquete `asicto-s19jpro-bb-nand-v1.2.6-install.tar.gz`, el script interno `runme.sh` valida la firma, formatea la partición del kernel/rootfs en la NAND eMMC y reinicia en VNish 1.2.6.
- Toda esta operación puede ser ejecutada de manera desatendida mediante una llamada HTTP en Python o script automatizado.

---

## 3. Plan de Arquitectura y Diseño (Futura Spec 076)

### Componente 1: Calibración de la Escalera de Presets de Hardware
- Actualizar `DEFAULT_PRESET_LADDER` en `app/governance/preset_balancer.py` y `app/governance/adaptive_contingency.py`:
  ```python
  DEFAULT_PRESET_LADDER: Tuple[PresetTier, ...] = (
      PresetTier(name="1740W", nominal_power_w=1740, nominal_ths=65.0, order=0),
      PresetTier(name="1800W", nominal_power_w=1800, nominal_ths=70.0, order=1),
      PresetTier(name="1850W", nominal_power_w=1850, nominal_ths=76.0, order=2),
      PresetTier(name="2000W", nominal_power_w=2000, nominal_ths=80.0, order=3),
      PresetTier(name="2150W", nominal_power_w=2150, nominal_ths=83.0, order=4),
      PresetTier(name="2300W", nominal_power_w=2300, nominal_ths=87.0, order=5),
      PresetTier(name="2500W", nominal_power_w=2500, nominal_ths=92.0, order=6),
      PresetTier(name="2700W", nominal_power_w=2700, nominal_ths=96.0, order=7),
      PresetTier(name="2970W", nominal_power_w=2970, nominal_ths=100.0, order=8),
  )
  ```
- Corregir `DEFAULT_MIN_PRESET_FLOOR = "2150W"` (reemplazando `2100W`).

### Componente 2: Módulo `FirmwareFlasher` (`app/network/firmware_flasher.py`)
- Módulo encargado de gestionar la carga de firmware sobre mineros en estado stock Bitmain:
  * Conexión con `requests.auth.HTTPDigestAuth('root', 'root')`.
  * Endpoint: `http://{host}/cgi-bin/upgrade.cgi`.
  * Carga vía streaming del archivo instalador `C:\asicto\asicto-s19jpro-bb-nand-v1.2.6-install.tar.gz`.
  * Manejo seguro de timeouts (hasta 120s para subida y descompresión).
  * Retorno estructurado `(ok: bool, message: str)`.

### Componente 3: Orquestador de Recuperación Desatendida (`AutoRecoveryPipeline`)
1. **Detección**: `unlock_miner()` detecta `stock_firmware_fallback_detected`.
2. **Notificación Interactiva en Telegram**:
   - En lugar de requerir que el operador abra Hashcore Toolkit, Telegram envía una tarjeta con botón:
     `[🛠️ Flashear VNish 1.2.6 en Minero 24]`
   - O comando manual: `/flash_vnish 24`.
3. **Ejecución del Flasheo**:
   - El worker en segundo plano envía el firmware a `/cgi-bin/upgrade.cgi`.
   - Se notifica progreso: `"Flasheo enviado. Esperando booteo de VNish (aprox 90s)..."`.
4. **Auto-Aprovisionamiento Post-Arranque**:
   - El monitor sondea `/api/v1/info` hasta que responde VNish 1.2.6.
   - Inmediatamente invoca `restore_miner_profile(name, host)`:
     * Restaura pools de Binance con worker correspondiente.
     * Restaura preset nominal (2300W / 2700W).
     * Restaura la matriz completa de **378 chips afinados** desde `data/miner_profiles/`.
   - El minero queda hasheando a plena potencia en minutos sin requerir ninguna acción física ni uso de software externo.

---

## 4. Fases de Trabajo y Criterios de Aceptación

1. **Fase 1 (Inmediata / Quick Win)**:
   - Calibrar `DEFAULT_PRESET_LADDER` a los valores de hardware (`1740`, `1800`, `1850`, `2000`, `2150`, `2300`, `2500`, `2700`).
   - Actualizar tests asociados en `tests/test_preset_balancer.py` y `tests/test_paired_elevator_contingency.py`.

2. **Fase 2 (Herramienta de Flasheo)**:
   - Implementar `app/network/firmware_flasher.py` y probar el método `flash_stock_bitmain(host, package_path)`.
   - Crear suite de pruebas simulando respuestas HTTP Digest de Bitmain.

3. **Fase 3 (Comando Telegram y Orquestación)**:
   - Añadir comando `/flash_vnish` en el centro de comandos de Telegram con confirmación inline.
   - Conectar el lazo post-flasheo con `restore_miner_profile`.

4. **Fase 4 (Auditoría y Certificación)**:
   - Auditoría de cerrojos, timeouts de red y validación en 1236+ tests.
