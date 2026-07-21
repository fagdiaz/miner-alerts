# Research: Vnish Operations Automation

## Tail Defect Evidence

The deployed WebSocket replays chronological history. The v1 parser stopped at
`max_events`, therefore large buffers retained old recognized events. Isolated
smoke evidence showed one miner capped in October 2025 despite later source data.
The parser must inspect the newest bounded lines and keep the newest events.

## Scheduling Decision

Use Windows ScheduledTasks because the production monitor and Hashcore Toolkit
are native Windows processes. `New-ScheduledTaskTrigger` supports repetition,
and `New-ScheduledTaskSettingsSet` supports `MultipleInstances IgnoreNew` on the
installed host. This avoids a permanent monitor thread and new runtime service.

## Timestamp Decision

Vnish emits wall-clock text without timezone. Parse known timestamps using either
an explicit fixed UTC offset or the collector host local timezone and persist the
clock provenance. Diagnosis remains advisory and excludes events outside its
window; no policy consumes this timestamp.
