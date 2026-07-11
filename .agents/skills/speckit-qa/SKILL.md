---
name: "speckit-qa"
description: "Risk-based pre-implementation quality gate for Miner Alerts specs. Use after plan/tasks and before speckit-implement to catch unsafe reboot behavior, Telegram command gaps, config/secret risks, missing validation, and broken Python syntax without performing an exhaustive audit for low-risk changes."
---

# Speckit QA

Review and improve the active feature before implementation. Be strict on security and contracts, proportional on cost, and surgical on scope.

## Boundary

- Inspect the plan, tasks, and only the source contracts they affect.
- Patch `tasks.md` and, only when contradictory, `plan.md` or `spec.md`.
- Do not implement production code.
- Do not promise zero defects. Return evidence and residual risk.
- Do not refactor unrelated debt.

## 1. Load Minimal Context

Read:

1. `.specify/feature.json`.
2. Active `spec.md`, `plan.md`, `tasks.md`, and requirement checklists.
3. `.specify/memory/constitution.md`.
4. `docs/speckit/ROADMAP.md` P0 and the matching module.

Use `rg` to inspect only paths, types, operations, and interfaces named by the feature. Do not read the full development log, generated migration designers, `bin`, `obj`, `dist`, or `node_modules`.

## 2. Classify Risk

Use the highest applicable level:

- **LOW**: documentation, release notes, examples, no runtime behavior change.
- **MEDIUM**: Telegram UX text, command parsing, logging, config examples, non-actionable diagnostics.
- **HIGH**: auto-reboot, manual reboot/restart, Hashcore execution, QA guardrails, startup guard, cooldown/window policy, Telegram delivery, secrets, startup/configuration.

Escalate when blast radius is unclear.

## 3. Run Deterministic Preflight

Run from repository root:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
& ".agents/skills/speckit-qa/scripts/preflight.ps1"
```

Add `-RunBuilds` for MEDIUM/HIGH changes affecting Python source.

Reuse a build result from the current turn only if no affected source changed afterward. Do not run duplicate builds.

## 4. Apply Relevant Gates

Always verify task IDs, exact paths, dependency order, command/config naming, reuse, configuration, negative paths, runtime evidence, and documentation closeout.

For MEDIUM or HIGH risk, read [risk-gates.md](references/risk-gates.md) and apply only the relevant headings. Do not load it for LOW risk.

## 5. Optimize Tasks

Patch only missing or unsafe steps. Prefer adding concise tasks over rewriting the file.

Required closeout for affected features:

- Targeted tests before or with implementation.
- Python `py_compile` when source changes.
- Telegram command checks when Telegram behavior changes.
- QA blocked-action checks when reboot/restart behavior changes.
- Exact evidence recording, including blockers.
- Roadmap update when backlog status changes.
- Evidence update with exact commands and blocked checks.

Do not paste the complete optimized `tasks.md` in the response; report changed task IDs.

## 6. Decision Rules

- **PASS**: no actionable gap; implementation may start.
- **FIXED**: tasks/artifacts were patched and all critical gates now pass.
- **BLOCKED**: stop before implementation when a requirement checklist is incomplete, baseline build is broken in affected scope, a HIGH-risk contract is ambiguous, or a critical security/data issue lacks a safe task.

Warnings outside the feature do not block unless they invalidate the baseline or increase its risk.

## Output (Concise)

```text
QA: PASS | FIXED | BLOCKED
Risk: LOW | MEDIUM | HIGH - reason
Preflight: checklist, diff, builds/EF actually run
Findings: only actionable P0/P1/P2 items with file references
Tasks changed: IDs or "none"
Residual risk: one short line
Proceed: yes/no
```

Keep the response under 25 lines unless blocked findings require detail.

## Token Discipline

- Prefer one `rg` query over broad file reads.
- Read relevant line windows, not whole large files.
- Use preflight JSON instead of narrating command output.
- Stop after one authoritative signal proves a gate.
- Skip backend, frontend, EF, browser, or security gates when the risk classification makes them irrelevant.
