"""Skill registry and role permissions."""

from __future__ import annotations

from lover_graph.schemas import Role

ROLE_SKILLS: dict[Role, list[str]] = {
    Role.MATCHMAKER: [
        "session_clock",
        "phase_coach",
        "phase_schedule",
        "post_moderation_coach",
        "contract_rag",
        "pace_control",
        "atmosphere_control",
    ],
    Role.MALE: ["heartfelt_share", "self_intro", "young_love_view"],
    Role.MALE_PARENTS: ["contract_rag", "trait_reveal", "old_school_wisdom"],
    Role.FEMALE: ["play_cool", "heartfelt_share", "young_love_view"],
    Role.FEMALE_PARENTS: ["contract_rag", "trait_probe", "reality_check"],
}


def allowed_skills(role: Role) -> list[str]:
    return ROLE_SKILLS.get(role, [])
