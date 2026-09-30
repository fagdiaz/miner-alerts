# Implementation Plan - Spec 080: Firmware Settings Corruption Watchdog & Assisted Recovery

## 1. Arquitectura Técnica y Módulos a Modificar

1. **`app/vnish/client.py`**:
   - Implementar `check_miner_settings_health(host: str, password: str, timeout: float = 2.5) -> Tuple[bool, str, Optional[str]]`:
     * Autentica con `unlock_miner`.
     * Ejecuta `GET /api/v1/settings` y `GET /api/v1/status`.
     * Retorna `(is_healthy, failure_code, message)`:
       - Si HTTP 200 y status normal: `(True, "OK", None)`
       - Si HTTP 500 con 'duplicate field' o 'Could not parse': `(False, "duplicate_field_error", err_str)`
       - Si `miner_state == 'failure'` y `failure_code == 1002`: `(False, "config_parse_failure", description)`
       - Si otro HTTP error: `(False, "http_error", err_str)`

2. **`app/miner_monitor.py`**:
   - Agregar comprobación en la rutina de diagnóstico / adquisición periódica:
     * Evalúa `check_miner_settings_health` para mineros Vnish.
     * Si detecta fallo de configuración:
       - Registra `operational_events` con severidad `warning` (o `critical` si el minero no mina).
       - Despacha alerta interactiva con dedup key `firmware_corrupt_{miner_name}` y cooldown de 900s:
         `⚠️ *ALERTA DE FIRMWARE: CONFIGURACIÓN BLOQUEADA*`
         Incluyendo botones interactivos de aprobación para el operador.

3. **`app/telegram/fleet_cards.py`**:
   - Agregar helper `build_firmware_corruption_keyboard(miner_id: str)`:
     * Botón 1: `[ ⚡ Reiniciar Minero ]` (`cb:reboot:{miner_id}`)
     * Botón 2: `[ 🔄 Reiniciar Minado ]` (`cb:restart:{miner_id}`)
     * Botón 3: `[ 🔍 Diagnóstico ]` (`diag:ref:diagnose`)

4. **`tests/test_firmware_corruption_watchdog.py`**:
   - Crear suite de pruebas exhaustiva:
     * Mock de respuestas HTTP 500 con error `duplicate field`.
     * Mock de respuestas HTTP 200 con `failure_code: 1002`.
     * Mock de respuestas HTTP 200 normales.
     * Verificación de formato de alertas y botoneras.
     * Validación de ancho móvil $\le 32$ columnas.

---

## 2. Gates de Estabilidad & Mitigación de Riesgos

- **G1 (No-Silence & Safety)**: La función de verificación captura todas las excepciones de red y retorna tupla limpia sin lanzar errores no controlados.
- **G2 (No-Spam Alert)**: La alerta utiliza `dedup_key` específico por minero con cooldown de 15 minutos (900 segundos).
- **G3 (Aprobación Requerida)**: El sistema nunca reinicia un minero automáticamente por este error; siempre solicita confirmación explícita al operador vía Telegram.
- **G4 (Validación de Regresión)**: 100% de la suite de pruebas existente debe continuar en PASS.
