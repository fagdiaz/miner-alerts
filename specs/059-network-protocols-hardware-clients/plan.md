# Implementation Plan: Spec 059 — Network Protocols & Hardware Clients Extraction (MT-02)

**Branch**: `codex/022-adaptive-acquisition` | **Date**: 2026-09-15 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `specs/059-network-protocols-hardware-clients/spec.md`  

---

## Summary

Extraer la comunicación de socket crudo TCP 4028 (protocolo CGMiner/Telnet JSON), los clientes de integración de hardware (Hashcore Toolkit CLI) y unificar la interfaz REST para Vnish fuera de `app/miner_monitor.py` en una arquitectura modular de clientes de red tipados bajo `app/network/`:
1. `app/network/cgminer_client.py`: Clase `CGMinerClient` y funciones `query_cgminer`, `read_summary`, `read_stats_snapshot`, `read_stats_active_boards`, `read_pools`, `read_version`, `count_active_boards`, `extract_temps`, `fw_hint`.
2. `app/network/hashcore_client.py`: Clase `HashcoreClient` y funciones `run_hashcore_cli`, `run_hashcore_discovery`, `get_hashcore_cli_path`.
3. `app/network/vnish_client.py`: Clase `VnishClient` tipada que proporciona métodos desacoplados con reintentos, manejo de sesiones y re-exporta funciones primitivas de `app/vnish/client.py`.
4. `app/network/__init__.py`: Paquete centralizado exportando todas las interfaces de red y clientes de hardware.
5. Fachadas y re-exportaciones en `app/miner_monitor.py` para preservar 100% de retrocompatibilidad con tests existentes e invocaciones del bucle principal.

---

## Technical Context

**Language/Version**: Python 3.12 (virtualenv en Windows 11)  
**Primary Protocols**: 
- TCP Socket 4028 (CGMiner Telnet API, JSON framed)
- Subprocess CLI (Hashcore Toolkit `.bat`/`.cmd`/executable sin creación de ventanas)
- HTTP REST API (Vnish firmware con timeouts de 2.5s y bearer token auth)  
**Testing**: `unittest` standard library (`tests/test_*.py`)  
**Target Platform**: Windows 11 Pro / Windows Service `MinerAlerts`  
**Constraints**:
- Ninguna operación de socket de red o subprocess debe ejecutarse bajo `state_lock`.
- Tolerancia a fallos: timeouts estrictos en socket (5.0s por defecto), limpieza de bytes nulos y decodificación UTF-8 con `errors="ignore"`.
- Respeto de guardarraíles QA en actuadores de hardware: si `qa_mode=True` y `qa_allow_actions=False`, el cliente de Hashcore no debe disparar subprocesos de reinicio reales.
- Conservar los contratos de inspección y símbolos en `app.miner_monitor` requeridos por las suites de tests.

---

## Constitution Check

*GATE: Must pass before implementation.*

1. **Principio 1 (Monitoreo Continuo & Seguridad)**: ✅ Las operaciones de red y llamadas a hardware se encapsulan con defensas ante timeout y caídas de conexión sin alterar la política autoritativa.
2. **Principio 2 (Single Source of Truth para Configuración)**: ✅ No se tocan archivos de configuración local ni secretos.
3. **Principio 3 (Interlocks & QA Guardrails)**: ✅ `HashcoreClient` preserva de manera estricta el bloqueo en modo QA cuando las acciones reales no están explícitamente autorizadas.
4. **Principio 4 (Windows Compatibility)**: ✅ Las llamadas de subprocess utilizan `creationflags=_NO_WINDOW_CREATION_FLAGS` (`0x08000000`) para evitar apertura de consolas en el servicio Windows.
5. **Principio 5 (Zero Regresiones)**: ✅ La suite completa de 910 tests debe pasar al 100%.

---

## Proposed Project Structure

```text
app/
├── miner_monitor.py             # Reducido al delegar funciones de red y hardware a app.network
├── network/                     # [NUEVO PAQUETE]
│   ├── __init__.py              # Exportaciones públicas de la capa de red
│   ├── cgminer_client.py        # Protocolo Socket 4028 y parsers
│   ├── hashcore_client.py       # Toolkit CLI actuador de reboots
│   └── vnish_client.py          # Cliente tipado de API REST Vnish
├── vnish/                       # Módulos especializados de telemetría y cadenas (existente)
├── telegram/                    # Módulos de mensajería y comandos (Spec 058)
├── governance/                  # Políticas de control térmico y eléctrico
└── core/                        # Núcleo de adquisición y eventos
```

---

## Migration & Facade Strategy

En `app/miner_monitor.py`:
```python
from app.network import (
    CGMinerClient,
    HashcoreClient,
    VnishClient,
    count_active_boards as _count_active_boards,
    extract_temps as _extract_temps,
    fw_hint as _fw_hint,
    get_hashcore_cli_path as _hashcore_cli_path,
    query_cgminer as _read_command,
    read_pools,
    read_stats_active_boards,
    read_stats_snapshot,
    read_summary,
    read_version,
    run_hashcore_cli,
    run_hashcore_discovery,
)
```
Esto garantiza que:
1. `from app.miner_monitor import read_summary, read_stats_snapshot, _count_active_boards, run_hashcore_cli` continúe funcionando exactamente igual.
2. Los decoradores `@patch("app.miner_monitor.read_stats_snapshot")` en los tests continúen parcheando el símbolo en el módulo `app.miner_monitor`.
3. `inspect.getsource(main)` encuentra `run_hashcore_cli(hashcore_cfg, miner, "reboot"` sin desfasar las posiciones requeridas por `test_reboot_safety.py` y `test_auto_reboot_signal_gate.py`.
