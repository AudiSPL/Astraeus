"""Astraeus calculation API.
POST /v1/chart-packet  -> validated chart packet (natal always; transit snapshot
                          if `transit` provided)
POST /v1/report/pdf    -> chart packet rendered as a downloadable PDF report
GET  /v1/cities        -> city search for the location-picker autocomplete
GET  /v1/health
GET  /                 -> local control-panel UI (form -> chart-packet -> copy JSON)
"""
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, Response

from .schemas import ChartRequest
from .core import config
from .core.packet import build_packet, InputError
from .core.report_pdf import generate_pdf_report
from .core.city_search import search as search_cities

app = FastAPI(title="Astraeus Calculation API", version="1.0.0")

STATIC_DIR = Path(__file__).parent / "static"


def _check_auth(authorization: str | None):
    if not config.REQUIRE_AUTH:
        return
    if authorization != f"Bearer {config.API_KEY}":
        raise HTTPException(status_code=401, detail="invalid or missing API key")


@app.get("/")
def ui():
    return FileResponse(
        STATIC_DIR / "ui.html",
        headers={"Cache-Control": "no-cache, must-revalidate"},
    )


@app.get("/v1/health")
def health():
    return {"ok": True, "ephemeris": config.EPHE_MODE}


@app.get("/v1/cities")
def cities(q: str, limit: int = 20):
    return {"results": search_cities(q, limit=min(limit, 50))}


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
