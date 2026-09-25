---
name: "speckit-stabilize"
description: "Exhaustive QA audit gate, documentary normalization, transient depuration, and certified commit/push/restart release closeout for Miner Alerts specs. Prioritizes pre-QA checks since last stabilization, blocks commit/push upon any defect by generating a detailed STABILIZATION_REPORT, and closes out the feature cleanly when 100% verified."
compatibility: "Requires spec-kit project structure with .specify/ directory and PowerShell runtime."
metadata:
  author: "github-spec-kit"
  source: "skills/speckit-stabilize/SKILL.md"
---

# Speckit Stabilize & Release Closeout Gate

Perform an exhaustive, multi-tier QA audit, documentary normalization, safe transient depuration, and certified commit/push closeout.

```text
                                  ┌────────────────────────┐
                                  │   speckit-stabilize    │
                                  └───────────┬────────────┘
                                              │
                                  ┌───────────▼────────────┐
                                  │ Phase 1: Preflight QA  │◄─── [speckit-qa integration]
                                  │ & Diff from Last Stable│
                                  └───────────┬────────────┘
                                              │
                                   Is QA 100% Clean & Passing?
                                              │
                      ┌───────────────────────┴───────────────────────┐
                      │                                               │
               [NO: Any Blocker]                               [YES: 100% PASS]
                      │                                               │
        ┌─────────────▼──────────────┐                 ┌──────────────▼─────────────┐
        │ Block Commit & Push        │                 │ Phase 3: Doc Normalization │
        │ Generate Audit Report:     │                 │ & Safe Transient Cleanup   │
        │ STABILIZATION_REPORT_*.md  │                 └──────────────┬─────────────┘
        │ Detail Pending Items       │                                │
        └─────────────┬──────────────┘                 ┌──────────────▼─────────────┐
                      │                                │ Phase 4: Service & Hardware│
                      ▼                                │ NSSM Restart & Fleet Check │
               Iterate Fixes                           └──────────────┬─────────────┘
                      │                                               │
                      ▼                                ┌──────────────▼─────────────┐
            Re-run speckit-stabilize                   │ Phase 5: Safe Git Commit   │
                                                       │ & Feature-Scoped Push      │
                                                       └──────────────┬─────────────┘
                                                                      │
                                                       ┌──────────────▼─────────────┐
                                                       │ Phase 6: Sync prompt.txt   │
                                                       │ & Model Handoff Protocol   │
                                                       └────────────────────────────┘
```

---

## Boundary & Scope

- **Exhaustive QA Scope**: Evaluates all code, tests, firmware contracts, and documentation changed since the last stabilization entry in `docs/audit/DEVELOPMENT_LOG.md`.
- **Absolute Immutability**: `docs/audit/DEVELOPMENT_LOG.md` is strictly **IMMUTABLE** against deletion or clearing. It must only receive newest-first additions.
- **Runtime Secret Protection**: `app/config.json` and `app/state.json` must NEVER be staged or committed.
- **Fail-Safe Gate**: If any test fails, syntax is broken, secret is exposed, or runtime safety rule is violated, commit/push is **STRICTLY BLOCKED**.

---

## Phase 1: Ingestion & Interlinked QA Preflight

1. **Resolve Active Feature Context**:
   - Read `.specify/feature.json` to identify the active feature directory.
   - Read the active feature's `spec.md`, `plan.md`, `tasks.md`, and `evidence.md`.
   - Read `.specify/memory/constitution.md` and `AGENTS.md`.
   - Inspect the newest entry in `docs/audit/DEVELOPMENT_LOG.md` to identify the last stabilization baseline.

2. **Run Automated Preflight Script**:
   Execute from the repository root:
   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
   & ".agents/skills/speckit-stabilize/scripts/preflight_stabilize.ps1" -RunTests -CheckFleet
   ```

3. **Perform Exhaustive Subsystem Audits**:
   Cross-reference all working tree and recent commit changes against [stabilization-checklist.md](references/stabilization-checklist.md):
   - **Actuators & Safety**: Ensure no ungated `safe_restart_mining` or `reboot` calls exist. Ensure all hot preset modulations check `should_allow_intervention(ACTION_PRESET_BALANCER)` and `presets_enabled`.
   - **VNish Firmware Harmony**: Verify `/api/v1/status` across all miners reports `restart_required: false` to eliminate unapplied "Apply" button prompts on the web UI.
   - **Telegram Routing & Anti-Spam**: Confirm histeresis (`fails_before_alert = 3`), secondary sensor alert suppression, multi-slot digests (`10:00,22:00`), and click-safe confirmation menus.
   - **Config Synchronization**: Confirm any new key in `app/config.json` is mirrored in `app/config.example.json` with descriptive documentation comments.

---

## Phase 2: The Stabilization Decision Gate

Evaluate preflight results and findings:

### IF GATES FAIL OR ACTIONABLE DEFECTS ARE FOUND (Status: BLOCKED)

1. **STOP**: Do NOT proceed to document depuration, service restart, git commit, or push.
2. **Generate Stabilization Audit Report**:
   Create a dedicated report at:
   `docs/audit/STABILIZATION_REPORT_<YYYYMMDD_HHMMSS>.md`
   using the template in [report-template.md](references/report-template.md).
3. **Report Structure**:
   - **Summary Table**: List all failed gates with severity (`P0 Blocker`, `P1 Critical`, `P2 Hygiene`).
   - **Detailed Findings**: Explain root causes, affected code with clickable links (`file:///...`), and exact required remediation.
   - **Pending Closeout Checklist**: Concrete `- [ ]` tasks required to unblock stabilization.
4. **Interactive Guidance**:
   Instruct the operator:
   > 🛑 **Estabilización Bloqueada**: Se detectaron inconsistencias o riesgos en la auditoría de calidad. Se ha generado el informe detallado en `[STABILIZATION_REPORT]`. Resuelve los ítems pendientes y vuelve a ejecutar `/speckit-stabilize` para iterar hasta la certificación completa.

---

### IF ALL GATES PASS (Status: PASS / CERTIFIED)

Proceed sequentially through Phases 3 to 6:

---

## Phase 3: Documentary Normalization & Safe Depuration

1. **Normalize Documentation**:
   - **Development Log**: Ensure `docs/audit/DEVELOPMENT_LOG.md` contains a newest-first entry capturing:
     - Context & Operator Intent.
     - Forensic findings & Root Causes.
     - Exact technical actions and architectural changes.
     - Validation evidence (tests, syntax, runtime checks).
     - Service and fleet operational state.
   - **Roadmap**: Update `docs/speckit/ROADMAP.md` to reflect completed items and active backlog.
   - **Active Tasks**: Ensure all completed tasks in `tasks.md` are checked `[x]`, and runtime commands are recorded in `evidence.md`.

2. **Execute Safe Transient Depuration**:
   Run the deterministic cleanup script:
   ```powershell
   & ".agents/skills/speckit-stabilize/scripts/cleanup_transients.ps1"
   ```
   - Purges stale diagnostic logs (`logs/deadlock_forensics_*.log` > 48h) and temporary `diagnostics/task-*.log`.
   - Cleans python bytecode caches (`__pycache__`, `.pytest_cache`).
   - **STRICT RULE**: Preserves `docs/audit/DEVELOPMENT_LOG.md`, `app/config.json`, `app/state.json`, and active service logs (`out.log`, `err.log`, `watchdog.log`).

---

## Phase 4: Runtime Service & Hardware Health

1. **Verify Windows NSSM Service**:
   Check service status:
   ```powershell
   nssm status MinerAlerts
   ```
   If Python source or configuration was modified, cleanly restart the service:
   ```powershell
   nssm restart MinerAlerts
   ```
   Verify that `logs/out.log` shows clean reconstitution without exceptions.

2. **Verify Live Fleet State**:
   Query ASIC 4028 / summary API to confirm:
   - All miners in `MINING` state with full chip complement (e.g. 126 chips/chain).
   - Real-time hashrate nominal.
   - Zero unapplied pending settings in VNish.

---

## Phase 5: Safe Git Commit & Feature-Scoped Push

1. **Inspect Working Tree**:
   ```powershell
   git status
   ```
   Verify that only intended files are staged. Guarantee `app/config.json` and `app/state.json` remain unstaged/untracked.

2. **Commit Changes**:
   Execute feature-scoped commit with standardized semantic message:
   ```powershell
   git add app/config.example.json app/miner_monitor.py docs/ ...
   git commit -m "fix/feat/chore(<scope>): <concise descriptive message>"
   ```

3. **Push to Remote**:
   Push the committed changes to the active tracking branch:
   ```powershell
   git push origin <active-branch>
   ```

---

## Phase 6: Handoff Protocol & `prompt.txt` Synchronization

1. **Update `prompt.txt`**:
   Write the updated context to `prompt.txt`:
   - Timestamp and active feature.
   - Summary of certified stabilization.
   - Current fleet telemetry (hashrate, presets, temperatures).
   - Reconstituted governance status (`reason=...`).
   - Essential diagnosis and verification commands.

2. **Console Notification**:
   In the final turn output, explicitly notify the user:
   - Stabilization certification status (`PASS - CERTIFIED`).
   - Commit hash and remote push confirmation.
   - Recommended model for the next session according to `AGENTS.md`:
     - **`Gemini 3.8 Flash High`**: Default engine for domain logic, monitoring, tests, and documentation.
     - **`Claude Sonnet 4.6 (Thinking)`**: For live multi-threading concurrency or core FSM race conditions.
