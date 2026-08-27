<!-- SPECKIT START -->
# Miner Alerts Agent Instructions

## Source Of Truth

1. Read `.specify/feature.json` to identify the active feature directory.
2. Read the active feature's `spec.md`, `plan.md`, `tasks.md`, and `evidence.md` when present.
3. Read `.specify/memory/constitution.md`.
4. Use `docs/speckit/ROADMAP.md` as the working backlog for quick wins, bug fixes, and audit priorities.
5. Use `docs/speckit/DELIVERY_PLAN.md` for estimated implementation, observation, and bug-fix windows; runtime evidence may move dates.
6. Use `docs/speckit/SPEC_PROGRAM.md` for the definitive future-spec sequence, dependencies, risk classes, and shared completion gates.

Active implementation plan:
`specs/022-adaptive-acquisition/plan.md` (Implementation complete; observation active)

Active production observation gate:
`specs/022-adaptive-acquisition/plan.md` (D+1/D+3 active since 2026-08-27 16:11:40, PID 38816)

Do not infer runtime safety from checked tasks alone. Runtime evidence and logs take precedence.

## Current Technical Baseline

- Runtime: Windows, PowerShell, Python virtualenv.
- Main script: `app/miner_monitor.py`.
- Config example: `app/config.example.json`.
- Real config/state: `app/config.json`, `app/state.json` are local runtime files and must not be committed.
- Integrations: Telegram Bot API polling, ASIC API 4028, Hashcore Toolkit CLI.

## Stabilization Priority

Prioritize quick wins that reduce production risk:

1. False alert reduction and clearer alert evidence.
2. Auto-reboot safety, startup guard behavior, cooldown/window correctness.
3. Telegram command reliability and no-silence delivery diagnostics.
4. Log clarity for production diagnosis without debug spam.
5. Windows validation and release hygiene.

Avoid unrelated feature expansion while safety and observability issues are open.

## Required Validation

- Python syntax: `& ".\\.venv\\Scripts\\python.exe" -m py_compile app\\miner_monitor.py`.
- Diagnostics syntax: `& ".\\.venv\\Scripts\\python.exe" -m py_compile tools\\miner_diagnostics.py` when the diagnostics tool changes.
- Telegram command changes: test with `DBG_TELEGRAM=1` and `DBG_TELEGRAM_COMMANDS_ONLY=1` when possible.
- Auto-reboot changes: validate QA mode first; real actions require explicit approval and controlled production conditions.
- Config changes: update `app/config.example.json` and docs only, unless local `app/config.json` alignment is explicitly requested.

## Model Workload & Handoff Protocol

1. **Gemini 3.7 Flash High Maximization (Primary Engine)**: Prioritize Gemini 3.7 Flash High for all tasks within its reasoning scope: code reading, architecture analysis, pure domain logic, data models, schemas, comprehensive test suites (unit, integration, deterministic proofs, performance/stress benchmarks), documentation, SpecKit tracking, and bounded implementations with established contracts. Execute in iterative, bounded turns to prevent overload.
2. **On-Demand Scaled Delegation to Claude**: Escalate to higher-reasoning models ONLY when the task demands it:
   - **Claude Sonnet 4.6 (Thinking)**: Escalate ONLY for live production multi-threading (`miner_monitor.py` concurrency, socket timeouts, Windows mutexes, queue worker coordination) or core finite state machines (`miner_states`, streak calculations, auto-reboot policies) where race conditions risk production outages.
   - **Claude Opus 4.6 (Thinking)**: Escalate STRICTLY as the terminal escalation option for persistent circular test failures, race conditions surviving Sonnet, or major cross-subsystem architectural redesigns.
3. **Handoff Prompt Protocol (`prompt.txt`)**: Every model at the end of its session MUST leave an updated, ready-to-run prompt in `prompt.txt` providing the simplest and most optimal context (either via explicit explanation or exact file/line reading directives).
4. **Console Model Notification**: In console/chat output, the agent MUST explicitly inform the user which model to select next (recommending `Gemini 3.7 Flash High`, `Claude Sonnet 4.6 (Thinking)`, or `Claude Opus 4.6 (Thinking)`).

## Spec Definition Of Done

Every implemented spec must:

1. Complete and check the relevant tasks in `tasks.md`.
2. Record commands and runtime checks in `evidence.md`.
3. Add a newest-first entry to `docs/audit/DEVELOPMENT_LOG.md`.
4. Update `docs/speckit/ROADMAP.md` when backlog state changes.
5. Leave unverified behavior explicitly marked as unverified or blocked.
6. Keep commits manual and feature-scoped.

<!-- SPECKIT END -->
