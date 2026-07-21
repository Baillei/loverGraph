#!/usr/bin/env python3
"""Quick DeepSeek / LLM connectivity test."""

import sys

from lover_graph.llm.client import LLMClient
from lover_graph.settings import get_settings


def main() -> None:
    s = get_settings()
    if s.platform == "deepseek" and not s.deepseek_api_key:
        print("ERROR: 请在 config/api_keys_local.py 填入 DEEPSEEK_API_KEY")
        sys.exit(1)

    print(f"Platform: {s.platform}")
    print(f"Model: {s.model}")
    print(f"Base URL: {s.deepseek_base_url if s.platform == 'deepseek' else s.openai_base_url}")
    print("Calling API...")

    llm = LLMClient()
    reply = llm.generate("你是助手。", "回复两个字：成功")
    print(f"Reply: {reply}")
    print("OK — API 连通")


if __name__ == "__main__":
    main()
