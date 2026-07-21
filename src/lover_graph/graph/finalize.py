"""Guarantee trial closure: closing ceremony + verdict always produced."""

from __future__ import annotations

from lover_graph.constraints import apply_forced_close
from lover_graph.graph.nodes.control import closing_node, outcome_node
from lover_graph.graph.state import SessionState
from lover_graph.procedure.closing_script import build_closing_ceremony
from lover_graph.schemas import Phase


def _merge_state(state: SessionState, update: dict) -> SessionState:
    merged: dict = dict(state)
    for key, val in update.items():
        if key in ("dialogues", "matchmaker_routing_log", "validator_results", "tool_calls"):
            merged[key] = list(merged.get(key, [])) + list(val)
        else:
            merged[key] = val
    return merged  # type: ignore[return-value]


def _has_closing_dialogue(state: SessionState) -> bool:
    return any(d.phase == Phase.CLOSING for d in state.get("dialogues", []))


def ensure_trial_closed(state: SessionState, *, run_verdict: bool = True) -> SessionState:
    """Ensure closing ceremony + verdict exist. Safe to call after interrupted graph stream."""
    if not state.get("termination"):
        state = _merge_state(state, apply_forced_close(state))

    if not _has_closing_dialogue(state):
        closing_turns = build_closing_ceremony(state)
        full = state.get("full_text", "")
        for t in closing_turns:
            full += f"\n{t.role_name}：{t.text}"
        state = _merge_state(
            state,
            {
                "dialogues": closing_turns,
                "full_text": full,
                "total_round": state.get("total_round", 0) + len(closing_turns),
                "current_phase": Phase.CLOSING,
            },
        )

    state = _merge_state(state, closing_node(state))

    if run_verdict and state.get("verdict") is None:
        state = _merge_state(state, outcome_node(state))

    return state
