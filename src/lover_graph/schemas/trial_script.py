from __future__ import annotations

from pydantic import BaseModel, Field

from lover_graph.schemas.session_input import Phase
from lover_graph.schemas.dialogue_turn import DialogueTurn


class MatchOutcome(BaseModel):
    observations: str = ""
    matchmaker_opinion: str = ""
    final_result: str = ""
    contract_refs: list[str] = Field(default_factory=list)


class SessionScript(BaseModel):
    session_id: str
    title: str
    phases_completed: list[Phase] = Field(default_factory=list)
    dialogues: list[DialogueTurn] = Field(default_factory=list)
    tool_calls: list[dict] = Field(default_factory=list)
    verdict: MatchOutcome | None = None
    termination: str = "normal"
