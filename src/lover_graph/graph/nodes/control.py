from lover_graph.constraints import compute_budget, get_constraints
from lover_graph.graph.state import SessionState
from lover_graph.procedure.closing_script import build_closing_ceremony
from lover_graph.procedure.opening_script import build_opening_ceremony, first_investigation_speaker
from lover_graph.prompts.loader import load_outcome_prompt
from lover_graph.schemas import Phase, Role

PHASE_ORDER = [Phase.OPENING, Phase.INVESTIGATION, Phase.EVIDENCE, Phase.DEBATE, Phase.CLOSING]


def opening_ceremony_node(state: SessionState) -> dict:
    """Inject fixed professional opening lines once before LLM turns."""
    if state.get("opening_ceremony_done"):
        return {}
    case = state["session_input"]
    scenario = state.get("scenario")
    turns = build_opening_ceremony(case, scenario)
    full = state.get("full_text", "")
    for t in turns:
        full += f"\n{t.role_name}：{t.text}"
    return {
        "dialogues": turns,
        "full_text": full,
        "total_round": state.get("total_round", 0) + len(turns),
        "current_phase": Phase.INVESTIGATION,
        "phase_round": 0,
        "next_speaker": first_investigation_speaker(case),
        "opening_ceremony_done": True,
        "matchmaker_routing_log": [
            {
                "round": 0,
                "next": first_investigation_speaker(case).value,
                "end": False,
                "reason": "opening_ceremony_complete",
            }
        ],
    }


def phase_controller(state: SessionState) -> dict:
    """Advance phase within party-round caps; phase transitions defer to harness window."""
    phase = state.get("current_phase", Phase.OPENING)
    pr = state.get("phase_round", 0) + 1
    update: dict = {"phase_round": pr}

    harness = state.get("harness_context") or {}
    forbid_advance = harness.get("forbid_phase_advance", False)

    constraints = get_constraints(state)
    snap = compute_budget(state, constraints)

    if snap.force_close_now and phase != Phase.CLOSING:
        update["current_phase"] = Phase.CLOSING
        update["phase_round"] = 0
        update["next_speaker"] = Role.MATCHMAKER
        return update

    # 全局收尾：仅当 harness 未禁止过早转段时，补全缺失阶段
    if snap.must_close_soon and phase != Phase.CLOSING and not forbid_advance:
        missing = snap.phases_missing
        if missing and missing[0] != phase.value:
            target = Phase(missing[0])
            if _phase_index(target) > _phase_index(phase):
                update["current_phase"] = target
                update["phase_round"] = 0
                update["next_speaker"] = Role.MATCHMAKER
                return update

    caps = constraints.phase_round_soft_caps
    soft_cap = caps.get(phase.value, 999)

    # 当事人轮次上限：仅在非 underfilled 时允许因轮次触达软上限而转段
    if not forbid_advance and pr >= soft_cap * 2 and phase != Phase.CLOSING:
        nxt = _next_phase(phase)
        if nxt:
            update["current_phase"] = nxt
            update["phase_round"] = 0
            update["next_speaker"] = Role.MATCHMAKER
            return update

    if phase == Phase.CLOSING and pr >= 2:
        update["next_speaker"] = "End"

    return update


def _phase_index(phase: Phase) -> int:
    try:
        return PHASE_ORDER.index(phase)
    except ValueError:
        return 99


def _next_phase(phase: Phase) -> Phase | None:
    idx = _phase_index(phase)
    if idx < 0 or idx >= len(PHASE_ORDER) - 1:
        return None
    return PHASE_ORDER[idx + 1]


def closing_node(state: SessionState) -> dict:
    snap = compute_budget(state)
    term = state.get("termination") or ""
    if not term and snap.termination_reason:
        term = snap.termination_reason
    if not term:
        term = "normal"
    update: dict = {
        "current_phase": Phase.CLOSING,
        "next_speaker": "End",
        "termination": term,
    }
    if not _has_closing_dialogue(state):
        closing_turns = build_closing_ceremony(state)
        full = state.get("full_text", "")
        for t in closing_turns:
            full += f"\n{t.role_name}：{t.text}"
        update["dialogues"] = closing_turns
        update["full_text"] = full
        update["total_round"] = state.get("total_round", 0) + len(closing_turns)
    return update


def _has_closing_dialogue(state: SessionState) -> bool:
    return any(d.phase == Phase.CLOSING for d in state.get("dialogues", []))


def outcome_node(state: SessionState) -> dict:
    from lover_graph.llm.client import LLMClient
    from lover_graph.schemas import MatchOutcome

    llm = LLMClient()
    case = state["session_input"]
    snap = compute_budget(state)
    history = "\n".join(
        f"[{d.phase.value}] {d.role_name}：{d.text}" for d in state["dialogues"]
    )
    dispute = "；".join(case.tension_points)
    constraints = get_constraints(state)
    if constraints.budget_mode.value == "time":
        budget_note = (
            f"庭审预算：词数 {snap.word_count_used}/{snap.word_count_limit}，"
            f"约 {snap.estimated_minutes_used}/{snap.estimated_minutes_limit} 分钟，"
            f"终止原因 {state.get('termination', 'normal')}"
        )
    else:
        budget_note = (
            f"庭审预算：法官发言 {snap.rounds_used}/{snap.max_rounds} 次，"
            f"终止原因 {state.get('termination', 'normal')}"
        )
    user = (
        f"局号：{case.session_id}\n"
        f"主题：{case.title}\n"
        f"双方理想对象：{case.ideal_partner_notes}\n"
        f"潜在分歧：{dispute}\n"
        f"{budget_note}\n\n"
        f"完整对话记录：\n{history}\n\n"
        "请撰写媒婆定论 JSON：observations, matchmaker_opinion, final_result（结婚或没谈成）, contract_refs。"
    )
    raw = llm.generate(load_outcome_prompt(), user)
    try:
        import json

        data = json.loads(raw[raw.find("{") : raw.rfind("}") + 1])
        verdict = MatchOutcome(**data)
    except Exception:
        verdict = MatchOutcome(
            observations="（待完善）",
            matchmaker_opinion="（待完善）",
            final_result="（待完善）",
        )
    return {
        "current_phase": Phase.VERDICT,
        "verdict": verdict,
        "termination": state.get("termination", "normal"),
    }
