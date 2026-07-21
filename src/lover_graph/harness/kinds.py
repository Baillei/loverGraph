"""Harness 节点分类 — MODEL 与确定性节点分离。"""

from __future__ import annotations

from enum import Enum


class NodeKind(str, Enum):
    """LangGraph 节点类型（harness 工程分层）。"""

    SCRIPT = "script"  # 固定台词，无 LLM
    DETERMINISTIC = "deterministic"  # 规则/工具/路由，无 LLM
    MODEL = "model"  # 思考智能体，调用 LLM structured output
    MODEL_BATCH = "model_batch"  # 单次 LLM 批量生成（如判决）


# 节点注册表（编译期文档 + 运行时校验）
NODE_REGISTRY: dict[str, NodeKind] = {
    "opening_ceremony": NodeKind.SCRIPT,
    "phase_controller": NodeKind.DETERMINISTIC,
    "harness_coach": NodeKind.DETERMINISTIC,
    "route_hub": NodeKind.DETERMINISTIC,
    "matchmaker": NodeKind.MODEL,
    "male": NodeKind.MODEL,
    "male_parents": NodeKind.MODEL,
    "female": NodeKind.MODEL,
    "female_parents": NodeKind.MODEL,
    "discipline_validator": NodeKind.DETERMINISTIC,
    "matchmaker_discipline": NodeKind.SCRIPT,
    "closing": NodeKind.DETERMINISTIC,
    "verdict": NodeKind.MODEL_BATCH,
}
