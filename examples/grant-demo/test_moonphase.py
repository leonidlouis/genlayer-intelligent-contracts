from datetime import date

from moonphase import PHASE_NAMES, illumination, phase_name


def test_known_new_moon():
    assert phase_name(date(2026, 1, 18)) == "New Moon"


def test_known_full_moon():
    assert phase_name(date(2026, 1, 3)) == "Full Moon"


def test_every_day_has_a_standard_name():
    for day in range(1, 29):
        assert phase_name(date(2026, 2, day)) in PHASE_NAMES


def test_illumination_bounds():
    assert illumination(date(2026, 1, 18)) < 0.05
    assert illumination(date(2026, 1, 3)) > 0.95
