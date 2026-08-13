# Research: Telegram Messaging Quality

## Decision 1 - Keep plain Bot API text

**Decision**: Continue with `requests` plus long polling and plain text.

**Rationale**: The current transport is stable, dependency-free and already has command delivery hardening. Message quality does not require callbacks, webhooks or a framework.

**Alternatives considered**: Inline keyboards, callback queries, `python-telegram-bot`, webhooks. Rejected for this feature because they expand routing and deployment risk without solving the observed message problems.

## Decision 2 - Bound messages before enqueue

**Decision**: Split oversized text deterministically below the 4096-character platform limit, preferring paragraph then line boundaries.

**Rationale**: `/diagnose`, event timelines and future grouped incidents can exceed the platform limit and currently fail as one HTTP request.

**Alternatives considered**: Truncation loses evidence; document attachments reduce mobile readability.

## Decision 3 - Preserve episode cadence

**Decision**: Keep the Spec 020 grouping window and reminder ages byte-for-byte in behavior.

**Rationale**: Runtime evidence shows the current cadence fixes forgotten outages without per-tick spam.

## Decision 4 - Official click-safe syntax only in help

**Decision**: Promote `/rb<ID>`, `/reboot_no_ok`, `/c<code>` and `/confirm ...`; accept but do not advertise legacy aliases.

**Rationale**: Telegram tokenization can truncate hyphenated or spaced CTAs when tapped.

## Decision 5 - No automatic retry

**Decision**: Keep no-retry delivery, but make every rejection/failure explicit and prevent command responses from entering notification dedupe.

**Rationale**: Automatic retry can duplicate dangerous confirmation/action messages. Explicit evidence is safer.
