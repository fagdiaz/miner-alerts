# Contract: Operator Workflow And Conditional API

## Purpose

Define the no-build decision gate and, only if approved, the local read-only API boundary.

## Inputs

- Workflow scorecard across current interfaces.
- Read-only SQLite data and assessment contracts.

## Outputs

- No-build or scoped-MVP decision.
- Conditional typed read-only resources and local views.

## Failure And Safety Contract

- Loopback binding only.
- No miner, action, Hashcore or config mutation imports.
- Bounded queries and redacted errors.

## Compatibility

- Telegram remains the action channel.
- Static HTML and Grafana remain valid even if the MVP is absent.
