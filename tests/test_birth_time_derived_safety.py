from __future__ import annotations


def _base_birth(accuracy="approx", uncertainty=5):
    b = {
        "date": "1984-07-24", "time": "05:10:00",
        "time_accuracy": accuracy, "place_label": "Belgrade, Serbia",
    }
    if uncertainty is not None:
        b["time_uncertainty_minutes"] = uncertainty
    return b


def _full_request():
    return {
        "birth": _base_birth(),
        "settings": {"zodiac": "tropical", "house_system": "placidus", "node_type": "true"},
        "transit": {"date": "2026-08-22", "time": "12:00:00", "timezone": "UTC"},
        "progressions": {"date": "2026-08-22"},
        "forecast": {"enabled": True, "start_date": "2026-08-22", "end_date": "2027-08-22", "include_inner": True},
        "solar_return": {"year": 2026},
    }


def test_primary_angle_relations_move_to_audit_only_arrays(client):
    r = client.post("/v1/chart-packet", json=_full_request())
    assert r.status_code == 200, r.text
    p = r.json()

    assert all(x.get("natal") not in {"ASC", "MC"} for x in p["transits"]["aspects_to_natal"])
    assert p["transits"]["birth_time_sensitive_nominal_aspects"]
    assert all(x["interpretation_status"] == "audit_only_nominal" for x in p["transits"]["birth_time_sensitive_nominal_aspects"])

    for section in ("secondary", "solar_arc"):
        part = p["progressions"][section]
        assert all(x.get("natal") not in {"ASC", "MC"} and x.get("directed") not in {"ASC", "MC"} for x in part["aspects_to_natal"])
        assert part["birth_time_dependency"]["geometry_resolved"] is False

    assert all(x.get("natal") not in {"ASC", "MC"} for x in p["forecast"]["transits"])
    assert "birth_time_sensitive_nominal_transits" in p["forecast"]
    for eclipse in p["forecast"]["eclipses"]:
        assert all(x.get("natal") not in {"ASC", "MC"} for x in eclipse["natal_hits"])
        assert "birth_time_sensitive_nominal_hits" in eclipse

    assert all(
        x.get("natal") not in {"ASC", "MC"} and x.get("solar_return") not in {"ASC", "MC"}
        for x in p["solar_return"]["aspects_to_natal"]
    )
    assert p["solar_return"]["birth_time_dependency"]["geometry_resolved"] is False


def test_exact_birth_keeps_derived_angle_relations_in_normal_arrays(client):
    req = _full_request()
    req["birth"] = _base_birth("exact", 0)
    r = client.post("/v1/chart-packet", json=req)
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["transits"]["birth_time_sensitive_nominal_aspects"] == []
    assert any(x.get("natal") in {"ASC", "MC"} for x in p["transits"]["aspects_to_natal"])
    assert p["solar_return"]["birth_time_dependency"]["geometry_resolved"] is True


def _syn_req(primary_accuracy="approx", primary_u=5, partner_accuracy="approx", partner_u=5):
    partner = {
        "date": "1985-09-19", "time": "12:00:00",
        "time_accuracy": partner_accuracy,
        "latitude": 44.27, "longitude": 19.89, "timezone": "Europe/Belgrade",
    }
    if partner_u is not None:
        partner["time_uncertainty_minutes"] = partner_u
    return {
        "birth": _base_birth(primary_accuracy, primary_u),
        "settings": {"zodiac": "tropical", "house_system": "placidus", "node_type": "true"},
        "synastry": {"enabled": True, "partner": partner, "include_composite": True, "house_overlay": True},
    }


def test_synastry_partner_is_qualified_and_geometry_is_suppressed_when_approx(client):
    r = client.post("/v1/chart-packet", json=_syn_req())
    assert r.status_code == 200, r.text
    p = r.json()
    syn = p["synastry"]
    assert syn["partner"]["birth_time_contract"]["version"] == "qualified_birth_time_v1"
    assert syn["partner_birth_time_stability"]["birth_time_precision"]["declared_uncertainty_minutes"] == 5
    assert syn["house_overlay"] is None
    assert syn["composite"] is None
    assert syn["time_geometry_status"]["resolved"] is False
    assert all(x.get("primary") not in {"ASC", "MC"} and x.get("partner") not in {"ASC", "MC"} for x in syn["cross_aspects"])
    assert syn["birth_time_sensitive_nominal_cross_aspects"]


def test_exact_synastry_keeps_overlay_and_composite(client):
    r = client.post("/v1/chart-packet", json=_syn_req("exact", 0, "exact", 0))
    assert r.status_code == 200, r.text
    syn = r.json()["synastry"]
    assert syn["house_overlay"] is not None
    assert syn["composite"] is not None
    assert syn["time_geometry_status"]["resolved"] is True
    assert syn["birth_time_sensitive_nominal_cross_aspects"] == []


def test_unknown_partner_blocks_synastry_validation(client):
    r = client.post("/v1/chart-packet", json=_syn_req("exact", 0, "unknown", None))
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["validation"]["synastry_validated"] is False
    assert p["validation"]["validated_for_interpretation"] is False
    assert any("partner birth time unknown" in reason for reason in p["validation"]["reasons"])


def test_ambiguous_partner_civil_time_blocks_synastry_even_if_marked_exact(client):
    req = {
        "birth": _base_birth("exact", 0),
        "synastry": {
            "enabled": True,
            "partner": {
                "date": "1984-09-30", "time": "02:30:00", "time_accuracy": "exact",
                "latitude": 44.80401, "longitude": 20.46513, "timezone": "Europe/Belgrade",
            },
        },
    }
    r = client.post("/v1/chart-packet", json=req)
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["validation"]["synastry_validated"] is False
    assert p["validation"]["validated_for_interpretation"] is False
    assert p["synastry"]["partner"]["birth"]["civil_time_status"] == "ambiguous"
    assert p["synastry"]["partner"]["angles"]["asc"]["sign"]["value"] is None
