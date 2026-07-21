"""Print default simulation parameters for operator review."""

from __future__ import annotations

import json

from lover_graph.schemas.behavior_constraints import BehaviorConstraints, SimulationDefaults
from lover_graph.schemas.trial_constraints import SessionConstraints


def format_defaults_report(
    defaults: SimulationDefaults | None = None,
) -> str:
    defaults = defaults or SimulationDefaults()
    constraints = SessionConstraints(**defaults.to_trial_constraints_kwargs())
    behavior = defaults.behavior

    lines = [
        "=== venueGraph 默认外置参数 ===",
        "",
        "【SimulationDefaults — 入口/场景默认】",
        f"  budget_mode             = {defaults.budget_mode.value}（matchmaker_turns | time，二选一）",
        f"  max_rounds              = {defaults.max_rounds}（仅 matchmaker_turns）",
        f"  duration_minutes        = {defaults.duration_minutes}（仅 time）",
        f"  words_per_minute        = {defaults.words_per_minute}",
        f"  word_count_limit (推导) = {defaults.derived_word_count_limit()}",
        f"  random_scenario         = {defaults.random_scenario}",
        f"  random_seed             = {defaults.random_seed}",
        f"  male_has_lawyer    = {defaults.male_has_lawyer}",
        f"  female_has_lawyer    = {defaults.female_has_lawyer}",
        "",
        "【SessionConstraints — 庭审预算与程序】",
        f"  word_count_limit        = {constraints.word_count_limit}",
        f"  budget_mode             = {constraints.budget_mode.value}",
        f"  soft_budget_ratio       = {constraints.soft_budget_ratio} → {constraints.soft_word_limit} 字",
        f"  hard_budget_ratio       = {constraints.hard_budget_ratio} → {constraints.hard_word_limit} 字",
        f"  max_rounds (法官发言)    = {constraints.max_rounds}",
        f"  required_phases         = {', '.join(constraints.required_phases)}",
        f"  phase_round_soft_caps   = {json.dumps(constraints.phase_round_soft_caps, ensure_ascii=False)}",
        f"  max_words_per_turn      = {constraints.max_words_per_turn}",
        f"  matchmaker_max_words_per_turn= {constraints.matchmaker_max_words_per_turn}",
        f"  require_final_statements= {constraints.require_final_statements}",
        f"  auto_force_close_at_hard_limit = {constraints.auto_force_close_at_hard_limit}",
        "",
        "【BehaviorConstraints — 纪律与人设】",
        f"  matchmaker_warning_limit     = {behavior.matchmaker_warning_limit}",
        f"  party_may_insult        = {behavior.party_may_insult}",
        f"  party_may_disobey_matchmaker = {behavior.party_may_disobey_matchmaker}",
        f"  lawyer_must_obey_matchmaker  = {behavior.lawyer_must_obey_matchmaker}",
        f"  emotion_per_turn        = {behavior.emotion_per_turn}",
        f"  enforce_big_five        = {behavior.enforce_big_five}",
        "",
        "【固定开庭】",
        "  程序台词：data/procedure/opening_ceremony.json",
        "  流程：审判员宣布 → 原告方确认 → 审判员询问被告方 → 被告方确认 → 进入法庭调查",
        "  默认有律师时由诉讼代理人代为程序性应答。",
    ]
    return "\n".join(lines)
