# Miner Diagnostics Snapshot

- Generated: 2026-07-21T00:41:34+00:00
- Config: F:\02-ASIC - mineros\miner-alerts\app\config.json
- Dry run: False
- Miners: 4

## Miner Summary

| Miner | Host | Status | TH/s | Boards | Temps C | Firmware | Power Fields | Action Hint |
| --- | --- | --- | ---: | ---: | --- | --- | --- | --- |
| S19JPRO-23 | 192.168.100.23:4028 | RESPONDED | 99.355 | 3 | 62.0, 67.0, 77.0, 82.0 | unknown | 6 | observe: power telemetry fields available for correlation |
| S19JPRO-24 | 192.168.100.24:4028 | RESPONDED | 97.938 | 3 | 60.0, 62.0, 67.0, 75.0, 77.0, 82.0 | unknown | 6 | observe: power telemetry fields available for correlation |
| S19JPRO-25 | 192.168.100.25:4028 | RESPONDED | 92.319 | 3 | 56.0, 58.0, 59.0, 71.0, 73.0, 74.0 | unknown | 6 | observe: power telemetry fields available for correlation |
| S19JPRO-26 | 192.168.100.26:4028 | RESPONDED | 100.613 | 3 | 61.0, 62.0, 76.0, 77.0 | unknown | 6 | observe: power telemetry fields available for correlation |

## Notes

- This report is read-only evidence. It does not reboot, restart, tune, or write miner state.
- Power fields are firmware-exposed hints only. AC input voltage requires PSU/PDU/UPS evidence unless the firmware exposes it explicitly.
- Use repeated snapshots before changing reboot policy.
