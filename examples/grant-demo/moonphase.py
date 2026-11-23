"""Moon phase helper for Asterie-style night journals (MilestoneGrantEscrow demo deliverable, milestone 0)."""
from datetime import date, datetime, timezone

SYNODIC_MONTH = 29.530588853  # mean length of a lunar cycle in days
REFERENCE_NEW_MOON = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
PHASE_NAMES = [
    "New Moon", "Waxing Crescent", "First Quarter", "Waxing Gibbous",
    "Full Moon", "Waning Gibbous", "Last Quarter", "Waning Crescent",
]


def moon_age(d: date) -> float:
    """Days since the last new moon at 12:00 UTC on the given date (0 <= age < SYNODIC_MONTH)."""
    noon = datetime(d.year, d.month, d.day, 12, tzinfo=timezone.utc)
    days = (noon - REFERENCE_NEW_MOON).total_seconds() / 86400
    return days % SYNODIC_MONTH


def phase_name(d: date) -> str:
    """One of the 8 standard phase names; each phase covers 1/8 of the cycle, centred on its exact moment."""
    index = int((moon_age(d) / SYNODIC_MONTH) * 8 + 0.5) % 8
    return PHASE_NAMES[index]


def illumination(d: date) -> float:
    """Approximate illuminated fraction of the disc (0.0 new moon .. 1.0 full moon)."""
    import math

    return round((1 - math.cos(2 * math.pi * moon_age(d) / SYNODIC_MONTH)) / 2, 3)
