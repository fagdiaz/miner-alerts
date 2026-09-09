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

*(Las evidencias de ejecución de tests y verificación sintáctica de cada iteración se registrarán aquí a medida que avancen las Fases 2 a 6)*
