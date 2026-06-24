"""Phase 4 synastry + composite tests."""
import copy
import pytest

from app.core import synastry
from app.core.packet import build_packet, InputError

PRIMARY = {
    "date": "1984-07-24", "time": "05:10:00", "time_accuracy": "exact",
    "place_label": "Belgrade, Serbia",
}
PARTNER = {
    "date": "1990-01-15", "time": "14:30:00", "time_accuracy": "exact",
    "place_label": "New York",
}


def test_circular_midpoint_basic():
    assert synastry._circular_midpoint(10, 20) == pytest.approx(15)


def test_circular_midpoint_handles_zero_wrap():
    # 350 deg and 10 deg are 20 deg apart the short way, around 0 -- midpoint
    # is 0 deg, NOT 180 deg (which plain (a+b)/2 would wrongly give)
    assert synastry._circular_midpoint(350, 10) == pytest.approx(0, abs=1e-9)


def test_circular_midpoint_symmetric():
    a = synastry._circular_midpoint(350, 10)
    b = synastry._circular_midpoint(10, 350)
    assert a == pytest.approx(b)


def test_self_synastry_is_all_exact_conjunctions():
    """Partner = identical chart -> every same-name cross pair must be an
    exact (orb ~0) conjunction. Strongest possible correctness check."""
    req = {"birth": PRIMARY, "synastry": {"enabled": True, "partner": PRIMARY}}
    p = build_packet(req)
    same_name = [a for a in p["synastry"]["cross_aspects"] if a["primary"] == a["partner"]]
    assert len(same_name) >= 13  # 15 minus Chiron if running in Moshier mode
    assert all(a["type"] == "conjunction" and a["orb"] < 0.001 for a in same_name)


def test_self_composite_equals_original_chart():
    """Composite of a chart with itself must equal the original exactly --
    midpoint(x, x) == x for every point."""
    req = {"birth": PRIMARY, "synastry": {"enabled": True, "partner": PRIMARY}}
    p = build_packet(req)
    comp = p["synastry"]["composite"]
    natal_sun = next(b for b in p["natal"]["planets"] if b["name"] == "Sun")["lon"]
    comp_sun = next(b for b in comp["planets"] if b["name"] == "Sun")["lon"]
    assert comp_sun == pytest.approx(natal_sun, abs=1e-6)
    assert comp["angles"]["asc"]["lon"] == pytest.approx(p["natal"]["angles"]["asc"]["lon"], abs=1e-6)
    for i in range(12):
        assert comp["houses"][i]["cusp_lon"] == pytest.approx(p["natal"]["houses"][i]["cusp_lon"], abs=1e-6)


def test_synastry_validated_and_hard_gates_interpretation():
    req = {"birth": PRIMARY, "synastry": {"enabled": True, "partner": PARTNER}}
    p = build_packet(req)
    assert p["validation"]["synastry_validated"] is True
    assert p["validation"]["validated_for_interpretation"] is True


def test_cross_aspects_use_primary_partner_labels():
    req = {"birth": PRIMARY, "synastry": {"enabled": True, "partner": PARTNER}}
    p = build_packet(req)
    for a in p["synastry"]["cross_aspects"]:
        assert "primary" in a and "partner" in a
        assert a["type"] in {"conjunction", "sextile", "square", "trine", "opposition"}


def test_house_overlay_both_directions_present():
    req = {"birth": PRIMARY, "synastry": {"enabled": True, "partner": PARTNER}}
    p = build_packet(req)
    overlay = p["synastry"]["house_overlay"]
    assert "primary_planets_in_partner_houses" in overlay
    assert "partner_planets_in_primary_houses" in overlay
    assert 1 <= overlay["primary_planets_in_partner_houses"]["Sun"] <= 12


def test_house_overlay_and_composite_are_optional():
    req = {"birth": PRIMARY, "synastry": {
        "enabled": True, "partner": PARTNER, "house_overlay": False, "include_composite": False,
    }}
    p = build_packet(req)
    assert p["synastry"]["house_overlay"] is None
    assert p["synastry"]["composite"] is None
    assert p["validation"]["synastry_validated"] is True  # still valid, just narrower output


def test_unknown_partner_city_raises_input_error():
    bad_partner = {"date": "1990-01-15", "time": "14:30:00", "city": "Atlantis"}
    req = {"birth": PRIMARY, "synastry": {"enabled": True, "partner": bad_partner}}
    with pytest.raises(InputError):
        build_packet(req)


def test_partner_approx_time_warns():
    req = {"birth": PRIMARY, "synastry": {
        "enabled": True, "partner": {**PARTNER, "time_accuracy": "approx"},
    }}
    p = build_packet(req)
    assert any("Partner birth time" in w for w in p["warnings"])


def test_hard_gate_blocks_when_synastry_not_complete():
    from app.core.validate import build
    v = build(True, "exact", False, False, False, False, False, False, True, False)
    assert v["validated_for_interpretation"] is False
    assert "synastry data missing" in v["reasons"]
