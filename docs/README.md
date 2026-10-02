# Miner Alerts — Centro de Documentación y Mapa Maestro

Bienvenido al centro de documentación técnica y operativa de **Miner Alerts**, el sistema de supervisión, telemetría y gobernanza en tiempo real para granjas de minado ASIC (Antminer S19j Pro con firmware Vnish).

El sistema se encuentra en **Modo de Observación Continua y Estabilización de Planta** tras la certificación y cierre del **Horizonte V5.2 de Gobernanza Integrada**.

---

## 🗺️ Mapa Maestro de Navegación

```
docs/
├── README.md                               <-- Este mapa maestro interactivo
├── audit/
│   ├── DEVELOPMENT_LOG.md                  <-- Bitácora inmutable de desarrollo (Specs 001-086)
│   └── DIRECTIVES_HARMONIZATION_AUDIT.md   <-- Auditoría canónica de directivas y gobernanza
├── speckit/                                <-- Marco de especificaciones y operación viva
│   ├── ROADMAP.md                          <-- Backlog activo, matriz de riesgos y estado de specs
│   ├── SPEC_PROGRAM.md                     <-- Marco programático, paquetes cerrados y DoD
│   ├── RUNBOOK.md                          <-- Manual de operaciones y catálogo de comandos Telegram
│   ├── DELIVERY_PLAN.md                    <-- Calendario de entregas y ventanas operativas
│   ├── TECHNOLOGY_STRATEGY.md              <-- Decisiones de arquitectura y estrategia tecnológica
│   └── MINER_DIAGNOSTICS.md                <-- Manual de la herramienta de diagnósticos CLI
├── proposals/
│   └── README.md                           <-- Registro y estado de propuestas de mejora (PROP-001 a PROP-021)
└── archive/                                <-- Repositorio centralizado de archivo histórico
    ├── README.md                           <-- Índice maestro del archivo histórico
    ├── proposals/                          <-- Propuestas históricas archivadas
    ├── historical_rfcs/                    <-- RFCs de Telegram y UX móvil implementadas
    ├── historical_plans/                   <-- Planes de acción de fases cerradas (V3, V4, V5, V5.1)
    ├── historical_audits/                  <-- Auditorías previas de directivas y QA
    ├── historical_diagnostics/             <-- Capturas y baselines de telemetría de julio/agosto 2026
    └── historical_artifacts/               <-- Artefactos de pruebas de recuperación
```

---

## 🧭 Secciones Principales del Sistema

### 1. Operación y Gobernanza Viva
- **Auditoría Canónica de Directivas**: [`docs/audit/DIRECTIVES_HARMONIZATION_AUDIT.md`](audit/DIRECTIVES_HARMONIZATION_AUDIT.md) — Análisis de fricciones, resolución de interlocks Fan Governor / Elevator Budget / VNish, y directivas operativas vigentes.
- **Manual de Operaciones (Runbook)**: [`docs/speckit/RUNBOOK.md`](speckit/RUNBOOK.md) — Catálogo de comandos de Telegram (`/menu`, `/status`, `/fans`, `/autopsia`, `/directivas`, `/efficiency`), manejo de contingencias y procedimientos de guardia.
- **Diagnósticos de Red y Hardware**: [`docs/speckit/MINER_DIAGNOSTICS.md`](speckit/MINER_DIAGNOSTICS.md) — Procedimientos para socket 4028, API REST VNish y herramientas locales.

### 2. Historial Canónico de Desarrollo
- **Bitácora Inmutable**: [`docs/audit/DEVELOPMENT_LOG.md`](audit/DEVELOPMENT_LOG.md) — Registro cronológico inverso (*newest-first*) de todas las especificaciones implementadas, pruebas de regresión, mitigación de riesgos e incidentes certificados (Specs 001 a 086). **Regla de oro: estrictamente aditiva e inmutable**.

### 3. Planificación y Backlog Activo
- **Roadmap del Sistema**: [`docs/speckit/ROADMAP.md`](speckit/ROADMAP.md) — Estado de la flota, matriz de riesgos, backlog de observación continua y próxima iniciativa planificada ([Spec 087: Monolith Decoupling Phase 3](speckit/ROADMAP.md)).
- **Programa de Especificaciones**: [`docs/speckit/SPEC_PROGRAM.md`](speckit/SPEC_PROGRAM.md) — Paquetes cerrados de Horizonte V5.2, dependencias técnicas y Definición de Terminado (DoD).
- **Plan de Entrega y Ventanas**: [`docs/speckit/DELIVERY_PLAN.md`](speckit/DELIVERY_PLAN.md) — Ventana activa de observación continua y estabilización de planta a 2500W / 2700W.

### 4. Propuestas de Mejora Resueltas
- **Índice de Propuestas**: [`docs/proposals/README.md`](proposals/README.md) — Registro de todas las propuestas históricas (PROP-001 a PROP-021) implementadas, certificadas e integradas al código productivo.

### 5. Repositorio de Archivo Histórico
- **Archivo Consolidado**: [`docs/archive/README.md`](archive/README.md) — Documentos de fases previas, diagnósticos antiguos, planes cerrados y RFCs implementadas, preservados con trazabilidad Git sin ruido documental.

---

## 🛡️ Reglas de Oro de Calidad e Invariantes

1. **Inmutabilidad del Development Log**: [`docs/audit/DEVELOPMENT_LOG.md`](audit/DEVELOPMENT_LOG.md) no se borra, no se trunca ni se reordena; solo admite entradas aditivas en el encabezado.
2. **Backlog Único**: [`docs/speckit/ROADMAP.md`](speckit/ROADMAP.md) y [`docs/speckit/SPEC_PROGRAM.md`](speckit/SPEC_PROGRAM.md) son las únicas fuentes de verdad de estado técnico.
3. **Cero Secretos en Repositorio**: `app/config.json`, `app/state.json`, contraseñas y tokens permanecen estrictamente fuera del control de versiones.
4. **Formato Mobile-First**: Todas las interfaces de usuario para Telegram deben garantizar líneas de $\le 32$ columnas visibles.
5. **Certificación Obligatoria**: Todo cambio debe validar `py_compile`, `git diff --check`, `pytest -q` y la compuerta de estabilización exhaustiva `speckit-stabilize`.
