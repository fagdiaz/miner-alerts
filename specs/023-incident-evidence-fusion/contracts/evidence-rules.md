# Contract: Evidence And Confidence Rules

## Vocabulary

- **Observed**: a normalized fact or pattern directly present in eligible
  persisted evidence. It is not a causal claim.
- **Suspected**: a candidate cause with eligible support, no decisive
  contradiction and no direct proof sufficient for confirmation.
- **Confirmed**: a narrowly defined cause supported by at least one recognized
  direct-cause fact, all required facts fresh and orderable, and no decisive
  contradiction.
- **Missing**: required evidence was absent, stale, invalid, unorderable or its
  collector failed.

Facts are always observations. Only a `CauseHypothesis` receives `suspected` or
`confirmed`. Rendering must not turn an observed symptom into a confirmed cause.

## Stable Fact Families

The initial ruleset recognizes these code families:

| Family | Examples | Meaning |
| --- | --- | --- |
| `signal.*` | `current_low`, `current_offline`, `current_hashboard`, `recovered` | API 4028 state observation |
| `restart.*` | `uptime_reset`, `unattributed` | Persisted elapsed/reset evidence |
| `action.*` | `manual_reboot`, `auto_reboot`, `service_restart`, `failed` | Recorded action and outcome |
| `firmware.*` | `chain_break`, `miner_stopped`, `thermal` | Normalized Vnish firmware event |
| `quality.*` | `reject_high`, `stale_high`, `hw_error_high`, `no_share_progress` | Deterministic mining-quality reason |
| `fleet.*` | `concurrent_degradation`, `isolated_degradation` | Bounded cross-miner timing pattern |
| `collector.*` | `ok`, `partial`, `failed`, `stale` | Firmware-source availability |
| `acquisition.*` | Spec 022 quality/reason codes | Authority and acquisition quality |
| `power.*` | Spec 024 external-source codes only | External electrical facts, when proven |

Unknown codes cannot support a hypothesis until a later ruleset explicitly
recognizes them.

## Time And Freshness

- `assessment_now_ts` is supplied once; pure rule code never calls the wall
  clock.
- Telemetry freshness uses `diagnosis_stale_seconds` (default 900 seconds).
- Firmware context uses `diagnosis_firmware_window_hours` (default 24 hours).
- Collector freshness uses `diagnosis_collector_stale_seconds` (default 3600
  seconds).
- Action attribution reuses `restart_attribution_window_seconds` (default 900
  seconds).
- Fleet concurrence uses `incident_fusion_fleet_window_seconds` (default 60
  seconds) and at least two distinct miners.
- Assessment context uses `incident_fusion_context_hours` (default 24 hours).

A future timestamp beyond five seconds of `assessment_now_ts` is clock-skewed.
Age is never silently clamped to make a future fact look current. Stale,
clock-skewed or unparsed-clock evidence remains visible but cannot confirm an
ordering-sensitive cause.

## Source Time

| Source | Effective time | Clock quality |
| --- | --- | --- |
| telemetry | `observed_ts` | `system` |
| operational event | `occurred_ts` | `system` |
| reboot decision | `evaluated_ts` | `system` |
| firmware parsed | `source_ts_epoch` | stored `system_local` or `fixed_utc_offset` |
| firmware unparsed | `collected_ts` | `unparsed` |
| collector run | `completed_ts` | `system` |

`collected_ts` proves ingestion, not when the firmware event occurred.

## Confidence Ceilings

| Evidence condition | Maximum use |
| --- | --- |
| Fresh direct source-specific causal code, valid authority and order | May participate in `confirmed` |
| Fresh symptom, quality reason or bounded fleet pattern | `suspected` cause at most |
| Temporal proximity without direct cause evidence | `suspected` at most |
| Stale, invalid, partial, late or clock-uncertain source | `observed` only |
| Free-form summary text | display context only |
| Missing or failed collector | missing evidence only |

The final hypothesis level is the minimum ceiling across every fact required by
that rule. More low-quality facts never increase confidence.

## Confirmation Rules

A cause may be `confirmed` only when the versioned rule declares all of:

1. a recognized direct-cause fact code;
2. subject identity match;
3. fresh and valid authoritative evidence where required;
4. orderable timestamps inside the rule window;
5. every required supporting fact present; and
6. no decisive contradiction.

Initial examples that may qualify are deliberately narrow:

- An attributed action: recorded successful action plus persisted uptime reset
  for the same miner inside the existing attribution window.
- A firmware-reported chain or thermal shutdown: direct normalized firmware
  code plus matching board/thermal symptom, with a parsed fresh source clock.

These statements confirm the recorded action or firmware-reported condition,
not every downstream physical root cause.

## Mandatory Conservative Cases

- API OFFLINE alone cannot confirm network, power or miner failure.
- LOW alone cannot confirm tuning, pool, board, temperature or electrical cause.
- Multiple miners changing together creates `fleet.concurrent_degradation` but
  cannot confirm a shared electrical event.
- Board/chain voltage fields are internal miner-domain observations and cannot
  confirm AC input fluctuation.
- `power.*` confirmation is unavailable until Spec 024 selects and validates an
  external PDU/UPS/meter source.
- Collector success with zero relevant events is not proof that firmware was
  healthy before the collected window.
- Collector failure or truncation cannot be interpreted as no firmware fault.
- Contradictory fresh evidence prevents confirmation and remains visible.

## Contradictions And Missing Evidence

Each hypothesis stores stable codes for:

- `supporting_fact_ids`;
- `contradicting_fact_ids`;
- `missing_requirement_codes`.

Examples of decisive contradictions include a claimed action-caused restart
with no successful action in the attribution window, or a claimed current LOW
condition contradicted by a newer valid OK sample. Absence is not automatically
a contradiction; it is represented as missing evidence.

## Fleet Correlation

A fleet pattern requires at least two distinct miners whose first persisted
irregular observation occurs within the configured 60-second default window.
The pattern stores the member miner keys, first observation references and
window span. It remains an observed pattern. It cannot directly produce an
action recommendation or electrical confirmation.

## Determinism And Versioning

- Rules execute in stable cause-code order.
- Source facts execute in canonical sort order.
- Numeric non-finite values are invalid facts, never serialized as NaN/Infinity.
- Canonical JSON uses sorted keys and stable separators.
- `ruleset_version` is a code constant and changes whenever normalization,
  eligibility or scoring semantics change.
- Replaying identical fact references, window and ruleset produces identical
  semantic JSON and `evidence_digest`.
- `created_ts` and database IDs are excluded from the digest.

## Action Boundary

No assessment field is an action recommendation or policy input. Fusion cannot
call Hashcore, change miner state, alter streaks, satisfy sustained LOW, bypass
QA/startup/cooldown/window guards, or suppress an existing alert.
