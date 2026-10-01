# Evidence: Spec 084 — Governance Dashboard (`/directivas`) (PROP-020)

**Fecha**: 2026-10-01
**Ejecutor**: Gemini 3.8 Flash High
**Estado**: CERTIFIED ✅

---

## 1. py_compile — Módulos Implementados y Modificados

### Módulos Principales
```powershell
& ".\.venv\Scripts\python.exe" -m py_compile app\core\event_store.py app\governance\governance_context.py app\governance\directives_dashboard.py app\telegram\commands\directives.py app\telegram\router.py app\miner_monitor.py tests\test_governance_dashboard.py
# Exit code: 0 (OK)
```

---

## 2. Tests Unitarios y de Integración — `pytest tests/test_governance_dashboard.py -v`

```text
tests/test_governance_dashboard.py::test_event_store_governance_snapshots PASSED [ 16%]
tests/test_governance_dashboard.py::test_evaluate_recovery_deadlock PASSED [ 33%]
tests/test_governance_dashboard.py::test_fleet_directives_card_formatting_max_32_cols PASSED [ 50%]
tests/test_governance_dashboard.py::test_miner_directive_card_formatting_max_32_cols PASSED [ 66%]
tests/test_governance_dashboard.py::test_deadlock_alert_formatting_max_32_cols PASSED [ 83%]
tests/test_governance_dashboard.py::test_directives_command_router_dispatch PASSED [100%]

============================== 6 passed in 0.72s ==============================
```

---

## 3. Verificación de Regresión en Gobernanza y Actuadores Conexos

```powershell
& ".\.venv\Scripts\python.exe" -m pytest tests\test_fga_actuator.py tests\test_facility_agent.py tests\test_governance_context_contracts.py -v
# 48 passed in 1.42s (OK)
```

---

## 4. Suite Global del Sistema — `pytest -q`

```text
1483 passed, 75 subtests passed in 42.34s (0 fallos, 0 errores)
```
- Baseline previo: 1477 passed, 75 subtests passed.
- Ganancia neta: +6 tests rigurosos verificando DDL SQLite, retención, formato Mobile-First $\le 32$ columnas, deadlock watchdog y dispatch Telegram.

---

## 5. Higiene de Código y Formato

```powershell
git diff --check
# Exit code: 0 (Sin trailing whitespaces)
```

---

## 6. Verificación de Invariantes de Seguridad y Contratos

1. **Mobile-First Estricto ($\le 32$ cols)**: Verificado programáticamente en `test_fleet_directives_card_formatting_max_32_cols`, `test_miner_directive_card_formatting_max_32_cols` y `test_deadlock_alert_formatting_max_32_cols`. Ninguna línea excede 32 caracteres.
2. **Compatibilidad Inversa en EventStore.prune()**: `EventStore.prune()` ejecuta el DELETE de `governance_snapshots` expiradas manteniendo intacto el diccionario de retorno de 5 claves requerido por `test_event_store.py` y `miner_monitor.py`. Adicionalmente se provee `prune_governance_snapshots()`.
3. **Deadlock Watchdog Anti-Spam**: Detecta estados `ACTION_RECOVERY_MAX_COOLING` persistentes por $>300$s suprimiendo alertas en fases de warmup y aplicando un cooldown de 1800s (30m) por minero.
4. **Protección de Secretos y Configuración**: No se tocan ni versionan `app/config.json` ni `app/state.json`. Cero tokens ni IPs privadas en repositorios.
