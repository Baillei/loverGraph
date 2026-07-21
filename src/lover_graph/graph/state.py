from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from lover_graph.schemas import SessionInput, DialogueTurn, Phase, Role, MatchScenario, MatchOutcome


class SessionState(TypedDict):
    session_input: SessionInput
    scenario: MatchScenario
    current_phase: Phase
    phase_round: int
    total_round: int

    dialogues: Annotated[list[DialogueTurn], operator.add]
    full_text: str

    next_speaker: Role | str
    matchmaker_routing_log: Annotated[list[dict], operator.add]

    validator_results: Annotated[list[dict], operator.add]
    saturation_flag: bool
    tool_calls: Annotated[list[dict], operator.add]

    termination: str
    verdict: MatchOutcome | None

    # 纪律状态
    discipline_warnings: dict[str, int]
    muted_roles: dict[str, int]

    # 纪律打断（validator 节点消费）
    needs_matchmaker_discipline: bool
    discipline_event: dict | None
    party_turn_buffer: DialogueTurn | None
    discipline_followup: dict | None

    # 固定开庭程序是否已注入
    opening_ceremony_done: bool

    # Harness：阶段性控场上下文（DETERMINISTIC 节点写入，MODEL 节点只读）
    harness_context: dict
