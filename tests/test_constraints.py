from lover_graph.constraints import compute_budget, count_matchmaker_turns
from lover_graph.schemas import DialogueTurn, Phase, Role
from lover_graph.schemas.trial_constraints import SessionConstraints


def test_count_matchmaker_turns_only():
    state = {
        "dialogues": [
            DialogueTurn(speaker=1, role=Role.MATCHMAKER, role_name="法官", phase=Phase.OPENING, text="a"),
            DialogueTurn(speaker=2, role=Role.MALE, role_name="原告", phase=Phase.OPENING, text="b"),
            DialogueTurn(speaker=1, role=Role.MATCHMAKER, role_name="法官", phase=Phase.INVESTIGATION, text="c"),
        ]
    }
    assert count_matchmaker_turns(state) == 2  # type: ignore[arg-type]


def test_budget_urgency_yellow_by_matchmaker_rounds():
    from lover_graph.schemas.trial_constraints import BudgetMode

    c = SessionConstraints(
        word_count_limit=10000,
        max_rounds=10,
        soft_budget_ratio=0.8,
        budget_mode=BudgetMode.MATCHMAKER_TURNS,
    )
    state = {
        "session_input": type("C", (), {"tension_points": ["a"], "max_rounds": 10})(),
        "dialogues": [
            DialogueTurn(
                speaker=1,
                role=Role.MATCHMAKER,
                role_name="法官",
                phase=Phase.OPENING,
                text="请",
            )
            for _ in range(8)
        ],
        "total_round": 8,
        "current_phase": "opening",
        "scenario": None,
    }
    snap = compute_budget(state, c)  # type: ignore[arg-type]
    assert snap.urgency.value == "yellow"


def test_budget_urgency_yellow_by_time_mode():
    from lover_graph.schemas.trial_constraints import BudgetMode

    c = SessionConstraints(
        word_count_limit=100,
        max_rounds=100,
        soft_budget_ratio=0.8,
        budget_mode=BudgetMode.TIME,
    )
    state = {
        "session_input": type("C", (), {"tension_points": ["a"], "max_rounds": 100})(),
        "dialogues": [
            DialogueTurn(
                speaker=1,
                role=Role.MATCHMAKER,
                role_name="法官",
                phase=Phase.OPENING,
                text="请" * 85,
            )
        ],
        "total_round": 2,
        "current_phase": "opening",
        "scenario": None,
    }
    snap = compute_budget(state, c)  # type: ignore[arg-type]
    assert snap.urgency.value == "yellow"


def test_word_count_ignored_in_matchmaker_turns_mode():
    from lover_graph.schemas.trial_constraints import BudgetMode

    c = SessionConstraints(
        word_count_limit=50,
        max_rounds=20,
        hard_budget_ratio=0.9,
        budget_mode=BudgetMode.MATCHMAKER_TURNS,
    )
    state = {
        "session_input": type("C", (), {"tension_points": [], "max_rounds": 20})(),
        "dialogues": [
            DialogueTurn(
                speaker=1,
                role=Role.MATCHMAKER,
                role_name="法官",
                phase=Phase.OPENING,
                text="请" * 200,
            )
        ],
        "total_round": 2,
        "current_phase": "opening",
        "scenario": None,
    }
    snap = compute_budget(state, c)  # type: ignore[arg-type]
    assert snap.force_close_now is False
    assert snap.termination_reason is None


def test_force_close_at_word_limit():
    from lover_graph.schemas.trial_constraints import BudgetMode

    c = SessionConstraints(
        word_count_limit=50,
        max_rounds=20,
        hard_budget_ratio=0.9,
        budget_mode=BudgetMode.TIME,
    )
    state = {
        "session_input": type("C", (), {"tension_points": [], "max_rounds": 20})(),
        "dialogues": [
            DialogueTurn(
                speaker=1,
                role=Role.MATCHMAKER,
                role_name="法官",
                phase=Phase.OPENING,
                text="请" * 50,
            )
        ],
        "total_round": 2,
        "current_phase": "opening",
        "scenario": None,
    }
    snap = compute_budget(state, c)  # type: ignore[arg-type]
    assert snap.must_close_soon is True
    assert snap.force_close_now is True
    assert snap.termination_reason == "word_limit"


def test_force_close_at_max_matchmaker_rounds():
    c = SessionConstraints(word_count_limit=5000, max_rounds=5)
    dialogues = [
        DialogueTurn(
            speaker=1,
            role=Role.MATCHMAKER,
            role_name="法官",
            phase=Phase.OPENING,
            text=f"法官发言{i}",
        )
        for i in range(5)
    ]
    state = {
        "session_input": type("C", (), {"tension_points": [], "max_rounds": 5})(),
        "dialogues": dialogues,
        "total_round": 10,
        "current_phase": "debate",
        "scenario": None,
    }
    snap = compute_budget(state, c)  # type: ignore[arg-type]
    assert snap.rounds_used == 5
    assert snap.force_close_now is True
    assert snap.termination_reason == "matchmaker_round_limit"
