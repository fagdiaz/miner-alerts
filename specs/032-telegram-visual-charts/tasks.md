# Tasks: Telegram Visual Charts (Spec 032)

**Input**: Design artifacts from `specs/032-telegram-visual-charts/`  
**Risk**: LOW-MEDIUM  
**Assigned Engine**: **Gemini 3.8 Flash High** (All Phases)  

---

## Phase 1: Baseline And Red Contracts

- [x] T001 Record baseline command registry and schema in `specs/032-telegram-visual-charts/evidence.md`.
- [x] T002 [P] Add failing tests for single miner data querying and PNG binary header validation in `tests/test_telegram_charts.py`.
- [x] T003 [P] Add failing tests for fleet data querying and PNG binary header validation in `tests/test_telegram_charts.py`.
- [x] T004 [P] Add failing tests for empty dataset or unknown miner fallback in `tests/test_telegram_charts.py`.

---

## Phase 2: Pure Charting Engine Implementation

- [x] T005 Implement `fetch_miner_chart_data` and `fetch_fleet_chart_data` in `app/telegram_charts.py` using read-only SQLite.
- [x] T006 Implement `render_miner_chart_png` and `render_fleet_chart_png` in `app/telegram_charts.py` using `matplotlib` with dark theme.
- [x] T007 Verify all tests in `tests/test_telegram_charts.py` pass.

---

## Phase 3: Monitor & Telegram Dispatcher Integration

- [x] T008 Implement `send_telegram_photo()` multipart HTTP helper in `app/miner_monitor.py`.
- [x] T009 Register `/chart [miner|fleet] [hours]` in the command index, aliases, and dispatcher in `app/miner_monitor.py`.
- [x] T010 Wire the `chart:<miner_id>` callback action in `_handle_callback_query()` to generate and send photo.

---

## Phase 4: Validation & Release

- [x] T011 Run full test suite regression (all 430+ tests) with zero failures.
- [x] T012 Verify Python syntax with `py_compile app/miner_monitor.py app/telegram_charts.py`.
- [x] T013 Record execution and image evidence in `specs/032-telegram-visual-charts/evidence.md`.
- [x] T014 Update `README.md`, `docs/speckit/RUNBOOK.md`, `docs/audit/DEVELOPMENT_LOG.md`, and `docs/speckit/ROADMAP.md`.

---

## Definition Of Done

- [x] `/chart <id>` and `/chart fleet` deliver valid PNG charts.
- [x] Inline button `[ 📊 Ver Gráfico ]` delivers photo in Telegram.
- [x] In-memory rendering leaves 0 temporary files on disk.
- [x] All unit tests pass with zero regressions.
- [x] Production process PID 38816 remains undisturbed.
