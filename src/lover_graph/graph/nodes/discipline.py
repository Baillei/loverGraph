"""纪律校验与法官打断 — DETERMINISTIC / SCRIPT 节点。"""

from __future__ import annotations

from lover_graph.graph.nodes.base import _get_behavior
from lover_graph.graph.state import SessionState
from lover_graph.schemas import ROLE_TO_SPEAKER, DialogueTurn, Role
from lover_graph.tools.discipline import (
    apply_interrupt,
    build_discipline_followup,
    build_matchmaker_discipline_text,
    discipline_tool_log,
    record_warning,
    should_interrupt,
    truncate_speech_at_violation,
)

_PARTY_ROLES = frozenset(
    {Role.MALE, Role.FEMALE, Role.MALE_PARENTS, Role.FEMALE_PARENTS}
)


def discipline_validator_node(state: SessionState) -> dict:
    """当事人发言后：检测违规、截断播出文本、决定是否插入法官打断。"""
    buf: DialogueTurn | None = state.get("party_turn_buffer")
    if buf is None or buf.role not in _PARTY_ROLES:
        return {"needs_matchmaker_discipline": False, "party_turn_buffer": None}

    behavior = _get_behavior(state)
    warnings = dict(state.get("discipline_warnings", {}))
    muted = dict(state.get("muted_roles", {}))

    truncated, remainder, violations = truncate_speech_at_violation(buf.text, buf.role)
    needs = bool(violations)
    action = "warn"

    if needs:
        for v in violations:
            warnings = record_warning(warnings, buf.role, v)
        if should_interrupt(warnings, buf.role, behavior):
            muted = apply_interrupt(muted, buf.role, behavior)
            action = "interrupt"

        turn = buf.model_copy(
            update={
                "text": truncated,
                "interrupted": True,
                "validator_passed": False,
                "attempted_speech": buf.text,
                "truncated_remainder": remainder or None,
                "skills_used": list(dict.fromkeys(buf.skills_used + ["discipline_truncated"])),
            }
        )
    else:
        turn = buf

    update: dict = {
        "dialogues": [turn],
        "party_turn_buffer": None,
        "full_text": state.get("full_text", "") + f"\n{buf.role_name}：{turn.text}",
        "discipline_warnings": warnings,
        "muted_roles": muted,
        "needs_matchmaker_discipline": needs,
        "next_speaker": Role.MATCHMAKER,
    }

    if needs:
        update["discipline_event"] = {
            "role": buf.role.value,
            "role_name": buf.role_name,
            "violations": violations,
            "action": action,
            "remainder": remainder,
            "attempted_speech": buf.text,
            "broadcast_text": truncated,
            "round": state["total_round"],
        }
        update["validator_results"] = [
            {"role": buf.role.value, "violations": violations, "round": state["total_round"]}
        ]
        tool_calls = list(state.get("tool_calls", []))
        tool_calls.append(
            discipline_tool_log(
                "interrupt" if action == "interrupt" else "warn",
                buf.role,
                violations[0],
                state["total_round"],
            )
        )
        update["tool_calls"] = tool_calls
    else:
        update["discipline_event"] = None

    return update


def matchmaker_discipline_node(state: SessionState) -> dict:
    """法官当场打断 — 固定纪律台词，无 LLM。"""
    evt = state.get("discipline_event") or {}
    role_name = evt.get("role_name", "当事人")
    violations = evt.get("violations", [])
    action = evt.get("action", "warn")
    target = Role(evt["role"]) if evt.get("role") else Role.FEMALE

    matchmaker_name = state["session_input"].matchmaker_name
    text = build_matchmaker_discipline_text(role_name, action, violations)

    turn = DialogueTurn(
        speaker=ROLE_TO_SPEAKER[Role.MATCHMAKER].value,
        role=Role.MATCHMAKER,
        role_name=matchmaker_name,
        phase=state["current_phase"],
        text=text,
        think="纪律打断：检测到当事人违规言辞，依法制止。",
        skills_used=["discipline_interrupt"],
        interrupted=False,
    )

    followup = build_discipline_followup(
        role=evt.get("role", target.value),
        role_name=role_name,
        broadcast_text=evt.get("broadcast_text", ""),
        attempted_speech=evt.get("attempted_speech", ""),
        remainder=evt.get("remainder", ""),
        violations=violations,
        action=action,
    )

    tool_calls = list(state.get("tool_calls", []))
    tool_calls.append(
        discipline_tool_log(
            "interrupt" if action == "interrupt" else "warn",
            target,
            "matchmaker_spoke",
            state["total_round"],
        )
    )

    tool_calls.append(
        {
            "round": state["total_round"],
            "role": "matchmaker",
            "tool": "post_moderation_coach",
            "input": followup.get("broadcast_text"),
            "output_summary": f"followup→{role_name}",
        }
    )

    return {
        "dialogues": [turn],
        "full_text": state.get("full_text", "") + f"\n{matchmaker_name}：{text}",
        "total_round": state["total_round"] + 1,
        "needs_matchmaker_discipline": False,
        "discipline_event": None,
        "discipline_followup": followup,
        "next_speaker": Role.MATCHMAKER,
        "tool_calls": tool_calls,
    }
