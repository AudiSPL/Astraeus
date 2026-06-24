"""pytest suite for app.core.report_pdf.generate_pdf_report.

Uses a real chart-packet fixture (tests/fixtures/sample_full_packet.json,
produced by a live /v1/chart-packet call with all 5 optional blocks enabled)
rather than fabricated data, so the field names/shapes are guaranteed to
match what packet.py actually emits.

Run: python -m pytest tests/test_report_pdf.py -v
"""
import copy
import io
import json
from pathlib import Path

import pytest
from pypdf import PdfReader

from app.core.report_pdf import generate_pdf_report, _fmt_deg, _fmt_date

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_full_packet.json"
with open(FIXTURE_PATH, encoding="utf-8-sig") as f:
    FULL_PACKET = json.load(f)


def _natal_only_packet():
    p = {k: copy.deepcopy(FULL_PACKET[k]) for k in
         ["meta", "validation", "birth", "settings", "natal"]}
    p["warnings"] = []
    for key in ["transits", "progressions", "forecast", "solar_return", "synastry"]:
        p[key] = None
    return p


def _page_count(pdf_bytes):
    return len(PdfReader(io.BytesIO(pdf_bytes)).pages)


def _extract_text(pdf_bytes):
    return "".join(pg.extract_text() for pg in PdfReader(io.BytesIO(pdf_bytes)).pages)


def test_full_packet_produces_valid_pdf():
    pdf_bytes = generate_pdf_report(FULL_PACKET)
    assert pdf_bytes.startswith(b"%PDF")
    assert _page_count(pdf_bytes) > 10  # all 5 optional blocks + composite


def test_natal_only_packet_produces_valid_pdf():
    pdf_bytes = generate_pdf_report(_natal_only_packet())
    assert pdf_bytes.startswith(b"%PDF")
    assert _page_count(pdf_bytes) >= 1


def test_natal_only_has_no_optional_section_headers():
    pdf_bytes = generate_pdf_report(_natal_only_packet())
    text = _extract_text(pdf_bytes)
    for absent in ["Transits", "Progressions", "Forecast", "Solar Return", "Synastry", "Composite"]:
        assert absent not in text


def test_each_optional_block_independently():
    """packet.py treats transit/progressions/forecast/solar_return/synastry as
    independent toggles -- the renderer must not assume any pairing between
    them, so each one is exercised alone here."""
    base = _natal_only_packet()
    for key in ["transits", "progressions", "forecast", "solar_return", "synastry"]:
        p = copy.deepcopy(base)
        p[key] = copy.deepcopy(FULL_PACKET[key])
        pdf_bytes = generate_pdf_report(p)
        assert pdf_bytes.startswith(b"%PDF"), f"failed with only '{key}' present"


def test_empty_aspect_lists_render_without_crash():
    p = _natal_only_packet()
    p["natal"] = copy.deepcopy(p["natal"])
    p["natal"]["aspects"] = []
    p["forecast"] = copy.deepcopy(FULL_PACKET["forecast"])
    p["forecast"]["transits"] = []
    p["forecast"]["stations"] = []
    p["forecast"]["eclipses"] = []
    pdf_bytes = generate_pdf_report(p)
    assert pdf_bytes.startswith(b"%PDF")


def test_eclipse_with_no_natal_hits():
    p = _natal_only_packet()
    p["forecast"] = copy.deepcopy(FULL_PACKET["forecast"])
    p["forecast"]["eclipses"] = [{
        "date": "2026-08-12T17:45:59Z", "julian_day_ut": 1.0,
        "eclipse_type": "solar", "kind": "total", "ecliptic_lon": 0.0,
        "orb_used": 5, "natal_hits": [],
    }]
    pdf_bytes = generate_pdf_report(p)
    assert pdf_bytes.startswith(b"%PDF")


def test_validation_failed_shows_warning_banner():
    p = _natal_only_packet()
    p["validation"] = copy.deepcopy(p["validation"])
    p["validation"]["validated_for_interpretation"] = False
    p["validation"]["reasons"] = ["forecast requested but failed to compute"]
    pdf_bytes = generate_pdf_report(p)
    assert "Validation failed" in _extract_text(pdf_bytes)


def test_synastry_without_composite():
    """include_composite=False -> composite key is None inside synastry block."""
    p = _natal_only_packet()
    p["synastry"] = copy.deepcopy(FULL_PACKET["synastry"])
    p["synastry"]["composite"] = None
    pdf_bytes = generate_pdf_report(p)
    assert pdf_bytes.startswith(b"%PDF")
    assert "Composite Chart" not in _extract_text(pdf_bytes)


def test_synastry_without_house_overlay():
    """house_overlay=False -> overlay key is None inside synastry block."""
    p = _natal_only_packet()
    p["synastry"] = copy.deepcopy(FULL_PACKET["synastry"])
    p["synastry"]["house_overlay"] = None
    pdf_bytes = generate_pdf_report(p)
    assert pdf_bytes.startswith(b"%PDF")


def test_fmt_deg():
    assert _fmt_deg(1.4007) == "1\u00b024'"
    assert _fmt_deg(29.999) == "30\u00b000'"  # rollover
    assert _fmt_deg(0.0) == "0\u00b000'"
    assert _fmt_deg(None) == "-"


def test_fmt_date():
    assert _fmt_date("2026-06-27T07:19:23Z") == "2026-06-27 07:19 UTC"
    assert _fmt_date(None) == "-"
    assert _fmt_date("not-a-date") == "not-a-date"


def test_solar_return_relocated_shows_relocation_note():
    p = _natal_only_packet()
    p["solar_return"] = copy.deepcopy(FULL_PACKET["solar_return"])
    p["solar_return"]["location"]["relocated"] = True
    pdf_bytes = generate_pdf_report(p)
    assert "relocated" in _extract_text(pdf_bytes).lower()

