"""Progressions golden test. The progressed Mars-conjunct-natal-Uranus hit was
cross-checked independently against astro-seek's progressed calendar for the
default profile (Jul 15, 2026 entry) — orb landed at 0.0, confirming the
secondary-progression math.
"""


def test_secondary_and_solar_arc_present(client):
    req = {
        "birth": {"date": "1984-07-24", "time": "05:10:00", "time_accuracy": "exact",
                  "place_label": "Belgrade, Serbia"},
        "progressions": {"date": "2026-07-15"},
    }
    p = client.post("/v1/chart-packet", json=req).json()
    assert p["validation"]["validated_for_interpretation"] is True
    assert p["validation"]["progressions_validated"] is True

    sec = p["progressions"]["secondary"]
    assert len(sec["planets"]) == 10
    assert len(sec["houses"]) == 12

    # Cross-checked against astro-seek's progressed calendar for this profile.
    hit = next((a for a in sec["aspects_to_natal"]
               if a["directed"] == "Mars" and a["natal"] == "Uranus"
               and a["type"] == "conjunction"), None)
    assert hit is not None, "expected progressed Mars conjunct natal Uranus around mid-2026"
    assert hit["orb"] < 0.1

    sa = p["progressions"]["solar_arc"]
    assert len(sa["directed_planets"]) >= 10  # shifts every natal point present (incl. Node/Chiron/Lilith)
    assert "asc" in sa["directed_angles"] and "mc" in sa["directed_angles"]
    assert sa["arc_degrees"] > 0


def test_progressions_blocked_by_unknown_birth_time(client):
    req = {
        "birth": {"date": "1984-07-24", "time": "05:10:00", "time_accuracy": "unknown",
                  "place_label": "Belgrade, Serbia"},
        "progressions": {"date": "2026-07-15"},
    }
    p = client.post("/v1/chart-packet", json=req).json()
    assert p["validation"]["validated_for_interpretation"] is False
