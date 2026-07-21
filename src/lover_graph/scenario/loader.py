"""Load trial scenario and build runtime artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from lover_graph.schemas import SessionInput, PartyInfo, Role
from lover_graph.schemas.party_profile import Gender
from lover_graph.schemas.trial_constraints import BudgetMode
from lover_graph.schemas.trial_scenario import (
    TraitItem,
    TraitStatus,
    PartySide,
    MatchScenario,
)
from lover_graph.settings import get_settings


def scenarios_dir() -> Path:
    return get_settings().data_dir / "scenarios"


def load_scenario(path: str | Path) -> MatchScenario:
    p = Path(path)
    if not p.is_absolute():
        candidate = scenarios_dir() / p
        if candidate.exists():
            p = candidate
        elif not p.exists():
            raise FileNotFoundError(path)
    if not p.exists():
        raise FileNotFoundError(p)
    data = json.loads(p.read_text(encoding="utf-8"))
    return MatchScenario.model_validate(data)


def _parse_gender(val: str | None) -> Gender:
    if not val:
        return Gender.UNKNOWN
    try:
        return Gender(val)
    except ValueError:
        return Gender.UNKNOWN


def scenario_to_session_input(scenario: MatchScenario) -> SessionInput:
    pl = scenario.parties["male"]
    df = scenario.parties["female"]
    matchmaker = scenario.parties.get("matchmaker", {})
    clerk = scenario.parties.get("clerk", {})
    has_pl = scenario.simulation.male_has_lawyer or pl.get("has_lawyer", True)
    has_dl = scenario.simulation.female_has_lawyer or df.get("has_lawyer", True)
    pl_lawyer_name = (
        scenario.parties.get("male_parents", {}).get("name")
        or pl.get("lawyer_name")
        or (f"{pl['name']}家长" if has_pl else None)
    )
    df_lawyer_name = (
        scenario.parties.get("female_parents", {}).get("name")
        or df.get("lawyer_name")
        or (f"{df['name']}家长" if has_dl else None)
    )

    return SessionInput(
        session_id=scenario.scenario_id,
        title=scenario.narrative.title,
        venue=scenario.venue,
        matchmaker_name=matchmaker.get("name", "王媒婆"),
        assistant_name=clerk.get("name", "小李"),
        male=PartyInfo(
            name=pl["name"],
            role=Role.MALE,
            gender=_parse_gender(pl.get("gender")),
            has_lawyer=has_pl,
            lawyer_name=pl_lawyer_name,
            lawyer_gender=_parse_gender(
                scenario.parties.get("male_parents", {}).get("gender") or pl.get("lawyer_gender")
            ),
            profile=pl.get("profile", ""),
            ideal_partner=pl.get("ideal_partner", ""),
        ),
        female=PartyInfo(
            name=df["name"],
            role=Role.FEMALE,
            gender=_parse_gender(df.get("gender")),
            has_lawyer=has_dl,
            lawyer_name=df_lawyer_name,
            lawyer_gender=_parse_gender(
                scenario.parties.get("female_parents", {}).get("gender") or df.get("lawyer_gender")
            ),
            profile=df.get("profile", ""),
            ideal_partner=df.get("ideal_partner", ""),
        ),
        ideal_partner_notes=scenario.ideal_partner_notes,
        background_summary=scenario.five_w_one_h.how,
        tension_points=scenario.tension_points,
        max_rounds=scenario.simulation.resolved_constraints().max_rounds,
    )


def _side_for_role(role: Role) -> PartySide | None:
    if role in (Role.MALE, Role.MALE_PARENTS):
        return PartySide.MALE
    if role in (Role.FEMALE, Role.FEMALE_PARENTS):
        return PartySide.FEMALE
    return None


def _is_on_docket(item: TraitItem, pool) -> bool:
    """证据已进入本案卷宗（PP 或 DP）。"""
    return item.id in pool.submitted_ids


def _can_see_content(item: TraitItem, side: PartySide | None, is_matchmaker: bool, pool) -> bool:
    if is_matchmaker:
        return _is_on_docket(item, pool) and item.content_access.venue
    if side == PartySide.MALE:
        return item.content_access.male
    if side == PartySide.FEMALE:
        return item.content_access.female
    return False


def _can_know_exists(item: TraitItem, side: PartySide | None, is_matchmaker: bool, pool) -> bool:
    if is_matchmaker:
        # 法官仅知晓已进入卷宗的证据；N-PP-DP 在当事人申请调取前不可见
        return _is_on_docket(item, pool)
    if side == PartySide.MALE:
        return item.known_to.male
    if side == PartySide.FEMALE:
        return item.known_to.female
    return False


def format_traits_for_role(scenario: MatchScenario, role: Role) -> str:
    """Role-filtered trait view — not the full pool."""
    side = _side_for_role(role)
    is_matchmaker = role == Role.MATCHMAKER
    pool = scenario.trait_pool
    pp_n, dp_n = len(pool.male_bundle), len(pool.female_bundle)

    if is_matchmaker:
        lines = [
            f"条件概况：男方主动展示 {pp_n} 项、女方主动展示 {dp_n} 项。"
            "你掌握双方已公开的条件；未公开部分需双方自愿补充。"
        ]
        lines.append("\n【男方已展示】")
        for eid in pool.male_bundle:
            item = next((e for e in pool.items if e.id == eid), None)
            if item:
                flag = []
                if item.authenticity_dispute:
                    flag.append("真实性争议")
                if item.relevance_dispute:
                    flag.append("关联性争议")
                extra = f"（{', '.join(flag)}）" if flag else ""
                lines.append(
                    f"- {item.id} {item.name}：{item.description}（证明：{item.proves}）{extra}"
                )
        lines.append("\n【女方已展示】")
        for eid in pool.female_bundle:
            item = next((e for e in pool.items if e.id == eid), None)
            if item:
                flag = []
                if item.authenticity_dispute:
                    flag.append("真实性争议")
                if item.relevance_dispute:
                    flag.append("关联性争议")
                extra = f"（{', '.join(flag)}）" if flag else ""
                lines.append(
                    f"- {item.id} {item.name}：{item.description}（证明：{item.proves}）{extra}"
                )
        return "\n".join(lines)

    lines = [
        f"条件概况：登记 {pool.total_count} 项；男方展示 {pp_n} 项；女方展示 {dp_n} 项；"
        f"另有 {pool.undisclosed_count} 项尚未公开（可能存在信息差）。"
    ]

    bundle_ids = set(
        pool.male_bundle if side == PartySide.MALE else pool.female_bundle
    )
    lines.append("\n【我方已公开（可引用）】")
    mine = [e for e in pool.items if e.id in bundle_ids and _can_see_content(e, side, False, pool)]
    if mine:
        for e in mine:
            lines.append(f"- {e.id} {e.name}：{e.description}（证明：{e.proves}）")
    else:
        lines.append("- （暂无已公开且可引用的我方条件）")

    lines.append("\n【对方条件（按你已知信息）】")
    other_bundle = (
        pool.female_bundle if side == PartySide.MALE else pool.male_bundle
    )
    for eid in other_bundle:
        item = next((e for e in pool.items if e.id == eid), None)
        if item and _can_know_exists(item, side, False, pool):
            if _can_see_content(item, side, False, pool):
                lines.append(f"- {item.id} {item.name}：{item.description}")
            else:
                lines.append(f"- {item.id} {item.name}：（知晓存在，但具体内容未知）")

    lines.append("\n【你可能听说但未核实】")
    rumored = [
        e
        for e in pool.items
        if e.id not in bundle_ids
        and e.id not in other_bundle
        and _can_know_exists(e, side, False, pool)
        and not _can_see_content(e, side, False, pool)
    ]
    if rumored:
        for e in rumored:
            lines.append(f"- {e.id} {e.name}：{e.notes or e.description}（状态:{e.status.value}）")
    else:
        lines.append("- （无）")

    return "\n".join(lines)


def build_role_scenario_context(scenario: MatchScenario, role: Role) -> str:
    """Structured slice for LLM — NOT the full narrative.synopsis."""
    w = scenario.five_w_one_h
    parts = [
        "## 组局要素（5W1H 摘要）",
        f"- Who：{w.who}",
        f"- What：{w.what}",
        f"- When：{w.when}",
        f"- Where：{w.where}",
        f"- Why：{w.why}",
        f"- How：{w.how}",
        "",
        "## 双方理想对象",
        scenario.ideal_partner_notes,
        "",
        "## 潜在分歧",
        "\n".join(f"- {p}" for p in scenario.tension_points),
    ]

    if scenario.relationship_issues and role in (
        Role.MATCHMAKER,
        Role.MALE_PARENTS,
        Role.FEMALE_PARENTS,
    ):
        parts.extend(["", "## 关系议题标签", "\n".join(f"- {x}" for x in scenario.relationship_issues)])

    side = _side_for_role(role)
    if role == Role.MALE:
        ideal = scenario.parties["male"].get("ideal_partner", "")
        if ideal:
            parts.extend(["", "## 你的理想对象（发言要符合）", ideal])
    elif role == Role.FEMALE:
        ideal = scenario.parties["female"].get("ideal_partner", "")
        if ideal:
            parts.extend(["", "## 你的理想对象（发言要符合）", ideal])
    elif role == Role.MALE_PARENTS:
        ideal = scenario.parties.get("male_parents", {}).get("ideal_partner", "")
        pk = scenario.parties.get("male_parents", {}).get("private_knowledge", "")
        if ideal:
            parts.extend(["", "## 你对儿媳/女婿的期待", ideal])
        if pk:
            parts.extend(["", "## 家长私有阅历（勿对年轻人全说）", pk])
    elif role == Role.FEMALE_PARENTS:
        ideal = scenario.parties.get("female_parents", {}).get("ideal_partner", "")
        pk = scenario.parties.get("female_parents", {}).get("private_knowledge", "")
        if ideal:
            parts.extend(["", "## 你对女婿/儿媳的期待", ideal])
        if pk:
            parts.extend(["", "## 家长私有阅历（勿对年轻人全说）", pk])

    if side == PartySide.MALE and role == Role.MALE:
        pk = scenario.parties["male"].get("private_knowledge", "")
        if pk:
            parts.extend(["", "## 我方私有认知（勿向对方泄露）", pk])
    elif side == PartySide.FEMALE and role == Role.FEMALE:
        pk = scenario.parties["female"].get("private_knowledge", "")
        if pk:
            parts.extend(["", "## 我方私有认知（勿向对方泄露）", pk])

    if scenario.value_tensions:
        parts.extend(["", "## 价值张力（背景，发言时体现立场差异即可）"])
        for vt in scenario.value_tensions:
            parts.append(f"- {vt.axis}：男方侧{vt.male_values} vs 女方侧{vt.female_values}")

    parts.extend(["", "## 条件信息（你的视角）", format_traits_for_role(scenario, role)])
    return "\n".join(parts)


def apply_constraint_overrides(
    scenario: MatchScenario,
    *,
    budget_mode: BudgetMode | None = None,
    word_count_limit: int | None = None,
    max_rounds: int | None = None,
    duration_minutes: float | None = None,
    words_per_minute: int | None = None,
) -> MatchScenario:
    """CLI 外置参数覆盖场景内 constraints（预算维度互斥）。"""
    from lover_graph.constraints.budget import INACTIVE_MAX_ROUNDS, validate_budget_inputs
    from lover_graph.schemas.trial_constraints import SessionConstraints

    c = scenario.simulation.resolved_constraints().model_copy(deep=True)
    if budget_mode is not None:
        c.budget_mode = budget_mode
    if words_per_minute is not None:
        c.words_per_minute = words_per_minute

    mode = validate_budget_inputs(
        budget_mode=c.budget_mode,
        max_rounds=max_rounds,
        word_count=word_count_limit,
        duration_minutes=duration_minutes,
    )
    c.budget_mode = mode

    if mode == BudgetMode.MATCHMAKER_TURNS:
        if max_rounds is not None:
            c.max_rounds = max_rounds
            scenario.simulation.max_rounds = max_rounds
        c.max_rounds = c.max_rounds or scenario.simulation.max_rounds
    else:
        wpm = c.words_per_minute
        if duration_minutes is not None:
            c.word_count_limit = int(duration_minutes * wpm)
        elif word_count_limit is not None:
            c.word_count_limit = word_count_limit
        c.max_rounds = INACTIVE_MAX_ROUNDS

    scenario.simulation.constraints = c
    return scenario


def print_scenario_brief(scenario: MatchScenario) -> str:
    """Human-readable intro — shown at CLI entry, not injected to agents."""
    pool = scenario.trait_pool
    lines = [
        "=" * 60,
        scenario.narrative.title,
        "=" * 60,
        "",
        scenario.narrative.synopsis,
        "",
        f"【场景来源】{scenario.source}",
        f"【地点】{scenario.venue}｜{scenario.meeting_type}",
        "",
        "【5W1H】",
        f"  Who   : {scenario.five_w_one_h.who[:80]}...",
        f"  What  : {scenario.five_w_one_h.what}",
        f"  When  : {scenario.five_w_one_h.when}",
        f"  Where : {scenario.five_w_one_h.where}",
        f"  Why   : {scenario.five_w_one_h.why[:80]}...",
        f"  How   : {scenario.five_w_one_h.how[:80]}...",
        "",
        f"【条件布局】N={pool.total_count}｜男方={len(pool.male_bundle)}｜"
        f"女方={len(pool.female_bundle)}｜未公开={pool.undisclosed_count}",
        f"  男方: {', '.join(pool.male_bundle)}",
        f"  女方: {', '.join(pool.female_bundle)}",
        "",
        "【价值不对齐】",
    ]
    for vt in scenario.value_tensions:
        lines.append(f"  - {vt.axis}")
    c = scenario.simulation.resolved_constraints()
    from lover_graph.constraints.budget import active_budget_summary

    lines.extend(
        [
            "",
            "【局时约束】",
            f"  预算维度 budget_mode = {c.budget_mode.value}",
            f"  控场目标：{active_budget_summary(c)}",
            f"  软预算 {c.soft_budget_ratio:.0%} / 硬预算 {c.hard_budget_ratio:.0%}",
        ]
    )
    lines.extend(
        [
            "",
            f"【氛围】{scenario.narrative.atmosphere}",
            "",
            "输入 Enter 开始相亲局，Ctrl+C 取消。",
            "=" * 60,
        ]
    )
    return "\n".join(lines)
