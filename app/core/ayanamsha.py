"""Ayanamsha registry and sidereal-mode handling.

Two jobs:

1. Name the ayanamsha explicitly instead of hardcoding Lahiri, and report its
   value in degrees at the epoch that produced it. The value drifts about 50
   arcseconds a year, so a number without a Julian day is not reproducible.

2. Make the sidereal mode a scoped, locked operation. swe.set_sid_mode() sets
   process-global C state. Setting it once and relying on it staying put is
   safe with a single hardcoded ayanamsha and unsafe the moment there is more
   than one.

The concrete failure this prevents:

    swe.houses_ex(jd, lat, lon, b'P', swe.FLG_SIDEREAL)

does NOT take an ayanamsha argument. It reads whatever set_sid_mode() left
behind. With no prior call, swisseph defaults to Fagan/Bradley, which for the
reference chart puts the sidereal Ascendant 0.88 degrees away from Lahiri.
Today compute_houses() only gets Lahiri cusps because compute_bodies() runs
first in _full_chart() and happens to set the mode. The lock is released
between those two calls.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from dataclasses import dataclass

import swisseph as swe

__all__ = [
    "AYANAMSHAS",
    "DEFAULT_AYANAMSHA",
    "Ayanamsha",
    "resolve",
    "value_at",
    "describe",
    "sidereal_scope",
    "SWISS_LOCK",
]

#: Shared with ephemeris.py. Every swe call in the process must hold it,
#: including calls that only read global state such as houses_ex().
SWISS_LOCK = threading.RLock()

DEFAULT_AYANAMSHA = "lahiri"


@dataclass(frozen=True)
class Ayanamsha:
    key: str
    swe_mode: int
    label: str
    note: str


AYANAMSHAS: dict[str, Ayanamsha] = {
    "lahiri": Ayanamsha(
        "lahiri", swe.SIDM_LAHIRI, "Lahiri (Chitrapaksha)",
        "Indian government standard; the default in most Vedic software."),
    "fagan_bradley": Ayanamsha(
        "fagan_bradley", swe.SIDM_FAGAN_BRADLEY, "Fagan/Bradley",
        "Western sidereal standard. Also swisseph's own default when "
        "set_sid_mode has never been called, which is why an unset mode is a "
        "silent bug rather than an error."),
    "krishnamurti": Ayanamsha(
        "krishnamurti", swe.SIDM_KRISHNAMURTI, "Krishnamurti",
        "KP system. Close to Lahiri, roughly a tenth of a degree apart."),
    "raman": Ayanamsha(
        "raman", swe.SIDM_RAMAN, "B. V. Raman",
        "About 1.4 degrees below Lahiri, enough to move a placement across a "
        "sign boundary."),
}


def resolve(name: str | None) -> Ayanamsha:
    key = (name or DEFAULT_AYANAMSHA).strip().lower()
    if key not in AYANAMSHAS:
        raise ValueError(
            f"unknown ayanamsha {name!r}; available: {', '.join(sorted(AYANAMSHAS))}")
    return AYANAMSHAS[key]


def value_at(jd_ut: float, name: str | None = None) -> float:
    """Ayanamsha in degrees at a specific instant.

    Called per epoch on purpose. Natal, transit and solar-return moments do
    not share a value, and quoting one figure for all three is the kind of
    thing that makes a packet unreproducible.
    """
    ayan = resolve(name)
    with SWISS_LOCK:
        swe.set_sid_mode(ayan.swe_mode)
        return swe.get_ayanamsa_ut(jd_ut)


def describe(jd_ut: float, zodiac: str, name: str | None = None) -> dict | None:
    """The ayanamsha block for the calculation metadata. None for tropical."""
    if zodiac != "sidereal":
        return None
    ayan = resolve(name)
    return {
        "name": ayan.key,
        "label": ayan.label,
        "value_deg": round(value_at(jd_ut, ayan.key), 6),
        "julian_day_ut": round(jd_ut, 7),
        "note": ayan.note,
    }


@contextmanager
def sidereal_scope(zodiac: str, name: str | None = None):
    """Hold the lock and pin the sidereal mode for the whole block.

    Wrap every sequence that computes bodies and houses for one chart, so no
    other thread can change the mode between the two calls.

        with sidereal_scope(zodiac, ayanamsha):
            bodies = compute_bodies(...)
            houses = compute_houses(...)

    Tropical still takes the lock. pyswisseph is not thread-safe regardless of
    zodiac, and a tropical request running beside a sidereal one must not
    interleave.
    """
    with SWISS_LOCK:
        if zodiac == "sidereal":
            swe.set_sid_mode(resolve(name).swe_mode)
        yield
