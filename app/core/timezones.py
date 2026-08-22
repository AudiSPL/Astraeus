"""IANA timezone listing and search for the Astraeus UI.

This module is deliberately UI-facing. It uses the same ``zoneinfo``/``tzdata``
source as the calculation engine so the browser never has to guess historical
or seasonal UTC offsets from its own OS database.

It does *not* change calculation semantics. In particular, a ``gap`` or
``ambiguous`` status is surfaced to the picker, while rejection/warning logic
for chart calculation belongs to the separate DST-correctness change.
"""
from __future__ import annotations

import importlib.metadata as _md
import re
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo, available_timezones

from .data.tz_countries import ZONE_COUNTRIES

__all__ = [
    "is_valid",
    "list_timezones",
    "resolve",
    "search",
    "tzdata_versions",
]

_OFFSET_QUERY = re.compile(
    r"^\s*(?:gmt|utc)?\s*([+-])\s*(\d{1,2})(?::?(\d{2}))?\s*$",
    re.IGNORECASE,
)
_ETC_REVERSED = re.compile(r"^Etc/GMT[+-]\d+$")


@lru_cache(maxsize=1)
def _zone_ids() -> tuple[str, ...]:
    return tuple(sorted(available_timezones()))


def is_valid(zone: str) -> bool:
    return zone in _zone_ids()


def tzdata_versions() -> dict[str, str | None]:
    """Return both package and IANA release identifiers.

    ``tzdata`` package versions use a Python-package form such as ``2026.2``;
    the underlying IANA release uses a different scheme such as ``2026b``.
    They are related, but not interchangeable, so the API exposes both.
    """
    try:
        package_version = _md.version("tzdata")
    except Exception:
        package_version = "system"

    try:
        import tzdata

        iana_version = getattr(tzdata, "IANA_VERSION", None)
    except Exception:
        iana_version = None

    return {
        "package_version": package_version,
        "iana_version": iana_version,
    }


def _format_offset(delta: timedelta, prefix: str = "GMT") -> str:
    total = int(delta.total_seconds())
    sign = "-" if total < 0 else "+"
    hours, minutes = divmod(abs(total) // 60, 60)
    return f"{prefix}{sign}{hours:02d}:{minutes:02d}"


def _clean_abbreviation(value: str | None) -> str | None:
    if not value:
        return None
    if value[0] in "+-" and value[1:].replace(":", "").isdigit():
        return None
    return value


def _candidate(naive: datetime, tz: ZoneInfo, fold: int) -> dict:
    aware = naive.replace(tzinfo=tz, fold=fold)
    utc = aware.astimezone(timezone.utc)
    roundtrip = utc.astimezone(tz)
    offset = aware.utcoffset() or timedelta(0)
    dst = aware.dst() or timedelta(0)
    return {
        "fold": fold,
        "valid": roundtrip.replace(tzinfo=None) == naive,
        "offset_minutes": int(offset.total_seconds() // 60),
        "offset_label": _format_offset(offset),
        "utc_offset": _format_offset(offset, "UTC"),
        "abbreviation": _clean_abbreviation(aware.tzname()),
        "dst_active": dst != timedelta(0),
    }


def _status_and_candidates(naive: datetime, tz: ZoneInfo) -> tuple[str, list[dict]]:
    c0 = _candidate(naive, tz, 0)
    c1 = _candidate(naive, tz, 1)
    valid = [c for c in (c0, c1) if c["valid"]]

    if not valid:
        return "gap", []

    # At ordinary times fold=0 and fold=1 describe the same instant/offset.
    if len(valid) == 2 and valid[0]["offset_minutes"] != valid[1]["offset_minutes"]:
        return "ambiguous", valid

    return "ok", [valid[0]]


def _city(zone: str) -> str:
    return zone.rsplit("/", 1)[-1].replace("_", " ")


def _is_legacy_fixed(zone: str) -> bool:
    return zone.startswith("Etc/")


def _display_for(entry: dict) -> str:
    zone = entry["id"]
    status = entry["status"]

    if status == "gap":
        return f"{zone} — invalid local time (DST gap)"

    if status == "ambiguous":
        parts = []
        for c in entry["possible_offsets"]:
            text = c["offset_label"]
            if c["abbreviation"]:
                text += f" ({c['abbreviation']})"
            parts.append(text)
        return f"{zone} — ambiguous: " + " / ".join(parts)

    text = f"{zone} — {entry['offset_label']}"
    if entry["abbreviation"]:
        text += f" ({entry['abbreviation']})"

    if entry["posix_sign_reversed"]:
        # Use the *actual* UTC offset prominently; the identifier itself uses
        # POSIX's historical reversed-sign naming convention.
        text = f"{zone} — {entry['utc_offset']} fixed (POSIX name sign reversed)"
    elif entry["legacy_fixed_offset"]:
        text += " fixed"
    return text


def resolve(zone: str, at: datetime) -> dict:
    """Resolve one IANA zone at one naive local wall-clock datetime."""
    if at.tzinfo is not None:
        raise ValueError("`at` must be a naive local datetime, not an aware one")
    if not is_valid(zone):
        raise ValueError(f"unknown timezone {zone!r}")

    tz = ZoneInfo(zone)
    status, candidates = _status_and_candidates(at, tz)
    primary = candidates[0] if status == "ok" else None
    countries = ZONE_COUNTRIES.get(zone, ())
    posix_reversed = bool(_ETC_REVERSED.match(zone))

    entry = {
        "id": zone,
        "city": _city(zone),
        "countries": [{"code": code, "name": name} for code, name in countries],
        "status": status,
        "offset_minutes": primary["offset_minutes"] if primary else None,
        "offset_label": primary["offset_label"] if primary else None,
        "utc_offset": primary["utc_offset"] if primary else None,
        "abbreviation": primary["abbreviation"] if primary else None,
        "dst_active": primary["dst_active"] if primary else None,
        "possible_offsets": candidates if status == "ambiguous" else [],
        "legacy_fixed_offset": _is_legacy_fixed(zone),
        "posix_sign_reversed": posix_reversed,
    }

    if status == "gap":
        entry["note"] = "this local time does not exist here; the clock jumps over it"
    elif status == "ambiguous":
        entry["note"] = "this local time occurs twice here; the clock repeats it"
    elif posix_reversed:
        entry["note"] = "Etc/GMT identifiers use the historical POSIX reversed-sign convention"

    entry["display"] = _display_for(entry)
    return entry


def _sort_offset(entry: dict) -> int:
    if entry["offset_minutes"] is not None:
        return entry["offset_minutes"]
    if entry["possible_offsets"]:
        return min(c["offset_minutes"] for c in entry["possible_offsets"])
    return 10**9


def list_timezones(at: datetime, zones: list[str] | tuple[str, ...] | None = None) -> list[dict]:
    """Resolve all requested zones, keeping legacy ``Etc/*`` entries last."""
    ids = zones if zones is not None else _zone_ids()
    out = [resolve(zone, at) for zone in ids if is_valid(zone)]
    out.sort(key=lambda e: (e["legacy_fixed_offset"], _sort_offset(e), e["id"]))
    return out


def _offset_from_query(query: str) -> int | None:
    match = _OFFSET_QUERY.match(query)
    if not match:
        return None
    sign, hours, minutes = match.groups()
    hour = int(hours)
    minute = int(minutes or 0)
    if hour > 23 or minute > 59:
        return None
    total = hour * 60 + minute
    return -total if sign == "-" else total


def _matches_offset(entry: dict, wanted: int) -> bool:
    if entry["offset_minutes"] == wanted:
        return True
    return any(c["offset_minutes"] == wanted for c in entry["possible_offsets"])


def search(query: str, at: datetime, limit: int = 50) -> list[dict]:
    """Search by id/city/country/code/abbreviation or UTC/GMT offset."""
    entries = list_timezones(at)
    text = query.strip().lower()
    if not text:
        return entries[:limit]

    wanted_offset = _offset_from_query(query)
    if wanted_offset is not None:
        hits = [entry for entry in entries if _matches_offset(entry, wanted_offset)]
        hits.sort(key=lambda e: (e["legacy_fixed_offset"], e["id"]))
        return hits[:limit]

    scored: list[tuple[int, dict]] = []
    for entry in entries:
        zone_id = entry["id"].lower()
        city = entry["city"].lower()
        countries = [(c["code"].lower(), c["name"].lower()) for c in entry["countries"]]
        abbreviations = []
        if entry["abbreviation"]:
            abbreviations.append(entry["abbreviation"].lower())
        abbreviations.extend(
            c["abbreviation"].lower()
            for c in entry["possible_offsets"]
            if c["abbreviation"]
        )

        if zone_id == text or city == text:
            rank = 0
        elif city.startswith(text):
            rank = 1
        elif any(code == text or name == text for code, name in countries):
            rank = 2
        elif any(name.startswith(text) for _, name in countries):
            rank = 3
        elif text in zone_id.replace("_", " "):
            rank = 4
        elif any(text in name for _, name in countries):
            rank = 5
        elif text in abbreviations:
            rank = 6
        else:
            continue
        scored.append((rank, entry))

    scored.sort(
        key=lambda pair: (
            pair[0],
            pair[1]["legacy_fixed_offset"],
            _sort_offset(pair[1]),
            pair[1]["id"],
        )
    )
    return [entry for _, entry in scored[:limit]]
