"""Conditional routing for LangGraph edges."""

from __future__ import annotations

from lover_graph.constraints.budget import rounds_enforced
from lover_graph.constraints import compute_budget, count_matchmaker_turns, get_constraints
from lover_graph.graph.nodes.base import _count_role_turns
from lover_graph.graph.state import SessionState
from lover_graph.schemas import Phase, Role


def _demo_party_route_override(state: SessionState, nxt: Role | str) -> str | None:
    """演示场景：有律师时仍保证被告本人凑满 speech_index 次发言。"""
    scenario = state.get("scenario")
    if scenario is None:
        return None
    demo = scenario.simulation.behavior.discipline_demo
    if demo is None or not demo.enabled or not demo.prefer_party_over_lawyer:
        return None
    phase = state.get("current_phase")
    if phase in (Phase.CLOSING, Phase.OPENING, Phase.VERDICT):
        return None
    try:
        target = Role(demo.role)
    except ValueError:
        return None
    if _count_role_turns(state, target) >= demo.speech_index:
        return None
    lawyer = {
        Role.MALE: Role.MALE_PARENTS,
        Role.FEMALE: Role.FEMALE_PARENTS,
    }.get(target)
    if nxt in (target, lawyer):
        return {
            Role.MALE: "male",
            Role.FEMALE: "female",
        }[target]
    return None


def route_after_discipline_validator(state: SessionState) -> str:
    if state.get("needs_matchmaker_discipline"):
        return "matchmaker_discipline"
    return "phase_controller"


def route_after_phase_controller(state: SessionState) -> str:
    phase = state["current_phase"]
    if phase == Phase.VERDICT:
        return "verdict"
    if phase == Phase.CLOSING:
        return "closing"
    return "dispatch_speaker"


def route_to_speaker(state: SessionState) -> str:
    nxt = state.get("next_speaker", Role.MATCHMAKER)
    if nxt in ("End", "end"):
        return "closing"
    if isinstance(nxt, Role):
        demo_route = _demo_party_route_override(state, nxt)
        if demo_route:
            return demo_route
    mapping = {
        Role.MATCHMAKER: "matchmaker",
        Role.MALE: "male",
        Role.MALE_PARENTS: "male_parents",
        Role.FEMALE: "female",
        Role.FEMALE_PARENTS: "female_parents",
    }
    return mapping.get(nxt, "matchmaker")  # type: ignore[arg-type]


def should_continue(state: SessionState) -> str:
    if state.get("termination") in ("forced", "round_limit", "matchmaker_round_limit", "word_limit", "budget_hard"):
        return "closing"
    nxt = state.get("next_speaker")
    if nxt in ("End", "end"):
        return "closing"
    if state.get("current_phase") == Phase.CLOSING:
        return "closing"

    constraints = get_constraints(state)
    snap = compute_budget(state, constraints)

    if snap.force_close_now and constraints.auto_force_close_at_hard_limit:
        return "closing"

    if rounds_enforced(constraints) and count_matchmaker_turns(state) >= constraints.max_rounds:
        return "closing"

    return "phase_controller"
