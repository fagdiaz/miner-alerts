# Research: Vnish Transition Reboot Interlock

## Decision: Use Current Chain-State Evidence

The deployed API 4028 payload exposes bounded `chain_stateN` values, and Spec 013 already normalizes explicit tuning/startup markers into `chains_transitioning_count`. This is stronger evidence than inferring tuning from low hashrate alone and requires no additional request.

## Decision: Block And Restart Sustained Observation

Blocking only the transition tick would allow accumulated LOW time to trigger an immediate reboot on the first post-transition sample. Resetting the existing `low_since_ts` to the block timestamp requires the configured sustained interval after the last observed transition while avoiding a new state field.

## Decision: Default Enabled, Explicit Disable

The gate is fail-open for absent evidence and only blocks on a positive current count. Enabling by default reduces unnecessary actions without classifying unknown data as safe or unsafe.

## Alternatives Considered

- Parse full Vnish logs now: rejected for this spec because no validated deployed log endpoint exists.
- Infer transition from uptime or low hashrate: rejected because it would create false positives.
- Add a new recovery state/timer: rejected because the existing sustained timer expresses the required observation window.
