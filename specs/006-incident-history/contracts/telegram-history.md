# Telegram History Contract

All commands are read-only, deterministic, and use command-delivery semantics.
They never call ASIC API 4028 or Hashcore Toolkit.

## `/events`

Returns up to the latest eight operational events, newest first.

```text
EVENTOS RECIENTES

#42 20/07 14:31 23 REINICIO INESPERADO
#41 20/07 14:29 23 OK -> LOW

Detalle: /event <id>
```

No data:

```text
No hay eventos registrados.
```

Store unavailable:

```text
Historial no disponible.
```

## `/events <miner>`

Uses the same stable miner resolution semantics as existing commands, then filters
by the resolved miner key. Unknown miner:

```text
Miner no encontrado.
```

## `/event <id>`

Returns one normalized event. Restart example:

```text
INCIDENTE #42

Miner: 23
Tipo: reinicio detectado
Clasificacion: inesperado
Evidencia uptime: 86400s -> 120s
Estado: OK | 99.20 TH/s
Fecha: 20/07/2026 14:31:00
```

Invalid usage:

```text
Uso: /event <id>
```

Unknown identifier:

```text
Evento no encontrado.
```

## Dedicated Unexpected-Restart Notification

```text
REINICIO NO ESPERADO

Miner: 23
Evidencia uptime: 86400s -> 120s
Estado actual: OK | 99.20 TH/s
Accion relacionada: ninguna en los ultimos 15 min
Incidente: #42
Detalle: /event 42
```

This notification is independent of state-change timing and never triggers an
action.
