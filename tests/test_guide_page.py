from pathlib import Path


def test_guide_route_is_served(client):
    response = client.get("/guide")
    assert response.status_code == 200
    assert "Astraeus Guide" in response.text
    assert "Qualified Output Contract" in response.text


def test_calculator_links_to_guide(client):
    response = client.get("/")
    assert response.status_code == 200
    assert 'href="/guide"' in response.text


def test_guide_documents_current_menu_modules(client):
    text = client.get("/guide").text
    for marker in (
        "Tropical, Sidereal i ayanamsha",
        "Progressions i Solar Arc",
        "Forecast",
        "Solar Return",
        "Synastry i Composite",
        "BaZi / Four Pillars",
        "Vreme rodjenja: precision, provenance i stability",
    ):
        assert marker in text


def test_guide_uses_real_release_shas(client):
    text = client.get("/guide").text
    for sha in (
        "46bcd81",
        "8fd97eb",
        "a6a1018",
        "8e64beb",
        "2cc6a68",
        "089d9b6",
        "e151901",
        "af33960",
    ):
        assert sha in text
    assert "1.5.0" not in text


def test_guide_lists_four_strict_xfail_topics(client):
    text = client.get("/guide").text
    assert "Whole Sign composite cusp geometry" in text
    assert "Whole Sign composite H1" in text
    assert "Circular midpoint" in text
    assert "cross_aspects" in text


def test_guide_keeps_prediction_features_out_of_this_release(client):
    text = client.get("/guide").text
    assert "Prompt Library je sada dostupna" in text
    assert "Context Builder i Prediction Audit jos nisu isporuceni" in text
    assert "Timeframe forecast prompt kartice se ne isporucuju pre audit loop-a" in text


def test_repo_docs_match_release_boundary():
    repo = Path(__file__).resolve().parents[1]
    history = (repo / "docs" / "RELEASE_HISTORY.md").read_text(encoding="utf-8")
    limitations = (repo / "docs" / "KNOWN_LIMITATIONS.md").read_text(encoding="utf-8")
    assert "af33960" in history
    assert "retroactive SemVer" in history
    assert "4 expected failures" in limitations
    assert "Prediction Audit" in limitations
