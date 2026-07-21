"""Format harness context for MODEL nodes."""

from __future__ import annotations


def format_harness_block(harness: dict) -> str:
    if not harness:
        return ""
    mode = harness.get("budget_mode", "matchmaker_turns")
    lines = [
        "## Harness 阶段性控场（DETERMINISTIC 节点已计算，请据此思考）",
        "",
        f"预算维度：{mode}",
        harness.get("coach_message", ""),
        "",
        f"- 当前阶段紧迫度：{harness.get('phase_urgency')} | 全局：{harness.get('global_urgency')}",
    ]
    if mode == "time":
        lines.append(
            f"- 本阶段词数：{harness.get('phase_word_used')}/{harness.get('phase_word_budget')} "
            f"（窗口 {harness.get('phase_word_min')}～{harness.get('phase_word_max')}）"
        )
        lines.append(
            f"- 本阶段约 {harness.get('phase_minutes_used')}/{harness.get('phase_minutes_target')} 分钟"
        )
    else:
        lines.append(
            f"- 本阶段法官发言：{harness.get('phase_matchmaker_used')}/{harness.get('phase_matchmaker_budget')} 次"
            f"（窗口 {harness.get('phase_matchmaker_min')}～{harness.get('phase_matchmaker_max')}）"
        )
    lines.append(f"- 已触发技能：{', '.join(harness.get('triggered_skills') or [])}")
    if harness.get("forbid_phase_advance"):
        lines.append("- **禁止转段/休庭**：本阶段尚未达窗口下沿，须继续充实内容。")
    if harness.get("suggest_phase_advance"):
        lines.append("- **建议适时转段**：已接近或达到本阶段计划节点。")
    if harness.get("force_advance_phase"):
        lines.append("- **必须转段**：已超过本阶段窗口上沿。")
    followup = harness.get("discipline_followup")
    if followup:
        lines.append("")
        lines.append(format_discipline_followup_block(followup))
    return "\n".join(lines)


def format_discipline_followup_block(followup: dict) -> str:
    """纪律打断后注入法官 MODEL 的硬约束块。"""
    if not followup:
        return ""
    return "\n".join(
        [
            "## 纪律跟进（post_moderation_coach · 不可忽略）",
            "",
            followup.get("coach_message", ""),
            "",
            f"- 辱骂/违规原话（完整，未播出）：{followup.get('attempted_speech', '')}",
            f"- 已播出（截断前）：{followup.get('broadcast_text', '')}",
            f"- 截断余文：{followup.get('remainder', '')}",
            f"- 当事人：{followup.get('party_name')}（{followup.get('party_role')}）",
            f"- 违规：{', '.join(followup.get('violations') or [])}",
        ]
    )
