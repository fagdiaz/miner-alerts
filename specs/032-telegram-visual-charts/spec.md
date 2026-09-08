# Feature Specification: Telegram Visual Charts (Spec 032)

**Feature Branch**: `codex/032-telegram-visual-charts`  
**Created**: 2026-09-07  
**Status**: Draft / SpecKit Ready  
**Input**: Telegram Max Initiative (V3 Expansion Plan) — In-memory visual chart generation and native photo delivery (`sendPhoto`) for single miners and fleet overview via `/chart` and inline alert buttons.  
**Risk Class**: LOW-MEDIUM (read-only SQLite queries, in-memory image generation, Telegram photo delivery)  
**Assigned Engine**: **Gemini 3.8 Flash High** (Pure domain logic, data querying, image rendering, and test suites).  

---

## User Scenarios & Testing

### User Story 1 - Instant Visual Inspection of Miner Health (Priority: P1)

An operator taps `[ 📊 Ver Gráfico ]` in an episode alert or types `/chart 23` in Telegram and immediately receives an image with the hashrate, temperature, and threshold curves over the last 60 minutes (or 24 hours).

**Why this priority**: A visual curve conveys trend direction (e.g. sharp drop vs gradual thermal throttle) in 1 second, far faster than reading numerical logs or tables.

**Independent Test**: Query SQLite `telemetry_samples` for miner 23 over the last 60 minutes, generate chart bytes, and verify that a valid PNG stream with width ≥ 800px is produced and sent via `sendPhoto`.

**Acceptance Scenarios**:
1. **Given** telemetry samples exist for `S19JPRO-23`, **When** the operator sends `/chart 23`, **Then** the bot replies with a PNG photo containing hashrate (TH/s), threshold, and temperature (°C) curves.
2. **Given** an episode alert with `[ 📊 Ver Gráfico ]`, **When** tapped, **Then** the callback dispatcher triggers the same `/chart <miner>` generation and sends the photo to the chat.

---

### User Story 2 - Fleet Overview Comparison Chart (Priority: P1)

An operator types `/chart fleet` (or `/chart fleet 24h`) and receives a multi-series chart showing each miner's hashrate alongside the total fleet aggregate.

**Why this priority**: Allows the operator to identify fleet-wide anomalies (e.g. ambient heat wave, power grid dip) in a single glance.

**Independent Test**: Render a fleet chart for all 4 miners across 24 hours and verify multi-line legend, proper scaling, and non-overlapping curves.

**Acceptance Scenarios**:
1. **Given** 4 miners active in the database, **When** `/chart fleet` is executed, **Then** a chart is generated showing each miner in a distinct color and a summary legend.

---

### User Story 3 - In-Memory Generation & Zero Disk Clutter (Priority: P1)

The charting engine renders directly to memory (`io.BytesIO`) and streams the payload to the Telegram `sendPhoto` endpoint without creating temporary files on the host filesystem.

**Why this priority**: Eliminates disk I/O bottlenecks and prevents orphaned file clutter in production.

**Independent Test**: Profile disk operations during 50 consecutive chart renders and assert 0 temporary files created in `data/`, `diagnostics/`, or OS temp directory.

---

### User Story 4 - Empty or Stale Data Protection (Priority: P2)

When an operator queries a non-existent miner (e.g. `/chart 99`) or a miner with zero samples in the requested window, the system responds with a helpful text message rather than crashing or sending a blank canvas.

**Acceptance Scenarios**:
1. **Given** a miner ID that does not exist, **When** `/chart 99` is queried, **Then** the bot replies: `"Minero '99' no encontrado. Mineros disponibles: 23, 24, 25, 26."`.

---

## Requirements

### Functional Requirements

- **FR-001**: System MUST support command syntax:
  - `/chart` -> shows fleet 1h chart.
  - `/chart <miner_id>` -> shows single miner 1h chart.
  - `/chart <miner_id> <hours>` -> shows single miner chart for custom hours (1 to 48).
  - `/chart fleet [hours]` -> shows fleet comparison chart.
- **FR-002**: Charts MUST include:
  - Title with miner name / fleet tag and timestamp window.
  - Hashrate curve (TH/s) with configured threshold reference line.
  - Max temperature curve (°C) on secondary axis or lower subplot.
  - Visual color coding (Green = OK, Orange = LOW / Degradado, Red = Hashboard drop / Offline).
- **FR-003**: System MUST deliver images using Telegram Bot API `sendPhoto` method with multipart/form-data.
- **FR-004**: System MUST wire the `chart:<miner_id>` callback action in `_handle_callback_query` to invoke chart generation and delivery.
- **FR-005**: Chart generation MUST complete in under 1.5 seconds.
- **FR-006**: All image generation MUST be strictly in-memory (`io.BytesIO`).

### Non-Functional & Safety Requirements

- **NFR-001**: All SQLite reads for charting MUST use read-only mode (`?mode=ro`).
- **NFR-002**: The chart generator MUST handle missing or sparse samples without exceptions.
- **NFR-003**: Zero interruption to the running monitor loop PID 38816.

---

## Success Criteria

- **SC-001**: `/chart` and `[ 📊 Ver Gráfico ]` deliver a crisp, readable PNG chart in < 2.0 seconds.
- **SC-002**: 100% of temporary chart data resides in RAM, leaving 0 artifacts on disk.
- **SC-003**: 100% unit test coverage for data extraction and image encoding with 0 regressions across existing 430 tests.
