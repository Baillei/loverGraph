"""Run skills for a role and return context + tool call logs."""

from __future__ import annotations

from lover_graph.schemas import Phase, Role
from lover_graph.skills.registry import allowed_skills
from lover_graph.tools import TraitDB, ContractRetriever, ProcedureRules
from lover_graph.tools.session_clock import SessionClock


def _build_contract_query(title: str, tension_points: list[str], phase: Phase) -> str:
    parts = [title, phase.value, *tension_points]
    if phase == Phase.EVIDENCE:
        parts.append("条件 信息 展示 归还 五金")
    if phase == Phase.DEBATE:
        parts.append("节奏 家长 边界 违法")
    return " ".join(parts)


def run_skills(
    role: Role,
    phase: Phase,
    session_id: str,
    case_title: str,
    tension_points: list[str],
    round_no: int,
    state: dict | None = None,
) -> tuple[str, list[dict], list[str]]:
    skills = allowed_skills(role)
    if not skills:
        return "", [], []

    contract_retriever = ContractRetriever()
    trait_db = TraitDB()
    procedure = ProcedureRules()

    context_parts: list[str] = []
    tool_calls: list[dict] = []
    skills_used: list[str] = []

    if "session_clock" in skills and state is not None:
        clock = SessionClock()
        clock_text = clock.format_for_context(state)  # type: ignore[arg-type]
        skills_used.append("session_clock")
        context_parts.insert(0, clock_text)
        snap = clock.snapshot(state)  # type: ignore[arg-type]
        tool_calls.append(
            {
                "round": round_no,
                "role": role.value,
                "tool": "session_clock",
                "input": {"phase": phase.value},
                "output_summary": (
                    f"剩余{snap['remaining_rounds']}轮/{snap['remaining_words']}字/"
                    f"{snap['remaining_minutes']}分钟 urgency={snap['urgency']}"
                ),
                "snapshot": snap,
            }
        )

    followup = (state or {}).get("discipline_followup")
    if "post_moderation_coach" in skills and followup:
        from lover_graph.harness.format import format_discipline_followup_block

        skills_used.append("post_moderation_coach")
        context_parts.insert(0, format_discipline_followup_block(followup))
        tool_calls.append(
            {
                "round": round_no,
                "role": role.value,
                "tool": "post_moderation_coach",
                "input": followup.get("broadcast_text"),
                "output_summary": f"coach→{followup.get('party_name')}",
            }
        )

    harness = (state or {}).get("harness_context") or {}
    coach_skills = harness.get("triggered_skills") or []

    if "phase_schedule" in skills and state is not None:
        from lover_graph.constraints import get_constraints
        from lover_graph.harness.phase_schedule import format_phase_schedule_table

        c = get_constraints(state)  # type: ignore[arg-type]
        table = format_phase_schedule_table(c)
        skills_used.append("phase_schedule")
        context_parts.append(table)
        tool_calls.append(
            {
                "round": round_no,
                "role": role.value,
                "tool": "phase_schedule",
                "input": phase.value,
                "output_summary": f"pace={harness.get('phase_pace_status', 'in_band')}",
            }
        )

    if "phase_coach" in skills and harness:
        skills_used.append("phase_coach")
        coach_msg = harness.get("coach_message", "")
        pace = harness.get("phase_pace_status", "in_band")
        block = [
            f"【阶段教练 phase_coach】节奏状态：{pace}（预算维度：{harness.get('budget_mode', 'matchmaker_turns')}）",
            coach_msg,
            "",
        ]
        if harness.get("budget_mode") == "time":
            block.append(
                f"本阶段窗口：词数 {harness.get('phase_word_min')}-{harness.get('phase_word_max')} "
                f"（已用 {harness.get('phase_word_used')}，目标 {harness.get('phase_word_budget')}）"
            )
        else:
            block.append(
                f"本阶段窗口：媒婆 {harness.get('phase_matchmaker_min')}-{harness.get('phase_matchmaker_max')} 次"
                f"（已用 {harness.get('phase_matchmaker_used')}，目标 {harness.get('phase_matchmaker_budget')}）"
            )
        if harness.get("forbid_phase_advance"):
            block.append("**禁止转段/散场**：本阶段尚未饱满。")
        context_parts.insert(0, "\n".join(block))
        tool_calls.append(
            {
                "round": round_no,
                "role": role.value,
                "tool": "phase_coach",
                "input": harness.get("current_phase"),
                "output_summary": f"pace={pace} matchmaker={harness.get('phase_matchmaker_used')}/{harness.get('phase_matchmaker_max')}",
                "harness": harness,
            }
        )
        for extra in coach_skills:
            skills_used.append(extra)

    _PACE_SKILL_HINTS = {
        "phase_pace_hold": "【节奏：保持】本阶段未达下沿，继续互相了解/交换条件，勿赶早转段。",
        "phase_pace_fill": "【节奏：充实】在窗口内稳步推进，让对话匹配本阶段时长。",
        "phase_pace_warn": "【节奏：将满】接近计划节点，归纳本阶段要点，准备适时宣布转段。",
        "phase_transition": "【节奏：转段】已达窗口上沿，必须宣布进入下一阶段。",
        "closing_prep": "【全局】注意整体时间，完成本阶段后进入最终表态。",
    }
    for sk, hint in _PACE_SKILL_HINTS.items():
        if sk in coach_skills:
            context_parts.append(hint)

    if "phase_transition" in coach_skills:
        rules = procedure.format_phase(phase.value)
        nxt = harness.get("next_phase")
        if nxt:
            rules += f"\n\n【转入】{nxt}"
        context_parts.append(f"【阶段转段程序】\n{rules}")

    if "pace_control" in skills and "pace_control" not in skills_used:
        skills_used.append("pace_control")
        rules = procedure.format_phase(phase.value)
        context_parts.append(f"【组局流程】\n{rules}")
        tool_calls.append(
            {
                "round": round_no,
                "role": role.value,
                "tool": "procedure_rules",
                "input": phase.value,
                "output_summary": rules[:200],
            }
        )

    if "contract_rag" in skills:
        query = _build_contract_query(case_title, tension_points, phase)
        results = contract_retriever.search(query, top_k=3)
        skills_used.append("contract_rag")
        formatted = contract_retriever.format_results(results)
        context_parts.append(f"【媒婆合约检索】查询：{query}\n{formatted}")
        tool_calls.append(
            {
                "round": round_no,
                "role": role.value,
                "tool": "contract_retriever",
                "input": query,
                "output_summary": formatted[:300],
                "hits": [r.cite() for r in results],
            }
        )

    if "trait_reveal" in skills and phase in (Phase.EVIDENCE, Phase.DEBATE):
        items = trait_db.list_by_case(session_id, party="male")
        skills_used.append("trait_reveal")
        formatted = trait_db.format_list(items)
        context_parts.append(f"【男方已展示条件】\n{formatted}")
        tool_calls.append(
            {
                "round": round_no,
                "role": role.value,
                "tool": "trait_db",
                "input": f"{session_id}/male",
                "output_summary": formatted[:300],
            }
        )

    if "trait_probe" in skills and phase in (Phase.EVIDENCE, Phase.DEBATE):
        items = trait_db.list_by_case(session_id)
        skills_used.append("trait_probe")
        formatted = trait_db.format_list(items)
        context_parts.append(f"【双方条件一览（供追问核实）】\n{formatted}")
        tool_calls.append(
            {
                "round": round_no,
                "role": role.value,
                "tool": "trait_db",
                "input": f"{session_id}/all",
                "output_summary": formatted[:300],
            }
        )

    if "old_school_wisdom" in skills and phase in (Phase.INVESTIGATION, Phase.DEBATE):
        skills_used.append("old_school_wisdom")
        hints = (
            "【老一辈土风格】看人家要\"看脚底\"：房本、工作、家里几口人得问清；"
            "别听嘴上\"会过日子\"，得看实际行动；彩礼五金事先讲明白，免得后面扯皮。"
        )
        context_parts.append(hints)

    if "young_love_view" in skills:
        skills_used.append("young_love_view")
        context_parts.append(
            "【年轻人恋爱观】可以先从共同兴趣聊起；"
            "条件重要但别像审犯人；不合适就礼貌说，不必硬凑。"
        )

    if "reality_check" in skills and phase in (Phase.EVIDENCE, Phase.DEBATE):
        skills_used.append("reality_check")
        context_parts.append(
            "【现实核对】留意对方是否回避房子、工作、身体等关键问题；"
            "说\"以后再说\"的往往有信息差。"
        )

    if "play_cool" in skills:
        skills_used.append("play_cool")
        context_parts.append("【恋爱小技巧】别表现得太急；适当保留神秘感；被问到了再慢慢说。")

    if "heartfelt_share" in skills:
        skills_used.append("heartfelt_share")
        context_parts.append("【表达提示】可以真诚分享想法，但避免人身攻击或羞辱对方。")

    if "self_intro" in skills:
        skills_used.append("self_intro")
        context_parts.append("【自我介绍】从工作、爱好、对婚姻的期待说起，符合年轻人语气。")

    if "atmosphere_control" in skills:
        skills_used.append("atmosphere_control")
        context_parts.append("【氛围控制】制止互相贬低、辱骂；引导按媒婆安排的顺序发言。")

    return "\n\n".join(context_parts), tool_calls, skills_used
