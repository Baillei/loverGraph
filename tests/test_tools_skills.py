from lover_graph.schemas import Phase, Role
from lover_graph.skills import run_skills
from lover_graph.tools import TraitDB, ContractRetriever, ProcedureRules


def test_contract_retriever_finds_rental_articles():
    r = ContractRetriever()
    hits = r.search("房屋租赁 租金支付", top_k=3)
    assert len(hits) >= 1
    assert any("租赁" in h.text for h in hits)


def test_trait_db_loads_sample_case():
    db = TraitDB()
    items = db.list_by_case("（2019）浙0702民初5398号")
    assert len(items) >= 4
    assert any(e.id == "P-E1" for e in items)


def test_procedure_rules():
    p = ProcedureRules()
    rules = p.get_phase_rules("investigation")
    assert len(rules) >= 2


def test_matchmaker_skills_invoke_tools():
    from lover_graph.graph.lover_graph import build_initial_state
    from lover_graph.scenario import generate_random_scenario, scenario_to_session_input
    from lover_graph.schemas.behavior_constraints import SimulationDefaults

    scenario = generate_random_scenario(SimulationDefaults(), seed=1)
    case = scenario_to_session_input(scenario)
    state = build_initial_state(case, scenario)

    ctx, tools, skills = run_skills(
        Role.MATCHMAKER,
        Phase.EVIDENCE,
        case.session_id,
        case.title,
        ["责任划分", "损失金额"],
        round_no=0,
        state=state,
    )
    assert "session_clock" in skills
    assert "contract_rag" in skills
    assert len(tools) >= 3
    assert "庭审倒计时" in ctx
