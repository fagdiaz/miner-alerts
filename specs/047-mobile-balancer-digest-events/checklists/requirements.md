# Requirements Checklist: Spec 047 - Mobile Diagnostics & Operational Events

## Requisitos Obligatorios RFC (C1-C10)

- [ ] **C1: Límite Estricto Mobile-First**: Cada línea de datos en los 7 reportes debe tener ancho visible $\le 32$ columnas.
- [ ] **C2: Pureza Funcional**: Ningún renderizador ejecuta I/O de red, consultas de sockets ni muta estados de control.
- [ ] **C3: Callbacks Aislados y ACK Rápido**: Los callbacks `diag:ref:*` no superan 64 bytes y reciben ACK inmediato (< 50ms).
- [ ] **C4: Paginación y Sin Particionado**: Cada mensaje mide $< 2,000$ caracteres para evitar split en Telegram.
- [ ] **C5: Sanitización Markdown**: Los nombres de mineros y argumentos se sanean ante caracteres hostiles.
- [ ] **C6: Fallback de Entrega**: Los mensajes son perfectamente legibles sin botones si la cola no está disponible.
- [ ] **C7: Invariantes Constitucionales**: Sin cambios a `MinerState`, políticas de reinicio, Hashcore ni workers.
