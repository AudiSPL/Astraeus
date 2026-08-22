"""Ayanamsha integration: every branch, not just the natal one.

The failure this exists to catch is a partial implementation. If one branch
still hardcodes Lahiri while the rest honour the selected ayanamsha, the
packet advertises a selector it does not have and quietly mixes reference
frames. That is worse than an honest hardcode, because nothing looks wrong.

Method: request the same chart twice, once with Raman and once with Lahiri.
Those two differ by about 1.45 degrees at the reference epoch, so every
sidereal longitude in the packet must move. Any block that comes back
byte-identical is still pinned to one ayanamsha, and the assertion names it.

Unit tests on the registry cannot catch this. Only the whole packet can.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

BIRTH = {"date": "1984-07-24", "time": "05:10:00", "time_accuracy": "exact",
         "place_label": "Belgrade, Serbia"}

#: Placidus, not Whole Sign. Whole Sign cusps are multiples of 30 derived from
#: the Ascendant's sign, so they only move if the ayanamsha shifts the ASC
#: across a boundary. Placidus cusps move continuously and always reveal a
#: frame mismatch.
SETTINGS = {"zodiac": "sidereal", "house_system": "placidus", "node_type": "true",
            "include_points": ["chiron", "lilith"]}

FULL_REQUEST = {
    "birth": BIRTH,
    "settings": SETTINGS,
    "transit": {"date": "2026-08-20", "time": "10:00:00", "timezone": "UTC"},
    "forecast": {"enabled": True, "start_date": "2026-08-20", "end_date": "2027-08-20",
                 "months": 12, "include_inner": True},
    "progressions": {"date": "2026-08-20", "angle_method": "fast"},
    "solar_return": {"year": 2026},
}

#: Lahiri minus Raman is about 1.45 degrees across the epochs used here. The
#: bounds are deliberately loose: the test asserts "moved by roughly an
#: ayanamsha difference", not an exact figure, so it survives an ephemeris
#: update without becoming a maintenance chore.
MIN_SHIFT, MAX_SHIFT = 1.0, 2.0


def _request(ayanamsha: str) -> dict:
    body = {k: (dict(v) if isinstance(v, dict) else v) for k, v in FULL_REQUEST.items()}
    body["settings"] = {**SETTINGS, "ayanamsha": ayanamsha}
    return body


def _packet(client, ayanamsha: str) -> dict:
    response = client.post("/v1/chart-packet", json=_request(ayanamsha))
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture(scope="module")
def pair():
    with TestClient(app) as client:
        yield _packet(client, "lahiri"), _packet(client, "raman")


def _angular_delta(a: float, b: float) -> float:
    return abs((a - b + 180) % 360 - 180)


def _assert_shifted(label: str, lahiri_values: dict[str, float], raman_values: dict[str, float]):
    """Every longitude in the block must move by roughly one ayanamsha gap."""
    assert lahiri_values, f"{label}: no values found; the block is missing from the packet"
    assert set(lahiri_values) == set(raman_values), f"{label}: key sets differ"

    identical = [k for k in lahiri_values
                 if _angular_delta(lahiri_values[k], raman_values[k]) < 1e-6]
    assert not identical, (
        f"{label} did not move when the ayanamsha changed: {sorted(identical)[:8]}. "
        f"This branch is still pinned to one ayanamsha."
    )

    for key, lahiri in lahiri_values.items():
        delta = _angular_delta(lahiri, raman_values[key])
        assert MIN_SHIFT <= delta <= MAX_SHIFT, (
            f"{label}.{key} moved {delta:.4f} deg, expected between {MIN_SHIFT} and "
            f"{MAX_SHIFT}. A shift outside that range means this branch is in a "
            f"different frame again, not merely a different ayanamsha."
        )


# --- the branches ----------------------------------------------------------

def test_natal_planets_follow_the_ayanamsha(pair):
    lahiri, raman = pair
    _assert_shifted(
        "natal.planets",
        {p["name"]: p["lon"] for p in lahiri["natal"]["planets"]},
        {p["name"]: p["lon"] for p in raman["natal"]["planets"]},
    )


def test_natal_angles_follow_the_ayanamsha(pair):
    lahiri, raman = pair
    _assert_shifted(
        "natal.angles",
        {k: v["lon"] for k, v in lahiri["natal"]["angles"].items()},
        {k: v["lon"] for k, v in raman["natal"]["angles"].items()},
    )


def test_natal_house_cusps_follow_the_ayanamsha(pair):
    """The specific bug: houses_ex reads the global sid mode and takes no
    ayanamsha argument, so a compute_houses that does not set the mode itself
    inherits whatever ran last."""
    lahiri, raman = pair
    _assert_shifted(
        "natal.houses",
        {str(h["num"]): h["cusp_lon"] for h in lahiri["natal"]["houses"]},
        {str(h["num"]): h["cusp_lon"] for h in raman["natal"]["houses"]},
    )


def test_transit_planets_follow_the_ayanamsha(pair):
    lahiri, raman = pair
    _assert_shifted(
        "transits.planets",
        {p["name"]: p["lon"] for p in lahiri["transits"]["planets"]},
        {p["name"]: p["lon"] for p in raman["transits"]["planets"]},
    )


def test_secondary_progressed_planets_follow_the_ayanamsha(pair):
    lahiri, raman = pair
    _assert_shifted(
        "progressions.secondary.planets",
        {p["name"]: p["lon"] for p in lahiri["progressions"]["secondary"]["planets"]},
        {p["name"]: p["lon"] for p in raman["progressions"]["secondary"]["planets"]},
    )


def test_progressed_angles_and_houses_follow_the_ayanamsha(pair):
    lahiri, raman = pair
    _assert_shifted(
        "progressions.secondary.angles",
        {k: v["lon"] for k, v in lahiri["progressions"]["secondary"]["angles"].items()},
        {k: v["lon"] for k, v in raman["progressions"]["secondary"]["angles"].items()},
    )
    _assert_shifted(
        "progressions.secondary.houses",
        {str(h["num"]): h["cusp_lon"] for h in lahiri["progressions"]["secondary"]["houses"]},
        {str(h["num"]): h["cusp_lon"] for h in raman["progressions"]["secondary"]["houses"]},
    )


def test_solar_return_follows_the_ayanamsha(pair):
    lahiri, raman = pair
    _assert_shifted(
        "solar_return.planets",
        {p["name"]: p["lon"] for p in lahiri["solar_return"]["planets"]},
        {p["name"]: p["lon"] for p in raman["solar_return"]["planets"]},
    )
    _assert_shifted(
        "solar_return.angles",
        {k: v["lon"] for k, v in lahiri["solar_return"]["angles"].items()},
        {k: v["lon"] for k, v in raman["solar_return"]["angles"].items()},
    )


def test_forecast_eclipse_longitudes_follow_the_ayanamsha(pair):
    """forecast.py computed eclipse longitude with base_flag("tropical").

    A tropical figure compared against sidereal natal points is a frame
    mismatch, and it is invisible in the output because both are just numbers
    in degrees.
    """
    lahiri, raman = pair
    _assert_shifted(
        "forecast.eclipses",
        {e["date"]: e["ecliptic_lon"] for e in lahiri["forecast"]["eclipses"]},
        {e["date"]: e["ecliptic_lon"] for e in raman["forecast"]["eclipses"]},
    )


def test_solar_arc_directed_positions_follow_the_ayanamsha(pair):
    lahiri, raman = pair
    _assert_shifted(
        "progressions.solar_arc.directed_planets",
        {p["name"]: p["lon"] for p in lahiri["progressions"]["solar_arc"]["directed_planets"]},
        {p["name"]: p["lon"] for p in raman["progressions"]["solar_arc"]["directed_planets"]},
    )


# --- what must NOT move ----------------------------------------------------

def test_aspects_are_unchanged_by_the_ayanamsha(pair):
    """Both endpoints shift by the same amount, so the arc between them does not.

    If an orb moves, one endpoint came from a different frame than the other,
    which is the frame-mixing bug showing up as an interpretive claim rather
    than a coordinate.
    """
    lahiri, raman = pair
    for block, path in [("natal", ("natal", "aspects"))]:
        a = {(x["a"], x["b"], x["type"]): x["orb"] for x in lahiri[path[0]][path[1]]}
        b = {(x["a"], x["b"], x["type"]): x["orb"] for x in raman[path[0]][path[1]]}
        assert set(a) == set(b), f"{block}: aspect set changed with the ayanamsha"
        for key in a:
            assert a[key] == pytest.approx(b[key], abs=1e-3), f"{block}.{key} orb moved"


def test_forecast_exact_dates_are_stable_across_ayanamshas(pair):
    """Changing ayanamsha must not change which exact-hit events exist.

    Swiss sidereal modes are not numerically identical transformations at all
    epochs, and the root finder rounds to whole seconds, so Lahiri/Raman can
    differ by a second or two. That is harmless numerical jitter; event
    identity and ordering must remain identical.
    """
    from datetime import datetime

    lahiri, raman = pair
    a = lahiri["forecast"]["transits"]
    b = raman["forecast"]["transits"]
    assert [(t["transit"], t["natal"], t["type"]) for t in a] == [
        (t["transit"], t["natal"], t["type"]) for t in b
    ]
    for x, y in zip(a, b, strict=True):
        dx = datetime.fromisoformat(x["date"].replace("Z", "+00:00"))
        dy = datetime.fromisoformat(y["date"].replace("Z", "+00:00"))
        assert abs((dx - dy).total_seconds()) <= 3.0


def test_stations_are_unchanged_by_the_ayanamsha(pair):
    """A station is a speed sign change. The ayanamsha is a constant offset at
    any instant, so it cannot move one."""
    lahiri, raman = pair
    a = [(s["date"], s["planet"], s["direction"]) for s in lahiri["forecast"]["stations"]]
    b = [(s["date"], s["planet"], s["direction"]) for s in raman["forecast"]["stations"]]
    assert a == b


# --- metadata --------------------------------------------------------------

def test_metadata_names_the_ayanamsha_actually_used(pair):
    lahiri, raman = pair
    for packet, expected in ((lahiri, "lahiri"), (raman, "raman")):
        calc = packet["calculation"]
        assert calc["zodiac"] == "sidereal"
        assert calc["ayanamsha"]["name"] == expected
        assert calc["ayanamsha"]["julian_day_ut"] == pytest.approx(
            packet["birth"]["julian_day_ut"], abs=1e-6)


def test_metadata_reports_a_value_per_epoch(pair):
    """One figure quoted for natal, transit and solar return is wrong for at
    least two of them: the ayanamsha drifts about 50 arcseconds a year."""
    lahiri, _ = pair
    by_epoch = lahiri["calculation"]["ayanamsha_by_epoch"]
    assert {"natal", "transit", "solar_return"} <= set(by_epoch)
    # Distinct epochs must get distinct ayanamsha values. Two labels may
    # legitimately share one value when they refer to the same JD (e.g. fast
    # progressed planets and progressed houses).
    by_jd = {}
    for label, item in by_epoch.items():
        by_jd.setdefault(item["julian_day_ut"], []).append((label, item["value_deg"]))
    distinct_epoch_values = [items[0][1] for items in by_jd.values()]
    assert len(set(distinct_epoch_values)) == len(distinct_epoch_values), by_epoch
    for items in by_jd.values():
        assert len({value for _, value in items}) == 1


def test_tropical_reports_a_null_ayanamsha(client):
    body = _request("lahiri")
    body["settings"] = {**SETTINGS, "zodiac": "tropical"}
    packet = client.post("/v1/chart-packet", json=body).json()
    calc = packet["calculation"]
    assert calc["zodiac"] == "tropical"
    assert calc["ayanamsha"] is None
    assert "ayanamsha_by_epoch" not in calc


def test_sidereal_without_an_explicit_ayanamsha_stays_lahiri(client):
    """The compatibility condition for the whole feature.

    sidereal_current_behavior.json was captured before the selector existed.
    If this fails, the golden drifts and the change was not backwards
    compatible.
    """
    body = _request("lahiri")
    body["settings"] = dict(SETTINGS)   # no ayanamsha key at all
    implicit = client.post("/v1/chart-packet", json=body).json()
    explicit = _packet(client, "lahiri")
    for a, b in zip(implicit["natal"]["planets"], explicit["natal"]["planets"], strict=True):
        assert a["lon"] == pytest.approx(b["lon"], abs=1e-9)
    assert implicit["calculation"]["ayanamsha"]["name"] == "lahiri"


def test_unknown_ayanamsha_is_rejected(client):
    body = _request("sri_yukteswar")
    assert client.post("/v1/chart-packet", json=body).status_code in (400, 422)
