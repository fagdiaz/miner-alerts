# Checklist de Requisitos y QA: Spec 045

## Condiciones Técnicas Obligatorias RFC (C1-C10)

- [x] **C1: Contrato Mobile-First Medible**: Líneas de datos de tarjetas <= 32 caracteres visibles sin tags Markdown. Bloques de triple comilla evitados para prevenir scroll horizontal.
- [x] **C2: Registro Canónico**: `app/telegram/help_center.py` es la fuente única de verdad para comandos, categorías, aliases y riesgos. Incluye `/menu` (`/start`, `/panel`) y `/silent` (`/silencio`, `/modo_silencio`).
- [x] **C3: Callbacks Aislados y ACK Temprano**: Gramática `help:` cerrada. Callback data <= 64 bytes UTF-8. ACK rápido sin I/O previo.
- [x] **C4: Paginación Antes que Particionado**: Cada vista interactiva mide < 3,600 caracteres (evita particionado con `split_telegram_message()` que rompería tags Markdown).
- [x] **C5: Política de Formato Única**: Funciones de escape para caracteres Markdown (`*`, `_`, `` ` ``, `[`).
- [ ] **C6: Fallback Equivalente**: Preservar `reply_markup` y `parse_mode` si `queue=None` (Fase 2).
- [x] **C7: Límites de Seguridad**: Cero impacto en auto-reboot, máquina de estados, polling ni workers concurrentes.
- [x] **C8: Fases por Spec**: Spec 045 enfocada en Help Center y registro canónico; diagnósticos de flota reservados para Spec 046.
- [x] **C9: Regresión y Delivery**: Suite unitaria determinista con pruebas de ancho, Markdown hostil, callbacks inválidos y 624 tests base continuos.
- [ ] **C10: Evidencia y Activación**: Smoke manual en Telegram Mobile y registro de logs (Fase 2).
