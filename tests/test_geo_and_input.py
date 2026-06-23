"""Geo resolution and input-error handling."""
from app.core import geo


def test_belgrade_resolves():
    assert geo.resolve("Belgrade, Serbia") == (44.80401, 20.46513, "Europe/Belgrade")
    assert geo.resolve("belgrade") is not None


def test_unknown_city_is_none():
    assert geo.resolve("Atlantis") is None
    assert geo.resolve(None) is None


def test_explicit_coords_bypass_table(client):
    req = {
        "birth": {
            "date": "1984-07-24", "time": "05:10:00", "time_accuracy": "exact",
            "latitude": 44.80401, "longitude": 20.46513, "timezone": "Europe/Belgrade",
        }
    }
    p = client.post("/v1/chart-packet", json=req).json()
    assert p["birth"]["timezone"] == "Europe/Belgrade"
    assert p["natal"]["angles"]["asc"]["sign"] == "Cancer"


def test_unresolvable_location_returns_422(client):
    req = {"birth": {"date": "1984-07-24", "time": "05:10:00", "place_label": "Atlantis"}}
    r = client.post("/v1/chart-packet", json=req)
    assert r.status_code == 422
