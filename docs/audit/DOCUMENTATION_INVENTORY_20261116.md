# Inventario documental del proyecto — 16/11/2026

> Inventario previo a la reorganización. Los valores y rutas de la tabla conservan ese corte; los enlaces de navegación se actualizaron cuando correspondía. El [registro de normalización](DOCUMENTATION_NORMALIZATION_20261116.md) describe los cambios.

Corte para preparar una normalización posterior. Se excluye íntegramente `specs/`.
Este trabajo enumera y clasifica; no reorganiza, reescribe, elimina ni certifica la vigencia técnica del contenido.

## Alcance

- Incluye raíz, docs/, .specify/, .agents/skills/ e índices de artefactos, incluso archivos ignorados por Git.
- Distingue documentación principal, evidencia generada, manifests y archivos de soporte de docs/.
- Excluye dependencias/cachés (.git, .venv, node_modules, vendor, cachés Python), perfiles efímeros scratch/ y datos privados de runtime (data/, logs/, backups/, backup-staging/).
- Los TXT/HTML de diagnóstico se enumeran por metadatos; no se copiaron sus contenidos ni credenciales.
- No incluye docstrings, comentarios en código ni JSON/CSV/bases operativas fuera de docs/.
- Fechas y estado Git son metadatos, no pruebas de vigencia. Clasificación por ruta, extensión y encabezado; lectura funcional integral pendiente.
- El corte antecede a estos dos archivos de inventario: no se cuentan a sí mismos.

## Resumen

| Grupo principal | Archivos |
|---|---:|
| Archivo histórico | 38 |
| Auditoría y operación documentada | 13 |
| Documentación en la raíz | 3 |
| Gobierno, plantillas y extensión Git | 12 |
| Instrucciones de skills | 19 |
| Operación, arquitectura y planificación | 8 |
| Índices de artefactos y diagnósticos | 2 |
| Índices generales y propuestas | 2 |
| **Total principal** | **97** |

- Evidencia/vistas generadas: **56**.
- Manifests de dependencias: **2**.
- Archivos de soporte adicionales en docs/: **26**.
- Registros totales del CSV: **181**.
- [CSV completo](DOCUMENTATION_INVENTORY_20261116.csv).

## Listado completo de documentación principal

### Documentación en la raíz (3)

| Archivo | Encabezado declarado | Git |
|---|---|---|
| [AGENTS.md](../../AGENTS.md) | Miner Alerts Agent Instructions | versionado |
| [prompt.txt](../../prompt.txt) | Última tarea — inventario documental,16/11/2026 | versionado |
| [README.md](../../README.md) | miner-alerts | versionado |

### Índices generales y propuestas (2)

| Archivo | Encabezado declarado | Git |
|---|---|---|
| [docs/proposals/README.md](../proposals/README.md) | Propuestas de Mejora del Sistema (System Improvement Proposals) | versionado |
| [docs/README.md](../README.md) | Miner Alerts — Centro de Documentación y Mapa Maestro | versionado |

### Operación, arquitectura y planificación (8)

| Archivo | Encabezado declarado | Git |
|---|---|---|
| [docs/speckit/DELIVERY_PLAN.md](../speckit/DELIVERY_PLAN.md) | Miner Alerts Delivery Plan | versionado |
| [docs/speckit/MINER_DIAGNOSTICS.md](../operations/DIAGNOSTICS.md) | Miner Diagnostics Strategy | versionado |
| [docs/speckit/MONOLITH_DECOUPLING_MASTER_PLAN.md](../archive/historical_plans/MONOLITH_DECOUPLING_MASTER_PLAN.md) | Programa Maestro de Modularización Arquitectónica del Monolito | versionado |
| [docs/speckit/README.md](../speckit/README.md) | Miner Alerts — Speckit Guide | versionado |
| [docs/speckit/ROADMAP.md](../speckit/ROADMAP.md) | Miner Alerts Speckit Roadmap | versionado |
| [docs/speckit/RUNBOOK.md](../operations/RUNBOOK.md) | Miner Alerts Validation Runbook | versionado |
| [docs/speckit/SPEC_PROGRAM.md](../speckit/SPEC_PROGRAM.md) | (sin encabezado H1) | versionado |
| [docs/speckit/TECHNOLOGY_STRATEGY.md](../architecture/TECHNOLOGY_STRATEGY.md) | Miner Alerts Technology Strategy | versionado |

### Auditoría y operación documentada (13)

| Archivo | Encabezado declarado | Git |
|---|---|---|
| [docs/audit/BACKUP_RUNBOOK.md](../operations/BACKUP_AND_RESTORE.md) | Respaldo de EventStore — operación local | versionado |
| [docs/audit/DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md) | Historial de Desarrollo y Cambios - Miner Alerts | versionado |
| [docs/audit/DIRECTIVES_HARMONIZATION_AUDIT.md](DIRECTIVES_HARMONIZATION_AUDIT.md) | Si restart_required activo, Fan Governor usa el preset en ejecución real | versionado |
| [docs/audit/OPERATIONAL_CHECK_20261115.md](OPERATIONAL_CHECK_20261115.md) | Verificación operativa — 2026-11-15 14:34 UTC-3 | versionado |
| [docs/audit/POST_OUTAGE_AUDIT_REPORT.md](POST_OUTAGE_AUDIT_REPORT.md) | Informe de Auditoría Post-Corte de Luz: Estado del Proyecto y Comparativa Código vs Documentación | versionado |
| [docs/audit/POWERUP_POLICY_20261116.md](POWERUP_POLICY_20261116.md) | Ajuste individual de powerup — 16/11/2026 01:26 UTC-3 | nuevo |
| [docs/audit/PRODUCTION_STABILITY_20261114.md](PRODUCTION_STABILITY_20261114.md) | Producción sostenible e incidente de rama 2 — 14 de noviembre de 2026 | versionado |
| [docs/audit/STABILIZATION_REPORT_20261112_HEAT.md](STABILIZATION_REPORT_20261112_HEAT.md) | Estabilización térmica — 12 de noviembre de 2026 | versionado |
| [docs/audit/STABILIZATION_REPORT_20261114_NIGHT.md](STABILIZATION_REPORT_20261114_NIGHT.md) | Estabilización nocturna — 14 de noviembre de 2026 | versionado |
| [docs/audit/STABILIZATION_REPORT_20261114_POWERUP.md](STABILIZATION_REPORT_20261114_POWERUP.md) | Miner Alerts — reconciliación verificada el 14 de noviembre de 2026 | versionado |
| [docs/audit/STABILIZATION_REPORT_20261115_BACKUP.md](STABILIZATION_REPORT_20261115_BACKUP.md) | Spec 094 — Respaldo verificable de EventStore | versionado |
| [docs/audit/STABILIZATION_REPORT_20261115_MESSAGING.md](STABILIZATION_REPORT_20261115_MESSAGING.md) | Estabilización de mensajería — 15/11/2026 | versionado |
| [docs/audit/STABILIZATION_REPORT_20261116_RESTART_SAFETY.md](STABILIZATION_REPORT_20261116_RESTART_SAFETY.md) | Estabilización 096 — reinicios durante cambios nativos | nuevo |

### Archivo histórico (38)

| Archivo | Encabezado declarado | Git |
|---|---|---|
| [docs/archive/historical_artifacts/activate-spec021-result.txt](../archive/historical_artifacts/activate-spec021-result.txt) | (artefacto histórico TXT/HTML; contenido no leído) | versionado |
| [docs/archive/historical_artifacts/dashboard_test.html](../archive/historical_artifacts/dashboard_test.html) | (artefacto histórico TXT/HTML; contenido no leído) | versionado |
| [docs/archive/historical_artifacts/service-recovery-before-20260813-153652.txt](../archive/historical_artifacts/service-recovery-before-20260813-153652.txt) | (artefacto histórico TXT/HTML; contenido no leído) | versionado |
| [docs/archive/historical_artifacts/test-spec021-scm-recovery-result.txt](../archive/historical_artifacts/test-spec021-scm-recovery-result.txt) | (artefacto histórico TXT/HTML; contenido no leído) | versionado |
| [docs/archive/historical_audits/AUDIT_DIRECTIVES_AND_GOVERNANCE_BRIEF.md](../archive/historical_audits/AUDIT_DIRECTIVES_AND_GOVERNANCE_BRIEF.md) | Briefing de Auditoría Arquitectónica y Gobernanza de Flota | versionado |
| [docs/archive/historical_audits/QA_SYSTEM_AUDIT_2026_09_20.md](../archive/historical_audits/QA_SYSTEM_AUDIT_2026_09_20.md) | Informe de Auditoría Técnica y QA Especializado — Sistema Miner Alerts | versionado |
| [docs/archive/historical_diagnostics/baseline/baseline.md](../archive/historical_diagnostics/baseline/baseline.md) | Miner Sweet-Spot Baseline | versionado |
| [docs/archive/historical_diagnostics/dry-run/summary.md](../archive/historical_diagnostics/dry-run/summary.md) | Miner Diagnostics Snapshot | versionado |
| [docs/archive/historical_diagnostics/latest/summary.md](../archive/historical_diagnostics/latest/summary.md) | Miner Diagnostics Snapshot | versionado |
| [docs/archive/historical_diagnostics/live-20260720-213925/summary.md](../archive/historical_diagnostics/live-20260720-213925/summary.md) | Miner Diagnostics Snapshot | versionado |
| [docs/archive/historical_diagnostics/live-20260720-213940/summary.md](../archive/historical_diagnostics/live-20260720-213940/summary.md) | Miner Diagnostics Snapshot | versionado |
| [docs/archive/historical_diagnostics/live-quality/index.html](../archive/historical_diagnostics/live-quality/index.html) | (artefacto histórico TXT/HTML; contenido no leído) | versionado |
| [docs/archive/historical_diagnostics/live-raw-20260720-214134/summary.md](../archive/historical_diagnostics/live-raw-20260720-214134/summary.md) | Miner Diagnostics Snapshot | versionado |
| [docs/archive/historical_diagnostics/live-raw-20260720-215415/summary.md](../archive/historical_diagnostics/live-raw-20260720-215415/summary.md) | Miner Diagnostics Snapshot | versionado |
| [docs/archive/historical_diagnostics/spec020-runtime-smoke/summary.md](../archive/historical_diagnostics/spec020-runtime-smoke/summary.md) | Miner Diagnostics Snapshot | versionado |
| [docs/archive/historical_diagnostics/summary.md](../archive/historical_diagnostics/summary.md) | Miner Diagnostics Snapshot | versionado |
| [docs/archive/historical_plans/HASHCORE_TOOLKIT_STRATEGY.md](../archive/historical_plans/HASHCORE_TOOLKIT_STRATEGY.md) | Hashcore Toolkit Strategy | versionado |
| [docs/archive/historical_plans/INTERFACE_STRATEGY.md](../archive/historical_plans/INTERFACE_STRATEGY.md) | Interface Strategy | versionado |
| [docs/archive/historical_plans/plans/ACTION_PLAN_POST_V5_EVOLUTION.md](../archive/historical_plans/plans/ACTION_PLAN_POST_V5_EVOLUTION.md) | 🚀 PLAN DE ACCIÓN POST-V5.0: RESILIENCIA, PROTECCIÓN DE SILICIO Y OBSERVABILIDAD AVANZADA (SPECS 061 A 065) | versionado |
| [docs/archive/historical_plans/plans/ACTION_PLAN_REPO_CLEANUP_AND_ROADMAP.md](../archive/historical_plans/plans/ACTION_PLAN_REPO_CLEANUP_AND_ROADMAP.md) | 📋 PLAN DE ACCIÓN: SANEAMIENTO ARQUITECTÓNICO & SECUENCIA DE SPECS (V5.1+) | versionado |
| [docs/archive/historical_plans/plans/ACTION_PLAN_V5_1_HORIZON.md](../archive/historical_plans/plans/ACTION_PLAN_V5_1_HORIZON.md) | 🚀 PLAN DE ACCIÓN HORIZONTE V5.1 & AUDITORÍA DE SEGURIDAD OPERATIVA (SPECS 067 A 070) | versionado |
| [docs/archive/historical_plans/plans/ACTION_PLAN_V5_MODULARIZATION.md](../archive/historical_plans/plans/ACTION_PLAN_V5_MODULARIZATION.md) | 🚀 PLAN DE ACCIÓN: MODULARIZACIÓN ARQUITECTÓNICA Y DESACOPLAMIENTO DEL MONOLITO (HORIZONTE V5.0) | versionado |
| [docs/archive/historical_plans/README.md](../archive/historical_plans/README.md) | Miner Alerts — Speckit Archive | versionado |
| [docs/archive/historical_plans/V3_EXPANSION_PLAN.md](../archive/historical_plans/V3_EXPANSION_PLAN.md) | Miner Alerts — Plan de Expansión V3 y Maximización de Capacidades | versionado |
| [docs/archive/historical_rfcs/README.md](../archive/historical_rfcs/README.md) | Miner Alerts — Requests for Comments (RFCs) | versionado |
| [docs/archive/historical_rfcs/RFC_TELEGRAM_INTERACTIVE_CONTROL.md](../archive/historical_rfcs/RFC_TELEGRAM_INTERACTIVE_CONTROL.md) | RFC: Telegram Interactive Command Center & Remote Control (VNish) | versionado |
| [docs/archive/historical_rfcs/RFC_TELEGRAM_MOBILE_UX_OPTIMIZATION.md](../archive/historical_rfcs/RFC_TELEGRAM_MOBILE_UX_OPTIMIZATION.md) | RFC: Telegram Mobile UX & Visual/Functional Command Optimization | versionado |
| [docs/archive/historical_rfcs/RFC_TEMPLATE.md](../archive/historical_rfcs/RFC_TEMPLATE.md) | RFC: [Nombre Descriptivo de la Feature o Refactor] | versionado |
| [docs/archive/proposals/PROP-009-contingency-stabilization-hypotheses.md](../archive/proposals/PROP-009-contingency-stabilization-hypotheses.md) | PROP-009: Diagnóstico Exhaustivo de Reinicios Múltiples en Contingencia y Arquitectura de Estabilización de Elevadores | versionado |
| [docs/archive/proposals/PROP-010-soft-landing-recovery-psu-protection.md](../archive/proposals/PROP-010-soft-landing-recovery-psu-protection.md) | PROP-010: Arquitectura de Recuperación Suave de Hasheo, Desescalada Pre-Reinicio y Blindaje Anticolapso de Fuentes APW12 | versionado |
| [docs/archive/proposals/PROP-011-autonomous-firmware-reflash-and-hardware-ladder.md](../archive/proposals/PROP-011-autonomous-firmware-reflash-and-hardware-ladder.md) | Propuesta de Mejora Técnica: PROP-011 | versionado |
| [docs/archive/proposals/PROP-012-staggered-elevator-governance-and-soft-contingency.md](../archive/proposals/PROP-012-staggered-elevator-governance-and-soft-contingency.md) | PROP-012: Gobernanza Escalonada de Elevadores, Bajada Compartida y Soft-Contingencia Horaria | versionado |
| [docs/archive/proposals/PROP-013-elevator-noise-autotune-stall-and-thermal-protection.md](../archive/proposals/PROP-013-elevator-noise-autotune-stall-and-thermal-protection.md) | PROP-013: Supresión de Ruido Eléctrico en Elevadores, Detección de Autotune Trabado y Gobernanza Térmica Solar | versionado |
| [docs/archive/proposals/PROP-014-maximum-power-and-asymmetric-combination-roadmap.md](../archive/proposals/PROP-014-maximum-power-and-asymmetric-combination-roadmap.md) | PROP-014: Roadmap Experimental de Combinaciones de Máxima Potencia y Estabilidad en Elevadores | versionado |
| [docs/archive/proposals/PROP-015-autonomous-facility-agent-and-interactive-supervisor.md](../archive/proposals/PROP-015-autonomous-facility-agent-and-interactive-supervisor.md) | PROP-015: Agente Autónomo de Gobernanza de Planta y Supervisor Conversacional Interactivo | versionado |
| [docs/archive/proposals/PROP-016-autonomous-incident-autopsy-and-conversational-qa.md](../archive/proposals/PROP-016-autonomous-incident-autopsy-and-conversational-qa.md) | PROP-016: Motor Autónomo de Autopsia de Incidentes (Post-Mortem Analyzer) y Supervisor Conversacional Q&A en Telegram | versionado |
| [docs/archive/proposals/SYSTEM_IMPROVEMENT_PROPOSALS.md](../archive/proposals/SYSTEM_IMPROVEMENT_PROPOSALS.md) | Propuestas de Mejora y Evolución del Sistema — Miner Alerts | versionado |
| [docs/archive/README.md](../archive/README.md) | Repositorio de Archivo Histórico — Miner Alerts | versionado |

### Gobierno, plantillas y extensión Git (12)

| Archivo | Encabezado declarado | Git |
|---|---|---|
| [.specify/extensions/git/commands/speckit.git.commit.md](../../.specify/extensions/git/commands/speckit.git.commit.md) | Auto-Commit Changes | versionado |
| [.specify/extensions/git/commands/speckit.git.feature.md](../../.specify/extensions/git/commands/speckit.git.feature.md) | Create Feature Branch | versionado |
| [.specify/extensions/git/commands/speckit.git.initialize.md](../../.specify/extensions/git/commands/speckit.git.initialize.md) | Initialize Git Repository | versionado |
| [.specify/extensions/git/commands/speckit.git.remote.md](../../.specify/extensions/git/commands/speckit.git.remote.md) | Detect Git Remote URL | versionado |
| [.specify/extensions/git/commands/speckit.git.validate.md](../../.specify/extensions/git/commands/speckit.git.validate.md) | Validate Feature Branch | versionado |
| [.specify/extensions/git/README.md](../../.specify/extensions/git/README.md) | Git Branching Workflow Extension | versionado |
| [.specify/memory/constitution.md](../../.specify/memory/constitution.md) | Miner Alerts Constitution | versionado |
| [.specify/templates/checklist-template.md](../../.specify/templates/checklist-template.md) | [CHECKLIST TYPE] Checklist: [FEATURE NAME] | versionado |
| [.specify/templates/constitution-template.md](../../.specify/templates/constitution-template.md) | [PROJECT_NAME] Constitution | versionado |
| [.specify/templates/plan-template.md](../../.specify/templates/plan-template.md) | Implementation Plan: [FEATURE] | versionado |
| [.specify/templates/spec-template.md](../../.specify/templates/spec-template.md) | Feature Specification: [FEATURE NAME] | versionado |
| [.specify/templates/tasks-template.md](../../.specify/templates/tasks-template.md) | Tasks: [FEATURE NAME] | versionado |

### Instrucciones de skills (19)

| Archivo | Encabezado declarado | Git |
|---|---|---|
| [.agents/skills/speckit-analyze/SKILL.md](../../.agents/skills/speckit-analyze/SKILL.md) | (sin encabezado H1) | versionado |
| [.agents/skills/speckit-checklist/SKILL.md](../../.agents/skills/speckit-checklist/SKILL.md) | (sin encabezado H1) | versionado |
| [.agents/skills/speckit-clarify/SKILL.md](../../.agents/skills/speckit-clarify/SKILL.md) | (sin encabezado H1) | versionado |
| [.agents/skills/speckit-constitution/SKILL.md](../../.agents/skills/speckit-constitution/SKILL.md) | (sin encabezado H1) | versionado |
| [.agents/skills/speckit-git-commit/SKILL.md](../../.agents/skills/speckit-git-commit/SKILL.md) | Auto-Commit Changes | versionado |
| [.agents/skills/speckit-git-feature/SKILL.md](../../.agents/skills/speckit-git-feature/SKILL.md) | Create Feature Branch | versionado |
| [.agents/skills/speckit-git-initialize/SKILL.md](../../.agents/skills/speckit-git-initialize/SKILL.md) | Initialize Git Repository | versionado |
| [.agents/skills/speckit-git-remote/SKILL.md](../../.agents/skills/speckit-git-remote/SKILL.md) | Detect Git Remote URL | versionado |
| [.agents/skills/speckit-git-validate/SKILL.md](../../.agents/skills/speckit-git-validate/SKILL.md) | Validate Feature Branch | versionado |
| [.agents/skills/speckit-implement/SKILL.md](../../.agents/skills/speckit-implement/SKILL.md) | (sin encabezado H1) | versionado |
| [.agents/skills/speckit-plan/SKILL.md](../../.agents/skills/speckit-plan/SKILL.md) | (sin encabezado H1) | versionado |
| [.agents/skills/speckit-qa/references/risk-gates.md](../../.agents/skills/speckit-qa/references/risk-gates.md) | Risk Gates | versionado |
| [.agents/skills/speckit-qa/SKILL.md](../../.agents/skills/speckit-qa/SKILL.md) | Speckit QA | versionado |
| [.agents/skills/speckit-specify/SKILL.md](../../.agents/skills/speckit-specify/SKILL.md) | (sin encabezado H1) | versionado |
| [.agents/skills/speckit-stabilize/references/report-template.md](../../.agents/skills/speckit-stabilize/references/report-template.md) | Stabilization Audit & Remediation Report Template | versionado |
| [.agents/skills/speckit-stabilize/references/stabilization-checklist.md](../../.agents/skills/speckit-stabilize/references/stabilization-checklist.md) | Stabilization & Closeout Exhaustive QA Checklist | versionado |
| [.agents/skills/speckit-stabilize/SKILL.md](../../.agents/skills/speckit-stabilize/SKILL.md) | Speckit Stabilize & Release Closeout Gate | versionado |
| [.agents/skills/speckit-tasks/SKILL.md](../../.agents/skills/speckit-tasks/SKILL.md) | (sin encabezado H1) | versionado |
| [.agents/skills/speckit-taskstoissues/SKILL.md](../../.agents/skills/speckit-taskstoissues/SKILL.md) | (sin encabezado H1) | versionado |

### Índices de artefactos y diagnósticos (2)

| Archivo | Encabezado declarado | Git |
|---|---|---|
| [artifacts/README.md](../../artifacts/README.md) | Directorio de Artefactos de Sesión | versionado |
| [diagnostics/README.md](../../diagnostics/README.md) | Directorio de Diagnósticos y Métricas en Runtime | versionado |

## Observaciones preliminares para la próxima iteración

Estas observaciones no reemplazan una auditoría de contenido ni autorizan traslados.

1. **Vigencia de índices:** docs/README.md todavía presenta V5.2 y specs001–086; docs/speckit/README.md declara V5.1.0,73 specs y1204 tests. Contrastar con el estado actual antes de normalizar.
2. **Autoridad:** separar instrucciones, planificación, procedimientos y reportes fechados. La coincidencia de temas no implica duplicado eliminable.
3. **Preservación:** DEVELOPMENT_LOG.md es estrictamente aditivo. No borrar ni truncar bitácora, archivo histórico o evidencias.
4. **Automatización:** .agents/skills/ y .specify/ son contratos de herramientas. Revisar sus consumidores antes de proponer renombres o movimientos.
5. **Material local:** artifacts/README.md y diagnostics/README.md existen aunque no aparezcan en el catálogo Git habitual.
6. **Mezcla de tipos:** audit/ contiene tanto reportes fechados como BACKUP_RUNBOOK.md, un procedimiento. Revisar su ubicación futura sin confundirlo con evidencia histórica.

### Referencias locales no resueltas en índices examinados

Se revisaron enlaces relativos literales de README.md, docs/README.md y docs/speckit/README.md. Se omitieron specs/, URLs y plantillas. No es una validación global de enlaces.

| Origen | Destino escrito que no existe |
|---|---|
| [docs/speckit/README.md](../speckit/README.md) | `rfcs/README.md` |
| [docs/speckit/README.md](../speckit/README.md) | `archive/README.md` |
| [docs/speckit/README.md](../speckit/README.md) | `archive/HASHCORE_TOOLKIT_STRATEGY.md` |
| [docs/speckit/README.md](../speckit/README.md) | `archive/INTERFACE_STRATEGY.md` |
| [docs/speckit/README.md](../speckit/README.md) | `archive/V3_EXPANSION_PLAN.md` |

### Señales de codificación para revisar

Heurística con posibles falsos positivos o citas históricas; no se transformó codificación.

- [docs/speckit/ROADMAP.md](../speckit/ROADMAP.md) — UTF-8.

### Duplicados exactos

Sin duplicados binarios entre documentos principales con hash calculado. No descarta contenido parcialmente duplicado.

## Anexo: evidencia generada y vistas de diagnóstico

Material local potencialmente regenerable o sensible; se listan solo metadatos. Revisar productores y referencias antes de decidir conservación.

| Archivo | Bytes | Git |
|---|---:|---|
| [diagnostics/backup-20261115/full.txt](../../diagnostics/backup-20261115/full.txt) | 1922 | ignorado |
| [diagnostics/backup-20261115/rendered-digest.txt](../../diagnostics/backup-20261115/rendered-digest.txt) | 511 | ignorado |
| [diagnostics/backup-20261115/targeted-final.txt](../../diagnostics/backup-20261115/targeted-final.txt) | 102 | ignorado |
| [diagnostics/backup-20261115/targeted.txt](../../diagnostics/backup-20261115/targeted.txt) | 102 | ignorado |
| [diagnostics/backup-20261115/task-register.txt](../../diagnostics/backup-20261115/task-register.txt) | 410 | ignorado |
| [diagnostics/dashboard-docker/index.html](../../diagnostics/dashboard-docker/index.html) | 10493 | ignorado |
| [diagnostics/dashboard-qa/index.html](../../diagnostics/dashboard-qa/index.html) | 10627 | ignorado |
| [diagnostics/dashboard-qa/stability-index.html](../../diagnostics/dashboard-qa/stability-index.html) | 12484 | ignorado |
| [diagnostics/dashboard-quality-docker/index.html](../../diagnostics/dashboard-quality-docker/index.html) | 13768 | ignorado |
| [diagnostics/dashboard-quality/index.html](../../diagnostics/dashboard-quality/index.html) | 13937 | ignorado |
| [diagnostics/dashboard-stability-docker/index.html](../../diagnostics/dashboard-stability-docker/index.html) | 12335 | ignorado |
| [diagnostics/docker-vnish/index.html](../../diagnostics/docker-vnish/index.html) | 17600 | ignorado |
| [diagnostics/heat-20261112/deployment-result.txt](../../diagnostics/heat-20261112/deployment-result.txt) | 140 | ignorado |
| [diagnostics/heat-20261112/prompt-before.txt](../../diagnostics/heat-20261112/prompt-before.txt) | 1831 | ignorado |
| [diagnostics/heat-20261112/pytest-final.txt](../../diagnostics/heat-20261112/pytest-final.txt) | 1804 | ignorado |
| [diagnostics/heat-20261112/pytest-isolated.txt](../../diagnostics/heat-20261112/pytest-isolated.txt) | 1804 | ignorado |
| [diagnostics/heat-20261112/pytest.txt](../../diagnostics/heat-20261112/pytest.txt) | 25955 | ignorado |
| [diagnostics/index.html](../../diagnostics/index.html) | 43778 | ignorado |
| [diagnostics/interface-baseline/index.html](../../diagnostics/interface-baseline/index.html) | 50741 | ignorado |
| [diagnostics/latest/summary.md](../../diagnostics/latest/summary.md) | 1318 | ignorado |
| [diagnostics/messaging-20261115/full.txt](../../diagnostics/messaging-20261115/full.txt) | 1903 | ignorado |
| [diagnostics/messaging-20261115/new-final.txt](../../diagnostics/messaging-20261115/new-final.txt) | 101 | ignorado |
| [diagnostics/messaging-20261115/release-tests.txt](../../diagnostics/messaging-20261115/release-tests.txt) | 1903 | ignorado |
| [diagnostics/messaging-20261115/rendered-digest.txt](../../diagnostics/messaging-20261115/rendered-digest.txt) | 510 | ignorado |
| [diagnostics/messaging-20261115/rendered-status.txt](../../diagnostics/messaging-20261115/rendered-status.txt) | 712 | ignorado |
| [diagnostics/messaging-20261115/targeted-final.txt](../../diagnostics/messaging-20261115/targeted-final.txt) | 2845 | ignorado |
| [diagnostics/messaging-20261115/targeted.txt](../../diagnostics/messaging-20261115/targeted.txt) | 1974 | ignorado |
| [diagnostics/operations_dashboard.html](../../diagnostics/operations_dashboard.html) | 43778 | ignorado |
| [diagnostics/production-20261114/pytest-final.txt](../../diagnostics/production-20261114/pytest-final.txt) | 5107 | ignorado |
| [diagnostics/production-20261114/pytest-release.txt](../../diagnostics/production-20261114/pytest-release.txt) | 1822 | ignorado |
| [diagnostics/production-20261114/pytest-thermal-final.txt](../../diagnostics/production-20261114/pytest-thermal-final.txt) | 1903 | ignorado |
| [diagnostics/production-20261114/pytest.txt](../../diagnostics/production-20261114/pytest.txt) | 1822 | ignorado |
| [diagnostics/production-20261114/restart-result.txt](../../diagnostics/production-20261114/restart-result.txt) | 140 | ignorado |
| [diagnostics/reconcile-20261114/miner-ui-index.html](../../diagnostics/reconcile-20261114/miner-ui-index.html) | 1275 | ignorado |
| [diagnostics/reconcile-20261114/pytest-final.txt](../../diagnostics/reconcile-20261114/pytest-final.txt) | 1804 | ignorado |
| [diagnostics/reconcile-20261114/pytest.txt](../../diagnostics/reconcile-20261114/pytest.txt) | 1804 | ignorado |
| [diagnostics/restarts-20261116/S19JPRO-23-autotune.txt](../../diagnostics/restarts-20261116/S19JPRO-23-autotune.txt) | 505856 | ignorado |
| [diagnostics/restarts-20261116/S19JPRO-23-miner.txt](../../diagnostics/restarts-20261116/S19JPRO-23-miner.txt) | 312066 | ignorado |
| [diagnostics/restarts-20261116/S19JPRO-23-status.txt](../../diagnostics/restarts-20261116/S19JPRO-23-status.txt) | 124588 | ignorado |
| [diagnostics/restarts-20261116/S19JPRO-24-autotune.txt](../../diagnostics/restarts-20261116/S19JPRO-24-autotune.txt) | 146402 | ignorado |
| [diagnostics/restarts-20261116/S19JPRO-24-miner.txt](../../diagnostics/restarts-20261116/S19JPRO-24-miner.txt) | 562531 | ignorado |
| [diagnostics/restarts-20261116/S19JPRO-24-status.txt](../../diagnostics/restarts-20261116/S19JPRO-24-status.txt) | 90118 | ignorado |
| [diagnostics/restarts-20261116/S19JPRO-26-autotune.txt](../../diagnostics/restarts-20261116/S19JPRO-26-autotune.txt) | 500631 | ignorado |
| [diagnostics/restarts-20261116/S19JPRO-26-miner.txt](../../diagnostics/restarts-20261116/S19JPRO-26-miner.txt) | 645112 | ignorado |
| [diagnostics/restarts-20261116/S19JPRO-26-status.txt](../../diagnostics/restarts-20261116/S19JPRO-26-status.txt) | 382899 | ignorado |
| [diagnostics/stability-20261116/commit094.txt](../../diagnostics/stability-20261116/commit094.txt) | 69 | ignorado |
| [diagnostics/stability-20261116/first-reload-exit.txt](../../diagnostics/stability-20261116/first-reload-exit.txt) | 4 | ignorado |
| [diagnostics/stability-20261116/first-reload.txt](../../diagnostics/stability-20261116/first-reload.txt) | 280 | ignorado |
| [diagnostics/stability-20261116/M24-status-after.txt](../../diagnostics/stability-20261116/M24-status-after.txt) | 91337 | ignorado |
| [diagnostics/stability-20261116/M26-status-1100.txt](../../diagnostics/stability-20261116/M26-status-1100.txt) | 384315 | ignorado |
| [diagnostics/stability-20261116/pytest096-final.txt](../../diagnostics/stability-20261116/pytest096-final.txt) | 2004 | ignorado |
| [diagnostics/stability-20261116/reload-exit.txt](../../diagnostics/stability-20261116/reload-exit.txt) | 4 | ignorado |
| [diagnostics/stability-20261116/reload.txt](../../diagnostics/stability-20261116/reload.txt) | 280 | ignorado |
| [diagnostics/summary.md](../../diagnostics/summary.md) | 1054 | ignorado |
| [diagnostics/vnish-dashboard-smoke.html](../../diagnostics/vnish-dashboard-smoke.html) | 17652 | ignorado |
| [diagnostics/vnish-ops-017/index.html](../../diagnostics/vnish-ops-017/index.html) | 17773 | ignorado |

## Anexo: manifests de dependencias

- [requirements-observability.txt](../../requirements-observability.txt) — configuración, no documentación narrativa.
- [requirements.txt](../../requirements.txt) — configuración, no documentación narrativa.

## Anexo: soporte no narrativo de docs/

Incluye JSON, scripts y una base histórica; solo metadatos. No se ejecutaron scripts ni se abrieron bases.

| Archivo | Tipo | Bytes |
|---|---|---:|
| [docs/archive/historical_artifacts/activate-spec021.ps1](../archive/historical_artifacts/activate-spec021.ps1) | .ps1 | 824 |
| [docs/archive/historical_artifacts/spec021-d0-current.json](../archive/historical_artifacts/spec021-d0-current.json) | .json | 2852 |
| [docs/archive/historical_artifacts/spec021-d0-latest.json](../archive/historical_artifacts/spec021-d0-latest.json) | .json | 2804 |
| [docs/archive/historical_artifacts/spec021-d0-observation.json](../archive/historical_artifacts/spec021-d0-observation.json) | .json | 2804 |
| [docs/archive/historical_artifacts/spec021-d0-pre-d1.json](../archive/historical_artifacts/spec021-d0-pre-d1.json) | .json | 2801 |
| [docs/archive/historical_artifacts/spec021-d1-early-check.json](../archive/historical_artifacts/spec021-d1-early-check.json) | .json | 2844 |
| [docs/archive/historical_artifacts/spec021-d1-observation.json](../archive/historical_artifacts/spec021-d1-observation.json) | .json | 2814 |
| [docs/archive/historical_artifacts/spec021-d3-observation.json](../archive/historical_artifacts/spec021-d3-observation.json) | .json | 2944 |
| [docs/archive/historical_artifacts/spec021-failure-envelope.json](../archive/historical_artifacts/spec021-failure-envelope.json) | .json | 248 |
| [docs/archive/historical_artifacts/spec021-observation-tasks.json](../archive/historical_artifacts/spec021-observation-tasks.json) | .json | 1726 |
| [docs/archive/historical_artifacts/spec022-sequential-baseline.json](../archive/historical_artifacts/spec022-sequential-baseline.json) | .json | 2839 |
| [docs/archive/historical_artifacts/spec024-electrical-capability-report.json](../archive/historical_artifacts/spec024-electrical-capability-report.json) | .json | 1573 |
| [docs/archive/historical_artifacts/spec026-hashcore-inventory.json](../archive/historical_artifacts/spec026-hashcore-inventory.json) | .json | 1526 |
| [docs/archive/historical_artifacts/test-spec021-scm-recovery-v2.ps1](../archive/historical_artifacts/test-spec021-scm-recovery-v2.ps1) | .ps1 | 2588 |
| [docs/archive/historical_artifacts/test-spec021-scm-recovery.ps1](../archive/historical_artifacts/test-spec021-scm-recovery.ps1) | .ps1 | 2832 |
| [docs/archive/historical_artifacts/v2_release_candidate_manifest.json](../archive/historical_artifacts/v2_release_candidate_manifest.json) | .json | 9921 |
| [docs/archive/historical_artifacts/verify-spec021-observation-tasks.ps1](../archive/historical_artifacts/verify-spec021-observation-tasks.ps1) | .ps1 | 1208 |
| [docs/archive/historical_diagnostics/baseline/baseline.json](../archive/historical_diagnostics/baseline/baseline.json) | .json | 2388 |
| [docs/archive/historical_diagnostics/dry-run/snapshot.json](../archive/historical_diagnostics/dry-run/snapshot.json) | .json | 1718 |
| [docs/archive/historical_diagnostics/latest/snapshot.json](../archive/historical_diagnostics/latest/snapshot.json) | .json | 20112 |
| [docs/archive/historical_diagnostics/live-20260720-213925/snapshot.json](../archive/historical_diagnostics/live-20260720-213925/snapshot.json) | .json | 4714 |
| [docs/archive/historical_diagnostics/live-20260720-213940/snapshot.json](../archive/historical_diagnostics/live-20260720-213940/snapshot.json) | .json | 20142 |
| [docs/archive/historical_diagnostics/live-quality/miner_alerts_live.db](../archive/historical_diagnostics/live-quality/miner_alerts_live.db) | .db | 61440 |
| [docs/archive/historical_diagnostics/live-raw-20260720-214134/snapshot.json](../archive/historical_diagnostics/live-raw-20260720-214134/snapshot.json) | .json | 47831 |
| [docs/archive/historical_diagnostics/live-raw-20260720-215415/snapshot.json](../archive/historical_diagnostics/live-raw-20260720-215415/snapshot.json) | .json | 47818 |
| [docs/archive/historical_diagnostics/spec020-runtime-smoke/snapshot.json](../archive/historical_diagnostics/spec020-runtime-smoke/snapshot.json) | .json | 20081 |

## Uso en la próxima iteración

1. Validar qué describe el presente y qué preserva un corte histórico.
2. Definir índice canónico y taxonomía: operación, arquitectura, desarrollo, gobierno e histórico.
3. Resolver autoridad, referencias y codificación antes de fusionar contenido.
4. Preparar mapa de rutas actuales a propuestas, con referencias desde código y automatizaciones.
5. Ejecutar la reorganización en una iteración documental separada, preservando bitácora, evidencias y datos privados.
