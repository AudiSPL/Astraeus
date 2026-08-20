"""Timezone regression tests for Astraeus.

These do not touch the astrology engine. They verify that the tz database on
this machine returns the correct historical offsets for Europe/Belgrade,
which is the input every downstream calculation depends on.

Windows note: zoneinfo has no bundled tz database. If these fail with
ZoneInfoNotFoundError, run `pip install tzdata`.

Values below were verified against the IANA database, not assumed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

BELGRADE = ZoneInfo("Europe/Belgrade")
UTC = timezone.utc


def _local(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=BELGRADE)


@pytest.mark.parametrize(
    "local_text, expected_offset_hours, expected_dst_hours, expected_utc",
    [
        # The reference chart. DST was in force in Yugoslavia in July 1984.
        ("1984-07-24 05:10", 2, 1, "1984-07-24T03:10:00+00:00"),
        # Same year, winter: standard time, catches a hardcoded +02:00.
        ("1984-01-15 12:00", 1, 0, "1984-01-15T11:00:00+00:00"),
        # 1983 is the first summer after DST was reintroduced.
        ("1983-07-01 12:00", 2, 1, "1983-07-01T10:00:00+00:00"),
        # 1982 summer has no DST. Catches a naive "July means +02:00" rule.
        ("1982-07-01 12:00", 1, 0, "1982-07-01T11:00:00+00:00"),
        # Modern date, sanity anchor.
        ("2026-08-19 12:00", 2, 1, "2026-08-19T10:00:00+00:00"),
    ],
)
def test_belgrade_historical_offsets(
    local_text, expected_offset_hours, expected_dst_hours, expected_utc
):
    moment = _local(local_text)
    assert moment.utcoffset().total_seconds() == expected_offset_hours * 3600
    assert moment.dst().total_seconds() == expected_dst_hours * 3600
    assert moment.astimezone(UTC).isoformat() == expected_utc


def test_reference_birth_moment_is_0310z():
    """The single assertion that matters most.

    A one-hour error here shifts the whole chart and, given the Ascendant
    sits about three minutes from the Cancer/Leo boundary, would silently
    produce an entirely different chart rather than an obviously wrong one.
    """
    assert _local("1984-07-24 05:10").astimezone(UTC).isoformat() == "1984-07-24T03:10:00+00:00"


def test_dst_transition_boundaries_1984():
    """Offsets flip at the transition, not a day early or late."""
    assert _local("1984-03-25 01:59").utcoffset().total_seconds() == 3600
    assert _local("1984-03-25 03:01").utcoffset().total_seconds() == 7200
    assert _local("1984-09-30 00:59").utcoffset().total_seconds() == 7200
    assert _local("1984-09-30 04:00").utcoffset().total_seconds() == 3600

# The engine-level DST assertion lives in tests/test_golden.py
# (test_engine_applies_dst_for_the_reference_birth), where it can go through
# the real /v1/chart-packet endpoint instead of guessing at an internal API.
