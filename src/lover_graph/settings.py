"""Settings — API keys from loverGraph/config/ first, then env."""

from __future__ import annotations

import importlib.util
import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# loverGraph project root (parent of src/)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"


def _load_local_keys() -> dict[str, str]:
    local = CONFIG_DIR / "api_keys_local.py"
    if not local.exists():
        return {}
    spec = importlib.util.spec_from_file_location("venuegraph_api_keys_local", local)
    if spec is None or spec.loader is None:
        return {}
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return {k: v for k, v in vars(mod).items() if k.isupper() and isinstance(v, str)}


_LOCAL_KEYS = _load_local_keys()


def _resolve(name: str, default: str = "") -> str:
    return os.getenv(name) or _LOCAL_KEYS.get(name, default)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    platform: str = Field(default_factory=lambda: _resolve("LOVERGRAPH_PLATFORM", "deepseek"))
    model: str = Field(default_factory=lambda: _resolve("LOVERGRAPH_MODEL", "deepseek-chat"))

    deepseek_api_key: str = Field(default_factory=lambda: _resolve("DEEPSEEK_API_KEY"))
    deepseek_base_url: str = Field(
        default_factory=lambda: _resolve("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    )
    openai_api_key: str = Field(default_factory=lambda: _resolve("OPENAI_API_KEY"))
    openai_base_url: str = Field(default_factory=lambda: _resolve("OPENAI_BASE_URL"))
    ali_api_key: str = Field(default_factory=lambda: _resolve("ALI_API_KEY"))
    google_api_key: str = Field(default_factory=lambda: _resolve("GOOGLE_API_KEY"))

    max_rounds: int = 40
    data_dir: Path = PROJECT_ROOT / "data"
    prompts_dir: Path = PROJECT_ROOT / "prompts"
    output_dir: Path = PROJECT_ROOT / "data" / "output"


@lru_cache
def get_settings() -> Settings:
    return Settings()
