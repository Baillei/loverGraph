"""Rich trial output schemas — 超越 GT 字段，供数字人下游使用。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from lover_graph.schemas.session_input import Phase
from lover_graph.schemas.dialogue_turn import DialogueTurn
from lover_graph.schemas.trial_script import MatchOutcome


class EmotionTimelineEntry(BaseModel):
    turn_index: int
    phase: Phase
    role: str
    role_name: str
    emotion: dict[str, float] = Field(default_factory=dict)
    speak_excerpt: str = ""


class GestureHint(BaseModel):
    turn_index: int
    role: str
    action: str = Field(description="如 interrupt, slam_table, point, calm_down")
    reason: str = ""


class DisputePointStatus(BaseModel):
    point: str
    status: str = "open"  # open | addressed | unresolved
    mentioned_in_turns: list[int] = Field(default_factory=list)


class DisputeTracker(BaseModel):
    points: list[DisputePointStatus] = Field(default_factory=list)


class ValueArcEntry(BaseModel):
    role: str
    values: list[str] = Field(default_factory=list)


class DigitalHumanAssets(BaseModel):
    emotion_timeline: list[EmotionTimelineEntry] = Field(default_factory=list)
    gesture_hints: list[GestureHint] = Field(default_factory=list)
    value_arc: list[ValueArcEntry] = Field(default_factory=list)


class RolePersonaSnapshot(BaseModel):
    role: str
    name: str
    gender: str = "unknown"
    archetype: str
    big_five: dict[str, float] = Field(default_factory=dict)
    value_preferences: list[str] = Field(default_factory=list)


class SimulationMetadata(BaseModel):
    budget_mode: str = "matchmaker_turns"
    max_rounds: int = Field(default=0, description="法官发言次数上限（matchmaker_turns 模式）")
    word_count_limit: int = 0
    word_count_used: int = 0
    rounds_used: int = Field(default=0, description="法官已发言次数")
    duration_minutes_limit: float = 0.0
    male_has_lawyer: bool = True
    female_has_lawyer: bool = True
    termination: str = "normal"
    phases_completed: list[str] = Field(default_factory=list)


class SessionScriptOutput(BaseModel):
    """完整庭审剧本输出 — 字段集参考 GT 并扩展，内容与任何真实案件无关。"""

    schema_version: str = "venueGraph/1.0"
    scenario_id: str
    session_id: str
    title: str
    venue: str = ""
    meeting_type: str = ""

    metadata: SimulationMetadata = Field(default_factory=SimulationMetadata)
    personas: list[RolePersonaSnapshot] = Field(default_factory=list)

    dialogues: list[DialogueTurn] = Field(default_factory=list)
    dispute_tracker: DisputeTracker = Field(default_factory=DisputeTracker)

    tool_calls: list[dict] = Field(default_factory=list)
    matchmaker_routing_log: list[dict] = Field(default_factory=list)
    discipline_warnings: dict[str, int] = Field(default_factory=dict)

    verdict: MatchOutcome | None = None
    digital_human_assets: DigitalHumanAssets = Field(default_factory=DigitalHumanAssets)
