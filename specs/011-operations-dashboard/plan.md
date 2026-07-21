# Implementation Plan: Read-Only Operations Dashboard

**Branch**: `011-operations-dashboard` | **Date**: 2026-07-20 | **Spec**: [spec.md](spec.md)

## Summary

Create a standalone standard-library CLI that opens the existing SQLite database
with `mode=ro`, builds a bounded operational view model, and renders a responsive
self-contained HTML dashboard. No server, framework, monitor import, or action
endpoint is introduced. An optional minimal Docker image runs the same generator.

## Technical Context

**Language/Version**: Python standard library
**Primary Dependencies**: `sqlite3`, `argparse`, `html`, inline SVG/CSS
**Storage**: Existing SQLite schema v1/v2, read-only
**Testing**: `unittest`, generated-document assertions, `py_compile`
**Target Platform**: Windows PowerShell and optional Docker Desktop
**Project Type**: Standalone report generator
**Performance Goals**: Generate a 24-hour small-fleet dashboard in under two seconds
**Constraints**: No network listener, no remote assets, no actions, bounded queries
**Scale/Scope**: Local ASIC fleet and up to one year selectable history

## Constitution Check

- **Production Safety First**: PASS. Strictly read-only and offline.
- **Single Source Of Truth**: PASS. No config or secret is read.
- **Telegram Operational Controls**: PASS. Telegram is untouched.
- **Auto-Reboot Evidence And Gates**: PASS. Decisions are displayed, never evaluated or changed.
- **Windows Compatibility**: PASS. Native command is primary; Docker is optional.
- **Evidence-Based Completion**: PASS. Read-only, escaping, bounds, and output tests are required.

## Design

1. Open SQLite through a read-only URI and inspect table/column availability.
2. Query latest samples per miner, bounded trend points, recent events, and recent decisions.
3. Build a JSON-compatible view model separated from rendering.
4. Render escaped semantic HTML with CSS Grid and inline SVG sparklines.
5. Mark stale cards from sample age without altering stored state.
6. Return explicit CLI exit codes for missing DB/schema/write failures.
7. Provide a minimal Dockerfile that only copies and runs the report generator.

## Project Structure

```text
tools/operations_dashboard.py
tests/test_operations_dashboard.py
Dockerfile.dashboard
docs/speckit/RUNBOOK.md
specs/011-operations-dashboard/
```

## Validation

- Test-first fixture using the real EventStore schema.
- Escaping test with hostile-looking names/summaries.
- Empty database and read-only connection tests.
- CLI generation smoke test and HTML size/bounds assertions.
- Full Python suite, compile, diff check, and Speckit MEDIUM-risk preflight.

## Complexity Tracking

No framework is introduced. Static HTML is intentionally selected before
FastAPI/HTMX because the current need is read-only visibility, not a long-running
web control plane.
