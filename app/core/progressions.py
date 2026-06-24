"""Progressions: long-term symbolic techniques, distinct from transits.

Secondary progressions: "a day for a year". The chart cast for
(birth date + N days) is read as the symbolic chart for age N. Progressed
planets get their own positions AND their own houses (using the progressed
Julian Day with the NATAL lat/lon — the progressed MC/ASC use the Naibod/
solar-arc-equivalent convention: the progressed Sun's arc since birth drives
the angle motion, computed here via the standard day-for-a-year JD directly
fed into swe.houses, which is the conventional fast method, not the slower
"real progressed GMT" variant).

Solar Arc directions: every natal point is shifted by the SAME arc — the
number of degrees the natal Sun has moved by the target date (via secondary
progression's Sun, which is the standard equivalence: 1 day after birth ~ 1
year of arc). Solar arc points are directed positions only; they don't have
their own houses (there is no "solar arc chart"), only aspects to natal
planets/angles.
"""
import swisseph as swe

from . import config
from .settings import ASPECTS, ASPECT_FACTOR, ORB_BY_BODY
from .ephemeris import position, base_flag, _mk, IPL, init, _LOCK, compute_houses
from .aspects import separation

PROG_MOVERS = ["Sun", "Moon", "Mercury", "Venus", "Mars",
               "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]

# Progressions use tighter orbs than natal aspects — they mark slow-turning
# life themes, not background coloring. Applying/separating doesn't apply
# (progressed speeds are ~1/365th of natal speeds and the question is moot
# at yearly resolution), so it's omitted from progression aspects.
PROG_ORB = 1.0


def _progressed_jd(birth_jd: float, target_date_iso: str, birth_date_iso: str) -> float:
    """Day-for-a-year: progressed JD = birth_jd + (years elapsed)."""
    from datetime import date
    b = date.fromisoformat(birth_date_iso)
    t = date.fromisoformat(target_date_iso)
    years_elapsed = (t - b).days / 365.2425
    return birth_jd + years_elapsed


def secondary_positions(birth_jd: float, target_date_iso: str, birth_date_iso: str,
                        zodiac: str, lat: float, lon: float, house_system: str):
    """Returns (prog_jd, bodies dict, angles dict, houses list)."""
    with _LOCK:
        init()
        if zodiac == "sidereal":
            swe.set_sid_mode(swe.SIDM_LAHIRI)
        flag = base_flag(zodiac)
        prog_jd = _progressed_jd(birth_jd, target_date_iso, birth_date_iso)

        bodies = {}
        for n in PROG_MOVERS:
            lon_, sp = position(prog_jd, IPL[n], flag)
            bodies[n] = _mk(n, lon_, sp)

        # progressed angles: progressed JD through the NATAL lat/lon (the
        # conventional fast/Naibod-equivalent method, not real progressed GMT)
        houses, angles, cusp_lons = compute_houses(prog_jd, lat, lon, house_system, zodiac)
        for b in bodies.values():
            from .ephemeris import house_of
            b["house"] = house_of(b["lon"], cusp_lons)

        return prog_jd, bodies, angles, houses


def solar_arc_positions(natal_bodies: dict, natal_angles: dict, arc_degrees: float):
    """Shift every natal point by the same arc. No houses — directed points only."""
    out = {}
    for name, b in natal_bodies.items():
        lon = (b["lon"] + arc_degrees) % 360
        out[name] = {"name": name, "lon": round(lon, 6),
                     "sign": _sign(lon), "deg_in_sign": round(lon % 30, 4)}
    angles = {}
    for key in ("asc", "mc"):
        lon = (natal_angles[key]["lon"] + arc_degrees) % 360
        angles[key] = {"lon": round(lon, 6), "sign": _sign(lon), "deg_in_sign": round(lon % 30, 4)}
    return out, angles


def _sign(lon):
    from .settings import SIGNS
    return SIGNS[int((lon % 360) // 30)]


def directed_to_natal(directed_points: dict, natal_points: dict, label: str) -> list[dict]:
    """Aspects from progressed/directed points to natal points. `label` is
    'secondary' or 'solar_arc', stamped onto each result for traceability."""
    out = []
    for dn, D in directed_points.items():
        for nn, N in natal_points.items():
            s = separation(D["lon"], N["lon"])
            for aspect, angle in ASPECTS.items():
                max_orb = PROG_ORB * ASPECT_FACTOR[aspect]
                d = abs(s - angle)
                if d <= max_orb:
                    tightness = max(0.0, 1.0 - d / max_orb)
                    bw = max(ORB_BY_BODY.get(dn, 3), ORB_BY_BODY.get(nn, 3)) / 8.0
                    out.append({
                        "technique": label,
                        "directed": dn, "natal": nn, "type": aspect,
                        "exact_deg": angle, "orb": round(d, 3),
                        "score": round(tightness * min(bw, 1.0), 3),
                    })
    out.sort(key=lambda x: -x["score"])
    return out
