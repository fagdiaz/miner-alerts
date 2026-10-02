# Miner Diagnostics Snapshot

- Generated: 2026-07-21T00:39:25+00:00
- Config: F:\02-ASIC - mineros\miner-alerts\app\config.json
- Dry run: False
- Miners: 4

## Miner Summary

| Miner | Host | Status | TH/s | Boards | Temps C | Firmware | Power Fields | Action Hint |
| --- | --- | --- | ---: | ---: | --- | --- | --- | --- |
| S19JPRO-23 | 192.168.100.23:4028 | NO_RESPONSE | N/A | N/A | N/A | unknown | 0 | observe: no response, avoid reboot until signal source is confirmed |
| S19JPRO-24 | 192.168.100.24:4028 | NO_RESPONSE | N/A | N/A | N/A | unknown | 0 | observe: no response, avoid reboot until signal source is confirmed |
| S19JPRO-25 | 192.168.100.25:4028 | NO_RESPONSE | N/A | N/A | N/A | unknown | 0 | observe: no response, avoid reboot until signal source is confirmed |
| S19JPRO-26 | 192.168.100.26:4028 | NO_RESPONSE | N/A | N/A | N/A | unknown | 0 | observe: no response, avoid reboot until signal source is confirmed |

## Notes

- This report is read-only evidence. It does not reboot, restart, tune, or write miner state.
- Power fields are firmware-exposed hints only. AC input voltage requires PSU/PDU/UPS evidence unless the firmware exposes it explicitly.
- Use repeated snapshots before changing reboot policy.
