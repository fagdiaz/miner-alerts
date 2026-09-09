import math
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional


STATE_OK = "OK"
STATE_LOW = "LOW"
STATE_OFFLINE = "OFFLINE"
STATE_HASHBOARD = "HASHBOARD"
IRREGULAR_STATES = frozenset((STATE_LOW, STATE_OFFLINE, STATE_HASHBOARD))


def _safe_rate(value: Any) -> Optional[float]:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def _format_rate(value: Any) -> str:
    numeric = _safe_rate(value)
    return f"{numeric:.2f} TH/s" if numeric is not None else "N/A"


def _state_label(
    state: str,
    *,
    active_boards: Optional[int],
    expected_boards: int,
) -> str:
    if state == STATE_HASHBOARD:
        active = active_boards if active_boards is not None else "N/A"
        return f"PLACAS {active}/{expected_boards}"
    return state


def _state_evidence(
    state: str,
    *,
    responded: bool,
    rate_ths: Any,
    threshold_ths: float,
    active_boards: Optional[int],
    expected_boards: int,
) -> str:
    if state == STATE_OFFLINE or not responded:
        return "sin respuesta API 4028"
    if state == STATE_HASHBOARD:
        active = active_boards if active_boards is not None else "N/A"
        return f"placas activas {active}/{expected_boards}; {_format_rate(rate_ths)}"
    if state == STATE_LOW:
        return f"{_format_rate(rate_ths)} < {float(threshold_ths):.2f} TH/s"
    return _format_rate(rate_ths)


@dataclass
class EpisodeStep:
    occurred_ts: float
    kind: str
    label: str
    evidence: str = ""
    event_id: Optional[int] = None


@dataclass
class IrregularEpisode:
    miner_key: str
    name_display: str
    host: str
    started_ts: float
    current_state: str
    responded: bool
    rate_ths: Optional[float]
    threshold_ths: float
    active_boards: Optional[int]
    expected_boards: int
    initial_due_ts: float
    history: list[EpisodeStep] = field(default_factory=list)
    detail_event_id: Optional[int] = None
    restart_event_ids: list[int] = field(default_factory=list)
    initial_notice_sent: bool = False
    update_due_ts: Optional[float] = None
    reminder_index: int = 0
    repeat_index: int = 1
    closed_ts: Optional[float] = None
    recovery_due_ts: Optional[float] = None
    max_history_steps: int = 12

    def add_step(
        self,
        *,
        occurred_ts: float,
        kind: str,
        label: str,
        evidence: str = "",
        event_id: Optional[int] = None,
    ) -> None:
        step = EpisodeStep(
            occurred_ts=float(occurred_ts),
            kind=str(kind),
            label=str(label),
            evidence=str(evidence),
            event_id=int(event_id) if event_id is not None else None,
        )
        if self.history and self.history[-1].kind == step.kind and self.history[-1].label == step.label:
            self.history[-1] = step
        else:
            self.history.append(step)
        while len(self.history) > max(2, int(self.max_history_steps)):
            # Preserve the initial baseline and the most recent evidence.
            self.history.pop(1)

    @property
    def sequence(self) -> str:
        return " -> ".join(step.label for step in self.history)

    @property
    def restart_step(self) -> Optional[EpisodeStep]:
        for step in reversed(self.history):
            if step.kind == "restart":
                return step
        return None


@dataclass
class EpisodeNotificationBatch:
    opened: list[IrregularEpisode] = field(default_factory=list)
    persistent: list[IrregularEpisode] = field(default_factory=list)
    recovered: list[IrregularEpisode] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not (self.opened or self.persistent or self.recovered)


class IrregularEpisodeCoordinator:
    def __init__(
        self,
        *,
        coalesce_seconds: float,
        reminder_schedule_seconds: Iterable[float],
        steady_repeat_seconds: float,
        max_history_steps: int = 12,
    ) -> None:
        self.coalesce_seconds = max(0.0, float(coalesce_seconds))
        schedule = sorted(
            {
                max(1.0, float(value))
                for value in reminder_schedule_seconds
            }
        )
        self.reminder_schedule_seconds = tuple(schedule or (300.0,))
        self.steady_repeat_seconds = max(60.0, float(steady_repeat_seconds))
        self.max_history_steps = max(4, int(max_history_steps))
        self.active: dict[str, IrregularEpisode] = {}
        self._recovered: list[IrregularEpisode] = []

    def _new_episode(
        self,
        *,
        miner_key: str,
        name_display: str,
        host: str,
        previous_state: str,
        state: str,
        responded: bool,
        rate_ths: Any,
        threshold_ths: float,
        active_boards: Optional[int],
        expected_boards: int,
        now_ts: float,
        transition_event_id: Optional[int],
        defer_current_state: bool = False,
    ) -> IrregularEpisode:
        episode = IrregularEpisode(
            miner_key=str(miner_key),
            name_display=str(name_display),
            host=str(host),
            started_ts=float(now_ts),
            current_state=str(state),
            responded=bool(responded),
            rate_ths=_safe_rate(rate_ths),
            threshold_ths=float(threshold_ths),
            active_boards=active_boards,
            expected_boards=int(expected_boards),
            initial_due_ts=float(now_ts) + self.coalesce_seconds,
            detail_event_id=transition_event_id,
            max_history_steps=self.max_history_steps,
        )
        if previous_state and previous_state != state:
            episode.add_step(
                occurred_ts=now_ts,
                kind="state",
                label=_state_label(
                    previous_state,
                    active_boards=None,
                    expected_boards=expected_boards,
                ),
            )
        if not defer_current_state:
            episode.add_step(
                occurred_ts=now_ts,
                kind="state",
                label=_state_label(
                    state,
                    active_boards=active_boards,
                    expected_boards=expected_boards,
                ),
                evidence=_state_evidence(
                    state,
                    responded=responded,
                    rate_ths=rate_ths,
                    threshold_ths=threshold_ths,
                    active_boards=active_boards,
                    expected_boards=expected_boards,
                ),
                event_id=transition_event_id,
            )
        self.active[miner_key] = episode
        return episode

    def observe(
        self,
        *,
        miner_key: str,
        name_display: str,
        host: str,
        previous_state: str,
        state: str,
        responded: bool,
        rate_ths: Any,
        threshold_ths: float,
        active_boards: Optional[int],
        expected_boards: int,
        now_ts: float,
        transition_event_id: Optional[int] = None,
        restart: Optional[dict[str, Any]] = None,
    ) -> Optional[IrregularEpisode]:
        episode = self.active.get(miner_key)
        should_open = state in IRREGULAR_STATES or restart is not None
        if episode is None and not should_open:
            return None
        if episode is None:
            episode = self._new_episode(
                miner_key=miner_key,
                name_display=name_display,
                host=host,
                previous_state=previous_state,
                state=state,
                responded=responded,
                rate_ths=rate_ths,
                threshold_ths=threshold_ths,
                active_boards=active_boards,
                expected_boards=expected_boards,
                now_ts=now_ts,
                transition_event_id=transition_event_id,
                defer_current_state=restart is not None,
            )
        else:
            episode.name_display = str(name_display)
            episode.host = str(host)
            episode.current_state = str(state)
            episode.responded = bool(responded)
            episode.rate_ths = _safe_rate(rate_ths)
            episode.threshold_ths = float(threshold_ths)
            episode.active_boards = active_boards
            episode.expected_boards = int(expected_boards)

        if restart is not None:
            restart_event_id = restart.get("event_id")
            if restart_event_id is not None:
                normalized_id = int(restart_event_id)
                if normalized_id not in episode.restart_event_ids:
                    episode.restart_event_ids.append(normalized_id)
                episode.detail_event_id = normalized_id
            classification = str(restart.get("classification") or "unexpected")
            previous_elapsed = restart.get("previous_elapsed")
            current_elapsed = restart.get("current_elapsed")
            if classification == "unexpected":
                attribution = "sin accion atribuida"
            elif classification == "expected_manual":
                attribution = "accion manual atribuida"
            elif classification == "expected_auto":
                attribution = "accion automatica atribuida"
            else:
                attribution = classification
            uptime = ""
            if previous_elapsed is not None and current_elapsed is not None:
                uptime = f"; uptime {previous_elapsed}s -> {current_elapsed}s"
            episode.add_step(
                occurred_ts=now_ts,
                kind="restart",
                label="REINICIO",
                evidence=f"{attribution}{uptime}",
                event_id=restart_event_id,
            )
            if episode.initial_notice_sent:
                episode.update_due_ts = float(now_ts) + self.coalesce_seconds

        current_label = _state_label(
            state,
            active_boards=active_boards,
            expected_boards=expected_boards,
        )
        last_label = episode.history[-1].label if episode.history else None
        if current_label != last_label:
            episode.add_step(
                occurred_ts=now_ts,
                kind="state",
                label=current_label,
                evidence=_state_evidence(
                    state,
                    responded=responded,
                    rate_ths=rate_ths,
                    threshold_ths=threshold_ths,
                    active_boards=active_boards,
                    expected_boards=expected_boards,
                ),
                event_id=transition_event_id,
            )
        elif transition_event_id is not None:
            episode.history[-1].event_id = int(transition_event_id)

        if episode.detail_event_id is None and transition_event_id is not None:
            episode.detail_event_id = int(transition_event_id)

        if state == STATE_OK:
            episode.closed_ts = float(now_ts)
            episode.recovery_due_ts = max(
                episode.initial_due_ts,
                float(now_ts) + (self.coalesce_seconds if episode.initial_notice_sent else 0.0),
            )
            self.active.pop(miner_key, None)
            self._recovered.append(episode)
        return episode

    def acknowledge_active_initials(self) -> None:
        for episode in self.active.values():
            episode.initial_notice_sent = True

    def detail_event_id(self, miner_key: str) -> Optional[int]:
        episode = self.active.get(miner_key)
        return episode.detail_event_id if episode is not None else None

    def _advance_missed_schedule(self, episode: IrregularEpisode, age: float) -> None:
        while (
            episode.reminder_index < len(self.reminder_schedule_seconds)
            and age >= self.reminder_schedule_seconds[episode.reminder_index]
        ):
            episode.reminder_index += 1

    def _next_reminder_due_ts(
        self,
        episode: IrregularEpisode,
    ) -> Optional[float]:
        if not episode.initial_notice_sent or episode.update_due_ts is not None:
            return None
        if episode.reminder_index < len(self.reminder_schedule_seconds):
            return (
                episode.started_ts
                + self.reminder_schedule_seconds[episode.reminder_index]
            )
        return (
            episode.started_ts
            + self.reminder_schedule_seconds[-1]
            + (self.steady_repeat_seconds * episode.repeat_index)
        )

    def pop_due(self, *, now_ts: float) -> EpisodeNotificationBatch:
        now = float(now_ts)
        batch = EpisodeNotificationBatch()

        recovery_batch_due = any(
            episode.recovery_due_ts is not None
            and now >= episode.recovery_due_ts
            for episode in self._recovered
        )
        remaining_recovered: list[IrregularEpisode] = []
        for episode in self._recovered:
            if (
                recovery_batch_due
                and episode.recovery_due_ts is not None
                and episode.recovery_due_ts <= now + self.coalesce_seconds
            ):
                batch.recovered.append(episode)
            else:
                remaining_recovered.append(episode)
        self._recovered = remaining_recovered

        active_episodes = list(self.active.values())
        opening_batch_due = any(
            (
                not episode.initial_notice_sent
                and now >= episode.initial_due_ts
            )
            or (
                episode.update_due_ts is not None
                and now >= episode.update_due_ts
            )
            for episode in active_episodes
        )
        persistent_batch_due = any(
            due_ts is not None and now >= due_ts
            for due_ts in (
                self._next_reminder_due_ts(episode)
                for episode in active_episodes
            )
        )

        for episode in active_episodes:
            age = max(0.0, now - episode.started_ts)
            if not episode.initial_notice_sent and opening_batch_due:
                episode.initial_notice_sent = True
                episode.update_due_ts = None
                batch.opened.append(episode)
                self._advance_missed_schedule(episode, age)
                continue
            if episode.update_due_ts is not None and now >= episode.update_due_ts:
                episode.update_due_ts = None
                batch.opened.append(episode)
                self._advance_missed_schedule(episode, age)
                continue
            if not episode.initial_notice_sent:
                continue
            reminder_due_ts = self._next_reminder_due_ts(episode)
            if episode.reminder_index < len(self.reminder_schedule_seconds):
                if (
                    persistent_batch_due
                    and reminder_due_ts is not None
                    and reminder_due_ts <= now + self.coalesce_seconds
                ):
                    batch.persistent.append(episode)
                    episode.reminder_index += 1
                    self._advance_missed_schedule(episode, age)
                continue
            if (
                persistent_batch_due
                and reminder_due_ts is not None
                and reminder_due_ts <= now + self.coalesce_seconds
            ):
                batch.persistent.append(episode)
                episode.repeat_index += 1

        key = lambda item: (
            not item.name_display.isdigit(),
            int(item.name_display) if item.name_display.isdigit() else item.name_display,
        )
        batch.opened.sort(key=key)
        batch.persistent.sort(key=key)
        batch.recovered.sort(key=key)
        return batch


def _format_age(seconds: float) -> str:
    s = max(0, int(seconds))
    if s < 60:
        return f"{s}s"
    m = s // 60
    return f"{m}m"


def _compact_alert_line(episode: IrregularEpisode, *, now_ts: float) -> str:
    end_ts = episode.closed_ts if episode.closed_ts is not None else float(now_ts)
    age = _format_age(end_ts - episode.started_ts)
    state_label = _state_label(
        episode.current_state,
        active_boards=episode.active_boards,
        expected_boards=episode.expected_boards,
    )
    parts = [f"{episode.name_display} {state_label}"]
    if episode.current_state == STATE_LOW and episode.responded:
        parts.append(_format_rate(episode.rate_ths))
    parts.append(age)
    if episode.detail_event_id is not None:
        parts.append(f"/e{episode.detail_event_id}")
    return " \u00b7 ".join(parts)


def _compact_recovery_lines(episode: IrregularEpisode, *, now_ts: float) -> list[str]:
    end_ts = episode.closed_ts if episode.closed_ts is not None else float(now_ts)
    age = _format_age(end_ts - episode.started_ts)
    lines: list[str] = [f"{episode.name_display} OK \u00b7 {_format_rate(episode.rate_ths)}"]
    detail_parts = [episode.sequence, age]
    if episode.detail_event_id is not None:
        detail_parts.append(f"/e{episode.detail_event_id}")
    lines.append(" \u00b7 ".join(detail_parts))
    return lines


def _compact_persistent_line(episode: IrregularEpisode) -> str:
    state_label = _state_label(
        episode.current_state,
        active_boards=episode.active_boards,
        expected_boards=episode.expected_boards,
    )
    parts = [f"{episode.name_display} {state_label}"]
    if episode.detail_event_id is not None:
        parts.append(f"/e{episode.detail_event_id}")
    return " \u00b7 ".join(parts)


def render_episode_notification_batch(
    batch: EpisodeNotificationBatch,
    *,
    now_ts: float,
) -> str:
    sections: list[str] = []
    if batch.opened:
        lines = ["ALERTA MINEROS", ""]
        for episode in batch.opened:
            lines.append(_compact_alert_line(episode, now_ts=now_ts))
        sections.append("\n".join(lines))
    if batch.persistent:
        oldest_age = max(
            now_ts - episode.started_ts for episode in batch.persistent
        )
        lines = [f"SIGUE AFECTADO \u00b7 {_format_age(oldest_age)}", ""]
        for episode in batch.persistent:
            lines.append(_compact_persistent_line(episode))
        sections.append("\n".join(lines))
    if batch.recovered:
        lines = ["RECUPERADOS", ""]
        for episode in batch.recovered:
            lines.extend(_compact_recovery_lines(episode, now_ts=now_ts))
        sections.append("\n".join(lines))
    return "\n\n---\n\n".join(sections)


def format_current_status_line(
    *,
    name_display: str,
    host: str,
    confirmed_state: str,
    responded: bool,
    rate_ths: Any,
    threshold_ths: float,
    active_boards: Optional[int],
    expected_boards: int,
    detail_event_id: Optional[int] = None,
) -> str:
    numeric_rate = _safe_rate(rate_ths)
    if not responded:
        signal = "N/A [OFFLINE]"
    elif active_boards is not None and active_boards < expected_boards:
        signal = f"{_format_rate(numeric_rate)} [PLACAS {active_boards}/{expected_boards}]"
    elif numeric_rate is None:
        signal = "N/A [SIN DATOS]"
    elif numeric_rate < float(threshold_ths):
        signal = f"{_format_rate(numeric_rate)} [LOW]"
    elif confirmed_state != STATE_OK:
        signal = f"{_format_rate(numeric_rate)} [RECUPERANDO]"
    else:
        signal = _format_rate(numeric_rate)
    detail = f" | /e{int(detail_event_id)}" if detail_event_id is not None else ""
    return f"- {name_display} ({host}): {signal}{detail}"
