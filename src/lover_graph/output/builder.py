"""Assemble rich trial output for digital human pipeline."""

from __future__ import annotations

from lover_graph.constraints import compute_budget, get_constraints
from lover_graph.graph.state import SessionState
from lover_graph.persona.formatter import get_persona
from lover_graph.schemas import Role
from lover_graph.schemas.role_persona import DEFAULT_PERSONAS
from lover_graph.schemas.trial_output import (
    DigitalHumanAssets,
    DisputePointStatus,
    DisputeTracker,
    EmotionTimelineEntry,
    GestureHint,
    RolePersonaSnapshot,
    SimulationMetadata,
    SessionScriptOutput,
    ValueArcEntry,
)

_ROLE_KEYS = [
    ("matchmaker", "matchmaker"),
    ("male", "male"),
    ("male_parents", "male_parents"),
    ("female", "female"),
    ("female_parents", "female_parents"),
]


def _party_gender(scenario, role_key: str) -> str:
    if not scenario:
        return "unknown"
    p = scenario.parties.get(role_key, {})
    return p.get("gender") or "unknown"


def _resolve_name(scenario, role_key: str) -> str:
    parties = scenario.parties
    if role_key == "matchmaker":
        return parties.get("matchmaker", {}).get("name", "审判员")
    if role_key == "male":
        return parties.get("male", {}).get("name", "原告")
    if role_key == "female":
        return parties.get("female", {}).get("name", "被告")
    if role_key == "male_parents":
        pl = parties.get("male", {})
        return parties.get("male_parents", {}).get("name") or pl.get("lawyer_name") or f"{pl.get('name', '原告')}律师"
    if role_key == "female_parents":
        df = parties.get("female", {})
        return parties.get("female_parents", {}).get("name") or df.get("lawyer_name") or f"{df.get('name', '被告')}律师"
    return role_key


def _should_include_lawyer(scenario, side: str) -> bool:
    sim = scenario.simulation
    if side == "male":
        return sim.male_has_lawyer or scenario.parties.get("male", {}).get("has_lawyer", False)
    return sim.female_has_lawyer or scenario.parties.get("female", {}).get("has_lawyer", False)


def _gesture_hint(turn, index: int) -> GestureHint | None:
    if turn.emotion and turn.emotion.get("anger", 0) >= 0.7:
        if turn.role in (Role.MALE, Role.FEMALE):
            return GestureHint(
                turn_index=index,
                role=turn.role.value,
                action="emotional_outburst",
                reason="愤怒情绪升高",
            )
    if any("discipline" in s for s in turn.skills_used):
        return GestureHint(turn_index=index, role="matchmaker", action="interrupt", reason="维护法庭纪律")
    return None


def build_trial_output(state: SessionState) -> SessionScriptOutput:
    scenario = state.get("scenario")
    case = state["session_input"]
    dialogues = state.get("dialogues", [])
    snap = compute_budget(state)
    constraints = get_constraints(state)

    personas: list[RolePersonaSnapshot] = []
    if scenario:
        parties = scenario.parties
        for role_key, persona_key in _ROLE_KEYS:
            if role_key.endswith("_lawyer") and not _should_include_lawyer(
                scenario, "male" if "male" in role_key else "female"
            ):
                continue
            persona = get_persona(parties, persona_key)
            personas.append(
                RolePersonaSnapshot(
                    role=role_key,
                    name=_resolve_name(scenario, role_key),
                    gender=_party_gender(scenario, role_key),
                    archetype=persona.archetype.value,
                    big_five=persona.big_five.model_dump(),
                    value_preferences=persona.value_preferences,
                )
            )

    emotion_timeline: list[EmotionTimelineEntry] = []
    gesture_hints: list[GestureHint] = []
    dispute_mentions: dict[str, list[int]] = {p: [] for p in case.tension_points}

    for i, turn in enumerate(dialogues):
        if turn.emotion:
            emotion_timeline.append(
                EmotionTimelineEntry(
                    turn_index=i,
                    phase=turn.phase,
                    role=turn.role.value,
                    role_name=turn.role_name,
                    emotion=turn.emotion,
                    speak_excerpt=turn.text[:80],
                )
            )
        hint = _gesture_hint(turn, i)
        if hint:
            gesture_hints.append(hint)
        for dp in case.tension_points:
            if dp[:4] in turn.text or any(k in turn.text for k in dp.split()[:2] if len(k) > 1):
                dispute_mentions[dp].append(i)

    dispute_tracker = DisputeTracker(
        points=[
            DisputePointStatus(
                point=dp,
                status="addressed" if mentions else "open",
                mentioned_in_turns=mentions,
            )
            for dp, mentions in dispute_mentions.items()
        ]
    )

    value_arc = [
        ValueArcEntry(role=p.role, values=p.value_preferences) for p in personas if p.value_preferences
    ]

    meta = SimulationMetadata(
        budget_mode=constraints.budget_mode.value,
        max_rounds=snap.max_rounds if constraints.budget_mode.value == "matchmaker_turns" else 0,
        word_count_limit=snap.word_count_limit if constraints.budget_mode.value == "time" else 0,
        word_count_used=snap.word_count_used,
        rounds_used=snap.rounds_used,
        duration_minutes_limit=snap.estimated_minutes_limit,
        male_has_lawyer=scenario.simulation.male_has_lawyer if scenario else True,
        female_has_lawyer=scenario.simulation.female_has_lawyer if scenario else True,
        termination=state.get("termination") or "normal",
        phases_completed=snap.phases_seen,
    )

    return SessionScriptOutput(
        scenario_id=scenario.scenario_id if scenario else case.session_id,
        session_id=case.session_id,
        title=case.title,
        venue=case.venue,
        meeting_type=scenario.meeting_type if scenario else "",
        metadata=meta,
        personas=personas,
        dialogues=dialogues,
        dispute_tracker=dispute_tracker,
        tool_calls=state.get("tool_calls", []),
        matchmaker_routing_log=state.get("matchmaker_routing_log", []),
        discipline_warnings=state.get("discipline_warnings", {}),
        verdict=state.get("verdict"),
        digital_human_assets=DigitalHumanAssets(
            emotion_timeline=emotion_timeline,
            gesture_hints=gesture_hints,
            value_arc=value_arc,
        ),
    )
