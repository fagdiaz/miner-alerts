# Quickstart: Operator Interface Decision

**Status**: Planned validation procedure; referenced implementation files are conditional and do not exist yet.

## Preconditions

- Spec 025 Grafana and Spec 028 restore proof are complete.
- Operator workflows and target times are agreed before build.

## Static And Automated Validation

```powershell
& ".\.venv\Scripts\python.exe" -m unittest tests.test_operations_dashboard tests.test_operator_api
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py"
& ".\.venv\Scripts\python.exe" -m py_compile app\operator_api.py app\operator_views.py
& ".\.venv\Scripts\python.exe" -c "import app.operator_api as a; print(a.app.openapi()['info']['title'])"
```

## Controlled Runtime Validation

1. Time P1 workflows in Telegram, static HTML and Grafana.
2. Record no-build or approved-MVP decision.
3. If built, audit loopback binding, OpenAPI routes, methods, query bounds and redaction.
4. Stop the interface and prove monitor independence.
5. Observe D+1/D+3 only if a service is deployed.

## Evidence To Capture

- Completed workflow scorecard.
- Signed no-build or scoped-MVP decision.
- Conditional route/OpenAPI/no-action audit.
- Query latency and bounded-result evidence.
- Service isolation and D+1/D+3 notes if built.
