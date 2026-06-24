"""Phase 4 solar return tests."""
import copy
import swisseph as swe
import pytest

from app.core import solar_return, ephemeris
from app.core.packet import build_packet, InputError

NATAL_SUN_LON = 121.4006  # Leo 1 24', golden chart

DEFAULT_PROFILE = {
    "birth": {
        "date": "1984-07-24",
        "time": "05:10:00",
        "time_accuracy": "exact",
        "place_label": "Belgrade, Serbia",
    },
    "settings": {"zodiac": "tropical", "house_system": "placidus", "node_type": "true"},
}


def test_find_return_jd_lands_on_natal_sun_degree():
    flag = ephemeris.base_flag("tropical")
    jd = solar_return.find_return_jd(NATAL_SUN_LON, 2026, flag)
    lon, _ = ephemeris.position(jd, swe.SUN, flag)
    assert abs(lon - NATAL_SUN_LON) < 0.0001


def test_find_return_jd_lands_near_birthday():
    flag = ephemeris.base_flag("tropical")
    jd = solar_return.find_return_jd(NATAL_SUN_LON, 2026, flag)
    y, mo, d, _ = swe.revjul(jd)
    assert y == 2026 and mo == 7 and 22 <= d <= 25


def test_solar_return_default_uses_natal_location():
    req = copy.deepcopy(DEFAULT_PROFILE)
    req["solar_return"] = {"year": 2026}
    p = build_packet(req)
    assert p["validation"]["solar_return_validated"] is True
    assert p["validation"]["validated_for_interpretation"] is True
    assert p["solar_return"]["location"]["relocated"] is False
    assert p["solar_return"]["location"]["latitude"] == pytest.approx(44.80401)


def test_solar_return_relocated_changes_angles_not_moment():
    req = copy.deepcopy(DEFAULT_PROFILE)
    req["solar_return"] = {"year": 2026}
    natal_loc = build_packet(req)["solar_return"]

    req["solar_return"] = {"year": 2026, "city": "New York"}
    relocated = build_packet(req)["solar_return"]

    assert relocated["location"]["relocated"] is True
    assert relocated["moment_utc"] == natal_loc["moment_utc"]
    assert relocated["angles"]["asc"]["lon"] != natal_loc["angles"]["asc"]["lon"]
    assert any("relocated" in w.lower() for w in
              build_packet(req)["warnings"])


def test_solar_return_unknown_city_raises():
    req = copy.deepcopy(DEFAULT_PROFILE)
    req["solar_return"] = {"year": 2026, "city": "Atlantis"}
    with pytest.raises(InputError):
        build_packet(req)


def test_solar_return_sun_exactly_conjunct_natal_sun():
    req = copy.deepcopy(DEFAULT_PROFILE)
    req["solar_return"] = {"year": 2026}
    p = build_packet(req)
    hits = [a for a in p["solar_return"]["aspects_to_natal"]
           if a["solar_return"] == "Sun" and a["natal"] == "Sun"]
    assert len(hits) == 1
    assert hits[0]["type"] == "conjunction"
    assert hits[0]["orb"] < 0.001


def test_aspects_to_natal_respects_sr_orb():
    req = copy.deepcopy(DEFAULT_PROFILE)
    req["solar_return"] = {"year": 2026}
    p = build_packet(req)
    for a in p["solar_return"]["aspects_to_natal"]:
        assert a["orb"] <= solar_return.SR_ORB


def test_hard_gate_blocks_when_not_complete():
    from app.core.validate import build
    v = build(True, "exact", False, False, False, False, True, False)
    assert v["validated_for_interpretation"] is False
    assert "solar return data missing" in v["reasons"]
