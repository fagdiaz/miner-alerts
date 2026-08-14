# Contract: Incident Assessment

## Purpose

Define deterministic normalization, persistence, confidence language and one
shared read-only rendering contract.

## Request

```text
subject_type: incident | episode | miner_window
subject_ref: stable non-empty reference
miner_key: optional stable miner identity
window_start_ts: finite epoch seconds
window_end_ts: finite epoch seconds
assessment_now_ts: finite epoch seconds, captured once by caller
ruleset_version: code-owned version
```

The window must be ordered, no longer than the configured bounded context and
must not end after `assessment_now_ts` beyond clock-skew tolerance.

## Inputs

- Persisted incident, episode or miner identity.
- Bounded telemetry, acquisition quality, operational event, reboot decision,
  firmware and collector rows.
- Existing deterministic stability, mining-quality and restart analyzers.
- Versioned rules and validated freshness limits.

## Semantic Output

```text
status: complete | incomplete | unpersisted | unavailable
ruleset_version
evidence_digest
window
findings[]
hypotheses[]
contradictions[]
missing_evidence[]
source_references[]
```

Every finding/hypothesis uses stable codes. Human text is produced only by the
shared renderer and cannot change stored semantics.

## Persistence

- Save is idempotent by subject, ruleset and evidence digest.
- Source references use canonical source table and row ID.
- Canonical semantic JSON is stored with stable ordering.
- Generated assessment ID and `created_ts` are audit metadata and do not affect
  replay equality.
- Persistence failure yields `unpersisted`; it never mutates source evidence.

## Renderer

The renderer presents, in this order:

1. subject, window, status and ruleset;
2. chronological observed facts with source/freshness;
3. suspected then confirmed hypotheses in stable code order;
4. contradictions;
5. missing/stale evidence;
6. explicit read-only/no-action footer when confidence is incomplete.

Telegram may bound output using its existing safe splitting. Dashboard output
may show more rows, but wording and semantic ordering come from the same
renderer.

## Failure And Safety Contract

- No miner IO, Vnish collection or Hashcore call during assessment.
- Timing alone never confirms causality.
- Stale, invalid, late or unknown-clock evidence cannot confirm an
  ordering-sensitive cause.
- Unknown codes fail closed.
- A source/query failure is shown as incomplete/missing evidence.
- A bounded query or render budget failure uses the existing diagnosis fallback.
- Assessment output never changes state, alerts, streaks or action decisions.

## Compatibility

- Existing event, episode and diagnosis views remain available.
- `incident_fusion_enabled=false` preserves current behavior.
- Schema migration is additive for old readers.
- Disabling fusion is sufficient rollback; no destructive migration is needed.
