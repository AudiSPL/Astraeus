"""Phase 4: synastry (two-chart comparison) and composite (midpoint chart).

cross_aspects reuses the exact same orb/weight/score formulas as
aspects.detect() (max(orb_a, orb_b) * aspect_factor, same strength/score
weighting) but applied across two different point-sets -- the full cross
product, not the within-one-chart combinations detect() does. A's Sun to B's
Moon and B's Sun to A's Moon are both real, distinct synastry contacts, so
nothing here is deduplicated the way intra-chart pairs are.

Synastry contacts pair positions from different natal epochs. Applying/
separating therefore has no single-time physical referent and is deliberately
reported as null regardless of whether point dictionaries happen to contain
speed fields.

Composite is the midpoint method (not Davison): matching planets and the two
angles are midpointed along the shorter arc. For quadrant/equal-style house
systems, matching house cusps are midpointed as before. For Whole Sign, houses
are rebuilt from the sign containing the composite Ascendant so the result is
still a valid Whole Sign chart. No synthetic time or place is invented.
"""
from .settings import ASPECTS, MINOR_ASPECTS
from .aspects import separation, _orb, _strength, _score
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
                        "applying": None,
                    })
    out.sort(key=lambda x: -x["score"])
    return out


def house_overlay(other_points: dict, cusp_lons: list[float]) -> dict:
    """Where each point in other_points falls among these house cusps."""
    return {name: house_of(p["lon"], cusp_lons) for name, p in other_points.items()}


def _circular_midpoint(lon_a: float, lon_b: float) -> float:
    """Midpoint along the SHORTER arc between two longitudes.

    The returned representation is canonical: 0 <= longitude < 360. Floating
    point rounding can otherwise turn a value infinitesimally below 360 into
    exactly 360.0 at the wrap boundary.
    """
    diff = (lon_b - lon_a) % 360.0
    if diff > 180.0:
        diff -= 360.0
    result = (lon_a + diff / 2.0) % 360.0
    if result >= 360.0:
        return 0.0
    return result


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


def composite_houses(cusps_a: list[float], cusps_b: list[float], *,
                     house_system: str | None = None,
                     composite_asc_lon: float | None = None) -> list[dict]:
    """Build composite houses while preserving the requested house system.

    Non-Whole-Sign systems retain the existing midpoint-of-matching-cusps
    convention. Whole Sign is different by definition: H1 starts at 0 degrees
    of the sign containing the Ascendant, with the remaining houses advancing
    by whole signs. Midpointing two Whole Sign cusp arrays independently can
    produce 15-degree cusps and even put H1 outside the composite ASC sign, so
    Whole Sign requires the already-computed composite Ascendant.
    """
    if house_system == "whole_sign":
        if composite_asc_lon is None:
            raise ValueError("Whole Sign composite houses require composite_asc_lon")
        start = int((composite_asc_lon % 360.0) // 30.0) * 30.0
        return [
            {
                "num": i + 1,
                "cusp_lon": (start + 30.0 * i) % 360.0,
                "sign": sign_of((start + 30.0 * i) % 360.0),
            }
            for i in range(12)
        ]

    out = []
    for i in range(12):
        lon = _circular_midpoint(cusps_a[i], cusps_b[i])
        out.append({"num": i + 1, "cusp_lon": round(lon, 6), "sign": sign_of(lon)})
    return out
