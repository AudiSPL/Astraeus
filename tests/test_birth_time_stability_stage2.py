from __future__ import annotations

import pytest


def _body(*, uncertainty=5, accuracy="approx", house_system="placidus", zodiac="tropical"):
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
            "zodiac": zodiac,
            "house_system": house_system,
            "node_type": "true",
            "include_points": ["chiron", "lilith"],
            "ayanamsha": "lahiri",
        },
    }


def _packet(client, **kwargs):
    r = client.post("/v1/chart-packet", json=_body(**kwargs))
    assert r.status_code == 200, r.text
    return r.json()


def test_stage2_emits_all_house_cusps_and_body_placements(client):
    packet = _packet(client)
    s = packet["birth_time_stability"]
    assert s["scope"] == "stage_2_angles_chart_ruler_angle_aspects_house_cusps_house_placements"
    assert len(s["house_cusps"]) == 12
    assert len(s["house_placements"]) == len(packet["natal"]["planets"])


@pytest.mark.parametrize("house_system", ["placidus", "koch", "equal", "whole_sign"])
def test_stage2_nominal_values_match_the_natal_packet(client, house_system):
    packet = _packet(client, uncertainty=15, house_system=house_system)
    s = packet["birth_time_stability"]

    for cusp_meta, natal_house in zip(s["house_cusps"], packet["natal"]["houses"], strict=True):
        assert cusp_meta["house"] == natal_house["num"]
        assert cusp_meta["sign"]["value"] == natal_house["sign"]["nominal"]
        assert cusp_meta["longitude"]["nominal"] == pytest.approx(natal_house["nominal_cusp_lon"], abs=1e-9)

    for placement, natal_planet in zip(s["house_placements"], packet["natal"]["planets"], strict=True):
        assert placement["body"] == natal_planet["name"]
        assert placement["nominal_house"] == natal_planet["house"]["nominal"]


def test_reference_plus_minus_five_minutes_finds_real_house_instability(client):
    s = _packet(client, uncertainty=5)["birth_time_stability"]
    by_house = {c["house"]: c for c in s["house_cusps"]}
    by_body = {p["body"]: p for p in s["house_placements"]}

    assert by_house[1]["possible_signs_within_declared_uncertainty"] == ["Cancer", "Leo"]
    assert by_house[7]["possible_signs_within_declared_uncertainty"] == ["Capricorn", "Aquarius"]
    assert by_house[1]["stable_for_declared_uncertainty"] is False
    assert by_house[7]["stable_for_declared_uncertainty"] is False
    assert by_house[1]["sign"]["stable_within_minutes"] == pytest.approx(3.238, abs=0.002)

    assert by_body["Mars"]["nominal_house"] == 5
    assert by_body["Mars"]["possible_houses_within_declared_uncertainty"] == [5, 4]
    assert by_body["Mars"]["stable_for_declared_uncertainty"] is False
    assert by_body["Mars"]["stable_within_minutes"] == pytest.approx(0.874, abs=0.002)


def test_nominal_field_status_points_to_actual_json_paths(client):
    s = _packet(client, uncertainty=5)["birth_time_stability"]
    unstable = s["nominal_field_status"]["unstable_fields"]
    paths = {u["path"] for u in unstable}
    assert paths == {
        "natal.angles.asc.sign",
        "natal.chart_ruler",
        "natal.houses[0].sign",
        "natal.houses[6].sign",
        "natal.planets[4].house",
    }
    mars = next(u for u in unstable if u.get("body") == "Mars")
    assert mars["possible_values"] == [5, 4]


def test_exact_time_assesses_zero_window_without_marking_fields_unstable(client):
    s = _packet(client, accuracy="exact", uncertainty=0)["birth_time_stability"]
    status = s["nominal_field_status"]
    assert status["declared_uncertainty_assessed"] is True
    assert status["nominal_values_are_point_estimates"] is False
    assert status["unstable_fields"] == []
    assert all(c["stable_for_declared_uncertainty"] is True for c in s["house_cusps"])
    assert all(p["stable_for_declared_uncertainty"] is True for p in s["house_placements"])


def test_unknown_time_keeps_stage2_house_ranges_unresolved(client):
    s = _packet(client, accuracy="unknown", uncertainty=None)["birth_time_stability"]
    status = s["nominal_field_status"]
    assert status["declared_uncertainty_assessed"] is False
    assert status["unstable_fields"] is None
    assert s["house_cusps"][0]["possible_signs_within_declared_uncertainty"] is None
    assert s["house_placements"][0]["possible_houses_within_declared_uncertainty"] is None
    assert s["house_cusps"][0]["sign"]["stable_within_minutes"] is None
    assert all(p["stable_within_minutes"] is None for p in s["house_placements"])
    # Stage 1 still provides intrinsic ASC/MC thresholds even without a declared range.
    assert s["asc"]["sign"]["stable_within_minutes"] == pytest.approx(3.238, abs=0.02)


def test_whole_sign_cusps_change_together_when_ascendant_changes_sign(client):
    s = _packet(client, uncertainty=5, house_system="whole_sign")["birth_time_stability"]
    assert all(c["stable_for_declared_uncertainty"] is False for c in s["house_cusps"])
    assert all(len(c["possible_signs_within_declared_uncertainty"]) == 2 for c in s["house_cusps"])
    thresholds = [c["sign"]["stable_within_minutes"] for c in s["house_cusps"]]
    asc_threshold = s["asc"]["sign"]["stable_within_minutes"]
    assert all(t == pytest.approx(asc_threshold, abs=0.002) for t in thresholds)


def test_sidereal_stage2_uses_selected_frame_and_matches_nominal_packet(client):
    packet = _packet(client, uncertainty=15, zodiac="sidereal")
    s = packet["birth_time_stability"]
    assert s["house_cusps"][0]["longitude"]["nominal"] == pytest.approx(
        packet["natal"]["houses"][0]["nominal_cusp_lon"], abs=1e-9
    )
    assert s["house_placements"][0]["nominal_house"] == packet["natal"]["planets"][0]["house"]["nominal"]


def test_unstable_nominal_fields_generate_explicit_warning(client):
    packet = _packet(client, uncertainty=5)
    warnings = "\n".join(packet.get("warnings", []))
    assert "natal field(s) non-unique" in warnings
    assert "natal.planets[4].house" in warnings
    assert "qualified output" in warnings


def test_exact_zero_window_does_not_generate_unstable_field_warning(client):
    packet = _packet(client, accuracy="exact", uncertainty=0)
    warnings = "\n".join(packet.get("warnings", []))
    assert "nominal natal field(s) non-unique" not in warnings
