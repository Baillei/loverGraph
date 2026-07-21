"""Self-contained LLM client for venueGraph — no parent-repo imports."""

from __future__ import annotations

import json
import re
from typing import TypeVar

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from lover_graph.settings import get_settings

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    def __init__(self, platform: str | None = None, model: str | None = None) -> None:
        settings = get_settings()
        self.platform = platform or settings.platform
        self.model = model or settings.model
        self._chat = self._build_chat(settings)

    def _build_chat(self, settings) -> ChatOpenAI:
        if self.platform == "deepseek":
            return ChatOpenAI(
                model=self.model,
                api_key=settings.deepseek_api_key or None,
                base_url=settings.deepseek_base_url.rstrip("/") + "/v1",
                temperature=0.7,
            )
        if self.platform == "openai":
            kwargs: dict = {
                "model": self.model,
                "api_key": settings.openai_api_key or None,
                "temperature": 0.7,
            }
            if settings.openai_base_url:
                kwargs["base_url"] = settings.openai_base_url
            return ChatOpenAI(**kwargs)
        if self.platform == "ali":
            return ChatOpenAI(
                model=self.model,
                api_key=settings.ali_api_key,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                temperature=0.7,
            )
        raise ValueError(f"Unsupported platform: {self.platform}. Configure in config/api_keys_local.py")

    def generate(self, system: str, user: str) -> str:
        msgs = [SystemMessage(content=system), HumanMessage(content=user)]
        resp = self._chat.invoke(msgs)
        return str(resp.content)

    def generate_structured(self, system: str, user: str, schema: type[T]) -> T:
        """Parse JSON from LLM into a Pydantic model."""
        schema_hint = json.dumps(schema.model_json_schema(), ensure_ascii=False, indent=2)
        prompt = (
            f"{user}\n\n"
            "Respond with a single JSON object only, no markdown fences.\n"
            f"Schema:\n{schema_hint}"
        )
        raw = self.generate(system, prompt)
        data = self._extract_json(raw)
        return schema.model_validate(data)

    @staticmethod
    def _extract_json(text: str) -> dict:
        text = text.strip()
        fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
        if fence:
            text = fence.group(1)
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
        return json.loads(text)
