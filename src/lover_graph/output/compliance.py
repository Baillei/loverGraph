"""庭审达标审计 — 写入 JSONL 末尾 compliance 记录。"""

from __future__ import annotations

from lover_graph.constraints import compute_budget, get_constraints
from lover_graph.constraints.budget import rounds_enforced, time_enforced
from lover_graph.graph.state import SessionState
from lover_graph.harness.phase_budget import count_matchmaker_turns_in_phase, count_words_in_phase
from lover_graph.harness.phase_schedule import PhasePaceStatus, get_phase_window
from lover_graph.schemas import Phase
from lover_graph.schemas.trial_constraints import BudgetMode, SessionConstraints

DYNAMIC_PHASES = ["investigation", "evidence", "debate", "closing"]


def _phase_pace_status(
    c: SessionConstraints,
    phase: str,
    matchmaker_used: int,
    words_used: int,
    minutes_used: float,
    w,
) -> str:
    if time_enforced(c):
        under = words_used < w.min_words and minutes_used < w.min_minutes
        over = words_used > w.max_words or minutes_used > w.max_minutes
    else:
        under = matchmaker_used < w.min_matchmaker_turns
        over = matchmaker_used > w.max_matchmaker_turns
    if matchmaker_used == 0 and words_used == 0:
        return PhasePaceStatus.UNDERFILLED.value  # missing treated as underfilled
    if under and not over:
        return PhasePaceStatus.UNDERFILLED.value
    if over:
        return PhasePaceStatus.OVERDUE.value
    lead = matchmaker_used / w.target_matchmaker_turns if w.target_matchmaker_turns and not time_enforced(c) else 0
    if not time_enforced(c) and lead >= 0.85:
        return PhasePaceStatus.APPROACHING.value
    if time_enforced(c):
        wr = words_used / w.target_words if w.target_words else 0
        if wr >= 0.85:
            return PhasePaceStatus.APPROACHING.value
    return PhasePaceStatus.IN_BAND.value


def _phase_pass(status: str, seen: bool) -> bool:
    if not seen:
        return False
    return status in (
        PhasePaceStatus.IN_BAND.value,
        PhasePaceStatus.APPROACHING.value,
        PhasePaceStatus.OVERDUE.value,
    )


def build_compliance_report(
    state: SessionState,
    constraints: SessionConstraints | None = None,
    *,
    max_steps: int | None = None,
    steps_executed: int | None = None,
) -> dict:
    """生成 type=compliance 记录，供 JSONL 末尾追加。"""
    c = constraints or get_constraints(state)
    snap = compute_budget(state, c)
    dialogues = state.get("dialogues", [])
    phases_seen = set(snap.phases_seen)

    phase_checks: dict[str, dict] = {}
    phase_all_pass = True

    for ph in DYNAMIC_PHASES:
        w = get_phase_window(c, ph)
        j_used = count_matchmaker_turns_in_phase(state, ph)
        words_used = count_words_in_phase(state, ph)
        minutes_used = round(words_used / max(c.words_per_minute, 1), 2)
        seen = ph in phases_seen or j_used > 0 or words_used > 0
        status = _phase_pace_status(c, ph, j_used, words_used, minutes_used, w)
        if not seen:
            status = "missing"
        ok = _phase_pass(status, seen) if seen else False
        if not ok:
            phase_all_pass = False

        entry: dict = {
            "pass": ok,
            "seen": seen,
            "pace_status": status,
        }
        if rounds_enforced(c):
            entry.update(
                {
                    "matchmaker_turns_used": j_used,
                    "matchmaker_turns_min": w.min_matchmaker_turns,
                    "matchmaker_turns_target": w.target_matchmaker_turns,
                    "matchmaker_turns_max": w.max_matchmaker_turns,
                }
            )
        if time_enforced(c):
            entry.update(
                {
                    "words_used": words_used,
                    "words_min": w.min_words,
                    "words_target": w.target_words,
                    "words_max": w.max_words,
                    "minutes_used": minutes_used,
                    "minutes_min": w.min_minutes,
                    "minutes_target": w.target_minutes,
                    "minutes_max": w.max_minutes,
                }
            )
        phase_checks[ph] = entry

    required = [p for p in c.required_phases if p not in ("opening", "verdict")]
    missing_phases = [p for p in required if p not in phases_seen]

    has_verdict = state.get("verdict") is not None
    forced_closing_injected = any(
        d.phase == Phase.CLOSING
        and d.skills_used
        and "fixed_ceremony" in d.skills_used
        for d in dialogues
    )
    program_complete = len(missing_phases) == 0 and phase_all_pass

    global_check: dict = {"pass": program_complete and has_verdict}
    if rounds_enforced(c):
        global_check.update(
            {
                "matchmaker_turns_used": snap.rounds_used,
                "matchmaker_turns_limit": c.max_rounds,
                "within_round_budget": snap.rounds_used <= c.max_rounds,
            }
        )
    if time_enforced(c):
        global_check.update(
            {
                "word_count_used": snap.word_count_used,
                "word_count_limit": c.word_count_limit,
                "within_word_budget": snap.word_count_used <= c.word_count_limit,
            }
        )

    graph_steps = {
        "max_steps_configured": max_steps,
        "steps_executed": steps_executed,
        "hit_max_steps": (
            max_steps is not None
            and steps_executed is not None
            and steps_executed >= max_steps
        ),
    }

    checks = {
        "has_verdict": {"pass": has_verdict},
        "required_phases": {
            "pass": len(missing_phases) == 0,
            "required": required,
            "completed": list(phases_seen),
            "missing": missing_phases,
        },
        "phase_windows": {"pass": phase_all_pass, "phases": phase_checks},
        "global_budget": global_check,
        "forced_closing_fixup": {
            "pass": not (forced_closing_injected and bool(missing_phases)),
            "injected": forced_closing_injected,
            "note": "固定收尾台词注入（通常表示程序未自然走完）" if forced_closing_injected else None,
        },
        "graph_execution": graph_steps,
    }

    overall_pass = all(
        checks[k]["pass"]
        for k in ("has_verdict", "required_phases", "phase_windows", "forced_closing_fixup")
    ) and global_check.get("pass", False)

    return {
        "type": "compliance",
        "overall_pass": overall_pass,
        "budget_mode": c.budget_mode.value,
        "termination": state.get("termination") or snap.termination_reason or "unknown",
        "checks": checks,
    }
