"""Big Five persona — five roles configurable."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class RoleArchetype(str, Enum):
    NEUTRAL = "neutral"  # 媒婆：面无表情、控场
    SOCIAL = "social"  # 男女主：年轻、经验少、可情绪化
    PROFESSIONAL = "professional"  # 家长：老练、有阅历


class BigFivePersona(BaseModel):
    openness: float = Field(default=0.5, ge=0.0, le=1.0)
    conscientiousness: float = Field(default=0.5, ge=0.0, le=1.0)
    extraversion: float = Field(default=0.5, ge=0.0, le=1.0)
    agreeableness: float = Field(default=0.5, ge=0.0, le=1.0)
    neuroticism: float = Field(default=0.5, ge=0.0, le=1.0)

    def summary(self) -> str:
        def level(v: float) -> str:
            if v >= 0.7:
                return "高"
            if v <= 0.3:
                return "低"
            return "中"

        return (
            f"开放性{level(self.openness)}、尽责性{level(self.conscientiousness)}、"
            f"外向性{level(self.extraversion)}、宜人性{level(self.agreeableness)}、"
            f"神经质{level(self.neuroticism)}"
        )


class RolePersona(BaseModel):
    archetype: RoleArchetype
    big_five: BigFivePersona = Field(default_factory=BigFivePersona)
    value_preferences: list[str] = Field(default_factory=list)
    behavior_notes: str = ""
    speech_style: str = ""

    @classmethod
    def matchmaker_default(cls) -> RolePersona:
        return cls(
            archetype=RoleArchetype.NEUTRAL,
            big_five=BigFivePersona(
                openness=0.3,
                conscientiousness=0.95,
                extraversion=0.25,
                agreeableness=0.5,
                neuroticism=0.1,
            ),
            value_preferences=["Rule of contract", "Fairness", "Pace control"],
            behavior_notes="面无表情，话不多但句句在点上；把控节奏，不偏袒任何一方。",
            speech_style="简短、冷静、像念流程",
        )

    @classmethod
    def parents_default(cls, side: str = "male") -> RolePersona:
        return cls(
            archetype=RoleArchetype.PROFESSIONAL,
            big_five=BigFivePersona(
                openness=0.45,
                conscientiousness=0.8,
                extraversion=0.55,
                agreeableness=0.4,
                neuroticism=0.35,
            ),
            value_preferences=["Security: family", "Face", "Experience"],
            behavior_notes="老练世故，懂人情；会用土办法试探对方；有刻骨铭心的婚姻经历但不轻易全说。",
            speech_style="语重心长、偶尔叹气、爱举身边例子",
        )

    @classmethod
    def party_default(cls, side: str = "male", emotional: bool = True) -> RolePersona:
        n = 0.6 if emotional else 0.35
        return cls(
            archetype=RoleArchetype.SOCIAL,
            big_five=BigFivePersona(
                openness=0.6,
                conscientiousness=0.35,
                extraversion=0.5,
                agreeableness=0.55,
                neuroticism=n,
            ),
            value_preferences=["Romance", "Autonomy", "Face"],
            behavior_notes="恋爱经验不多，容易紧张、害羞或嘴硬；说话偏年轻人风格。",
            speech_style="口语化、有时结巴、偶尔网络用语",
        )


DEFAULT_PERSONAS: dict[str, RolePersona] = {
    "matchmaker": RolePersona.matchmaker_default(),
    "male": RolePersona.party_default("male", emotional=True),
    "female": RolePersona.party_default("female", emotional=True),
    "male_parents": RolePersona.parents_default("male"),
    "female_parents": RolePersona.parents_default("female"),
}
