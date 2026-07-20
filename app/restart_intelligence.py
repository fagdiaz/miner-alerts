from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RestartClassification:
    classification: str
    severity: str
    restart_reason: str
    action_source: Optional[str]
    action_ts: Optional[float]
    action_age_seconds: Optional[float]


def classify_restart(
    *,
    restart_reason: str,
    detected_ts: float,
    last_manual_action_ts: Optional[float],
    last_auto_action_ts: Optional[float],
    attribution_window_seconds: int,
    skew_tolerance_seconds: int = 10,
) -> RestartClassification:
    candidates: list[tuple[float, str]] = []
    for action_source, action_ts in (
        ("manual", last_manual_action_ts),
        ("auto", last_auto_action_ts),
    ):
        if action_ts is None:
            continue
        action_value = float(action_ts)
        if action_value > detected_ts + skew_tolerance_seconds:
            continue
        action_age = max(0.0, detected_ts - action_value)
        if action_age <= attribution_window_seconds:
            candidates.append((action_value, action_source))

    if not candidates:
        return RestartClassification(
            classification="unexpected",
            severity="critical",
            restart_reason=restart_reason,
            action_source=None,
            action_ts=None,
            action_age_seconds=None,
        )

    action_ts, action_source = max(candidates, key=lambda item: item[0])
    return RestartClassification(
        classification=f"expected_{action_source}",
        severity="info",
        restart_reason=restart_reason,
        action_source=action_source,
        action_ts=action_ts,
        action_age_seconds=max(0.0, detected_ts - action_ts),
    )
