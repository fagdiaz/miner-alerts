from app.governance.power_notifications import PowerObservation, observe_power


def test_startup_noise_and_confirmed_step():
    s = PowerObservation()
    assert observe_power(s, 1998, 0) is None
    assert observe_power(s, 2002, 30) is None
    assert observe_power(s, 2148, 60) is None
    assert observe_power(s, 2149, 120) is None
    assert observe_power(s, 2148, 150) == (2000, 2150)


def test_flapping_returns_to_baseline_without_notice():
    s = PowerObservation()
    for power, now in [(2000, 0), (2150, 30), (2000, 60), (2150, 90)]:
        assert observe_power(s, power, now) is None
    assert observe_power(s, 2150, 150) is None


def test_cooldown_coalesces_latest_change_in_both_directions():
    s = PowerObservation()
    observe_power(s, 2000, 0)
    observe_power(s, 2150, 30)
    assert observe_power(s, 2150, 120) == (2000, 2150)
    assert observe_power(s, 2000, 150) is None
    assert observe_power(s, 2000, 300) is None
    assert observe_power(s, 1850, 900) is None
    assert observe_power(s, 1850, 1020) == (2150, 1850)


def test_missing_telemetry_maintenance_and_stops_reset_confirmation():
    for invalid in [None, 0, float('nan'), float('inf')]:
        s = PowerObservation()
        observe_power(s, 2000, 0)
        observe_power(s, 2150, 30)
        assert observe_power(s, invalid, 120) is None
        assert observe_power(s, 2150, 150) is None
    s = PowerObservation()
    observe_power(s, 2000, 0)
    observe_power(s, 2150, 30)
    assert observe_power(s, 2150, 120, valid=False) is None
    assert observe_power(s, 2150, 150) is None
