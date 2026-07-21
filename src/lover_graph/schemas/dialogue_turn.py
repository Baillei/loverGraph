from __future__ import annotations

from pydantic import BaseModel, Field

from lover_graph.schemas.session_input import Phase, Role


class ThinkingOutput(BaseModel):
    """Structured output from a thinking agent node."""

    think: str = Field(description="Internal reasoning, not spoken in venue")
    speak: str = Field(description="Formal venueroom utterance")
    next_speaker: Role | None = Field(
        default=None,
        description="Judge only: who speaks next",
    )
    end_session: bool = False
    skills_used: list[str] = Field(default_factory=list)
    contract_refs: list[str] = Field(default_factory=list)
    emotion: dict[str, float] = Field(
        default_factory=dict,
        description="本轮情绪向量，如 anger/anxiety/defensiveness 0.0~1.0",
    )
    value_signal: list[str] = Field(default_factory=list, description="价值偏好信号")


class DialogueTurn(BaseModel):
    speaker: int
    role: Role
    role_name: str = ""
    phase: Phase
    text: str
    think: str = ""
    routing: dict | None = None
    emotion: dict[str, float] | None = None
    contract_refs: list[str] = Field(default_factory=list)
    skills_used: list[str] = Field(default_factory=list)
    value_signal: list[str] = Field(
        default_factory=list,
        description="本轮体现的价值偏好信号",
    )
    validator_passed: bool = True
    interrupted: bool = Field(default=False, description="发言是否被法庭截断")
    attempted_speech: str | None = Field(
        default=None,
        description="截断前当事人意图说出的完整原话（含未播出部分，供庭审记录与法官上下文）",
    )
    truncated_remainder: str | None = Field(
        default=None,
        description="截断点之后未播出的余文",
    )
