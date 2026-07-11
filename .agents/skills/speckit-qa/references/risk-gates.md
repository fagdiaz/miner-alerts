# Risk Gates

Read only for MEDIUM or HIGH QA. Apply relevant headings; do not turn this into a repository-wide audit.

## Runtime Safety

- Preserve QA guardrails and require explicit evidence before real reboot/restart behavior is considered verified.
- Preserve startup guard, sustained LOW checks, cooldowns, reboot windows, and degraded-mode limits.
- Ensure `state.json` cannot become a direct trigger for immediate auto-reboot after restart.
- Keep manual dangerous actions behind confirmation.

Block unresolved paths that can cause unnecessary reboots, false recovery, or silent dangerous action.

## Telegram Operations

- Commands must reply deterministically, including invalid confirm and expired pending cases.
- Click-safe aliases must map to existing confirmed flows and must not bypass confirmation.
- Delivery hardening must preserve non-command dedupe/coalesce behavior.
- Debug logging must be gated unless the log is an explicit production safety log.

Block command changes that can silently drop operator replies or execute action without confirmation.

## Configuration And Secrets

- Keep `app/config.json`, `app/state.json`, logs, tokens, chat IDs, and local runtime files out of commits.
- Update `app/config.example.json` and docs only for shared configuration examples.
- Do not log secrets, tokens, or full Telegram payloads.
- Keep Windows PowerShell commands valid.

Block secret exposure or ambiguity about which config is active in production.

## Hashcore And Miner IO

- Hashcore CLI calls must remain explicit and gated by QA/config policy.
- ASIC API calls must have bounded timeouts.
- Status/help paths should avoid unnecessary live IO when snapshot data is sufficient.
- Failures must produce actionable logs without causing repeated command execution.
