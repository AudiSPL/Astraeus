"""Convert local civil birth time to UTC and Julian Day (UT).

Uses zoneinfo + pinned tzdata so historical DST is correct (e.g. Belgrade in
July 1984 = CEST, +02:00). Always pass an IANA id, never a raw offset.
"""
import calendar
from datetime import datetime, date
from zoneinfo import ZoneInfo
import importlib.metadata as _md

import swisseph as swe

UTC = ZoneInfo("UTC")


def _parse_time(t: str):
    parts = [int(x) for x in t.split(":")] + [0, 0]
    return parts[0], parts[1], parts[2]


def to_utc_and_jd(date: str, time: str, tz: str):
    """date 'YYYY-MM-DD', time 'HH:MM[:SS]', tz IANA id.

    Returns (local_iso, utc_iso, offset_str, dst_active, julian_day_ut).
    """
    y, m, d = (int(x) for x in date.split("-"))
    hh, mm, ss = _parse_time(time)
    local = datetime(y, m, d, hh, mm, ss, tzinfo=ZoneInfo(tz))
    utc = local.astimezone(UTC)

    offset = local.utcoffset()
    offset_str = _fmt_offset(offset)
    dst_active = bool(local.dst()) and local.dst().total_seconds() != 0

    jd = swe.julday(utc.year, utc.month, utc.day,
                    utc.hour + utc.minute / 60 + utc.second / 3600, swe.GREG_CAL)
    return local.isoformat(), utc.isoformat(), offset_str, dst_active, jd


def _fmt_offset(off):
    total = int(off.total_seconds())
    sign = "+" if total >= 0 else "-"
    total = abs(total)
    return f"{sign}{total // 3600:02d}:{(total % 3600) // 60:02d}"


def tzdata_version():
    try:
        return _md.version("tzdata")
    except Exception:
        return "system"


def add_months(d: date, months: int) -> date:
    """Calendar-correct month addition for forecast period boundaries: clamps
    the day to the target month's length (Jan 31 + 1 month = Feb 28/29 on leap
    years), rolls the year over cleanly."""
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    day = min(d.day, calendar.monthrange(y, m)[1])
    return date(y, m, day)


def progressed_house_jd_real_gmt(birth_date: str, birth_time: str, tz: str, target_date: str) -> float:
    """Julian Day (UT) for secondary-progressed houses/angles using real progressed GMT.

    Progressed calendar date = birth date + day-for-a-year offset; local civil time =
    birth time at birth place, converted to UT with zoneinfo (DST-aware).
    """
    from datetime import timedelta

    b = date.fromisoformat(birth_date)
    t = date.fromisoformat(target_date)
    years_elapsed = (t - b).days / 365.2425
    prog_date = b + timedelta(days=years_elapsed)
    hh, mm, ss = _parse_time(birth_time)
    local = datetime(prog_date.year, prog_date.month, prog_date.day,
                     hh, mm, ss, tzinfo=ZoneInfo(tz))
    utc = local.astimezone(UTC)
    return swe.julday(utc.year, utc.month, utc.day,
                    utc.hour + utc.minute / 60 + utc.second / 3600, swe.GREG_CAL)


def date_to_jd_ut0(d: date) -> float:
    """Julian Day at 00:00 UT for a calendar date. Used for forecast scan
    period boundaries, where sub-day precision doesn't matter since the
    underlying scan steps daily anyway."""
    return swe.julday(d.year, d.month, d.day, 0.0)


def jd_to_utc_iso(jd: float) -> str:
    """Julian Day -> UTC ISO string, second precision. Single source of truth
    for JD->calendar conversion (forecast.py and solar_return.py both use
    this instead of rolling their own)."""
    y, m, d, h = swe.revjul(jd)
    hh = int(h)
    mm_full = (h - hh) * 60
    mm = int(mm_full)
    ss = int(round((mm_full - mm) * 60))
    if ss == 60:
        mm, ss = mm + 1, 0
    if mm == 60:
        hh, mm = hh + 1, 0
    return f"{y:04d}-{m:02d}-{d:02d}T{hh:02d}:{mm:02d}:{ss:02d}Z"
