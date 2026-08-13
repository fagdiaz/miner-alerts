<!--
SYNC IMPACT REPORT
- Initial Miner Alerts constitution for Speckit.
- Scope: Windows Python monitor for ASIC miners, Telegram bot, Hashcore Toolkit CLI.
- Dependent artifacts:
  * AGENTS.md
  * docs/speckit/README.md
  * docs/speckit/ROADMAP.md
  * docs/speckit/SPEC_PROGRAM.md
  * docs/speckit/DELIVERY_PLAN.md
  * docs/speckit/RUNBOOK.md
  * specs/001-miner-alerts-quality-hardening/*
  * specs/021-029/* (planning artifacts only)
- Amendment 1.1.0: require explicit implementation and stabilization windows
  without allowing schedule pressure to bypass runtime evidence.
- Amendment 1.2.0: require one dependency/risk program for future specs and keep
  planned, blocked, no-build, implemented and runtime-verified states distinct.
-->

# Miner Alerts Constitution

## Core Principles

### I. Production Safety First

The monitor MUST prefer safe observation over automated action when evidence is incomplete. Changes that affect state transitions, alert policies, manual reboot, auto-reboot, degraded mode, startup guard, cooldowns, or Hashcore execution require explicit validation evidence. False alerts and unnecessary reboots are production incidents.

### II. Single Source Of Truth For Runtime Configuration

Runtime configuration lives in `app/config.json` and MUST NOT be committed. Documentation and examples use `app/config.example.json` only. Secrets, Telegram tokens, chat IDs from production, miner credentials, and local state MUST NOT enter specs, docs, or commits.

### III. Telegram Commands Are Operational Controls

Telegram handlers MUST be treated as production control paths. User commands must reply deterministically, avoid silent drops, and preserve confirmation flows for dangerous actions. Click-safe command aliases are allowed only when they map to existing safe behavior and do not bypass confirmation.

### IV. Auto-Reboot Requires Evidence And Gates

Auto-reboot changes MUST preserve QA guardrails, startup guard, sustained LOW requirements, cooldowns, reboot windows, and persisted-state sanitization. `state.json` MUST NOT become a direct trigger for immediate auto-reboot on process start.

### V. Windows Compatibility Is Required

The project targets Windows with PowerShell, Python virtualenv, Telegram polling, ASIC API 4028, and Hashcore Toolkit CLI. Validation instructions MUST use Windows-compatible commands unless explicitly marked otherwise.

### VI. Evidence-Based Completion

`py_compile` is required but insufficient for production-affecting changes. Each completed spec MUST record the exact commands run, Telegram command checks when relevant, observed logs, and any blocked runtime validation.

## Development Workflow And Quality Gates

- Read `.specify/feature.json`, the active spec directory, this constitution,
  `docs/speckit/SPEC_PROGRAM.md`, `docs/speckit/ROADMAP.md`, and
  `docs/speckit/DELIVERY_PLAN.md` before implementation.
- Future specs MUST preserve their declared dependencies, risk class and action
  boundary. A planned spec is not active or implemented merely because all of
  its design artifacts exist.
- Reserve a post-rollout observation/fix window for every production-affecting spec. Estimated dates MUST move rather than compress safety gates.
- Do not touch `app/config.json` or `app/state.json` unless the task explicitly requires local runtime alignment.
- Keep changes minimal and scoped. Prefer documentation, logs, and guardrails over broad rewrites.
- For monitor code changes, run `& ".\\.venv\\Scripts\\python.exe" -m py_compile app\\miner_monitor.py`.
- For Telegram changes, validate command reply, queue behavior, and relevant logs under `DBG_TELEGRAM=1` when feasible.
- For auto-reboot changes, validate QA blocked behavior before production behavior.
- Commits are manual and feature-scoped.

## Governance

- This constitution supersedes conflicting Speckit guidance for this repository.
- Amendments MUST update affected docs under `docs/speckit/` and active specs.
- Reviews MUST verify production safety, config hygiene, Telegram control safety, Windows compatibility, and validation evidence.

**Version**: 1.2.0 | **Ratified**: 2026-07-11 | **Last Amended**: 2026-08-13
