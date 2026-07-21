# Contract: Firmware Transition Reboot Decision

## Input

- Current automatic reboot candidate and existing gate context.
- Current `chains_transitioning_count` from already-fetched telemetry.
- `auto_reboot_firmware_transition_guard_enabled`.

## Output

When enabled and the count is positive:

```text
allowed=false
reason=firmware_transition
chains_transitioning_count=<bounded integer>
```

Runtime evidence:

```text
[AUTO-REBOOT] blocked_by=firmware_transition miner=<name> transitioning_chains=<n>
```

The existing `/why` decision renderer identifies the transition and states that a new sustained LOW observation is required.
