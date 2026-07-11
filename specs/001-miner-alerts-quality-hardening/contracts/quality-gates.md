# Quality Gates

## Required For Code Changes

- `py_compile` passes.
- Affected Telegram commands are tested when Telegram behavior changes.
- Auto-reboot changes include QA-mode blocked validation.
- Evidence is recorded in `evidence.md`.

## Required For Documentation Changes

- No secrets are introduced.
- Windows commands are valid for PowerShell.
- Docs point to `app/config.example.json` for examples, not real config.
