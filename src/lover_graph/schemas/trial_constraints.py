"""External trial constraints — extensible budget & completeness rules."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class UrgencyLevel(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class BudgetMode(str, Enum):
    """庭审预算维度：轮数与时间难以同时满足，默认仅按法官发言次数控场。"""

    MATCHMAKER_TURNS = "matchmaker_turns"
    TIME = "time"


class SessionConstraints(BaseModel):
    """外置庭审约束参数（可在场景 JSON 或 CLI 覆盖）。"""

    budget_mode: BudgetMode = Field(
        default=BudgetMode.MATCHMAKER_TURNS,
        description="预算维度：matchmaker_turns=法官发言次数（默认）；time=词数/时长",
    )

    # --- 时长 / 词数（count）---
    word_count_limit: int = Field(
        default=1000,
        description="庭审发言总词数上限（默认5分钟×200字/分）",
    )
    words_per_minute: int = Field(
        default=200,
        description="正常庭审语速（字/词 per 分钟），用于估算时长",
    )

    # --- 轮次 ---
    max_rounds: int = Field(default=25, description="法官发言次数上限（一次审判员发言=一次）")

    # --- 软/硬预算 ---
    soft_budget_ratio: float = Field(
        default=0.80,
        ge=0.5,
        le=0.99,
        description="达到此比例时提醒法官加速（yellow）",
    )
    hard_budget_ratio: float = Field(
        default=0.95,
        ge=0.8,
        le=1.0,
        description="达到此比例时紧迫收尾（red）",
    )

    # --- 程序完备性 ---
    required_phases: list[str] = Field(
        default_factory=lambda: ["opening", "investigation", "evidence", "debate", "closing"],
        description="必须经历的阶段（不含 verdict）",
    )
    min_tension_points_addressed: int = Field(
        default=1,
        description="至少应覆盖的争议焦点数量（由法官引导）",
    )

    # --- 阶段法官发言预算（将 max_rounds 切分到各阶段，用于阶段性控场）---
    phase_matchmaker_turn_budget: dict[str, int] = Field(
        default_factory=lambda: {
            "investigation": 6,
            "evidence": 6,
            "debate": 7,
            "closing": 4,
        },
        description="各阶段法官发言次数预算（opening 多为固定台词不计入）",
    )
    phase_word_budget_ratio: dict[str, float] = Field(
        default_factory=lambda: {
            "investigation": 0.28,
            "evidence": 0.28,
            "debate": 0.28,
            "closing": 0.16,
        },
        description="各阶段词数目标占总词数比例",
    )
    phase_matchmaker_tolerance: int = Field(
        default=2,
        description="各阶段法官发言次数 ± 容差（目标±tol 为窗口；budget_mode=matchmaker_turns 时生效）",
    )
    phase_word_tolerance_ratio: float = Field(
        default=0.15,
        ge=0.05,
        le=0.35,
        description="各阶段词数 ± 比例容差（仅 budget_mode=time 时用于阶段节奏）",
    )
    phase_minute_tolerance: float = Field(
        default=0.5,
        description="各阶段时长（分钟）± 绝对容差（仅 budget_mode=time 时用于阶段节奏）",
    )

    # --- 阶段轮次建议（当事人总轮次参考，法官以 phase_matchmaker_turn_budget 为准）---
    phase_round_soft_caps: dict[str, int] = Field(
        default_factory=lambda: {
            "opening": 3,
            "investigation": 8,
            "evidence": 8,
            "debate": 6,
            "closing": 3,
        },
        description="各阶段建议最大轮次，超出应推进",
    )

    # --- 发言长度 ---
    max_words_per_turn: int = Field(default=600, description="单轮发言词数软上限（提示法官控制）")
    matchmaker_max_words_per_turn: int = Field(default=300, description="法官单轮词数软上限")

    # --- 行为约束 ---
    forbid_interruption_without_closing: bool = Field(
        default=True,
        description="禁止在未进入 closing 且未 end_session 时因预算硬停而截断",
    )
    allow_abbreviated_evidence: bool = Field(
        default=True,
        description="预算紧张时允许简化举证质证，但不可跳过 closing",
    )
    require_final_statements: bool = Field(default=True, description="必须作最后陈述")
    auto_force_close_at_hard_limit: bool = Field(
        default=True,
        description="触及硬上限时自动进入 closing（保证有始有终）",
    )

    # --- 拓展：重复与饱和 ---
    max_same_role_consecutive: int = Field(default=2, description="同一角色连续发言轮次上限")
    repetition_ngram_threshold: float = Field(
        default=0.6,
        description="预留：重复度阈值（后续 validator 使用）",
    )

    @model_validator(mode="after")
    def check_ratios(self) -> SessionConstraints:
        if self.soft_budget_ratio >= self.hard_budget_ratio:
            raise ValueError("soft_budget_ratio must be < hard_budget_ratio")
        return self

    @property
    def soft_word_limit(self) -> int:
        return int(self.word_count_limit * self.soft_budget_ratio)

    @property
    def hard_word_limit(self) -> int:
        return int(self.word_count_limit * self.hard_budget_ratio)

    @property
    def soft_round_limit(self) -> int:
        return int(self.max_rounds * self.soft_budget_ratio)

    @property
    def hard_round_limit(self) -> int:
        return int(self.max_rounds * self.hard_budget_ratio)

    @property
    def estimated_minutes_limit(self) -> float:
        return self.word_count_limit / max(self.words_per_minute, 1)


class BudgetSnapshot(BaseModel):
    """运行时预算快照。"""

    word_count_used: int = 0
    word_count_limit: int = 0
    words_per_minute: int = 200
    rounds_used: int = 0
    max_rounds: int = 0
    phases_seen: list[str] = Field(default_factory=list)
    phases_missing: list[str] = Field(default_factory=list)
    current_phase: str = ""
    urgency: UrgencyLevel = UrgencyLevel.GREEN
    should_accelerate: bool = False
    must_close_soon: bool = False
    force_close_now: bool = False
    termination_reason: str | None = None
    estimated_minutes_used: float = 0.0
    estimated_minutes_limit: float = 0.0
    tension_points_total: int = 0
    matchmaker_guidance: str = ""
    # 分阶段预算（harness）
    phase_matchmaker_used: int = 0
    phase_matchmaker_budget: int = 0
    phase_word_used: int = 0
    phase_word_budget: int = 0
    phase_urgency: str = "green"
