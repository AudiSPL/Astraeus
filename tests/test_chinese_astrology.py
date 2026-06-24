"""Chinese astrology layer tests."""
import copy

import pytest

from app.core import chinese_astrology
from app.core.packet import build_packet

BIRTH = {
    "date": "1990-06-15",
    "time": "12:00:00",
    "time_accuracy": "exact",
    "place_label": "Belgrade, Serbia",
}


@pytest.fixture
def base_req():
    return {
        "birth": copy.deepcopy(BIRTH),
        "settings": {"zodiac": "tropical", "house_system": "placidus", "node_type": "true"},
    }


def test_1984_jia_zi_rat():
    block = chinese_astrology.calculate_chinese_astrology("1984-07-24")
    pillar = block["year_pillar"]
    assert pillar["stem"]["name"] == "Jia"
    assert pillar["branch"]["name"] == "Zi"
    assert pillar["combined"]["characters"] == "甲子"
    assert pillar["branch"]["animal"] == "Rat"


def test_1990_geng_wu_horse():
    block = chinese_astrology.calculate_chinese_astrology("1990-01-15")
    pillar = block["year_pillar"]
    assert pillar["stem"]["name"] == "Geng"
    assert pillar["branch"]["name"] == "Wu"
    assert pillar["combined"]["characters"] == "庚午"
    assert pillar["branch"]["animal"] == "Horse"
    assert block["five_elements_presence"] == {
        "Wood": 0, "Fire": 1, "Earth": 0, "Metal": 1, "Water": 0,
    }
    assert block["yin_yang_presence"] == {"Yin": 0, "Yang": 2}


def test_2000_geng_chen_dragon():
    block = chinese_astrology.calculate_chinese_astrology("2000-03-01")
    pillar = block["year_pillar"]
    assert pillar["stem"]["name"] == "Geng"
    assert pillar["branch"]["name"] == "Chen"
    assert pillar["combined"]["characters"] == "庚辰"
    assert pillar["branch"]["animal"] == "Dragon"


def test_year_boundary_warning_present():
    block = chinese_astrology.calculate_chinese_astrology("1990-01-15")
    assert chinese_astrology.YEAR_BOUNDARY_WARNING in block["warnings"]


def test_include_false_omits_block(base_req, client):
    r = client.post("/v1/chart-packet", json=base_req).json()
    assert r.get("chinese_astrology") is None


def test_include_true_returns_block(base_req, client):
    base_req["include_chinese_astrology"] = True
    r = client.post("/v1/chart-packet", json=base_req).json()
    ca = r["chinese_astrology"]
    assert ca is not None
    assert ca["system"] == "chinese_zodiac_basic"
    assert ca["year_pillar"]["combined"]["characters"] == "庚午"
    assert chinese_astrology.YEAR_BOUNDARY_WARNING in ca["warnings"]
    assert r["validation"]["chinese_astrology_validated"] is True
    assert r["validation"]["validated_for_interpretation"] is True


def test_build_packet_direct(base_req):
    block = build_packet({**base_req, "include_chinese_astrology": True})
    assert block["chinese_astrology"]["year_pillar"]["branch"]["animal"] == "Horse"
