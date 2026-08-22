"""Lightweight static checks that the transit timezone picker is wired."""
from pathlib import Path

UI = Path('app/static/ui.html').read_text(encoding='utf-8')


def test_transit_timezone_input_has_searchable_list():
    assert 'id="tTz"' in UI
    assert 'id="tTzList"' in UI
    assert 'id="tTzStatus"' in UI
    assert 'attachTimezoneAC()' in UI


def test_ui_queries_server_timezone_endpoint_with_full_transit_moment():
    assert "fetch('/v1/timezones?'" in UI
    assert 'function transitLocalMoment()' in UI
    assert "return `${d}T${t}`;" in UI


def test_ui_surfaces_gap_ambiguous_and_posix_legacy_statuses():
    assert "entry.status === 'gap'" in UI
    assert "entry.status === 'ambiguous'" in UI
    assert 'posix_sign_reversed' in UI
