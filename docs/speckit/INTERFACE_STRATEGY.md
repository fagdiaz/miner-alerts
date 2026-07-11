# Interface Strategy

## Current Control Surface

Telegram is the correct primary control surface today because it is already
integrated, remote-friendly, and supports confirmation flows for dangerous
actions. It should remain the only write/control interface until a separate UI
has authentication, local binding, confirmation, and audit logs.

## Why Consider A Separate Interface

Telegram is good for commands and alerts, but weak for analysis:

- It is not ideal for comparing miners side by side.
- It does not show timelines well.
- It is hard to inspect Vnish logs, repeated LOW events, and blocked reboot reasons.
- It is hard to visualize "sweet spot" stability over hours or days.

## Recommended Path

### Phase 1 - Read-Only Local Report

Generate a local HTML or Markdown report from existing state/logs.

Scope:

- Current miner state.
- Last seen timestamp.
- Last alert and last state transition.
- Last manual/auto reboot.
- Recent blocked_by reasons.
- Hashcore enabled/status.

Risk: low. No auth required if it is a local file and contains no secrets.

### Phase 2 - Local Read-Only Dashboard

Run a local-only dashboard bound to `127.0.0.1`.

Scope:

- Miner cards.
- Timeline of alerts, LOW/OK transitions, reboot attempts, Vnish events.
- Per-miner diagnostics view.
- Export sanitized evidence for specs.

Risk: medium. Must avoid exposing secrets, tokens, or action buttons.

### Phase 3 - Controlled Actions UI

Only after Phase 2 is stable.

Requirements:

- Local-only binding or explicit auth.
- Reboot/restart confirmation with short TTL.
- Full audit log.
- Same guardrails as Telegram.
- No bypass of QA mode or `qa_allow_real_actions`.

## Decision

Do not build a full web app first. Start with read-only reporting and diagnostics.
Telegram remains the action interface.
