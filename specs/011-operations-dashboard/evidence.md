# Evidence: Read-Only Operations Dashboard

**Status**: Implementation and local validation complete
**Service activation**: Not required; the generator is standalone.

## Validation

### Test-First Evidence

The targeted suite initially failed with `ModuleNotFoundError` for
`tools.operations_dashboard`. After implementation:

```powershell
& ".\.venv\Scripts\python.exe" -m unittest tests.test_operations_dashboard -v
```

Result: PASS, 5 targeted tests covering bounded view-model generation, HTML
escaping, read-only enforcement, empty-store output, and the absence of monitor,
network, subprocess, or mutating SQL paths.

### Fixture Smoke

A representative four-miner SQLite fixture generated:

```text
diagnostics/dashboard-qa/index.html
```

Result: PASS, self-contained HTML, 10,627 bytes. The fixture and output are under
ignored `diagnostics/` paths. The production `data/miner_alerts.db` does not exist
yet because the running service has not loaded the SQLite feature branch.

### Visual Validation

Automated browser navigation to the local `file://` artifact was blocked by the
browser security policy. No workaround was attempted. Manual desktop/mobile
opening remains explicitly unverified until the generated artifact is opened by
the operator or served through an approved local-only mechanism.

### Safety

- SQLite opens with URI `mode=ro`; a test proves DDL raises `OperationalError`.
- All persisted text is HTML escaped.
- No JavaScript, CDN, remote font, API request, monitor import, Telegram config,
  miner connection, or Hashcore path exists in the generator.
- Queries and output rows are bounded; trends retain newest samples.
- `data/`, `diagnostics/`, SQLite sidecars, and generated HTML remain ignored.

### Final Gates

- `py_compile` for `app/miner_monitor.py` and `tools/operations_dashboard.py`:
  PASS.
- Full test suite: PASS, 56 tests.
- Docker image build (`miner-alerts-dashboard:qa`): PASS.
- Docker generation against the ignored fixture: PASS, 10,493-byte HTML.
- `git diff --check`: PASS.
- Speckit QA preflight with builds: PASS, checklist 7/7.
- Windows service restart: not required and not performed.
