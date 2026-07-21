from lover_graph.scenario import generate_random_scenario, scenario_to_session_input
from lover_graph.schemas import Role
from lover_graph.scenario.loader import build_role_scenario_context, format_evidence_for_role
from lover_graph.schemas.behavior_constraints import SimulationDefaults

FIXTURE = generate_random_scenario(SimulationDefaults(), seed=12345)


def test_random_fixture_valid():
    s = FIXTURE
    assert s.trait_pool.total_count >= 6
    assert s.simulation.male_has_lawyer is True
    assert s.simulation.female_has_lawyer is True


def test_pp_dp_leq_n():
    s = FIXTURE
    pp = len(s.trait_pool.male_bundle)
    dp = len(s.trait_pool.female_bundle)
    assert pp + dp <= s.trait_pool.total_count


def test_scenario_to_session_input_has_lawyers():
    case = scenario_to_session_input(FIXTURE)
    assert case.male.has_lawyer is True
    assert case.female.has_lawyer is True
    assert case.male.lawyer_name
    assert case.female.lawyer_name


def test_role_context_not_full_narrative():
    ctx = build_role_scenario_context(FIXTURE, Role.MALE)
    assert "Who" in ctx or "5W1H" in ctx
    assert FIXTURE.narrative.synopsis not in ctx


def test_matchmaker_sees_only_pp_and_dp():
    text = format_evidence_for_role(FIXTURE, Role.MATCHMAKER)
    assert "全局登记" not in text


def test_female_sees_rumored_if_any():
    text = format_evidence_for_role(FIXTURE, Role.FEMALE)
    assert "证据概况" in text
