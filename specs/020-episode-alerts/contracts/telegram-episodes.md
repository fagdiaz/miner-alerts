# Telegram Contract: Irregular Episodes

## Initial or restart-aware alert

```text
ALERTA DE MINEROS

- 25: OFFLINE | sin respuesta API 4028 | 1 min
  Secuencia: OK -> OFFLINE -> REINICIO -> PLACAS 0/3
  Detalle: /e37
```

Several affected miners appear in the same message. Intermediate restart states update the sequence rather than producing separate alerts.

## Persistent reminder

```text
FALLA PERSISTENTE

- 24: OFFLINE | sin respuesta API 4028 | 10 min
  Secuencia: OK -> OFFLINE
  Detalle: /e33

Proximo aviso segun escalamiento mientras persista.
```

Due miners are grouped. Reminder ages are 5, 10, 15, 30, 60 and 120 minutes, then hourly.

## Recovery

```text
MINEROS RECUPERADOS

- 25: OK | 90.23 TH/s | duracion 2 min
  Secuencia: OK -> OFFLINE -> REINICIO -> PLACAS 0/3 -> LOW -> OK
  Detalle: /e37
```

## Status

```text
STATUS (timestamp)

- 23 (host): 98.00 TH/s
- 24 (host): N/A [OFFLINE]
- 25 (host): 97.87 TH/s [RECUPERANDO] | /e37
- 26 (host): 0.00 TH/s [PLACAS 0/3]
```

The contract forbids a finite positive current rate combined with `[OFFLINE]`.

## Detail commands

- `/event <id>` remains supported.
- `/e<ID>` is the official click-safe alias shown in notifications and event lists.
- Both return the selected incident followed by a bounded, chronological related timeline.

## User-facing state vocabulary

- `OFFLINE`: no API 4028 response.
- `LOW`: API responds but current finite rate is below threshold.
- `PLACAS x/y`: fewer active hashboards than expected; internal state remains `HASHBOARD`.
- `RECUPERANDO`: current signal is healthy but state recovery hysteresis is still being confirmed.
