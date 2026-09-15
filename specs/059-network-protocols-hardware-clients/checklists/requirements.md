# Requirements Checklist: Spec 059 — Network Protocols & Hardware Clients Extraction (MT-02)

## Baseline & Gates

- [x] Base branch is `codex/022-adaptive-acquisition`.
- [x] Initial regression suite passes (910 tests PASS in 13.197s).
- [x] No changes committed to `app/config.json` or `app/state.json`.

## Requirements Validation

- [x] **R1 (CGMiner 4028 Client)**: `app/network/cgminer_client.py` implements pure socket operations, JSON parsing, and defensive handling for all CGMiner endpoints (`summary`, `stats`, `pools`, `version`).
- [x] **R2 (Hashcore CLI Client)**: `app/network/hashcore_client.py` isolates command generation, subprocess execution, QA guards, and Windows flags (`CREATE_NO_WINDOW = 0x08000000`).
- [x] **R3 (Vnish REST Client)**: `app/network/vnish_client.py` provides typed OOP abstraction over Vnish REST endpoints (`VnishClient`), with context manager lock/unlock and timeout bounds (2.5s).
- [x] **R4 (Backward Compatibility)**: `app/miner_monitor.py` re-exports all extracted symbols with facades maintaining exact parameter signatures and patch intercepts for tests.
- [x] **R5 (Unit Test Coverage)**: `tests/test_network_clients.py` tests all clients with deterministic mocks (18 tests passing).
- [x] **R6 (Regression Invariant)**: 100% of global test suite passes (928/928 tests PASS in 13.166s).
