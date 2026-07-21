"""阶段教练 — 目标窗口 ± 容差控场，饱满展开而非越早越好。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from lover_graph.constraints import compute_budget, get_constraints
from lover_graph.graph.state import SessionState
from lover_graph.harness.phase_schedule import (
    PhasePaceStatus,
    evaluate_phase_pace,
    format_phase_schedule_table,
)
from lover_graph.schemas.trial_constraints import UrgencyLevel

PHASE_ORDER = ["investigation", "evidence", "debate", "closing"]

PHASE_TRANSITION_HINTS = {
    "investigation": "法庭调查已饱满：请归纳争议焦点，宣布「法庭调查结束，现在进入举证质证阶段」。",
    "evidence": "举证质证已饱满：请归纳证据争点，宣布「现在进入法庭辩论阶段」。",
    "debate": "法庭辩论已饱满：请归纳分歧，宣布进入最后陈述阶段。",
    "closing": "最后陈述完毕：请宣布休庭并设置 end_session=true。",
}

PHASE_HOLD_HINTS = {
    "investigation": "调查尚未饱满：继续要求双方陈述、追问关键事实，**勿**提前进入举证。",
    "evidence": "举证质证尚未饱满：继续组织出示证据、质证，**勿**跳过辩论。",
    "debate": "辩论尚未饱满：引导双方围绕争点充分辩论，**勿**过早休庭。",
    "closing": "继续完成最后陈述程序。",
}


class PhaseCoachResult(BaseModel):
    current_phase: str
    budget_mode: str = "matchmaker_turns"
    phase_pace_status: str = "in_band"
    phase_matchmaker_used: int = 0
    phase_matchmaker_budget: int = 0
    phase_matchmaker_min: int = 0
    phase_matchmaker_max: int = 0
    phase_word_used: int = 0
    phase_word_budget: int = 0
    phase_word_min: int = 0
    phase_word_max: int = 0
    phase_minutes_used: float = 0.0
    phase_minutes_target: float = 0.0
    phase_urgency: str = "green"
    phase_progress_ratio: float = 0.0
    triggered_skills: list[str] = Field(default_factory=list)
    triggered_tools: list[str] = Field(default_factory=list)
    coach_message: str = ""
    suggest_phase_advance: bool = False
    forbid_phase_advance: bool = False
    force_advance_phase: bool = False
    next_phase: str | None = None
    global_urgency: str = "green"


def _next_phase(current: str) -> str | None:
    try:
        i = PHASE_ORDER.index(current)
    except ValueError:
        return None
    if i + 1 < len(PHASE_ORDER):
        return PHASE_ORDER[i + 1]
    return None


def run_phase_coach(state: SessionState) -> PhaseCoachResult:
    c = get_constraints(state)
    global_snap = compute_budget(state)
    pace = evaluate_phase_pace(state, c)
    current = pace.phase
    w = pace.window

    skills: list[str] = []
    tools: list[str] = ["session_clock", "phase_schedule"]
    messages: list[str] = [pace.coach_hint]
    suggest_advance = False
    forbid_advance = False
    force_advance = False
    nxt = None
    phase_urgency = UrgencyLevel.GREEN

    if pace.status == PhasePaceStatus.UNDERFILLED:
        phase_urgency = UrgencyLevel.GREEN
        forbid_advance = True
        skills.extend(["phase_pace_hold", "pace_control"])
        messages.append(PHASE_HOLD_HINTS.get(current, "继续本阶段，勿过早转段。"))
    elif pace.status == PhasePaceStatus.IN_BAND:
        skills.extend(["phase_pace_fill", "pace_control"])
        messages.append("节奏正常：使本阶段内容充实，匹配分配时长与法官发言次数。")
    elif pace.status == PhasePaceStatus.APPROACHING:
        phase_urgency = UrgencyLevel.YELLOW
        suggest_advance = True
        skills.extend(["phase_pace_warn", "pace_control"])
        messages.append(PHASE_TRANSITION_HINTS.get(current, "准备适时转段。"))
    elif pace.status == PhasePaceStatus.OVERDUE:
        phase_urgency = UrgencyLevel.RED
        suggest_advance = True
        force_advance = True
        skills.extend(["phase_transition", "pace_control"])
        nxt = _next_phase(current)
        messages.append(PHASE_TRANSITION_HINTS.get(current, "必须转段。"))

    if global_snap.must_close_soon and current != "closing" and not forbid_advance:
        if pace.status != PhasePaceStatus.UNDERFILLED:
            skills.append("closing_prep")
            messages.append("【全局】整体时间趋紧，在当前阶段要点完成后进入下一阶段，仍须走完 debate→closing。")

    return PhaseCoachResult(
        current_phase=current,
        budget_mode=c.budget_mode.value,
        phase_pace_status=pace.status.value,
        phase_matchmaker_used=pace.matchmaker_used,
        phase_matchmaker_budget=w.target_matchmaker_turns,
        phase_matchmaker_min=w.min_matchmaker_turns,
        phase_matchmaker_max=w.max_matchmaker_turns,
        phase_word_used=pace.words_used,
        phase_word_budget=w.target_words,
        phase_word_min=w.min_words,
        phase_word_max=w.max_words,
        phase_minutes_used=pace.minutes_used,
        phase_minutes_target=w.target_minutes,
        phase_urgency=phase_urgency.value,
        phase_progress_ratio=pace.progress_in_band,
        triggered_skills=list(dict.fromkeys(skills)),
        triggered_tools=list(dict.fromkeys(tools)),
        coach_message="\n".join(messages),
        suggest_phase_advance=suggest_advance,
        forbid_phase_advance=forbid_advance,
        force_advance_phase=force_advance,
        next_phase=nxt,
        global_urgency=global_snap.urgency.value,
    )


def format_coach_schedule_block(constraints=None) -> str:
    from lover_graph.constraints import get_constraints

    if constraints is None:
        from lover_graph.schemas.trial_constraints import SessionConstraints

        constraints = SessionConstraints()
    return format_phase_schedule_table(constraints)
