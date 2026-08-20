"""Semantic comparator for Astraeus golden regression files.

Engine-agnostic. Compares two decoded JSON packets and reports meaningful
differences, ignoring volatile fields and applying per-field numeric tolerance.

Design notes
------------
* A golden file records what v1 *currently produces*, not what is
  astronomically correct. When a real calculation bug is found, the golden
  file is updated deliberately, after a test proving the bug passes.
* List comparison can be positional or key-based. Key-based matching is
  important for aspect lists: a refactor that changes iteration order would
  otherwise produce hundreds of false positives.
"""

from __future__ import annotations

import fnmatch
import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

__all__ = [
    "REFACTOR_EXTRA_IGNORE",
    "Difference",
    "CompareConfig",
    "DEFAULT_CONFIG",
    "compare",
    "compare_files",
    "format_report",
]

_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?")


@dataclass(frozen=True)
class Difference:
    """A single semantic difference between golden and actual."""

    path: str
    kind: str
    golden: Any = None
    actual: Any = None
    detail: str = ""

    def __str__(self) -> str:
        base = f"{self.path or '<root>'}: {self.kind}"
        if self.kind not in ("missing_key", "extra_key", "missing_item", "extra_item"):
            base += f"  golden={self.golden!r}  actual={self.actual!r}"
        else:
            value = self.golden if self.golden is not None else self.actual
            base += f"  value={value!r}"
        if self.detail:
            base += f"  ({self.detail})"
        return base


@dataclass
class CompareConfig:
    """Comparison policy.

    ignore
        Glob patterns of paths skipped entirely. Volatile metadata only.
    numeric_tolerance
        Ordered (glob, abs_tolerance) pairs. First match wins, so put the
        most specific patterns first.
    default_numeric_tolerance
        Applied when no pattern matches.
    timestamp_tolerance_seconds
        Applied when both values parse as ISO-8601 datetimes.
    list_keys
        Ordered (glob, field-names) pairs. When a list path matches, items
        are matched by the tuple of those fields instead of by index.
    allow_new_keys
        False during the refactor (output shape must not change). Set True
        later when deliberately adding fields such as provenance or
        stable_within_minutes.
    """

    ignore: Sequence[str] = ()
    numeric_tolerance: Sequence[tuple[str, float]] = ()
    default_numeric_tolerance: float = 1e-9
    timestamp_tolerance_seconds: float = 1.0
    list_keys: Sequence[tuple[str, Sequence[str]]] = ()
    allow_new_keys: bool = False

    def tolerance_for(self, path: str) -> float:
        for pattern, tol in self.numeric_tolerance:
            if fnmatch.fnmatchcase(path, pattern):
                return tol
        return self.default_numeric_tolerance

    def keys_for(self, path: str) -> tuple[str, ...] | None:
        for pattern, keys in self.list_keys:
            if fnmatch.fnmatchcase(path, pattern):
                return tuple(keys)
        return None

    def ignored(self, path: str) -> bool:
        return any(fnmatch.fnmatchcase(path, p) for p in self.ignore)


DEFAULT_CONFIG = CompareConfig(
    ignore=("meta.generated_at",),
    numeric_tolerance=(
        # Angles straight out of Swiss Ephemeris.
        # "*lon" covers lon, cusp_lon and ecliptic_lon; "longitude" does not
        # end in "lon" so birth.longitude needs its own pattern.
        ("*lon", 1e-6),
        ("*longitude", 1e-6),
        ("*latitude", 1e-6),
        ("*.speed", 1e-6),
        ("*arc_degrees", 1e-6),
        # ~0.09 s. Tighter than the 1 s used for ISO timestamps because a JD
        # is stored, not reparsed.
        ("*julian_day_ut", 1e-6),
        # Engine-rounded display values.
        ("*deg_in_sign", 1e-4),
        ("*sun_moon_angle", 1e-2),
        # Derived quantities.
        ("*.orb", 1e-3),
        ("*.score", 1e-3),
    ),
    default_numeric_tolerance=1e-9,
    timestamp_tolerance_seconds=1.0,
    # Patterns match the full dotted path. Note that aspect lists use
    # different identity fields depending on where they sit in the packet,
    # so these cannot be collapsed into one "*aspects_to_natal" rule.
    list_keys=(
        ("*.planets", ("name",)),
        ("*directed_planets", ("name",)),
        ("*.houses", ("num",)),
        ("natal.aspects", ("a", "b", "type")),
        ("solar_return.aspects", ("a", "b", "type")),
        ("transits.aspects_to_natal", ("transit", "natal", "type")),
        ("solar_return.aspects_to_natal", ("solar_return", "natal", "type")),
        ("progressions.*.aspects_to_natal", ("directed", "natal", "type")),
        ("*natal_hits", ("natal", "type")),
        # synastry.py: cross_aspects uses primary/partner, not a/b.
        # (primary, partner, type) is unique - the function walks the full
        # cross product once, so A-Sun/B-Moon and A-Moon/B-Sun are separate
        # entries rather than duplicates.
        ("*cross_aspects", ("primary", "partner", "type")),
        ("*composite.aspects", ("a", "b", "type")),
        # forecast.transits and forecast.stations are deliberately absent:
        # the same transit/natal/type triple recurs at different dates, so
        # there is no stable key. They are date-sorted and compared
        # positionally.
    ),
    allow_new_keys=False,
)

# meta.input_hash is expected to change if the request schema changes during
# the compute_chart(config) refactor. That is a decision to make consciously,
# not a silent default, so add it to `ignore` only for the commit where the
# schema actually changes.
REFACTOR_EXTRA_IGNORE = ("meta.input_hash",)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _parse_ts(value: Any) -> datetime | None:
    if not isinstance(value, str) or not _ISO_RE.match(value):
        return None
    text = value.strip().replace(" ", "T")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _join(parent: str, key: str) -> str:
    return f"{parent}.{key}" if parent else key


def _kind_of(value: Any) -> str:
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, bool):
        return "bool"
    if _is_number(value):
        return "number"
    if value is None:
        return "null"
    return type(value).__name__


def compare(
    golden: Any,
    actual: Any,
    config: CompareConfig | None = None,
    path: str = "",
) -> list[Difference]:
    """Return every semantic difference between ``golden`` and ``actual``."""
    cfg = config or DEFAULT_CONFIG
    diffs: list[Difference] = []
    _walk(golden, actual, path, cfg, diffs)
    return diffs


def _walk(g: Any, a: Any, path: str, cfg: CompareConfig, out: list[Difference]) -> None:
    if cfg.ignored(path):
        return

    gk, ak = _kind_of(g), _kind_of(a)
    if gk != ak:
        out.append(Difference(path, "type_changed", g, a, f"{gk} -> {ak}"))
        return

    if gk == "object":
        _walk_object(g, a, path, cfg, out)
    elif gk == "array":
        _walk_array(g, a, path, cfg, out)
    elif gk == "number":
        _walk_number(g, a, path, cfg, out)
    else:
        _walk_scalar(g, a, path, cfg, out)


def _walk_object(g: dict, a: dict, path: str, cfg: CompareConfig, out: list[Difference]) -> None:
    for key in g:
        child = _join(path, key)
        if cfg.ignored(child):
            continue
        if key not in a:
            out.append(Difference(child, "missing_key", golden=g[key]))
            continue
        _walk(g[key], a[key], child, cfg, out)

    if not cfg.allow_new_keys:
        for key in a:
            child = _join(path, key)
            if key not in g and not cfg.ignored(child):
                out.append(Difference(child, "extra_key", actual=a[key]))


def _item_key(item: Any, keys: tuple[str, ...]) -> tuple | None:
    if not isinstance(item, dict):
        return None
    if any(k not in item for k in keys):
        return None
    return tuple(item[k] for k in keys)


def _walk_array(g: list, a: list, path: str, cfg: CompareConfig, out: list[Difference]) -> None:
    keys = cfg.keys_for(path)
    if keys:
        g_keyed = [(_item_key(i, keys), i) for i in g]
        a_keyed = [(_item_key(i, keys), i) for i in a]
        g_ok = all(k is not None for k, _ in g_keyed)
        a_ok = all(k is not None for k, _ in a_keyed)
        g_unique = len({k for k, _ in g_keyed}) == len(g_keyed)
        a_unique = len({k for k, _ in a_keyed}) == len(a_keyed)
        if g_ok and a_ok and g_unique and a_unique:
            _walk_keyed_array(dict(g_keyed), dict(a_keyed), path, keys, cfg, out)
            return
        out.append(
            Difference(
                path,
                "list_key_fallback",
                detail=f"key {keys} not usable here; compared positionally",
            )
        )

    if len(g) != len(a):
        out.append(
            Difference(path, "length_changed", len(g), len(a), "compared up to shorter list")
        )
    for index in range(min(len(g), len(a))):
        _walk(g[index], a[index], f"{path}[{index}]", cfg, out)


def _walk_keyed_array(
    g: dict, a: dict, path: str, keys: tuple[str, ...], cfg: CompareConfig, out: list[Difference]
) -> None:
    for key, item in g.items():
        label = "|".join(str(part) for part in key)
        child = f"{path}[{label}]"
        if key not in a:
            out.append(Difference(child, "missing_item", golden=item))
            continue
        _walk(item, a[key], child, cfg, out)
    for key, item in a.items():
        if key not in g:
            label = "|".join(str(part) for part in key)
            out.append(Difference(f"{path}[{label}]", "extra_item", actual=item))


def _walk_number(g: float, a: float, path: str, cfg: CompareConfig, out: list[Difference]) -> None:
    if math.isnan(g) and math.isnan(a):
        return
    if math.isnan(g) or math.isnan(a):
        out.append(Difference(path, "value_changed", g, a, "nan mismatch"))
        return
    tol = cfg.tolerance_for(path)
    delta = abs(g - a)
    if delta > tol:
        out.append(Difference(path, "value_changed", g, a, f"delta={delta:.3e} tol={tol:.1e}"))


def _walk_scalar(g: Any, a: Any, path: str, cfg: CompareConfig, out: list[Difference]) -> None:
    gt, at = _parse_ts(g), _parse_ts(a)
    if gt and at:
        if gt.tzinfo is None or at.tzinfo is None:
            if (gt.tzinfo is None) != (at.tzinfo is None):
                out.append(Difference(path, "value_changed", g, a, "tz-awareness mismatch"))
                return
        delta = abs((gt - at).total_seconds())
        if delta > cfg.timestamp_tolerance_seconds:
            out.append(
                Difference(
                    path,
                    "value_changed",
                    g,
                    a,
                    f"delta={delta:.3f}s tol={cfg.timestamp_tolerance_seconds}s",
                )
            )
        return
    if g != a:
        out.append(Difference(path, "value_changed", g, a))


def compare_files(
    golden_path: str | Path,
    actual: Any | str | Path,
    config: CompareConfig | None = None,
) -> list[Difference]:
    """Compare a golden file against a packet or another file."""
    golden = json.loads(Path(golden_path).read_text(encoding="utf-8"))
    if isinstance(actual, (str, Path)) and Path(actual).exists():
        actual = json.loads(Path(actual).read_text(encoding="utf-8"))
    return compare(golden, actual, config)


def format_report(diffs: Iterable[Difference], limit: int = 40) -> str:
    diffs = list(diffs)
    if not diffs:
        return "no differences"
    lines = [f"{len(diffs)} difference(s):"]
    lines += [f"  {d}" for d in diffs[:limit]]
    if len(diffs) > limit:
        lines.append(f"  ... {len(diffs) - limit} more")
    return "\n".join(lines)
