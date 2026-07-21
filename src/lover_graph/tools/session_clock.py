"""Trial countdown tool — 为法官提供结构化庭审倒计时与阶段进度。"""

from __future__ import annotations

from lover_graph.constraints import compute_budget, get_constraints
from lover_graph.graph.state import SessionState
from lover_graph.schemas import Phase

PHASE_ORDER = ["opening", "investigation", "evidence", "debate", "closing", "verdict"]
PHASE_LABELS = {
    "opening": "开庭",
    "investigation": "法庭调查",
    "evidence": "举证质证",
    "debate": "法庭辩论",
    "closing": "最后陈述与休庭",
    "verdict": "宣判",
}


class SessionClock:
    """结构化庭审时钟，供法官 Skills/Tools 调用。"""

    def snapshot(self, state: SessionState) -> dict:
        constraints = get_constraints(state)
        snap = compute_budget(state, constraints)
        current = snap.current_phase
        try:
            idx = PHASE_ORDER.index(current)
        except ValueError:
            idx = 0
        remaining_phases = [p for p in constraints.required_phases if p not in snap.phases_seen]

        remaining_rounds = max(0, snap.max_rounds - snap.rounds_used)
        remaining_words = max(0, snap.word_count_limit - snap.word_count_used)
        remaining_minutes = round(remaining_words / max(snap.words_per_minute, 1), 1)
        hc = state.get("harness_context") or {}

        return {
            "current_phase": current,
            "current_phase_label": PHASE_LABELS.get(current, current),
            "phase_index": idx + 1,
            "phase_total": len(PHASE_ORDER),
            "phases_completed": snap.phases_seen,
            "phases_missing": snap.phases_missing,
            "remaining_phases": remaining_phases,
            "rounds_used": snap.rounds_used,
            "max_rounds": snap.max_rounds,
            "remaining_rounds": remaining_rounds,
            "word_count_used": snap.word_count_used,
            "word_count_limit": snap.word_count_limit,
            "remaining_words": remaining_words,
            "words_per_minute": snap.words_per_minute,
            "minutes_used": snap.estimated_minutes_used,
            "minutes_limit": snap.estimated_minutes_limit,
            "remaining_minutes": remaining_minutes,
            "urgency": snap.urgency.value,
            "must_close_soon": snap.must_close_soon,
            "force_close_now": snap.force_close_now,
            "termination_reason": snap.termination_reason,
            "matchmaker_action_hint": self._action_hint(snap, remaining_rounds, remaining_words, hc),
            "phase_pace_status": hc.get("phase_pace_status"),
        }

    @staticmethod
    def _action_hint(snap, remaining_rounds: int, remaining_words: int, harness: dict | None = None) -> str:
        hc = harness or {}
        pace = hc.get("phase_pace_status")
        if pace == "underfilled":
            return "本阶段未达窗口下沿：继续充实调查/举证/辩论，**禁止过早转段**。"
        if pace == "approaching":
            return "接近本阶段计划节点：归纳要点，适时宣布转段。"
        if pace == "overdue":
            return "已超过本阶段窗口上沿：必须宣布进入下一阶段。"
        if snap.force_close_now or remaining_rounds <= 1:
            return "全局预算将尽：组织最后陈述并设置 end_session=true。"
        if snap.must_close_soon or remaining_rounds <= 3:
            return "全局时间趋紧：在当前阶段要点完成后推进，仍须走完 debate→closing。"
        if pace == "in_band":
            return "本阶段在计划窗口内：稳步推进，使庭审内容**填满**分配时长，勿赶早结束。"
        return "按程序主持，参考 phase_schedule 各阶段目标窗口。"

    def format_for_context(self, state: SessionState) -> str:
        s = self.snapshot(state)
        hc = state.get("harness_context") or {}
        mode = hc.get("budget_mode", "matchmaker_turns")
        lines = [
            "【庭审倒计时 session_clock】",
            f"预算维度：{mode}",
            f"当前阶段：{s['current_phase_label']}（{s['current_phase']}）"
            f" — 进度 {s['phase_index']}/{s['phase_total']}",
            f"已完成阶段：{', '.join(s['phases_completed']) or '无'}",
            f"待完成阶段：{', '.join(s['phases_missing']) or '无'}",
        ]
        if mode == "time":
            lines.append(
                f"全局时长：已用约 {s['minutes_used']} / {s['minutes_limit']} 分钟，"
                f"词数 {s['word_count_used']}/{s['word_count_limit']}"
            )
        else:
            lines.append(
                f"全局法官发言：已用 {s['rounds_used']}/{s['max_rounds']} 次，剩余 {s['remaining_rounds']} 次"
            )
        if hc:
            pace = hc.get("phase_pace_status", "in_band")
            if mode == "time":
                lines.append(
                    f"本阶段窗口：词数 {hc.get('phase_word_min', '?')}～{hc.get('phase_word_max', '?')} "
                    f"（已用 {hc.get('phase_word_used', '?')}），约 "
                    f"{hc.get('phase_minutes_used', '?')}/{hc.get('phase_minutes_target', '?')} 分钟，节奏 {pace}"
                )
            else:
                lines.append(
                    f"本阶段窗口：法官 {hc.get('phase_matchmaker_min', '?')}～{hc.get('phase_matchmaker_max', '?')} 次"
                    f"（已用 {hc.get('phase_matchmaker_used', '?')}，目标 {hc.get('phase_matchmaker_budget', '?')}），"
                    f"节奏 {pace}"
                )
        if mode == "time":
            ref = f"法官发言参考 {s['rounds_used']} 次（本模式不限制轮数）"
        else:
            ref = f"词数参考 {s['word_count_used']} 字（本模式不限制词数）"
        lines.extend(
            [
            ref,
            f"紧迫度：{s['urgency']}"
            + (" | 须尽快收尾" if s["must_close_soon"] else "")
            + (" | 【强制收尾】" if s["force_close_now"] else ""),
            f"节奏建议：{s['matchmaker_action_hint']}",
            ]
        )
        return "\n".join(lines)
