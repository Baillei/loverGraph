from lover_graph.output.builder import build_trial_output
from lover_graph.scenario import generate_random_scenario, scenario_to_session_input
from lover_graph.graph.lover_graph import build_initial_state
from lover_graph.schemas import DialogueTurn, Phase, Role
from lover_graph.schemas.behavior_constraints import SimulationDefaults


def test_trial_output_has_digital_human_fields():
    scenario = generate_random_scenario(SimulationDefaults(), seed=1)
    case = scenario_to_session_input(scenario)
    state = build_initial_state(case, scenario)
    state["dialogues"] = [
        DialogueTurn(
            speaker=2,
            role=Role.MALE,
            role_name="原告",
            phase=Phase.INVESTIGATION,
            text="我要求被告赔偿",
            emotion={"anger": 0.5},
            value_signal=["Fairness"],
        )
    ]
    out = build_trial_output(state)
    assert out.schema_version.startswith("venueGraph/")
    assert len(out.personas) >= 5
    assert out.digital_human_assets.emotion_timeline
    assert out.metadata.male_has_lawyer is True
