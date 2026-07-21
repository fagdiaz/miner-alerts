# Miner Alerts Speckit Roadmap

## Operating Goal

Miner Alerts should become an operations layer for S19j Pro miners, not only a
Telegram alert script. The priority is to reduce false alerts, prevent unnecessary
reboots, expose useful diagnostics, and keep dangerous actions controlled.

## P0 - Production Safety And No Unnecessary Reboots

- [x] Persist and classify uptime-reset incidents as expected-manual, expected-auto, or unexpected without changing action policy.
- [x] Send evidence-rich restart alerts without false cause certainty; coalesce fleet restarts and suppress only transient Telegram recovery noise.
- [ ] Audit false alert scenarios: transient LOW, recovery hysteresis, stale snapshot, offline/no-data.
- [ ] Audit auto-reboot gates: startup guard, sustained LOW, cooldown, reboot window, QA block.
- [x] Require a current finite below-threshold signal before auto-reboot evaluation; invalid and recovered samples now break the sustained LOW timer.
- [x] Align production Vnish hashboard detection with real `STATS[1].chain_acn1..N` payloads and the read-only diagnostics parser.
- [x] Block automatic reboot on current high-temperature evidence or fresh shared fleet degradation without adding miner IO.
- [ ] Verify `state.json` cannot trigger immediate auto-reboot after restart.
- [x] Split "bad signal" from "actionable reboot candidate": LOW alone no longer implies reboot.
- [x] Add an audit table for every reboot decision with signal, duration, board/Vnish evidence, cooldown, window, QA and startup-guard context.
- [ ] Keep Telegram dangerous actions behind confirmation.
- [ ] Define "do not reboot" reasons: stale data, no hash but offline, autotune active, firmware restart in progress, high temp protection, pool outage, power anomaly suspected.

## P1 - Miner Diagnostics And Sweet Spot Discovery

- [x] Add a read-only diagnostics collector for API 4028 commands: `summary`, `stats`, `pools`, `version`.
- [x] Add a diagnostics matrix for each miner: hashrate, elapsed, active boards, temps, pool status, firmware hint, candidate telemetry fields.
- [x] Normalize observed Vnish fields from all `STATS` entries: chain voltage/consumption/frequency/HW errors, temperatures and fan indicators.
- [x] Add an initial sweet-spot baseline analyzer from diagnostics snapshots: TH/s band, board count, max temp, chain voltage, consumption, frequency and HW errors.
- [ ] Define production sweet-spot profiles from multiple snapshots per miner: stable TH/s range, temperature band, board count, error rate, reboot history, restart history.
- [x] Add a robust read-only per-miner baseline (median/MAD) with learning, stable, watch, and critical diagnosis from persisted healthy samples.
- [x] Persist and classify interval accepted/rejected/stale shares, HW-error growth, chain faults, and firmware transitions from existing Vnish telemetry.
- [ ] Track "soft symptoms" before reboot: repeated LOW with recovery, board missing, pool reconnects, high reject/stale shares, temperature throttling, watchdog restarts.
- [ ] Decide whether a restart is safer than reboot when firmware/miner service is alive but hash is degraded.

## P2 - Hashcore Toolkit Integration

- [ ] Inventory available Hashcore Toolkit CLI commands locally with `version`, `help`, and discovery commands.
- [ ] Document which commands are safe read-only and which are action commands.
- [ ] Keep current action scope limited to `reboot` and `restart` until command behavior is proven.
- [ ] Evaluate useful read-only integrations: discovery, status, firmware info, batch inventory, profile/config export if supported by local toolkit.
- [ ] Add a Hashcore capability map: command, arguments, risk, timeout, expected output, parsing strategy, validation evidence.
- [ ] Add dry-run or QA-only wrappers for new Hashcore features before enabling production use.

## P3 - Vnish Firmware Logs And Miner-Side Evidence

- [x] Identify how Vnish exposes logs on the deployed firmware: confirmed read-only WebSockets at `/api/v1/logs-ws/{status|miner|autotune|system}`.
- [x] Build a log taxonomy: autotune, voltage/frequency changes, chain restarts, miner process restarts, fan/temp protections, pool reconnects, watchdog actions.
- [x] Create a bounded parser and schema-v4 store for normalized events without full raw logs.
- [x] Correlate Vnish events with Miner Alerts state changes and Telegram alerts through bounded SQLite-only `/diagnose` evidence.
- [x] Detect "Vnish working normally" vs "miner actually needs intervention" with advisory OK/WATCH/CRITICAL diagnosis that never authorizes actions.
- [x] Avoid reboot during current Vnish chain autotune/profile transitions and require a fresh sustained LOW interval after they end.

## P4 - Power And Electrical Observability

- [ ] Determine whether S19j Pro/Vnish exposes PSU input voltage, PSU output voltage, current, or power draw through API/logs.
- [ ] If miner firmware does not expose AC input voltage, document the limitation and use external PDU/UPS/smart meter integration as the source.
- [x] Confirm current API 4028 voltage fields are chain-side only and keep AC-input diagnosis outside miner telemetry.
- [ ] Track symptoms that suggest power instability: simultaneous miner drops, board resets, PSU warnings, fan spikes, hashboard disappear/reappear events.
- [ ] Decide data source for electrical telemetry: firmware stats, PDU API, UPS API, smart plug, or manual CSV import.
- [ ] Add power anomaly as a separate diagnosis; do not auto-reboot based only on suspected voltage fluctuation.

## P5 - Telegram Reliability And UX

- [x] Keep empty QA polling batches free of command-local references and exception backoff.
- [x] Add read-only `/events`, `/events <miner>`, and `/event <id>` incident-history commands.
- [ ] Validate click-safe commands: `/rb<ID>`, `/reboot_no_ok`, `/c<code>`.
- [ ] Ensure all command replies use command delivery semantics and avoid dedupe/coalesce loss.
- [ ] Keep no-silence behavior for invalid confirms and expired pending actions.
- [ ] Document debug flags and expected log traces.
- [x] Disable noisy degraded hourly status by default and keep Telegram notifications event-driven.
- [x] Add clearer event context to `STATE_CHANGE` Telegram messages.
- [x] Coalesce restart incidents across a bounded fleet window and emit one post-recovery summary without changing persisted transitions.
- [x] Add read-only `/why [miner]` explanations for QA, startup guard, cooldown, not sustained, window, invalid signal and action outcomes.
- [x] Add read-only `/health [all|miner]` diagnosis against each miner's learned stable baseline without live miner IO.
- [x] Add read-only `/quality [all|miner]` interval diagnosis for shares, HW errors, chain faults, and firmware transitions.

## P6 - Optional Local Interface

- [ ] Keep Telegram as the primary remote-control surface for now.
- [x] Evaluate and implement a local read-only static dashboard after the diagnostics collector produced stable evidence.
- [x] Generate a self-contained HTML fleet view with current cards, trends, incidents, and reboot-decision history from SQLite.
- [x] Reuse the Stability Advisor in dashboard cards so Telegram and local HTML share the same diagnosis.
- [x] Reuse Mining Quality assessments in dashboard cards with interval deltas and bounded reasons.
- [ ] Dashboard MVP: miner cards, current state, last event, last reboot, blocked_by reasons, Vnish event timeline, Hashcore capability status.
- [ ] Do not expose reboot/restart from a web UI until auth, local-only binding, audit logs, and confirmation are designed.
- [ ] Prefer a local Windows dashboard or static HTML report before a full web app.

## P7 - Observability And Release Hygiene

- [x] Add a bounded SQLite operational history for telemetry, state transitions, restart incidents, and action outcomes.
- [x] Add schema-v2 normalized Vnish telemetry, reboot-decision history, retention, and a read-only incident report.
- [x] Add additive schema-v3 mining-quality counters and chain-health evidence without raw firmware payloads.
- [x] Add additive schema-v4 idempotent Vnish firmware events with bounded read-only collector and views.
- [x] Add additive schema-v5 source-time provenance, collector-run health and a non-overlapping Windows scheduled collector.
- [ ] Standardize logs for blocked actions and delivery failures.
- [ ] Maintain production defaults in `app/config.example.json`.
- [ ] Keep release checklist current for Windows PowerShell.
- [ ] Record validation evidence per spec.
- [ ] Keep raw runtime logs, exported Vnish logs, and electrical telemetry out of git unless anonymized samples are explicitly needed.
