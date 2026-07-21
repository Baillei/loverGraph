"""Matchmaking phase rules lookup."""

from __future__ import annotations

import json
from pathlib import Path

from lover_graph.settings import get_settings


class ProcedureRules:
    def __init__(self, procedure_dir: Path | None = None) -> None:
        settings = get_settings()
        path = (procedure_dir or settings.data_dir / "procedure") / "match_phases.json"
        self._data = json.loads(path.read_text(encoding="utf-8"))

    def get_phase_rules(self, phase: str) -> list[str]:
        entry = self._data.get("phases", {}).get(phase)
        if not entry:
            return []
        rules = entry.get("rules", "")
        return [rules] if isinstance(rules, str) else list(rules)

    def format_phase(self, phase: str) -> str:
        entry = self._data.get("phases", {}).get(phase)
        if not entry:
            return f"（未知阶段：{phase}）"
        label = entry.get("label", phase)
        rules = entry.get("rules", "")
        return f"【{label}】\n  - {rules}"
