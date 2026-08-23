from __future__ import annotations

import pytest


def _body(*, accuracy="approx", uncertainty=5):
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
            "house_system": "placidus",
            "node_type": "true",
            "include_points": ["chiron", "lilith"],
        },
    }


def _packet(client, **kwargs):
    r = client.post("/v1/chart-packet", json=_body(**kwargs))
    assert r.status_code == 200, r.text
    return r.json()


def test_stage3_contract_is_explicit(client):
    p = _packet(client)
    assert p["meta"]["output_contract_version"] == "qualified_birth_time_v1"
    assert p["natal"]["birth_time_contract"]["version"] == "qualified_birth_time_v1"
    assert p["validation"]["birth_time_qualified_output"] is True


def test_reference_unstable_fields_no_longer_expose_resolved_scalars(client):
    p = _packet(client, uncertainty=5)
    natal = p["natal"]

    ruler = natal["chart_ruler"]
    assert ruler["value"] is None
    assert ruler["nominal"] == "Moon"
    assert ruler["possible_values"] == ["Moon", "Sun"]

    asc = natal["angles"]["asc"]
    assert "lon" not in asc and "deg_in_sign" not in asc
    assert asc["sign"]["value"] is None
    assert asc["sign"]["possible_values"] == ["Cancer", "Leo"]
    assert asc["nominal_lon"] == pytest.approx(119.373963, abs=1e-6)

    mars = next(x for x in natal["planets"] if x["name"] == "Mars")
    assert mars["house"]["value"] is None
    assert mars["house"]["nominal"] == 5
    assert mars["house"]["possible_values"] == [5, 4]

    h1 = natal["houses"][0]
    assert "cusp_lon" not in h1
    assert h1["sign"]["value"] is None
    assert h1["sign"]["possible_values"] == ["Cancer", "Leo"]


def test_angle_aspects_remove_plain_orb_strength_and_score(client):
    p = _packet(client, uncertainty=15)
    a = next(x for x in p["natal"]["aspects"] if {x["a"], x["b"]} == {"Pluto", "ASC"})
    assert "orb" not in a
    assert "strength" not in a
    assert "score" not in a
    assert a["nominal_orb"] == pytest.approx(0.002, abs=0.001)
    assert a["orb_range"][0] <= 0.01
    assert 2.8 < a["orb_range"][1] < 3.1
    assert a["birth_time_sensitive"] is True


def test_planet_to_planet_aspects_keep_v1_shape(client):
    p = _packet(client, uncertainty=15)
    a = next(x for x in p["natal"]["aspects"] if x["a"] == "Sun" and x["b"] == "Pluto")
    assert "orb" in a and "strength" in a and "score" in a
    assert "nominal_orb" not in a


def test_exact_time_uses_same_contract_but_resolves_values(client):
    p = _packet(client, accuracy="exact", uncertainty=0)
    assert p["natal"]["chart_ruler"]["value"] == "Moon"
    assert p["natal"]["angles"]["asc"]["sign"]["value"] == "Cancer"
    mars = next(x for x in p["natal"]["planets"] if x["name"] == "Mars")
    assert mars["house"]["value"] == 5
    assert p["validation"]["time_dependent_natal_fields_resolved"] is True


def test_unknown_time_is_qualified_but_still_blocks_interpretation(client):
    p = _packet(client, accuracy="unknown", uncertainty=None)
    assert p["validation"]["validated_for_interpretation"] is False
    assert p["validation"]["natal_validated"] is False
    assert p["validation"]["time_dependent_natal_fields_resolved"] is None
    assert p["natal"]["chart_ruler"]["value"] is None
    assert p["natal"]["angles"]["asc"]["sign"]["value"] is None
    assert p["natal"]["houses"][0]["sign"]["value"] is None
    assert next(x for x in p["natal"]["planets"] if x["name"] == "Mars")["house"]["value"] is None
    assert any("planetary longitude stability is not yet sampled" in w for w in p["warnings"])


def test_schema_default_is_unknown_and_therefore_not_interpretable(client):
    body = {"birth": {"date": "1984-07-24", "time": "05:10:00", "place_label": "Belgrade, Serbia"}}
    r = client.post("/v1/chart-packet", json=body)
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["birth"]["time_accuracy"] == "unknown"
    assert p["validation"]["validated_for_interpretation"] is False
    assert p["natal"]["chart_ruler"]["value"] is None


@pytest.mark.parametrize("payload", [
    {"time_accuracy": "approx"},
    {"time_accuracy": "approx", "time_uncertainty_minutes": 0},
    {"time_accuracy": "exact", "time_uncertainty_minutes": 5},
    {"time_accuracy": "unknown", "time_uncertainty_minutes": 5},
])
def test_incoherent_precision_contract_is_rejected_by_api(client, payload):
    birth = {"date": "1984-07-24", "time": "05:10:00", "place_label": "Belgrade, Serbia", **payload}
    r = client.post("/v1/chart-packet", json={"birth": birth})
    assert r.status_code == 422


def test_bounded_approximate_precision_is_accepted(client):
    r = client.post("/v1/chart-packet", json=_body(accuracy="approx", uncertainty=0.1))
    assert r.status_code == 200, r.text


def test_direct_build_packet_enforces_precision_contract():
    from app.core.packet import InputError, build_packet
    body = _body(accuracy="approx", uncertainty=None)
    with pytest.raises(InputError):
        build_packet(body)


def test_ambiguous_civil_birth_time_cannot_be_marked_resolved_even_if_accuracy_exact(client):
    body = {
        "birth": {
            "date": "1984-09-30", "time": "02:30:00", "time_accuracy": "exact",
            "latitude": 44.80401, "longitude": 20.46513, "timezone": "Europe/Belgrade",
        }
    }
    r = client.post("/v1/chart-packet", json=body)
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["birth"]["civil_time_status"] == "ambiguous"
    assert p["validation"]["natal_validated"] is False
    assert p["validation"]["validated_for_interpretation"] is False
    assert p["validation"]["time_dependent_natal_fields_resolved"] is None
    assert p["natal"]["angles"]["asc"]["sign"]["value"] is None
