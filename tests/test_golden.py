"""Golden regression tests.

Regenerates each packet from the live engine and compares it against the
pinned golden file. The merge condition for the compute_chart(config)
refactor is that every test here passes with no changes to the golden files.

Generate the golden files first:

    python -m tests.golden.capture

Deliberately updating a golden file (only after a test proving the old
behaviour was wrong):

    python -m tests.golden.capture --only natal_tropical_placidus
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from tests.golden.capture import load_requests
from tests.golden.compare import DEFAULT_CONFIG, compare, format_report

GOLDEN_DIR = Path(__file__).parent / "golden" / "v1"


def _available() -> list[str]:
    if not GOLDEN_DIR.exists():
        return []
    return sorted(p.stem for p in GOLDEN_DIR.glob("*.json"))


AVAILABLE = _available()

# Scoped to the golden-comparison tests ONLY. A module-level skipif here
# would silently disable the invariant tests below whenever the golden
# directory is missing or mislocated, which is exactly the false-green this
# scaffolding exists to prevent.
requires_golden = pytest.mark.skipif(
    not AVAILABLE,
    reason="no golden files captured yet; run `python -m tests.golden.capture`",
)


@requires_golden
@pytest.mark.parametrize("name", AVAILABLE)
def test_packet_matches_golden(client, name):
    body = load_requests()[name]
    response = client.post("/v1/chart-packet", json=body)
    assert response.status_code == 200, response.text

    golden = json.loads((GOLDEN_DIR / f"{name}.json").read_text(encoding="utf-8"))
    # This feature deliberately adds a new top-level calculation audit block
    # and the request schema now carries an explicit ayanamsha default, which
    # changes input_hash. Legacy goldens continue to pin the numerical v1
    # payload; dedicated ayanamsha integration tests pin the new metadata.
    legacy_cfg = replace(
        DEFAULT_CONFIG,
        ignore=tuple(DEFAULT_CONFIG.ignore) + ("meta.input_hash", "calculation"),
    )
    diffs = compare(golden, response.json(), legacy_cfg)
    assert not diffs, f"{name} drifted from golden:\n{format_report(diffs)}"


def test_engine_applies_dst_for_the_reference_birth(client):
    """A one-hour DST error would not look like an error.

    The Ascendant sits about three minutes from the Cancer/Leo boundary, so a
    wrong offset produces a different but entirely plausible chart rather
    than an obviously broken one.
    """
    body = load_requests()["natal_tropical_placidus"]
    packet = client.post("/v1/chart-packet", json=body).json()
    assert packet["birth"]["utc"].startswith("1984-07-24T03:10:00")
    assert packet["birth"]["utc_offset"] == "+02:00"
    assert packet["birth"]["dst_active"] is True


def test_engine_does_not_hardcode_summer_offset(client):
    body = load_requests()["natal_winter_no_dst"]
    packet = client.post("/v1/chart-packet", json=body).json()
    assert packet["birth"]["utc_offset"] == "+01:00"
    assert packet["birth"]["dst_active"] is False


# ---------------------------------------------------------------------------
# Invariants. These check logic rather than a snapshot, so they keep working
# after the golden files are deliberately updated.
# ---------------------------------------------------------------------------

HOUSE_SYSTEMS = ["placidus", "koch", "equal", "whole_sign"]


def _natal_body(house_system: str, node_type: str = "true", zodiac: str = "tropical") -> dict:
    return {
        "birth": {
            "date": "1984-07-24",
            "time": "05:10:00",
            "time_accuracy": "unknown",
            "place_label": "Belgrade, Serbia",
        },
        "settings": {"zodiac": zodiac, "house_system": house_system, "node_type": node_type},
    }


def _packet(client, body: dict) -> dict:
    response = client.post("/v1/chart-packet", json=body)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize("house_system", HOUSE_SYSTEMS[1:])
def test_house_system_does_not_move_planets(client, house_system):
    base = _packet(client, _natal_body("placidus"))
    other = _packet(client, _natal_body(house_system))
    for a, b in zip(base["natal"]["planets"], other["natal"]["planets"], strict=True):
        assert a["name"] == b["name"]
        assert a["lon"] == pytest.approx(b["lon"], abs=1e-9)


@pytest.mark.parametrize("house_system", HOUSE_SYSTEMS[1:])
def test_house_system_does_not_change_angles(client, house_system):
    """ASC and MC are defined by the horizon and meridian, not by the cusp
    division method, so they must be identical across house systems."""
    base = _packet(client, _natal_body("placidus"))["natal"]["angles"]
    other = _packet(client, _natal_body(house_system))["natal"]["angles"]
    for angle in ("asc", "mc"):
        assert base[angle]["lon"] == pytest.approx(other[angle]["lon"], abs=1e-9)


@pytest.mark.parametrize("house_system", HOUSE_SYSTEMS[1:])
def test_house_system_does_not_change_planet_to_planet_aspects(client, house_system):
    """Aspects between planets are longitude arithmetic. Only aspects that
    involve ASC or MC may legitimately be affected by the house system, and
    in a correct engine not even those."""

    def planet_only(packet):
        return {
            (a["a"], a["b"], a["type"]): a["orb"]
            for a in packet["natal"]["aspects"]
            if a["a"] not in ("ASC", "MC") and a["b"] not in ("ASC", "MC")
        }

    assert planet_only(_packet(client, _natal_body("placidus"))) == planet_only(
        _packet(client, _natal_body(house_system))
    )


def test_node_type_moves_only_the_node(client):
    true_node = _packet(client, _natal_body("placidus", node_type="true"))
    mean_node = _packet(client, _natal_body("placidus", node_type="mean"))
    for a, b in zip(true_node["natal"]["planets"], mean_node["natal"]["planets"], strict=True):
        assert a["name"] == b["name"]
        if a["name"] == "Node":
            continue
        assert a["lon"] == pytest.approx(b["lon"], abs=1e-9), f"{a['name']} moved"


def test_repeated_identical_requests_are_deterministic(client):
    """Guards the pyswisseph threading issue: state that leaks between calls
    has previously caused Chiron to silently disappear on the second request.
    """
    body = _natal_body("whole_sign")
    first, second = _packet(client, body), _packet(client, body)
    diffs = compare(first, second, replace(DEFAULT_CONFIG, ignore=("meta.generated_at",)))
    assert not diffs, format_report(diffs)


def test_every_expected_body_is_present(client):
    """A body silently dropping out is the failure mode that a golden diff
    catches late and a human never notices."""
    packet = _packet(client, _natal_body("whole_sign"))
    names = {p["name"] for p in packet["natal"]["planets"]}
    assert names == {
        "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
        "Uranus", "Neptune", "Pluto", "Node", "Chiron", "Lilith",
    }


def test_forecast_horizon_does_not_change_the_natal_chart(client):
    """The natal chart is a function of the birth moment alone.

    If asking for a longer forecast moves a natal longitude, some piece of
    forecast state is leaking backwards into the base calculation.
    """
    short = dict(_natal_body("placidus"))
    short["forecast"] = {"enabled": True, "start_date": "2026-08-20",
                         "end_date": "2026-11-20", "months": 3, "include_inner": False}
    long_ = dict(_natal_body("placidus"))
    long_["forecast"] = {"enabled": True, "start_date": "2026-08-20",
                         "end_date": "2027-08-20", "months": 12, "include_inner": True}
    a, b = _packet(client, short)["natal"], _packet(client, long_)["natal"]
    diffs = compare(a, b, replace(DEFAULT_CONFIG, ignore=()))
    assert not diffs, format_report(diffs)


def test_solar_return_moment_is_independent_of_the_house_system(client):
    """The return is the instant the Sun regains its natal longitude.

    Cusp division has nothing to do with it, so the moment, and the ASC and
    MC that follow from it, must be identical across house systems. Only the
    cusps may differ.
    """
    def solar_return(house_system):
        body = dict(_natal_body("placidus"))
        body["solar_return"] = {"year": 2026, "house_system": house_system}
        return _packet(client, body)["solar_return"]

    placidus, whole_sign = solar_return("placidus"), solar_return("whole_sign")
    assert placidus["moment_utc"] == whole_sign["moment_utc"]
    assert placidus["julian_day_ut"] == pytest.approx(whole_sign["julian_day_ut"], abs=1e-9)
    for angle in ("asc", "mc"):
        assert placidus["angles"][angle]["lon"] == pytest.approx(
            whole_sign["angles"][angle]["lon"], abs=1e-9)
    assert placidus["houses"] != whole_sign["houses"], "house systems produced identical cusps"


@requires_golden
def test_golden_set_covers_every_request():
    """A partial capture would otherwise look like a smaller but passing suite."""
    expected = set(load_requests())
    assert set(AVAILABLE) == expected, (
        f"missing: {sorted(expected - set(AVAILABLE))}  "
        f"stale: {sorted(set(AVAILABLE) - expected)}"
    )


# ---------------------------------------------------------------------------
# Known v1 defects, recorded now so the refactor cannot quietly inherit them.
#
# xfail(strict=True): when one of these starts passing, pytest fails and the
# marker has to be removed deliberately. That is the point - a silent fix is
# as much of a problem as a silent break.
# ---------------------------------------------------------------------------

KNOWN_BUG = "known v1 defect; remove this marker in the commit that fixes it"


def test_nonexistent_civil_time_is_rejected(client):
    """1984-03-25 02:30 Europe/Belgrade never happened.

    The clock jumped 02:00 -> 03:00. datetime(..., tzinfo=ZoneInfo(tz)) resolves
    it silently to +01:00 instead of reporting that the instant does not exist.
    """
    body = _natal_body("placidus")
    body["birth"]["date"] = "1984-03-25"
    body["birth"]["time"] = "02:30:00"
    assert client.post("/v1/chart-packet", json=body).status_code == 422


def test_ambiguous_civil_time_is_flagged(client):
    """1984-09-30 02:30 Europe/Belgrade happened twice.

    The clock fell back 03:00 -> 02:00, so this civil time maps to two
    instants an hour apart. Either is defensible; choosing one without
    saying so is not.
    """
    body = _natal_body("placidus")
    body["birth"]["date"] = "1984-09-30"
    body["birth"]["time"] = "02:30:00"
    packet = client.post("/v1/chart-packet", json=body).json()
    assert any("ambiguous" in w.lower() for w in packet.get("warnings", []))


def test_eclipse_longitude_follows_the_zodiac_setting(client):
    """Under sidereal, natal points are sidereal but the eclipse point is not.

    The two are then compared to each other, which mixes coordinate frames.
    A correct engine puts roughly one ayanamsha between the two figures.
    """
    forecast = {"enabled": True, "start_date": "2026-08-20", "end_date": "2027-08-20",
                "months": 12, "include_inner": False}

    def first_eclipse_lon(zodiac):
        body = _natal_body("whole_sign", zodiac=zodiac)
        body["forecast"] = forecast
        eclipses = _packet(client, body)["forecast"]["eclipses"]
        assert eclipses, "no eclipses in the forecast window"
        return eclipses[0]["ecliptic_lon"]

    tropical, sidereal = first_eclipse_lon("tropical"), first_eclipse_lon("sidereal")
    assert abs(tropical - sidereal) > 20.0, (
        f"tropical {tropical} and sidereal {sidereal} eclipse longitudes are the "
        "same frame; expected roughly an ayanamsha apart"
    )


@pytest.mark.xfail(strict=True, reason=f"{KNOWN_BUG}: time_accuracy is accepted on input and dropped from the packet")
def test_time_accuracy_round_trips_into_the_packet(client):
    """The provenance of the birth time has to survive into the output.

    Without it the interpreter cannot tell a hospital record from a guess,
    and the whole field-level stability design has nothing to key off.
    """
    body = _natal_body("placidus")
    body["birth"]["time_accuracy"] = "approx"
    assert _packet(client, body)["birth"]["time_accuracy"] == "approx"


@pytest.mark.xfail(strict=True, reason=f"{KNOWN_BUG}: settings echo omits include_points")
def test_settings_echo_is_complete(client):
    body = _natal_body("placidus")
    body["settings"]["include_points"] = ["chiron"]
    assert _packet(client, body)["settings"]["include_points"] == ["chiron"]
