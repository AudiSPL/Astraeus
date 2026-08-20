"""Synastry and composite invariants.

These import app.core.synastry directly rather than going through the
packet, so they do not depend on where the composite block lands in the
response shape.

Three categories here, and the distinction matters:

* plain tests   - current behaviour that must keep working
* xfail(strict) - a defect with a definable acceptance criterion; pytest
                  fails if one starts passing, so a fix is acknowledged
* OPEN          - a methodological choice with no single correct answer.
                  Documented as a passing test, NOT as a bug, because there
                  is nothing to "fix" until the decision is made.
"""

from __future__ import annotations

import pytest

from app.core.synastry import (
    _circular_midpoint,
    composite_angles,
    composite_houses,
    cross_aspects,
)

KNOWN_BUG = "known v1 defect; remove this marker in the commit that fixes it"

# Real values from the synastry_reference golden packet.
PRIMARY_ASC = 119.373963  # Cancer
PARTNER_ASC = 139.084773  # Leo


def _angular_delta(a: float, b: float) -> float:
    """Distance between two longitudes, treating 0 and 360 as one point."""
    return abs((a - b + 180) % 360 - 180)


def _whole_sign_cusps(asc_lon: float) -> list[float]:
    """Whole Sign: house 1 starts at 0 degrees of the sign holding the ASC."""
    start = (asc_lon // 30) * 30
    return [(start + 30 * i) % 360 for i in range(12)]


def _sign_index(lon: float) -> int:
    return int(lon % 360 // 30)


# --- behaviour that must keep working --------------------------------------


def test_midpoint_takes_the_shorter_arc_across_zero():
    assert _angular_delta(_circular_midpoint(350.0, 10.0), 0.0) < 1e-9
    assert _angular_delta(_circular_midpoint(10.0, 350.0), 0.0) < 1e-9


def test_midpoint_is_symmetric():
    """Compared as longitudes, not as plain floats.

    _circular_midpoint(359.9, 0.1) gives 0.0 and the reversed argument order
    gives 360.0. Those are the same point on a circle, so an equality check
    on the raw numbers reports a failure that is not one. The representation
    problem is a separate matter, covered below.
    """
    for a, b in [(12.5, 200.0), (359.9, 0.1), (45.0, 46.0), (0.0, 90.0), (271.3, 0.0)]:
        forward, reverse = _circular_midpoint(a, b), _circular_midpoint(b, a)
        assert _angular_delta(forward, reverse) < 1e-9, f"{a},{b}: {forward} vs {reverse}"


def test_cross_aspects_leave_applying_null_without_speeds():
    """This is how packet.py currently calls it.

    The point sets it builds carry name and lon only, so _applying receives
    None for both speeds and returns None. Pinning it here means the
    companion hazard below cannot be reintroduced unnoticed.
    """
    a = {"Sun": {"name": "Sun", "lon": 121.400681}}
    b = {"Moon": {"name": "Moon", "lon": 121.5}}
    contacts = cross_aspects(a, b)
    assert contacts, "expected a conjunction within orb"
    assert all(c["applying"] is None for c in contacts)


# --- defects with a definable fix ------------------------------------------


@pytest.mark.xfail(strict=True, reason=f"{KNOWN_BUG}: _circular_midpoint can return exactly 360.0")
def test_midpoint_returns_a_canonical_longitude():
    """A longitude belongs in [0, 360).

    _circular_midpoint(0.1, 359.9) lands 2.3e-14 below 360, and the float
    spacing at 360 is 5.7e-14, so it rounds up to 360.0 exactly.
    composite_bodies then emits {"lon": 360.0, "sign": "Aries",
    "deg_in_sign": 0.0} - sign and degree right, longitude out of range.
    Everything downstream happens to take a modulo, which is why this has
    never surfaced.
    """
    for a, b in [(0.1, 359.9), (359.9, 0.1), (180.05, 179.95)]:
        lon = _circular_midpoint(a, b)
        assert 0.0 <= lon < 360.0, f"{a},{b} -> {lon}"


@pytest.mark.xfail(strict=True, reason=f"{KNOWN_BUG}: whole-sign composite cusps are not sign boundaries")
def test_whole_sign_composite_cusps_stay_on_sign_boundaries():
    """Midpointing twelve cusps independently does not preserve the house
    system that produced them.

    Whole Sign cusps are multiples of 30 by definition. Midpointing two Whole
    Sign charts an ODD number of signs apart puts every composite cusp 15
    degrees into a sign. The result is still labelled whole_sign and is not a
    Whole Sign chart.

    An even gap lands cleanly, which is why this went unnoticed.
    """
    composite = composite_houses(_whole_sign_cusps(PRIMARY_ASC), _whole_sign_cusps(PARTNER_ASC))
    offsets = sorted({round(h["cusp_lon"] % 30, 6) for h in composite})
    assert offsets == [0.0], f"cusps sit at {offsets} degrees into their signs"


@pytest.mark.xfail(strict=True, reason=f"{KNOWN_BUG}: composite house 1 can fall outside the composite Ascendant's sign")
def test_whole_sign_composite_house_one_holds_the_ascendant():
    """The second half of the same defect, and the more visible one.

    In Whole Sign the Ascendant does not sit on the cusp of house 1 - house 1
    begins at 0 degrees of the sign containing it. So the invariant is not
    "cusp equals ASC", it is "house 1 is in the ASC's sign".

    With Cancer rising against Leo rising the composite Ascendant lands in
    Leo while composite house 1 starts at 15 degrees Cancer. A reader is told
    the chart rises in Leo and then handed houses built on Cancer.
    """
    angles = composite_angles(
        {"asc": {"lon": PRIMARY_ASC}, "mc": {"lon": 10.87234}},
        {"asc": {"lon": PARTNER_ASC}, "mc": {"lon": 30.0}},
    )
    houses = composite_houses(_whole_sign_cusps(PRIMARY_ASC), _whole_sign_cusps(PARTNER_ASC))
    assert _sign_index(houses[0]["cusp_lon"]) == _sign_index(angles["asc"]["lon"]), (
        f"composite ASC {angles['asc']['lon']:.4f} but house 1 cusp {houses[0]['cusp_lon']:.4f}"
    )


@pytest.mark.xfail(
    strict=True,
    reason="latent module contract hazard: cross_aspects will compute applying if given speeds",
)
def test_cross_aspects_refuse_applying_even_when_given_speeds():
    """Not a current packet defect - packet.py passes no speeds, so live
    output already carries applying: null throughout.

    It is a contract hazard. cross_aspects accepts speeds and will use them,
    so a refactor that starts passing full body dicts would silently turn on
    a meaningless field. Applying describes two bodies converging as time
    advances; a synastry contact pairs a 1984 position with a 1988 one, and
    the closing rate of that pair has no referent at any single instant.

    Section 6.5 of the interpreter prompt already defines applying: null as
    "do not infer timing direction", which is the correct value regardless of
    what the caller supplies.
    """
    a = {"Sun": {"name": "Sun", "lon": 121.400681, "speed": 0.955291}}
    b = {"Moon": {"name": "Moon", "lon": 121.5, "speed": 12.89052}}
    for contact in cross_aspects(a, b):
        assert contact["applying"] is None, contact


# --- open methodology, not a bug -------------------------------------------


def test_midpoint_is_antipodal_across_exact_opposition():
    """Documented, deliberately NOT marked xfail.

    At 179.99 degrees apart the shorter arc runs one way; at 180.01 it runs
    the other, so the two midpoints are antipodal. Given shorter-arc
    semantics that jump is forced, not a defect - you cannot have both the
    shorter arc and continuity through 180. At exactly 180 there are two
    equally valid midpoints and the current tie-break picks one silently.

    The reason to record it: the reference chart's Ascendant is unresolved
    across roughly 0.6 degrees, far wider than the interval where this flip
    lives. If a partner's Ascendant falls near the opposition, the composite
    Ascendant is decided by birth-time noise. That belongs in the sensitivity
    work as an ambiguity flag, not in a fix that pretends one scalar is
    reliable.
    """
    below = _circular_midpoint(0.0, 179.99)
    above = _circular_midpoint(0.0, 180.01)
    assert _angular_delta(below, above) == pytest.approx(180.0, abs=0.05)
    assert _circular_midpoint(0.0, 180.0) == pytest.approx(90.0, abs=1e-9)
