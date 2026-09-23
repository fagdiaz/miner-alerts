# Evidence: Spec 079 — Agente Autónomo de Gobernanza de Planta (FGA) y Optimizador Asimétrico de Potencia

## 1. Validación de Pruebas Automatizadas

Comando: `pytest -q`
Resultado: **1343 passed, 75 subtests passed in 43.37s (100% PASS RATE)**.
Nuevas pruebas añadidas:
- `tests/test_facility_agent.py`: 11 tests PASS (Cálculo de $R_{th}$, predicción térmica, cohortes de silicio, asignación asimétrica, persistencia SQLite).
- `tests/test_agent_commands.py`: 5 tests PASS (`/agent`, `/strategy`, `/fwhy`, validación de comandos y actualización de estrategias).

## 2. Evidencia de Ejecución en Vivo en Base de Datos SQLite

Comando:
```powershell
& ".\.venv\Scripts\python.exe" -c "import sqlite3; conn=sqlite3.connect('data/miner_alerts.db'); cur=conn.cursor(); cur.execute('SELECT * FROM facility_agent_knowledge'); print(cur.fetchall())"
```
Salida obtenida en producción:
```text
[
  ('24', 0.02122, '2500W', 'STANDARD', 78.0, 25.0, 2498.0, 1789852313.8027122, 'FGA live update: R_th=0.0212 C/W (STANDARD)'),
  ('25', 0.02201, '2300W', 'STANDARD', 80.0, 25.0, 2499.0, 1789852313.803177, 'FGA live update: R_th=0.0220 C/W (STANDARD)'),
  ('26', 0.02162, '2500W', 'STANDARD', 79.0, 25.0, 2498.0, 1789852313.8035047, 'FGA live update: R_th=0.0216 C/W (STANDARD)')
]
```

## 3. Simulación de Salida del Comando `/agent`

```text
🤖 *FACILITY GOVERNANCE AGENT (FGA)*
────────────────────────────
• Estrategia Activa: *BALANCED*
• Hashrate Global: *382.4 TH/s*
• Consumo Total: *10000 W* (Proyectado: *10000 W*)
• Eficiencia Planta: *26.1 J/TH*
────────────────────────────
⚡ *ASIGNACIÓN POR ELEVADOR*:
• *ELEVATOR_1*: 5000W / 5400W máx
  - S19JPRO-23: *2500W* (T=85.0°C, R_th=0.0240, STANDARD)
  - S19JPRO-24: *2500W* (T=78.0°C, R_th=0.0212, STANDARD)
• *ELEVATOR_2*: 5000W / 5400W máx
  - S19JPRO-25: *2500W* (T=80.0°C, R_th=0.0220, STANDARD)
  - S19JPRO-26: *2500W* (T=79.0°C, R_th=0.0216, STANDARD)
────────────────────────────
💡 Comandos disponibles:
• `/strategy <modo>` (balanced|max_power|efficiency|cool_quiet)
• `/fwhy <minero>` (Explicación detallada por máquina)
```

## 4. Estado del Servicio de Windows

Comando: `Get-Service MinerAlerts`
Resultado: `Status: Running` (PID verificado y bucle de 30s ejecutando la recalibración FGA).

## 5. Auditoría de Estabilización y Neutralización de Sobre-Intervención

### 5.1. Diagnóstico Forense
- **Problema Observado**: Múltiples reinicios en Mineros 23, 25 y 26 que no ocurrían bajo operación manual estática.
- **Causa Raíz Identificada**:
  1. `auto_restart_mining=True`: `safe_set_miner_preset` forzaba la invocación de `restart_mining()` (`/api/v1/mining/restart`) en cada cambio de preset rutinario porque VNish siempre reporta `restart_required: true`.
  2. Lazo de oscilación térmica por histéresis estrecha (escalada a 2700W a <80°C, desescalada a 2500W a >=84°C) con ventana de settle de solo 180s.
  3. Desincronización de caché en `_get_miner_wattage`: utilizaba el string en caché `balancer_preset` en lugar de la potencia real de la fuente, intentando "escalar" mineros que ya estaban hasheando en 2700W.
  4. Intervención desacoplada de gobernanza: el bloque de orquestación no consultaba `_GLOBAL_INTERVENTION_GOV.presets_enabled`.

### 5.2. Correcciones Implementadas
- `_get_miner_wattage`: Resuelve potencia efectiva por consumo eléctrico real ($P \ge 2600\text{W} \to 2700\text{W}$, $P \ge 2400\text{W} \to 2500\text{W}$, etc.).
- `auto_restart_mining=False`: Suprime la terminación forzada del backend de minería en modulaciones de preset.
- Respeto a `_GLOBAL_INTERVENTION_GOV`: Modo Pasivo garantizado si los presets están desactivados por política o por el operador (`/interventions off`).

### 5.3. Telemetría de Auditoría en Producción (20:35 hs)
- **S19JPRO-23**: 2499W | 89.4 TH/s | Chip: 80°C | Uptime: 139 min (mining)
- **S19JPRO-24**: 2498W | 95.1 TH/s | Chip: 81°C | Uptime: 602 min / 10.0 horas (mining)
- **S19JPRO-25**: 2499W | 93.9 TH/s | Chip: 83°C | Uptime: 12 min sostenidos post-estabilización (mining)
- **S19JPRO-26**: 2699W | 101.7 TH/s | Chip: 78°C | Uptime: 9 min sostenidos a 2700W (mining)
- **Potencia Total**: 10.19 kW | **Hashrate Total**: 380.1 TH/s | **Reinicios**: 0 en los últimos 15 min.

### 5.4. Certificación de Pruebas
Comando: `pytest -q`
Resultado: **1346 passed, 75 subtests passed in 44.78s (100% PASS RATE)**.
Nuevas pruebas añadidas:
- `tests/test_vnish_client.py::test_set_miner_preset_does_not_restart_when_auto_restart_false`
- `tests/test_elevator_budget.py::TestWattageResolverAndGovernancePermissions::test_wattage_resolver_ground_truth_power`
- `tests/test_elevator_budget.py::TestWattageResolverAndGovernancePermissions::test_governance_policy_blocks_preset_mutations_when_presets_disabled`
