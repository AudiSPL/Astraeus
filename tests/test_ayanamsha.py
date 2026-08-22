from concurrent.futures import ThreadPoolExecutor

import pytest
import swisseph as swe

from app.core import ayanamsha, ephemeris

JD = 2445905.6319444
LAT = 44.80401
LON = 20.46513


def test_registry_contains_only_supported_initial_choices():
    assert set(ayanamsha.AYANAMSHAS) == {
        "lahiri", "fagan_bradley", "krishnamurti", "raman"
    }
    assert ayanamsha.DEFAULT_AYANAMSHA == "lahiri"


@pytest.mark.parametrize("name, low, high", [
    ("fagan_bradley", 24.4, 24.7),
    ("lahiri", 23.5, 23.8),
    ("krishnamurti", 23.4, 23.7),
    ("raman", 22.0, 22.4),
])
def test_reference_epoch_values_are_in_expected_ranges(name, low, high):
    value = ayanamsha.value_at(JD, name)
    assert low < value < high


def test_compute_houses_sets_sidereal_mode_itself():
    lahiri = ephemeris.compute_houses(
        JD, LAT, LON, "placidus", "sidereal", "lahiri")[1]["asc"]["lon"]
    raman = ephemeris.compute_houses(
        JD, LAT, LON, "placidus", "sidereal", "raman")[1]["asc"]["lon"]
    assert 1.0 < abs((lahiri - raman + 180) % 360 - 180) < 2.0

    # Pollute Swiss global state deliberately. compute_houses must still return
    # Lahiri because it pins its own mode instead of inheriting this value.
    with ayanamsha.SWISS_LOCK:
        swe.set_sid_mode(swe.SIDM_FAGAN_BRADLEY)
    again = ephemeris.compute_houses(
        JD, LAT, LON, "placidus", "sidereal", "lahiri")[1]["asc"]["lon"]
    assert again == pytest.approx(lahiri, abs=1e-9)


def test_concurrent_ayanamshas_do_not_leak_between_threads():
    expected = {
        name: ephemeris.compute_houses(
            JD, LAT, LON, "placidus", "sidereal", name)[1]["asc"]["lon"]
        for name in ("lahiri", "raman")
    }

    def worker(name):
        vals = []
        for _ in range(40):
            bodies = ephemeris.compute_bodies(
                JD, "sidereal", "true", ["chiron", "lilith"], name)
            _, angles, _ = ephemeris.compute_houses(
                JD, LAT, LON, "placidus", "sidereal", name)
            vals.append((bodies["Sun"]["lon"], angles["asc"]["lon"]))
        return name, vals

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = dict(pool.map(worker, ("lahiri", "raman")))

    for name, vals in results.items():
        for _, asc in vals:
            assert asc == pytest.approx(expected[name], abs=1e-9)

    assert expected["lahiri"] != pytest.approx(expected["raman"], abs=1e-6)
