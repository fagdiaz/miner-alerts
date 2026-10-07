# Implementation Plan: Spec 091 — Pipeline Declarativo de Hooks y Cierre V6.0

**Feature**: `091-core-daemon-hookification`  
**Dependencies**: Requiere Spec 090 cerrada  
**Target Outcome**: `app/miner_monitor.py` $\le 450$ LOC, disolución final del monolito.

---

## 1. Technical Architecture & Declarative Pipeline

```mermaid
flowchart TD
    subgraph Bootstrap [miner_monitor.py (<= 450 LOC)]
        Init["main() -> CoreSupervisoryEngine(config)"]
        Init --> Run["engine.run_forever()"]
    end

    subgraph Pipeline [app/core/engine.py: 7 Etapas Ordenadas]
        S1["StagePreTick (10): Liveness & Time Sync"]
        S2["StageAcquisition (20): Parallel Sockets & VNish"]
        S3["StageDetection (30): State Machine & Anomaly Streaks"]
        S4["StageGovernance (40): Fan Gov, Balancer, FGA, Elevators"]
        S5["StageActuator (50): Safe Reboots, Presets, Cooldowns"]
        S6["StagePersistence (60): Atomic Disk Flush & SQLite WAL"]
        S7["StagePostTick (70): Daily Digest & _WAKEUP_EVENT.wait()"]

        Run --> S1 --> S2 --> S3 --> S4 --> S5 --> S6 --> S7
        S7 -.->|Siguiente Tick| S1
    end
```

---

## 2. Step-by-Step Implementation Sequence

### Paso 1: Encapsulamiento de Inicialización
* Mover el arranque de Watchdog IPC Pipe, carga de EventStore, shims y logging a `CoreSupervisoryEngine.initialize()`.

### Paso 2: Mapeo de Etapas Procedurales a Hooks
* Conectar las rutinas de `while True:` a los hooks canónicos correspondientes en `app/core/engine.py`:
  - `PreTickHook`: heartbeats y monotonic time tracking.
  - `AcquisitionHook`: adquisición paralela mediante `AdaptiveAcquisitionEngine`.
  - `DetectionHook`: evaluación de rachas y candidaturas a reinicio.
  - `GovernanceHook`: orquestación de ventiladores, balanceador, envolvente solar y FGA.
  - `ActuatorHook`: despacho de reinicios escalonados y safe landing.
  - `PersistenceHook`: persistencia atómica de `state.json` y eventos en SQLite.
  - `PostTickHook`: digest diario y `_WAKEUP_EVENT.wait(poll_seconds)`.

### Paso 3: Reducción Definitiva de `miner_monitor.py`
* Limpiar el bucle viejo en `miner_monitor.py` y dejar únicamente la función `main()` declarativa.
* Verificar conteo de líneas con `(Get-Content app/miner_monitor.py).Count` ($\le 450$ L).

---

## 3. Verification & Quality Gates

1. `py_compile app/core/engine.py app/miner_monitor.py`.
2. `pytest -q` garantizando $\ge 1522$ tests PASS (0 fallos, 0 regresiones).
3. `preflight_stabilize.ps1` (8/8 gates PASS).
4. Reinicio y verificación en caliente del servicio Windows NSSM `MinerAlerts`.
5. Ejecución de `speckit-stabilize` y cierre formal del hito Horizon V6.0.
