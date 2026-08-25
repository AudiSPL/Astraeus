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


def lab_text() -> str:
    return LAB.read_text(encoding="utf-8")


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


def test_v12_uses_same_season_control_not_183_day_displacement():
    text = lab_text()
    assert "same-season-plus-1y-v1" in text
    assert "addYearsSameSeason(start,1)" in text
    assert "controlEnd=addDays(controlStart,days-1)" in text
    assert "controlStart=addDays(targetEnd,183)" not in text


def test_ranker_v12_keeps_candidate_technique_caps_and_groups_multipass():
    text = lab_text()
    assert "context-blind-forecast-v1.2" in text
    assert "CANDIDATE_QUOTAS={transit_series:5,eclipses:2}" in text
    assert "const groups=new Map()" in text
    assert "`${x.transit}|${x.natal}|${x.type}`" in text
    assert "do not collapse techniques into one universal score" in text.lower()


def test_v12_pairs_evidence_counts_by_technique_before_hashing():
    text = lab_text()
    for token in (
        "function pairEvidenceCounts(A,B)",
        "Math.min(CANDIDATE_QUOTAS.transit_series",
        "Math.min(CANDIDATE_QUOTAS.eclipses",
        "paired_quotas",
        "Evidence counts are PAIRED BY TECHNIQUE",
    ):
        assert token in text
    assert "pairEvidenceCounts(A,B)" in text
    assert "freezeHashPayload(draft)" in text


def test_scored_llm_package_withholds_calendar_dates_and_uses_day_offsets():
    text = lab_text()
    for token in (
        "calendar_dates_withheld_from_llm:true",
        "Calendar dates are deliberately withheld from you",
        "exact_day_offsets",
        "day_offset",
        "start_day",
        "end_day",
        "forecast_claims_v3",
    ):
        assert token in text
    assert "Do NOT infer, back-solve or output calendar dates" in text


def test_full_packet_is_withheld_and_selection_is_hashed_before_context():
    text = lab_text()
    assert "full_forecast_packet_withheld:true" in text
    assert "full forecast packet is intentionally WITHHELD" in text
    assert "crypto.subtle.digest('SHA-256'" in text
    assert "selection_hash" in text
    assert "MINIMAL DOMAIN CONTEXT" in text


def test_v12_recomputes_freeze_hash_before_accepting_claims():
    text = lab_text()
    for token in (
        "function freezeHashPayload(f)",
        "async function verifyFrozenIntegrity",
        "const actual=await sha256(freezeHashPayload(f))",
        "actual!==f.selection_hash",
        "Frozen evidence integrity check failed",
        "await verifyFrozenIntegrity();validateClaims(obj)",
    ):
        assert token in text


def test_v12_hashes_structured_claims_and_rechecks_before_reveal():
    text = lab_text()
    for token in (
        "claims_hash",
        "const claimsHash=await sha256(obj)",
        "async function verifyAuditIntegrity",
        "actual!==a.claims_hash",
        "await verifyAuditIntegrity(a)",
        "outcome_log_hash mismatch",
    ):
        assert token in text


def test_scored_phase_gets_only_minimal_domain_not_detailed_life_context():
    text = lab_text()
    assert "function minimalDomainContext(){return {domain:$('topic').value}}" in text
    assert "You do NOT receive detailed life context in this scored phase" in text
    assert "DETAILED USER CONTEXT (NON-SCORED)" in text


def test_fixed_claim_slots_remove_equal_claim_count_ambiguity():
    text = lab_text()
    for token in (
        "CLAIM_SLOTS=2",
        "Each window MUST contain exactly ${CLAIM_SLOTS} claim_slots",
        'Each slot is either kind=',
        'no_claim',
        "NEVER invent a filler event",
        "slots.length!==CLAIM_SLOTS",
        "no_claim slot mora imati kratak reason",
    ):
        assert token in text
    assert "Max 3 scored claims per window" not in text


def test_claim_contract_is_falsifiable_and_rejects_legal_related_money_outcomes():
    text = lab_text()
    for token in (
        "observable_event",
        "verification_rule",
        "evidence_ids",
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
    text = lab_text()
    assert "DATE_RX" in text
    assert "Number.isInteger(c.start_day)" in text
    assert "c.end_day>=frozen.horizon_days" in text
    assert "scored claim ne sme sadržati kalendarski datum" in text


def test_sealed_self_audit_is_default_and_requires_external_file_handoff():
    text = lab_text()
    assert '<option value="sealed_self_v1" selected>' in text
    assert "Import sealed response" in text
    assert "external operator" in text.lower() or "spoljnom operatoru" in text.lower()
    assert "Astraeus ne može učiniti ručno otvoren ChatGPT razgovor nevidljivim" in text
    assert "sealedClaimsImport" in text


def test_sealed_mode_hides_local_evidence_details_and_claim_content():
    text = lab_text()
    for token in (
        "Sealed local view",
        "Evidence names and exact local dates are hidden from the subject",
        "Claim content sealed",
        "renderEvidenceGrid",
        "sealed_claims_revealed",
    ):
        assert token in text


def test_open_mode_is_explicitly_exploratory_not_blind():
    text = lab_text()
    assert "open_exploratory_v1" in text
    assert "Open exploratory" in text
    assert "nije blind self-audit" in text
    assert "This output must not be described as a blinded self-audit" in text


def test_sealed_review_requires_both_windows_end_and_outcome_log_first():
    text = lab_text()
    for token in (
        "function windowsEnded(a)",
        "freezeOutcomeLog",
        "outcome_log_hash",
        "outcome_log_frozen_utc",
        "Zamrzni outcome log pre reveal-a",
        "Outcome log prvo mora biti zamrznut",
        "revealSealedClaims",
    ):
        assert token in text


def test_sealed_mode_blocks_detailed_context_until_claim_reveal():
    text = lab_text()
    assert "function contextAllowed(a)" in text
    assert "a.audit_mode!==MODE_SEALED||a.sealed_claims_revealed===true" in text
    assert "Context ostaje zaključan" in text


def test_review_scoring_and_target_control_reveal_still_ship_together():
    text = lab_text()
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
    text = lab_text()
    assert "function claimRange(w,c)" in text
    assert "addDays(w.period.start,c.start_day)" in text
    assert "addDays(w.period.start,c.end_day)" in text


def test_v3_export_is_written_and_legacy_exports_remain_importable():
    text = lab_text()
    assert "astraeus_audits_export_v3" in text
    assert "'astraeus_audits_export_v1','astraeus_audits_export_v2','astraeus_audits_export_v3'" in text
    assert "astraeus_saved_audit_v3" in text


def test_prompt_library_forecast_links_remain_audit_gated():
    text = PROMPTS.read_text(encoding="utf-8")
    for h in ("30", "90", "365"):
        assert f'href="/forecast-lab?horizon={h}"' in text
    assert 'data-template="forecast_30"' not in text
    assert 'data-template="forecast_90"' not in text
    assert 'data-template="forecast_365"' not in text


def test_v12_methodology_is_documented_in_both_docs():
    text = DOC.read_text(encoding="utf-8")
    prompt_text = PROMPT_DOC.read_text(encoding="utf-8")
    for token in (
        "Paired evidence counts",
        "Verified freeze checksum",
        "Fixed claim slots",
        "Sealed Self-Audit",
        "outcome log",
        "forecast_audit_v3",
        "forecast_claims_v3",
        "integrity checksum",
    ):
        assert token in text
    assert "Forecast Lab v1.2" in prompt_text
    assert "pair" in prompt_text.lower()
    assert "no_claim" in prompt_text
    assert "sealed" in prompt_text.lower()
