"""Compile the venue trial LangGraph."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from lover_graph.graph.edges import (
    route_after_discipline_validator,
    route_after_phase_controller,
    route_to_speaker,
    should_continue,
)
from lover_graph.graph.nodes import (
    closing_node,
    female_parents_node,
    female_node,
    discipline_validator_node,
    harness_coach_node,
    matchmaker_discipline_node,
    matchmaker_node,
    opening_ceremony_node,
    phase_controller,
    male_parents_node,
    male_node,
    outcome_node,
)
from lover_graph.graph.state import SessionState
from lover_graph.schemas import SessionInput, Phase, Role, MatchScenario

SPEAKER_NODES = {
    "matchmaker": matchmaker_node,
    "male": male_node,
    "male_parents": male_parents_node,
    "female": female_node,
    "female_parents": female_parents_node,
}

PARTY_NODES = ("male", "male_parents", "female", "female_parents")


def build_initial_state(case: SessionInput, scenario: MatchScenario) -> SessionState:
    return SessionState(
        session_input=case,
        scenario=scenario,
        current_phase=Phase.OPENING,
        phase_round=0,
        total_round=0,
        dialogues=[],
        full_text="",
        next_speaker=Role.MATCHMAKER,
        matchmaker_routing_log=[],
        validator_results=[],
        saturation_flag=False,
        tool_calls=[],
        termination="",
        verdict=None,
        discipline_warnings={},
        muted_roles={},
        needs_matchmaker_discipline=False,
        discipline_event=None,
        party_turn_buffer=None,
        discipline_followup=None,
        opening_ceremony_done=False,
        harness_context={},
    )


def build_graph():
    g = StateGraph(SessionState)

    g.add_node("opening_ceremony", opening_ceremony_node)
    g.add_node("harness_coach", harness_coach_node)
    g.add_node("phase_controller", phase_controller)
    for name, fn in SPEAKER_NODES.items():
        g.add_node(name, fn)
    g.add_node("closing", closing_node)
    g.add_node("verdict", outcome_node)
    g.add_node("discipline_validator", discipline_validator_node)
    g.add_node("matchmaker_discipline", matchmaker_discipline_node)

    g.add_edge(START, "opening_ceremony")
    g.add_edge("opening_ceremony", "phase_controller")
    g.add_edge("phase_controller", "harness_coach")
    g.add_conditional_edges(
        "harness_coach",
        route_after_phase_controller,
        {"dispatch_speaker": "route_hub", "closing": "closing", "verdict": "verdict"},
    )

    # virtual hub: route to next speaker
    def route_hub(state: SessionState) -> dict:
        return {}

    g.add_node("route_hub", route_hub)
    g.add_conditional_edges(
        "route_hub",
        route_to_speaker,
        {
            "matchmaker": "matchmaker",
            "male": "male",
            "male_parents": "male_parents",
            "female": "female",
            "female_parents": "female_parents",
            "closing": "closing",
        },
    )

    for name in PARTY_NODES:
        g.add_edge(name, "discipline_validator")

    g.add_conditional_edges(
        "discipline_validator",
        route_after_discipline_validator,
        {"matchmaker_discipline": "matchmaker_discipline", "phase_controller": "phase_controller"},
    )
    g.add_edge("matchmaker_discipline", "phase_controller")

    g.add_conditional_edges(
        "matchmaker",
        should_continue,
        {"phase_controller": "phase_controller", "closing": "closing"},
    )

    g.add_edge("closing", "verdict")
    g.add_edge("verdict", END)

    return g.compile()
