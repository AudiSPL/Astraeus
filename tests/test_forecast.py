"""Phase 3 forecast scanner tests. Eclipse dates are checked against published
2026/2027 calendar values (NASA/USNO), not just internal self-consistency --
if these drift, the ephemeris/eclipse-flag setup is wrong, not just this test.
"""
import swisseph as swe

from app.core import forecast
from app.core.transits import FORECAST_MOVERS

NATAL = {
    "Sun": {"name": "Sun", "lon": 121.4},
    "Moon": {"name": "Moon", "lon": 65.3333},
    "Mercury": {"name": "Mercury", "lon": 147.3333},
    "Venus": {"name": "Venus", "lon": 131.9167},
    "Mars": {"name": "Mars", "lon": 228.7},
    "Jupiter": {"name": "Jupiter", "lon": 275.1333},
    "Saturn": {"name": "Saturn", "lon": 219.7833},
    "Uranus": {"name": "Uranus", "lon": 249.7833},
    "Neptune": {"name": "Neptune", "lon": 269.2167},
    "Pluto": {"name": "Pluto", "lon": 209.3667},
    "Node": {"name": "Node", "lon": 65.1},
    "Chiron": {"name": "Chiron", "lon": 67.1167},
    "Lilith": {"name": "Lilith", "lon": 355.1667},
    "ASC": {"name": "ASC", "lon": 119.3667},
    "MC": {"name": "MC", "lon": 10.8667},
}


def _jd(y, m, d):
    return swe.julday(y, m, d, 0.0)


def test_eclipses_match_published_2026_2027_dates():
    jd0, jd1 = _jd(2026, 6, 20), _jd(2027, 6, 20)
    ev = forecast.eclipses(NATAL, jd0, jd1)
    found = {(e["eclipse_type"], e["kind"], e["date"][:10]) for e in ev}
    # NASA/USNO published 2026-2027 eclipse calendar
    assert ("solar", "total", "2026-08-12") in found
    assert ("lunar", "partial", "2026-08-28") in found
    assert ("solar", "annular", "2027-02-06") in found
    assert ("lunar", "penumbral", "2027-02-20") in found


def test_eclipse_records_have_required_fields():
    jd0, jd1 = _jd(2026, 6, 20), _jd(2027, 6, 20)
    for e in forecast.eclipses(NATAL, jd0, jd1):
        assert e["julian_day_ut"] > 0
        assert 0 <= e["ecliptic_lon"] < 360
        assert e["eclipse_type"] in ("solar", "lunar")
        for h in e["natal_hits"]:
            assert h["orb"] <= forecast.ECLIPSE_ORB
            assert h["type"] in ("conjunction", "opposition", "square")


def test_mover_hits_only_uses_forecast_movers():
    jd0, jd1 = _jd(2026, 6, 20), _jd(2026, 9, 20)
    hits = forecast.mover_hits(NATAL, jd0, jd1, "tropical")
    assert hits, "expected at least one outer-planet hit in this window"
    assert all(h["transit"] in FORECAST_MOVERS for h in hits)


def test_mover_hits_chronologically_sorted():
    jd0, jd1 = _jd(2026, 6, 20), _jd(2027, 6, 20)
    hits = forecast.mover_hits(NATAL, jd0, jd1, "tropical")
    jds = [h["julian_day_ut"] for h in hits]
    assert jds == sorted(jds)


def test_stations_never_repeat_direction_back_to_back():
    jd0, jd1 = _jd(2026, 6, 20), _jd(2027, 6, 20)
    by_planet = {}
    for s in forecast.station_events(jd0, jd1, "tropical"):
        by_planet.setdefault(s["planet"], []).append(s["direction"])
    for planet, seq in by_planet.items():
        for i in range(1, len(seq)):
            assert seq[i] != seq[i - 1], f"{planet} stationed {seq[i]} twice in a row"


def test_scan_returns_expected_shape():
    jd0, jd1 = _jd(2026, 6, 20), _jd(2026, 9, 20)
    result = forecast.scan(NATAL, jd0, jd1, "tropical")
    assert set(result.keys()) == {
        "period", "eclipse_orb", "movers_used", "transits", "stations", "eclipses"
    }
    assert result["movers_used"] == FORECAST_MOVERS


def test_resolve_forecast_movers_include_inner():
    from app.core.transits import resolve_forecast_movers, FORECAST_INNER

    movers = resolve_forecast_movers({"enabled": True, "include_inner": True})
    assert movers[:2] == FORECAST_INNER
    assert movers[2:] == FORECAST_MOVERS


def test_forecast_include_inner_via_api(client):
    req = {
        "birth": {"date": "1984-07-24", "time": "05:10:00", "time_accuracy": "exact",
                  "place_label": "Belgrade, Serbia"},
        "forecast": {"enabled": True, "start_date": "2026-06-20", "months": 3, "include_inner": True},
    }
    p = client.post("/v1/chart-packet", json=req).json()
    assert p["forecast"]["movers_used"][:2] == ["Sun", "Mars"]
    hits = p["forecast"]["transits"]
    assert any(h["transit"] in ("Sun", "Mars") for h in hits)
    assert not any("Jupiter-Pluto" in w and "excluded by design" in w for w in p["warnings"])
    assert any("Sun and Mars" in w for w in p["warnings"])
