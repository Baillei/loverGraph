import json
from pathlib import Path

from lover_graph.graph.lover_graph import build_initial_state
from lover_graph.graph.finalize import ensure_trial_closed
from lover_graph.output.builder import build_trial_output
from lover_graph.output.jsonl_writer import write_trial_jsonl
from lover_graph.scenario import generate_random_scenario, scenario_to_session_input
from lover_graph.schemas.behavior_constraints import SimulationDefaults


def test_jsonl_writer_lines(tmp_path: Path):
    scenario = generate_random_scenario(SimulationDefaults(), seed=3)
    case = scenario_to_session_input(scenario)
    state = build_initial_state(case, scenario)
    out = build_trial_output(state)
    path = tmp_path / "trial.jsonl"
    from lover_graph.constraints import get_constraints
    from lover_graph.output.compliance import build_compliance_report

    write_trial_jsonl(
        path,
        out,
        compliance=build_compliance_report(state, get_constraints(state)),
    )
    lines = path.read_text(encoding="utf-8").strip().split("\n")
    assert lines[0].startswith('{"type": "meta"')
    types = [json.loads(line)["type"] for line in lines]
    assert types[0] == "meta"
    assert "persona" in types
    assert types[-1] == "compliance"


def test_ensure_trial_closed_adds_closing_without_verdict(monkeypatch):
    scenario = generate_random_scenario(SimulationDefaults(), seed=3)
    case = scenario_to_session_input(scenario)
    state = build_initial_state(case, scenario)
    state["opening_ceremony_done"] = True
    state["total_round"] = 5

    monkeypatch.setattr(
        "lover_graph.graph.finalize.outcome_node",
        lambda s: {"verdict": None, "current_phase": "verdict"},
    )
    closed = ensure_trial_closed(state, run_verdict=True)
    phases = {d.phase.value for d in closed["dialogues"]}
    assert "closing" in phases
