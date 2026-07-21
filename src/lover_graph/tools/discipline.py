"""Judge discipline tools — 提醒、截断当事人发言。"""

from __future__ import annotations

import re
from typing import Any

from lover_graph.schemas import Role
from lover_graph.schemas.behavior_constraints import BehaviorConstraints

# 违规信号（启发式，后续可换分类器）
_INSULT_PATTERNS = re.compile(
    r"缺德|混蛋|不要脸|放屁|胡说|神经病|去死|妈的|操你|傻逼|滚|草泥马"
)
_DISOBEDIENCE_PATTERNS = re.compile(
    r"不要插嘴|别管我|你管不着|我就要说|凭什么|闭嘴"
)

_PARTY_ROLES = frozenset({Role.MALE, Role.FEMALE})
_LAWYER_ROLES = frozenset({Role.MALE_PARENTS, Role.FEMALE_PARENTS})


def _earliest_match_start(text: str) -> int | None:
    starts: list[int] = []
    for pat in (_INSULT_PATTERNS, _DISOBEDIENCE_PATTERNS):
        m = pat.search(text)
        if m:
            starts.append(m.start())
    return min(starts) if starts else None


def detect_violations(text: str, role: Role) -> list[str]:
    if role in _PARTY_ROLES:
        pass
    elif role in _LAWYER_ROLES:
        pass
    else:
        return []
    flags = []
    if _INSULT_PATTERNS.search(text):
        flags.append("insult")
    if _DISOBEDIENCE_PATTERNS.search(text):
        flags.append("disobedience")
    return flags


def truncate_speech_at_violation(text: str, role: Role) -> tuple[str, str, list[str]]:
    """在首个违规匹配处截断发言，返回 (播出文本, 被截断余文, 违规类型列表)。"""
    violations = detect_violations(text, role)
    if not violations:
        return text, "", []

    start = _earliest_match_start(text)
    if start is None:
        return text, "", violations

    prefix = text[:start].rstrip("，,。.!！?？、；;：: \t")
    if prefix:
        truncated = f"{prefix}——"
    else:
        truncated = "——"
    remainder = text[start:].strip()
    return truncated, remainder, violations


def build_discipline_followup(
    role: str,
    role_name: str,
    broadcast_text: str,
    attempted_speech: str,
    remainder: str,
    violations: list[str],
    action: str,
) -> dict:
    """打断后给下一轮法官的硬约束上下文（含截断前已播出内容）。"""
    labels = {"insult": "侮辱性言辞", "disobedience": "对抗法庭指挥"}
    vtext = "、".join(labels.get(v, v) for v in violations) or "违规发言"
    coach = (
        f"【纪律跟进·必达】你刚已当庭警告 {role_name}（{role}）。"
        f"当事人意图说出的**完整原话**（含辱骂，法庭已截断未向旁听播出）是：「{attempted_speech}」。"
        f"其中已记入庭审记录、对外播出的片段为：「{broadcast_text}」。"
    )
    if remainder and remainder not in attempted_speech:
        coach += f"截断余文：「{remainder}」。"
    if action == "interrupt":
        coach += "已责令其禁言。"
    coach += (
        f"违规类型：{vtext}。"
        "**本轮你的 speak 必须**："
        f"(1) 明确回应刚才的警告，并点明对方使用了不当言辞（可概述为「侮辱性语言」"
        f"，须体现你已知晓其原话为「{attempted_speech}」），不得装作没看见；"
        "(2) 要求对方规范陈述或服从禁言；"
        "(3) 再继续本案程序。"
        "speak 中勿重复脏话原词。"
    )
    return {
        "party_role": role,
        "party_name": role_name,
        "broadcast_text": broadcast_text,
        "attempted_speech": attempted_speech,
        "remainder": remainder,
        "violations": violations,
        "action": action,
        "coach_message": coach,
        "skill": "post_moderation_coach",
    }


def build_matchmaker_discipline_text(
    role_name: str,
    action: str,
    violations: list[str],
) -> str:
    if action == "interrupt":
        return (
            f"{role_name}，法庭已多次警告。"
            f"现责令你保持安静，不得再随意发言！"
        )
    if "insult" in violations:
        return (
            f"法庭警告！{role_name}，注意言辞！"
            f"庭审是严肃场合，请规范陈述，不得使用侮辱性语言。"
        )
    return (
        f"法庭警告！{role_name}，请服从法庭指挥，按程序陈述，不得随意插话或对抗法庭。"
    )


def record_warning(
    warnings: dict[str, int],
    role: Role,
    violation: str,
) -> dict[str, int]:
    key = role.value
    warnings = dict(warnings)
    warnings[key] = warnings.get(key, 0) + 1
    return warnings


def should_interrupt(
    warnings: dict[str, int],
    role: Role,
    constraints: BehaviorConstraints,
) -> bool:
    if not constraints.matchmaker_can_interrupt_parties:
        return False
    if role not in (Role.MALE, Role.FEMALE):
        return False
    return warnings.get(role.value, 0) >= constraints.matchmaker_warning_limit


def apply_interrupt(
    muted_roles: dict[str, int],
    role: Role,
    constraints: BehaviorConstraints,
) -> dict[str, int]:
    muted = dict(muted_roles)
    muted[role.value] = constraints.interrupt_duration_turns
    return muted


def tick_muted(muted_roles: dict[str, int]) -> dict[str, int]:
    return {k: v - 1 for k, v in muted_roles.items() if v > 1}


def is_muted(muted_roles: dict[str, int], role: Role) -> bool:
    return muted_roles.get(role.value, 0) > 0


def format_discipline_context(
    warnings: dict[str, int],
    muted_roles: dict[str, int],
    constraints: BehaviorConstraints,
) -> str:
    lines = [
        f"纪律提醒上限：{constraints.matchmaker_warning_limit} 次/人，超限可截断。",
        "当前警告计数：" + (", ".join(f"{k}={v}" for k, v in warnings.items()) or "无"),
    ]
    if muted_roles:
        lines.append("禁言中：" + ", ".join(f"{k}({v}轮)" for k, v in muted_roles.items() if v > 0))
    lines.append("可用工具：discipline_warn（记录警告）、discipline_interrupt（截断当事人本轮/下轮）。")
    return "\n".join(lines)


def discipline_tool_log(
    action: str,
    role: Role,
    reason: str,
    round_no: int,
) -> dict[str, Any]:
    return {
        "round": round_no,
        "tool": f"discipline_{action}",
        "role": "matchmaker",
        "target": role.value,
        "input": reason,
        "output_summary": f"{action} -> {role.value}",
    }
