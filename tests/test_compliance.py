import json
from pathlib import Path

from lover_graph.constraints import get_constraints
from lover_graph.graph.lover_graph import build_initial_state
from lover_graph.harness.phase_budget import count_matchmaker_turns_in_phase
from lover_graph.output.compliance import build_compliance_report
from lover_graph.output.jsonl_writer import write_trial_jsonl
from lover_graph.schemas import DialogueTurn, Phase, Role
from lover_graph.schemas.trial_constraints import SessionConstraints


def test_compliance_flags_missing_debate():
    c = SessionConstraints(max_rounds=30, phase_matchmaker_turn_budget={"investigation": 8, "evidence": 8, "debate": 8, "closing": 4})
    dialogues = [
        DialogueTurn(speaker=1, role=Role.MATCHMAKER, role_name="法官", phase=Phase.INVESTIGATION, text="问")
        for _ in range(7)
    ] + [
        DialogueTurn(speaker=1, role=Role.MATCHMAKER, role_name="法官", phase=Phase.EVIDENCE, text="举证"),
    ]
    state = {
        "session_input": type("C", (), {"tension_points": ["a"], "max_rounds": 30})(),
        "dialogues": dialogues,
        "current_phase": Phase.EVIDENCE,
        "scenario": None,
        "verdict": None,
    }
    report = build_compliance_report(state, c, max_steps=500, steps_executed=40)
    assert report["type"] == "compliance"
    assert report["checks"]["required_phases"]["missing"] == ["debate", "closing"]
    assert report["overall_pass"] is False
    assert report["checks"]["phase_windows"]["phases"]["debate"]["pace_status"] == "missing"


def test_jsonl_ends_with_compliance(tmp_path: Path):
    from lover_graph.output.builder import build_trial_output
    from lover_graph.scenario import generate_random_scenario, scenario_to_session_input
    from lover_graph.schemas.behavior_constraints import SimulationDefaults

    scenario = generate_random_scenario(SimulationDefaults(), seed=3)
    case = scenario_to_session_input(scenario)
    state = build_initial_state(case, scenario)
    out = build_trial_output(state)
    compliance = build_compliance_report(state, get_constraints(state), max_steps=500, steps_executed=10)
    path = tmp_path / "trial.jsonl"
    write_trial_jsonl(path, out, compliance=compliance)
    lines = path.read_text(encoding="utf-8").strip().split("\n")
    last = json.loads(lines[-1])
    assert last["type"] == "compliance"
    assert "overall_pass" in last
    assert "checks" in last
