# Contract: Telegram Messages

## Size

- Every API `text` payload is at most 3900 characters.
- Multi-part output is ordered and labelled `Parte N/M` only when more than one part exists.
- Splitting prefers blank lines, then line boundaries, then a hard safe boundary.

## Commands

- Every recognized command response sets `is_command=true`.
- Command responses are never coalesced or deduplicated.
- Official click-safe actions are `/rb<ID>`, `/reboot_no_ok` and `/c<code>`.

## Notifications

- `ALERTA DE MINEROS`: newly confirmed irregular episodes.
- `FALLA PERSISTENTE`: due reminders only.
- `MINEROS RECUPERADOS`: confirmed closure with bounded sequence.
- `AUTO-REBOOT FAILED`: action failure, never success wording.
- Routine healthy state is not pushed by default.

## Delivery Evidence

- Queue unavailable: unconditional `TG ENQUEUE_FAIL`; command fallback emits `TG FALLBACK_SEND ok|err|exc`.
- HTTP non-success: unconditional `TG SEND_ERR` with redacted bounded body.
- Queue rejection/drop: unconditional type/class/reason log without payload.
