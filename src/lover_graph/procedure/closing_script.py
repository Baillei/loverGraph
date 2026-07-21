"""Fixed professional closing ceremony before verdict."""

from __future__ import annotations

from lover_graph.constraints import compute_budget
from lover_graph.graph.state import SessionState
from lover_graph.schemas import ROLE_TO_SPEAKER, SessionInput, DialogueTurn, Phase, Role


def build_closing_ceremony(state: SessionState) -> list[DialogueTurn]:
    """Inject fixed closing lines when trial must end without full LLM closing."""
    case: SessionInput = state["session_input"]
    snap = compute_budget(state)
    phases = "、".join(snap.phases_seen) or "法庭调查"
    missing = snap.phases_missing
    if missing:
        phase_intro = f"本案已历经{phases}。"
    else:
        phase_intro = "法庭调查、举证质证、法庭辩论等程序阶段已进行完毕。"
    matchmaker = case.matchmaker_name

    turns: list[DialogueTurn] = []

    def _turn(role: Role, name: str, text: str) -> DialogueTurn:
        return DialogueTurn(
            speaker=ROLE_TO_SPEAKER[role].value,
            role=role,
            role_name=name,
            phase=Phase.CLOSING,
            text=text,
            think="（固定收尾程序台词。）",
            skills_used=["fixed_ceremony"],
            emotion={"confidence": 0.85},
        )

    turns.append(
        _turn(
            Role.MATCHMAKER,
            matchmaker,
            f"{phase_intro}"
            f"现在由双方当事人作最后陈述。请原告方作最后陈述。",
        )
    )

    if case.male.has_lawyer:
        turns.append(
            _turn(
                Role.MALE_PARENTS,
                case.male.lawyer_name or f"{case.male.name}律师",
                "审判员，我方最后陈述如下：坚持起诉状载明的诉讼请求及事实理由，"
                "请求法庭依法支持原告的全部诉请。",
            )
        )
    else:
        turns.append(
            _turn(
                Role.MALE,
                case.male.name,
                "我坚持起诉状上的诉讼请求，请法庭支持。",
            )
        )

    turns.append(
        _turn(
            Role.MATCHMAKER,
            matchmaker,
            "请被告方作最后陈述。",
        )
    )

    if case.female.has_lawyer:
        turns.append(
            _turn(
                Role.FEMALE_PARENTS,
                case.female.lawyer_name or f"{case.female.name}律师",
                "审判员，我方最后陈述如下：请求法庭依法驳回原告不合理的诉讼请求，"
                "维护被告的合法权益。",
            )
        )
    else:
        turns.append(
            _turn(
                Role.FEMALE,
                case.female.name,
                "我不同意原告的诉讼请求，请法庭驳回。",
            )
        )

    turns.append(
        _turn(
            Role.MATCHMAKER,
            matchmaker,
            "各方最后陈述完毕。本案法庭审理终结，现在休庭。经评议，现在当庭宣判。",
        )
    )
    return turns
