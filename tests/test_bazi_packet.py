from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _request():
    return {
        "birth": {
            "date": "1984-07-24",
            "time": "05:10:00",
            "time_accuracy": "exact",
            "latitude": 44.80401,
            "longitude": 20.46513,
            "timezone": "Europe/Belgrade",
            "place_label": "Belgrade, Serbia",
        },
        "settings": {
            "zodiac": "tropical",
            "house_system": "placidus",
            "node_type": "true",
            "include_points": ["chiron", "lilith"],
        },
    }


def test_bazi_is_opt_in_and_does_not_change_legacy_packet_shape():
    response = client.post("/v1/chart-packet", json=_request())
    assert response.status_code == 200
    assert "bazi" not in response.json()


def test_bazi_four_pillars_are_exposed_in_chart_packet():
    req = _request()
    req["bazi"] = {
        "enabled": True,
        "hour_pillar_time_basis": "local_mean_solar_time",
        "late_zi_advances_day": False,
        "gender": "male",
    }
    response = client.post("/v1/chart-packet", json=req)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["validation"]["bazi_validated"] is True
    assert [p["combined"]["name"] for p in data["bazi"]["four_pillars"]] == [
        "Jia Zi", "Xin Wei", "Ji Wei", "Bing Yin"
    ]
    assert data["bazi"]["day_master"] == "Ji"
    assert data["bazi"]["luck_pillars"]["available"] is True
    assert data["bazi"]["hour_pillar_sensitivity"]["school_dependent"] is True
