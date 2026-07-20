# Telegram Contract: Reboot Diagnosis

## `/why`

Returns the latest recorded auto-reboot decision across configured miners.

## `/why <miner>`

Resolves the miner using the existing name/display-name rules and returns its
latest decision. The response contains:

- time and miner;
- policy result (`blocked_by` or action outcome);
- state, rate, threshold, and LOW duration when known;
- board, temperature, voltage, consumption, frequency, HW-error, and fan evidence when known;
- cooldown/window context when relevant;
- explicit note that chain voltage is not AC input voltage.

## Deterministic Errors

- Missing history: `No hay decisiones de auto-reboot registradas.`
- Unknown miner: existing miner-not-found wording.
- Store disabled/unavailable: `Diagnostico historico temporalmente no disponible.`

## Safety Contract

- Commands read SQLite only.
- No ASIC API, Hashcore, reboot, restart, or configuration write is permitted.
- Replies use `is_command=True` and existing Telegram delivery diagnostics.
