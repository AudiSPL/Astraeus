from pathlib import Path

from agent.prompt import SYSTEM_PROMPT


ROOT = Path(__file__).resolve().parents[1]
GPT = (ROOT / "astraeus_gpt_instructions.md").read_text(encoding="utf-8")
CORE = (ROOT / "docs" / "ASTRAL_KING_STAGE3_CORE_PROMPT.md").read_text(encoding="utf-8")


def _all_text() -> str:
    return "\n".join((SYSTEM_PROMPT, GPT, CORE))


def test_prompt_knows_stage3_contract():
    text = _all_text()
    assert "qualified_birth_time_v1" in text
    assert "possible_values" in text
    assert "nominal_orb" in text
    assert "orb_range" in text


def test_prompt_forbids_nominal_promotion_when_unresolved():
    text = _all_text().lower()
    assert "never promote `nominal` to fact" in text or "never choose `nominal`" in text
    assert "value` is null" in text


def test_prompt_treats_audit_only_arrays_as_non_interpretive():
    text = _all_text()
    assert "birth_time_sensitive_nominal_" in text
    assert "audit_only_nominal" in text
    assert "audit-only" in text.lower()


def test_prompt_protects_synastry_suppression():
    text = _all_text().lower()
    assert "house_overlay" in text
    assert "composite" in text
    assert "never reconstruct" in text


def test_prompt_does_not_keep_old_chart_specific_gate():
    text = _all_text()
    assert "1984-07-24T03:10:00Z" not in text
    assert "TEMPORARY CHART-SPECIFIC" not in text


def test_prompt_uses_task_scoped_validation():
    text = _all_text()
    for token in (
        "validated_for_interpretation", "natal_validated", "transits_validated",
        "forecast_validated", "solar_return_validated", "synastry_validated",
        "bazi_validated", "progressions_validated",
    ):
        assert token in text
    assert "aggregate packet summary" in text
    assert "MUST NOT be used as an unconditional hard stop" in SYSTEM_PROMPT
    assert "packet-explanation or technical-audit task" in SYSTEM_PROMPT
    assert "If none of the requested" in SYSTEM_PROMPT


def test_prompt_distinguishes_evidence_context_interpretation():
    text = _all_text().lower()
    assert "calculated evidence" in text
    assert "user context" in text
    assert "interpretation" in text


def test_prompt_has_beginner_intermediate_expert_grounding():
    text = _all_text()
    assert "Beginner" in text
    assert "Intermediate" in text
    assert "Expert" in text
    assert "Beginner means simpler language" in text
