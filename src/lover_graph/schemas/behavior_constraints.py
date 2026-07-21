"""角色行为与外置纪律参数 — 可进 context / tools / skills。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from lover_graph.schemas.trial_constraints import BudgetMode


class DisciplineDemo(BaseModel):
    """演示用 scripted 违规发言（跳过 LLM，省 token）。"""

    enabled: bool = Field(default=False, description="是否启用演示台词注入（默认关，见 discipline_demo.json）")
    role: str = Field(default="female", description="角色：male | female | …")
    speech_index: int = Field(default=3, description="该角色第几次发言时注入")
    text: str = Field(default="我草泥马！", description="注入的完整发言文本")
    prefer_party_over_lawyer: bool = Field(
        default=False,
        description="演示：目标当事人未满 speech_index 前，将本方可发言轮次强制路由给本人",
    )


class BehaviorConstraints(BaseModel):
    """庭审行为约束（拓展参数）。"""

    # 法官纪律权
    matchmaker_warning_limit: int = Field(
        default=2,
        description="对同一当事人违规的默认提醒次数，超限可截断发言",
    )
    matchmaker_can_interrupt_parties: bool = Field(
        default=True,
        description="法官是否有权截断原告/被告发言（通过 discipline 工具）",
    )
    interrupt_duration_turns: int = Field(
        default=1,
        description="截断后该角色被禁言轮数",
    )

    # 社会人（当事人）
    party_may_insult: bool = Field(default=True, description="当事人可能出现辱骂等过激言辞")
    party_may_disobey_matchmaker: bool = Field(default=True, description="当事人可能不听指挥、插话")
    party_may_cry_or_breakdown: bool = Field(default=True, description="允许情绪崩溃式表达")

    # 律师
    lawyer_must_obey_matchmaker: bool = Field(default=True)
    lawyer_forbid_insult: bool = Field(default=True)
    lawyer_forbid_disobey: bool = Field(default=True)

    # 法官
    matchmaker_must_stay_neutral: bool = Field(default=True)
    matchmaker_forbid_emotional_outburst: bool = Field(default=True)

    # 情绪输出
    emotion_per_turn: bool = Field(
        default=True,
        description="每轮由模型生成 emotion 向量写入 DialogueTurn",
    )
    emotion_dimensions: list[str] = Field(
        default_factory=lambda: [
            "anger",
            "anxiety",
            "sadness",
            "defensiveness",
            "confidence",
            "distress",
        ],
    )

    # 人设驱动
    enforce_big_five: bool = Field(default=True, description="发言须符合大五人格")
    enforce_value_alignment: bool = Field(default=True, description="立场须符合价值偏好")

    discipline_demo: DisciplineDemo | None = Field(
        default_factory=DisciplineDemo,
        description="演示：指定角色第 N 次发言注入违规台词",
    )


class SimulationDefaults(BaseModel):
    """全局默认外置参数（可被场景/CLI 覆盖）。"""

    max_rounds: int = Field(default=25, description="法官发言次数上限（一次审判员发言=一次）")
    budget_mode: BudgetMode = Field(
        default=BudgetMode.MATCHMAKER_TURNS,
        description="预算维度：默认 matchmaker_turns；time 时以词数/时长为准",
    )
    duration_minutes: float = Field(default=5.0, description="budget_mode=time 时的默认庭审时长（分钟）")
    words_per_minute: int = Field(default=200, description="语速，用于 count↔时长")
    random_scenario: bool = Field(default=True, description="入口默认随机生成背景")
    random_seed: int | None = Field(default=None, description="随机种子；None 则每次不同")
    male_has_lawyer: bool = Field(default=True)
    female_has_lawyer: bool = Field(default=True)

    behavior: BehaviorConstraints = Field(default_factory=BehaviorConstraints)

    def derived_word_count_limit(self) -> int:
        return int(self.duration_minutes * self.words_per_minute)

    def budget_synopsis(self) -> str:
        if self.budget_mode == BudgetMode.MATCHMAKER_TURNS:
            return f"按法官发言轮数控场：共 {self.max_rounds} 次（各阶段 ±{2} 次窗口）。"
        return f"按时长控场：约 {self.duration_minutes} 分钟（各阶段 ±容差窗口）。"

    def to_trial_constraints_kwargs(self) -> dict:
        base = {
            "budget_mode": self.budget_mode,
            "words_per_minute": self.words_per_minute,
        }
        if self.budget_mode == BudgetMode.MATCHMAKER_TURNS:
            base["max_rounds"] = self.max_rounds
            base["word_count_limit"] = self.derived_word_count_limit()
        else:
            base["word_count_limit"] = self.derived_word_count_limit()
            from lover_graph.constraints.budget import INACTIVE_MAX_ROUNDS

            base["max_rounds"] = INACTIVE_MAX_ROUNDS
        return base
