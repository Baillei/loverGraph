"""Format persona block for LLM context."""

from __future__ import annotations

from lover_graph.schemas import Role
from lover_graph.schemas.behavior_constraints import BehaviorConstraints
from lover_graph.schemas.role_persona import DEFAULT_PERSONAS, RoleArchetype, RolePersona


def get_persona(scenario_parties: dict, role_key: str) -> RolePersona:
    party = scenario_parties.get(role_key, {})
    if "persona" in party:
        raw = party["persona"]
        if isinstance(raw, RolePersona):
            return raw
        return RolePersona.model_validate(raw)
    return DEFAULT_PERSONAS.get(role_key, RolePersona.party_default())


def format_persona_context(
    role: Role,
    scenario_parties: dict,
    behavior: BehaviorConstraints,
) -> str:
    key = role.value
    persona = get_persona(scenario_parties, key)
    lines = [
        "## 角色人设（大五人格 + 价值偏好）",
        f"- 社会类型：{persona.archetype.value}",
        f"- 大五：{persona.big_five.summary()}",
        f"- 价值偏好：{', '.join(persona.value_preferences) or '（未标注）'}",
    ]
    if persona.behavior_notes:
        lines.append(f"- 行为倾向：{persona.behavior_notes}")
    if persona.speech_style:
        lines.append(f"- 说话风格：{persona.speech_style}")

    if persona.archetype == RoleArchetype.NEUTRAL:
        lines.append("- 约束：保持中立，不得辱骂、偏袒、情绪失控。")
    elif persona.archetype == RoleArchetype.PROFESSIONAL:
        lines.append("- 约束：专业文明，严守法官指挥，禁止辱骂与插话对抗法庭。")
    elif persona.archetype == RoleArchetype.SOCIAL:
        lines.append(
            "- 约束：社会人，可按人格出现激动、骂人、不服指挥；"
            f"法官警告累计 {behavior.matchmaker_warning_limit} 次后可能被截断。"
        )
    if behavior.enforce_big_five:
        lines.append("- 发言须与上述大五人格一致（屁股决定脑袋）。")
    return "\n".join(lines)
