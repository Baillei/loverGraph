"""CLI entry point."""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from lover_graph.constraints.budget import validate_budget_inputs
from lover_graph.graph.lover_graph import build_graph, build_initial_state
from lover_graph.scenario import (
    SimulationDefaults,
    apply_constraint_overrides,
    generate_random_scenario,
    load_scenario,
    print_scenario_brief,
    scenario_to_session_input,
)
from lover_graph.constraints import get_constraints
from lover_graph.output.builder import build_trial_output
from lover_graph.output.compliance import build_compliance_report
from lover_graph.output.jsonl_writer import write_trial_jsonl
from lover_graph.graph.finalize import ensure_trial_closed
from lover_graph.procedure.defaults_report import format_defaults_report
from lover_graph.schemas.trial_constraints import BudgetMode
from lover_graph.settings import get_settings

DEFAULT_SCENARIO = None  # 默认随机生成，不对齐任何真实/GT 案件


def _has_api_key(settings) -> bool:
    if settings.platform == "deepseek":
        return bool(settings.deepseek_api_key)
    if settings.platform == "openai":
        return bool(settings.openai_api_key)
    if settings.platform == "ali":
        return bool(settings.ali_api_key)
    return False


def _build_simulation_defaults(args) -> SimulationDefaults:
    wpm = args.words_per_minute or 200
    mode = validate_budget_inputs(
        budget_mode=BudgetMode(args.budget_mode) if args.budget_mode else None,
        max_rounds=args.max_rounds,
        word_count=args.word_count,
        duration_minutes=args.duration_minutes,
    )
    if mode == BudgetMode.MATCHMAKER_TURNS:
        return SimulationDefaults(
            budget_mode=mode,
            max_rounds=args.max_rounds or 25,
            words_per_minute=wpm,
            random_seed=args.seed,
        )
    if args.duration_minutes is not None:
        duration = args.duration_minutes
    elif args.word_count is not None:
        duration = args.word_count / wpm
    else:
        duration = 5.0
    return SimulationDefaults(
        budget_mode=mode,
        duration_minutes=duration,
        words_per_minute=wpm,
        random_seed=args.seed,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="venueGraph 庭审模拟 — 从场景 JSON 入口启动",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  lover-sim --show-scenario                    # 随机背景预览（默认）
  lover-sim --scenario path/to/custom.json       # 自定义场景文件
  lover-sim --dry-run                          # 验证图编译

预算（二选一，不可混用）:
  lover-sim -y --budget-mode matchmaker_turns --max-rounds 25
  lover-sim -y --budget-mode time --duration-minutes 40
  lover-sim -y --budget-mode time --word-count 8000
        """,
    )
    parser.add_argument(
        "--scenario",
        default=None,
        help=f"固定场景 JSON（指定则不用随机；默认随机生成）",
    )
    parser.add_argument(
        "--random",
        action="store_true",
        help="强制随机生成背景",
    )
    parser.add_argument(
        "--no-random",
        action="store_true",
        help="使用固定场景文件，不随机生成",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="随机场景种子",
    )
    parser.add_argument(
        "--show-scenario",
        action="store_true",
        help="仅展示场景背景（5W1H、证据布局、价值张力），不开庭",
    )
    parser.add_argument(
        "--show-defaults",
        action="store_true",
        help="展示默认外置参数（轮次、词数预算、律师、纪律等）",
    )
    parser.add_argument("--yes", "-y", action="store_true", help="跳过「按 Enter 开庭」确认")
    parser.add_argument("--dry-run", action="store_true", help="仅编译图，不调用 LLM")
    parser.add_argument(
        "--max-steps",
        type=int,
        default=500,
        help="LangGraph 最大步数（默认 500，不作为庭审截断预算）",
    )
    parser.add_argument(
        "--budget-mode",
        choices=["matchmaker_turns", "time"],
        default=None,
        help="预算维度：matchmaker_turns=法官发言轮数；time=词数/时长（二选一）",
    )
    parser.add_argument(
        "--duration-minutes",
        type=float,
        default=None,
        help="time 模式：庭审总时长（分钟）",
    )
    parser.add_argument(
        "--word-count",
        type=int,
        default=None,
        help="time 模式：庭审总词数上限（与 --duration-minutes 二选一）",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=None,
        help="matchmaker_turns 模式：法官发言次数上限",
    )
    parser.add_argument(
        "--words-per-minute",
        type=int,
        default=None,
        help="time 模式语速（字/分），用于词数↔时长换算",
    )
    args = parser.parse_args()

    if args.show_defaults:
        print(format_defaults_report())
        return

    settings = get_settings()

    try:
        defaults = _build_simulation_defaults(args)
    except ValueError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    use_random = not args.no_random and (args.random or args.scenario is None)
    if use_random:
        scenario = generate_random_scenario(defaults, seed=args.seed)
    else:
        if not args.scenario:
            print("ERROR: 请使用随机模式（默认）或 --scenario 指定场景文件")
            sys.exit(1)
        path = args.scenario
        try:
            scenario = load_scenario(path)
        except FileNotFoundError:
            print(f"ERROR: 场景文件不存在: {path}")
            sys.exit(1)
        except Exception as e:
            print(f"ERROR: 场景 JSON 校验失败: {e}")
            sys.exit(1)
        scenario = apply_constraint_overrides(
            scenario,
            budget_mode=defaults.budget_mode,
            word_count_limit=defaults.derived_word_count_limit() if defaults.budget_mode == BudgetMode.TIME else None,
            max_rounds=defaults.max_rounds if defaults.budget_mode == BudgetMode.MATCHMAKER_TURNS else None,
            duration_minutes=defaults.duration_minutes if defaults.budget_mode == BudgetMode.TIME else None,
            words_per_minute=defaults.words_per_minute,
        )

    brief = print_scenario_brief(scenario)
    print(brief)

    if args.show_scenario:
        return

    if not args.yes and not args.dry_run:
        try:
            input()
        except KeyboardInterrupt:
            print("\n已取消。")
            sys.exit(0)

    if not args.dry_run and not _has_api_key(settings):
        print("ERROR: 请配置 API Key（.env 或 config/api_keys_local.py）")
        sys.exit(1)

    case = scenario_to_session_input(scenario)
    graph = build_graph()
    state = build_initial_state(case, scenario)

    if args.dry_run:
        print("Graph compiled OK. Nodes:", list(graph.get_graph().nodes))
        print(f"Scenario: {scenario.scenario_id}")
        print(f"Budget mode: {defaults.budget_mode.value}")
        return

    print(f"\n开庭：{case.title}")
    print(f"LLM: {settings.platform} / {settings.model}")
    print(f"预算：{defaults.budget_synopsis()}\n")

    event = state
    last_dialogue_count = 0
    steps_executed = 0
    for step, event in enumerate(graph.stream(state, stream_mode="values")):
        steps_executed = step + 1
        if step >= args.max_steps:
            break
        dialogues = event.get("dialogues", [])
        if len(dialogues) > last_dialogue_count:
            for turn in dialogues[last_dialogue_count:]:
                print(f"[{turn.phase.value}] {turn.role_name}: {turn.text[:120]}")
            last_dialogue_count = len(dialogues)

    event = ensure_trial_closed(event, run_verdict=True)
    if len(event.get("dialogues", [])) > last_dialogue_count:
        for turn in event["dialogues"][last_dialogue_count:]:
            print(f"[{turn.phase.value}] {turn.role_name}: {turn.text[:120]}")

    script = build_trial_output(event)
    compliance = build_compliance_report(
        event,
        get_constraints(event),
        max_steps=args.max_steps,
        steps_executed=steps_executed,
    )

    out_dir = settings.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"{scenario.scenario_id}_{ts}.jsonl"
    write_trial_jsonl(out_path, script, compliance=compliance)
    print(f"\n庭审记录已保存: {out_path}")
    print(f"达标审计 overall_pass={compliance['overall_pass']}")
    if script.verdict:
        print(f"判决结果: {script.verdict.final_result[:200]}")


if __name__ == "__main__":
    main()
