# Miner Diagnostics Snapshot

- Generated: 2026-07-11T16:45:39+00:00
- Config: F:\02-ASIC - mineros\miner-alerts\app\config.example.json
- Dry run: True
- Miners: 4

## Miner Summary

| Miner | Host | Status | TH/s | Boards | Temps C | Firmware | Power Fields | Action Hint |
| --- | --- | --- | ---: | ---: | --- | --- | --- | --- |
| S19JPRO-1 | 192.168.1.101:4028 | SKIPPED_DRY_RUN | N/A | N/A | N/A | unknown | 0 | dry-run only |
| S19JPRO-2 | 192.168.1.102:4028 | SKIPPED_DRY_RUN | N/A | N/A | N/A | unknown | 0 | dry-run only |
| S19JPRO-3 | 192.168.1.103:4028 | SKIPPED_DRY_RUN | N/A | N/A | N/A | unknown | 0 | dry-run only |
| S19JPRO-4 | 192.168.1.104:4028 | SKIPPED_DRY_RUN | N/A | N/A | N/A | unknown | 0 | dry-run only |

## Notes

- This report is read-only evidence. It does not reboot, restart, tune, or write miner state.
- Power fields are firmware-exposed hints only. AC input voltage requires PSU/PDU/UPS evidence unless the firmware exposes it explicitly.
- Use repeated snapshots before changing reboot policy.
