"""Transit snapshot + the root-finding utilities the forecast layer reuses."""
import copy
import swisseph as swe
from app.core import ephemeris, transits
from tests.conftest import DEFAULT_PROFILE


def test_transit_snapshot_present(client):
    req = copy.deepcopy(DEFAULT_PROFILE)
    req["transit"] = {"date": "2026-06-19", "time": "12:00:00", "timezone": "Europe/London"}
    p = client.post("/v1/chart-packet", json=req).json()
    assert p["transits"] is not None
    assert len(p["transits"]["planets"]) >= 8
    assert p["validation"]["transits_validated"] is True
    assert p["validation"]["validated_for_interpretation"] is True
    for a in p["transits"]["aspects_to_natal"]:
        assert a["type"] in {"conjunction", "sextile", "square", "trine", "opposition"}
        assert "applying" in a


def test_forecast_request_validates_and_populates(client):
    """Phase 3: forecast is now a hard gate (was a soft warning in Phase 2).
    Pinned to a known window so the eclipse count assertion is deterministic --
    this range contains the published Aug 12 2026 total solar, Aug 28 2026
    partial lunar, Feb 6 2027 annular solar, and Feb 20 2027 penumbral lunar
    eclipses (NASA/USNO)."""
    req = copy.deepcopy(DEFAULT_PROFILE)
    req["forecast"] = {"enabled": True, "start_date": "2026-06-20", "months": 12}
    p = client.post("/v1/chart-packet", json=req).json()
    assert p["validation"]["forecast_validated"] is True
    assert p["validation"]["validated_for_interpretation"] is True
    assert p["forecast"] is not None
    assert p["forecast"]["period"]["start"].startswith("2026-06-20")
    assert len(p["forecast"]["eclipses"]) >= 1
    assert not any("not implemented" in w.lower() for w in p["warnings"])


def test_exact_hits_solar_return():
    """Transiting Sun conjunct natal Sun must occur once per year, ~the birthday."""
    ephemeris.init()
    flag = ephemeris.base_flag("tropical")
    natal_sun_lon = 121.4006  # Leo 1 24'
    jd0 = swe.julday(2026, 1, 1, 0.0, swe.GREG_CAL)
    jd1 = swe.julday(2026, 12, 31, 0.0, swe.GREG_CAL)
    hits = transits.exact_hits(swe.SUN, natal_sun_lon, 0, flag, jd0, jd1, step=1.0)
    assert len(hits) == 1
    y, mo, d, _ = swe.revjul(hits[0], swe.GREG_CAL)
    assert mo == 7 and 22 <= d <= 25   # solar return ~ 23-24 July


def test_stations_jupiter_in_window():
    """Jupiter has at least one station in any ~13-month window."""
    ephemeris.init()
    flag = ephemeris.base_flag("tropical")
    jd0 = swe.julday(2026, 1, 1, 0.0, swe.GREG_CAL)
    jd1 = swe.julday(2027, 2, 1, 0.0, swe.GREG_CAL)
    st = transits.stations(swe.JUPITER, flag, jd0, jd1, step=2.0)
    assert len(st) >= 1
    assert st[0]["direction"] in {"retrograde", "direct"}
