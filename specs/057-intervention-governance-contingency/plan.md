# Implementation Plan - Spec 057: Intervention Governance & Adaptive Elevator Contingency

> **Status**: Release V4.1.5 DEPLOYED & APPROVED; 902 tests PASS, Windows Service RUNNING under PID 23420.

## User Review Required

> [!IMPORTANT]
> Esta spec introduce dos capacidades operativas clave solicitadas:
> 1. **Gobernanza de Intervenciones & Modo "Vnish Libre"**: Menú interactivo en Telegram para desactivar todas las intervenciones sobre los mineros o granularmente (reinicios L1/L2, fans, presets), con temporizador de reactivación segura, preservando el monitoreo y las alertas al 100%.
> 2. **Contingencia Asimétrica Adaptativa por Elevador**: Reducción de potencia relativa al **estado actual** del minero canario (más sensible) de cada elevador ante fluctuaciones de red matutinas, con exploración de límites (escalado profundo si persiste la inestabilidad) y recuperación progresiva tras soak.
> 
> Para mantener la máxima precisión cognitiva (~40-50% por iteración en Gemini 3.8 Flash High) y cero riesgo de regresión en producción, el desarrollo se divide en **4 Iteraciones Bounded y Secuenciales**.

---

## 4 Iteraciones Bounded para Gemini 3.8 Flash High

### Iteración 1: Modelo Puro de Gobernanza de Intervenciones y Menús Táctiles de Telegram
- **Objetivo**: 
  - Diseñar el módulo puro `app/governance/intervention_policy.py` con el dataclass `InterventionGovernance`, temporizador de expiración y funciones puras de decisión (`should_allow_intervention`, `toggle_actuator`).
  - Extender `app/telegram/command_center.py` con `render_interventions_menu`, botón dinámico en `render_main_dashboard` y callbacks `cc:act:int_*`.
  - Suite de tests unitarios iniciales en `tests/test_intervention_governance.py`.
- **Riesgo Operativo**: **0%** (componentes aislados y funciones puras, sin impacto en el bucle en vivo).

### Iteración 2: Integración de Interlocking en Actuadores del Monitor
- **Objetivo**:
  - Conectar los checks de gobernanza en `app/miner_monitor.py` antes de cualquier llamada mutante:
    1. Auto-Restart de minado (Nivel 1).
    2. Auto-Reboot de hardware (Nivel 2).
    3. Fan Governor (control dinámico PWM). Al desactivar, devuelve los fans a modo `auto` en Vnish o congela escrituras.
    4. Preset Balancer.
  - Persistencia de `InterventionGovernance` en `state.json` con restauración en arranque y reseteo por temporizador.
  - Validar que SQLite, telemetría de cadenas, watchdog y alertas de Telegram sigan funcionando al 100% cuando las intervenciones estén apagadas.
- **Riesgo Operativo**: Muy bajo (protegido por `state_lock` y tests deterministas).

### Iteración 3: Módulo de Contingencia Asimétrica Relativa al Estado Actual (Canary Throttle)
- **Objetivo**:
  - Implementar `app/governance/adaptive_contingency.py`:
    * Resolución de estado actual: toma `current_preset` o potencia medida del minero (nunca asume 2700W fijos).
    * Identificación de mineros canarios por grupo eléctrico (`elevator_1` $\to$ S19JPRO-24; `elevator_2` $\to$ S19JPRO-25).
    * Regla de primer reinicio: solo desescala 1 peldaño el minero canario del elevador afectado.
    * Regla de prueba en los límites: si el canario vuelve a reiniciar, desescala otro peldaño. Si el minero robusto reinicia, también reduce su potencia.
    * Rampa de recuperación progresiva (Step-Up) tras 2 horas de estabilidad sin reinicios.
  - Tests unitarios en `tests/test_adaptive_contingency.py`.
- **Riesgo Operativo**: Muy bajo (lógica desacoplada y verificada con mocks).

### Iteración 4: UX Telegram, Certificación Global (880+ tests), Bitácoras y Documentación
- **Objetivo**:
  - Cablear el ruteo de callbacks en `_handle_command_center_callback` en `app/miner_monitor.py`.
  - Notificaciones ejecutivas de Telegram Mobile-First.
  - Ejecución de la suite completa de pruebas (cero regresiones sobre los 881 tests existentes).
  - Documentación en `docs/audit/DEVELOPMENT_LOG.md` y actualización de `prompt.txt`.
- **Riesgo Operativo**: Bajo.
