# Contract: Firmware Evidence Commands

## `/firmware`

Returns the newest bounded warning/critical firmware events across the fleet from SQLite.

## `/firmware all`

Returns the newest bounded firmware events of all severities across the fleet.

## `/firmware <miner>`

Returns recent firmware events for one resolved miner.

## Safety

- Commands never connect to miners.
- Commands never execute Hashcore or change policy/state.
- Empty history returns an explicit collector guidance message.
