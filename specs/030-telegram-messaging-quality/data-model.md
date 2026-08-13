# Data Model: Telegram Messaging Quality

## MessageEnvelope

- `text`: normalized user-facing text
- `message_type`: stable operational type
- `reason`: bounded diagnostic reason
- `delivery_class`: `command`, `critical`, `notification`, or `informational`
- `is_command`: command-response bypass flag
- `update_id`: optional inbound correlation
- `command_name`: optional normalized command
- `performance_context`: optional existing timing context

## MessagePart

- `part_index`: zero-based order
- `part_count`: total fragments
- `text`: bounded fragment
- `envelope_metadata`: unchanged parent metadata

**Invariant**: Joining part payloads in order preserves the complete semantic content.

## CommandMetadata

- `name`
- `summary`
- `usage`
- `danger_level`
- `aliases`
- `official_click_safe_aliases`
- `enabled`

**Invariant**: Displayed commands must resolve through the parser/dispatcher.

## DeliveryOutcome

- `status`: `enqueued`, `sent`, `rejected`, `dropped`, or `failed`
- `message_type`
- `delivery_class`
- `update_id`
- `reason`
- `http_status`: optional
- `duration_ms`: optional

**Invariant**: No credential or message payload is persisted in outcome logs.
