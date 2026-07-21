from lover_graph.graph.nodes.base import run_thinking_agent
from lover_graph.graph.state import SessionState
from lover_graph.schemas import Role


def matchmaker_node(state: SessionState) -> dict:
    name = state["session_input"].matchmaker_name
    return run_thinking_agent(state, Role.MATCHMAKER, name)


def male_node(state: SessionState) -> dict:
    p = state["session_input"].male
    return run_thinking_agent(state, Role.MALE, p.name)


def male_parents_node(state: SessionState) -> dict:
    p = state["session_input"].male
    name = p.lawyer_name or f"{p.name}家长"
    return run_thinking_agent(state, Role.MALE_PARENTS, name)


def female_node(state: SessionState) -> dict:
    d = state["session_input"].female
    return run_thinking_agent(state, Role.FEMALE, d.name)


def female_parents_node(state: SessionState) -> dict:
    d = state["session_input"].female
    name = d.lawyer_name or f"{d.name}家长"
    return run_thinking_agent(state, Role.FEMALE_PARENTS, name)
