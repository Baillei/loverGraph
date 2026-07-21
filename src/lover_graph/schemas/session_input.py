from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from lover_graph.schemas.party_profile import Gender


class Phase(str, Enum):
    OPENING = "opening"
    INVESTIGATION = "investigation"
    EVIDENCE = "evidence"
    DEBATE = "debate"
    CLOSING = "closing"
    VERDICT = "verdict"


class Role(str, Enum):
    MATCHMAKER = "matchmaker"
    MALE = "male"
    MALE_PARENTS = "male_parents"
    FEMALE = "female"
    FEMALE_PARENTS = "female_parents"


class SpeakerId(int, Enum):
    DISCIPLINE = 0
    MATCHMAKER = 1
    MALE = 2
    FEMALE_OR_PARTY = 3
    OTHER_PARTY = 4


ROLE_TO_SPEAKER: dict[Role, SpeakerId] = {
    Role.MATCHMAKER: SpeakerId.MATCHMAKER,
    Role.MALE: SpeakerId.MALE,
    Role.MALE_PARENTS: SpeakerId.OTHER_PARTY,
    Role.FEMALE: SpeakerId.FEMALE_OR_PARTY,
    Role.FEMALE_PARENTS: SpeakerId.OTHER_PARTY,
}


class PartyInfo(BaseModel):
    name: str
    role: Role
    gender: Gender = Gender.UNKNOWN
    has_lawyer: bool = False  # 家长是否陪同（沿用字段名以兼容图结构）
    lawyer_name: str | None = None  # 家长代表称呼
    lawyer_gender: Gender = Gender.UNKNOWN
    profile: str = ""
    ideal_partner: str = ""


class SessionInput(BaseModel):
    session_id: str
    title: str
    venue: str = ""
    matchmaker_name: str = "王媒婆"
    assistant_name: str = "小李"
    male: PartyInfo
    female: PartyInfo
    ideal_partner_notes: str = ""
    background_summary: str = ""
    tension_points: list[str] = Field(default_factory=list)
    max_rounds: int = 40
