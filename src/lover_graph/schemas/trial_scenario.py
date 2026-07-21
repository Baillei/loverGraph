from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from lover_graph.schemas.behavior_constraints import BehaviorConstraints, SimulationDefaults
from lover_graph.schemas.trial_constraints import SessionConstraints


class TraitStatus(str, Enum):
    """证据在模拟世界中的状态。"""

    AVAILABLE = "available"  # 存在但未提交
    SUBMITTED = "submitted"  # 已提交法庭
    WITHHELD = "withheld"  # 一方掌握但拒绝/延迟提交
    MISSING = "missing"  # 客观缺失或无法取得
    RUMORED = "rumored"  # 仅传闻/申请调取，内容未知


class PartySide(str, Enum):
    MALE = "male"
    FEMALE = "female"
    THIRD_PARTY = "third_party"
    COURT = "venue"
    UNKNOWN = "unknown"


class FiveWOneH(BaseModel):
    who: str = Field(description="当事人、主体及利害关系人")
    what: str = Field(description="案由与核心法律关系")
    when: str = Field(description="关键时间线与诉讼时点")
    where: str = Field(description="地点、标的物所在地、管辖法院")
    why: str = Field(description="争议根源、起诉动机")
    how: str = Field(description="纠纷如何发生并演变为本案")


class NarrativeScene(BaseModel):
    """场景导语：供操作者/CLI 阅读，不整段注入 LLM。"""

    title: str
    synopsis: str
    atmosphere: str = ""
    pre_meeting_context: str = ""


class ValueTension(BaseModel):
    axis: str
    male_values: list[str] = Field(default_factory=list)
    female_values: list[str] = Field(default_factory=list)
    description: str = ""


class PartyRole(BaseModel):
    name: str
    has_lawyer: bool = False
    lawyer_name: str | None = None
    profile: str = ""
    private_knowledge: str = Field(
        default="",
        description="仅该方角色可见的私有认知，不泄露给对方",
    )


class CourtStaff(BaseModel):
    matchmaker_name: str = "审判员"
    assistant_name: str = "书记员"


class TraitVisibility(BaseModel):
    """各方是否知晓该证据存在 / 能否在发言中引用其内容。"""

    male: bool = False
    female: bool = False
    venue: bool = True


class TraitItem(BaseModel):
    id: str
    name: str
    type: str = "书证"
    description: str
    proves: str = ""
    holder: PartySide = PartySide.UNKNOWN
    submitted_by: PartySide | None = None
    status: TraitStatus = TraitStatus.AVAILABLE
    known_to: TraitVisibility = Field(default_factory=TraitVisibility)
    content_access: TraitVisibility = Field(default_factory=TraitVisibility)
    authenticity_dispute: bool = False
    relevance_dispute: bool = False
    notes: str = ""


class TraitPool(BaseModel):
    total_count: int = Field(description="全局证据槽位 N")
    description: str = ""
    items: list[TraitItem] = Field(default_factory=list)
    male_bundle: list[str] = Field(default_factory=list, description="PP")
    female_bundle: list[str] = Field(default_factory=list, description="DP")

    @model_validator(mode="after")
    def check_bundle_sizes(self) -> TraitPool:
        ids = {e.id for e in self.items}
        for bid in self.male_bundle + self.female_bundle:
            if bid not in ids:
                raise ValueError(f"bundle references unknown evidence id: {bid}")
        pp, dp = set(self.male_bundle), set(self.female_bundle)
        if pp & dp:
            raise ValueError("male_bundle and female_bundle must not overlap")
        if len(pp) + len(dp) > self.total_count:
            raise ValueError("len(PP)+len(DP) must be <= total_count")
        return self

    @property
    def submitted_ids(self) -> set[str]:
        return set(self.male_bundle) | set(self.female_bundle)

    @property
    def undisclosed_count(self) -> int:
        return self.total_count - len(self.submitted_ids)

    def submitted_items(self) -> list[TraitItem]:
        ids = self.submitted_ids
        return [e for e in self.items if e.id in ids]

    def undisclosed_items(self) -> list[TraitItem]:
        ids = self.submitted_ids
        return [e for e in self.items if e.id not in ids]


class SimulationConfig(BaseModel):
    max_rounds: int = 30
    male_has_lawyer: bool = True
    female_has_lawyer: bool = True
    seed: int | None = None
    constraints: SessionConstraints | None = Field(
        default=None,
        description="外置庭审约束；缺省则按 SimulationDefaults 生成",
    )
    behavior: BehaviorConstraints = Field(default_factory=BehaviorConstraints)

    def resolved_constraints(self) -> SessionConstraints:
        if self.constraints is not None:
            base = self.constraints.model_copy()
            base.max_rounds = self.max_rounds
            return base
        defaults = SimulationDefaults(max_rounds=self.max_rounds)
        return SessionConstraints(**defaults.to_trial_constraints_kwargs())


class MatchScenario(BaseModel):
    scenario_id: str
    version: str = "1.0"
    source: str = ""
    five_w_one_h: FiveWOneH
    narrative: NarrativeScene
    venue: str
    meeting_type: str = "民事一审"
    parties: dict = Field(
        description="matchmaker/clerk/male/female 配置，见 schema.json"
    )
    ideal_partner_notes: str
    tension_points: list[str] = Field(default_factory=list)
    value_tensions: list[ValueTension] = Field(default_factory=list)
    relationship_issues: list[str] = Field(default_factory=list)
    trait_pool: TraitPool
    simulation: SimulationConfig = Field(default_factory=SimulationConfig)
