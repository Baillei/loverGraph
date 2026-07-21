"""分阶段法官发言 / 词数预算 — 将总预算切分到各程序阶段。"""

from __future__ import annotations

from lover_graph.constraints.tracker import count_speech_units
from lover_graph.graph.state import SessionState
from lover_graph.schemas import Phase, Role
from lover_graph.schemas.trial_constraints import SessionConstraints

DYNAMIC_PHASES = [
    Phase.INVESTIGATION,
    Phase.EVIDENCE,
    Phase.DEBATE,
    Phase.CLOSING,
]


def count_matchmaker_turns_in_phase(state: SessionState, phase: str | Phase) -> int:
    pv = phase.value if isinstance(phase, Phase) else phase
    return sum(
        1 for d in state.get("dialogues", []) if d.role == Role.MATCHMAKER and d.phase.value == pv
    )


def count_words_in_phase(state: SessionState, phase: str | Phase) -> int:
    pv = phase.value if isinstance(phase, Phase) else phase
    return sum(count_speech_units(d.text) for d in state.get("dialogues", []) if d.phase.value == pv)


def phase_matchmaker_budget(c: SessionConstraints, phase: str) -> int:
    return c.phase_matchmaker_turn_budget.get(phase, c.phase_round_soft_caps.get(phase, 6))


def phase_word_budget(c: SessionConstraints, phase: str) -> int:
    ratio = c.phase_word_budget_ratio.get(phase, 0.2)
    return max(50, int(c.word_count_limit * ratio))


def build_phase_budget_table(c: SessionConstraints) -> dict[str, dict]:
    """各阶段预算表（用于 harness / session_clock）。"""
    table = {}
    for ph in DYNAMIC_PHASES:
        key = ph.value
        table[key] = {
            "matchmaker_turn_budget": phase_matchmaker_budget(c, key),
            "word_budget": phase_word_budget(c, key),
        }
    return table
