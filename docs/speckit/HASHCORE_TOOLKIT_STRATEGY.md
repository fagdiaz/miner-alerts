# Hashcore Toolkit Strategy

## Current Integration

The current shared config supports Hashcore Toolkit CLI for:

- `reboot`
- `restart`
- discovery/help fallback when action args are not configured
- `version` check in selftest

These are action-oriented capabilities and must remain gated by QA and manual
confirmation where applicable.

## Capability Inventory

Before adding new features, inventory the local toolkit installation:

```powershell
& "C:\\Program Files\\Hashcore\\Toolkit\\toolkit_cli.bat" version
& "C:\\Program Files\\Hashcore\\Toolkit\\toolkit_cli.bat" help
```

For each available command, record:

- command name
- read-only or action
- arguments
- expected output
- timeout expectation
- whether it touches a miner
- QA validation path

## Recommended Feature Order

### 1. Read-Only Inventory

Goal: know what the toolkit sees without acting.

Examples:

- discovery
- device list
- firmware/version info
- profile/config read if supported

### 2. Safer Diagnostics

Goal: enrich diagnosis before reboot.

Examples:

- miner reachable through toolkit
- toolkit error classification
- per-miner command availability
- last known toolkit result

### 3. Controlled Actions

Goal: keep actions limited and auditable.

Allowed only with confirmation and QA guardrails:

- restart
- reboot
- future action commands only after separate spec and evidence

## Rules

- Do not add batch actions until single-miner behavior is proven.
- Do not parse arbitrary CLI output without samples in evidence.
- Do not enable new action commands by default.
- Do not run real actions in QA unless `qa_allow_real_actions` is explicitly enabled.
