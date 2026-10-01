# Investigación y Decisiones de Diseño: Spec 084 — Governance Dashboard (`/directivas`)

**Created**: 2026-10-01
**PROP**: PROP-020

---

## 1. Contexto de Directivas y Capas de Prevalencia (P0–P4)

A partir de la auditoría de armonización de directivas [`docs/audit/DIRECTIVES_HARMONIZATION_AUDIT.md`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/docs/audit/DIRECTIVES_HARMONIZATION_AUDIT.md), el ecosistema de gobernanza cuenta con 16 directivas activas categorizadas en 5 capas:

| Capa | Nombre / Directiva | Módulo Fuente | Indicador Visual en Card |
| :--- | :--- | :--- | :--- |
| **P0** | Thermal Guard (84°C step-down / 87°C pausa) | `thermal_guard.py` | `P0: THERMAL [OK / DOWN / PAUSE]` |
| **P0** | Failsafe Fan (100% PWM tras 3 fallos HTTP) | `fan_governor.py` | `P0: FAN [FAILSAFE]` |
| **P0** | Recovery Max Cooling (100% si $P < P_{tgt}-120W$) | `fan_governor.py` | `P0: FAN [REC_COOL]` |
| **P1** | Stock Firmware Fallback Block | `miner_monitor.py` | `P1: FW [STOCK / VNISH]` |
| **P1** | Thermal Pause Interlock | `miner_monitor.py` | `P1: RESTART [BLOCKED]` |
| **P2** | Soft Contingency Schedule (pico 5000W / valle 5400W) | `elevator_budget.py` | `P2: CONTINGENCY [PEAK / VALLEY]` |
| **P2** | Solar Thermal Envelope (cap 2500W si 11:00-17:00 y T≥82°C) | `elevator_budget.py` | `P2: SOLAR [ACTIVE / OFF]` |
| **P2** | Thermal Headroom Gate (chip < 80°C para subir a 2700W) | `elevator_budget.py` | `P2: HEADROOM [PASS / BLOCKED]` |
| **P3** | Incident Quiet Window (300s post-incidente por grupo) | `elevator_budget.py` | `P3: QUIET [QUIET: Xs / OK]` |
| **P3** | Facility Settle Window (180s entre transiciones) | `elevator_budget.py` | `P3: SETTLE [SETTLE: Xs / OK]` |
| **P3** | Symmetric Balance Preference | `elevator_budget.py` | `P3: BALANCE [OK / WAITING]` |
| **P3** | FGA Asymmetric Optimizer (cohortes COOL/STANDARD/HOT) | `facility_agent.py` | `P3: FGA [COOL / STD / HOT]` |
| **P4** | VNish Internal Daemon (rise_temp/decrease_temp) | Firmware VNish | `P4: VNISH [NOMINAL / AUTO]` |
| **P4** | Headroom Chilling (`boost_cooling` preventivo) | `fan_governor.py` | `P4: BOOST [ACTIVE / OFF]` |

---

## 2. Restricción Estricta Mobile-First ($\le 32$ Columnas)

Las pantallas móviles en Telegram requieren que los mensajes no superen los **32 caracteres por línea** para evitar saltos automáticos no intencionados (*line-wrap*).

### Tarjeta de Flota (`/directivas`)
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

### Tarjeta Detallada de Minero (`/directivas M24`)
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

## 3. Modelo de Persistencia en SQLite (`governance_snapshots`)

### Estimación de Crecimiento y Rendimiento
- **Volumen**: 4 mineros × 2 registros/minuto (ticks cada 30s) = 8 registros/minuto = 11,520 registros/día.
- **Tamaño por fila**: ~220 bytes.
- **Tasa diaria**: ~2.5 MB/día.
- **Retención**: 7 días estándar en WAL mode = ~17.5 MB (completamente seguro para almacenamiento embebido).
- **Indexación**:
  - `ix_gov_snapshots_created`: Búsquedas temporales de flota.
  - `ix_gov_snapshots_miner`: Búsquedas temporales por minero para el dashboard y el futuro *Incident Autopsy Engine*.

---

## 4. Detección Proactiva de Deadlocks (Fricción F-02)

### Condición Lógica
El deadlock ocurre cuando un minero queda clavado en ventilación forzada al 100% debido a discrepancia entre la potencia medida y el target, sin poder avanzar:
```python
is_deadlocked = bool(
    getattr(state, "governor_last_action", "") == ACTION_RECOVERY_MAX_COOLING
    and getattr(state, "governor_recovery_since_ts", None) is not None
    and (now_ts - state.governor_recovery_since_ts) > 300.0
    and not getattr(state, "is_warming_up", False)
)
```

### Protocolo de Alerta
- Se emite una alerta única hacia el chat autorizado de Telegram:
  `⚠️ ALERTA DE GOBERNANZA: S19JPRO-24 estancado en RECOVERY_MAX_COOLING por >300s (potencia: 2498W / target: 2700W). Verificar si requiere reinicio de cgminer (/agent o /directivas).`
- Cooldown: 1800 segundos (30 minutos) por minero para prevenir saturación de notificaciones.
