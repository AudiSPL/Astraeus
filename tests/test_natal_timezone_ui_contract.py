"""Contract checks for the date-aware natal timezone picker."""
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

UI = Path("app/static/ui.html").read_text(encoding="utf-8")
client = TestClient(app)


def test_natal_timezone_input_is_visible_and_searchable_for_city_and_coords_modes():
    assert 'id="bTz"' in UI
    assert 'id="bTzList"' in UI
    assert 'id="bTzStatus"' in UI
    assert 'aria-controls="bTzList"' in UI
    assert 'attachBirthTimezoneAC()' in UI


def test_natal_timezone_lookup_uses_full_birth_local_moment():
    assert 'function birthLocalMoment()' in UI
    assert "const d = $('bDate')?.value || '';" in UI
    assert "const t = $('bTime')?.value || '';" in UI
    assert 'async function birthTimezonePayload(query, limit)' in UI


def test_city_selection_syncs_timezone_but_preserves_explicit_picker_as_request_source():
    assert 'function syncBirthTimezoneFromCity(city)' in UI
    assert "attachAC('bCity', 'bCityList', c => { syncBirthTimezoneFromCity(c); });" in UI
    assert "req.birth.timezone = $('bTz').value.trim() || s.timezone;" in UI


def test_default_city_is_primed_so_timezone_override_is_not_silently_ignored():
    assert 'async function primeBirthCity()' in UI
    assert 'primeBirthCity();' in UI


def test_historical_belgrade_picker_offset_matches_reference_birth_instant():
    response = client.get(
        "/v1/timezones",
        params={"at": "1984-07-24T05:10:00", "q": "belgrade"},
    )
    assert response.status_code == 200
    belgrade = next(e for e in response.json()["timezones"] if e["id"] == "Europe/Belgrade")
    assert belgrade["status"] == "ok"
    assert belgrade["offset_label"] == "GMT+02:00"


def test_natal_picker_surfaces_dst_gap_and_ambiguous_statuses_through_shared_endpoint():
    gap = client.get(
        "/v1/timezones",
        params={"at": "2026-03-29T02:30:00", "q": "belgrade"},
    ).json()["timezones"][0]
    ambiguous = client.get(
        "/v1/timezones",
        params={"at": "2026-10-25T02:30:00", "q": "belgrade"},
    ).json()["timezones"][0]
    assert gap["status"] == "gap"
    assert ambiguous["status"] == "ambiguous"
