"""当事人/角色基础画像字段（姓名、性别等）。"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"
    UNKNOWN = "unknown"

    def display(self) -> str:
        return {"male": "男", "female": "女", "unknown": "未知"}[self.value]

    def honorific(self) -> str:
        return {"male": "先生", "female": "女士", "unknown": ""}[self.value]


class PartyProfile(BaseModel):
    name: str
    gender: Gender = Gender.UNKNOWN
    age: int | None = None

    def labeled_name(self) -> str:
        if self.gender == Gender.UNKNOWN:
            return self.name
        return f"{self.name}（{self.gender.display()}）"
