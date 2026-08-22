from __future__ import annotations

import pytest

from app.core import timeutil


def _body(date: str, time: str, *, transit=None):
    body = {
        "birth": {
            "date": date,
            "time": time,
            "time_accuracy": "exact",
            "place_label": "Belgrade, Serbia",
        },
        "settings": {
            "zodiac": "tropical",
            "house_system": "placidus",
            "node_type": "true",
        },
    }
    if transit is not None:
        body["transit"] = transit
    return body


def test_resolver_marks_nonexistent_belgrade_time_as_gap():
    r = timeutil.resolve_local_civil_datetime("1984-03-25", "02:30:00", "Europe/Belgrade")
    assert r["status"] == "gap"
    assert r["candidates"] == []
    assert r["selected"] is None


def test_resolver_marks_fallback_time_as_ambiguous_with_two_offsets():
    r = timeutil.resolve_local_civil_datetime("1984-09-30", "02:30:00", "Europe/Belgrade")
    assert r["status"] == "ambiguous"
    assert [c["fold"] for c in r["candidates"]] == [0, 1]
    assert [c["offset_str"] for c in r["candidates"]] == ["+02:00", "+01:00"]
    assert [c["utc"].isoformat() for c in r["candidates"]] == [
        "1984-09-30T00:30:00+00:00",
        "1984-09-30T01:30:00+00:00",
    ]


def test_ordinary_reference_birth_stays_byte_for_byte_equivalent_at_timeutil_boundary():
    base = timeutil.to_utc_and_jd("1984-07-24", "05:10:00", "Europe/Belgrade")
    detailed = timeutil.to_utc_and_jd(
        "1984-07-24", "05:10:00", "Europe/Belgrade", return_resolution=True
    )
    assert detailed[:5] == base
    assert detailed[5]["status"] == "ok"
    assert base[0] == "1984-07-24T05:10:00+02:00"
    assert base[1] == "1984-07-24T03:10:00+00:00"
    assert base[2] == "+02:00"
    assert base[3] is True


def test_to_utc_rejects_nonexistent_local_time():
    with pytest.raises(timeutil.NonexistentLocalTimeError, match="does not exist"):
        timeutil.to_utc_and_jd("1984-03-25", "02:30:00", "Europe/Belgrade")


def test_api_returns_422_for_nonexistent_birth_time(client):
    response = client.post("/v1/chart-packet", json=_body("1984-03-25", "02:30:00"))
    assert response.status_code == 422
    assert "does not exist" in response.json()["detail"]


def test_api_flags_ambiguous_birth_time_without_silently_claiming_certainty(client):
    response = client.post("/v1/chart-packet", json=_body("1984-09-30", "02:30:00"))
    assert response.status_code == 200, response.text
    packet = response.json()
    warnings = packet.get("warnings", [])
    assert any("ambiguous" in warning.lower() for warning in warnings)
    assert any("unresolved" in warning.lower() for warning in warnings)
    # The nominal result stays fold=0 to avoid an unrelated behavior change.
    assert packet["birth"]["utc_offset"] == "+02:00"
    assert packet["birth"]["utc"].startswith("1984-09-30T00:30:00")


def test_api_rejects_nonexistent_transit_time(client):
    body = _body("1984-07-24", "05:10:00", transit={
        "date": "2026-03-29",
        "time": "02:30:00",
        "timezone": "Europe/Belgrade",
    })
    response = client.post("/v1/chart-packet", json=body)
    assert response.status_code == 422
    assert "does not exist" in response.json()["detail"]


def test_api_warns_on_ambiguous_transit_time(client):
    body = _body("1984-07-24", "05:10:00", transit={
        "date": "2026-10-25",
        "time": "02:30:00",
        "timezone": "Europe/Belgrade",
    })
    response = client.post("/v1/chart-packet", json=body)
    assert response.status_code == 200, response.text
    assert any("transit local time is ambiguous" in w.lower() for w in response.json()["warnings"])
