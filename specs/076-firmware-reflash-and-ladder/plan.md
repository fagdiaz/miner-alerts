# Implementation Plan: Spec 076 — Reinstalación Autónoma de Firmware VNish en NAND y Calibración de Escalera de Hardware S19j Pro

## 1. Architectural Overview & Component Structure

Spec 076 implementa la calibración precisa de la escalera de hardware para los Antminer S19j Pro y el pipeline integral de recuperación autónoma ante caídas a firmware de fábrica Bitmain:

```
+---------------------------------------------------------------------------------+
|                              SUPERVISOR DE FLOTA                                |
|                             (app/miner_monitor.py)                              |
+---------------------------------------------------------------------------------+
       |                                                    |
       v (unlock detecta stock_firmware)                    v (evaluación de presets)
+-------------------------------------+             +-----------------------------+
|   STOCK FIRMWARE DETECTION          |             |       PRESET BALANCER       |
|  (unlock_miner / fallback alarm)    |             |  (app/governance/           |
+-------------------------------------+             |   preset_balancer.py)       |
       |                                            | - Escalera 1:1 Hardware:    |
       v                                            |   1740, 1800, 1850, 2000,   |
+-------------------------------------+             |   2150, 2300, 2500, 2700,   |
| TELEGRAM COMMAND CENTER & CALLBACKS |             |   2970                      |
| - /flash_vnish <miner>              |             +-----------------------------+
| - [⚠️ Confirmar Flasheo]            |                            |
+-------------------------------------+                            v
       | (hilo worker desacoplado)                  +-----------------------------+
       v                                            |    ADAPTIVE CONTINGENCY     |
+-------------------------------------+             | (app/governance/            |
|       FIRMWARE FLASHER              |             |  adaptive_contingency.py)   |
| (app/network/firmware_flasher.py)   |             | - Min Floor: 2150W (no 2100)|
| - Verifica HTTP Digest Bitmain      |             | - Prevención HTTP 400       |
| - POST /cgi-bin/upgrade.cgi         |             +-----------------------------+
| - Paquete: C:\asicto\*.tar.gz       |
+-------------------------------------+
       | (booteo en VNish ~90s)
       v
+-------------------------------------+
|      AUTO-PROVISIONING PIPELINE     |
| (app/governance/miner_provisioner)  |
| - Setea Pools Binance (user.miner)  |
| - Setea Preset 2300W / Top 2700W    |
| - Inyecta 378 chips afinados        |
| - Reinicia hasheo automático        |
+-------------------------------------+
```

---

## 2. Module Specifications & Modifications

### 2.1 Escalera de Hardware S19j Pro (`app/governance/preset_balancer.py` & `adaptive_contingency.py`)
Reemplazar la constante teórica `DEFAULT_PRESET_LADDER` por los valores exactos reportados por el endpoint `/api/v1/autotune/presets` de VNish 1.2.6 en los S19j Pro:
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
En `app/governance/adaptive_contingency.py`:
- Modificar `DEFAULT_MIN_PRESET_FLOOR = "2150W"` (reemplaza `"2100W"`).

### 2.2 Módulo de Flasheo: `app/network/firmware_flasher.py`
Módulo puro encargado de la comunicación con el firmware stock de Bitmain:
- **`is_stock_bitmain(host: str, timeout_s: float = 5.0) -> bool`**:
  Verifica si el puerto 80 responde con el realm `antMiner Configuration` o encabezado `lighttpd/1.4.32`.
- **`flash_bitmain_nand(host: str, package_path: str, username: str = "root", password: str = "root", timeout_s: float = 120.0) -> Tuple[bool, str]`**:
  - Utiliza `requests.auth.HTTPDigestAuth(username, password)`.
  - Envía `POST http://{host}/cgi-bin/upgrade.cgi` con archivo multipart `tar.gz`.
  - Retorna estado y mensaje estructurado.
  - No lanza excepciones fatales hacia el llamador.

### 2.3 Módulo de Aprovisionamiento: `app/governance/miner_provisioner.py`
- **`provision_miner_from_profile(host: str, miner_name: str, profiles_dir: str = "data/miner_profiles", admin_pw: str = "admin") -> Tuple[bool, str]`**:
  - Lee `data/miner_profiles/{miner_name}.json`.
  - Desbloquea la API `/api/v1/unlock` con token Bearer.
  - Configura pools de Binance (`POST /api/v1/pools` o `/settings`).
  - Configura preset nominal (`2300W`) y `top_preset` (`2700W`).
  - Restaura los 378 chip offsets afinados (`data.get("autotune", {}).get("chips")`).
  - Aplica cambios y reinicia minado (`POST /api/v1/mining/restart`).

### 2.4 Comandos Telegram & Orquestación en Background
- En `app/telegram_command_center.py` y `app/telegram_callbacks.py`:
  - Registrar `/flash_vnish <miner>`.
  - Si no viene con `CONFIRM`, emitir teclado inline con `confirm_flash_{miner_name}` y `cancel_flash_{miner_name}`.
  - Al confirmar, invocar `start_background_flash_pipeline(miner_name, host, notify_cb)` en un daemon thread.
  - Notificar progreso a Telegram en 4 fases:
    1. `[1/4] Verificando estado Bitmain stock...`
    2. `[2/4] Subiendo instalador VNish 1.2.6 (56 MB)...`
    3. `[3/4] Flasheo recibido. Esperando booteo de VNish (~90s)...`
    4. `[4/4] Minero booteó VNish. Inyectando pools y 378 chips afinados... Listo!`

---

## 3. Risk Assessment & Mitigations

| Riesgo | Impacto | Severidad | Mitigación |
|---|---|---|---|
| Sobreescritura accidental de minero con VNish activo | Desconexión innecesaria | Alta | `is_stock_bitmain` aborta inmediatamente si detecta VNish o rechazo de Digest Bitmain. |
| Timeout de socket bloquea monitor principal | Pérdida de telemetría | Crítica | El flasheo corre 100% en subproceso daemon desacoplado (`threading.Thread`). |
| Fallo en la subida del archivo `.tar.gz` | Minero queda en stock | Media | Retry acotado y mensaje explícito de error a Telegram. |
| Archivo de instalador inexistente en disco | Falla silenciosa | Baja | Chequeo preliminar de `os.path.exists(package_path)` antes de contactar al minero. |
| Discrepancia en tests por cambio de escalera | Tests rotos | Media | Actualización y parametrización de fixtures en tests de balancer y contingencia. |

---

## 4. Verification & Testing Strategy

1. **Pruebas de Escalera de Hardware**:
   - Verificar escalón por escalón las funciones `find_previous_preset_tier`, `find_next_preset_tier` y `find_preset_index`.
   - Probar que `1800W` se reconoce y se puede transicionar bidireccionalmente.
   - Probar que `2150W` es el piso de contingencia y que `2100W` ya no se propone.
2. **Pruebas de `firmware_flasher`**:
   - Mocking de `requests` simulando HTTP Digest 401 Challenge y 200 OK en `/cgi-bin/upgrade.cgi`.
   - Mocking de timeout y de respuesta no-Bitmain.
3. **Pruebas de `miner_provisioner`**:
   - Carga y validación del JSON de perfil guardado (`S19JPRO-24.json`).
   - Mock de inyección de settings y chip offsets.
4. **Pruebas de Comandos Telegram**:
   - Verificación de confirmación en dos pasos (`/flash_vnish` vs `/flash_vnish 24 CONFIRM`).
   - Verificación de callback `confirm_flash_24`.
5. **Regresión Total**:
   - Ejecutar la suite completa de 1236+ tests asegurando 100% PASS.
