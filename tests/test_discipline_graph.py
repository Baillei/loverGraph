"""纪律 validator 图节点与发言截断。"""

from lover_graph.graph.nodes.discipline import discipline_validator_node, matchmaker_discipline_node
from lover_graph.schemas import DialogueTurn, Phase, Role
from lover_graph.schemas.behavior_constraints import DisciplineDemo, SimulationDefaults
from lover_graph.scenario import generate_random_scenario
from lover_graph.tools.discipline import detect_violations, truncate_speech_at_violation
from lover_graph.graph.nodes.base import _get_scripted_speak, _count_role_turns


def _minimal_state(**overrides):
    from lover_graph.scenario import generate_random_scenario, scenario_to_session_input

    scenario = generate_random_scenario(SimulationDefaults(), seed=1)
    case = scenario_to_session_input(scenario)
    base = {
        "session_input": case,
        "scenario": scenario,
        "current_phase": Phase.DEBATE,
        "phase_round": 1,
        "total_round": 5,
        "dialogues": [],
        "full_text": "",
        "discipline_warnings": {},
        "muted_roles": {},
        "tool_calls": [],
        "party_turn_buffer": None,
        "needs_matchmaker_discipline": False,
        "discipline_event": None,
    }
    base.update(overrides)
    return base


def test_truncate_before_insult_tail():
    text = "我草泥马，我明明没有偷钱"
    truncated, remainder, violations = truncate_speech_at_violation(text, Role.FEMALE)
    assert "insult" in violations
    assert "偷钱" not in truncated
    assert truncated.endswith("——")
    assert "草泥马" in remainder


def test_truncate_pure_insult():
    truncated, remainder, violations = truncate_speech_at_violation(
        "我草泥马！", Role.FEMALE
    )
    assert violations == ["insult"]
    assert truncated == "我——"
    assert "草泥马" in remainder


def test_detect_caonima_pattern():
    assert "insult" in detect_violations("我草泥马！", Role.FEMALE)


def test_discipline_validator_truncates_and_flags():
    buf = DialogueTurn(
        speaker=2,
        role=Role.FEMALE,
        role_name="王某",
        phase=Phase.DEBATE,
        text="我草泥马，我明明没有偷钱",
        think="激动",
    )
    state = _minimal_state(party_turn_buffer=buf)
    out = discipline_validator_node(state)

    assert out["needs_matchmaker_discipline"] is True
    assert out["dialogues"][0].interrupted is True
    assert out["dialogues"][0].attempted_speech == "我草泥马，我明明没有偷钱"
    assert "草泥马" in (out["dialogues"][0].truncated_remainder or "")
    assert "偷钱" not in out["dialogues"][0].text
    assert out["discipline_event"]["remainder"]
    assert out["discipline_warnings"].get("female") == 1


def test_matchmaker_discipline_inserts_script_turn():
    state = _minimal_state(
        needs_matchmaker_discipline=True,
        discipline_event={
            "role": "female",
            "role_name": "王某",
            "violations": ["insult"],
            "action": "warn",
            "remainder": "草泥马，我明明没有偷钱",
            "attempted_speech": "我草泥马，我明明没有偷钱",
            "broadcast_text": "我——",
            "round": 5,
        },
    )
    out = matchmaker_discipline_node(state)
    assert out["dialogues"][0].role == Role.MATCHMAKER
    assert "法庭警告" in out["dialogues"][0].text
    assert out["needs_matchmaker_discipline"] is False
    assert out["next_speaker"] == Role.MATCHMAKER
    fu = out["discipline_followup"]
    assert fu is not None
    assert fu["broadcast_text"] == "我——"
    assert "我——" in fu["coach_message"]
    assert "我草泥马" in fu["coach_message"]
    assert fu["attempted_speech"] == "我草泥马，我明明没有偷钱"


def test_discipline_demo_disabled_by_default():
    scenario = generate_random_scenario(SimulationDefaults(), seed=2)
    assert scenario.simulation.behavior.discipline_demo is not None
    assert scenario.simulation.behavior.discipline_demo.enabled is False


def test_scripted_female_when_demo_enabled():
    from lover_graph.scenario import generate_random_scenario, scenario_to_session_input

    defaults = SimulationDefaults()
    defaults.behavior.discipline_demo = DisciplineDemo(
        enabled=True, role="female", speech_index=3, text="我草泥马！"
    )
    scenario = generate_random_scenario(defaults, seed=2)
    case = scenario_to_session_input(scenario)
    dialogues = [
        DialogueTurn(
            speaker=2,
            role=Role.FEMALE,
            role_name=case.female.name,
            phase=Phase.INVESTIGATION,
            text=f"被告发言{i}",
        )
        for i in range(2)
    ]
    state = {
        "scenario": scenario,
        "dialogues": dialogues,
    }
    assert _count_role_turns(state, Role.FEMALE) == 2  # type: ignore[arg-type]
    scripted = _get_scripted_speak(state, Role.FEMALE)  # type: ignore[arg-type]
    assert scripted == "我草泥马！"


def test_discipline_demo_disabled():
    from lover_graph.scenario import generate_random_scenario, scenario_to_session_input

    defaults = SimulationDefaults()
    defaults.behavior.discipline_demo = DisciplineDemo(enabled=False)
    scenario = generate_random_scenario(defaults, seed=2)
    state = {"scenario": scenario, "dialogues": []}
    assert _get_scripted_speak(state, Role.FEMALE) is None  # type: ignore[arg-type]
