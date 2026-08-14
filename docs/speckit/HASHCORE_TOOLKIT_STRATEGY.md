# Hashcore Toolkit Strategy

**Last reviewed**: 2026-08-13
**Planned inventory window**: 2026-10-20 to 2026-10-29
**Spec**: `specs/026-hashcore-capability-inventory`

## Current Integration

The current shared config supports Hashcore Toolkit CLI for:

- `reboot`
- `restart`
- discovery/help fallback when action args are not configured
- `version` check in selftest

These are action-oriented capabilities and must remain gated by QA and manual
confirmation where applicable.

Hashcore is not a monitoring transport. It must not replace API 4028 polling,
Vnish evidence or the independent monitor watchdog.

## Capability Inventory

Before adding new features, inventory the local Toolkit installation through the
Spec 026 metadata-only tool. This default mode does not start the wrapper or
executable:

```powershell
& ".\\.venv\\Scripts\\python.exe" tools\\hashcore_inventory.py --config app\\config.json --metadata-only
```

Static inspection on 2026-08-13 established a local Hashcore Toolkit
`1.6.0+167` installation and a batch wrapper that forwards arbitrary `%*`
arguments. That proves installation identity, not command safety. The reviewed
invocation allowlist is currently empty, so process discovery remains blocked.
Existing production `version`/help probes are baseline behavior and are not
automatically approved for the inventory tool.

For each available command, record:

- command name
- read-only or action
- arguments
- expected output
- timeout expectation
- whether it touches a miner
- QA validation path

Metadata-only starts zero processes. Any future invocation requires exact
wrapper/executable fingerprints plus vendor evidence, fixed argv, no miner or
settings arguments, `shell=False`, no-window, disabled stdin, one attempt, a
10-second timeout and 64 KiB per-stream bounds. Unknown commands remain
prohibited (classified as mutating for execution policy) until vendor
documentation and controlled evidence prove otherwise.

## Recommended Feature Order

### 1. Read-Only Inventory

Goal: know what the toolkit sees without acting.

Examples:

- discovery
- device list
- firmware/version info
- profile/config read if supported

Deliverable: a versioned capability matrix with sanitized command samples,
exit codes, timeouts, side-effect classification and parser feasibility.

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
- Do not add a background Hashcore poller; use it only for proven diagnostics or
  explicitly confirmed actions.
- Do not schedule inventory commands until their cost and output are measured.
- Do not expand action scope during the Spec 026 inventory window.
- Do not treat wrapper pass-through, command names or existing monitor probes as
  proof of read-only behavior.
- Do not invoke any command while the fingerprint-bound allowlist is empty.

## Calendar Gate

Spec 026 starts only after monitor liveness, acquisition resilience, evidence
fusion, electrical discovery and metrics export have completed their production
review windows. Any new read-only integration becomes a separate spec; any new
action requires a separate high-risk spec and controlled production approval.

The current calendar places the inventory after Spec 025 and before Spec 028.
Its valid completion result may be a fully classified inventory with zero new
integration candidates.
