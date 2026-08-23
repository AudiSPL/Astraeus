"""Interpreter-safe qualification of birth-time-dependent natal fields.

The calculation core still produces one nominal chart at the recorded civil
instant.  This module is an output adapter: it combines that nominal chart with
``birth_time_stability`` so fields whose value depends materially on birth time
cannot be mistaken for uniquely known facts.

Only fields already measured by the stability sampler are transformed here:
angles, chart ruler, house cusps, natal house placements, and natal aspects that
involve ASC/MC. Planetary longitudes and planet-to-planet aspects keep their v1
shape.
"""
from __future__ import annotations

import copy


def _resolved_value(nominal, stable):
    """Return the nominal value only when the declared window resolves it."""
    return nominal if stable is True else None


def _qualified_discrete(
    nominal,
    possible,
    stable,
    *,
    stable_within_minutes=None,
    previous_transition=None,
    following_transition=None,
    birth_time_sensitive=True,
):
    return {
        "value": _resolved_value(nominal, stable),
        "nominal": nominal,
        "possible_values": possible,
        "resolved": stable is True,
        "assessment_available": stable is not None,
        "stable_for_declared_uncertainty": stable,
        "stable_within_minutes": stable_within_minutes,
        "previous_transition": previous_transition,
        "following_transition": following_transition,
        "birth_time_sensitive": birth_time_sensitive,
    }


def _qualify_angle(nominal_angle: dict, meta: dict) -> dict:
    sign_meta = meta["sign"]
    return {
        "nominal_lon": nominal_angle["lon"],
        "nominal_deg_in_sign": nominal_angle["deg_in_sign"],
        "longitude_range": meta["longitude"].get("range_within_declared_uncertainty"),
        "sensitivity_deg_per_min": meta["longitude"].get("sensitivity_deg_per_min"),
        "sign": _qualified_discrete(
            nominal_angle["sign"],
            meta.get("possible_signs_within_declared_uncertainty"),
            meta.get("stable_for_declared_uncertainty"),
            stable_within_minutes=sign_meta.get("stable_within_minutes"),
            previous_transition=sign_meta.get("previous_transition"),
            following_transition=sign_meta.get("following_transition"),
        ),
    }


def _qualify_ruler(nominal_ruler: str, meta: dict) -> dict:
    return _qualified_discrete(
        nominal_ruler,
        meta.get("possible_values_within_declared_uncertainty"),
        meta.get("stable_for_declared_uncertainty"),
        stable_within_minutes=meta.get("stable_within_minutes"),
        previous_transition=meta.get("previous_transition"),
        following_transition=meta.get("following_transition"),
    )


def _qualify_houses(nominal_houses: list[dict], metas: list[dict]) -> list[dict]:
    by_num = {m["house"]: m for m in metas}
    out = []
    for house in nominal_houses:
        meta = by_num[house["num"]]
        sign_meta = meta["sign"]
        out.append({
            "num": house["num"],
            "nominal_cusp_lon": house["cusp_lon"],
            "cusp_longitude_range": meta["longitude"].get("range_within_declared_uncertainty"),
            "cusp_sensitivity_deg_per_min": meta["longitude"].get("sensitivity_deg_per_min"),
            "sign": _qualified_discrete(
                house["sign"],
                meta.get("possible_signs_within_declared_uncertainty"),
                meta.get("stable_for_declared_uncertainty"),
                stable_within_minutes=sign_meta.get("stable_within_minutes"),
                previous_transition=sign_meta.get("previous_transition"),
                following_transition=sign_meta.get("following_transition"),
            ),
        })
    return out


def _qualify_planets(nominal_planets: list[dict], metas: list[dict]) -> list[dict]:
    by_body = {m["body"]: m for m in metas}
    out = []
    for planet in nominal_planets:
        p = copy.deepcopy(planet)
        meta = by_body.get(p["name"])
        if meta is not None and "house" in p:
            nominal_house = p.pop("house")
            p["house"] = _qualified_discrete(
                nominal_house,
                meta.get("possible_houses_within_declared_uncertainty"),
                meta.get("stable_for_declared_uncertainty"),
                stable_within_minutes=meta.get("stable_within_minutes"),
                previous_transition=meta.get("previous_transition"),
                following_transition=meta.get("following_transition"),
            )
        out.append(p)
    return out


def _angle_aspect_key(item: dict) -> tuple[frozenset[str], str]:
    return frozenset((item["a"], item["b"])), item["type"]


def _qualify_aspects(nominal_aspects: list[dict], metas: list[dict]) -> list[dict]:
    meta_by_key = {_angle_aspect_key(m): m for m in metas}
    out = []
    for aspect in nominal_aspects:
        if aspect["a"] not in ("ASC", "MC") and aspect["b"] not in ("ASC", "MC"):
            out.append(copy.deepcopy(aspect))
            continue

        meta = meta_by_key.get(_angle_aspect_key(aspect))
        if meta is None:
            # Defensive fallback: never leave a plain high-precision angle orb
            # in the interpreter-facing contract if metadata is unexpectedly
            # unavailable.
            out.append({
                "a": aspect["a"],
                "b": aspect["b"],
                "type": aspect["type"],
                "exact_deg": aspect.get("exact_deg"),
                "birth_time_sensitive": True,
                "nominal_orb": aspect.get("orb"),
                "orb_range": None,
                "nominal_strength": aspect.get("strength"),
                "possible_strengths": None,
                "nominal_score": aspect.get("score"),
                "present_throughout_declared_uncertainty": None,
                "assessment_available": False,
            })
            continue

        out.append({
            "a": aspect["a"],
            "b": aspect["b"],
            "type": aspect["type"],
            "exact_deg": aspect.get("exact_deg"),
            "birth_time_sensitive": True,
            "nominal_orb": meta.get("nominal_orb", aspect.get("orb")),
            "orb_range": meta.get("orb_range"),
            "max_orb": meta.get("max_orb"),
            "orb_sensitivity_deg_per_min": meta.get("orb_sensitivity_deg_per_min"),
            "nominal_strength": aspect.get("strength"),
            "possible_strengths": meta.get("possible_strengths_within_declared_uncertainty"),
            "nominal_score": aspect.get("score"),
            "present_throughout_declared_uncertainty": meta.get("present_throughout_declared_uncertainty"),
            "assessment_available": meta.get("orb_range") is not None,
        })
    return out


def qualify_natal(natal: dict, stability: dict) -> dict:
    """Return the Stage-3 interpreter-facing natal contract.

    The nominal calculation remains available only under explicitly named
    ``nominal_*`` fields for time-dependent values.  Resolved scalar values are
    exposed inside qualification objects as ``value``; unresolved ones use
    ``value: null`` and carry candidates/ranges when a numeric uncertainty was
    declared.
    """
    q = copy.deepcopy(natal)
    q["chart_ruler"] = _qualify_ruler(natal["chart_ruler"], stability["chart_ruler"])
    q["angles"] = {
        "asc": _qualify_angle(natal["angles"]["asc"], stability["asc"]),
        "mc": _qualify_angle(natal["angles"]["mc"], stability["mc"]),
    }
    q["houses"] = _qualify_houses(natal["houses"], stability.get("house_cusps", []))
    q["planets"] = _qualify_planets(natal["planets"], stability.get("house_placements", []))
    q["aspects"] = _qualify_aspects(natal["aspects"], stability.get("angle_aspects", []))
    q["birth_time_contract"] = {
        "version": "qualified_birth_time_v1",
        "nominal_time_dependent_scalars_suppressed_when_unresolved": True,
        "scope": [
            "chart_ruler",
            "angles.asc",
            "angles.mc",
            "houses[].cusp/sign",
            "planets[].house",
            "natal_aspects_involving_ASC_or_MC",
        ],
        "not_yet_sampled": [
            "planetary_longitude/sign uncertainty from birth-time error",
            "new natal angle aspects that are absent at the nominal instant but enter orb elsewhere in the uncertainty window",
            "full stability ranges for progressed/solar-arc/solar-return angle geometry",
        ],
    }
    return q

_ANGLE_NAMES = {"ASC", "MC"}


def time_geometry_uncertain(stability: dict | None) -> bool:
    """True unless the declared birth-time window is exactly zero minutes."""
    if not stability:
        return True
    precision = stability.get("birth_time_precision") or {}
    declared = precision.get("declared_uncertainty_minutes")
    return declared is None or float(declared) > 0.0


def _audit_row(row: dict) -> dict:
    item = copy.deepcopy(row)
    item["birth_time_sensitive_nominal"] = True
    item["interpretation_status"] = "audit_only_nominal"
    return item


def partition_relations_by_angles(
    rows: list[dict] | None,
    *,
    fields: tuple[str, ...],
    active: bool,
) -> tuple[list[dict], list[dict]]:
    """Move relations touching ASC/MC out of normal interpreter-facing arrays.

    This does not invent an uncertainty range for a derived technique. It simply
    prevents a point-estimate angle relation from masquerading as resolved when
    the natal time geometry is not resolved.
    """
    rows = rows or []
    if not active:
        return copy.deepcopy(rows), []
    safe: list[dict] = []
    sensitive: list[dict] = []
    for row in rows:
        if any(row.get(field) in _ANGLE_NAMES for field in fields):
            sensitive.append(_audit_row(row))
        else:
            safe.append(copy.deepcopy(row))
    return safe, sensitive


def protect_transit_block(block: dict | None, stability: dict) -> dict | None:
    if block is None:
        return None
    q = copy.deepcopy(block)
    active = time_geometry_uncertain(stability)
    safe, sensitive = partition_relations_by_angles(
        q.get("aspects_to_natal"), fields=("natal",), active=active)
    q["aspects_to_natal"] = safe
    q["birth_time_sensitive_nominal_aspects"] = sensitive
    return q


def protect_progressions_block(block: dict | None, stability: dict) -> dict | None:
    if block is None:
        return None
    q = copy.deepcopy(block)
    active = time_geometry_uncertain(stability)
    for section in ("secondary", "solar_arc"):
        part = q.get(section)
        if not part:
            continue
        safe, sensitive = partition_relations_by_angles(
            part.get("aspects_to_natal"), fields=("directed", "natal"), active=active)
        part["aspects_to_natal"] = safe
        part["birth_time_sensitive_nominal_aspects"] = sensitive
        part["birth_time_dependency"] = {
            "geometry_resolved": not active,
            "note": (
                "Progressed/directed angle geometry is nominal when natal birth-time uncertainty is non-zero or unknown."
                if active else "Natal birth-time geometry is resolved for the declared input."
            ),
        }
    return q


def protect_forecast_block(block: dict | None, stability: dict) -> dict | None:
    if block is None:
        return None
    q = copy.deepcopy(block)
    active = time_geometry_uncertain(stability)
    safe, sensitive = partition_relations_by_angles(
        q.get("transits"), fields=("natal",), active=active)
    q["transits"] = safe
    q["birth_time_sensitive_nominal_transits"] = sensitive
    for eclipse in q.get("eclipses") or []:
        safe_hits, sensitive_hits = partition_relations_by_angles(
            eclipse.get("natal_hits"), fields=("natal",), active=active)
        eclipse["natal_hits"] = safe_hits
        eclipse["birth_time_sensitive_nominal_hits"] = sensitive_hits
    return q


def protect_solar_return_block(block: dict | None, stability: dict) -> dict | None:
    if block is None:
        return None
    q = copy.deepcopy(block)
    active = time_geometry_uncertain(stability)
    safe, sensitive = partition_relations_by_angles(
        q.get("aspects_to_natal"), fields=("solar_return", "natal"), active=active)
    q["aspects_to_natal"] = safe
    q["birth_time_sensitive_nominal_aspects"] = sensitive
    q["birth_time_dependency"] = {
        "geometry_resolved": not active,
        "note": (
            "Solar-return angles/houses are a nominal derived chart when natal birth-time uncertainty is non-zero or unknown; no SR-angle stability range is computed in this contract."
            if active else "Natal birth-time geometry is resolved for the declared input."
        ),
    }
    return q


def protect_synastry_block(
    block: dict | None,
    primary_stability: dict,
    partner_stability: dict | None,
) -> dict | None:
    if block is None:
        return None
    q = copy.deepcopy(block)
    primary_active = time_geometry_uncertain(primary_stability)
    partner_active = time_geometry_uncertain(partner_stability)

    safe: list[dict] = []
    sensitive: list[dict] = []
    for row in q.get("cross_aspects") or []:
        is_sensitive = (
            (primary_active and row.get("primary") in _ANGLE_NAMES)
            or (partner_active and row.get("partner") in _ANGLE_NAMES)
        )
        (sensitive if is_sensitive else safe).append(_audit_row(row) if is_sensitive else copy.deepcopy(row))
    q["cross_aspects"] = safe
    q["birth_time_sensitive_nominal_cross_aspects"] = sensitive

    geometry_resolved = not primary_active and not partner_active
    if not geometry_resolved:
        if q.get("house_overlay") is not None:
            q["house_overlay_nominal_suppressed"] = True
        q["house_overlay"] = None
        if q.get("composite") is not None:
            q["composite_nominal_suppressed"] = True
        q["composite"] = None
    q["time_geometry_status"] = {
        "resolved": geometry_resolved,
        "primary_resolved": not primary_active,
        "partner_resolved": not partner_active,
        "note": (
            "House overlays and midpoint composite are suppressed unless both birth-time geometries are resolved."
            if not geometry_resolved else "Both birth-time geometries are resolved for the declared inputs."
        ),
    }
    return q
