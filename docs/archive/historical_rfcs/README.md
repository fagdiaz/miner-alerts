# Miner Alerts — Requests for Comments (RFCs)

Este directorio centraliza las propuestas de diseño arquitectónico y de experiencia de usuario (**RFC**) previas a la creación de especificaciones formales de implementación en el marco Speckit.

---

## 📋 Proceso de RFC

1. **Creación**: Copiar [`RFC_TEMPLATE.md`](RFC_TEMPLATE.md) asignando un nombre descriptivo: `RFC_[TEMA_CORTO].md`.
2. **Revisión y Auditoría**: Se auditan los riesgos de concurrencia, impacto en Telegram (límites de mensajes, caracteres y callbacks), compatibilidad con SQLite y seguridad operativa.
3. **Aprobación**: Se asignan condiciones de aceptación (P0/P1 o condiciones C1-C10).
4. **Traducción a Specs**: Una vez aprobado, el RFC se desglosa en especificaciones atómicas numeradas dentro del directorio `specs/`.

---

## 📑 Catálogo de RFCs

| Documento | Título | Estado | Specs Resultantes |
|---|---|:---:|---|
| [`RFC_TEMPLATE.md`](RFC_TEMPLATE.md) | Plantilla Estándar de RFC | Activo | — |
| [`RFC_TELEGRAM_INTERACTIVE_CONTROL.md`](RFC_TELEGRAM_INTERACTIVE_CONTROL.md) | Centro de Control Táctil, Modo Silencio con Temporizador y Safety Thermal Guard | **Aprobado & Implementado** | [Spec 043](../../../specs/043-telegram-interactive-command-center) y [Spec 044](../../../specs/044-silent-mode-thermal-guard) |
| [`RFC_TELEGRAM_MOBILE_UX_OPTIMIZATION.md`](RFC_TELEGRAM_MOBILE_UX_OPTIMIZATION.md) | Optimización UX Telegram Mobile-First (Tarjetas $\le 32$ columnas y navegación táctil) | **Aprobado & Implementado** | [Specs 045 a 052](../../../specs) y [Spec 068](../../../specs/068-telegram-compact-ux) |

---

## 🔗 Referencias Relacionadas

- **Backlog Activo**: [`../ROADMAP.md`](../ROADMAP.md)
- **Marco Programático de Specs**: [`../SPEC_PROGRAM.md`](../SPEC_PROGRAM.md)
- **Manual de Operaciones**: [`../RUNBOOK.md`](../RUNBOOK.md)
