from lover_graph.harness.phase_schedule import PhasePaceStatus, evaluate_phase_pace, get_phase_window
from lover_graph.schemas.trial_constraints import SessionConstraints


def test_phase_window_tolerance():
    c = SessionConstraints(
        phase_matchmaker_turn_budget={"debate": 8},
        phase_matchmaker_tolerance=2,
    )
    w = get_phase_window(c, "debate")
    assert w.min_matchmaker_turns == 6
    assert w.max_matchmaker_turns == 10
    assert w.target_matchmaker_turns == 8


def test_underfilled_blocks_advance():
    from lover_graph.graph.lover_graph import build_initial_state
    from lover_graph.harness.phase_coach import run_phase_coach
    from lover_graph.scenario import generate_random_scenario, scenario_to_session_input
    from lover_graph.schemas import DialogueTurn, Phase, Role
    from lover_graph.schemas.behavior_constraints import SimulationDefaults

    scenario = generate_random_scenario(SimulationDefaults(), seed=1)
    case = scenario_to_session_input(scenario)
    state = build_initial_state(case, scenario)
    state["current_phase"] = Phase.DEBATE
    state["dialogues"] = [
        DialogueTurn(
            speaker=1, role=Role.MATCHMAKER, role_name="法官", phase=Phase.DEBATE, text="短"
        )
    ]
    result = run_phase_coach(state)
    assert result.phase_pace_status == PhasePaceStatus.UNDERFILLED.value
    assert result.forbid_phase_advance is True
    assert "phase_pace_hold" in result.triggered_skills


def test_overdue_forces_advance():
    from lover_graph.graph.lover_graph import build_initial_state
    from lover_graph.harness.phase_coach import run_phase_coach
    from lover_graph.scenario import generate_random_scenario, scenario_to_session_input
    from lover_graph.schemas import DialogueTurn, Phase, Role
    from lover_graph.schemas.behavior_constraints import SimulationDefaults

    scenario = generate_random_scenario(SimulationDefaults(), seed=1)
    case = scenario_to_session_input(scenario)
    state = build_initial_state(case, scenario)
    state["current_phase"] = Phase.DEBATE
    w = get_phase_window(scenario.simulation.resolved_constraints(), "debate")
    state["dialogues"] = [
        DialogueTurn(
            speaker=1,
            role=Role.MATCHMAKER,
            role_name="法官",
            phase=Phase.DEBATE,
            text="辩论发言" * 80,
        )
        for _ in range(w.max_matchmaker_turns + 1)
    ]
    result = run_phase_coach(state)
    assert result.phase_pace_status == PhasePaceStatus.OVERDUE.value
    assert result.force_advance_phase is True
    assert result.next_phase == "closing"
