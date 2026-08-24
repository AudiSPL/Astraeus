"""Synastry and composite invariants.

These import app.core.synastry directly rather than going through the
packet, so they do not depend on where the composite block lands in the
response shape.

The four formerly strict-xfail cases in this file are now ordinary regression
tests. The remaining OPEN item is a methodological choice with no single
correct answer and stays documented as a passing test rather than a bug.
"""

from __future__ import annotations

import pytest
from app.core.synastry import (
    _circular_midpoint,
    composite_angles,
    composite_houses,
    cross_aspects,
)

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
    """Compared as longitudes, not as plain floats."""
    for a, b in [(12.5, 200.0), (359.9, 0.1), (45.0, 46.0), (0.0, 90.0), (271.3, 0.0)]:
        forward, reverse = _circular_midpoint(a, b), _circular_midpoint(b, a)
        assert _angular_delta(forward, reverse) < 1e-9, f"{a},{b}: {forward} vs {reverse}"


def test_cross_aspects_leave_applying_null_without_speeds():
    a = {"Sun": {"name": "Sun", "lon": 121.400681}}
    b = {"Moon": {"name": "Moon", "lon": 121.5}}
    contacts = cross_aspects(a, b)
    assert contacts, "expected a conjunction within orb"
    assert all(c["applying"] is None for c in contacts)


# --- fixed v1 defects, now pinned as ordinary regressions ------------------


def test_midpoint_returns_a_canonical_longitude():
    """A longitude belongs in [0, 360), including at the float wrap edge."""
    for a, b in [(0.1, 359.9), (359.9, 0.1), (180.05, 179.95)]:
        lon = _circular_midpoint(a, b)
        assert 0.0 <= lon < 360.0, f"{a},{b} -> {lon}"


def test_whole_sign_composite_cusps_stay_on_sign_boundaries():
    angles = composite_angles(
        {"asc": {"lon": PRIMARY_ASC}, "mc": {"lon": 10.87234}},
        {"asc": {"lon": PARTNER_ASC}, "mc": {"lon": 30.0}},
    )
    composite = composite_houses(
        _whole_sign_cusps(PRIMARY_ASC),
        _whole_sign_cusps(PARTNER_ASC),
        house_system="whole_sign",
        composite_asc_lon=angles["asc"]["lon"],
    )
    offsets = sorted({round(h["cusp_lon"] % 30, 6) for h in composite})
    assert offsets == [0.0], f"cusps sit at {offsets} degrees into their signs"


def test_whole_sign_composite_house_one_holds_the_ascendant():
    angles = composite_angles(
        {"asc": {"lon": PRIMARY_ASC}, "mc": {"lon": 10.87234}},
        {"asc": {"lon": PARTNER_ASC}, "mc": {"lon": 30.0}},
    )
    houses = composite_houses(
        _whole_sign_cusps(PRIMARY_ASC),
        _whole_sign_cusps(PARTNER_ASC),
        house_system="whole_sign",
        composite_asc_lon=angles["asc"]["lon"],
    )
    assert _sign_index(houses[0]["cusp_lon"]) == _sign_index(angles["asc"]["lon"]), (
        f"composite ASC {angles['asc']['lon']:.4f} but house 1 cusp {houses[0]['cusp_lon']:.4f}"
    )


def test_cross_aspects_refuse_applying_even_when_given_speeds():
    """Cross-chart positions come from different natal epochs.

    Applying/separating describes convergence at one instant, so synastry
    contacts deliberately carry applying:null even if a future caller passes
    full body dictionaries containing speed fields.
    """
    a = {"Sun": {"name": "Sun", "lon": 121.400681, "speed": 0.955291}}
    b = {"Moon": {"name": "Moon", "lon": 121.5, "speed": 12.89052}}
    for contact in cross_aspects(a, b):
        assert contact["applying"] is None, contact


# --- open methodology, not a bug -------------------------------------------


def test_midpoint_is_antipodal_across_exact_opposition():
    """Documented, deliberately not treated as a defect.

    At 179.99 degrees apart the shorter arc runs one way; at 180.01 it runs
    the other, so the two midpoints are antipodal. Given shorter-arc semantics
    that jump is forced. Birth-time uncertainty near this boundary belongs in
    sensitivity/ambiguity handling rather than a fake scalar continuity fix.
    """
    below = _circular_midpoint(0.0, 179.99)
    above = _circular_midpoint(0.0, 180.01)
    assert _angular_delta(below, above) == pytest.approx(180.0, abs=0.05)
    assert _circular_midpoint(0.0, 180.0) == pytest.approx(90.0, abs=1e-9)
