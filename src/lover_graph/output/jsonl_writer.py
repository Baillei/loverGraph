"""Write trial output as JSONL — one record per line."""

from __future__ import annotations

import json
from pathlib import Path

from lover_graph.schemas.trial_output import SessionScriptOutput


def write_trial_jsonl(
    path: str | Path,
    output: SessionScriptOutput,
    compliance: dict | None = None,
) -> None:
    """Each line is a self-contained JSON object."""
    path = Path(path)
    records: list[dict] = []

    records.append(
        {
            "type": "meta",
            "schema_version": output.schema_version,
            "scenario_id": output.scenario_id,
            "session_id": output.session_id,
            "title": output.title,
            "venue": output.venue,
            "meeting_type": output.meeting_type,
            "metadata": output.metadata.model_dump(mode="json"),
        }
    )

    for p in output.personas:
        records.append({"type": "persona", **p.model_dump(mode="json")})

    for i, turn in enumerate(output.dialogues):
        records.append({"type": "turn", "index": i, **turn.model_dump(mode="json")})

    if output.dispute_tracker.points:
        records.append(
            {
                "type": "dispute_tracker",
                "points": [p.model_dump(mode="json") for p in output.dispute_tracker.points],
            }
        )

    if output.verdict is not None:
        records.append({"type": "verdict", **output.verdict.model_dump(mode="json")})

    records.append(
        {
            "type": "summary",
            "termination": output.metadata.termination,
            "phases_completed": output.metadata.phases_completed,
            "word_count_used": output.metadata.word_count_used,
            "rounds_used": output.metadata.rounds_used,
            "has_verdict": output.verdict is not None,
            "digital_human_assets": {
                "emotion_timeline_count": len(output.digital_human_assets.emotion_timeline),
                "gesture_hints_count": len(output.digital_human_assets.gesture_hints),
            },
        }
    )

    if compliance is not None:
        records.append(compliance)

    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
        encoding="utf-8",
    )
