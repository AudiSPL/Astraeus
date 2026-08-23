import pytest


def _body(*, accuracy="approx", uncertainty=5, house_system="placidus"):
    birth = {
        "date": "1984-07-24",
        "time": "05:10:00",
        "time_accuracy": accuracy,
        "birth_time_provenance": "user_supplied",
        "place_label": "Belgrade, Serbia",
    }
    if uncertainty is not None:
        birth["time_uncertainty_minutes"] = uncertainty
    return {
        "birth": birth,
        "settings": {
            "zodiac": "tropical",
            "house_system": house_system,
            "node_type": "true",
            "include_points": ["chiron", "lilith"],
        },
    }


def _packet(client, body):
    r = client.post("/v1/chart-packet", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _angle_aspect(stability, a, b, aspect_type):
    for item in stability["angle_aspects"]:
        if {item["a"], item["b"]} == {a, b} and item["type"] == aspect_type:
            return item
    raise AssertionError(f"missing {a}-{b} {aspect_type}")


def test_birth_time_precision_and_provenance_round_trip(client):
    p = _packet(client, _body(uncertainty=15))
    b = p["birth"]
    assert b["time_accuracy"] == "approx"
    assert b["time_uncertainty_minutes"] == 15
    assert b["birth_time_provenance"] == "user_supplied"
    assert b["birth_time_precision"] == {"accuracy": "approx", "uncertainty_minutes": 15.0}
    assert b["civil_time_status"] == "ok"


def test_settings_echo_includes_points_and_ayanamsha(client):
    body = _body()
    body["settings"]["include_points"] = ["chiron"]
    body["settings"]["zodiac"] = "sidereal"
    body["settings"]["ayanamsha"] = "raman"
    p = _packet(client, body)
    assert p["settings"]["include_points"] == ["chiron"]
    assert p["settings"]["ayanamsha"] == "raman"


def test_reference_asc_boundary_is_found_generically(client):
    s = _packet(client, _body(uncertainty=5))["birth_time_stability"]
    asc = s["asc"]
    assert asc["sign"]["value"] == "Cancer"
    assert asc["sign"]["stable_within_minutes"] == pytest.approx(3.238, abs=0.02)
    assert asc["sign"]["next_transition"]["value"] == "Leo"
    assert asc["sign"]["next_transition"]["offset_minutes"] == pytest.approx(3.238, abs=0.02)
    assert asc["possible_signs_within_declared_uncertainty"] == ["Cancer", "Leo"]
    assert asc["stable_for_declared_uncertainty"] is False


def test_reference_mc_is_stable_across_five_minutes(client):
    s = _packet(client, _body(uncertainty=5))["birth_time_stability"]
    mc = s["mc"]
    assert mc["sign"]["value"] == "Aries"
    assert mc["sign"]["stable_within_minutes"] == pytest.approx(39.866, abs=0.05)
    assert mc["possible_signs_within_declared_uncertainty"] == ["Aries"]
    assert mc["stable_for_declared_uncertainty"] is True


def test_chart_ruler_reports_both_candidates_when_uncertainty_crosses_asc_boundary(client):
    r = _packet(client, _body(uncertainty=5))["birth_time_stability"]["chart_ruler"]
    assert r["value"] == "Moon"
    assert r["stable_within_minutes"] == pytest.approx(3.238, abs=0.02)
    assert r["possible_values_within_declared_uncertainty"] == ["Moon", "Sun"]
    assert r["stable_for_declared_uncertainty"] is False


def test_angle_aspect_orb_range_replaces_false_precision_in_stability_layer(client):
    s = _packet(client, _body(uncertainty=15))["birth_time_stability"]
    pluto_asc = _angle_aspect(s, "Pluto", "ASC", "square")
    assert pluto_asc["nominal_orb"] == pytest.approx(0.002, abs=0.001)
    assert pluto_asc["orb_range"][0] <= 0.01
    assert 2.8 < pluto_asc["orb_range"][1] < 3.1
    assert pluto_asc["orb_sensitivity_deg_per_min"] == pytest.approx(0.194, abs=0.01)
    # Stage 3 removes the unqualified orb from ASC/MC aspects.
    natal = _packet(client, _body(uncertainty=15))["natal"]
    qualified = next(a for a in natal["aspects"] if {a["a"], a["b"]} == {"Pluto", "ASC"})
    assert "orb" not in qualified
    assert qualified["nominal_orb"] == pytest.approx(0.002, abs=0.001)
    assert qualified["orb_range"] == pluto_asc["orb_range"]


def test_exact_time_has_zero_declared_uncertainty(client):
    s = _packet(client, _body(accuracy="exact", uncertainty=None))["birth_time_stability"]
    assert s["birth_time_precision"]["declared_uncertainty_minutes"] == 0.0
    assert s["asc"]["possible_signs_within_declared_uncertainty"] == ["Cancer"]
    assert s["asc"]["stable_for_declared_uncertainty"] is True
    pluto_asc = _angle_aspect(s, "Pluto", "ASC", "square")
    assert pluto_asc["orb_range"] == [pluto_asc["nominal_orb"], pluto_asc["nominal_orb"]]


def test_approx_without_numeric_uncertainty_is_rejected(client):
    r = client.post("/v1/chart-packet", json=_body(accuracy="approx", uncertainty=None))
    assert r.status_code == 422


def test_unknown_precision_remains_unresolved_and_validation_behavior_is_unchanged(client):
    p = _packet(client, _body(accuracy="unknown", uncertainty=None))
    assert p["birth_time_stability"]["birth_time_precision"]["declared_uncertainty_minutes"] is None
    assert p["validation"]["natal_validated"] is False
    assert p["validation"]["validated_for_interpretation"] is False


def test_angle_stability_is_independent_of_house_system(client):
    a = _packet(client, _body(uncertainty=5, house_system="placidus"))["birth_time_stability"]
    b = _packet(client, _body(uncertainty=5, house_system="whole_sign"))["birth_time_stability"]
    assert a["asc"]["sign"]["stable_within_minutes"] == b["asc"]["sign"]["stable_within_minutes"]
    assert a["mc"]["sign"]["stable_within_minutes"] == b["mc"]["sign"]["stable_within_minutes"]
    assert a["chart_ruler"]["possible_values_within_declared_uncertainty"] == b["chart_ruler"]["possible_values_within_declared_uncertainty"]


def test_uncertainty_schema_bounds(client):
    body = _body(uncertainty=-1)
    assert client.post("/v1/chart-packet", json=body).status_code == 422
    body = _body(uncertainty=181)
    assert client.post("/v1/chart-packet", json=body).status_code == 422
