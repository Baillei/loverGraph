"""Fixed opening ceremony for matchmaking sessions."""

from __future__ import annotations

import json
from pathlib import Path

from lover_graph.schemas import SessionInput, DialogueTurn, Phase, Role, MatchScenario
from lover_graph.settings import get_settings

_CEREMONY_PATH = get_settings().data_dir / "procedure" / "opening_ceremony.json"


def _parents_intro(side: str, case: SessionInput) -> str:
    if side == "male":
        if case.male.has_lawyer and case.male.lawyer_name:
            return f"这边是我家{case.male.name}，我是他家长{case.male.lawyer_name}，今天一起来见个面。"
        return ""
    if case.female.has_lawyer and case.female.lawyer_name:
        return f"这边是我家{case.female.name}，我是她家长{case.female.lawyer_name}，今天一起来见个面。"
    return ""


def _investigation_call(case: SessionInput) -> str:
    if case.male.has_lawyer:
        return f"先请{case.male.name}和家长简单介绍一下自己，再说说对对象的期待。"
    return f"先请{case.male.name}介绍一下自己，再说说对对象的期待。"


def _format_context(case: SessionInput, scenario: MatchScenario | None) -> dict[str, str]:
    meeting = scenario.meeting_type if scenario else "相亲局"
    return {
        "male_name": case.male.name,
        "female_name": case.female.name,
        "meeting_type": meeting,
        "matchmaker_name": case.matchmaker_name,
        "assistant_name": case.assistant_name,
        "parents_intro": "",
        "investigation_call": _investigation_call(case),
        "venue": case.venue or "相亲地点",
    }


def _resolve_role(role_key: str, case: SessionInput) -> tuple[Role, str]:
    if role_key == "matchmaker":
        return Role.MATCHMAKER, case.matchmaker_name
    if role_key == "male_side":
        if case.male.has_lawyer:
            return Role.MALE_PARENTS, case.male.lawyer_name or f"{case.male.name}家长"
        return Role.MALE, case.male.name
    if role_key == "female_side":
        if case.female.has_lawyer:
            return Role.FEMALE_PARENTS, case.female.lawyer_name or f"{case.female.name}家长"
        return Role.FEMALE, case.female.name
    raise ValueError(f"unknown ceremony role: {role_key}")


def build_opening_ceremony(
    case: SessionInput,
    scenario: MatchScenario | None = None,
) -> list[DialogueTurn]:
    path = _CEREMONY_PATH
    if not path.exists():
        raise FileNotFoundError(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    ctx = _format_context(case, scenario)
    turns: list[DialogueTurn] = []

    for item in data["turns"]:
        role_key = item["role"]
        if role_key == "male_side":
            ctx_side = {**ctx, "parents_intro": _parents_intro("male", case)}
            text = item["template"].format(**ctx_side)
        elif role_key == "female_side":
            ctx_side = {**ctx, "parents_intro": _parents_intro("female", case)}
            text = item["template"].format(**ctx_side)
        else:
            text = item["template"].format(**ctx)

        role, role_name = _resolve_role(role_key, case)
        from lover_graph.schemas import ROLE_TO_SPEAKER

        turns.append(
            DialogueTurn(
                speaker=ROLE_TO_SPEAKER[role].value,
                role=role,
                role_name=role_name,
                phase=Phase.OPENING,
                text=text,
                think="（固定开场流程，按媒婆安排宣读。）",
                skills_used=["fixed_ceremony"],
                emotion={"confidence": 0.85} if role == Role.MATCHMAKER else {"confidence": 0.7},
            )
        )
    return turns


def first_investigation_speaker(case: SessionInput) -> Role:
    if case.male.has_lawyer:
        return Role.MALE_PARENTS
    return Role.MALE
