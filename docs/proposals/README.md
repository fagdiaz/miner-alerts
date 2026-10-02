# Propuestas de Mejora del Sistema (System Improvement Proposals)

Todas las propuestas históricas (PROP-001 a PROP-021) han sido implementadas, certificadas e incorporadas al código en producción. Han sido archivadas en [`docs/archive/proposals/`](../archive/proposals/).

Actualmente **NO hay propuestas de mejora pendientes abiertas**. El sistema opera bajo el Horizonte V5.2 de Gobernanza Integrada en modo de observación continua y estabilización de planta.

---

## Tabla Resumen de Propuestas Históricas y Resolución

| Propuesta | Título | Estado | Spec de Resolución |
| :--- | :--- | :---: | :--- |
| **PROP-001** | Cold-Boot Grace Period | Completada | [Spec 066](file:///F:/02-ASIC%20-%20mineros/miner-alerts/specs/066-cold-boot-grace) |
| **PROP-002** | SQLite WAL Integrity | Completada | [Spec 061](file:///F:/02-ASIC%20-%20mineros/miner-alerts/specs/061-sqlite-wal-integrity) |
| **PROP-003** | HW Error Tripwire | Completada | [Spec 062](file:///F:/02-ASIC%20-%20mineros/miner-alerts/specs/062-hw-error-tripwire) |
| **PROP-004** | Ambient Thermal PID | Completada | [Spec 063](file:///F:/02-ASIC%20-%20mineros/miner-alerts/specs/063-ambient-thermal-pid) |
| **PROP-005** | Gateway Heartbeat | Completada | [Spec 067](file:///F:/02-ASIC%20-%20mineros/miner-alerts/specs/067-gateway-heartbeat) |
| **PROP-006** | Multi-Miner Charts | Completada | [Spec 064](file:///F:/02-ASIC%20-%20mineros/miner-alerts/specs/064-multi-miner-charts) |
| **PROP-007** | IPC Watchdog Pipe | Completada | [Spec 068](file:///F:/02-ASIC%20-%20mineros/miner-alerts/specs/068-ipc-watchdog-pipe) |
| **PROP-008** | Deep Chain Telemetry | Completada | [Spec 069](file:///F:/02-ASIC%20-%20mineros/miner-alerts/specs/069-deep-chain-telemetry) |
| **PROP-009** | Paired Elevator Contingency | Completada | [Spec 074](file:///F:/02-ASIC%20-%20mineros/miner-alerts/specs/074-paired-elevator-contingency) |
| **PROP-010** | Soft-Landing APW12 Protection | Completada | [Spec 075](file:///F:/02-ASIC%20-%20mineros/miner-alerts/specs/075-soft-landing-recovery) |
| **PROP-011** | Autonomous Firmware Reflash | Completada | [Spec 076](file:///F:/02-ASIC%20-%20mineros/miner-alerts/specs/076-autonomous-firmware-reflash) |
| **PROP-012** | Staggered Elevator Governance | Completada | [Spec 077](file:///F:/02-ASIC%20-%20mineros/miner-alerts/specs/077-staggered-elevator-governance) |
| **PROP-013** | Electrical Noise & Solar Envelope | Completada | [Spec 078](file:///F:/02-ASIC%20-%20mineros/miner-alerts/specs/078-electrical-noise-solar-envelope) |
| **PROP-014/015** | Facility Agent (FGA) | Completada | [Spec 079](file:///F:/02-ASIC%20-%20mineros/miner-alerts/specs/079-facility-governance-agent) / [Spec 083](file:///F:/02-ASIC%20-%20mineros/miner-alerts/specs/083-fga-actuator-loop) |
| **PROP-016** | Incident Autopsy & Conversational QA | Completada | [Spec 080](file:///F:/02-ASIC%20-%20mineros/miner-alerts/specs/080-incident-autopsy-engine) / [Spec 086](file:///F:/02-ASIC%20-%20mineros/miner-alerts/specs/086-incident-autopsy-engine) |
| **PROP-017** | Restart Required Harmonization | Completada | [Spec 081](file:///F:/02-ASIC%20-%20mineros/miner-alerts/specs/081-restart-required-harmonization) |
| **PROP-018** | MinerGovernanceContext Contract | Completada | [Spec 082](file:///F:/02-ASIC%20-%20mineros/miner-alerts/specs/082-miner-governance-context) |
| **PROP-019** | FGA Actuator Loop & Elevator Gate | Completada | [Spec 083](file:///F:/02-ASIC%20-%20mineros/miner-alerts/specs/083-fga-actuator-loop) |
| **PROP-020** | Governance Dashboard & Deadlock Watchdog | Completada | [Spec 084](file:///F:/02-ASIC%20-%20mineros/miner-alerts/specs/084-governance-dashboard) |
| **PROP-021** | Governance Orchestrator Decoupling | Completada | [Spec 085](file:///F:/02-ASIC%20-%20mineros/miner-alerts/specs/085-governance-orchestrator) |

---

## Procedimiento para Nuevas Propuestas

Cuando surja una nueva necesidad arquitectónica que no esté cubierta por el marco operativo actual:

1. Se redactará un nuevo borrador siguiendo la nomenclatura `PROP-022-<nombre-descriptivo>.md`.
2. Toda nueva propuesta debe ser evaluada frente a las directivas consolidadas en [`docs/audit/DIRECTIVES_HARMONIZATION_AUDIT.md`](../audit/DIRECTIVES_HARMONIZATION_AUDIT.md).
3. Tras la aprobación del operador, se generará la especificación correspondiente en `specs/` para su planificación formal en [`docs/speckit/ROADMAP.md`](../speckit/ROADMAP.md).
