from pathlib import Path

UI = Path("app/static/ui.html")


def _text():
    return UI.read_text(encoding="utf-8")


def test_birth_precision_ui_has_requested_levels_and_unknown_default():
    text = _text()
    for token in ('value="exact"', 'value="approx_5"', 'value="approx_15"', 'value="approx_60"', 'value="unknown"'):
        assert token in text
    assert '<option value="unknown" selected data-desc="Vreme nepoznato' in text


def test_ui_sends_numeric_uncertainty_and_provenance():
    text = _text()
    assert "function precisionPayload(selectId, provenanceId, customId)" in text
    assert "v === 'custom' ? parseFloat($(customId).value) : parseFloat(v.split('_')[1])" in text
    assert "birth_time_provenance" in text
    assert "...precisionPayload('bAccuracy', 'bProvenance', 'bCustomUncertainty')" in text
    assert "...precisionPayload('ynAccuracy', 'ynProvenance', 'ynCustomUncertainty')" in text
