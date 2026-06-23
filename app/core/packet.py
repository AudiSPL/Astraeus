"""Orchestrator: request dict -> validated chart packet dict.

Pipeline: resolve location -> local->UTC->JD -> natal bodies/houses/aspects ->
derived analysis -> (optional transit snapshot) -> (optional progressions) ->
(optional forecast scan) -> (optional solar return) -> (optional synastry) ->
validation -> meta.
"""
import hashlib
import json
from datetime import datetime, timezone, date

from . import config
from . import (geo, timeutil, ephemeris, aspects, analysis, transits, validate,
               progressions, forecast, solar_return, synastry)
from .settings import CALC_VERSION, SETTINGS_VERSION


class InputError(ValueError):
    pass


def _resolve_location(birth: dict):
    if birth.get("latitude") is not None and birth.get("longitude") is not None and birth.get("timezone"):
        return float(birth["latitude"]), float(birth["longitude"]), birth["timezone"], birth.get("place_label")
    hit = geo.resolve(birth.get("city") or birth.get("place_label"))
    if hit:
        lat, lon, tz = hit
        return lat, lon, tz, (birth.get("place_label") or birth.get("city"))
    raise InputError(
        "Could not resolve location. Provide latitude+longitude+timezone, "
        "or a city present in the geo table (e.g. 'Belgrade, Serbia')."
    )


def _input_hash(req: dict) -> str:
    blob = json.dumps(req, sort_keys=True, default=str).encode()
    return "sha256:" + hashlib.sha256(blob).hexdigest()[:32]


def _full_chart(jd, lat, lon, house_system, zodiac, node_type, include_points):
    """Natal-shaped chart (bodies/houses/angles/own aspects/balances/phase) at
    an arbitrary moment+location. Used for both the primary natal block and
    the synastry partner -- same computation, same shape, just called twice."""
    bodies = ephemeris.compute_bodies(jd, zodiac, node_type, include_points)
    houses, angles, cusp_lons = ephemeris.compute_houses(jd, lat, lon, house_system, zodiac)
    analysis.assign_houses(bodies, cusp_lons)

    asc_point = {"name": "ASC", "lon": angles["asc"]["lon"], "speed": None}
    mc_point = {"name": "MC", "lon": angles["mc"]["lon"], "speed": None}
    aspect_targets = {**bodies, "ASC": asc_point, "MC": mc_point}
    own_aspects = aspects.detect(aspect_targets, include_minors=False)

    el, mo = analysis.balances(bodies)
    phase_name, phase_angle = analysis.lunar_phase(bodies["Sun"]["lon"], bodies["Moon"]["lon"])

    complete = (
        all(p in bodies for p in ["Sun", "Moon", "Mercury", "Venus", "Mars",
                                   "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"])
        and len(houses) == 12 and "asc" in angles and "mc" in angles
    )

    chart = {
        "chart_ruler": analysis.chart_ruler(angles["asc"]["lon"]),
        "planets": list(bodies.values()),
        "angles": angles,
        "houses": houses,
        "aspects": own_aspects,
        "element_balance": el,
        "modality_balance": mo,
        "lunar_phase": {"name": phase_name, "sun_moon_angle": phase_angle},
        "retrogrades": analysis.retrogrades(bodies),
    }
    return bodies, houses, angles, cusp_lons, chart, complete


def build_packet(req: dict) -> dict:
    birth = req["birth"]
    settings = req.get("settings") or {}
    zodiac = settings.get("zodiac", "tropical")
    house_system = settings.get("house_system", "placidus")
    node_type = settings.get("node_type", "true")
    include_points = settings.get("include_points", ["chiron", "lilith"])
    time_accuracy = birth.get("time_accuracy", "exact")

    lat, lon, tz, label = _resolve_location(birth)
    local_iso, utc_iso, offset, dst, jd = timeutil.to_utc_and_jd(
        birth["date"], birth["time"], tz)

    # --- natal ---
    bodies, houses, angles, cusp_lons, natal, natal_complete = _full_chart(
        jd, lat, lon, house_system, zodiac, node_type, include_points)

    # natal points reused by transit/progressions/forecast/solar_return/synastry
    natal_points = {**{k: {"name": k, "lon": v["lon"]} for k, v in bodies.items()},
                    "ASC": {"name": "ASC", "lon": angles["asc"]["lon"]},
                    "MC": {"name": "MC", "lon": angles["mc"]["lon"]}}

    # --- optional transit snapshot ---
    transit_block = None
    transit_requested = bool(req.get("transit"))
    transit_complete = False
    if transit_requested:
        t = req["transit"]
        _, t_utc, _, _, t_jd = timeutil.to_utc_and_jd(
            t["date"], t.get("time", "12:00:00"), t.get("timezone", "UTC"))
        tb = transits.transit_bodies(t_jd, zodiac)
        t2n = transits.transit_to_natal(tb, natal_points)
        from .transits import ORB_POLICY
        transit_complete = len(tb) > 0
        transit_block = {
            "moment_utc": t_utc,
            "orb_policy": ORB_POLICY,
            "planets": list(tb.values()),
            "aspects_to_natal": t2n,
        }

    # --- optional progressions (secondary + solar arc) ---
    prog_block = None
    prog_requested = bool(req.get("progressions"))
    prog_complete = False
    if prog_requested:
        p = req["progressions"]
        target_date = p["date"]  # the calendar date to progress TO, e.g. "2026-07-15"

        sec_jd, sec_bodies, sec_angles, sec_houses = progressions.secondary_positions(
            jd, target_date, birth["date"], zodiac, lat, lon, house_system)
        sec_directed = {**{k: {"name": k, "lon": v["lon"]} for k, v in sec_bodies.items()},
                        "ASC": {"name": "ASC", "lon": sec_angles["asc"]["lon"]},
                        "MC": {"name": "MC", "lon": sec_angles["mc"]["lon"]}}
        sec_aspects = progressions.directed_to_natal(sec_directed, natal_points, "secondary")

        # solar arc: the arc the progressed Sun has moved since birth
        arc = (sec_bodies["Sun"]["lon"] - bodies["Sun"]["lon"]) % 360
        sa_bodies, sa_angles = progressions.solar_arc_positions(bodies, angles, arc)
        sa_directed = {**{k: {"name": k, "lon": v["lon"]} for k, v in sa_bodies.items()},
                      "ASC": {"name": "ASC", "lon": sa_angles["asc"]["lon"]},
                      "MC": {"name": "MC", "lon": sa_angles["mc"]["lon"]}}
        sa_aspects = progressions.directed_to_natal(sa_directed, natal_points, "solar_arc")

        prog_complete = bool(sec_bodies) and bool(sa_bodies)
        prog_block = {
            "target_date": target_date,
            "secondary": {
                "method": "day_for_a_year; angles via progressed JD through natal coordinates "
                          "(conventional fast method, not real progressed GMT)",
                "progressed_julian_day_ut": round(sec_jd, 7),
                "planets": list(sec_bodies.values()),
                "angles": sec_angles,
                "houses": sec_houses,
                "aspects_to_natal": sec_aspects,
            },
            "solar_arc": {
                "method": "every natal point shifted by the secondary-progressed Sun's arc; "
                          "directed positions only, no houses of their own",
                "arc_degrees": round(arc, 6),
                "directed_planets": list(sa_bodies.values()),
                "directed_angles": sa_angles,
                "aspects_to_natal": sa_aspects,
            },
        }

    # --- optional forecast scan (Phase 3: exact transit-to-natal hits,
    # outer-planet stations, and eclipses, over a date range) ---
    forecast_block = None
    forecast_requested = bool((req.get("forecast") or {}).get("enabled"))
    forecast_complete = False
    if forecast_requested:
        f = req["forecast"]
        start = date.fromisoformat(f.get("start_date") or datetime.now(timezone.utc).date().isoformat())
        end = (date.fromisoformat(f["end_date"]) if f.get("end_date")
               else timeutil.add_months(start, f.get("months", 12)))
        f_jd0 = timeutil.date_to_jd_ut0(start)
        f_jd1 = timeutil.date_to_jd_ut0(end)

        forecast_block = forecast.scan(natal_points, f_jd0, f_jd1, zodiac)
        forecast_complete = bool(forecast_block)

    # --- optional solar return (Phase 4: full chart for the year's Sun-return
    # moment, natal location by default, relocatable on request) ---
    sr_block = None
    sr_requested = bool(req.get("solar_return"))
    sr_complete = False
    sr_relocated = False
    sr_lat = sr_lon = None
    if sr_requested:
        sr = req["solar_return"]
        sr_lat, sr_lon, sr_tz = lat, lon, tz
        if sr.get("latitude") is not None and sr.get("longitude") is not None:
            sr_lat, sr_lon = float(sr["latitude"]), float(sr["longitude"])
            sr_tz = sr.get("timezone") or tz
            sr_relocated = True
        elif sr.get("city"):
            hit = geo.resolve(sr["city"])
            if not hit:
                raise InputError(
                    f"solar_return.city '{sr['city']}' not found in the geo table; "
                    "provide solar_return.latitude + solar_return.longitude instead.")
            sr_lat, sr_lon, sr_tz = hit
            sr_relocated = True
        sr_house_system = sr.get("house_system") or house_system

        sr_flag = ephemeris.base_flag(zodiac)
        sr_jd = solar_return.find_return_jd(bodies["Sun"]["lon"], sr["year"], sr_flag)

        sr_bodies, sr_houses, sr_angles, sr_cusp_lons, sr_chart, _ = _full_chart(
            sr_jd, sr_lat, sr_lon, sr_house_system, zodiac, node_type, include_points)

        sr_points = {**{k: {"name": k, "lon": v["lon"]} for k, v in sr_bodies.items()},
                    "ASC": {"name": "ASC", "lon": sr_angles["asc"]["lon"]},
                    "MC": {"name": "MC", "lon": sr_angles["mc"]["lon"]}}
        sr_to_natal = solar_return.aspects_to_natal(sr_points, natal_points)

        sr_complete = True
        sr_block = {
            "year": sr["year"],
            "moment_utc": timeutil.jd_to_utc_iso(sr_jd),
            "julian_day_ut": round(sr_jd, 7),
            "location": {"latitude": sr_lat, "longitude": sr_lon, "timezone": sr_tz,
                        "relocated": sr_relocated},
            "house_system": sr_house_system,
            **sr_chart,
            "aspects_to_natal": sr_to_natal,
            "orb_used": solar_return.SR_ORB,
        }

    # --- optional synastry (Phase 4: second chart compared against primary,
    # plus optional composite/midpoint chart) ---
    synastry_block = None
    synastry_requested = bool((req.get("synastry") or {}).get("enabled"))
    synastry_complete = False
    p_time_accuracy = None
    if synastry_requested:
        syn = req["synastry"]
        partner = syn["partner"]
        p_time_accuracy = partner.get("time_accuracy", "exact")

        p_lat, p_lon, p_tz, p_label = _resolve_location(partner)
        p_local_iso, p_utc_iso, p_offset, p_dst, p_jd = timeutil.to_utc_and_jd(
            partner["date"], partner["time"], p_tz)

        p_bodies, p_houses, p_angles, p_cusp_lons, partner_natal, _ = _full_chart(
            p_jd, p_lat, p_lon, house_system, zodiac, node_type, include_points)
        partner_natal["birth"] = {
            "local": p_local_iso, "utc": p_utc_iso, "utc_offset": p_offset, "dst_active": p_dst,
            "julian_day_ut": round(p_jd, 7),
            "latitude": p_lat, "longitude": p_lon, "timezone": p_tz, "place_label": p_label,
        }

        partner_points = {**{k: {"name": k, "lon": v["lon"]} for k, v in p_bodies.items()},
                          "ASC": {"name": "ASC", "lon": p_angles["asc"]["lon"]},
                          "MC": {"name": "MC", "lon": p_angles["mc"]["lon"]}}

        cross = synastry.cross_aspects(natal_points, partner_points)

        overlay = None
        if syn.get("house_overlay", True):
            overlay = {
                "primary_planets_in_partner_houses": synastry.house_overlay(natal_points, p_cusp_lons),
                "partner_planets_in_primary_houses": synastry.house_overlay(partner_points, cusp_lons),
            }

        composite_block = None
        if syn.get("include_composite", True):
            comp_bodies = synastry.composite_bodies(bodies, p_bodies)
            comp_angles = synastry.composite_angles(angles, p_angles)
            comp_houses = synastry.composite_houses(cusp_lons, p_cusp_lons)

            comp_asc_point = {"name": "ASC", "lon": comp_angles["asc"]["lon"], "speed": None}
            comp_mc_point = {"name": "MC", "lon": comp_angles["mc"]["lon"], "speed": None}
            comp_targets = {**comp_bodies, "ASC": comp_asc_point, "MC": comp_mc_point}
            comp_aspects = aspects.detect(comp_targets, include_minors=False)

            composite_block = {
                "method": "midpoint (near arc); planets, angles, and house cusps each "
                          "independently midpointed -- not Davison, no synthetic time/place",
                "planets": list(comp_bodies.values()),
                "angles": comp_angles,
                "houses": comp_houses,
                "aspects": comp_aspects,
            }

        synastry_complete = True
        synastry_block = {
            "partner": partner_natal,
            "cross_aspects": cross,
            "house_overlay": overlay,
            "composite": composite_block,
        }

    vflags = validate.build(natal_complete, time_accuracy,
                            transit_requested, transit_complete,
                            forecast_requested, forecast_complete,
                            sr_requested, sr_complete,
                            synastry_requested, synastry_complete)
    if prog_requested:
        vflags["progressions_validated"] = prog_complete
        if not prog_complete:
            vflags["reasons"].append("progressions requested but failed to compute")
            vflags["validated_for_interpretation"] = False

    warnings = []
    if config.EPHE_MODE == "moshier":
        warnings.append("Moshier model in use: reduced precision and Chiron unavailable. "
                        "Run scripts/fetch_ephe.py for full Swiss-Ephemeris accuracy.")
    if time_accuracy == "approx":
        warnings.append("Birth time marked approximate: ASC, MC, houses and Moon degree may shift.")
    if prog_requested:
        warnings.append("Progressed angles (MC/ASC) use the conventional fast method "
                        "(progressed JD through natal coordinates), not 'real' progressed GMT. "
                        "Most progressed-planet aspects are unaffected; only progressed-angle "
                        "house/aspect precision differs slightly between conventions.")
    if forecast_requested:
        warnings.append("Forecast scans outer-planet movers only (Jupiter-Pluto); "
                        "Moon, Sun, Mercury, Venus, Mars are excluded by design "
                        "(see transits.FORECAST_MOVERS).")
    if sr_requested and sr_relocated:
        warnings.append(f"Solar return cast for relocated coordinates "
                        f"({sr_lat:.4f}, {sr_lon:.4f}), not the natal location.")
    if synastry_requested and p_time_accuracy in ("approx", "unknown"):
        warnings.append(f"Partner birth time marked {p_time_accuracy}: partner's ASC, MC, "
                        "houses and Moon degree may shift, and so may the house overlay.")

    return {
        "meta": {
            "calc_version": CALC_VERSION,
            "settings_version": SETTINGS_VERSION,
            "ephemeris": config.EPHE_MODE,
            "tzdata_version": timeutil.tzdata_version(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "input_hash": _input_hash(req),
        },
        "validation": vflags,
        "birth": {
            "local": local_iso, "utc": utc_iso, "utc_offset": offset, "dst_active": dst,
            "julian_day_ut": round(jd, 7),
            "latitude": lat, "longitude": lon, "timezone": tz, "place_label": label,
        },
        "settings": {"zodiac": zodiac, "house_system": house_system, "node_type": node_type},
        "natal": natal,
        "transits": transit_block,
        "progressions": prog_block,
        "forecast": forecast_block,
        "solar_return": sr_block,
        "synastry": synastry_block,
        "warnings": warnings,
    }
