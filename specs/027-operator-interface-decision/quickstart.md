# Quickstart: Operator Interface Decision

**Status**: Planned validation procedure; referenced implementation files are conditional and do not exist yet.

## Preconditions

- Spec 025 Grafana and Spec 028 restore proof are complete.
- The fixed `workflow-scorecard.md` fields and target times are used unchanged.

If either dependency is incomplete, record `blocked` and stop. Do not install
FastAPI/Uvicorn/HTMX or create conditional source files.

## Static And Automated Validation

```powershell
& ".\.venv\Scripts\python.exe" -m unittest tests.test_operations_dashboard
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py"
```

Run `tests.test_operator_api`, compile/import and OpenAPI commands only after the
scorecard explicitly selects `fastapi_mvp` and those conditional files exist.

## Controlled Runtime Validation

1. Confirm Spec 025/028 evidence and time three runs for every eligible P1
   workflow/interface pair.
2. Record no-build or approved-MVP decision.
3. If no-build, prove all conditional files/dependencies/services are absent and stop.
4. If built, audit exact loopback binding, disabled proxy/CORS, OpenAPI methods,
   query bounds, read-only/query-only SQLite and redaction.
5. Stop the interface and prove monitor independence.
6. Observe D+1/D+3 only if a service is deployed.

## Evidence To Capture

- Completed three-run workflow scorecard with dependency evidence.
- Signed no-build or scoped-MVP decision.
- No-build conditional-file absence audit, when selected.
- Conditional route/OpenAPI/no-action audit.
- Query latency and bounded-result evidence.
- Service isolation and D+1/D+3 notes if built.
