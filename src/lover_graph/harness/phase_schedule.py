"""分阶段目标窗口 — 默认按法官发言次数饱满展开，非越早越好。"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from lover_graph.graph.state import SessionState
from lover_graph.harness.phase_budget import count_matchmaker_turns_in_phase, count_words_in_phase
from lover_graph.schemas.trial_constraints import BudgetMode, SessionConstraints

DYNAMIC_PHASES = ["investigation", "evidence", "debate", "closing"]


class PhasePaceStatus(str, Enum):
    """当前阶段节奏状态（相对目标窗口）。"""

    UNDERFILLED = "underfilled"
    IN_BAND = "in_band"
    APPROACHING = "approaching"
    OVERDUE = "overdue"


class PhaseWindow(BaseModel):
    """单阶段目标窗口。"""

    phase: str
    target_matchmaker_turns: int
    min_matchmaker_turns: int
    max_matchmaker_turns: int
    # 以下仅 budget_mode=time 时用于节奏判定；matchmaker_turns 模式下仅作参考展示
    target_words: int = 0
    min_words: int = 0
    max_words: int = 0
    target_minutes: float = 0.0
    min_minutes: float = 0.0
    max_minutes: float = 0.0
    tolerance_matchmaker_turns: int = 2
    tolerance_minutes: float = 0.0


class PhasePaceSnapshot(BaseModel):
    phase: str
    status: PhasePaceStatus
    budget_mode: str = "matchmaker_turns"
    matchmaker_used: int = 0
    words_used: int = 0
    minutes_used: float = 0.0
    window: PhaseWindow
    progress_in_band: float = Field(
        description="0=刚达下沿，1=达目标，>1 趋近或超过上沿",
    )
    coach_hint: str = ""


def _phase_targets(c: SessionConstraints) -> dict[str, PhaseWindow]:
    tol_j = c.phase_matchmaker_tolerance
    tol_m = c.phase_minute_tolerance
    windows: dict[str, PhaseWindow] = {}

    for ph in DYNAMIC_PHASES:
        j_target = c.phase_matchmaker_turn_budget.get(ph, 6)
        w_target = max(50, int(c.word_count_limit * c.phase_word_budget_ratio.get(ph, 0.25)))
        m_target = w_target / max(c.words_per_minute, 1)

        windows[ph] = PhaseWindow(
            phase=ph,
            target_matchmaker_turns=j_target,
            min_matchmaker_turns=max(1, j_target - tol_j),
            max_matchmaker_turns=j_target + tol_j,
            target_words=w_target,
            min_words=max(30, int(w_target * (1 - c.phase_word_tolerance_ratio))),
            max_words=int(w_target * (1 + c.phase_word_tolerance_ratio)),
            target_minutes=round(m_target, 1),
            min_minutes=round(max(0.5, m_target - tol_m), 1),
            max_minutes=round(m_target + tol_m, 1),
            tolerance_matchmaker_turns=tol_j,
            tolerance_minutes=tol_m,
        )
    return windows


def get_phase_window(c: SessionConstraints, phase: str) -> PhaseWindow:
    return _phase_targets(c).get(
        phase,
        PhaseWindow(
            phase=phase,
            target_matchmaker_turns=6,
            min_matchmaker_turns=4,
            max_matchmaker_turns=8,
            target_words=200,
            min_words=160,
            max_words=240,
            target_minutes=1.0,
            min_minutes=0.5,
            max_minutes=1.5,
        ),
    )


def _evaluate_by_matchmaker_turns(j_used: int, w: PhaseWindow) -> tuple[PhasePaceStatus, float, str]:
    j_progress = j_used / w.target_matchmaker_turns if w.target_matchmaker_turns else 0

    if j_used < w.min_matchmaker_turns:
        status = PhasePaceStatus.UNDERFILLED
        hint = (
            f"本阶段尚未饱满（法官发言 {j_used}/{w.min_matchmaker_turns} 次下限，"
            f"目标 {w.target_matchmaker_turns} 次）。"
            "**禁止过早转段**；请继续发问、归纳争点、组织举证/辩论，使本阶段法官发言达到计划轮数。"
        )
    elif j_used > w.max_matchmaker_turns:
        status = PhasePaceStatus.OVERDUE
        hint = (
            f"本阶段已超过计划窗口上沿（法官 ≤{w.max_matchmaker_turns} 次，目标 {w.target_matchmaker_turns} 次）。"
            "**必须**归纳并宣布进入下一阶段。"
        )
    elif j_progress >= 0.85:
        status = PhasePaceStatus.APPROACHING
        hint = (
            f"接近本阶段计划节点（法官 {j_used}/{w.target_matchmaker_turns} 次）。"
            "请归纳本阶段要点，**适时**宣布转段，不必再拖延，也勿提前跳段。"
        )
    else:
        status = PhasePaceStatus.IN_BAND
        hint = (
            f"本阶段在计划窗口内（法官 {j_used}/{w.target_matchmaker_turns} 次目标，"
            f"窗口 {w.min_matchmaker_turns}～{w.max_matchmaker_turns} 次）。"
            "按程序稳步推进，使庭审**填满**本阶段轮数而非赶早结束。"
        )

    band_progress = 0.0
    if w.target_matchmaker_turns:
        band_progress = (j_used - w.min_matchmaker_turns) / max(1, w.target_matchmaker_turns - w.min_matchmaker_turns)

    return status, round(band_progress, 2), hint


def _evaluate_by_time(words_used: int, minutes_used: float, w: PhaseWindow) -> tuple[PhasePaceStatus, float, str]:
    w_progress = words_used / w.target_words if w.target_words else 0
    m_progress = minutes_used / w.target_minutes if w.target_minutes else 0
    lead = max(w_progress, m_progress)

    underfilled = words_used < w.min_words and minutes_used < w.min_minutes
    overdue = words_used > w.max_words or minutes_used > w.max_minutes

    if underfilled and not overdue:
        status = PhasePaceStatus.UNDERFILLED
        hint = (
            f"本阶段尚未饱满（词数 {words_used}/{w.min_words}，约 {minutes_used}/{w.min_minutes} 分钟）。"
            "**禁止过早转段**；请继续充实本阶段内容至计划时长。"
        )
    elif overdue:
        status = PhasePaceStatus.OVERDUE
        hint = (
            f"本阶段已超过计划窗口上沿（词数 ≤{w.max_words}，约 ≤{w.max_minutes} 分钟）。"
            "**必须**归纳并宣布进入下一阶段。"
        )
    elif lead >= 0.85:
        status = PhasePaceStatus.APPROACHING
        hint = (
            f"接近本阶段计划节点（约 {w.target_minutes} 分钟 / {w.target_words} 字）。"
            "请归纳本阶段要点，**适时**宣布转段。"
        )
    else:
        status = PhasePaceStatus.IN_BAND
        hint = (
            f"本阶段在计划窗口内（词数 {words_used}/{w.target_words}，约 {minutes_used}/{w.target_minutes} 分钟）。"
            "按程序稳步推进，使庭审**填满**本阶段时长而非赶早结束。"
        )

    band_progress = 0.0
    if w.target_words:
        band_progress = (words_used - w.min_words) / max(1, w.target_words - w.min_words)

    return status, round(band_progress, 2), hint


def evaluate_phase_pace(state: SessionState, constraints: SessionConstraints | None = None) -> PhasePaceSnapshot:
    from lover_graph.constraints import get_constraints

    c = constraints or get_constraints(state)
    phase = state.get("current_phase")
    if hasattr(phase, "value"):
        phase = phase.value
    if phase == "opening":
        phase = "investigation"

    w = get_phase_window(c, phase)
    j_used = count_matchmaker_turns_in_phase(state, phase)
    words_used = count_words_in_phase(state, phase)
    minutes_used = round(words_used / max(c.words_per_minute, 1), 2)

    if c.budget_mode == BudgetMode.TIME:
        status, band_progress, hint = _evaluate_by_time(words_used, minutes_used, w)
    else:
        status, band_progress, hint = _evaluate_by_matchmaker_turns(j_used, w)

    return PhasePaceSnapshot(
        phase=phase,
        status=status,
        budget_mode=c.budget_mode.value,
        matchmaker_used=j_used,
        words_used=words_used,
        minutes_used=minutes_used,
        window=w,
        progress_in_band=band_progress,
        coach_hint=hint,
    )


def format_phase_schedule_table(c: SessionConstraints) -> str:
    mode = c.budget_mode.value
    if c.budget_mode == BudgetMode.TIME:
        header = "【分阶段目标窗口】（按词数/时长，±容差内饱满展开）"
    else:
        header = "【分阶段目标窗口】（按法官发言次数，±容差内饱满展开）"
    lines = [header, f"预算维度：{mode}", ""]
    for ph, w in _phase_targets(c).items():
        if c.budget_mode == BudgetMode.TIME:
            lines.append(
                f"- {ph}：词数 {w.min_words}～{w.max_words}（目标 {w.target_words}），"
                f"约 {w.min_minutes}～{w.max_minutes} 分钟（目标 {w.target_minutes}）"
            )
        else:
            lines.append(
                f"- {ph}：法官 {w.min_matchmaker_turns}～{w.max_matchmaker_turns} 次（目标 {w.target_matchmaker_turns}）"
            )
    return "\n".join(lines)
