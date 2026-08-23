from pathlib import Path

UI = Path("app/static/ui.html")


def _text():
    return UI.read_text(encoding="utf-8")


def test_ui_offers_custom_uncertainty_and_keeps_unknown_default():
    text = _text()
    assert 'value="custom"' in text
    assert 'id="bCustomUncertainty"' in text
    assert 'min="0.1" max="180" step="0.1"' in text
    assert '<option value="unknown" selected data-desc="Vreme nepoznato' in text


def test_ui_persists_birth_precision_preferences():
    text = _text()
    assert "function initBirthPrecisionPreferences()" in text
    assert "astraeus-birth-precision" in text
    assert "localStorage.setItem(key" in text
    assert "initBirthPrecisionPreferences();" in text


def test_ui_custom_precision_is_sent_as_positive_numeric_minutes():
    text = _text()
    assert "v === 'custom' ? parseFloat($(customId).value)" in text
    assert "minutes <= 0 || minutes > 180" in text
    assert "...precisionPayload('bAccuracy', 'bProvenance', 'bCustomUncertainty')" in text
