"""Timezone picker core tests."""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import available_timezones

import pytest

from app.core import timezones as tzm

SUMMER = datetime(2026, 8, 22, 12, 0)
WINTER = datetime(2026, 12, 22, 12, 0)


@pytest.mark.parametrize(
    "zone, summer, winter",
    [
        ("Europe/Belgrade", ("GMT+02:00", "CEST"), ("GMT+01:00", "CET")),
        ("Europe/London", ("GMT+01:00", "BST"), ("GMT+00:00", "GMT")),
        ("America/New_York", ("GMT-04:00", "EDT"), ("GMT-05:00", "EST")),
    ],
)
def test_northern_zones_flip_with_the_season(zone, summer, winter):
    s, w = tzm.resolve(zone, SUMMER), tzm.resolve(zone, WINTER)
    assert (s["offset_label"], s["abbreviation"]) == summer
    assert (w["offset_label"], w["abbreviation"]) == winter
    assert s["dst_active"] is True and w["dst_active"] is False


def test_southern_hemisphere_is_inverted():
    s, w = tzm.resolve("Australia/Sydney", SUMMER), tzm.resolve("Australia/Sydney", WINTER)
    assert (s["abbreviation"], s["dst_active"]) == ("AEST", False)
    assert (w["abbreviation"], w["dst_active"]) == ("AEDT", True)


def test_zones_without_dst_do_not_move():
    for zone in ("Asia/Tokyo", "Asia/Kolkata", "Asia/Dubai"):
        assert tzm.resolve(zone, SUMMER)["offset_minutes"] == tzm.resolve(zone, WINTER)["offset_minutes"]


def test_half_and_quarter_hour_offsets_render_correctly():
    assert tzm.resolve("Asia/Kolkata", SUMMER)["offset_label"] == "GMT+05:30"
    assert tzm.resolve("Asia/Kathmandu", SUMMER)["offset_label"] == "GMT+05:45"
    assert tzm.resolve("Pacific/Marquesas", SUMMER)["offset_label"] == "GMT-09:30"


def test_numeric_tznames_are_not_presented_as_abbreviations():
    dubai = tzm.resolve("Asia/Dubai", SUMMER)
    assert dubai["abbreviation"] is None
    assert dubai["display"] == "Asia/Dubai — GMT+04:00"


def test_no_entry_ever_shows_a_numeric_abbreviation():
    for entry in tzm.list_timezones(SUMMER):
        if entry["abbreviation"]:
            assert entry["abbreviation"][0] not in "+-", entry["id"]
        for candidate in entry["possible_offsets"]:
            if candidate["abbreviation"]:
                assert candidate["abbreviation"][0] not in "+-", entry["id"]


def test_transition_day_offset_depends_on_the_hour():
    assert tzm.resolve("Europe/Belgrade", datetime(2026, 3, 29, 0, 0))["offset_label"] == "GMT+01:00"
    assert tzm.resolve("Europe/Belgrade", datetime(2026, 3, 29, 12, 0))["offset_label"] == "GMT+02:00"


def test_aware_datetime_is_rejected():
    with pytest.raises(ValueError, match="naive"):
        tzm.resolve("Europe/Belgrade", SUMMER.replace(tzinfo=timezone.utc))


def test_nonexistent_local_time_has_no_fake_primary_offset():
    entry = tzm.resolve("Europe/Belgrade", datetime(2026, 3, 29, 2, 30))
    assert entry["status"] == "gap"
    assert entry["offset_minutes"] is None
    assert entry["offset_label"] is None
    assert entry["possible_offsets"] == []
    assert "does not exist" in entry["note"]


def test_ambiguous_local_time_exposes_both_valid_offsets():
    entry = tzm.resolve("Europe/Belgrade", datetime(2026, 10, 25, 2, 30))
    assert entry["status"] == "ambiguous"
    assert entry["offset_minutes"] is None
    assert [c["offset_minutes"] for c in entry["possible_offsets"]] == [120, 60]
    assert [c["fold"] for c in entry["possible_offsets"]] == [0, 1]
    assert "twice" in entry["note"]


def test_ordinary_times_on_transition_day_are_ok():
    for hour in (1, 3):
        assert tzm.resolve("Europe/Belgrade", datetime(2026, 3, 29, hour, 30))["status"] == "ok"


def test_status_is_zone_specific():
    moment = datetime(2026, 3, 29, 2, 30)
    assert tzm.resolve("Europe/Belgrade", moment)["status"] == "gap"
    assert tzm.resolve("Asia/Tokyo", moment)["status"] == "ok"


def _ids(query, at=SUMMER, **kw):
    return [e["id"] for e in tzm.search(query, at, **kw)]


def test_search_by_city():
    assert _ids("belgrade") == ["Europe/Belgrade"]


def test_search_by_country_name():
    assert "Europe/Belgrade" in _ids("serbia")
    cyprus = _ids("cyprus")
    assert "Asia/Nicosia" in cyprus and "Asia/Famagusta" in cyprus


def test_search_by_country_code():
    assert "Europe/Belgrade" in _ids("rs")


def test_search_by_full_identifier():
    assert _ids("europe/belgrade") == ["Europe/Belgrade"]


def test_search_by_region_returns_many():
    assert len(_ids("europe", limit=200)) > 40


@pytest.mark.parametrize("query", ["+2", "gmt+2", "utc+2", "GMT+02:00", "+02:00", "+0200"])
def test_search_by_offset_in_several_spellings(query):
    hits = tzm.search(query, SUMMER, limit=300)
    assert hits, query
    assert "Europe/Belgrade" in [e["id"] for e in hits]
    assert all(
        e["offset_minutes"] == 120 or any(c["offset_minutes"] == 120 for c in e["possible_offsets"])
        for e in hits
    )


def test_offset_search_follows_the_date():
    assert "Europe/Belgrade" in _ids("+2", SUMMER, limit=300)
    assert "Europe/Belgrade" not in _ids("+2", WINTER, limit=300)
    assert "Europe/Belgrade" in _ids("+1", WINTER, limit=300)


def test_offset_search_can_match_either_side_of_ambiguous_time():
    at = datetime(2026, 10, 25, 2, 30)
    assert "Europe/Belgrade" in _ids("+2", at, limit=300)
    assert "Europe/Belgrade" in _ids("+1", at, limit=300)


def test_search_by_abbreviation():
    assert "Europe/Belgrade" in _ids("cest")


def test_exact_city_outranks_substring_match():
    assert _ids("london", limit=5)[0] == "Europe/London"


def test_empty_query_can_return_every_available_zone():
    assert len(tzm.search("", SUMMER, limit=2000)) == len(available_timezones())


def test_listing_contains_every_available_zone():
    assert {e["id"] for e in tzm.list_timezones(SUMMER)} == set(available_timezones())


def test_legacy_etc_zones_are_kept_but_sorted_after_normal_zones():
    entries = tzm.list_timezones(SUMMER)
    first_etc = next(i for i, e in enumerate(entries) if e["legacy_fixed_offset"])
    assert all(not e["legacy_fixed_offset"] for e in entries[:first_etc])
    assert all(e["legacy_fixed_offset"] for e in entries[first_etc:])


def test_etc_posix_reversed_sign_is_explicit():
    e = tzm.resolve("Etc/GMT+5", SUMMER)
    assert e["utc_offset"] == "UTC-05:00"
    assert e["posix_sign_reversed"] is True
    assert "POSIX name sign reversed" in e["display"]


def test_offset_search_puts_legacy_etc_matches_after_normal_zones():
    hits = tzm.search("+5", SUMMER, limit=300)
    flags = [e["legacy_fixed_offset"] for e in hits]
    if True in flags and False in flags:
        assert flags.index(True) > max(i for i, f in enumerate(flags) if not f)


def test_validation():
    assert tzm.is_valid("Europe/Belgrade")
    assert not tzm.is_valid("Europe/Beograd")
    with pytest.raises(ValueError, match="unknown timezone"):
        tzm.resolve("Mars/Olympus_Mons", SUMMER)


def test_country_table_covers_real_zones_not_synthetic_etc():
    from app.core.data.tz_countries import ZONE_COUNTRIES

    assert len(ZONE_COUNTRIES) > 400
    assert "Etc/GMT+5" not in ZONE_COUNTRIES
    assert ZONE_COUNTRIES["Europe/Belgrade"] == (("RS", "Serbia"),)


def test_version_metadata_distinguishes_package_from_iana():
    versions = tzm.tzdata_versions()
    assert "package_version" in versions
    assert "iana_version" in versions
    assert versions["package_version"]
