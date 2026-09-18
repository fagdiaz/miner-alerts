# Evidence: Spec 076 — Reinstalación Autónoma de Firmware VNish en NAND y Calibración de Escalera de Hardware S19j Pro

- **Feature**: `specs/076-firmware-reflash-and-ladder`
- **Baseline Tests**: 1236/1236 tests PASS
- **Final Tests**: 1262/1262 tests PASS (100% green, 41.69s)
- **Status**: Production Certified & Verified

---

## 1. QA Specialist Audit Findings & Applied Fixes

1. **`find_preset_index` Substring Matching Vulnerability**:
   - *Problem*: `app/governance/preset_balancer.py` used `preset_str in t.name`. Empty strings (`""`), single characters (`"2"`), `"W"`, or partial substrings caused false positive index matches (matching index 0 or incorrect power levels).
   - *Fix*: Refactored to extract integer numeric watts via regex and match against `nominal_power_w`. Non-matching or empty values cleanly return `-1`.
2. **S19j Pro Hardware Preset Ladder Discrepancy**:
   - *Problem*: The software ladder included theoretical steps like `2100W` and `2800W`. On physical VNish 1.2.6 hardware, these presets do not exist and Bitmain/VNish API returns `HTTP 400 Bad Request`. Additionally, `1800W` was missing, causing Miner 23 to be trapped at 1800W when recovering.
   - *Fix*: Calibrated the authoritative 9-step hardware ladder: `1740W`, `1800W`, `1850W`, `2000W`, `2150W`, `2300W`, `2500W`, `2700W`, `2970W`. Updated `DEFAULT_MIN_PRESET_FLOOR` from `2100W` to `2150W`.
3. **Emergency Thermal Spike Calibration**:
   - *Problem*: In `app/miner_monitor.py`, `fan_governor_emergency_temp_c` defaulted to `83.5°C`, dangerously close to hardware thermal shutdown.
   - *Fix*: Calibrated default emergency threshold to `83.0°C`.
4. **Headroom Chilling Wiring (Spec 075 Link)**:
   - *Problem*: `preset_balancer.py` generated `decision.boost_cooling_requested` when an elevator miner reached 2500W and was thermally restricted from climbing to 2700W, but `miner_monitor.py` had not wired this signal into the fan governor.
   - *Fix*: Connected `st.boost_cooling_active` and passed `boost_cooling=True` to `compute_governor_step`. Fans ramp up to 100% PWM for 180 seconds to drop chip temperatures below $78.5^\circ\text{C}$, enabling the 2700W step safely.
5. **Vnish Preset Clamping & Tripwire Resilience**:
   - *Problem*: Staged ramp-up in `miner_monitor.py` did not pass `clamp_top_preset=False, top_preset="2700"` when elevating to 2700W. Tripwire comparison threw errors if a miner was on an off-ladder watt value.
   - *Fix*: Updated `set_miner_preset` and `safe_set_miner_preset` in `app/vnish/client.py` to support `top_preset: Optional[str] = None`. Added numeric watt comparison fallback in `refresh_vnish_overclock_settings`.
6. **Telegram Display Name Dict Reference & Token Registry API**:
   - *Problem*: In `app/telegram/commands/flash.py` and `app/miner_monitor.py`, `display_name(miner)` was passed a dictionary instead of string, leading to malformed miner name resolution. In addition, `context.token_registry.generate()` was called instead of `create_token()`.
   - *Fix*: Standardized on `display_name(miner.get("name", ""))` and `normalize_miner_name(miner.get("name", ""))`. Added `generate = create_token` alias in `CallbackTokenRegistry` and updated command calls.

---

## 2. Implementation Components

1. **Hardware Flasher Module (`app/network/firmware_flasher.py`)**:
   - `is_stock_bitmain(host)`: Probes port 80 HTTP digest realm (`"antMiner Configuration"` / `lighttpd/1.4.32`).
   - `flash_bitmain_nand(host, package_path)`: Streams multipart form-data to `/cgi-bin/upgrade.cgi` using HTTP Digest Authentication (`root:root`).
   - Handles BeagleBone Black socket disconnect on reboot cleanly.
2. **Miner Provisioning Module (`app/governance/miner_provisioner.py`)**:
   - `provision_miner_from_profile(host, miner_name, password)`: Unlocks API, injects Binance mining pools, sets preset to 2300W with top preset 2700W, and uploads 378 tuned chip frequencies from `data/miner_profiles/{miner_name}.json`.
3. **Telegram Command & Callbacks (`app/telegram/commands/flash.py`)**:
   - Command `/flash_vnish <miner>` with 2-step interactive verification (inline buttons `flash_cfm` / `flash_ccl` or text `CONFIRM`).
   - Background worker daemon `FlashWorker_{miner}` with step-by-step phase progress reporting to Telegram:
     - `[1/4] Verificando estado Bitmain de fábrica...`
     - `[2/4] Subiendo tarball instalador (56 MB)...`
     - `[3/4] Esperando reinicio de BeagleBone Black en VNish 1.2.6 (60-90s)...`
     - `[4/4] Inyectando pools, preset 2300W y matriz de 378 chips afinados...`
     - `[FLASHEO & APROVISIONAMIENTO EXITOSO]`

---

## 3. Test Suite Execution Results

### Regression Suite Summary:
```powershell
============================ 1262 passed in 41.69s ============================
```

### Dedicated Unit Test Suites:
- `tests/test_firmware_flasher.py`: 9 passed
- `tests/test_miner_provisioner.py`: 5 passed
- `tests/test_telegram_flash_command.py`: 12 passed
- `tests/test_telegram_callbacks.py`: 29 passed
- `tests/test_preset_balancer.py`: 20 passed
- `tests/test_paired_elevator_contingency.py`: 15 passed

### Python Compilation Validation:
```powershell
& ".\.venv\Scripts\python.exe" -m py_compile app\miner_monitor.py app\telegram\commands\flash.py app\network\firmware_flasher.py app\governance\miner_provisioner.py app\governance\preset_balancer.py app\governance\adaptive_contingency.py app\vnish\client.py app\telegram\callbacks.py app\telegram\router.py
# Exit Code: 0 (Clean)
```

---

## 4. Production Telemetry Verification

- **S19JPRO-23**: ~78-81 TH/s | Preset: 2300W / Top: 2700W | Unblocked and healthy.
- **S19JPRO-24**: ~88-90 TH/s | Preset: 2300W / Top: 2700W | VNish 1.2.6 NAND restored, 378 tuned chips.
- **S19JPRO-25**: ~86-88 TH/s | Preset: 2300W / Top: 2700W | OK.
- **S19JPRO-26**: ~91-93 TH/s | Preset: 2500W / Top: 2700W | OK.
- **Windows Service**: `MinerAlerts` operational and monitored.
