# Evidence: Spec 041 - Arquitectura Modular y Reorganización de Dominios en `app/`

## Estado y Metadatos
- **Spec ID**: `041-app-modular-architecture`
- **Fecha de Inicio**: 2026-09-08
- **Línea Base Inicial**: 587/587 tests pasando en 11.58s. Servicio Windows `MinerAlerts` activo bajo PID 71304.
- **Resultado Global**: En Proceso (Fase 1 completada)

---

## 1. Línea Base Pre-Migración

```text
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py"
Ran 587 tests in 11.586s
OK
```

```text
& ".\.venv\Scripts\python.exe" tools\release_audit.py --check-only
RELEASE AUDIT: PASS. Runtime payload SHA-256: 810e41c17a914e0999d44e5ba22b151a0db10812a632a54e2a2838aea33089e4
Payload files counted: 55
Terminal dispositions: 8/8 verified
```

---

## 2. Registro de Fases de Migración

### Fase 2: Dominio Telegram (`app/telegram/`) - [COMPLETADA]
- **Archivos migrados**:
  * `app/telegram_callbacks.py` -> `app/telegram/callbacks.py`
  * `app/telegram_charts.py` -> `app/telegram/charts.py`
  * `app/telegram_messages.py` -> `app/telegram/messages.py`
  * `app/telegram_snooze.py` -> `app/telegram/snooze.py`
  * `app/daily_digest.py` -> `app/telegram/daily_digest.py`
- **Subpaquete creado**: `app/telegram/__init__.py` con re-exportaciones canónicas de los 5 submódulos y alias retrocompatibles (`TokenRegistry = CallbackTokenRegistry`).
- **Shims retrocompatibles creados**: 5 shims en `app/` preservando acceso sin quiebres (incluyendo `_connect_ro` para compatibilidad de tests de concurrencia).
- **Validación sintáctica**:
  ```powershell
  & ".\.venv\Scripts\python.exe" -m py_compile app\telegram\__init__.py app\telegram\callbacks.py app\telegram\charts.py app\telegram\messages.py app\telegram\snooze.py app\telegram\daily_digest.py app\telegram_callbacks.py app\telegram_charts.py app\telegram_messages.py app\telegram_snooze.py app\daily_digest.py
  # Retorno: 0 (OK)
  ```
- **Validación de Suite de Tests**:
  ```text
  Ran 587 tests in 10.887s
  OK
  ```
- **Auditoría de Release**:
  ```text
  RELEASE AUDIT: PASS. Runtime payload SHA-256: 097ddf9de957c87e97fcd9984e10bdbb8724632852eedaf5867de85cae2323bd
  Payload files counted: 61
  Terminal dispositions: 8/8 verified
  ```
