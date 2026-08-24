from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "app" / "static" / "forecast_lab.html"
UI = ROOT / "app" / "static" / "ui.html"
PROMPTS = ROOT / "app" / "static" / "prompts.html"
GUIDE = ROOT / "app" / "static" / "guide.html"
DOC = ROOT / "docs" / "FORECAST_AUDIT.md"


def test_forecast_lab_route_serves_without_cache():
    r = TestClient(app).get("/forecast-lab")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert r.headers["cache-control"] == "no-cache, must-revalidate"
    assert "Astraeus Forecast Lab" in r.text


def test_all_product_surfaces_link_forecast_lab():
    for path in (UI, PROMPTS, GUIDE):
        assert 'href="/forecast-lab"' in path.read_text(encoding="utf-8") or 'href="/forecast-lab?' in path.read_text(encoding="utf-8")


def test_calculator_persists_request_only_for_forecast_lab_handoff():
    text = UI.read_text(encoding="utf-8")
    assert "astraeus-last-request" in text
    assert "requestPayload = buildRequest()" in text
    assert "localStorage.setItem('astraeus-last-request'" in text


def test_context_is_structurally_after_freeze_and_full_packet_is_withheld():
    text = LAB.read_text(encoding="utf-8")
    assert "Prvo zamrzni evidence" in text
    assert "full_forecast_packet_withheld:true" in text
    assert "full forecast packet is intentionally WITHHELD" in text
    assert "USER CONTEXT JSON (ADDED AFTER FREEZE)" in text
    assert "selection_hash" in text
    assert "crypto.subtle.digest('SHA-256'" in text


def test_blind_ranker_has_fixed_per_technique_quotas_and_groups_multipass():
    text = LAB.read_text(encoding="utf-8")
    assert "context-blind-forecast-v1" in text
    assert "transit_series:5" in text
    assert "eclipses:2" in text
    assert "const groups=new Map()" in text
    assert "`${x.transit}|${x.natal}|${x.type}`" in text
    assert "Do not collapse transit-series and eclipse rank scores into one universal score" in text


def test_control_window_is_same_length_and_non_overlapping():
    text = LAB.read_text(encoding="utf-8")
    assert "controlStart=addDays(targetEnd,183)" in text
    assert "controlEnd=addDays(controlStart,days-1)" in text
    assert "A/B" in text


def test_claim_contract_is_falsifiable_and_excludes_high_risk_outcomes():
    text = LAB.read_text(encoding="utf-8")
    for token in (
        "observable_event",
        "verification_rule",
        "evidence_ids",
        "Max 3 scored claims per window",
        "Vague claims",
        "health diagnosis/treatment claims",
        "legal verdict/win-loss claims",
        "Do not assign numeric probability/confidence",
    ):
        assert token in text


def test_review_scoring_and_target_control_reveal_ship_together():
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


def test_prompt_library_forecast_links_are_audit_gated_not_direct_templates():
    text = PROMPTS.read_text(encoding="utf-8")
    for h in ("30", "90", "365"):
        assert f'href="/forecast-lab?horizon={h}"' in text
    assert 'data-template="forecast_30"' not in text
    assert 'data-template="forecast_90"' not in text
    assert 'data-template="forecast_365"' not in text


def test_audit_methodology_is_documented():
    text = DOC.read_text(encoding="utf-8")
    assert "freeze-before-context" in text
    assert "target-vs-control" in text
    assert "browser `localStorage`" in text
    assert "not a complete randomized null model" in text
