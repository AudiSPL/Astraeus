"""Birth-time sensitivity for angle-dependent natal fields.

This module deliberately does not change the nominal chart calculation. It
measures how selected fields move when the birth instant is perturbed and
emits interpreter-facing metadata that can be used to avoid false precision.

Stage 1 covers ASC/MC sign + longitude sensitivity, chart ruler, and natal
aspects involving ASC/MC. Stage 2 adds all twelve house cusps, natal body
house-placement sensitivity, and a machine-readable list of nominal fields
that become non-unique inside the declared birth-time uncertainty.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from . import analysis, aspects, ephemeris
from .settings import ASPECTS, ASPECT_FACTOR, ORB_BY_BODY

_SEARCH_LIMIT_MINUTES = 720.0
_TRANSITION_SCAN_STEP_MINUTES = 1.0
_TRANSITION_TOLERANCE_MINUTES = 0.001  # 0.06 s
_RANGE_STEP_MINUTES = 1.0


def _signed_delta_deg(value: float, reference: float) -> float:
    """Shortest signed angular delta value-reference in [-180, 180)."""
    return ((value - reference + 180.0) % 360.0) - 180.0


def _pair_max_orb(a: str, b: str, aspect_type: str) -> float:
    base = max(ORB_BY_BODY.get(a, 3), ORB_BY_BODY.get(b, 3))
    return base * ASPECT_FACTOR[aspect_type]


def _strength(orb: float, max_orb: float) -> str:
    ratio = orb / max_orb if max_orb else 1.0
    return "tight" if ratio <= 0.25 else ("moderate" if ratio <= 0.6 else "wide")


@dataclass
class _Sampler:
    jd_ut: float
    lat: float
    lon: float
    house_system: str
    zodiac: str
    node_type: str
    include_points: list[str]
    ayanamsha_name: str | None

    def __post_init__(self):
        self._angles_cache: dict[float, dict] = {}
        self._houses_cache: dict[float, tuple[list[dict], dict, list[float]]] = {}
        self._full_cache: dict[float, tuple[dict, dict]] = {}

    @staticmethod
    def _key(offset_minutes: float) -> float:
        return round(float(offset_minutes), 6)

    def _jd(self, offset_minutes: float) -> float:
        return self.jd_ut + float(offset_minutes) / 1440.0

    def houses(self, offset_minutes: float) -> tuple[list[dict], dict, list[float]]:
        key = self._key(offset_minutes)
        if key not in self._houses_cache:
            houses, angles, cusp_lons = ephemeris.compute_houses(
                self._jd(offset_minutes), self.lat, self.lon, self.house_system,
                self.zodiac, self.ayanamsha_name,
            )
            self._houses_cache[key] = (houses, angles, cusp_lons)
            self._angles_cache[key] = angles
        return self._houses_cache[key]

    def angles(self, offset_minutes: float) -> dict:
        key = self._key(offset_minutes)
        if key not in self._angles_cache:
            self.houses(offset_minutes)
        return self._angles_cache[key]

    def full(self, offset_minutes: float) -> tuple[dict, dict]:
        key = self._key(offset_minutes)
        if key not in self._full_cache:
            bodies = ephemeris.compute_bodies(
                self._jd(offset_minutes), self.zodiac, self.node_type,
                self.include_points, self.ayanamsha_name,
            )
            angles = self.angles(offset_minutes)
            self._full_cache[key] = (bodies, angles)
        return self._full_cache[key]


def _find_transition(
    value_at: Callable[[float], str],
    nominal_value: str,
    direction: int,
    *,
    limit_minutes: float = _SEARCH_LIMIT_MINUTES,
) -> tuple[float, str] | None:
    """Nearest signed offset in one direction where a discrete value changes."""
    prev = 0.0
    step = _TRANSITION_SCAN_STEP_MINUTES
    x = step
    while x <= limit_minutes + 1e-12:
        off = direction * x
        current = value_at(off)
        if current != nominal_value:
            unchanged = prev
            changed = x
            # Binary search in positive distance from nominal; direction is
            # applied only when evaluating the field.
            while changed - unchanged > _TRANSITION_TOLERANCE_MINUTES:
                mid = (unchanged + changed) / 2.0
                if value_at(direction * mid) == nominal_value:
                    unchanged = mid
                else:
                    changed = mid
            signed = direction * changed
            return signed, value_at(signed)
        prev = x
        x += step
    return None


def _discrete_stability(value_at: Callable[[float], str], nominal: str) -> dict:
    backward = _find_transition(value_at, nominal, -1)
    forward = _find_transition(value_at, nominal, +1)
    candidates = [x for x in (backward, forward) if x is not None]
    nearest = min(candidates, key=lambda item: abs(item[0])) if candidates else None
    return {
        "value": nominal,
        "stable_within_minutes": round(abs(nearest[0]), 3) if nearest else None,
        "next_transition": (
            {"offset_minutes": round(nearest[0], 3), "value": nearest[1]}
            if nearest else None
        ),
        "previous_transition": (
            {"offset_minutes": round(backward[0], 3), "value": backward[1]}
            if backward else None
        ),
        "following_transition": (
            {"offset_minutes": round(forward[0], 3), "value": forward[1]}
            if forward else None
        ),
        "search_limit_minutes": int(_SEARCH_LIMIT_MINUTES),
    }


def _sample_offsets(uncertainty_minutes: float) -> list[float]:
    u = max(0.0, float(uncertainty_minutes))
    if u == 0:
        return [0.0]
    n = int(u // _RANGE_STEP_MINUTES)
    offsets = [float(i) for i in range(-n, n + 1)]
    if -u not in offsets:
        offsets.append(-u)
    if u not in offsets:
        offsets.append(u)
    if 0.0 not in offsets:
        offsets.append(0.0)
    return sorted(set(round(x, 6) for x in offsets))


def _angle_block(
    sampler: _Sampler,
    key: str,
    uncertainty_minutes: float | None,
) -> dict:
    nominal = sampler.angles(0.0)[key]
    sign_at = lambda off: sampler.angles(off)[key]["sign"]
    discrete = _discrete_stability(sign_at, nominal["sign"])

    minus = sampler.angles(-0.5)[key]["lon"]
    plus = sampler.angles(+0.5)[key]["lon"]
    sensitivity = _signed_delta_deg(plus, minus)  # total interval = 1 minute

    if uncertainty_minutes is None:
        possible_signs = None
        longitude_range = None
        stable_for_uncertainty = None
    else:
        offsets = _sample_offsets(uncertainty_minutes)
        points = [sampler.angles(off)[key] for off in offsets]
        possible_signs = list(dict.fromkeys([nominal["sign"], *(p["sign"] for p in points)]))
        deltas = [_signed_delta_deg(p["lon"], nominal["lon"]) for p in points]
        longitude_range = {
            "min_delta_deg": round(min(deltas), 6),
            "max_delta_deg": round(max(deltas), 6),
            "min_lon": round((nominal["lon"] + min(deltas)) % 360.0, 6),
            "max_lon": round((nominal["lon"] + max(deltas)) % 360.0, 6),
        }
        threshold = discrete["stable_within_minutes"]
        stable_for_uncertainty = bool(
            threshold is None or float(uncertainty_minutes) < float(threshold)
        )

    return {
        "sign": discrete,
        "longitude": {
            "nominal": nominal["lon"],
            "nominal_deg_in_sign": nominal["deg_in_sign"],
            "sensitivity_deg_per_min": round(sensitivity, 6),
            "range_within_declared_uncertainty": longitude_range,
        },
        "possible_signs_within_declared_uncertainty": possible_signs,
        "stable_for_declared_uncertainty": stable_for_uncertainty,
    }


def _aspect_orb_at(
    sampler: _Sampler,
    offset_minutes: float,
    a_name: str,
    b_name: str,
    aspect_type: str,
) -> float:
    bodies, angles = sampler.full(offset_minutes)

    def lon_of(name: str) -> float:
        if name == "ASC":
            return angles["asc"]["lon"]
        if name == "MC":
            return angles["mc"]["lon"]
        return bodies[name]["lon"]

    sep = aspects.separation(lon_of(a_name), lon_of(b_name))
    return abs(sep - ASPECTS[aspect_type])


def _angle_aspects(
    sampler: _Sampler,
    uncertainty_minutes: float | None,
) -> list[dict]:
    bodies, angles = sampler.full(0.0)
    targets = {
        **bodies,
        "ASC": {"name": "ASC", "lon": angles["asc"]["lon"], "speed": None},
        "MC": {"name": "MC", "lon": angles["mc"]["lon"], "speed": None},
    }
    nominal = [
        a for a in aspects.detect(targets, include_minors=False)
        if a["a"] in ("ASC", "MC") or a["b"] in ("ASC", "MC")
    ]

    out: list[dict] = []
    offsets = _sample_offsets(uncertainty_minutes) if uncertainty_minutes is not None else None
    for item in nominal:
        a_name = item["a"]
        b_name = item["b"]
        aspect_type = item["type"]
        max_orb = _pair_max_orb(a_name, b_name, aspect_type)

        if offsets is None:
            orb_range = None
            present_throughout = None
            strength_values = None
        else:
            raw = [
                _aspect_orb_at(sampler, off, a_name, b_name, aspect_type)
                for off in offsets
            ]
            low, high = min(raw), max(raw)
            orb_range = [round(low, 3), round(high, 3)]
            present_throughout = high <= max_orb + 1e-12
            strength_values = list(dict.fromkeys(
                _strength(min(v, max_orb), max_orb) if v <= max_orb else "out_of_orb"
                for v in raw
            ))

        # A local sensitivity measure is useful even when the declared time
        # uncertainty is absent. Near exactness it describes how quickly the
        # attractive nominal orb changes with one minute of birth-time shift.
        o_minus = _aspect_orb_at(sampler, -0.5, a_name, b_name, aspect_type)
        o_plus = _aspect_orb_at(sampler, +0.5, a_name, b_name, aspect_type)
        nominal_orb = float(item["orb"])
        orb_sensitivity = max(
            abs(o_minus - nominal_orb) / 0.5,
            abs(o_plus - nominal_orb) / 0.5,
        )

        out.append({
            "a": item["a"],
            "b": item["b"],
            "type": aspect_type,
            "nominal_orb": item["orb"],
            "max_orb": round(max_orb, 3),
            "birth_time_sensitive": True,
            "orb_sensitivity_deg_per_min": round(orb_sensitivity, 6),
            "orb_range": orb_range,
            "present_throughout_declared_uncertainty": present_throughout,
            "possible_strengths_within_declared_uncertainty": strength_values,
        })
    return out


def _bounded_discrete_stability(
    value_at: Callable[[float], object],
    nominal_value: object,
    uncertainty_minutes: float | None,
) -> dict:
    """Find discrete transitions only inside the declared uncertainty window.

    Stage-2 house fields do not scan an arbitrary 12-hour horizon when the
    user has not declared a numeric uncertainty. This keeps the packet cheap
    while answering the question that matters: can this field change inside
    the stated +/- window?
    """
    if uncertainty_minutes is None:
        return {
            "value": nominal_value,
            "stable_within_minutes": None,
            "stable_at_least_minutes": None,
            "next_transition": None,
            "previous_transition": None,
            "following_transition": None,
            "search_limit_minutes": None,
        }

    limit = max(0.0, float(uncertainty_minutes))
    if limit == 0:
        return {
            "value": nominal_value,
            "stable_within_minutes": None,
            "stable_at_least_minutes": 0.0,
            "next_transition": None,
            "previous_transition": None,
            "following_transition": None,
            "search_limit_minutes": 0.0,
        }

    backward = _find_transition(value_at, nominal_value, -1, limit_minutes=limit)
    forward = _find_transition(value_at, nominal_value, +1, limit_minutes=limit)
    candidates = [x for x in (backward, forward) if x is not None]
    nearest = min(candidates, key=lambda item: abs(item[0])) if candidates else None
    return {
        "value": nominal_value,
        "stable_within_minutes": round(abs(nearest[0]), 3) if nearest else None,
        "stable_at_least_minutes": None if nearest else round(limit, 3),
        "next_transition": (
            {"offset_minutes": round(nearest[0], 3), "value": nearest[1]}
            if nearest else None
        ),
        "previous_transition": (
            {"offset_minutes": round(backward[0], 3), "value": backward[1]}
            if backward else None
        ),
        "following_transition": (
            {"offset_minutes": round(forward[0], 3), "value": forward[1]}
            if forward else None
        ),
        "search_limit_minutes": round(limit, 3),
    }


def _cusp_block(
    sampler: _Sampler,
    house_index: int,
    uncertainty_minutes: float | None,
) -> dict:
    """Stability metadata for one house cusp (0-based house_index)."""
    nominal = sampler.houses(0.0)[0][house_index]

    def sign_at(off: float) -> str:
        return sampler.houses(off)[0][house_index]["sign"]

    discrete = _bounded_discrete_stability(sign_at, nominal["sign"], uncertainty_minutes)
    minus = sampler.houses(-0.5)[0][house_index]["cusp_lon"]
    plus = sampler.houses(+0.5)[0][house_index]["cusp_lon"]
    sensitivity = _signed_delta_deg(plus, minus)

    if uncertainty_minutes is None:
        possible_signs = None
        longitude_range = None
        stable_for_uncertainty = None
    else:
        offsets = _sample_offsets(uncertainty_minutes)
        points = [sampler.houses(off)[0][house_index] for off in offsets]
        transition_values = [
            t["value"] for t in (discrete["previous_transition"], discrete["following_transition"])
            if t is not None
        ]
        possible_signs = list(dict.fromkeys(
            [nominal["sign"], *transition_values, *(p["sign"] for p in points)]
        ))
        deltas = [_signed_delta_deg(p["cusp_lon"], nominal["cusp_lon"]) for p in points]
        longitude_range = {
            "min_delta_deg": round(min(deltas), 6),
            "max_delta_deg": round(max(deltas), 6),
            "min_lon": round((nominal["cusp_lon"] + min(deltas)) % 360.0, 6),
            "max_lon": round((nominal["cusp_lon"] + max(deltas)) % 360.0, 6),
        }
        stable_for_uncertainty = not bool(
            discrete["previous_transition"] or discrete["following_transition"]
        )

    return {
        "house": house_index + 1,
        "sign": discrete,
        "longitude": {
            "nominal": nominal["cusp_lon"],
            "sensitivity_deg_per_min": round(sensitivity, 6),
            "range_within_declared_uncertainty": longitude_range,
        },
        "possible_signs_within_declared_uncertainty": possible_signs,
        "stable_for_declared_uncertainty": stable_for_uncertainty,
    }


def _house_placement_at(sampler: _Sampler, offset_minutes: float, body_name: str) -> int:
    bodies, _ = sampler.full(offset_minutes)
    _, _, cusp_lons = sampler.houses(offset_minutes)
    return ephemeris.house_of(bodies[body_name]["lon"], cusp_lons)


def _house_placements(
    sampler: _Sampler,
    uncertainty_minutes: float | None,
) -> list[dict]:
    bodies, _ = sampler.full(0.0)
    offsets = _sample_offsets(uncertainty_minutes) if uncertainty_minutes is not None else None
    out: list[dict] = []

    for planet_index, body_name in enumerate(bodies):
        nominal_house = _house_placement_at(sampler, 0.0, body_name)
        value_at = lambda off, name=body_name: _house_placement_at(sampler, off, name)
        discrete = _bounded_discrete_stability(value_at, nominal_house, uncertainty_minutes)

        if offsets is None:
            possible_houses = None
            stable_for_uncertainty = None
        else:
            transition_values = [
                t["value"] for t in (discrete["previous_transition"], discrete["following_transition"])
                if t is not None
            ]
            possible_houses = list(dict.fromkeys(
                [nominal_house, *transition_values, *(value_at(off) for off in offsets)]
            ))
            stable_for_uncertainty = not bool(
                discrete["previous_transition"] or discrete["following_transition"]
            )

        out.append({
            "body": body_name,
            "planet_index": planet_index,
            "nominal_house": nominal_house,
            "stable_within_minutes": discrete["stable_within_minutes"],
            "stable_at_least_minutes": discrete["stable_at_least_minutes"],
            "previous_transition": discrete["previous_transition"],
            "following_transition": discrete["following_transition"],
            "next_transition": discrete["next_transition"],
            "search_limit_minutes": discrete["search_limit_minutes"],
            "possible_houses_within_declared_uncertainty": possible_houses,
            "stable_for_declared_uncertainty": stable_for_uncertainty,
        })
    return out


def _nominal_field_status(
    *,
    declared: float | None,
    asc: dict,
    mc: dict,
    ruler: dict,
    cusps: list[dict],
    placements: list[dict],
) -> dict:
    """Summarize nominal fields that are non-unique in the declared window.

    Legacy natal values remain unchanged for backward compatibility. This block
    tells interpreters which point estimates are only one of several candidates.
    """
    if declared is None:
        return {
            "declared_uncertainty_assessed": False,
            "nominal_values_are_point_estimates": True,
            "unstable_fields": None,
        }

    unstable: list[dict] = []
    for angle_name, angle in (("asc", asc), ("mc", mc)):
        signs = angle.get("possible_signs_within_declared_uncertainty") or []
        if len(signs) > 1:
            unstable.append({
                "path": f"natal.angles.{angle_name}.sign",
                "angle": angle_name.upper(),
                "nominal": angle["sign"]["value"],
                "possible_values": signs,
            })

    ruler_values = ruler.get("possible_values_within_declared_uncertainty") or []
    if len(ruler_values) > 1:
        unstable.append({
            "path": "natal.chart_ruler",
            "nominal": ruler["value"],
            "possible_values": ruler_values,
        })

    for cusp in cusps:
        signs = cusp.get("possible_signs_within_declared_uncertainty") or []
        if len(signs) > 1:
            unstable.append({
                "path": f"natal.houses[{cusp['house'] - 1}].sign",
                "house": cusp["house"],
                "nominal": cusp["sign"]["value"],
                "possible_values": signs,
            })

    for placement in placements:
        houses = placement.get("possible_houses_within_declared_uncertainty") or []
        if len(houses) > 1:
            unstable.append({
                "path": f"natal.planets[{placement['planet_index']}].house",
                "body": placement["body"],
                "nominal": placement["nominal_house"],
                "possible_values": houses,
            })

    return {
        "declared_uncertainty_assessed": True,
        "nominal_values_are_point_estimates": bool(declared > 0),
        "unstable_fields": unstable,
    }


def compute_birth_time_stability(
    *,
    jd_ut: float,
    lat: float,
    lon: float,
    house_system: str,
    zodiac: str,
    node_type: str,
    include_points: list[str],
    ayanamsha_name: str | None,
    time_accuracy: str,
    time_uncertainty_minutes: float | None,
    birth_time_provenance: str = "user_supplied",
    civil_time_status: str = "ok",
) -> dict:
    """Return additive field-level birth-time sensitivity metadata.

    ``time_uncertainty_minutes`` is symmetric (+/- minutes). ``None`` means the
    amount of uncertainty was not declared, so intrinsic thresholds are still
    calculated but uncertainty-dependent ranges are intentionally left null.
    """
    # A repeated civil wall time (DST fold) represents two different UTC instants.
    # Even an otherwise "exact" clock reading is unresolved until the occurrence
    # is known, so do not let a zero-minute declaration falsely mark angle/house
    # fields as resolved.
    if civil_time_status == "ambiguous":
        declared = None
    elif time_accuracy == "exact" and time_uncertainty_minutes is None:
        declared = 0.0
    elif time_accuracy == "unknown":
        declared = None
    else:
        declared = None if time_uncertainty_minutes is None else float(time_uncertainty_minutes)

    sampler = _Sampler(
        jd_ut=jd_ut, lat=lat, lon=lon, house_system=house_system, zodiac=zodiac,
        node_type=node_type, include_points=include_points,
        ayanamsha_name=ayanamsha_name,
    )

    asc = _angle_block(sampler, "asc", declared)
    mc = _angle_block(sampler, "mc", declared)

    ruler_nominal = analysis.chart_ruler(sampler.angles(0.0)["asc"]["lon"])
    ruler_at = lambda off: analysis.chart_ruler(sampler.angles(off)["asc"]["lon"])
    ruler = _discrete_stability(ruler_at, ruler_nominal)
    if declared is None:
        ruler["possible_values_within_declared_uncertainty"] = None
        ruler["stable_for_declared_uncertainty"] = None
    else:
        values = [ruler_at(off) for off in _sample_offsets(declared)]
        ruler["possible_values_within_declared_uncertainty"] = list(dict.fromkeys(values))
        threshold = ruler["stable_within_minutes"]
        ruler["stable_for_declared_uncertainty"] = bool(
            threshold is None or declared < float(threshold)
        )

    house_cusps = [_cusp_block(sampler, i, declared) for i in range(12)]
    house_placements = _house_placements(sampler, declared)
    nominal_status = _nominal_field_status(
        declared=declared, asc=asc, mc=mc, ruler=ruler,
        cusps=house_cusps, placements=house_placements,
    )

    return {
        "method": "symmetric birth-time perturbation around nominal UT; Swiss Ephemeris recomputation",
        "scope": "stage_2_angles_chart_ruler_angle_aspects_house_cusps_house_placements",
        "birth_time_provenance": birth_time_provenance,
        "birth_time_precision": {
            "time_accuracy": time_accuracy,
            "declared_uncertainty_minutes": declared,
            "civil_time_status": civil_time_status,
        },
        "asc": asc,
        "mc": mc,
        "chart_ruler": ruler,
        "angle_aspects": _angle_aspects(sampler, declared),
        "house_cusps": house_cusps,
        "house_placements": house_placements,
        "nominal_field_status": nominal_status,
        "notes": [
            "The calculation core remains nominal; Stage-3 output qualification suppresses unresolved scalar angle/house values in the interpreter-facing packet.",
            "Use nominal_field_status and the per-field possible-values arrays whenever declared uncertainty is non-zero.",
            "Stage-2 house transition searches are bounded to the declared uncertainty window; stable_at_least_minutes records a cleared window when no transition is found.",
            "A null uncertainty-dependent range means no numeric birth-time uncertainty was declared.",
        ],
    }
