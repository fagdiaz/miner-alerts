# Data Model: Incident Evidence Fusion

## EvidenceFact

Immutable normalized observation generated from a persisted source row.

- `fact_id`: deterministic `<source_table>:<source_row_id>:<code>` reference.
- `subject_type / subject_key`: miner or fleet subject.
- `source / source_row_id`: canonical source table and integer row identity.
- `code`: stable normalized fact code from the versioned ruleset.
- `effective_ts / ingested_ts`: event time and optional collection time.
- `freshness`: `fresh`, `stale`, `future_skew`, `unknown`.
- `clock_quality`: `system`, `system_local`, `fixed_utc_offset`, `unparsed`,
  or `unknown`.
- `authority / quality / reason_code`: Spec 022 acquisition contract where
  applicable.
- `value / units`: sanitized finite scalar or bounded structured value.
- `confidence_ceiling`: `observed`, `suspected` or `confirmed`.

Facts do not copy free-form source payloads and are not written back to source
tables.

## CauseHypothesis

- `cause_code`: stable candidate code.
- `level`: `suspected` or `confirmed`.
- `summary_code`: renderer-owned stable phrase key.
- `supporting_fact_ids`: sorted evidence references.
- `contradicting_fact_ids`: sorted counterevidence references.
- `missing_requirement_codes`: sorted required evidence not available.
- `confidence_ceiling`: lowest eligible ceiling used by the rule.

An observed symptom or fleet pattern is rendered as a finding, not a cause
hypothesis.

## IncidentAssessment

- `assessment_id`: SQLite-generated audit identity.
- `subject_type`: `incident`, `episode` or `miner_window`.
- `subject_ref`: stable canonical subject reference.
- `miner_key`: nullable for fleet assessments.
- `ruleset_version`: code-owned semantic version.
- `window_start_ts / window_end_ts / assessment_now_ts`: explicit bounded time.
- `status`: `complete`, `incomplete`, `unpersisted` or `unavailable`.
- `evidence_digest`: canonical SHA-256 digest of semantic inputs.
- `findings_json`: canonical observed findings.
- `hypotheses_json`: canonical hypotheses and confidence.
- `contradictions_json`: canonical visible contradictions.
- `missing_evidence_json`: canonical missing requirement codes.
- `created_ts`: audit insertion time, excluded from semantic digest.

Uniqueness is `(subject_type, subject_ref, ruleset_version, evidence_digest)`.
Repeated save returns the existing assessment identity.

## AssessmentFactReference

- `assessment_id`: parent assessment.
- `fact_id`: normalized deterministic fact identity.
- `source_table / source_row_id`: canonical source reference.
- `fact_code`: normalized code.
- `relation`: `finding`, `supporting` or `contradicting`.

Primary identity is `(assessment_id, fact_id, relation)`. Missing evidence has
no invented source row and stays in `missing_evidence_json`.

## MinerBaseline

This is a derived in-memory value produced by the existing stability analyzer:

- stable finite operating bands;
- source sample IDs and window;
- eligibility count and exclusion reasons;
- ruleset/version context.

It is not a second mutable miner profile table in the first release.

## Additive SQLite Shape

```sql
CREATE TABLE incident_assessments (...);
CREATE UNIQUE INDEX ux_assessment_replay
  ON incident_assessments(subject_type, subject_ref, ruleset_version, evidence_digest);
CREATE INDEX ix_assessment_subject_time
  ON incident_assessments(subject_type, subject_ref, created_ts DESC);

CREATE TABLE assessment_fact_refs (...);
CREATE INDEX ix_assessment_fact_source
  ON assessment_fact_refs(source_table, source_row_id);
```

The exact migration follows EventStore's schema-version pattern. Existing
tables and rows are never rewritten by Spec 023.

## Invariants

- No hypothesis outranks the lowest ceiling of its required evidence.
- Raw facts are never rewritten by fusion.
- Clock-uncertain facts cannot prove ordering-sensitive causes.
- Non-finite values never enter canonical JSON.
- Canonical digest excludes generated IDs and creation wall time.
- Assessments never feed action authorization, state transitions or alert
  suppression.
