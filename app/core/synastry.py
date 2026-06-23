"""Phase 4: synastry (two-chart comparison) and composite (midpoint chart).

cross_aspects reuses the exact same orb/weight/score formulas as
aspects.detect() (max(orb_a, orb_b) * aspect_factor, same strength/score
weighting) but applied across two different point-sets -- the full cross
product, not the within-one-chart combinations detect() does. A's Sun to B's
Moon and B's Sun to A's Moon are both real, distinct synastry contacts, so
nothing here is deduplicated the way intra-chart pairs are.

Composite is the standard midpoint method (not Davison): every matching
planet, the two angles, and the twelve house cusps are each independently
midpointed along the shorter arc. No synthetic time or place is invented.
"""
from .settings import ASPECTS, MINOR_ASPECTS
from .aspects import separation, _orb, _applying, _strength, _score
from .ephemeris import house_of, sign_of


def cross_aspects(primary_points: dict, partner_points: dict,
                  include_minors: bool = False) -> list[dict]:
    table = dict(ASPECTS)
    if include_minors:
        table.update(MINOR_ASPECTS)
    out = []
    for A in primary_points.values():
        for B in partner_points.values():
            s = separation(A["lon"], B["lon"])
            for aspect, angle in table.items():
                max_orb = _orb(A["name"], B["name"], aspect)
                d = abs(s - angle)
                if d <= max_orb:
                    out.append({
                        "primary": A["name"], "partner": B["name"], "type": aspect,
                        "exact_deg": angle, "orb": round(d, 3),
                        "strength": _strength(d, max_orb),
                        "score": _score(A["name"], B["name"], aspect, d, max_orb),
                        "applying": _applying(A["lon"], A.get("speed"),
                                              B["lon"], B.get("speed"), angle),
                    })
    out.sort(key=lambda x: -x["score"])
    return out


def house_overlay(other_points: dict, cusp_lons: list[float]) -> dict:
    """Where each point in other_points falls among these house cusps."""
    return {name: house_of(p["lon"], cusp_lons) for name, p in other_points.items()}


def _circular_midpoint(lon_a: float, lon_b: float) -> float:
    """Midpoint along the SHORTER arc between two longitudes -- the
    conventional 'near' composite midpoint, not the antipodal/far point.
    Plain (a+b)/2 breaks across the 0 deg wrap (350 deg and 10 deg should
    midpoint to 0 deg, not 180 deg)."""
    diff = (lon_b - lon_a) % 360
    if diff > 180:
        diff -= 360
    return (lon_a + diff / 2) % 360


def composite_bodies(bodies_a: dict, bodies_b: dict) -> dict:
    out = {}
    for name in bodies_a:
        if name in bodies_b:
            lon = _circular_midpoint(bodies_a[name]["lon"], bodies_b[name]["lon"])
            out[name] = {"name": name, "lon": round(lon, 6), "sign": sign_of(lon),
                        "deg_in_sign": round(lon % 30, 4)}
    return out


def composite_angles(angles_a: dict, angles_b: dict) -> dict:
    asc = _circular_midpoint(angles_a["asc"]["lon"], angles_b["asc"]["lon"])
    mc = _circular_midpoint(angles_a["mc"]["lon"], angles_b["mc"]["lon"])
    return {
        "asc": {"lon": round(asc, 6), "sign": sign_of(asc), "deg_in_sign": round(asc % 30, 4)},
        "mc": {"lon": round(mc, 6), "sign": sign_of(mc), "deg_in_sign": round(mc % 30, 4)},
    }


def composite_houses(cusps_a: list[float], cusps_b: list[float]) -> list[dict]:
    """Midpoint of each matching house cusp (1-12) -- the same convention
    Astrodienst uses for 'composite chart, midpoint method'."""
    out = []
    for i in range(12):
        lon = _circular_midpoint(cusps_a[i], cusps_b[i])
        out.append({"num": i + 1, "cusp_lon": round(lon, 6), "sign": sign_of(lon)})
    return out
