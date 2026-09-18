# Miner Alerts — Centro de Documentación

Bienvenido al centro de documentación técnica y operativa de **Miner Alerts**, el sistema de supervisión, telemetría y protección en tiempo real para granjas de minado ASIC (Antminer S19j Pro con firmware Vnish).

Este directorio organiza la arquitectura, procedimientos de operador, propuestas de mejora, historial de auditoría y el marco formal de especificaciones del proyecto.

---

## 🗺️ Mapa de Navegación Documental

```
docs/
├── README.md                               <-- Este índice maestro
├── audit/
│   └── DEVELOPMENT_LOG.md                  <-- Bitácora inmutable de desarrollo (Specs 001-075)
├── proposals/
│   ├── SYSTEM_IMPROVEMENT_PROPOSALS.md     <-- Propuestas maestras del sistema (PROP-001 a PROP-010)
│   ├── PROP-009-contingency-stabilization-hypotheses.md <-- Estudio de estabilización de elevadores
│   └── PROP-010-soft-landing-recovery-psu-protection.md <-- Protección de fuentes APW12 y Headroom Chilling
└── speckit/                                <-- Marco de especificaciones y operación viva
    ├── README.md                           <-- Guía del framework Speckit y ciclo de vida
    ├── ROADMAP.md                          <-- Backlog activo, matriz de riesgos y estado de specs
    ├── RUNBOOK.md                          <-- Manual de operaciones y catálogo de comandos Telegram
    ├── SPEC_PROGRAM.md                     <-- Marco programático, límites arquitectónicos y DoD
    ├── DELIVERY_PLAN.md                    <-- Calendario de entregas y ventanas de estabilización
    ├── TECHNOLOGY_STRATEGY.md              <-- Decisiones de arquitectura y estrategia tecnológica
    ├── MINER_DIAGNOSTICS.md                <-- Manual de la herramienta de diagnósticos CLI
    ├── rfcs/                               <-- Requests for Comments (diseño arquitectónico)
    │   ├── README.md                       <-- Índice y flujo de aprobación de RFCs
    │   ├── RFC_TEMPLATE.md                 <-- Plantilla para nuevos RFCs
    │   ├── RFC_TELEGRAM_INTERACTIVE_CONTROL.md
    │   └── RFC_TELEGRAM_MOBILE_UX_OPTIMIZATION.md
    └── archive/                            <-- Archivo histórico y decisiones terminales
        ├── README.md                       <-- Índice de documentos archivados
        ├── HASHCORE_TOOLKIT_STRATEGY.md
        ├── INTERFACE_STRATEGY.md
        ├── V3_EXPANSION_PLAN.md
        └── plans/                          <-- Planes de acción de fases cerradas
            ├── ACTION_PLAN_V5_MODULARIZATION.md
            ├── ACTION_PLAN_POST_V5_EVOLUTION.md
            ├── ACTION_PLAN_V5_1_HORIZON.md
            └── ACTION_PLAN_REPO_CLEANUP_AND_ROADMAP.md
```

---

## 📚 Guía Rápida por Rol

### Para Operadores de Campo & Minería
- **Operación diaria y comandos de Telegram**: [`speckit/RUNBOOK.md`](speckit/RUNBOOK.md).
- **Diagnósticos de hardware y red 4028**: [`speckit/MINER_DIAGNOSTICS.md`](speckit/MINER_DIAGNOSTICS.md).
- **Entendimiento de incidentes y alarmas**: [`speckit/RUNBOOK.md`](speckit/RUNBOOK.md) § Contingencias.

### Para Desarrolladores & Agentes AI
- **Backlog maestro y prioridades**: [`speckit/ROADMAP.md`](speckit/ROADMAP.md).
- **Instrucciones para agentes e invariantes del monitor**: [`../AGENTS.md`](../AGENTS.md).
- **Marco de especificaciones y Definición de Terminado (DoD)**: [`speckit/SPEC_PROGRAM.md`](speckit/SPEC_PROGRAM.md).
- **Estrategia y principios tecnológicos**: [`speckit/TECHNOLOGY_STRATEGY.md`](speckit/TECHNOLOGY_STRATEGY.md).
- **Historial de cambios y auditoría**: [`audit/DEVELOPMENT_LOG.md`](audit/DEVELOPMENT_LOG.md).

### Para Arquitectura y Nuevas Propuestas
- **Propuestas de mejora del sistema (PROP)**: [`proposals/SYSTEM_IMPROVEMENT_PROPOSALS.md`](proposals/SYSTEM_IMPROVEMENT_PROPOSALS.md).
- **Requests for Comments (RFCs)**: [`speckit/rfcs/README.md`](speckit/rfcs/README.md).
- **Historial de planes cerrados**: [`speckit/archive/README.md`](speckit/archive/README.md).

---

## 🛡️ Reglas de Oro Documentales

1. **La Joya del Proyecto**: [`audit/DEVELOPMENT_LOG.md`](audit/DEVELOPMENT_LOG.md) debe actualizarse en cada spec o cambio con un registro cronológico inverso (*newest-first*).
2. **Backlog Único**: [`speckit/ROADMAP.md`](speckit/ROADMAP.md) es la única fuente de verdad para el estado de las especificaciones y riesgos.
3. **Cero Secretos**: Ningún archivo bajo `docs/` debe contener contraseñas, tokens de Telegram, chat IDs de producción o datos confidenciales de la red.
