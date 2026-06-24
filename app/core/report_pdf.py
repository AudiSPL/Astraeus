"""Render a validated chart packet (as produced by core.packet.build_packet)
into a readable PDF report.

This module knows only the packet dict shape -- it has no knowledge of how
the packet was built. Sections are rendered conditionally based on which
top-level blocks are present (not None): natal is always rendered; transits/
progressions/forecast/solar_return/synastry only if present.

Public API:
    generate_pdf_report(packet: dict) -> bytes
"""
import io
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
)

PAGE_SIZE = letter
MARGIN = 0.55 * inch
AVAIL_WIDTH = PAGE_SIZE[0] - 2 * MARGIN

# ---------------------------------------------------------------- styles --

_styles = getSampleStyleSheet()
_styles.add(ParagraphStyle(name="ReportTitle", parent=_styles["Title"], fontSize=20, spaceAfter=4))
_styles.add(ParagraphStyle(name="SubTitle", parent=_styles["Normal"], fontSize=10,
                            textColor=colors.HexColor("#555555"), spaceAfter=14))
_styles.add(ParagraphStyle(name="Section", parent=_styles["Heading1"], fontSize=15,
                            spaceBefore=4, spaceAfter=8, textColor=colors.HexColor("#1a1a2e")))
_styles.add(ParagraphStyle(name="SubSection", parent=_styles["Heading2"], fontSize=11.5,
                            spaceBefore=10, spaceAfter=4, textColor=colors.HexColor("#2c2c54")))
_styles.add(ParagraphStyle(name="Body", parent=_styles["Normal"], fontSize=9, leading=13))
_styles.add(ParagraphStyle(name="Caption", parent=_styles["Normal"], fontSize=8,
                            textColor=colors.HexColor("#666666"), leading=11))
_styles.add(ParagraphStyle(name="Note", parent=_styles["Normal"], fontSize=8,
                            textColor=colors.HexColor("#777777"), leading=11, spaceAfter=6))
_styles.add(ParagraphStyle(name="CellWrap", parent=_styles["Normal"], fontSize=8, leading=10))
_styles.add(ParagraphStyle(name="Warning", parent=_styles["Normal"], fontSize=8.5,
                            textColor=colors.HexColor("#8a4b00"), leading=12, spaceAfter=4))

_HEADER_BG = colors.HexColor("#2c2c54")
_HEADER_FG = colors.white
_ROW_ALT_BG = colors.HexColor("#f4f4f8")
_GRID = colors.HexColor("#cccccc")


# --------------------------------------------------------------- helpers --

def _fmt_deg(decimal_deg: float) -> str:
    """30.8167 -> 30 49'"""
    if decimal_deg is None:
        return "-"
    d = int(decimal_deg)
    m = int(round((decimal_deg - d) * 60))
    if m == 60:
        d += 1
        m = 0
    return f"{d}\u00b0{m:02d}'"


def _fmt_date(iso_str: str) -> str:
    if not iso_str:
        return "-"
    try:
        s = iso_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return iso_str


def _fmt_speed(p: dict) -> str:
    speed = p.get("speed")
    if speed is None:
        return "-"
    return f"{speed:.2f}{'R' if p.get('retrograde') else ''}"


def _make_table(data, col_weights, header=True, font_size=8):
    widths = [w * AVAIL_WIDTH for w in col_weights]
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    style = [
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("GRID", (0, 0), (-1, -1), 0.4, _GRID),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        style += [
            ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
            ("TEXTCOLOR", (0, 0), (-1, 0), _HEADER_FG),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ]
        for i in range(1, len(data)):
            if i % 2 == 0:
                style.append(("BACKGROUND", (0, i), (-1, i), _ROW_ALT_BG))
    t.setStyle(TableStyle(style))
    return t


def _planets_table(planets):
    has_house = any("house" in p for p in planets)
    headers = ["Planet", "Sign", "Degree", "Speed"]
    weights = [0.22, 0.28, 0.25, 0.25] if not has_house else [0.20, 0.24, 0.20, 0.18, 0.18]
    if has_house:
        headers.append("House")
    data = [headers]
    for p in planets:
        row = [p["name"], p["sign"], _fmt_deg(p["deg_in_sign"]), _fmt_speed(p)]
        if has_house:
            row.append(str(p.get("house", "-")))
        data.append(row)
    return _make_table(data, weights)


def _houses_table(houses):
    data = [["House", "Cusp Sign", "Cusp Degree"]]
    for h in houses:
        data.append([str(h["num"]), h["sign"], _fmt_deg(h["cusp_lon"] % 30)])
    return _make_table(data, [0.25, 0.40, 0.35])


def _relation_table(rows, a_key, b_key, a_header, b_header):
    """Generic aspect-style table: works for natal aspects (a/b + strength),
    transit/progression/solar_return aspects_to_natal (various key names,
    strength or score or neither), and synastry cross_aspects."""
    if not rows:
        return Paragraph("None detected.", _styles["Note"])
    has_strength = any(r.get("strength") for r in rows)
    has_score = (not has_strength) and any("score" in r for r in rows)
    headers = [a_header, b_header, "Aspect", "Orb"]
    weights = [0.22, 0.22, 0.26, 0.14]
    if has_strength:
        headers.append("Strength")
        weights.append(0.16)
    elif has_score:
        headers.append("Score")
        weights.append(0.16)
    else:
        weights[-1] = 0.30
    data = [headers]
    for r in rows:
        row = [r[a_key], r[b_key], r["type"].capitalize(), f"{r['orb']:.2f}\u00b0"]
        if has_strength:
            row.append((r.get("strength") or "-").capitalize())
        elif has_score:
            row.append(f"{r.get('score', 0):.2f}")
        data.append(row)
    return _make_table(data, weights)


def _angles_para(angles):
    asc, mc = angles["asc"], angles["mc"]
    text = (f"<b>ASC</b> {_fmt_deg(asc['deg_in_sign'])} {asc['sign']} "
            f"&nbsp;&nbsp;&nbsp; <b>MC</b> {_fmt_deg(mc['deg_in_sign'])} {mc['sign']}")
    return Paragraph(text, _styles["Body"])


def _chart_summary_para(chart):
    el = chart["element_balance"]["counts"]
    mo = chart["modality_balance"]["counts"]
    lp = chart["lunar_phase"]
    retro = ", ".join(chart.get("retrogrades", [])) or "None"
    text = (
        f"<b>Elements</b> Fire {el['fire']} &middot; Earth {el['earth']} &middot; "
        f"Air {el['air']} &middot; Water {el['water']} &nbsp;&nbsp; "
        f"<b>Modality</b> Cardinal {mo['cardinal']} &middot; Fixed {mo['fixed']} &middot; "
        f"Mutable {mo['mutable']}<br/>"
        f"<b>Lunar phase</b> {lp['name']} ({lp['sun_moon_angle']:.1f}\u00b0) &nbsp;&nbsp; "
        f"<b>Retrograde</b> {retro}"
    )
    return Paragraph(text, _styles["Body"])


def _ruler_para(chart_ruler):
    return Paragraph(f"<b>Chart ruler:</b> {chart_ruler}", _styles["Body"])


def _full_chart_block(story, chart, ruler=True, planets_label="Planets",
                       houses_label="Houses", aspects_label="Aspects"):
    """Shared renderer for any natal-shaped chart dict (natal / solar_return /
    composite / synastry partner) -- planets/angles/houses/aspects/balances."""
    if ruler and chart.get("chart_ruler"):
        story.append(_ruler_para(chart["chart_ruler"]))
        story.append(Spacer(1, 4))
    story.append(_angles_para(chart["angles"]))
    story.append(Spacer(1, 6))
    story.append(_chart_summary_para(chart))
    story.append(Spacer(1, 10))

    story.append(Paragraph(planets_label, _styles["SubSection"]))
    story.append(_planets_table(chart["planets"]))
    story.append(Spacer(1, 8))

    story.append(Paragraph(houses_label, _styles["SubSection"]))
    story.append(_houses_table(chart["houses"]))
    story.append(Spacer(1, 8))

    story.append(Paragraph(aspects_label, _styles["SubSection"]))
    story.append(_relation_table(chart["aspects"], "a", "b", "Planet", "Planet"))


def _eclipse_hits_text(hits):
    if not hits:
        return "-"
    return ", ".join(f"{h['natal']} {h['type']} ({h['orb']:.2f}\u00b0)" for h in hits)


# ----------------------------------------------------------------- main --

def generate_pdf_report(packet: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=PAGE_SIZE,
        leftMargin=MARGIN, rightMargin=MARGIN, topMargin=MARGIN, bottomMargin=MARGIN,
        title="Astraeus Chart Report",
    )
    story = []

    birth = packet["birth"]
    settings = packet["settings"]
    meta = packet["meta"]
    validation = packet["validation"]
    warnings = packet.get("warnings") or []

    # ---- cover ----
    story.append(Paragraph("Astraeus Chart Report", _styles["ReportTitle"]))
    story.append(Paragraph(
        f"{birth.get('place_label') or '-'} &nbsp;&middot;&nbsp; {birth['local'][:16].replace('T', ' ')} "
        f"({birth['timezone']}) &nbsp;&middot;&nbsp; "
        f"{settings['zodiac'].capitalize()} / {settings['house_system'].capitalize()} houses / "
        f"{settings['node_type'].capitalize()} node",
        _styles["SubTitle"],
    ))

    if not validation.get("validated_for_interpretation", True):
        story.append(Paragraph(
            "<b>Validation failed</b> -- one or more requested blocks did not compute cleanly. "
            "Reasons: " + "; ".join(validation.get("reasons") or ["unspecified"]),
            _styles["Warning"],
        ))
        story.append(Spacer(1, 6))

    if warnings:
        story.append(Paragraph("Notes", _styles["SubSection"]))
        for w in warnings:
            story.append(Paragraph(f"&bull; {w}", _styles["Warning"]))
        story.append(Spacer(1, 8))

    story.append(Paragraph(
        f"<font color='#999999'>calc {meta['calc_version']} / settings {meta['settings_version']} / "
        f"{meta['ephemeris']} / generated {meta['generated_at'][:16].replace('T', ' ')} UTC</font>",
        _styles["Caption"],
    ))
    story.append(Spacer(1, 14))

    # ---- natal ----
    story.append(Paragraph("Natal Chart", _styles["Section"]))
    _full_chart_block(story, packet["natal"])

    # ---- transits ----
    transits = packet.get("transits")
    if transits:
        story.append(PageBreak())
        story.append(Paragraph("Transits", _styles["Section"]))
        story.append(Paragraph(f"Snapshot at {_fmt_date(transits['moment_utc'])}", _styles["Body"]))
        story.append(Spacer(1, 8))
        story.append(Paragraph("Transiting Planets", _styles["SubSection"]))
        story.append(_planets_table(transits["planets"]))
        story.append(Spacer(1, 8))
        story.append(Paragraph("Aspects to Natal", _styles["SubSection"]))
        story.append(_relation_table(transits["aspects_to_natal"], "transit", "natal", "Transit", "Natal"))

    # ---- progressions ----
    prog = packet.get("progressions")
    if prog:
        story.append(PageBreak())
        story.append(Paragraph("Progressions", _styles["Section"]))
        story.append(Paragraph(f"Target date: {prog['target_date']}", _styles["Body"]))
        story.append(Spacer(1, 8))

        sec = prog["secondary"]
        story.append(Paragraph("Secondary Progressions", _styles["SubSection"]))
        story.append(Paragraph(sec["method"], _styles["Note"]))
        story.append(_angles_para(sec["angles"]))
        story.append(Spacer(1, 6))
        story.append(Paragraph("Progressed Planets", _styles["SubSection"]))
        story.append(_planets_table(sec["planets"]))
        story.append(Spacer(1, 8))
        story.append(Paragraph("Aspects to Natal", _styles["SubSection"]))
        story.append(_relation_table(sec["aspects_to_natal"], "directed", "natal", "Progressed", "Natal"))

        sa = prog["solar_arc"]
        story.append(Spacer(1, 10))
        story.append(Paragraph("Solar Arc Directions", _styles["SubSection"]))
        story.append(Paragraph(sa["method"], _styles["Note"]))
        story.append(Paragraph(f"<b>Arc:</b> {sa['arc_degrees']:.2f}\u00b0", _styles["Body"]))
        story.append(Spacer(1, 4))
        story.append(_angles_para(sa["directed_angles"]))
        story.append(Spacer(1, 6))
        story.append(Paragraph("Directed Planets", _styles["SubSection"]))
        story.append(_planets_table(sa["directed_planets"]))
        story.append(Spacer(1, 8))
        story.append(Paragraph("Aspects to Natal", _styles["SubSection"]))
        story.append(_relation_table(sa["aspects_to_natal"], "directed", "natal", "Directed", "Natal"))

    # ---- forecast ----
    forecast = packet.get("forecast")
    if forecast:
        story.append(PageBreak())
        story.append(Paragraph("Forecast", _styles["Section"]))
        period = forecast["period"]
        story.append(Paragraph(
            f"{period['start'][:10]} \u2192 {period['end'][:10]} &nbsp;&middot;&nbsp; "
            f"Movers: {', '.join(forecast['movers_used'])}",
            _styles["Body"],
        ))
        story.append(Spacer(1, 8))

        story.append(Paragraph("Exact Transits", _styles["SubSection"]))
        if forecast["transits"]:
            data = [["Date", "Transit", "Natal", "Aspect"]]
            for t in forecast["transits"]:
                data.append([_fmt_date(t["date"]), t["transit"], t["natal"], t["type"].capitalize()])
            story.append(_make_table(data, [0.32, 0.22, 0.22, 0.24]))
        else:
            story.append(Paragraph("None in this period.", _styles["Note"]))
        story.append(Spacer(1, 8))

        story.append(Paragraph("Stations", _styles["SubSection"]))
        if forecast["stations"]:
            data = [["Date", "Planet", "Direction"]]
            for s in forecast["stations"]:
                data.append([_fmt_date(s["date"]), s["planet"], s["direction"].capitalize()])
            story.append(_make_table(data, [0.40, 0.30, 0.30]))
        else:
            story.append(Paragraph("None in this period.", _styles["Note"]))
        story.append(Spacer(1, 8))

        story.append(Paragraph("Eclipses", _styles["SubSection"]))
        if forecast["eclipses"]:
            data = [["Date", "Type", "Kind", "Natal Hits"]]
            for e in forecast["eclipses"]:
                hits_para = Paragraph(_eclipse_hits_text(e["natal_hits"]), _styles["CellWrap"])
                data.append([_fmt_date(e["date"]), e["eclipse_type"].capitalize(),
                             e["kind"].capitalize(), hits_para])
            story.append(_make_table(data, [0.26, 0.14, 0.16, 0.44]))
        else:
            story.append(Paragraph("None in this period.", _styles["Note"]))

    # ---- solar return ----
    sr = packet.get("solar_return")
    if sr:
        story.append(PageBreak())
        loc = sr["location"]
        story.append(Paragraph(f"Solar Return {sr['year']}", _styles["Section"]))
        story.append(Paragraph(
            f"{_fmt_date(sr['moment_utc'])}"
            + (f" &middot; relocated to {loc['latitude']:.2f}, {loc['longitude']:.2f} ({loc['timezone']})"
               if loc.get("relocated") else f" &middot; natal location ({loc['timezone']})"),
            _styles["Body"],
        ))
        story.append(Spacer(1, 8))
        _full_chart_block(story, sr)
        story.append(Spacer(1, 8))
        story.append(Paragraph("Aspects to Natal", _styles["SubSection"]))
        story.append(_relation_table(sr["aspects_to_natal"], "solar_return", "natal", "Solar Return", "Natal"))

    # ---- synastry ----
    syn = packet.get("synastry")
    if syn:
        story.append(PageBreak())
        story.append(Paragraph("Synastry", _styles["Section"]))
        partner_birth = syn["partner"].get("birth", {})
        story.append(Paragraph(
            f"Partner: {partner_birth.get('place_label') or '-'} &nbsp;&middot;&nbsp; "
            f"{(partner_birth.get('local') or '')[:16].replace('T', ' ')} "
            f"({partner_birth.get('timezone', '-')})",
            _styles["Body"],
        ))
        story.append(Spacer(1, 10))

        story.append(Paragraph("Partner Chart", _styles["SubSection"]))
        _full_chart_block(story, syn["partner"], planets_label="Partner Planets",
                           houses_label="Partner Houses", aspects_label="Partner Aspects")

        story.append(Spacer(1, 10))
        story.append(Paragraph("Cross Aspects", _styles["SubSection"]))
        story.append(_relation_table(syn["cross_aspects"], "primary", "partner", "Primary", "Partner"))

        overlay = syn.get("house_overlay")
        if overlay:
            story.append(Spacer(1, 10))
            story.append(Paragraph("House Overlay", _styles["SubSection"]))
            p_in_p = overlay["primary_planets_in_partner_houses"]
            q_in_p = overlay["partner_planets_in_primary_houses"]
            data = [["Planet", "Primary in Partner's House", "Partner in Primary's House"]]
            for planet in p_in_p:
                data.append([planet, str(p_in_p.get(planet, "-")), str(q_in_p.get(planet, "-"))])
            story.append(_make_table(data, [0.30, 0.35, 0.35]))

        composite = syn.get("composite")
        if composite:
            story.append(PageBreak())
            story.append(Paragraph("Composite Chart", _styles["Section"]))
            story.append(Paragraph(composite["method"], _styles["Note"]))
            story.append(Spacer(1, 4))
            story.append(_angles_para(composite["angles"]))
            story.append(Spacer(1, 8))
            story.append(Paragraph("Composite Planets", _styles["SubSection"]))
            story.append(_planets_table(composite["planets"]))
            story.append(Spacer(1, 8))
            story.append(Paragraph("Composite Houses", _styles["SubSection"]))
            story.append(_houses_table(composite["houses"]))
            story.append(Spacer(1, 8))
            story.append(Paragraph("Composite Aspects", _styles["SubSection"]))
            story.append(_relation_table(composite["aspects"], "a", "b", "Planet", "Planet"))

    doc.build(story)
    return buf.getvalue()
