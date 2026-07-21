from lover_graph.procedure.opening_script import build_opening_ceremony, first_investigation_speaker
from lover_graph.scenario import generate_random_scenario, scenario_to_session_input
from lover_graph.schemas import Phase, Role
from lover_graph.schemas.behavior_constraints import SimulationDefaults


def test_opening_ceremony_five_turns():
    scenario = generate_random_scenario(SimulationDefaults(), seed=7)
    case = scenario_to_session_input(scenario)
    turns = build_opening_ceremony(case, scenario)
    assert len(turns) == 5
    assert all(t.phase == Phase.OPENING for t in turns)
    assert all("fixed_ceremony" in t.skills_used for t in turns)


def test_opening_ceremony_professional_matchmaker_text():
    scenario = generate_random_scenario(SimulationDefaults(), seed=7)
    case = scenario_to_session_input(scenario)
    matchmaker_turn = build_opening_ceremony(case, scenario)[0]
    assert matchmaker_turn.role == Role.MATCHMAKER
    assert "法庭纪律" in matchmaker_turn.text
    assert "公开审理" in matchmaker_turn.text
    assert "独任审判" in matchmaker_turn.text
    assert case.male.name in matchmaker_turn.text
    assert case.female.name in matchmaker_turn.text


def test_opening_ceremony_uses_lawyers_by_default():
    scenario = generate_random_scenario(SimulationDefaults(), seed=7)
    case = scenario_to_session_input(scenario)
    turns = build_opening_ceremony(case, scenario)
    assert turns[1].role == Role.MALE_PARENTS
    assert turns[3].role == Role.FEMALE_PARENTS
    assert "委托诉讼代理人" in turns[1].text
    assert first_investigation_speaker(case) == Role.MALE_PARENTS


def test_opening_ceremony_without_lawyers():
    scenario = generate_random_scenario(
        SimulationDefaults(male_has_lawyer=False, female_has_lawyer=False),
        seed=7,
    )
    case = scenario_to_session_input(scenario)
    turns = build_opening_ceremony(case, scenario)
    assert turns[1].role == Role.MALE
    assert turns[3].role == Role.FEMALE
    assert first_investigation_speaker(case) == Role.MALE
