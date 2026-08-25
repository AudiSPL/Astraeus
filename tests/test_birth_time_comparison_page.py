from copy import deepcopy
from pathlib import Path


BASE_REQUEST = {
    "birth": {
        "date": "1984-07-24",
        "time": "05:10:00",
        "time_accuracy": "approx",
        "time_uncertainty_minutes": 5,
        "birth_time_provenance": "hospital_record",
        "place_label": "Belgrade, Serbia",
        "latitude": 44.80401,
        "longitude": 20.46513,
        "timezone": "Europe/Belgrade",
    },
    "settings": {
        "zodiac": "tropical",
        "ayanamsha": "lahiri",
        "house_system": "whole_sign",
        "node_type": "true",
        "include_points": ["chiron", "lilith"],
    },
}


def compare(client, times):
    return client.post(
        "/v1/birth-time-comparison",
        json={"base_request": deepcopy(BASE_REQUEST), "candidate_times": times},
    )


def test_birth_time_comparison_page_is_served(client):
    r = client.get("/birth-time-comparison")
    assert r.status_code == 200
    text = r.text
    assert "Birth-Time Comparison v1" in text
    assert "candidate_geometry_must_not_be_mixed" not in text
    assert "/v1/birth-time-comparison" in text
    assert "not validated rectification" in text


def test_navigation_exposes_birth_time_comparison(client):
    for route in ["/", "/guide", "/prompts", "/forecast-lab", "/birth-time-comparison"]:
        r = client.get(route)
        assert r.status_code == 200
        assert 'href="/birth-time-comparison"' in r.text


def test_endpoint_requires_two_candidates(client):
    r = compare(client, ["05:10"])
    assert r.status_code == 422
    assert "at least 2 candidate times" in r.json()["detail"]


def test_endpoint_rejects_invalid_candidate_time(client):
    r = compare(client, ["05:10", "25:00"])
    assert r.status_code == 422
    assert "invalid candidate time" in r.json()["detail"]


def test_endpoint_rejects_duplicate_normalized_times(client):
    r = compare(client, ["05:10", "05:10:00"])
    assert r.status_code == 422
    assert "duplicate candidate time" in r.json()["detail"]


def test_endpoint_sorts_and_normalizes_candidates(client):
    r = compare(client, ["05:15", "05:05", "05:10"])
    assert r.status_code == 200, r.text
    assert r.json()["candidate_times"] == ["05:05:00", "05:10:00", "05:15:00"]



def test_endpoint_reuses_calculator_birth_settings_validation(client):
    base = deepcopy(BASE_REQUEST)
    base["birth"]["latitude"] = "north"
    r = client.post(
        "/v1/birth-time-comparison",
        json={"base_request": base, "candidate_times": ["05:10", "05:15"]},
    )
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["message"] == "invalid base_request birth/settings"


def test_endpoint_refuses_ambiguous_candidate_civil_time(client):
    base = deepcopy(BASE_REQUEST)
    base["birth"].update({
        "date": "2026-10-25",
        "time": "01:30:00",
        "time_accuracy": "exact",
        "time_uncertainty_minutes": 0,
    })
    r = client.post(
        "/v1/birth-time-comparison",
        json={"base_request": base, "candidate_times": ["01:30", "02:30"]},
    )
    assert r.status_code == 422
    assert "ambiguous local civil time" in str(r.json()["detail"])

def test_candidate_states_preserve_source_precision_but_use_point_evaluation(client):
    r = compare(client, ["05:10", "05:15"])
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["schema_version"] == "birth_time_comparison_v1"
    assert data["source_birth"]["declared_precision"]["time_accuracy"] == "approx"
    assert data["source_birth"]["declared_precision"]["time_uncertainty_minutes"] == 5
    assert data["source_birth"]["declared_precision"]["birth_time_provenance"] == "hospital_record"
    assert data["contract"]["candidate_time_is_point_evaluation_only"] is True
    assert data["contract"]["source_provenance_not_rewritten"] is True
    assert all(s["civil_time_status"] == "ok" for s in data["candidate_states"])


def test_known_cancer_to_leo_asc_transition_is_detected(client):
    r = compare(client, ["05:10", "05:15"])
    assert r.status_code == 200, r.text
    data = r.json()
    states = data["candidate_states"]
    assert states[0]["angles"]["asc"]["sign"] == "Cancer"
    assert states[1]["angles"]["asc"]["sign"] == "Leo"
    assert states[0]["chart_ruler"] == "Moon"
    assert states[1]["chart_ruler"] == "Sun"
    transitions = data["comparison"]["transition_intervals"]
    assert any(t["field"] == "asc.sign" and t["from_time"] == "05:10:00" and t["to_time"] == "05:15:00" for t in transitions)
    assert any(t["field"] == "chart_ruler" for t in transitions)


def test_candidate_specific_angle_orbs_are_not_mixed(client):
    r = compare(client, ["05:10", "05:15"])
    assert r.status_code == 200, r.text
    states = r.json()["candidate_states"]

    def pluto_asc(state):
        return next(
            a for a in state["angle_aspects"]
            if a["body"] == "Pluto" and a["angle"] == "ASC" and a["type"] == "square"
        )

    a = pluto_asc(states[0])
    b = pluto_asc(states[1])
    assert a["orb"] < 0.05
    assert b["orb"] > 0.5
    assert a["orb"] != b["orb"]


def test_optional_modules_are_not_exposed_in_candidate_states(client):
    base = deepcopy(BASE_REQUEST)
    base["forecast"] = {"enabled": True, "start_date": "2026-08-25", "end_date": "2026-09-25"}
    base["transit"] = {"date": "2026-08-25", "time": "12:00:00", "timezone": "UTC"}
    r = client.post(
        "/v1/birth-time-comparison",
        json={"base_request": base, "candidate_times": ["05:10", "05:15"]},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["contract"]["optional_modules_withheld"] == [
        "transit", "forecast", "progressions", "solar_return", "synastry", "bazi"
    ]
    for state in data["candidate_states"]:
        assert set(state) == {
            "state_id", "candidate_time", "birth_local", "birth_utc", "utc_offset",
            "civil_time_status", "chart_ruler", "angles", "houses", "planets", "angle_aspects"
        }


def test_transition_intervals_are_explicitly_sample_bounded(client):
    r = compare(client, ["05:07", "05:10", "05:13", "05:15"])
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["contract"]["transition_intervals_are_sample_bounds_not_exact_roots"] is True
    assert all(
        t["resolution"] == "bounded_by_adjacent_sampled_candidates"
        for t in data["comparison"]["transition_intervals"]
    )


def test_comparison_hash_is_deterministic(client):
    a = compare(client, ["05:10", "05:15"])
    b = compare(client, ["05:10", "05:15"])
    assert a.status_code == 200 and b.status_code == 200
    assert a.json()["comparison_hash"] == b.json()["comparison_hash"]
    assert a.json()["comparison_hash"].startswith("sha256:")
    assert "generated_utc" in a.json() and "generated_utc" in b.json()


def test_docs_define_non_rectification_contract():
    repo = Path(__file__).resolve().parents[1]
    text = (repo / "docs" / "BIRTH_TIME_COMPARISON.md").read_text(encoding="utf-8")
    assert "not a rectification engine" in text
    assert "never combine" in text
    assert "sample bounds" in text
    assert "comparison_hash" in text
