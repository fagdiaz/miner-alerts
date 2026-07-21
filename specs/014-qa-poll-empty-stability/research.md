# Research: QA Poll-Empty Stability

## Finding

The empty-batch branch is outside every command branch. Its nested QA log interpolates `action` and `cmd_start`, both assigned only in selected command branches. On a fresh idle worker these names are unbound and the surrounding broad exception handler converts the programming error into Telegram polling backoff.

## Decision

Delete the misplaced duration log and retain the existing `POLL_EMPTY` diagnostic.

## Rationale

There is no command to time in an empty batch. Removing the statement restores the intended idle path without introducing state or changing the polling algorithm.

## Alternatives Considered

- Initialize dummy values before every poll: rejected because it would hide a scope defect and emit a false command-duration event.
- Move the log elsewhere: rejected because actual confirm branches already own their command replies and the scope of this fix is the empty path.
- Integration-test live Telegram polling: deferred to final runtime rollout; a deterministic source test directly captures this regression without a second bot consumer.
