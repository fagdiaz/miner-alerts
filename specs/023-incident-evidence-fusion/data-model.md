# Data Model: Incident Evidence Fusion

## EvidenceFact

- `fact_id`: Persisted or derived reference.
- `miner_key`: Miner or fleet subject.
- `source / code`: Normalized origin and meaning.
- `observed_ts / ingested_ts`: Time and freshness.
- `value / units`: Sanitized payload.
- `clock_quality`: System, offset, unparsed or unknown.
- `confidence_ceiling`: Highest conclusion this fact supports.

## CauseHypothesis

- `cause_code`: Stable candidate.
- `confidence`: Observed, suspected or confirmed.
- `supporting_fact_ids`: Evidence references.
- `contradicting_fact_ids`: Counterevidence.
- `missing_requirements`: Needed facts.

## IncidentAssessment

- `assessment_id / ruleset_version`: Audit identity.
- `incident_id / episode_ref`: Canonical subject.
- `window_start_ts / window_end_ts`: Bounded context.
- `findings / hypotheses`: Versioned result.
- `created_ts`: Generation time.

## Invariants

- No conclusion outranks the strongest eligible evidence.
- Raw facts are never rewritten by fusion.
- Clock-uncertain facts cannot prove ordering-sensitive causes.
- Assessments never feed action authorization.
