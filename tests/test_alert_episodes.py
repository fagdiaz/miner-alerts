import unittest

from app.alert_episodes import (
    IrregularEpisodeCoordinator,
    format_current_status_line,
    render_episode_notification_batch,
)


def observe(
    coordinator: IrregularEpisodeCoordinator,
    *,
    miner: str = "25",
    previous_state: str = "OK",
    state: str = "LOW",
    now_ts: float = 100.0,
    rate_ths: float | None = 40.0,
    responded: bool = True,
    active_boards: int | None = 3,
    transition_event_id: int | None = 10,
    restart: dict | None = None,
) -> None:
    coordinator.observe(
        miner_key=f"S19JPRO-{miner}|192.168.100.{miner}:4028",
        name_display=miner,
        host=f"192.168.100.{miner}",
        previous_state=previous_state,
        state=state,
        responded=responded,
        rate_ths=rate_ths,
        threshold_ths=60.0,
        active_boards=active_boards,
        expected_boards=3,
        now_ts=now_ts,
        transition_event_id=transition_event_id,
        restart=restart,
    )


class IrregularEpisodeCoordinatorTests(unittest.TestCase):
    def make_coordinator(self, *, max_history_steps: int = 12) -> IrregularEpisodeCoordinator:
        return IrregularEpisodeCoordinator(
            coalesce_seconds=30,
            reminder_schedule_seconds=(300, 600, 900, 1800, 3600, 7200),
            steady_repeat_seconds=3600,
            max_history_steps=max_history_steps,
        )

    def test_initial_notice_is_bounded_and_grouped(self) -> None:
        coordinator = self.make_coordinator()
        observe(coordinator, miner="23", now_ts=100.0)
        observe(
            coordinator,
            miner="24",
            now_ts=125.0,
            state="OFFLINE",
            rate_ths=None,
            responded=False,
            active_boards=None,
            transition_event_id=11,
        )

        self.assertTrue(coordinator.pop_due(now_ts=129.9).empty)
        batch = coordinator.pop_due(now_ts=130.0)

        self.assertEqual(["23", "24"], [item.name_display for item in batch.opened])
        self.assertTrue(coordinator.pop_due(now_ts=155.0).empty)

    def test_three_five_minute_reminders_then_wider_episode_ages(self) -> None:
        coordinator = self.make_coordinator()
        observe(coordinator, now_ts=100.0)
        coordinator.pop_due(now_ts=130.0)

        expected_due = (400, 700, 1000, 1900, 3700, 7300, 10900)
        for index, due_ts in enumerate(expected_due, start=1):
            self.assertTrue(coordinator.pop_due(now_ts=due_ts - 0.1).empty)
            batch = coordinator.pop_due(now_ts=due_ts)
            self.assertEqual(1, len(batch.persistent), f"reminder {index}")
            self.assertEqual("25", batch.persistent[0].name_display)

    def test_due_reminders_for_multiple_miners_share_one_batch(self) -> None:
        coordinator = self.make_coordinator()
        observe(coordinator, miner="23", now_ts=100.0)
        observe(coordinator, miner="24", now_ts=100.0)
        coordinator.pop_due(now_ts=130.0)

        batch = coordinator.pop_due(now_ts=400.0)

        self.assertEqual(["23", "24"], [item.name_display for item in batch.persistent])
        message = render_episode_notification_batch(batch, now_ts=400.0)
        self.assertEqual(1, message.count("FALLA PERSISTENTE"))
        self.assertIn("- 23:", message)
        self.assertIn("- 24:", message)

    def test_nearby_reminders_and_recoveries_share_the_short_batch(self) -> None:
        coordinator = self.make_coordinator()
        observe(coordinator, miner="23", now_ts=100.0)
        observe(coordinator, miner="24", now_ts=125.0)
        coordinator.pop_due(now_ts=130.0)

        reminder = coordinator.pop_due(now_ts=400.0)
        self.assertEqual(
            ["23", "24"],
            [item.name_display for item in reminder.persistent],
        )

        observe(
            coordinator,
            miner="23",
            previous_state="LOW",
            state="OK",
            now_ts=500.0,
            rate_ths=95.0,
        )
        observe(
            coordinator,
            miner="24",
            previous_state="LOW",
            state="OK",
            now_ts=525.0,
            rate_ths=96.0,
        )

        recovery = coordinator.pop_due(now_ts=530.0)
        self.assertEqual(
            ["23", "24"],
            [item.name_display for item in recovery.recovered],
        )

    def test_short_low_recovery_is_one_complete_sequence(self) -> None:
        coordinator = self.make_coordinator()
        observe(coordinator, now_ts=100.0)
        observe(
            coordinator,
            previous_state="LOW",
            state="OK",
            now_ts=120.0,
            rate_ths=92.0,
            transition_event_id=12,
        )

        self.assertTrue(coordinator.pop_due(now_ts=129.9).empty)
        batch = coordinator.pop_due(now_ts=130.0)
        self.assertEqual(1, len(batch.recovered))
        message = render_episode_notification_batch(batch, now_ts=130.0)
        self.assertIn("MINEROS RECUPERADOS", message)
        self.assertIn("OK -> LOW -> OK", message)
        self.assertNotIn("FALLA PERSISTENTE", message)

    def test_restart_episode_tracks_intermediate_states_and_closes(self) -> None:
        coordinator = self.make_coordinator()
        observe(
            coordinator,
            previous_state="OK",
            state="OFFLINE",
            now_ts=100.0,
            rate_ths=None,
            responded=False,
            active_boards=None,
            transition_event_id=20,
        )
        observe(
            coordinator,
            previous_state="OFFLINE",
            state="HASHBOARD",
            now_ts=120.0,
            rate_ths=0.0,
            active_boards=0,
            transition_event_id=22,
            restart={
                "event_id": 21,
                "classification": "unexpected",
                "previous_elapsed": 40_000,
                "current_elapsed": 1,
            },
        )
        opening = coordinator.pop_due(now_ts=130.0)
        self.assertEqual(1, len(opening.opened))
        self.assertIn("/e21", render_episode_notification_batch(opening, now_ts=130.0))

        observe(
            coordinator,
            previous_state="HASHBOARD",
            state="LOW",
            now_ts=150.0,
            rate_ths=20.0,
            transition_event_id=23,
        )
        observe(
            coordinator,
            previous_state="LOW",
            state="OK",
            now_ts=180.0,
            rate_ths=95.0,
            transition_event_id=24,
        )
        recovery = coordinator.pop_due(now_ts=210.0)
        message = render_episode_notification_batch(recovery, now_ts=210.0)
        self.assertIn("OK -> OFFLINE -> REINICIO -> PLACAS 0/3 -> LOW -> OK", message)
        self.assertEqual({}, coordinator.active)

    def test_expected_restart_names_the_attributed_action(self) -> None:
        coordinator = self.make_coordinator()
        observe(
            coordinator,
            previous_state="OK",
            state="LOW",
            now_ts=100.0,
            rate_ths=12.0,
            transition_event_id=31,
            restart={
                "event_id": 30,
                "classification": "expected_manual",
                "previous_elapsed": 20_000,
                "current_elapsed": 5,
            },
        )

        message = render_episode_notification_batch(
            coordinator.pop_due(now_ts=130.0),
            now_ts=130.0,
        )

        self.assertIn("accion manual atribuida", message)
        self.assertIn("uptime 20000s -> 5s", message)
        self.assertIn("OK -> REINICIO -> LOW", message)

    def test_history_is_bounded_without_losing_first_state(self) -> None:
        coordinator = self.make_coordinator(max_history_steps=5)
        observe(coordinator, now_ts=100.0)
        previous = "LOW"
        for index, state in enumerate(("OFFLINE", "LOW", "HASHBOARD", "LOW", "OFFLINE"), start=1):
            observe(
                coordinator,
                previous_state=previous,
                state=state,
                now_ts=100.0 + index,
                rate_ths=None if state == "OFFLINE" else 20.0,
                responded=state != "OFFLINE",
                active_boards=0 if state == "HASHBOARD" else 3,
                transition_event_id=10 + index,
            )
            previous = state

        episode = next(iter(coordinator.active.values()))
        self.assertLessEqual(len(episode.history), 5)
        self.assertEqual("OK", episode.history[0].label)


class CurrentStatusRenderingTests(unittest.TestCase):
    def render(self, **overrides: object) -> str:
        values = {
            "name_display": "25",
            "host": "192.168.100.25",
            "confirmed_state": "OK",
            "responded": True,
            "rate_ths": 97.87,
            "threshold_ths": 60.0,
            "active_boards": 3,
            "expected_boards": 3,
            "detail_event_id": None,
        }
        values.update(overrides)
        return format_current_status_line(**values)

    def test_offline_never_shows_stale_positive_rate(self) -> None:
        line = self.render(responded=False, rate_ths=97.87, confirmed_state="OFFLINE")
        self.assertIn("N/A [OFFLINE]", line)
        self.assertNotIn("97.87", line)

    def test_healthy_signal_during_hysteresis_is_recovering(self) -> None:
        line = self.render(confirmed_state="OFFLINE", rate_ths=97.87)
        self.assertIn("97.87 TH/s [RECUPERANDO]", line)
        self.assertNotIn("[OFFLINE]", line)

    def test_low_and_board_loss_use_current_evidence(self) -> None:
        self.assertIn("55.00 TH/s [LOW]", self.render(rate_ths=55.0))
        board_line = self.render(rate_ths=0.0, active_boards=0, confirmed_state="HASHBOARD")
        self.assertIn("[PLACAS 0/3]", board_line)
        self.assertNotIn("HASHBOARD", board_line)

    def test_active_restart_detail_is_click_safe(self) -> None:
        line = self.render(confirmed_state="LOW", rate_ths=20.0, detail_event_id=37)
        self.assertIn("/e37", line)


if __name__ == "__main__":
    unittest.main()
