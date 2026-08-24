from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "app" / "static" / "forecast_lab.html"
UI = ROOT / "app" / "static" / "ui.html"
PROMPTS = ROOT / "app" / "static" / "prompts.html"
GUIDE = ROOT / "app" / "static" / "guide.html"
DOC = ROOT / "docs" / "FORECAST_AUDIT.md"
PROMPT_DOC = ROOT / "docs" / "PROMPT_LIBRARY.md"


def test_forecast_lab_route_serves_without_cache():
    r = TestClient(app).get("/forecast-lab")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert r.headers["cache-control"] == "no-cache, must-revalidate"
    assert "Astraeus Forecast Lab" in r.text


def test_all_product_surfaces_link_forecast_lab():
    for path in (UI, PROMPTS, GUIDE):
        text = path.read_text(encoding="utf-8")
        assert 'href="/forecast-lab"' in text or 'href="/forecast-lab?' in text


def test_calculator_persists_request_for_forecast_lab_handoff():
    text = UI.read_text(encoding="utf-8")
    assert "astraeus-last-request" in text
    assert "requestPayload = buildRequest()" in text
    assert "localStorage.setItem('astraeus-last-request'" in text


def test_v11_uses_same_season_control_not_183_day_displacement():
    text = LAB.read_text(encoding="utf-8")
    assert "same-season-plus-1y-v1" in text
    assert "addYearsSameSeason(start,1)" in text
    assert "controlEnd=addDays(controlStart,days-1)" in text
    assert "controlStart=addDays(targetEnd,183)" not in text


def test_ranker_still_has_fixed_per_technique_quotas_and_groups_multipass():
    text = LAB.read_text(encoding="utf-8")
    assert "context-blind-forecast-v1.1" in text
    assert "transit_series:5" in text
    assert "eclipses:2" in text
    assert "const groups=new Map()" in text
    assert "`${x.transit}|${x.natal}|${x.type}`" in text
    assert "Do not collapse transit-series and eclipse rank scores into one universal score" in text


def test_scored_llm_package_withholds_calendar_dates_and_uses_day_offsets():
    text = LAB.read_text(encoding="utf-8")
    for token in (
        "calendar_dates_withheld_from_llm:true",
        "Calendar dates are deliberately withheld from you",
        "exact_day_offsets",
        "day_offset",
        "start_day",
        "end_day",
        "forecast_claims_v2",
    ):
        assert token in text
    assert "Do NOT infer, back-solve or output calendar dates" in text


def test_full_packet_is_withheld_and_selection_is_hashed_before_context():
    text = LAB.read_text(encoding="utf-8")
    assert "full_forecast_packet_withheld:true" in text
    assert "full forecast packet is intentionally WITHHELD" in text
    assert "crypto.subtle.digest('SHA-256'" in text
    assert "selection_hash" in text
    assert "MINIMAL DOMAIN CONTEXT" in text


def test_scored_phase_gets_only_minimal_domain_not_detailed_life_context():
    text = LAB.read_text(encoding="utf-8")
    assert "function minimalDomainContext(){return {domain:$('topic').value}}" in text
    assert "You do NOT receive detailed life context in this scored phase" in text
    assert "DETAILED USER CONTEXT (NON-SCORED; ADDED AFTER CLAIM FREEZE)" in text
    assert "Sačuvaj blind claims pre detaljnog konteksta" in text
    assert "currentAuditForFreeze" in text


def test_post_claim_context_cannot_modify_scored_claims():
    text = LAB.read_text(encoding="utf-8")
    for token in (
        "POST-CLAIM CONTEXT INTERPRETATION",
        "MUST NOT add, delete, edit, relabel, widen, narrow or replace any forecast claim",
        "Do not output a new ASTRAEUS_AUDIT_JSON block",
        "Do not generate additional scored predictions",
    ):
        assert token in text


def test_claim_contract_is_falsifiable_and_rejects_legal_related_money_outcomes():
    text = LAB.read_text(encoding="utf-8")
    for token in (
        "observable_event",
        "verification_rule",
        "evidence_ids",
        "Max 3 scored claims per window",
        "Vague claims",
        "Do not assign numeric probability/confidence",
        "settlements",
        "damages",
        "severance",
        "back pay",
        "legal/settlement/dispute-related outcome nije dozvoljen scored claim",
    ):
        assert token in text


def test_claim_validator_rejects_calendar_date_leakage_and_out_of_window_offsets():
    text = LAB.read_text(encoding="utf-8")
    assert "DATE_RX" in text
    assert "Number.isInteger(c.start_day)" in text
    assert "c.end_day>=frozen.horizon_days" in text
    assert "scored claim ne sme sadržati kalendarski datum" in text


def test_review_scoring_and_target_control_reveal_still_ship_together():
    text = LAB.read_text(encoding="utf-8")
    for token in (
        "Review previous forecast",
        "Occurred",
        "Did not occur",
        "Not assessable",
        "Reveal target/control + score",
        "Target = Window",
        "Control = Window",
        "astraeus-audits-v1",
    ):
        assert token in text


def test_saved_audit_review_maps_day_offsets_back_to_real_dates_locally():
    text = LAB.read_text(encoding="utf-8")
    assert "function claimRange(w,c)" in text
    assert "addDays(w.period.start,c.start_day)" in text
    assert "addDays(w.period.start,c.end_day)" in text


def test_legacy_audit_exports_can_still_be_imported():
    text = LAB.read_text(encoding="utf-8")
    assert "astraeus_audits_export_v2" in text
    assert "'astraeus_audits_export_v1','astraeus_audits_export_v2'" in text


def test_prompt_library_forecast_links_remain_audit_gated():
    text = PROMPTS.read_text(encoding="utf-8")
    for h in ("30", "90", "365"):
        assert f'href="/forecast-lab?horizon={h}"' in text
    assert 'data-template="forecast_30"' not in text
    assert 'data-template="forecast_90"' not in text
    assert 'data-template="forecast_365"' not in text


def test_v11_methodology_is_documented_in_both_docs():
    text = DOC.read_text(encoding="utf-8")
    prompt_text = PROMPT_DOC.read_text(encoding="utf-8")
    for token in (
        "same-season",
        "Day 0",
        "detailed context",
        "legal-dispute-related payments",
        "target-vs-control",
    ):
        assert token in text
    assert "blind scored claims" in prompt_text.lower()
    assert "same-season" in prompt_text
    assert "day offsets" in prompt_text.lower()
