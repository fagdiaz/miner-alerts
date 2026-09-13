# Implementation Plan - Spec 056: Two-Tier Mining Recovery (Auto-Restart vs Auto-Reboot)

## User Review Required

> [!IMPORTANT]
> Esta spec introduce la arquitectura de recuperación en dos niveles: Nivel 1 (Auto-reinicio rápido de proceso de minado vía REST API) y Nivel 2 (Escalación a auto-reboot completo de hardware cuando Nivel 1 no resuelve la falla).
> Para mantener la máxima precisión cognitiva (~40-50% por iteración en Gemini 3.8 Flash High) y cero riesgo de regresión en producción, el desarrollo se divide en **4 Iteraciones Bounded y Secuenciales**.

---

## 4 Iteraciones Bounded para Gemini 3.8 Flash High

### Iteración 1: Cliente REST Vnish y Modelo de Estado de Minado
- **Objetivo**: Implementar `safe_restart_mining(host, password, timeout)` en `app/vnish/client.py` y estructurar la extracción de flags (`restart_required`, `reboot_required`, `miner_state`) en `get_miner_status`.
- **Riesgo Operativo**: **0%** (funciones puras desacopladas del monitor, probadas con tests unitarios mockeados).

### Iteración 2: Evaluación de Nivel 1 (Soft Auto-Restart Policy)
- **Objetivo**: Crear la función pura de evaluación de auto-reinicio de minado (`evaluate_auto_restart_candidate`), con temporizador de cooldown (`auto_restart_cooldown_seconds`, default 300s), límites de reintentos y soporte en `MinerState` (`last_auto_restart_ts`, `auto_restart_count`).
- **Riesgo Operativo**: Muy bajo (solo lógica de decisión y estado).

### Iteración 3: Canalización en el Monitor y Escalación a Nivel 2 (Auto-Reboot)
- **Objetivo**: Integrar la llamada a `safe_restart_mining` cuando el minero califica para Nivel 1. Si Nivel 1 falla o las placas continúan caídas, preservar la escalación a `run_hashcore_cli(..., "reboot")` de la Spec 055 tras cumplirse los 10 minutos sostenidos y los 6 interlocks.
- **Riesgo Operativo**: Medio (controlado con interlocks y modo QA).

### Iteración 4: UX Telegram, Certificación Global (860+ tests), Commit y Despliegue
- **Objetivo**: Notificación ejecutiva `AUTO-RESTART` vs `AUTO-REBOOT`, ejecución de la suite completa de pruebas, actualización de bitácoras, commit, push y reinicio del servicio Windows.
- **Riesgo Operativo**: Bajo.
