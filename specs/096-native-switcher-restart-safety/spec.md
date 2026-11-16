# Spec 096 — Reinicios seguros durante cambios nativos de potencia

Estado: desplegada y verificada en ventana de660s; releaseGit yD+1 pendientes. Riesgo HIGH, prioridad P0.
Dependencia: 094 cerrada y publicada como a8ce841. Esta corrección precede a 095,
que permanece planificada y sin implementación.

El usuario solicita corregir reinicios y temperaturas bajas, conservar el mayor
rendimiento sostenible y restablecer la banda VNish 79/84 °C con check_time=300.

## Evidencia del problema

M24 alcanzó 86 °C: el monitor ordenó bajar a 2300 W y, un segundo después, el L1
interpretó restart_required como fallo de minado, aplicó 1800 W y reinició. La
condición eludía el soak y la temperatura del watchdog de presets. El engine
fabricaba el estado mining a partir de una respuesta TCP y desconocía auto-tuning.
M23 tuvo chain break después de subir a 2700 W; M26 también registró chain break.
La evidencia no identifica una causa AC ni demuestra un origen común entre ambos.

## Contratos

- Una marca pendiente en un minero que produce no autoriza L1. El watchdog de
  presets conserva soak, temperatura y cooldown.
- Consultar estado nativo fresco antes de considerar una intervención. Un fallo
  de lectura no autoriza L1. Autotune queda a cargo de su watchdog específico.
- Respetar mantenimiento, snooze, pausa térmica y asentamiento tras un downstep.
  Evitar L1 y L2 simultáneos o durante la ventana de recuperación de L1.
- Preservar el techo nativo durante el preclamp. QA y gobernanza se comprueban en
  los workers; el watchdog revalida estado, marca pendiente y temperatura.
- Conservar las notificaciones y protecciones existentes. No forzar reinicios de
  mineros para demostrar la corrección.

Operación: 79/84 y 300 segundos en los cuatro equipos; M23 limitado a 2500 W tras
el fallo a 2700 W; M26 limitado a 2300 W tras repetición del chain break a2500 W;
M24 y M25 conservan techos de2500 W. No se certifica la
inclusión exacta de 79 °C mostrado por la UI ni una reparación eléctrica física.
