# Feature Specification: Spec 056 - Two-Tier Mining Recovery (Auto-Restart vs Auto-Reboot)

## Contexto y Motivación
En instalaciones con firmware Vnish, las caídas de tasa de hasheo o cortes de cadena (`chain_break`) frecuentemente detienen el proceso de minado (`bmminer`, estado `miner_stopped` o `restart_required: true`) mientras que la placa controladora, el sistema operativo Linux y la conectividad de red permanecen 100% funcionales y saludables.
Actualmente, el sistema recurre exclusivamente a reinicios duros de hardware (`reboot` completo vía Hashcore CLI o API), lo cual genera:
1. Caídas innecesarias de la controladora y desconexión de red de 3 a 4 minutos.
2. Desgaste prematuro de relés de potencia de las fuentes de alimentación.
3. Incapacidad de auto-recuperar mineros cuyo hasheo se detuvo y requieren únicamente un reinicio de software (`mining/restart`).

## Objetivos
1. **Nivel 1 (Soft Auto-Restart)**: Detectar cuándo un minero está detenido (`miner_state == "stopped"`, `"paused"`, o `restart_required == True` con `rate_ths == 0.0`) y ejecutar un reinicio rápido de software mediante `POST /api/v1/mining/restart` (tiempo de recuperación: 15-25 segundos).
2. **Nivel 2 (Hard Auto-Reboot Escalation)**: Si tras el auto-reinicio de Nivel 1 el minero no levanta y las placas continúan en falla (0/3 placas o hashrate 0.0 TH/s sostenido por 10 minutos), escalar al auto-reboot completo de hardware (Spec 055) aplicando los 6 interlocks constitucionales.
3. **Discriminación Inteligente Nativa**: Ingestar y evaluar los flags nativos expuestos por `/api/v1/status`: `restart_required` y `reboot_required`.
4. **Interlocks de Nivel 1**:
   - Respetar modo mantenimiento y silenciamiento (`is_snoozed`, `in_maintenance`).
   - Cooldown propio de auto-reinicio (ej. 300 segundos) para evitar bucles rápidos de reinicio de software.
   - Máximo de reintentos de software antes de escalar a Nivel 2.
5. **Observabilidad y UX**: Tarjetas diferenciadas en Telegram (`[AUTO-RESTART]` vs `[AUTO-REBOOT]`) y registro en base de datos.
