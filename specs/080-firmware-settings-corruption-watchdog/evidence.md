# Evidencia Operativa - Spec 080: Firmware Settings Corruption Watchdog & Assisted Recovery

## 1. Evidencia Empírica de Causa Raíz en Producción (Minero 24)

- **Comando Ejecutado**:
  ```python
  from app.vnish.client import safe_get_overclock_settings
  ok, s, err = safe_get_overclock_settings('192.168.100.24', 'admin')
  ```
- **Respuesta de la API de Vnish**:
  ```json
  {"err": "Could not parse file /config/cgminer.conf duplicate field `fan-fixed-duty` at line 42 column 20"}
  ```
  `HTTP 500 Internal Server Error`.

- **Comportamiento Secundario**:
  - El proceso de minado intentó reiniciar y reportó:
    `failure_code: 1002, description: 'Failed to parse miner configuration'`.
  - El minero permanecía entregando 2498W con coolers al 100% fijos sin poder ascender a 2700W.

## 2. Resolución Empírica Aplicada

1. **Reinicio de Hardware (Reboot)**:
   - Ejecutado reinicio vía comando de Hashcore Toolkit (`toolkit_cli.bat reboot 192.168.100.24-192.168.100.24`).
   - El script de arranque de Vnish en Linux detectó la inconsistencia de `/config/cgminer.conf` y reconstituyó la configuración limpia de fábrica en NAND.
2. **Verificación Post-Reinicio**:
   - `GET /api/v1/settings` respondió `200 OK`.
   - Vnish arrancó en estado `initializing`.
3. **Inyección Exitosa de 2700W**:
   - `safe_set_miner_preset('192.168.100.24', 'admin', '2700', clamp_top_preset=True, top_preset='2700', min_preset='1740')` respondió:
     `ok: True, err: None`.
   - Configuración verificada en el minero:
     `preset: 2700`, `top_preset: 2700`, `min_preset: 1740`.
