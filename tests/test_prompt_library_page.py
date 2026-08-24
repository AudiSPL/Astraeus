from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = ROOT / "app" / "static" / "prompts.html"
UI = ROOT / "app" / "static" / "ui.html"
GUIDE = ROOT / "app" / "static" / "guide.html"


def test_prompts_route_serves_page_without_cache():
    r = TestClient(app).get("/prompts")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert r.headers["cache-control"] == "no-cache, must-revalidate"
    assert "Astraeus Prompt Library" in r.text


def test_navigation_links_prompt_library_from_calculator_and_guide():
    assert 'href="/prompts"' in UI.read_text(encoding="utf-8")
    assert 'href="/prompts"' in GUIDE.read_text(encoding="utf-8")


def test_prompt_library_has_only_non_audit_templates():
    text = PROMPTS.read_text(encoding="utf-8")
    expected = {
        "explain", "natal", "synastry", "composite", "solar_return",
        "progressions", "bazi", "combined", "static_full",
    }
    import re
    found = set(re.findall(r'data-template="([^"]+)"', text))
    assert found == expected
    for forbidden in ("current_period", "specific_date", "forecast_30", "forecast_90", "forecast_365"):
        assert f'data-template="{forbidden}"' not in text


def test_stage3_safety_contract_is_embedded_in_generated_prompts():
    text = PROMPTS.read_text(encoding="utf-8")
    for token in (
        "qualified", "value is null", "nominal is NOT a fact", "possible_values",
        "nominal_orb", "audit_only_nominal", "birth_time_sensitive_nominal_",
        "Never reconstruct suppressed synastry overlay/composite geometry",
    ):
        assert token in text


def test_prompt_library_has_audience_and_depth_controls():
    text = PROMPTS.read_text(encoding="utf-8")
    for token in (
        'value="beginner"', 'value="intermediate"', 'value="expert"',
        'value="concise"', 'value="detailed"', 'value="exhaustive"',
    ):
        assert token in text


def test_calculator_persists_last_successful_packet_for_copy_handoff():
    text = UI.read_text(encoding="utf-8")
    assert "astraeus-last-packet" in text
    assert "localStorage.setItem" in text


def test_prompt_page_supports_prompt_and_packet_copy_without_new_api_upload():
    text = PROMPTS.read_text(encoding="utf-8")
    assert "Kopiraj prompt + current packet" in text
    assert "navigator.clipboard.writeText" in text
    assert "astraeus-last-packet" in text
    assert "fetch('/v1/" not in text


def test_prediction_boundary_is_explicit():
    text = PROMPTS.read_text(encoding="utf-8")
    assert "Forecast je audit-gated" in text
    assert "blind ranker" in text
    assert "Forecast Lab" in text
    assert 'href="/forecast-lab?horizon=30"' in text
    assert 'href="/forecast-lab?horizon=90"' in text
    assert 'href="/forecast-lab?horizon=365"' in text
    assert "NON-PREDICTIVE" in text

def test_prompt_library_uses_task_scoped_validation():
    text = PROMPTS.read_text(encoding="utf-8")
    for token in (
        "TASK-SCOPED", "natal_validated", "transits_validated",
        "forecast_validated", "solar_return_validated", "synastry_validated",
        "bazi_validated", "progressions_validated", "task_scoped_v1",
    ):
        assert token in text
    assert "aggregate summary, NOT by itself a stop signal" in text
    assert "A false synastry_validated or other unrelated optional-block flag must not block a valid natal reading" in text
    assert "This is a diagnostic task. Never hard-stop solely because validated_for_interpretation is false" in text
