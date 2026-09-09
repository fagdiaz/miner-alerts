# Contrato de Interfaz: Safe Fleet Shutdown & Multi-Select API

## 1. Endpoints Autoritativos Vnish REST API
- `POST /api/v1/mining/stop`
  * Headers: `Authorization: Bearer <token>`
  * Response: HTTP 200 `{"description": "Mining stopped"}`
  * Efecto de hardware: PLL de hashboards apagados, APW12 corta riel DC de 12V a 0V. Consumo cae de ~2.700W a ~25W.
- `POST /api/v1/mining/resume`
  * Headers: `Authorization: Bearer <token>`
  * Response: HTTP 200 `{"description": "Mining resumed"}`
  * Efecto de hardware: Reactivación de riel DC de 12V, reinicio de minado y autotuning.

## 2. Gramática de Callbacks Telegram (RFC C3: $\le 64$ bytes)
- `cc:act:sd_tog:<miner_id>:<bitmask>`: Conmuta casilla de verificación (ej: `cc:act:sd_tog:23:1010` = 21 bytes).
- `cc:act:sd_req:<bitmask>`: Solicita confirmación para los mineros marcados en bitmask (ej: `cc:act:sd_req:1010` = 18 bytes).
- `cc:act:sd_cfm:<token>:<bitmask>`: Confirma la parada con token efímero (ej: `cc:act:sd_cfm:a1b2c3:1010` = 26 bytes).
- `cc:act:sd_ccl:<bitmask>`: Cancela la confirmación y regresa al selector.
- `cc:act:resume:<miner_id|bitmask>`: Despacha reanudación de minado y revoca el snooze.

## 3. Máquina de Estados y Mantenimiento
- Al confirmar parada:
  * `MinerState.snooze_until_ts = time.time() + 14400.0` (4 horas).
  * `MinerState.snooze_reason = "Mantenimiento Eléctrico"`.
  * `MinerState.is_shutdown_maintenance = True`.
- Al reanudar (`/resume`):
  * `MinerState.snooze_until_ts = 0.0`.
  * `MinerState.snooze_reason = ""`.
  * `MinerState.is_shutdown_maintenance = False`.\n