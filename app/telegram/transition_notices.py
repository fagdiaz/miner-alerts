"""Notification-only flap limiter, owned by the single DetectionHook loop."""

from dataclasses import dataclass, field


@dataclass
class TransitionNotices:
    notified: dict[str, float] = field(default_factory=dict)

    def allow(self, state: str, now_ts: float) -> bool:
        if state == "OK":
            self.notified.clear()
            return True
        if state not in ("LOW", "HASHBOARD"):
            return True
        previous = self.notified.get(state)
        if previous is not None and 0 <= now_ts - previous < 300:
            return False
        self.notified[state] = now_ts
        return True
