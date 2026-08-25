"""Astraeus calculation API.
POST /v1/chart-packet  -> validated chart packet (natal always; transit snapshot
                          if `transit` provided)
POST /v1/report/pdf    -> chart packet rendered as a downloadable PDF report
GET  /v1/cities        -> city search for the location-picker autocomplete
GET  /v1/timezones     -> searchable IANA timezone picker data
GET  /v1/health
GET  /                 -> local control-panel UI (form -> chart-packet -> copy JSON)
"""
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from pydantic import ValidationError
from fastapi.responses import FileResponse, Response

from .schemas import ChartRequest
from .core import config
from .core.packet import build_packet, InputError
from .core.birth_time_compare import build_birth_time_comparison
from .core.report_pdf import generate_pdf_report
from .core.city_search import search as search_cities
from .core.timezones import (
    is_valid as is_valid_timezone,
    list_timezones,
    resolve as resolve_timezone,
    search as search_timezones,
    tzdata_versions,
)

app = FastAPI(title="Astraeus Calculation API", version="1.0.0")

STATIC_DIR = Path(__file__).parent / "static"


def _check_auth(authorization: str | None):
    if not config.REQUIRE_AUTH:
        return
    if authorization != f"Bearer {config.API_KEY}":
        raise HTTPException(status_code=401, detail="invalid or missing API key")


def _timezone_picker_moment(at: str | None) -> datetime:
    if at is None:
        # A full datetime default, never a date-only midnight guess.
        return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
    if "T" not in at:
        raise HTTPException(
            status_code=422,
            detail="`at` must include local date and time, e.g. 2026-08-22T12:00",
        )
    try:
        moment = datetime.fromisoformat(at)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"invalid `at` value: {at!r}")
    if moment.tzinfo is not None:
        raise HTTPException(
            status_code=422,
            detail="`at` must be a naive local datetime; the selected zone supplies the offset",
        )
    return moment


@app.get("/")
def ui():
    return FileResponse(
        STATIC_DIR / "ui.html",
        headers={"Cache-Control": "no-cache, must-revalidate"},
    )


@app.get("/guide")
def guide():
    return FileResponse(
        STATIC_DIR / "guide.html",
        headers={"Cache-Control": "no-cache, must-revalidate"},
    )


@app.get("/prompts")
def prompts():
    return FileResponse(
        STATIC_DIR / "prompts.html",
        headers={"Cache-Control": "no-cache, must-revalidate"},
    )


@app.get("/forecast-lab")
def forecast_lab():
    return FileResponse(
        STATIC_DIR / "forecast_lab.html",
        headers={"Cache-Control": "no-cache, must-revalidate"},
    )


@app.get("/birth-time-comparison")
def birth_time_comparison_page():
    return FileResponse(
        STATIC_DIR / "birth_time_compare.html",
        headers={"Cache-Control": "no-cache, must-revalidate"},
    )


@app.post("/v1/birth-time-comparison")
def birth_time_comparison(payload: dict, authorization: str | None = Header(default=None)):
    _check_auth(authorization)
    raw_base = payload.get("base_request") if isinstance(payload, dict) else None
    if not isinstance(raw_base, dict):
        raise HTTPException(status_code=422, detail="base_request must be an object")

    # Reuse the normal Calculator schema for the natal birth/settings input,
    # while intentionally withholding optional modules from candidate states.
    try:
        validated_base = ChartRequest.model_validate({
            "birth": raw_base.get("birth"),
            "settings": raw_base.get("settings") or {},
        }).model_dump()
    except ValidationError as e:
        raise HTTPException(
            status_code=422,
            detail={"message": "invalid base_request birth/settings", "errors": e.errors()},
        )

    clean_payload = dict(payload)
    clean_payload["base_request"] = validated_base
    try:
        return build_birth_time_comparison(clean_payload)
    except InputError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"birth-time comparison error: {e}")


@app.get("/v1/health")
def health():
    return {"ok": True, "ephemeris": config.EPHE_MODE}


@app.get("/v1/cities")
def cities(q: str, limit: int = 20):
    return {"results": search_cities(q, limit=min(max(limit, 1), 50))}


@app.get("/v1/timezones")
def timezones(
    at: str | None = None,
    q: str | None = None,
    limit: int = 500,
    recommended: str | None = None,
):
    """IANA zones resolved for the local wall-clock moment typed in the UI."""
    moment = _timezone_picker_moment(at)
    limit = min(max(limit, 1), 1000)

    results = (
        search_timezones(q, moment, limit=limit)
        if q is not None and q.strip()
        else list_timezones(moment)[:limit]
    )

    picks = []
    seen = set()
    for zone in (recommended or "").split(","):
        zone = zone.strip()
        if zone and zone not in seen and is_valid_timezone(zone):
            picks.append(resolve_timezone(zone, moment))
            seen.add(zone)

    versions = tzdata_versions()
    return {
        "tzdata_package_version": versions["package_version"],
        "iana_version": versions["iana_version"],
        "at": moment.isoformat(),
        "count": len(results),
        "recommended": picks,
        "timezones": results,
    }


@app.post("/v1/chart-packet")
def chart_packet(req: ChartRequest, authorization: str | None = Header(default=None)):
    _check_auth(authorization)
    try:
        return build_packet(req.model_dump())
    except InputError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:  # noqa: BLE001 - surface a clean error to the agent
        raise HTTPException(status_code=500, detail=f"calculation error: {e}")


@app.post("/v1/report/pdf")
def report_pdf(req: ChartRequest, authorization: str | None = Header(default=None)):
    _check_auth(authorization)
    try:
        packet = build_packet(req.model_dump())
    except InputError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"calculation error: {e}")
    pdf_bytes = generate_pdf_report(packet)
    filename = f"astraeus-{packet['birth']['local'][:10]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
