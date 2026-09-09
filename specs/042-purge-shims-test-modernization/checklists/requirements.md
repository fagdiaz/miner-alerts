# Checklist de Requisitos: Spec 042 - Purga Limpia de Shims y Modernización de Tests en `app/`

## Requisitos de Higiene y Ordenamiento Máximo
- [ ] CHK01: Mapear todos los archivos de prueba en `tests/` que aún importan desde módulos en la raíz de `app/`.
- [ ] CHK02: Actualizar las importaciones canónicas y `unittest.mock.patch` en `tests/` hacia los dominios canónicos (`app.core`, `app.vnish`, `app.governance`, `app.telegram`).
- [ ] CHK03: Eliminar los 22 archivos shims en `app/` mediante `git rm`.
- [ ] CHK04: Verificar que no queden archivos `.py` sueltos en `app/` excepto `app/miner_monitor.py` y `app/__init__.py`.
- [ ] CHK05: Validar que 587/587 tests pasen limpiamente sin advertencias de módulos no encontrados.
- [ ] CHK06: Validar auditoría de release con `tools/release_audit.py --check-only`.
- [ ] CHK07: Garantizar continuidad operativa del servicio en producción `MinerAlerts`.
