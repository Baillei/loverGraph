"""Trial budget tracking and enforcement."""

from __future__ import annotations

import re

from lover_graph.constraints.budget import rounds_enforced, time_enforced
from lover_graph.schemas import Phase, Role
from lover_graph.schemas.trial_constraints import BudgetSnapshot, SessionConstraints, UrgencyLevel
from lover_graph.graph.state import SessionState

PHASE_ORDER = [
    Phase.OPENING,
    Phase.INVESTIGATION,
    Phase.EVIDENCE,
    Phase.DEBATE,
    Phase.CLOSING,
]


def count_speech_units(text: str) -> int:
    """庭审语速统计：汉字按字计，连续英文按词计，数字按个计。"""
    if not text:
        return 0
    chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
    english = len(re.findall(r"[a-zA-Z]+", text))
    digits = len(re.findall(r"\d+", text))
    return chinese + english + digits


def count_matchmaker_turns(state: SessionState) -> int:
    """统计法官发言次数（含固定开庭/收尾程序中的审判员台词）。"""
    return sum(1 for d in state.get("dialogues", []) if d.role == Role.MATCHMAKER)


def get_constraints(state: SessionState) -> SessionConstraints:
    scenario = state.get("scenario")
    if scenario and hasattr(scenario, "simulation"):
        return scenario.simulation.resolved_constraints()
    case = state["session_input"]
    return SessionConstraints(max_rounds=case.max_rounds)


def compute_budget(state: SessionState, constraints: SessionConstraints | None = None) -> BudgetSnapshot:
    c = constraints or get_constraints(state)
    dialogues = state.get("dialogues", [])
    words = sum(count_speech_units(d.text) for d in dialogues)
    matchmaker_rounds = count_matchmaker_turns(state)
    current = state.get("current_phase", Phase.OPENING)
    if isinstance(current, Phase):
        current_phase = current.value
    else:
        current_phase = str(current)

    phases_seen = sorted({d.phase.value for d in dialogues}, key=lambda p: _phase_index(p))
    required = [p for p in c.required_phases if p != "verdict"]
    phases_missing = [p for p in required if p not in phases_seen]

    word_ratio = words / c.word_count_limit if c.word_count_limit else 0
    round_ratio = matchmaker_rounds / c.max_rounds if c.max_rounds else 0

    if c.budget_mode.value == "time":
        ratio = word_ratio
        enforce_words = True
        enforce_rounds = False
    else:
        ratio = round_ratio
        enforce_words = False
        enforce_rounds = True

    urgency = UrgencyLevel.GREEN
    should_accelerate = False
    must_close_soon = False
    force_close_now = False
    termination_reason = None

    remaining_matchmaker_rounds = max(0, c.max_rounds - matchmaker_rounds)
    remaining_words = max(0, c.word_count_limit - words)

    if rounds_enforced(c) and (remaining_matchmaker_rounds <= 3):
        must_close_soon = True
        if urgency == UrgencyLevel.GREEN:
            urgency = UrgencyLevel.YELLOW
    if time_enforced(c) and (remaining_words <= 120):
        must_close_soon = True
        if urgency == UrgencyLevel.GREEN:
            urgency = UrgencyLevel.YELLOW

    hit_hard = ratio >= c.hard_budget_ratio
    if rounds_enforced(c) and (remaining_matchmaker_rounds <= 1 or matchmaker_rounds >= c.max_rounds):
        hit_hard = True
    if time_enforced(c) and words >= c.word_count_limit:
        hit_hard = True

    if hit_hard:
        urgency = UrgencyLevel.RED
        must_close_soon = True
        force_close_now = True
        if c.auto_force_close_at_hard_limit:
            if rounds_enforced(c) and matchmaker_rounds >= c.max_rounds:
                termination_reason = "matchmaker_round_limit"
            elif time_enforced(c) and words >= c.word_count_limit:
                termination_reason = "word_limit"
            else:
                termination_reason = "budget_hard"
    elif ratio >= c.soft_budget_ratio:
        urgency = UrgencyLevel.YELLOW
        should_accelerate = True

    minutes_used = words / max(c.words_per_minute, 1)
    guidance = _build_matchmaker_guidance(
        c, words, matchmaker_rounds, current_phase, phases_missing, urgency, must_close_soon, force_close_now
    )

    return BudgetSnapshot(
        word_count_used=words,
        word_count_limit=c.word_count_limit,
        words_per_minute=c.words_per_minute,
        rounds_used=matchmaker_rounds,
        max_rounds=c.max_rounds,
        phases_seen=phases_seen,
        phases_missing=phases_missing,
        current_phase=current_phase,
        urgency=urgency,
        should_accelerate=should_accelerate,
        must_close_soon=must_close_soon,
        force_close_now=force_close_now,
        termination_reason=termination_reason,
        estimated_minutes_used=round(minutes_used, 1),
        estimated_minutes_limit=round(c.estimated_minutes_limit, 1),
        tension_points_total=len(state["session_input"].tension_points),
        matchmaker_guidance=guidance,
    )


def _phase_index(phase_value: str) -> int:
    try:
        return PHASE_ORDER.index(Phase(phase_value))
    except ValueError:
        return 99


def _can_force_close(phases_seen: list[str], c: SessionConstraints) -> bool:
    """硬停前须满足最低程序完备性。"""
    minimal = {"opening", "investigation", "closing"}
    if c.require_final_statements:
        minimal.add("closing")
    # debate/evidence 可在预算紧时 abbreviated，但 closing 必须有
    seen = set(phases_seen)
    if "closing" in seen:
        return True
    # 若尚未 closing，但已完成 opening+investigation，允许强制进入收尾
    return minimal.issubset(seen) or ("opening" in seen and "investigation" in seen)


def _build_matchmaker_guidance(
    c: SessionConstraints,
    words: int,
    matchmaker_rounds: int,
    current_phase: str,
    phases_missing: list[str],
    urgency: UrgencyLevel,
    must_close_soon: bool,
    force_close_now: bool,
) -> str:
    lines = [
        f"预算维度：{c.budget_mode.value}（{'法官发言轮数' if rounds_enforced(c) else '词数/时长'}）",
    ]
    if rounds_enforced(c):
        lines.append(f"法官发言 {matchmaker_rounds}/{c.max_rounds} 次（剩余 {max(0, c.max_rounds - matchmaker_rounds)} 次）")
    if time_enforced(c):
        lines.append(
            f"词数 {words}/{c.word_count_limit}（剩余约 {max(0, c.word_count_limit - words)} 字，"
            f"约 {max(0, c.word_count_limit - words) / max(c.words_per_minute, 1):.1f} 分钟）"
        )
    if not rounds_enforced(c):
        lines.append(f"法官发言参考 {matchmaker_rounds} 次（本模式不限制轮数）")
    if not time_enforced(c):
        lines.append(f"词数参考 {words} 字（本模式不限制词数）")
    lines.append(f"当前阶段：{current_phase}")
    if phases_missing:
        lines.append(f"尚未经历阶段：{', '.join(phases_missing)}")
    cap = c.phase_round_soft_caps.get(current_phase)
    if cap:
        lines.append(f"本阶段建议不超过 {cap} 轮，超出应推进程序")

    if urgency == UrgencyLevel.YELLOW:
        lines.append("【yellow】接近预算，请压缩发问、减少重复，尽快推进至未经历阶段。")
    if must_close_soon:
        lines.append("【red】预算紧迫：优先完成举证质证/辩论要点，随后进入最后陈述并设置 end_session=true。")
    if force_close_now:
        if c.budget_mode.value == "matchmaker_turns":
            lines.append(
                "【强制收尾】法官发言次数即将用尽：必须立即进入最后陈述→休庭→宣判，"
                "设置 end_session=true，系统保证产出判决结果。"
            )
        else:
            lines.append(
                "【强制收尾】词数/时长即将用尽：必须立即进入最后陈述→休庭→宣判，"
                "设置 end_session=true，系统保证产出判决结果。"
            )
    lines.append(
        "完备性要求：庭审须经历 opening→…→closing→verdict；禁止无判决结束。"
    )
    return "\n".join(lines)


def format_matchmaker_budget_block(state: SessionState) -> str:
    from lover_graph.tools.session_clock import SessionClock

    snap = compute_budget(state)
    clock = SessionClock().format_for_context(state)
    return (
        "## 庭审预算与程序进度（外置约束）\n\n"
        f"{snap.matchmaker_guidance}\n\n"
        f"{clock}"
    )


def apply_forced_close(state: SessionState) -> dict:
    """硬上限触发时写入状态，路由至 closing。"""
    snap = compute_budget(state)
    update: dict = {
        "next_speaker": "End",
        "current_phase": Phase.CLOSING,
        "saturation_flag": True,
    }
    if snap.termination_reason:
        update["termination"] = snap.termination_reason
    else:
        update["termination"] = "budget_hard"
    return update
