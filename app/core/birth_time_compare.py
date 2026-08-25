"""Deterministic birth-time candidate comparison.

Each candidate wall-clock time is calculated independently as a point state.
The output never mixes angle/house geometry from different candidate states and
never claims that a candidate time is the true birth time.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any

from .packet import InputError, build_packet

SCHEMA_VERSION = "birth_time_comparison_v1"
MAX_CANDIDATES = 12
_TIME_RE = re.compile(r"^(?P<h>[01]\d|2[0-3]):(?P<m>[0-5]\d)(?::(?P<s>[0-5]\d))?$")
_ANGLES = {"ASC", "MC"}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _normalise_time(value: str) -> tuple[str, int]:
    if not isinstance(value, str):
        raise InputError("candidate_times entries must be strings in HH:MM or HH:MM:SS form")
    m = _TIME_RE.fullmatch(value.strip())
    if not m:
        raise InputError(f"invalid candidate time {value!r}; expected HH:MM or HH:MM:SS")
    h = int(m.group("h"))
    minute = int(m.group("m"))
    second = int(m.group("s") or 0)
    return f"{h:02d}:{minute:02d}:{second:02d}", h * 3600 + minute * 60 + second


def _normalise_candidates(values: Any) -> list[str]:
    if not isinstance(values, list):
        raise InputError("candidate_times must be a list")
    if len(values) < 2:
        raise InputError("Birth-Time Comparison requires at least 2 candidate times")
    if len(values) > MAX_CANDIDATES:
        raise InputError(f"Birth-Time Comparison supports at most {MAX_CANDIDATES} candidate times")
    parsed = [_normalise_time(v) for v in values]
    by_time: dict[int, str] = {}
    for text, seconds in parsed:
        if seconds in by_time:
            raise InputError(f"duplicate candidate time after normalisation: {text}")
        by_time[seconds] = text
    return [by_time[k] for k in sorted(by_time)]


def _qualified_value(value: Any) -> Any:
    if isinstance(value, dict):
        if value.get("resolved") is False:
            return None
        if "value" in value:
            return value.get("value")
        if "nominal" in value:
            return value.get("nominal")
    return value


def _candidate_request(base_request: dict[str, Any], candidate_time: str) -> dict[str, Any]:
    birth = deepcopy(base_request.get("birth"))
    if not isinstance(birth, dict):
        raise InputError("base_request.birth is required")
    if not birth.get("date"):
        raise InputError("base_request.birth.date is required")

    # Candidate charts are point evaluations only. This does not rewrite the
    # source provenance; it simply disables uncertainty sampling inside each
    # candidate so all geometry belongs to one exact calculated instant.
    birth["time"] = candidate_time
    birth["time_accuracy"] = "exact"
    birth["time_uncertainty_minutes"] = 0

    settings = deepcopy(base_request.get("settings") or {})
    if not isinstance(settings, dict):
        raise InputError("base_request.settings must be an object when provided")

    # Optional modules are intentionally not copied. v1 is natal geometry only.
    return {"birth": birth, "settings": settings}


def _angle_state(natal: dict[str, Any], key: str) -> dict[str, Any]:
    raw = (natal.get("angles") or {}).get(key) or {}
    sign = _qualified_value(raw.get("sign"))
    lon = raw.get("nominal_lon", raw.get("lon"))
    if lon is None:
        raise InputError(f"candidate packet is missing natal angle longitude for {key}")
    return {
        "longitude": round(float(lon) % 360.0, 6),
        "sign": sign,
        "deg_in_sign": round(float(lon) % 30.0, 4),
    }


def _house_state(row: dict[str, Any]) -> dict[str, Any]:
    num = row.get("num", row.get("house"))
    lon = row.get("nominal_cusp_lon", row.get("cusp_lon"))
    if num is None or lon is None:
        raise InputError("candidate packet contains an incomplete natal house row")
    return {
        "house": int(num),
        "cusp_longitude": round(float(lon) % 360.0, 6),
        "sign": _qualified_value(row.get("sign")),
    }


def _planet_state(row: dict[str, Any]) -> dict[str, Any]:
    house = _qualified_value(row.get("house"))
    return {
        "name": row.get("name"),
        "longitude": round(float(row.get("lon")) % 360.0, 6),
        "sign": row.get("sign"),
        "deg_in_sign": round(float(row.get("deg_in_sign")), 4),
        "retrograde": bool(row.get("retrograde")),
        "house": None if house is None else int(house),
    }


def _aspect_state(row: dict[str, Any]) -> dict[str, Any] | None:
    a, b = row.get("a"), row.get("b")
    if a not in _ANGLES and b not in _ANGLES:
        return None
    if a in _ANGLES and b in _ANGLES:
        body, angle = a, b
    elif a in _ANGLES:
        body, angle = b, a
    else:
        body, angle = a, b
    orb = row.get("nominal_orb", row.get("orb"))
    if orb is None:
        return None
    item = {
        "body": body,
        "angle": angle,
        "type": row.get("type"),
        "orb": round(float(orb), 3),
        "strength": row.get("nominal_strength", row.get("strength")),
    }
    return item


def _aspect_key(row: dict[str, Any]) -> str:
    return f"{row['body']}|{row['angle']}|{row['type']}"


def _extract_state(packet: dict[str, Any], state_id: str, candidate_time: str) -> dict[str, Any]:
    natal = packet.get("natal") or {}
    birth = packet.get("birth") or {}
    civil_status = birth.get("civil_time_status")
    if civil_status == "ambiguous":
        raise InputError(
            f"candidate {candidate_time} is an ambiguous local civil time; "
            "Birth-Time Comparison v1 requires one unambiguous instant per candidate"
        )
    if (packet.get("validation") or {}).get("natal_validated") is not True:
        raise InputError(f"candidate {candidate_time} did not produce a validated natal block")

    chart_ruler = _qualified_value(natal.get("chart_ruler"))
    houses = sorted((_house_state(h) for h in natal.get("houses") or []), key=lambda x: x["house"])
    planets = [_planet_state(p) for p in natal.get("planets") or []]
    angle_aspects = [x for x in (_aspect_state(a) for a in natal.get("aspects") or []) if x]
    angle_aspects.sort(key=lambda x: (x["angle"], x["body"], x["type"] or ""))

    return {
        "state_id": state_id,
        "candidate_time": candidate_time,
        "birth_local": birth.get("local"),
        "birth_utc": birth.get("utc"),
        "utc_offset": birth.get("utc_offset"),
        "civil_time_status": civil_status,
        "chart_ruler": chart_ruler,
        "angles": {
            "asc": _angle_state(natal, "asc"),
            "mc": _angle_state(natal, "mc"),
        },
        "houses": houses,
        "planets": planets,
        "angle_aspects": angle_aspects,
    }


def _categorical_rows(states: list[dict[str, Any]]) -> list[tuple[str, list[Any]]]:
    rows: list[tuple[str, list[Any]]] = []
    rows.append(("chart_ruler", [s.get("chart_ruler") for s in states]))
    rows.append(("asc.sign", [s["angles"]["asc"].get("sign") for s in states]))
    rows.append(("mc.sign", [s["angles"]["mc"].get("sign") for s in states]))

    house_nums = sorted({h["house"] for s in states for h in s.get("houses", [])})
    for num in house_nums:
        vals = []
        for s in states:
            item = next((h for h in s.get("houses", []) if h["house"] == num), None)
            vals.append(None if item is None else item.get("sign"))
        rows.append((f"house.{num}.sign", vals))

    planet_names = sorted({p["name"] for s in states for p in s.get("planets", []) if p.get("name")})
    for name in planet_names:
        house_vals, sign_vals = [], []
        for s in states:
            item = next((p for p in s.get("planets", []) if p.get("name") == name), None)
            house_vals.append(None if item is None else item.get("house"))
            sign_vals.append(None if item is None else item.get("sign"))
        rows.append((f"planet.{name}.house", house_vals))
        rows.append((f"planet.{name}.sign", sign_vals))
    return rows


def _comparison(states: list[dict[str, Any]]) -> dict[str, Any]:
    stable_fields: list[dict[str, Any]] = []
    changed_fields: list[dict[str, Any]] = []
    transition_intervals: list[dict[str, Any]] = []

    rows = _categorical_rows(states)
    for field, values in rows:
        if all(v == values[0] for v in values[1:]):
            stable_fields.append({"field": field, "value": values[0]})
        else:
            changed_fields.append({
                "field": field,
                "values": [
                    {"state_id": s["state_id"], "time": s["candidate_time"], "value": value}
                    for s, value in zip(states, values)
                ],
            })
            for i in range(len(states) - 1):
                if values[i] != values[i + 1]:
                    transition_intervals.append({
                        "field": field,
                        "from_state_id": states[i]["state_id"],
                        "from_time": states[i]["candidate_time"],
                        "from_value": values[i],
                        "to_state_id": states[i + 1]["state_id"],
                        "to_time": states[i + 1]["candidate_time"],
                        "to_value": values[i + 1],
                        "resolution": "bounded_by_adjacent_sampled_candidates",
                    })

    aspect_maps = [{_aspect_key(a): a for a in s.get("angle_aspects", [])} for s in states]
    all_keys = sorted(set().union(*(set(m) for m in aspect_maps))) if aspect_maps else []
    stable_angle_aspects: list[dict[str, Any]] = []
    variable_angle_aspects: list[dict[str, Any]] = []
    for key in all_keys:
        present = [key in m for m in aspect_maps]
        values = [m.get(key) for m in aspect_maps]
        if all(present):
            first = values[0]
            stable_angle_aspects.append({
                "aspect": key,
                "body": first["body"],
                "angle": first["angle"],
                "type": first["type"],
                "orb_by_candidate": [
                    {"state_id": s["state_id"], "time": s["candidate_time"], "orb": v["orb"], "strength": v.get("strength")}
                    for s, v in zip(states, values)
                ],
            })
        else:
            variable_angle_aspects.append({
                "aspect": key,
                "presence_by_candidate": [
                    {"state_id": s["state_id"], "time": s["candidate_time"], "present": p, "orb": None if v is None else v.get("orb")}
                    for s, p, v in zip(states, present, values)
                ],
            })
            for i in range(len(states) - 1):
                if present[i] != present[i + 1]:
                    transition_intervals.append({
                        "field": f"angle_aspect.{key}",
                        "from_state_id": states[i]["state_id"],
                        "from_time": states[i]["candidate_time"],
                        "from_value": "present" if present[i] else "absent",
                        "to_state_id": states[i + 1]["state_id"],
                        "to_time": states[i + 1]["candidate_time"],
                        "to_value": "present" if present[i + 1] else "absent",
                        "resolution": "bounded_by_adjacent_sampled_candidates",
                    })

    return {
        "stable_fields": stable_fields,
        "changed_fields": changed_fields,
        "transition_intervals": transition_intervals,
        "stable_angle_aspects": stable_angle_aspects,
        "variable_angle_aspects": variable_angle_aspects,
        "summary": {
            "candidate_count": len(states),
            "stable_field_count": len(stable_fields),
            "changed_field_count": len(changed_fields),
            "transition_interval_count": len(transition_intervals),
            "stable_angle_aspect_count": len(stable_angle_aspects),
            "variable_angle_aspect_count": len(variable_angle_aspects),
        },
    }


def build_birth_time_comparison(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise InputError("Birth-Time Comparison payload must be an object")
    base_request = payload.get("base_request")
    if not isinstance(base_request, dict):
        raise InputError("base_request must be an object")
    candidates = _normalise_candidates(payload.get("candidate_times"))

    source_birth = deepcopy(base_request.get("birth") or {})
    source_precision = {
        "time": source_birth.get("time"),
        "time_accuracy": source_birth.get("time_accuracy", "unknown"),
        "time_uncertainty_minutes": source_birth.get("time_uncertainty_minutes"),
        "birth_time_provenance": source_birth.get("birth_time_provenance", "user_supplied"),
    }

    states: list[dict[str, Any]] = []
    calc_meta: dict[str, Any] | None = None
    for idx, candidate_time in enumerate(candidates, start=1):
        packet = build_packet(_candidate_request(base_request, candidate_time))
        if calc_meta is None:
            calc_meta = {
                "calc_version": (packet.get("meta") or {}).get("calc_version"),
                "settings_version": (packet.get("meta") or {}).get("settings_version"),
                "output_contract_version": (packet.get("meta") or {}).get("output_contract_version"),
                "settings": deepcopy(packet.get("settings") or {}),
            }
        states.append(_extract_state(packet, f"T{idx}", candidate_time))

    comparison = _comparison(states)
    core = {
        "schema_version": SCHEMA_VERSION,
        "mode": "independent_point_candidate_states",
        "source_birth": {
            "date": source_birth.get("date"),
            "place_label": source_birth.get("place_label"),
            "city": source_birth.get("city"),
            "latitude": source_birth.get("latitude"),
            "longitude": source_birth.get("longitude"),
            "timezone": source_birth.get("timezone"),
            "declared_precision": source_precision,
        },
        "calculation": calc_meta,
        "candidate_times": candidates,
        "candidate_states": states,
        "comparison": comparison,
        "contract": {
            "candidate_time_is_point_evaluation_only": True,
            "source_provenance_not_rewritten": True,
            "optional_modules_withheld": ["transit", "forecast", "progressions", "solar_return", "synastry", "bazi"],
            "candidate_geometry_must_not_be_mixed": True,
            "transition_intervals_are_sample_bounds_not_exact_roots": True,
            "rectification_claimed": False,
        },
    }
    return {
        **core,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "comparison_hash": _sha256(core),
    }
