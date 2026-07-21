"""Prompt loading utilities."""

from __future__ import annotations

from pathlib import Path

from lover_graph.schemas import Phase, Role
from lover_graph.settings import get_settings

PROMPTS_DIR = get_settings().prompts_dir

PHASE_LABELS: dict[Phase, str] = {
    Phase.OPENING: "组局开场",
    Phase.INVESTIGATION: "互相了解",
    Phase.EVIDENCE: "条件交换",
    Phase.DEBATE: "深入交流",
    Phase.CLOSING: "最终表态",
    Phase.VERDICT: "媒婆定论",
}


def _read(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return ""


def load_prompt(role: Role, phase: Phase) -> str:
    parts: list[str] = []

    shared = _read(PROMPTS_DIR / "_shared" / "output_format.md")
    if shared:
        parts.append(shared)

    role_default = _read(PROMPTS_DIR / role.value / "default.md")
    if role_default:
        parts.append(role_default)
    else:
        parts.append(_builtin_prompt(role))

    if role == Role.MATCHMAKER:
        pace = _read(PROMPTS_DIR / role.value / "phase_pace.md")
        if pace:
            parts.append(pace)

    phase_overlay = _read(PROMPTS_DIR / role.value / f"{phase.value}.md")
    if phase_overlay:
        parts.append(phase_overlay)

    return "\n\n---\n\n".join(parts)


def load_outcome_prompt() -> str:
    text = _read(PROMPTS_DIR / "outcome.md")
    return text or (
        "你是媒婆，根据整场相亲对话撰写 JSON："
        "observations, matchmaker_opinion, final_result, contract_refs。"
        "final_result 只能是「结婚」或「没谈成」。"
    )


def _builtin_prompt(role: Role) -> str:
    base = {
        Role.MATCHMAKER: "你是面无表情的媒婆，组局、控场、定节奏，不偏袒任何一方。",
        Role.MALE: "你是男方，年轻，恋爱经验不多，按自己的人设表达理想对象与真实想法。",
        Role.MALE_PARENTS: "你是男方家长代表，老练，有婚姻阅历，替儿子把关，默认不把刻骨铭心的经历全说给年轻人听。",
        Role.FEMALE: "你是女方，年轻，恋爱经验不多，按自己的人设表达理想对象与真实想法。",
        Role.FEMALE_PARENTS: "你是女方家长代表，老练，有婚姻阅历，替女儿掌眼，默认不把刻骨铭心的经历全说给年轻人听。",
    }
    return base.get(role, "你是相亲局参与者。")
