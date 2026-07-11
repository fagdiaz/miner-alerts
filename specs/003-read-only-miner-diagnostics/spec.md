# Feature Specification: Read-Only Miner Diagnostics

## User Story

As an operator, I want a read-only diagnostics collector that captures miner
health evidence before changing reboot policy, so that false alerts and
unnecessary reboots can be investigated without risking production behavior.

## Scope

In scope:

- Load Miner Alerts config from a chosen JSON path.
- Read the configured miners list.
- Query ASIC API 4028 commands: `summary`, `stats`, `pools`, `version`.
- Generate sanitized `summary.md` and `snapshot.json` outputs.
- Support `--dry-run` for validation without miner network calls.
- Provide an optional Docker image for the diagnostics collector only.

Out of scope:

- Reboot, restart, firmware tuning, or Hashcore action commands.
- Changes to `app/miner_monitor.py`.
- Changes to `app/config.json` or `app/state.json`.
- A web dashboard.

## Acceptance Criteria

- The collector is read-only and does not call Hashcore Toolkit.
- The collector does not write `app/state.json`.
- The collector can run against `app/config.example.json` with `--dry-run`.
- Generated outputs avoid Telegram tokens, chat IDs, and pool user disclosure.
- Docker usage is documented and limited to diagnostics.

## Safety Notes

- Diagnostics evidence is descriptive. It must not automatically change
  auto-reboot policy.
- Power telemetry is reported only when firmware exposes candidate fields.
  AC input voltage needs external PSU/PDU/UPS evidence unless proven otherwise.
