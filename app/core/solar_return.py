"""Phase 4: solar return -- the moment each calendar year the transiting Sun
returns to its exact natal longitude. A full chart is cast for that moment
(own planets/houses/angles/internal aspects, like a mini natal chart) and then
compared back to the natal chart.

The exact-moment search reuses transits.exact_hits (already tested). chart_at
is a thin delegation to ephemeris, mirroring how transits.py wraps ephemeris
for its own snapshot rather than packet.py calling ephemeris directly.
"""
import swisseph as swe

from .ephemeris import compute_bodies, compute_houses
from .settings import ASPECTS
from .aspects import separation
from .transits import exact_hits

SR_ORB = 3.0


def find_return_jd(natal_sun_lon: float, year: int, flag: int) -> float:
    """Exact JD of the solar return in the given calendar year. The Sun
    crosses any given longitude exactly once per year, so a full-year scan
    finds exactly one hit. +/-10 day boundary pad covers the rare case where
    the return falls right at the year edge (birthdays very close to Jan 1)."""
    jd0 = swe.julday(year, 1, 1, 0.0)
    jd1 = swe.julday(year + 1, 1, 1, 0.0)
    hits = exact_hits(swe.SUN, natal_sun_lon, 0, flag, jd0, jd1, step=1.0)
    if not hits:
        hits = exact_hits(swe.SUN, natal_sun_lon, 0, flag, jd0 - 10, jd1 + 10, step=1.0)
    if not hits:
        raise ValueError(f"no solar return found near {year} -- check natal Sun longitude")
    return hits[0]


def chart_at(jd: float, lat: float, lon: float, house_system: str,
            zodiac: str, node_type: str, include_points: list[str]):
    """Full chart (bodies, houses, angles, cusp_lons) at an arbitrary moment
    and location -- the same shape ephemeris produces for the natal chart."""
    bodies = compute_bodies(jd, zodiac, node_type, include_points)
    houses, angles, cusp_lons = compute_houses(jd, lat, lon, house_system, zodiac)
    return bodies, houses, angles, cusp_lons


def aspects_to_natal(sr_points: dict, natal_points: dict) -> list[dict]:
    """SR planets/angles vs the natal chart, flat SR_ORB on all five major
    aspects. Chart-to-chart comparison, not a moving transit."""
    out = []
    for sn, S in sr_points.items():
        for nn, N in natal_points.items():
            s = separation(S["lon"], N["lon"])
            for aspect, angle in ASPECTS.items():
                d = abs(s - angle)
                if d <= SR_ORB:
                    out.append({
                        "solar_return": sn, "natal": nn, "type": aspect,
                        "exact_deg": angle, "orb": round(d, 3),
                    })
    out.sort(key=lambda x: x["orb"])
    return out
