from lover_graph.prompts.loader import load_prompt, load_outcome_prompt
from lover_graph.schemas import Phase, Role


def test_matchmaker_prompt_includes_shared_and_phase():
    text = load_prompt(Role.MATCHMAKER, Phase.EVIDENCE)
    assert "输出格式" in text or "JSON" in text
    assert "举证质证" in text
    assert "审判员" in text


def test_male_prompt_forbids_law_citation():
    text = load_prompt(Role.MALE, Phase.INVESTIGATION)
    assert "禁止" in text or "不要" in text
    assert "原告" in text


def test_verdict_prompt_exists():
    text = load_outcome_prompt()
    assert "判决" in text
    assert "observations" in text
