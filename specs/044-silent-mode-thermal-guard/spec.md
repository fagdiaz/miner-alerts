# Spec 044: Modo Silencio Inteligente con Temporizador Persistente y Thermal Guard

## Estado y Metadatos
- **ID**: `044-silent-mode-thermal-guard`
- **Prioridad**: P0 (Protección de Hardware, Control Acústico Operativo y Concurrencia Crítica)
- **Estado**: ESPECIFICACIÓN APROBADA (Con Restricciones Constitucionales C1-C4)
- **Fecha**: 2026-09-08
- **Autor**: Antigravity (Gemini 3.8 Flash High)
- **Revisor y Auditor de Concurrencia**: Claude Sonnet 4.6 (Thinking)
- **Documento Base**: `docs/speckit/RFC_TELEGRAM_INTERACTIVE_CONTROL.md` (Sección 6)
- **Dependencias**: Specs 039 (Fan Governor), 040 (Presets & VNish Client), 041/042 (Modular Architecture), 043 (Interactive Command Center).

---

## 1. Contexto y Objetivos

### 1.1 El Problema Operativo
En ocasiones (visitas, reuniones, trabajo en áreas cercanas a la granja), el ruido de los ventiladores al 100% o ~80% resulta perturbador. El operador requiere reducir acústicamente los equipos a un rango moderado (40% a 70% PWM).  
Sin embargo:
1. Limitar los ventiladores sin bajar la potencia sobrecalienta los chips ASIC en cuestión de segundos.
2. Si el operador silencia manualmente las máquinas, con frecuencia olvida reactivarlas, perdiendo hashrate valioso durante días.
3. Si el monitor o el servicio NSSM se reinician durante un modo silencio, una restauración incorrecta de parámetros podría congelar los ventiladores en valores bajos con el ASIC a máxima potencia, arriesgando daños permanentes de hardware.

### 1.2 Objetivos de la Spec 044
1. **Modo Silencio / Visitas**:
   - Limitación estricta de velocidad de ventiladores a un techo seguro (ej. 40% - 70% PWM).
   - Ajuste complementario de potencia / preset de frecuencia para que los chips no superen el objetivo térmico de **82.0°C**.
2. **Temporizador Persistente Multiescala**:
   - Selección táctil de duración: `30 min`, `1 hora`, `2 horas`, `4 horas`, `6 horas` o `Indefinido`.
   - Reversión automática a máxima potencia de producción al cumplirse el plazo, con notificación formal a Telegram.
3. **Safety Thermal Guard (Protección Térmica Absoluta)**:
   - Vigilancia prioritaria en cada tick del monitor.
   - Si cualquier chip alcanza **83.0°C** (`EMERGENCY_SPIKE`) o supera **85.0°C**, el Modo Silencio se **anula de inmediato**, los ventiladores saltan al 100% forzado, se persiste la anulación en `state.json` y se envía alerta urgente a Telegram.

---

## 2. Restricciones Constitucionales Obligatorias (Auditoría Claude §6.5)

Esta especificación incorpora como restricciones de diseño no negociables las cuatro condiciones identificadas en la auditoría arquitectónica:

### Condición C1 (P0 - Concurrencia y No-Bloqueo de Polling)
- **Regla**: El hilo `telegram_polling_worker` tiene estrictamente prohibido realizar llamadas HTTP síncronas a la API de VNish.
- **Implementación**: Las órdenes de cambio de modo y PWM despachadas desde botones de Telegram se ejecutan mediante un `ThreadPoolExecutor` desacoplado con `shutdown(wait=False)` y timeouts estrictos (2.5s por minero, 5.0s flota) reutilizando el patrón ya probado en `execute_governor_cycle()`. El callback responde `answerCallbackQuery` de inmediato.

### Condición C2 (P0 - Separación Estricta de FSM y Persistencia Resiliente)
- **Regla**: El Modo Silencio (actuador de hardware) y el Snooze (supresor de alertas de software) son dos máquinas de estado finitas completamente independientes.
- **Implementación**: `MinerState` incorpora campos exclusivos y aislados:
  ```python
  silent_mode_active: bool = False
  silent_mode_revert_ts: Optional[float] = None       # Unix timestamp de expiración
  silent_mode_prev_duty: Optional[int] = None        # PWM previo para restauración
  silent_mode_prev_preset: Optional[str] = None      # Preset previo
  silent_mode_target_max_duty: int = 70             # Techo de silencio
  ```
- **Verificación en Primer Tick**: Al iniciar `miner_monitor.py` (arranque del servicio NSSM o reinicio de Windows), en `first_tick` se evalúa `silent_mode_revert_ts`. Si `revert_ts <= time.time()`, el modo silencio se cancela en caliente, se restauran los ventiladores y se registra en log.

### Condición C3 (P0 - Coexistencia Armónica entre Fan Governor y Modo Silencio)
- **Regla**: El Fan Governor (`app/governance/fan_governor.py`) y el Modo Silencio no deben competir en sentidos opuestos sobre el mismo actuador PWM.
- **Implementación**: En cada ciclo de gobernanza, si `silent_mode_active == True` para un minero, se inyectan en `GovernorConfig` límites dinámicos:
  - `min_fan_duty_percent = 40`
  - `max_fan_duty_percent = silent_mode_target_max_duty` (ej. 70%)
  De esta forma, el Gobernador modula los ventiladores exclusivamente *dentro* del rango acústico permitido mientras la temperatura sea segura (< 82.0°C).

### Condición C4 (P0 - Anulación Atómica por Thermal Guard)
- **Regla**: Ante cualquier disparo de `EMERGENCY_SPIKE` (83.0°C) o falla térmica, el estado en memoria y en disco (`state.json`) debe quedar limpio de modo silencio.
- **Implementación**: Si el monitor detecta condición de spike o emergencia:
  1. Adquiere `state_lock`.
  2. Setea `silent_mode_active = False` y `silent_mode_revert_ts = None`.
  3. Ejecuta `save_state()`.
  4. Envía comando VNish con PWM = 100%.
  5. Emite notificación urgente a Telegram:
     `⚠️ MODO SILENCIO ANULADO: Temperatura máxima alcanzó {temp}°C (Umbral seguro: 83.0°C). Ventiladores forzados al 100%.`

---

## 3. Interfaz de Usuario y Flujo de Control en Telegram

### 3.1 Teclado de Selección de Duración
Al presionar `[ 🔇 Modo Silencio ]` en el Command Center (Spec 043):
```text
🔇 MODO SILENCIO / VISITAS
Ventiladores limitados a 40% - 70% PWM.
Temp Target: <= 82.0°C.

Selecciona la duración deseada:
[ ⏱️ 30 min ]   [ ⏱️ 1 hora ]   [ ⏱️ 2 horas ]
[ ⏱️ 4 horas ]  [ ⏱️ 6 horas ]  [ ♾️ Sin límite ]
[ ❌ Desactivar Ahora ]         [ ⬅️ Volver ]
```

### 3.2 Feedback Táctil y Cuenta Regresiva
Al seleccionar por ejemplo `[ ⏱️ 2 horas ]`:
- Se aplica el límite acústico y se programa la reversión.
- Telegram edita el mensaje a:
  `✅ Modo Silencio ACTIVADO (Fans max 70% | 82°C max). Reversión automática en 1h 59m.`

---

## 4. Criterios de Aceptación y Definición de Terminado (DoD)

1. **Cumplimiento Integral de C1-C4**:
   - Pruebas deterministas de no-bloqueo en callbacks con mocks lentos de VNish (2.5s).
   - Verificación de campos independientes en `MinerState` y recuperación post-reinicio en `first_tick`.
   - Pruebas de integración Governor + Modo Silencio comprobando que el duty no supere el techo acústico salvo emergencia.
   - Test unitario de Thermal Guard verificando anulación atómica en `state.json` y disparo de alerta a 83.0°C.
2. **Pruebas de Concurrencia y FSM (`tests/test_silent_mode.py`)**:
   - Batería completa de pruebas emulando expiración normal, cancelación manual y aborto térmico.
3. **Cero Regresiones**:
   - Los 587 tests de la suite continúan pasando al 100%.
4. **Certificación en Producción**:
   - Servicio NSSM operando sin fallos y verificación de logs en caliente.
