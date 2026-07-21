"""Local matchmaker contract retriever — no external API."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from lover_graph.settings import get_settings


@dataclass
class ContractClause:
    id: str
    source: str
    section: str
    title: str
    text: str
    tags: list[str]
    score: float = 0.0

    def cite(self) -> str:
        return f"《{self.source}》{self.section}"


class ContractRetriever:
    def __init__(self, contracts_dir: Path | None = None) -> None:
        settings = get_settings()
        self.contracts_dir = contracts_dir or (settings.data_dir / "contracts")
        self._clauses: list[ContractClause] = []
        self._load()

    def _load(self) -> None:
        if not self.contracts_dir.exists():
            return
        for path in sorted(self.contracts_dir.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            for item in data.get("articles", []):
                self._clauses.append(
                    ContractClause(
                        id=item["id"],
                        source=item.get("law", item.get("source", "媒婆服务合约")),
                        section=item.get("article", item.get("section", "")),
                        title=item.get("title", ""),
                        text=item["text"],
                        tags=item.get("tags", []),
                    )
                )

    def search(self, query: str, top_k: int = 3) -> list[ContractClause]:
        if not query.strip():
            return []
        tokens = self._tokenize(query)
        scored: list[ContractClause] = []
        for art in self._clauses:
            hay = f"{art.source} {art.section} {art.title} {art.text} {' '.join(art.tags)}"
            score = sum(1.0 for t in tokens if t in hay)
            if score > 0:
                scored.append(
                    ContractClause(
                        id=art.id,
                        source=art.source,
                        section=art.section,
                        title=art.title,
                        text=art.text,
                        tags=art.tags,
                        score=score,
                    )
                )
        scored.sort(key=lambda a: a.score, reverse=True)
        return scored[:top_k]

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        text = text.lower()
        chunks = re.findall(r"[\u4e00-\u9fff]{2,}|[a-z0-9]+", text)
        extras = []
        for kw in ("五金", "饭钱", "归还", "违法", "彩礼", "条件", "家长", "节奏", "散场", "结婚"):
            if kw in text:
                extras.append(kw)
        return list(dict.fromkeys(chunks + extras))

    def format_results(self, results: list[ContractClause]) -> str:
        if not results:
            return "（未检索到相关合约条款）"
        lines = []
        for r in results:
            lines.append(f"- {r.cite()} {r.title}：{r.text}")
        return "\n".join(lines)
