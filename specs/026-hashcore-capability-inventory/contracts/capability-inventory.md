# Contract: Hashcore Capability Inventory

## Purpose

Define safe discovery, classification and the gate for future Toolkit integrations.

## Inputs

- Installed Toolkit identity.
- Vendor-proven help/version output and documentation.

## Outputs

- Sanitized installation record.
- Complete command classification table.
- Ranked read-only integration candidates or explicit blocked result.

## Failure And Safety Contract

- No unknown or mutating new invocation.
- All calls timeout and use no-window execution.
- No action-template change.

## Compatibility

- Existing reboot/restart flows remain byte/semantically unchanged.
- Future integrations reference inventory and use separate specs.
