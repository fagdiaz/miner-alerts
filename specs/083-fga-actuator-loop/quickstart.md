# Quickstart: Spec 083 — FGA Actuator Loop (PROP-019)

**Feature**: `083-fga-actuator-loop` | **Date**: 2026-10-01

---

## 1. Verificación de Tests Automatizados

Para ejecutar la suite de pruebas del actuador FGA:

```powershell
& ".\.venv\Scripts\python.exe" -m pytest tests\test_fga_actuator.py -v
```

Para validar la suite completa sin regresiones:

```powershell
& ".\.venv\Scripts\python.exe" -m pytest -q
```

---

## 2. Operación desde Telegram

### Ejecución de Optimización On-Demand
Envía al bot:
```text
/agent run
```
Respuesta esperada (formato móvil $\le 32$ columnas):
```text
🤖 FGA ACTUATOR: RUN
────────────────────────────
• Estrategia: BALANCED
• Minero: S19JPRO-26
• Transición: 2500W ➔ 2700W
• Estado: EXECUTED (o BLOCKED)
• Compuerta: ALLOW_TRANSITION
• Reposo Acometida: 180s iniciado
────────────────────────────
```

### Consulta de Historial de Acciones
Envía al bot:
```text
/agent history
```
o para un minero específico:
```text
/agent history S19JPRO-24
```

---

## 3. Inspección en SQLite

Consultar las últimas acciones registradas por el actuador en la base de datos local:

```powershell
& ".\.venv\Scripts\python.exe" -c "import sqlite3; c = sqlite3.connect('app/event_store.db'); print(c.execute('SELECT created_ts, miner_name, from_preset, to_preset, action_status, gate_name FROM facility_agent_actions ORDER BY id DESC LIMIT 5').fetchall())"
```
