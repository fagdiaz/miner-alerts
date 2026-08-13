# Research: Electrical Source Discovery

## Baseline Findings

- Current API 4028 voltage-like fields are board/chain-side measurements.
- SNMPv3 provides authentication/privacy models suitable for management telemetry.
- Modbus TCP requires a vendor register map and read-only function discipline.
- MQTT is publish/subscribe and only useful when a real source already publishes.

## Decisions

1. Separate physical-source discovery from adapter implementation.
2. Require direct measurement documentation before naming a metric AC voltage.
3. Select at most one first adapter based on reliability and access.
4. Keep all electrical conclusions advisory in this program.

## Rejected Or Deferred Alternatives

- Inferring mains voltage from hashrate, temperatures or chain voltage.
- Adding an MQTT broker without a publisher.
- Generic Modbus register scanning because it can be unsafe and ambiguous.
- PDU outlet control because it is a new dangerous action surface.

## External Validation Sources

- Modbus specifications: https://www.modbus.org/modbus-specifications
- SNMPv3 USM: https://www.rfc-editor.org/info/rfc3414/
- MQTT 5.0: https://docs.oasis-open.org/mqtt/mqtt/v5.0/mqtt-v5.0.html
