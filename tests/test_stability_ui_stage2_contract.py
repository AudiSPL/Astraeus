from pathlib import Path


UI = Path(__file__).parents[1] / "app" / "static" / "ui.html"


def test_ui_renders_birth_time_stability_summary():
    text = UI.read_text(encoding="utf-8")
    assert "function stabilitySummaryHtml(data)" in text
    assert 'id="stabilitySummary"' in text
    assert "house changes:" in text
    assert "nominal_field_status" in text


def test_ui_keeps_full_json_output_after_stability_summary():
    text = UI.read_text(encoding="utf-8")
    assert "let html = stabilitySummaryHtml(data);" in text
    assert 'html += `<pre class="json-pre">' in text
