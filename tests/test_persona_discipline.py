from lover_graph.schemas.behavior_constraints import SimulationDefaults
from lover_graph.scenario.random_generator import generate_random_scenario
from lover_graph.tools.discipline import detect_violations, record_warning, should_interrupt
from lover_graph.schemas import Role
from lover_graph.schemas.behavior_constraints import BehaviorConstraints


def test_defaults_25_matchmaker_rounds_5_minutes():
    d = SimulationDefaults()
    assert d.max_rounds == 25
    assert d.derived_word_count_limit() == 1000


def test_random_scenario_has_lawyers():
    s = generate_random_scenario(SimulationDefaults(), seed=42)
    assert s.simulation.male_has_lawyer is True
    assert s.simulation.female_has_lawyer is True
    assert "male_parents" in s.parties or s.parties["male"].get("lawyer_name")


def test_detect_insult():
    assert "insult" in detect_violations("你真缺德", Role.FEMALE)


def test_warning_then_interrupt():
    b = BehaviorConstraints(matchmaker_warning_limit=2)
    w = {}
    w = record_warning(w, Role.MALE, "insult")
    assert not should_interrupt(w, Role.MALE, b)
    w = record_warning(w, Role.MALE, "insult")
    assert should_interrupt(w, Role.MALE, b)
