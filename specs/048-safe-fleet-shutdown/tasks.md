# Tareas: Spec 048 - Safe Fleet Shutdown & Multi-Select Maintenance Mode

## Estado General
- **Total Tareas**: 8
- **Completadas**: 8
- **Pendientes**: 0

---

## Tareas de Fase 1 (Cliente Vnish, Orquestador y Pruebas de Dominio)

- [x] **T1: Métodos de Parada y Reanudación en Cliente Vnish (`app/vnish/client.py`)**:
  - Implementar `stop_mining(host, token, ...)` contra `POST /api/v1/mining/stop`.
  - Implementar `resume_mining(host, token, ...)` contra `POST /api/v1/mining/resume`.
  - Envolver en wrappers transaccionales seguros `safe_stop_mining` y `safe_resume_mining`.

- [x] **T2: Orquestador Desacoplado de Parada y Purga Térmica (`app/governance/fleet_shutdown.py`)**:
  - Crear clase/funciones de coordinación paralela de parada.
  - Implementar secuencia de purga térmica activa (45s de ventilación forzada).
  - Formatear tarjeta de confirmación de área eléctrica segura en $\le 32$ columnas.

- [x] **T3: Suite Unitaria de Dominio (`tests/test_fleet_shutdown.py`)**:
  - Validar mocks de API exitosos y con timeout.
  - Validar cálculo de purga térmica y contratos de retorno.

---

## Tareas de Fase 2 (Selector Multiselección Táctil y UI Móvil)

- [x] **T4: Vistas Táctiles del Selector en Command Center (`app/telegram/command_center.py`)**:
  - Diseñar `render_shutdown_menu(states, miners, selected_mask)` con casillas `⬜`/`☑️`.
  - Diseñar botón dinámico de acción `[ 🛑 APAGAR SELECCIONADOS (N) 🛑 ]`.
  - Diseñar `render_shutdown_confirmation(...)` con token de 2 pasos.
  - Diseñar menú de reanudación `render_resume_menu(...)`.

- [x] **T5: Pruebas Unitarias de UI Móvil (`tests/test_command_center.py`)**:
  - Validar que todas las líneas cumplan $\le 32$ columnas visibles.
  - Validar mutación determinista de máscaras de selección (`0000` $\leftrightarrow$ `1010`).

---

## Tareas de Fase 3 (Integración en Monitor, Callbacks, Interlocks y Certificación)

- [x] **T6: Conexión de Callbacks y Comandos de Texto (`app/miner_monitor.py`)**:
  - Conectar handlers `cc:act:sd_tog`, `cc:act:sd_req`, `cc:act:sd_cfm`, `cc:act:sd_ccl`, `cc:act:resume`.
  - Implementar comandos de texto `/shutdown [id1 id2|all]`, `/stop`, `/resume [id1 id2|all]`.
  - Aplicar Auto-Snooze de Mantenimiento de 4 horas y Auto-Unsnooze al reanudar.

- [x] **T7: Armonización de Comandos y Subsistemas del Monitor**:
  - Registrar `/shutdown` y `/resume` en `app/telegram/help_center.py` (categoría `ctrl`).
  - Agregar botón `[ 🛑 Parada Segura ]` en el dashboard principal de `/menu`.
  - Agregar guarda de seguridad en `/reboot` para evitar reiniciar mineros detenidos.
  - Adaptar `/snoozed`, `/status`, `/digest`, `fan_governor` y `preset_balancer` para reconocer `stopped`.

- [x] **T8: Validación Global, Release Audit y Certificación**:
  - Ejecutar suite global completa ($\ge 695$ PASS).
  - Validar sintaxis con `py_compile`.
  - Reiniciar servicio Windows `MinerAlerts` y verificar logs limpios.
  - Actualizar `prompt.txt` y registrar entrada en `DEVELOPMENT_LOG.md`.\n