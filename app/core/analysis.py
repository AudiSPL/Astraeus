"""Derived natal facts computed from positions + houses. Still deterministic,
still no interpretation.
"""
from .settings import SIGN_ELEMENT, SIGN_MODALITY, MODERN_RULERS, SIGNS, CORE_FOR_BALANCE
from .ephemeris import house_of

_PHASES = ["New", "Waxing Crescent", "First Quarter", "Waxing Gibbous",
           "Full", "Waning Gibbous", "Last Quarter", "Waning Crescent"]


def assign_houses(bodies: dict, cusp_lons: list[float]):
    for b in bodies.values():
        b["house"] = house_of(b["lon"], cusp_lons)


def balances(bodies: dict):
    el = {"fire": 0, "earth": 0, "air": 0, "water": 0}
    mo = {"cardinal": 0, "fixed": 0, "mutable": 0}
    for n in CORE_FOR_BALANCE:
        sign = bodies[n]["sign"]
        el[SIGN_ELEMENT[sign]] += 1
        mo[SIGN_MODALITY[sign]] += 1
    return ({"scope": "Sun_through_Pluto", "counts": el},
            {"scope": "Sun_through_Pluto", "counts": mo})


def chart_ruler(asc_lon: float) -> str:
    return MODERN_RULERS[SIGNS[int((asc_lon % 360) // 30)]]


def lunar_phase(sun_lon: float, moon_lon: float):
    ang = (moon_lon - sun_lon) % 360
    idx = int(((ang + 22.5) % 360) // 45)
    return _PHASES[idx], round(ang, 2)


def retrogrades(bodies: dict) -> list[str]:
    return [b["name"] for b in bodies.values() if b.get("retrograde")]
