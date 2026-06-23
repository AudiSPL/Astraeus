"""Golden-master test. These values were verified directly against the Swiss
Ephemeris engine. If a refactor, a tzdata bump, or a cusp-indexing change ever
shifts them, this test fails loudly. That is the point.
"""


def _planet(packet, name):
    return next(p for p in packet["natal"]["planets"] if p["name"] == name)


def test_timezone_and_jd(client, default_profile):
    p = client.post("/v1/chart-packet", json=default_profile).json()
    b = p["birth"]
    assert b["utc"] == "1984-07-24T03:10:00+00:00"
    assert b["utc_offset"] == "+02:00"
    assert b["dst_active"] is True
    assert abs(b["julian_day_ut"] - 2445905.6319444) < 1e-5


def test_angles_and_ruler(client, default_profile):
    p = client.post("/v1/chart-packet", json=default_profile).json()
    asc = p["natal"]["angles"]["asc"]
    mc = p["natal"]["angles"]["mc"]
    # ASC 29 22' Cancer — the knife-edge case; guards birth-time/tz regressions
    assert asc["sign"] == "Cancer"
    assert abs(asc["deg_in_sign"] - 29.37) < 0.05
    assert mc["sign"] == "Aries"
    assert abs(mc["deg_in_sign"] - 10.87) < 0.05
    assert p["natal"]["chart_ruler"] == "Moon"


def test_planet_positions(client, default_profile):
    p = client.post("/v1/chart-packet", json=default_profile).json()
    expect = {
        "Sun": ("Leo", 1.40), "Moon": ("Gemini", 5.34), "Mercury": ("Leo", 27.34),
        "Venus": ("Leo", 11.92), "Mars": ("Scorpio", 18.71), "Jupiter": ("Capricorn", 5.15),
        "Saturn": ("Scorpio", 9.80), "Uranus": ("Sagittarius", 9.79),
        "Neptune": ("Sagittarius", 29.22), "Pluto": ("Libra", 29.38),
    }
    for name, (sign, deg) in expect.items():
        pl = _planet(p, name)
        assert pl["sign"] == sign, f"{name}: {pl['sign']} != {sign}"
        assert abs(pl["deg_in_sign"] - deg) < 0.05, f"{name}: {pl['deg_in_sign']} vs {deg}"


def test_retrogrades(client, default_profile):
    p = client.post("/v1/chart-packet", json=default_profile).json()
    retro = set(p["natal"]["retrogrades"])
    assert {"Jupiter", "Uranus", "Neptune"} <= retro
    assert "Sun" not in retro and "Moon" not in retro


def test_chiron_present_in_swiss_mode(client, default_profile):
    p = client.post("/v1/chart-packet", json=default_profile).json()
    if p["meta"]["ephemeris"] == "swiss_ephemeris":
        ch = _planet(p, "Chiron")
        assert ch["sign"] == "Gemini"          # 7 07' Gemini
        assert abs(ch["deg_in_sign"] - 7.13) < 0.1


def test_houses_complete_and_h1_is_asc(client, default_profile):
    p = client.post("/v1/chart-packet", json=default_profile).json()
    houses = p["natal"]["houses"]
    assert len(houses) == 12
    asc = p["natal"]["angles"]["asc"]["lon"]
    assert abs(houses[0]["cusp_lon"] - asc) < 1e-6   # Placidus H1 cusp == ASC


def test_validation_clean(client, default_profile):
    p = client.post("/v1/chart-packet", json=default_profile).json()
    v = p["validation"]
    assert v["natal_validated"] is True
    assert v["validated_for_interpretation"] is True


def test_unknown_birth_time_blocks(client, default_profile):
    default_profile["birth"]["time_accuracy"] = "unknown"
    p = client.post("/v1/chart-packet", json=default_profile).json()
    v = p["validation"]
    assert v["natal_validated"] is False
    assert v["validated_for_interpretation"] is False
    assert any("birth time unknown" in r for r in v["reasons"])
