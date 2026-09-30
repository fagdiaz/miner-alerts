# Spec 080: Watchdog de Corrupción de Configuración de Firmware y Resolución Asistida (PROP-016)

## 1. Contexto y Objetivos

### 1.1 El Problema Operativo y la Evidencia Empírica en Producción
En mineros Antminer S19j Pro corriendo firmware Vnish (ej. v1.2.6), se evidenció en producción que el archivo `/config/cgminer.conf` dentro del sistema de archivos Linux de la placa de control puede corromperse o duplicar claves (específicamente `duplicate field fan-fixed-duty at line 42 column 20`).

Cuando esto ocurre:
1. **Fallo Crítico de API de Configuración**: Cualquier petición `GET` o `POST` a `/api/v1/settings` falla con `HTTP 500 Internal Server Error` (`Could not parse file /config/cgminer.conf`).
2. **Autoswitcher Nativo Paralizado**: La rutina interna de Vnish (`preset_switcher`) se detiene por completo porque no puede deserializar su archivo de configuración JSON. El minero queda estancado en un preset inferior (ej. 2500W en Minero 24), a pesar de tener chips fríos (78°C <= 80°C) y estar habilitado para 2700W.
3. **Bloqueo del Fan Governor**: El Fan Governor detecta que el minero entrega 2498W frente a su meta de 2700W, por lo que aplica la directiva de seguridad manteniendo los ventiladores clavados al 100% PWM (`RECOVERY_MAX_COOLING`), generando ruido y desgaste innecesario mientras espera un escalamiento que nunca ocurrirá.
4. **Fallo de Inicialización de Cgminer**: Si el proceso minero intenta reiniciar, reporta `failure_code: 1002, description: 'Failed to parse miner configuration'`.

### 1.2 Directiva del Operador
El operador requiere:
- *"cuando es asi, informarme y doy el ok para un reboot o para subir la potencia del miner. programar alerta y realizar el paso mas indicado para estos casos. quizas subiendo o bajando la potencia se arregla y sino reboot quizas. ahora ejecutalo vos. arma la spec y la resolucion, pasalo por qa y estabilizacion"*.

### 1.3 Objetivos de la Especificación
1. **Detección Automatizada**: Monitorear la salud de configuración de firmware en el ciclo de adquisición o diagnóstico (`check_miner_settings_health`), identificando errores HTTP 500, claves JSON duplicadas y código de fallo 1002.
2. **Alerta Interactiva de Telegram con Aprobación del Operador**:
   - Notificación clara explicando el bloqueo exacto de firmware y por qué el minero no puede subir de potencia.
   - Botonera táctil interactiva para autorizar reinicio (`[ ⚡ Reiniciar Minero ]`), reinicio de software (`[ 🔄 Reiniciar Minado ]`) o diagnóstico (`[ 🔍 Ver Detalle ]`).
3. **Mecanismo Asistido de Remediación**:
   - Verificación de que el reinicio de hardware (reboot) reconstruye `/config/cgminer.conf` limpio desde la partición NAND de fábrica de Vnish.
   - Restablecimiento automático o guiado del preset objetivo (2700W) una vez normalizado el endpoint `/api/v1/settings`.

---

## 2. Requerimientos Funcionales

- **FR-001**: El cliente Vnish (`app/vnish/client.py`) DEBE proveer la función `check_miner_settings_health(host, password, timeout=2.5)` que valida si `/api/v1/settings` responde `200 OK` o si genera un error `HTTP 500` con fallo de deserialización (`duplicate field`, `Could not parse file`).
- **FR-002**: El cliente Vnish DEBE detectar estados de fallo de configuración en `/api/v1/status` (`miner_state == 'failure'` y `failure_code == 1002`).
- **FR-003**: El monitor (`app/miner_monitor.py`) DEBE evaluar periódicamente la salud de configuración de firmware de los mineros y, ante una anomalía detectada, registrar un evento operacional en `operational_events` con tipo `firmware_settings_corrupted` y severidad `warning` o `critical`.
- **FR-004**: El sistema DEBE despachar una alerta de Telegram dedicada con dedup key por minero (`firmware_corrupt_{miner_name}`) y cooldown de 900s, incluyendo explicación clara y botones inline de aprobación para el operador:
  - Botón: `[ ⚡ Reiniciar Minero ]` (vía token de confirmación `/reboot <id>`).
  - Botón: `[ 🔄 Reiniciar Minado ]` (vía confirmación `/restart <id>`).
- **FR-005**: Las tarjetas y textos de alerta DEBEN cumplir con la regla de ancho móvil $\le 32$ columnas en datos tabulares y formateo limpio.
- **FR-006**: La resolución de Minero 24 ejecutada en vivo (reboot de hardware que saneó `/config/cgminer.conf` y posterior inyección exitosa de `preset: 2700W`, `top_preset: 2700W`) DEBE quedar documentada y certificada.

---

## 3. Historias de Usuario y Casos de Aceptación

### Historia 1: Detección y Notificación de Configuración Corrupta (P1)
**Dado** un minero cuyo archivo `/config/cgminer.conf` está corrupto o duplicado arrojando error 500 en `/api/v1/settings`,
**Cuando** el supervisor ejecuta su ciclo de adquisición y diagnóstico de firmware,
**Entonces** el monitor identifica la anomalía, registra el evento en SQLite y emite una alerta a Telegram explicando que el minero está congelado y requiere aprobación de reinicio.

### Historia 2: Aprobación y Resolución del Operador (P2)
**Dado** un operador que recibe la alerta interactiva en Telegram,
**Cuando** pulsa el botón de reinicio o ejecuta el comando `/reboot <id>`,
**Entonces** el sistema despacha el comando de reinicio a la máquina, la cual limpia su configuración de NAND al arrancar y permite inyectar el preset 2700W.
