"""Harness coach node — DETERMINISTIC，在 MODEL 发言前注入阶段性控场。"""

from __future__ import annotations

from lover_graph.graph.state import SessionState
from lover_graph.harness.phase_coach import run_phase_coach
from lover_graph.schemas import Phase, Role


def harness_coach_node(state: SessionState) -> dict:
    """分析阶段预算，写入 harness_context；必要时确定性推进阶段。"""
    result = run_phase_coach(state)
    hc = result.model_dump()
    followup = state.get("discipline_followup")
    if followup:
        prefix = followup.get("coach_message", "")
        existing = hc.get("coach_message") or ""
        hc["coach_message"] = f"{prefix}\n\n{existing}".strip() if existing else prefix
        hc["discipline_followup"] = followup
        skills = list(hc.get("triggered_skills") or [])
        if "post_moderation_coach" not in skills:
            skills.insert(0, "post_moderation_coach")
        hc["triggered_skills"] = skills

    update: dict = {
        "harness_context": hc,
    }

    if result.force_advance_phase and result.next_phase and not result.forbid_phase_advance:
        try:
            target = Phase(result.next_phase)
        except ValueError:
            target = None
        if target and target != state.get("current_phase"):
            update["current_phase"] = target
            update["phase_round"] = 0
            update["next_speaker"] = Role.MATCHMAKER
            update["tool_calls"] = [
                {
                    "round": state.get("total_round", 0),
                    "role": "harness",
                    "tool": "phase_coach",
                    "input": result.current_phase,
                    "output_summary": f"force_advance→{result.next_phase}",
                    "triggered_skills": result.triggered_skills,
                }
            ]

    return update
