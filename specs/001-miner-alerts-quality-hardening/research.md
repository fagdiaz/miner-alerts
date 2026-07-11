# Research: Miner Alerts Quality Hardening

## Decision 1: Keep Speckit Local And Lightweight

Decision: Copy the proven OneITB23 `.specify` and `.agents/skills` layout, then adapt project memory and docs for Miner Alerts.

Rationale: The user already has this workflow locally and wants the same operating model.

Alternatives considered: installing a different external package or redesigning the workflow. Rejected because this project needs a known local process, not a tooling migration.

## Decision 2: Focus Specs On Operational Safety

Decision: The first active spec targets quick wins and audits around alerts, reboots, logs, and Telegram operations.

Rationale: These areas directly affect production behavior and operator trust.

## Decision 3: Evidence Before Runtime Claims

Decision: Every production-affecting change must record commands and observed logs.

Rationale: `py_compile` validates syntax only; it does not prove Telegram delivery, Hashcore behavior, or auto-reboot safety.
