"""Profile trait database for matchmaking sessions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from lover_graph.settings import get_settings


@dataclass
class TraitRecord:
    id: str
    party: str
    name: str
    type: str
    description: str
    visibility: str
    dispute: str


class TraitDB:
    def __init__(self, traits_dir: Path | None = None) -> None:
        settings = get_settings()
        self.traits_dir = traits_dir or (settings.data_dir / "traits")
        self._by_case: dict[str, list[TraitRecord]] = {}
        self._load()

    def _load(self) -> None:
        if not self.traits_dir.exists():
            return
        for path in sorted(self.traits_dir.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            session_id = data["session_id"]
            items = [
                TraitRecord(
                    id=e["id"],
                    party=e["party"],
                    name=e["name"],
                    type=e["type"],
                    description=e["description"],
                    visibility=e.get("visibility", ""),
                    dispute=e.get("dispute", ""),
                )
                for e in data.get("traits", [])
            ]
            self._by_case[session_id] = items

    def list_by_case(self, session_id: str, party: str | None = None) -> list[TraitRecord]:
        items = self._by_case.get(session_id, [])
        if party:
            return [e for e in items if e.party == party]
        return items

    def get(self, session_id: str, trait_id: str) -> TraitRecord | None:
        for e in self._by_case.get(session_id, []):
            if e.id == trait_id:
                return e
        return None

    def format_list(self, items: list[TraitRecord]) -> str:
        if not items:
            return "（暂无已登记条件）"
        lines = []
        for e in items:
            lines.append(
                f"- [{e.id}|{e.party}] {e.name}（{e.type}）：{e.description}；"
                f"可见性：{e.visibility or '未标注'}；疑点：{e.dispute or '无'}"
            )
        return "\n".join(lines)
