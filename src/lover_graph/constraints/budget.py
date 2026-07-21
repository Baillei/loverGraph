"""预算维度互斥 — matchmaker_turns 与 time 二选一，不可同时控场。"""

from __future__ import annotations

from lover_graph.schemas.trial_constraints import BudgetMode, SessionConstraints

# 非激活维度的占位上限（不参与判定，仅避免除零）
INACTIVE_MAX_ROUNDS = 1_000_000
INACTIVE_WORD_LIMIT = 100_000_000


def rounds_enforced(c: SessionConstraints) -> bool:
    return c.budget_mode == BudgetMode.MATCHMAKER_TURNS


def time_enforced(c: SessionConstraints) -> bool:
    return c.budget_mode == BudgetMode.TIME


def normalize_for_mode(c: SessionConstraints) -> SessionConstraints:
    """确保非激活维度不会意外触发硬停。"""
    out = c.model_copy(deep=True)
    if rounds_enforced(out):
        if out.word_count_limit < INACTIVE_WORD_LIMIT:
            # 保留原值作 JSONL 参考；强制收尾逻辑由 enforce_* 开关处理
            pass
    else:
        out.max_rounds = INACTIVE_MAX_ROUNDS
    return out


def active_budget_summary(c: SessionConstraints) -> str:
    if rounds_enforced(c):
        return f"法官发言 {c.max_rounds} 次（±阶段容差 {c.phase_matchmaker_tolerance}）"
    minutes = c.estimated_minutes_limit
    return (
        f"约 {minutes:.1f} 分钟 / {c.word_count_limit} 字"
        f"（±阶段 {c.phase_minute_tolerance} 分钟）"
    )


def validate_budget_inputs(
    *,
    budget_mode: BudgetMode | None,
    max_rounds: int | None,
    word_count: int | None,
    duration_minutes: float | None,
) -> BudgetMode:
    """解析并校验 CLI/场景入口的互斥参数。"""
    has_time = word_count is not None or duration_minutes is not None
    has_rounds = max_rounds is not None

    if budget_mode is None:
        if has_time and has_rounds:
            raise ValueError(
                "不能同时指定 --max-rounds 与 --word-count/--duration-minutes；"
                "请用 --budget-mode matchmaker_turns|time 明确选择一种控场方式"
            )
        if has_time:
            budget_mode = BudgetMode.TIME
        else:
            budget_mode = BudgetMode.MATCHMAKER_TURNS
    elif budget_mode == BudgetMode.MATCHMAKER_TURNS and has_time:
        raise ValueError("matchmaker_turns 模式不可指定 --word-count 或 --duration-minutes")
    elif budget_mode == BudgetMode.TIME and has_rounds:
        raise ValueError("time 模式不可指定 --max-rounds")

    return budget_mode
