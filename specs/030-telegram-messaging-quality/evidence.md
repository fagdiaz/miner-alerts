# Evidence: Telegram Messaging Quality

## Runtime Baseline - 2026-08-13

- Spec 020 was closed before this feature began.
- Authorized Telegram runtime smoke passed for `/status`, `/events`, `/e531`
  and `/help` after credential rotation and service restart.
- The observed help response lists read-only and manual commands but omits the
  official click-safe `/rb<ID>`, `/reboot_no_ok` and `/c<code>` paths.
- Episode messages already group miners, show persistent ages and render a
  bounded sequence plus `/e<ID>`; this cadence is an invariant, not a rewrite.
- Source inventory contains 58 `send_telegram` call sites: 50 explicit command
  responses and eight automatic notifications. Command paths currently set
  `is_command=true`; automatic paths keep notification dedupe semantics.
- Current sender rejects oversized text only at Telegram HTTP time and the
  full-queue path discards the oldest queued item without delivery-class
  awareness. These are the primary delivery contracts to harden.

## Validation

### Test-First And Invariants

- Red contracts initially failed because `app/telegram_messages.py` did not
  exist; implementation then made the same contracts pass.
- Targeted messaging, episode and notification suites: 26/26 PASS.
- Full suite: 129/129 PASS. This includes auto-reboot signal gates, thermal,
  fleet and firmware interlocks, startup/state invariants, Hashcore QA block,
  episode cadence and Telegram polling stability.
- Command wiring AST contract found more than 30 command reply calls and zero
  missing `is_command=true` arguments. STARTUP, EPISODE_ALERT and STATE_CHANGE
  remain outside command delivery.

### Static Gates

- `py_compile` for `app/miner_monitor.py`, `app/telegram_messages.py` and
  `app/alert_episodes.py`: PASS.
- `app/config.example.json`: valid JSON.
- Top-level AST: 56 symbols, zero duplicate definitions.
- Tracked secret scan: zero Telegram-token-shaped values.
- `git diff --check`: PASS.
- Ignore proof covers `app/config.json`, `app/state.json`, `*.log`,
  `__pycache__`, `.pyright` and `.mypy_cache`.
- Speckit QA preflight: PASS, requirements 16/16, Python build PASS.

### Delivery Scenarios Without Real Actions

- Oversized response reconstructs exactly from ordered parts, each at most
  3900 characters.
- Normal queue admission preserves `part_index` order and the complete original
  content for a two-part command response.
- A command presented to a full queue performs one bounded direct POST with
  timeout `(1.5, 4.0)` and leaves the queued item intact.
- A full-queue STARTUP is rejected without eviction and emits
  `TG QUEUE_DROP` without payload content.
- A full-queue critical notification also cannot evict an already admitted
  command; the incoming notification is rejected with explicit class/type.
- No test invoked a real miner action; existing QA Hashcore block remains PASS.

### Runtime Activation

- A single read-only `/help` renderer smoke was sent through the new bounded
  queue-unavailable fallback without starting a monitor. Telegram returned
  HTTP 200 in 2588 ms and the authorized Web client displayed the complete
  1045-character index with monitoring/actions/system sections and official
  `/rb<ID>`, `/reboot_no_ok`, `/c<code>` references.
- The first sandboxed attempt was denied by local socket policy and emitted an
  unconditional redacted `TG FALLBACK_SEND exc`; the approved network attempt
  emitted `TG FALLBACK_SEND ok`. No token or payload was logged.
- Two non-interactive elevated attempts timed out waiting for Windows UAC and
  left the previous service untouched. A later visible UAC-approved restart
  completed once: NSSM PID changed `36380 -> 32796` and monitor PID `36396`
  acquired the single global mutex at `2026-08-13 15:09:02`.
- The activated process loaded the expected script/config hash `14955dc1`,
  `qa_mode=false`, `qa_allow_real_actions=false`, startup guard 600 seconds,
  all three conservative interlocks and EventStore schema 5.
- The authorized Telegram client observed the new STARTUP and successful
  responses for `/help`, `/help reboot_no_ok`, `/status` and `/events`.
  `/status` reported all four miners healthy at 77.25-85.38 TH/s. The detailed
  help included the official underscore command, `/c<code>`, TTL and restart
  warning. Three back-to-back command replies arrived without loss.
- No post-start traceback, Telegram delivery error, Hashcore call or immediate
  auto-reboot was present in the inspected startup block.
- Spec 030 runtime activation is complete. Commit and push remain intentionally
  unperformed because they were not requested in this iteration.
