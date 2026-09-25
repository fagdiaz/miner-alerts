# Stabilization & Closeout Exhaustive QA Checklist

Apply this exhaustive checklist before every feature stabilization, commit, and release closeout.

## 1. Runtime & Actuator Safety

- [ ] **No Ungated Auto-Reboots**: All automated restart/reboot actuators are protected by `should_allow_intervention`, sustained failure streaks, thermal guards (max 85°C), fleet guardrails, and firmware transition checks.
- [ ] **No Hot Preset Mutations Without Permission**: Any function calling `safe_set_miner_preset` or altering `overclock.preset` / `top_preset` in runtime MUST verify `presets_allowed` or `should_allow_intervention(ACTION_PRESET_BALANCER)`. When `presets_enabled = False`, hot mutations are strictly suppressed.
- [ ] **Soft-Landing Safe Recovery**: Level 1 soft restart does not apply destructive pre-clamps (e.g. 1800W) or hot jumps (e.g. 1800W -> 2300W) if automated preset modulation is paused by governance.
- [ ] **Fan Governor Thermal Protection**: When active, Fan Governor modulates fan speeds based on chip temperature deadband (target 82.0°C) with bounded duty cycles [30%, 100%] without changing overclock presets.
- [ ] **Startup & Cold-Boot Grace**: Fleet cold-boot grace period and startup guards prevent premature OFFLINE or LOW alerts while hashboards are initializing/warming up.

## 2. Firmware (VNish) Harmony & "Apply" Loop Prevention

- [ ] **No Dirty Staged Settings**: No REST API call writes to `/api/v1/settings` without immediate execution or proper state lifecycle.
- [ ] **Restart Required Flag**: Verify `/api/v1/status` on all miners returns `restart_required: false` (or clean operational state).
- [ ] **Web UI Protection**: The VNish web dashboard must NOT display an unapplied "Changes detected: Click [Apply]" banner. The operator must be able to use the browser as a passive telemetry viewer without accidental reboot triggers.
- [ ] **Preset Switcher Consistency**: `preset_switcher.enabled` and `top_preset` match the desired ceiling (e.g., 2700W) across all active miners.

## 3. Telegram UX, Anti-Spam & Delivery Diagnostics

- [ ] **Anti-Spam Flap Suppression**: Offline threshold uses at least 3 consecutive failures (`fails_before_alert = 3` / 90s) to prevent false alerts during transient network hiccups, while preserving sub-second phase drop detection.
- [ ] **Secondary Sensor Alerts Routed to Daily Digest**: Non-fatal single-sensor anomalies (e.g., thermal sensor disconnect on a fully functional board) are suppressed from standalone push alerts and channeled into the daily digest.
- [ ] **Multi-Slot Daily Digest**: Supports scheduled digest delivery (e.g., `10:00,22:00`) without duplicate sends within the same hour window.
- [ ] **Deterministic Command Routing**: All Telegram slash commands (`/status`, `/why`, `/interventions`, `/maintenance`) reply predictably without hanging or unhandled exceptions.
- [ ] **Click-Safe Confirmations**: Sensitive manual actions require explicit, tokenized 2-step confirmation.

## 4. Configuration, State & Secret Hygiene

- [ ] **Local Files Untracked**: `app/config.json` and `app/state.json` are in `.gitignore` and NEVER staged or committed to Git.
- [ ] **Config Example Synchronization**: Any new configuration key introduced in `app/config.json` is documented in `app/config.example.json` with explanatory comments.
- [ ] **No Leaked Secrets**: Telegram `bot_token`, chat IDs, API passwords, and internal tokens are absent from git diffs and logs.
- [ ] **Bounded Sockets & Timeouts**: All network HTTP and socket 4028 calls enforce strict timeouts (1.5s - 5.0s).

## 5. SpecKit Traceability & Definition of Done

- [ ] **Tasks Closeout**: All actionable tasks in the active feature's `tasks.md` are marked completed `[x]`, or explicitly documented as deferred/blocked.
- [ ] **Evidence Recording**: `evidence.md` records exact PowerShell verification commands and runtime output snapshots.
- [ ] **Development Log**: A newest-first entry exists in `docs/audit/DEVELOPMENT_LOG.md` detailing context, forensics, actions, test evidence, and service state.
- [ ] **Roadmap Alignment**: `docs/speckit/ROADMAP.md` reflects current completion and active horizon.
- [ ] **Deterministic Test Suite**: Pytest regression suite passes 100% with 0 failures (`1397+ tests PASS`).
- [ ] **Service Running**: Windows NSSM service `MinerAlerts` is verified in `SERVICE_RUNNING` state.
