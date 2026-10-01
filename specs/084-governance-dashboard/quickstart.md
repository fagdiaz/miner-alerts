# Quickstart: Spec 084 — Governance Dashboard (`/directivas`)

**Created**: 2026-10-01
**PROP**: PROP-020

---

## 1. Comandos de Telegram

### Visualizar Estado de Toda la Flota
Envía desde la app de Telegram:
```text
/directivas
```
*(O sus alias equivalentes `/gov_status` o `/gov`)*

Respuesta:
```text
╔══════════════════════════════╗
║  DIRECTIVAS DE GOBERNANZA   ║
╚══════════════════════════════╝
M23 [2700W] 92% HOLD  OK
M24 [2700W] 92% HOLD  OK
M25 [2700W] 92% HOLD  OK
M26 [2700W] 92% HOLD  OK
--------------------------------
SOLAR: OFF (18:50)
ELEV1: 5396W [VALLEY 5400W]
ELEV2: 5398W [VALLEY 5400W]
DEADLOCK: NINGUNO
Usa: /directivas <minero>
```

### Inspección Detallada por Minero
```text
/directivas 24
```
o
```text
/directivas S19JPRO-24
```

Respuesta:
```text
╔══════════════════════════════╗
║ DIRECTIVAS: S19JPRO-24       ║
╚══════════════════════════════╝
P0: SEGURIDAD HARDWARE
  Fan: HOLD_TARGET (92%)
  Chips: 68.2°C (Techo 84°C)
  Deadlock: NO (0s)
P1: FIRMWARE & REINICIO
  Firmware: Vnish OK
  RestartReq: NO
P2: ELEVADOR & AMBIENTE
  Grupo: elevator_1
  Potencia: 2698W / 2700W
  Solar Envelope: INACTIVO
  Headroom Gate: OK (<80°C)
P3: AGENTE DE PLANTA (FGA)
  Cohorte: COOL (Rth: 0.019)
  Elevator Gate: PERMITIDO
  Contingencia: VALLE (5400W)
P4: ESTADO FIRMWARE
  Preset Activo: 2700W
```

---

## 2. Ejecución de Pruebas Automatizadas

Para validar las suites correspondientes a esta especificación:

```powershell
& ".\.venv\Scripts\python.exe" -m pytest tests/test_governance_dashboard.py -v
```

Para validar la suite completa de regresión:
```powershell
& ".\.venv\Scripts\python.exe" -m pytest -q
```
