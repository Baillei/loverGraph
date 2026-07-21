#!/usr/bin/env python3
"""Offline check: tools, skills — uses random fixture, not GT case."""

from lover_graph.scenario import generate_random_scenario
from lover_graph.schemas import Phase, Role
from lover_graph.schemas.behavior_constraints import SimulationDefaults
from lover_graph.skills import run_skills
from lover_graph.tools import TraitDB, ContractRetriever, ProcedureRules

SCENARIO = generate_random_scenario(SimulationDefaults(), seed=99)


def main() -> None:
    print("=== Law Retriever ===")
    law = ContractRetriever()
    hits = law.search("合同 证据", top_k=2)
    for h in hits:
        print(f"  {h.cite()} — {h.title}")

    print("\n=== Random scenario ===")
    print(f"  id={SCENARIO.scenario_id}")
    print(f"  lawyers: PL={SCENARIO.simulation.male_has_lawyer} DL={SCENARIO.simulation.female_has_lawyer}")

    print("\n=== Procedure Rules ===")
    print(ProcedureRules().format_phase("evidence"))

    ctx, tools, skills = run_skills(
        Role.MATCHMAKER, Phase.EVIDENCE, SCENARIO.scenario_id,
        SCENARIO.narrative.title, SCENARIO.tension_points, 1,
    )
    print("\n=== Skills ===", skills, "tools", len(tools))


if __name__ == "__main__":
    main()
