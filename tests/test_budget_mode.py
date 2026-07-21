from lover_graph.constraints.budget import validate_budget_inputs
from lover_graph.schemas.trial_constraints import BudgetMode


def test_mutual_exclusive_budget_inputs():
    mode = validate_budget_inputs(budget_mode=None, max_rounds=30, word_count=None, duration_minutes=None)
    assert mode == BudgetMode.MATCHMAKER_TURNS

    mode = validate_budget_inputs(budget_mode=None, max_rounds=None, word_count=None, duration_minutes=40)
    assert mode == BudgetMode.TIME

    try:
        validate_budget_inputs(budget_mode=None, max_rounds=30, word_count=1000, duration_minutes=None)
        assert False, "should raise"
    except ValueError as e:
        assert "不能同时" in str(e)

    try:
        validate_budget_inputs(budget_mode=BudgetMode.TIME, max_rounds=30, word_count=None, duration_minutes=None)
        assert False
    except ValueError as e:
        assert "time 模式" in str(e)


def test_edges_ignore_max_rounds_in_time_mode():
    from lover_graph.constraints.budget import INACTIVE_MAX_ROUNDS
    from lover_graph.graph.edges import should_continue
    from lover_graph.schemas import DialogueTurn, Phase, Role
    from lover_graph.schemas.trial_constraints import SessionConstraints

    c = SessionConstraints(budget_mode=BudgetMode.TIME, word_count_limit=5000, max_rounds=INACTIVE_MAX_ROUNDS)
    dialogues = [
        DialogueTurn(
            speaker=1,
            role=Role.MATCHMAKER,
            role_name="法官",
            phase=Phase.DEBATE,
            text="x" * 20,
        )
        for _ in range(50)
    ]
    class _FakeSim:
        def resolved_constraints(self):
            return c

    state = {
        "session_input": type("C", (), {"tension_points": [], "max_rounds": 5})(),
        "dialogues": dialogues,
        "current_phase": Phase.DEBATE,
        "next_speaker": Role.MALE,
        "scenario": type("S", (), {"simulation": _FakeSim()})(),
    }
    assert should_continue(state) == "phase_controller"  # type: ignore[arg-type]
