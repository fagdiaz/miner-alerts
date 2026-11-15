"""Bounded, detection-loop-owned correlation. Observes events; never actuates."""
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass
class RestartCorrelation:
    recent: Dict[str, float] = field(default_factory=dict)
    notified: Dict[str, float] = field(default_factory=dict)

    def observe(self, miners: List[dict], unexpected: List[str], now: float,
                window_seconds: float = 45.0, cooldown_seconds: float = 900.0
                ) -> List[Tuple[str, List[str]]]:
        groups: Dict[str, List[str]] = {}
        for miner in miners:
            group = miner.get("electrical_group")
            if group:
                groups.setdefault(str(group), []).append(str(miner["name"]))
        known = {name for members in groups.values() for name in members}
        self.recent = {name: ts for name, ts in self.recent.items()
                       if name in known and 0 <= now - ts <= window_seconds}
        self.notified = {group: ts for group, ts in self.notified.items() if group in groups}
        for name in unexpected:
            if name in known:
                self.recent[name] = now
        result = []
        for group, members in groups.items():
            if len(members) < 2 or not any(name in unexpected for name in members):
                continue
            if not all(name in self.recent for name in members):
                continue
            last = self.notified.get(group)
            if last is not None and now - last < cooldown_seconds:
                continue
            self.notified[group] = now
            result.append((group, members))
        return result
