"""Shared thinking-agent logic for role nodes."""

from __future__ import annotations

from lover_graph.constraints import compute_budget, count_matchmaker_turns, format_matchmaker_budget_block, get_constraints
from lover_graph.constraints.budget import rounds_enforced
from lover_graph.graph.state import SessionState
from lover_graph.llm.client import LLMClient
from lover_graph.harness.format import format_harness_block
from lover_graph.persona.formatter import format_persona_context
from lover_graph.prompts.loader import PHASE_LABELS, load_prompt
from lover_graph.scenario import build_role_scenario_context
from lover_graph.schemas import (
    ROLE_TO_SPEAKER,
    SessionInput,
    DialogueTurn,
    Phase,
    Role,
    ThinkingOutput,
)
from lover_graph.schemas.behavior_constraints import BehaviorConstraints
from lover_graph.skills import run_skills
from lover_graph.tools.discipline import (
    format_discipline_context,
    is_muted,
    tick_muted,
)

_PARTY_ROLES = frozenset(
    {Role.MALE, Role.FEMALE, Role.MALE_PARENTS, Role.FEMALE_PARENTS}
)


def _count_role_turns(state: SessionState, role: Role) -> int:
    return sum(1 for d in state.get("dialogues", []) if d.role == role)


def _get_scripted_speak(state: SessionState, role: Role) -> str | None:
    scenario = state.get("scenario")
    if scenario is None:
        return None
    behavior = scenario.simulation.behavior
    demo = behavior.discipline_demo
    if demo is None or not demo.enabled:
        return None
    if demo.role != role.value:
        return None
    if _count_role_turns(state, role) + 1 != demo.speech_index:
        return None
    return demo.text


def _get_behavior(state: SessionState) -> BehaviorConstraints:
    scenario = state.get("scenario")
    if scenario and hasattr(scenario.simulation, "behavior"):
        return scenario.simulation.behavior
    return BehaviorConstraints()


def format_history(state: SessionState, limit: int = 12) -> str:
    lines = []
    for d in state["dialogues"][-limit:]:
        emo = ""
        if d.emotion:
            top = sorted(d.emotion.items(), key=lambda x: -x[1])[:2]
            emo = " [" + ",".join(f"{k}:{v:.1f}" for k, v in top) + "]"
        lines.append(
            f"[{PHASE_LABELS.get(d.phase, d.phase.value)}|{d.role.value}|{d.role_name}]{emo} {d.text}"
        )
    return "\n".join(lines) or "（尚无发言）"


def _format_case_context(case: SessionInput, role: Role) -> str:
    lines = [
        f"局号：{case.session_id}",
        f"主题：{case.title}",
        f"地点：{case.venue or '（未填）'}",
        f"媒婆：{case.matchmaker_name}；助手：{case.assistant_name}",
        f"双方理想对象：{case.ideal_partner_notes}",
        f"背景：{case.background_summary}",
        f"潜在分歧：{'；'.join(case.tension_points) or '（未标注）'}",
        f"男方：{case.male.name}（{case.male.gender.display()}）"
        + (f"（家长：{case.male.lawyer_name}）" if case.male.has_lawyer else "（独自赴局）"),
        f"女方：{case.female.name}（{case.female.gender.display()}）"
        + (f"（家长：{case.female.lawyer_name}）" if case.female.has_lawyer else "（独自赴局）"),
    ]
    if role == Role.MALE:
        lines.append(f"你的画像：{case.male.profile}")
        if case.male.ideal_partner:
            lines.append(f"你的理想对象：{case.male.ideal_partner}")
    elif role == Role.FEMALE:
        lines.append(f"你的画像：{case.female.profile}")
        if case.female.ideal_partner:
            lines.append(f"你的理想对象：{case.female.ideal_partner}")
    elif role == Role.MALE_PARENTS:
        lines.append("你是男方家长代表，经验丰富，替儿子把关，说话老练但不失礼。")
    elif role == Role.FEMALE_PARENTS:
        lines.append("你是女方家长代表，经验丰富，替女儿掌眼，说话老练但不失礼。")
    return "\n".join(lines)


def run_thinking_agent(
    state: SessionState,
    role: Role,
    role_name: str,
    llm: LLMClient | None = None,
) -> dict:
    behavior = _get_behavior(state)
    warnings = dict(state.get("discipline_warnings", {}))
    muted = dict(state.get("muted_roles", {}))
    muted = tick_muted(muted)

    if is_muted(muted, role):
        turn = DialogueTurn(
            speaker=ROLE_TO_SPEAKER[role].value,
            role=role,
            role_name=role_name,
            phase=state["current_phase"],
            text="（媒婆示意，先别说话。）",
            think="被媒婆截断/禁言中，本轮不发言。",
            emotion={"anxiety": 0.6, "anger": 0.4},
            skills_used=["discipline_muted"],
            interrupted=True,
        )
        return {
            "dialogues": [turn],
            "full_text": state.get("full_text", "") + f"\n{role_name}：{turn.text}",
            "total_round": state["total_round"] + 1,
            "next_speaker": Role.MATCHMAKER,
            "muted_roles": muted,
            "discipline_warnings": warnings,
            "party_turn_buffer": None,
        }

    case: SessionInput = state["session_input"]
    phase = state["current_phase"]
    phase_label = PHASE_LABELS.get(phase, phase.value)

    skill_context, tool_calls, auto_skills = run_skills(
        role=role,
        phase=phase,
        session_id=case.session_id,
        case_title=case.title,
        tension_points=case.tension_points,
        round_no=state["total_round"],
        state=state,
    )

    system = load_prompt(role, phase)
    scenario = state.get("scenario")
    if scenario is not None:
        system += f"\n\n---\n\n{build_role_scenario_context(scenario, role)}"
        system += f"\n\n---\n\n{format_persona_context(role, scenario.parties, behavior)}"
    if role == Role.MATCHMAKER:
        system += f"\n\n---\n\n{format_matchmaker_budget_block(state)}"
        hc = state.get("harness_context")
        if hc:
            system += f"\n\n---\n\n{format_harness_block(hc)}"
        system += f"\n\n---\n\n## 现场秩序状态\n{format_discipline_context(warnings, muted, behavior)}"
    if skill_context:
        system += f"\n\n---\n\n## 系统预检索（Skills/Tools）\n\n{skill_context}"

    if behavior.emotion_per_turn:
        system += (
            "\n\n请在 JSON 中填写 `emotion` 对象（0.0~1.0），"
            f"维度可含：{', '.join(behavior.emotion_dimensions)}。"
        )

    scripted = _get_scripted_speak(state, role)
    if scripted is not None:
        out = ThinkingOutput(
            think="（演示注入）按剧本说出违规台词。",
            speak=scripted,
            skills_used=["discipline_demo_script"],
            emotion={"anger": 0.9, "defensiveness": 0.8} if behavior.emotion_per_turn else {},
        )
        tool_calls = list(tool_calls)
        tool_calls.append(
            {
                "round": state["total_round"],
                "tool": "discipline_demo",
                "role": role.value,
                "target": role.value,
                "input": scripted,
                "output_summary": "scripted_party_line",
            }
        )
    else:
        user = (
            f"## 组局信息\n{_format_case_context(case, role)}\n\n"
            f"## 当前流程\n"
            f"- 阶段：{phase_label}（{phase.value}）\n"
            f"- 总发言轮次：第 {state['total_round'] + 1} 轮\n"
            f"- 媒婆已发言：{count_matchmaker_turns(state)} 次（上限见局时预算）\n"
            f"- 你的身份：{role_name}（{role.value}）\n\n"
            f"## 近期对话记录\n{format_history(state)}\n\n"
            f"请根据上述信息，生成本轮 `{role_name}` 的发言。"
        )
        llm = llm or LLMClient()
        out = llm.generate_structured(system, user, ThinkingOutput)

    merged_skills = list(dict.fromkeys(auto_skills + out.skills_used))
    emotion = out.emotion if behavior.emotion_per_turn else None

    turn = DialogueTurn(
        speaker=ROLE_TO_SPEAKER[role].value,
        role=role,
        role_name=role_name,
        phase=phase,
        text=out.speak,
        think=out.think,
        contract_refs=out.contract_refs,
        skills_used=merged_skills,
        emotion=emotion or None,
        value_signal=out.value_signal,
        routing={"next": out.next_speaker.value} if out.next_speaker else None,
    )

    update: dict = {
        "total_round": state["total_round"] + 1,
        "tool_calls": tool_calls,
        "discipline_warnings": warnings,
        "muted_roles": muted,
        "needs_matchmaker_discipline": False,
        "discipline_event": None,
    }

    if role in _PARTY_ROLES:
        update["party_turn_buffer"] = turn
    else:
        update["dialogues"] = [turn]
        update["full_text"] = state.get("full_text", "") + f"\n{role_name}：{out.speak}"

    if role == Role.MATCHMAKER:
        update["next_speaker"] = out.next_speaker or Role.MALE
        update["matchmaker_routing_log"] = [
            {"round": state["total_round"], "next": str(out.next_speaker), "end": out.end_session}
        ]
        if state.get("discipline_followup"):
            update["discipline_followup"] = None

        if out.end_session:
            hc = state.get("harness_context") or {}
            if hc.get("forbid_phase_advance"):
                update["next_speaker"] = out.next_speaker or Role.MALE
                update["matchmaker_routing_log"] = [
                    {
                        "round": state["total_round"],
                        "next": str(update["next_speaker"]),
                        "end": False,
                        "reason": "phase_underfilled_block_end_session",
                    }
                ]
            else:
                update["next_speaker"] = "End"
                update["current_phase"] = Phase.CLOSING
                update["termination"] = "normal"
        else:
            merged_state = {**state, **update}
            merged_state["dialogues"] = state.get("dialogues", []) + update.get("dialogues", [])
            snap = compute_budget(merged_state)  # type: ignore[arg-type]
            constraints = get_constraints(state)
            force_by_rounds = False
            if rounds_enforced(constraints):
                remaining = constraints.max_rounds - count_matchmaker_turns(merged_state)
                force_by_rounds = remaining <= 2
            if snap.force_close_now or force_by_rounds:
                update["next_speaker"] = "End"
                update["current_phase"] = Phase.CLOSING
                update["termination"] = snap.termination_reason or "budget_hard"
                update["matchmaker_routing_log"] = [
                    {
                        "round": state["total_round"],
                        "next": "End",
                        "end": True,
                        "reason": "constraint_force_close",
                    }
                ]
    return update
