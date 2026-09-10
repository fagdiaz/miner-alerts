# Plan de Implementación: Spec 048 - Safe Fleet Shutdown & Multi-Select Maintenance Mode

**Feature Directory**: `specs/048-safe-fleet-shutdown`
**Fecha**: 2026-09-09
**Motor Principal**: Gemini 3.8 Flash High
**Condiciones de Control**: RFC C1-C10

---

## 1. Arquitectura y Desglose de Componentes

### 1.1 Principio de Pureza y Desacoplamiento
- **Cliente Vnish (`app/vnish/client.py`)**: Implementa `stop_mining()` y `resume_mining()` asegurando patrón transaccional unlock $\to$ POST $\to$ lock en bloque `finally`.
- **Orquestador de Parada (`app/governance/fleet_shutdown.py`)**: Módulo puro de gobernanza que coordina la parada en paralelo sobre los mineros seleccionados, inicia la purga de 45s en un hilo secundario temporal acotado y emite la tarjeta de área segura sin bloquear el hilo principal de sondeo ni el poller de Telegram.
- **Selector Móvil Multiselección (`app/telegram/command_center.py`)**: Renderiza la matriz de casillas `⬜`/`☑️` usando una máscara binaria de 4 bits (`0000` a `1111`) en el `callback_data` para máxima eficiencia (<25 bytes).
- **Armonización de Comandos**: Integración con `/help`, `/menu`, `/reboot`, `/snooze`, `/status` y `/digest`.

### 1.2 Módulos Afectados
1. `app/vnish/client.py`: Endpoints `mining/stop` y `mining/resume`.
2. `app/governance/fleet_shutdown.py`: Nuevo módulo orquestador.
3. `app/telegram/command_center.py`: Vistas `render_shutdown_menu` y `render_shutdown_confirmation`.
4. `app/telegram/callbacks.py`: Registro de tokens con `action="shutdown"`.
5. `app/telegram/help_center.py`: Registro de comandos `/shutdown` y `/resume` en categoría `ctrl`.
6. `app/miner_monitor.py`: Dispatcher de comandos `/shutdown`, `/stop`, `/resume`, callbacks `sd_*`, interlocks de reboot y auto-snooze de 4h.

---

## 2. Fases de Entrega

### Fase 1: Cliente Vnish, Orquestador Desacoplado y Pruebas de Dominio
- [x] **P1.1**: Implementar `stop_mining()` y `resume_mining()` en `app/vnish/client.py` con manejo de excepciones y transaccionalidad de token.
- [x] **P1.2**: Implementar `app/governance/fleet_shutdown.py` con orquestación de parada, purga térmica de 45s y generación de tarjetas mobile-first $\le 32$ columnas.
- [x] **P1.3**: Desarrollar suite `tests/test_fleet_shutdown.py` validando mocks de API Vnish, ejecución concurrente, estados de purga y contratos de retorno.

### Fase 2: Selector Táctil Multiselección en Command Center
- [x] **P2.1**: Implementar `render_shutdown_menu(states, miners, selected_mask)` en `app/telegram/command_center.py` con casillas `⬜`/`☑️` y botón dinámico con contador.
- [x] **P2.2**: Implementar `render_shutdown_confirmation(selected_ids, token)` con diálogo de 2 pasos.
- [x] **P2.3**: Desarrollar pruebas unitarias de renderizado móvil ($\le 32$ cols) y parsing de bitmask en `tests/test_command_center.py`.

### Fase 3: Integración en Monitor, Callbacks, Interlocks y Armonización
- [x] **P3.1**: Conectar callbacks `cc:act:sd_tog`, `cc:act:sd_req`, `cc:act:sd_cfm`, `cc:act:sd_ccl`, `cc:act:resume` en `app/miner_monitor.py`.
- [x] **P3.2**: Conectar comandos de texto `/shutdown`, `/stop`, `/resume` con soporte para lista de argumentos múltiples (`/shutdown 23 25`).
- [x] **P3.3**: Aplicar Auto-Snooze de Mantenimiento de 4 horas en parada y Auto-Unsnooze en reanudación.
- [x] **P3.4**: Integrar guarda en `/reboot` para mineros en mantenimiento y armonizar `/help`, `/status`, `/digest`, Fan Governor y Preset Balancer.
- [x] **P3.5**: Ejecutar suite completa ($\ge 695$ PASS), release audit, restart de servicio y validación de sintaxis.

---

## 3. Matriz de Validación de Calidad

| Condición | Requisito | Mecanismo de Verificación |
|---|---|---|
| **C1** | Líneas de datos $\le$ 32 cols visibles | Verificación programática con `visible_line_width()` en tests |
| **C2** | Pureza y no-bloqueo del monitor | Purga térmica ejecutada en hilo desacoplado sin frenar el polling |
| **C3** | Callbacks $\le$ 64 bytes & ACK < 50ms | Máscara binaria compacta (`sd_tog:23:1010`) de <25 bytes |
| **C4** | Token criptográfico efímero (60s) | Validación estricta con `CallbackTokenRegistry` |
| **C5** | Cero falsas alarmas | Auto-snooze de 4 horas bloquea alertas de caído/dead |
| **C6** | Guarda de reinicio | `/reboot` rechaza equipos en parada intencional |
| **C7** | Windows Service Compatibility | Validación de reinicio limpio del servicio `MinerAlerts` |\n