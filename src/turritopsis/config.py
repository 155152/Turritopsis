from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


DATA_RELATIVE = Path(".turritopsis") / "stages.json"
CONFIG_RELATIVE = Path(".turritopsis") / "config.json"


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    model: str
    api_key_env: str
    base_url: str
    timeout: float = 120.0
    max_tokens: int = 4096

    def api_key(self, environ: Mapping[str, str] | None = None) -> str:
        source = environ if environ is not None else os.environ
        value = source.get(self.api_key_env, "").strip()
        if not value:
            raise ValueError(
                f"LLM API key environment variable is not set: {self.api_key_env}"
            )
        return value


def _config_path(data_path: Path | None = None, project_root: Path | None = None) -> Path:
    if data_path is not None:
        return Path(data_path).resolve().parent / "config.json"
    return Path(project_root or Path.cwd()).resolve() / CONFIG_RELATIVE


def load_llm_config(
    data_path: Path | None = None,
    project_root: Path | None = None,
    model_override: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> LLMConfig:
    """Load scan/maintenance LLM settings without exposing the API key."""
    env = environ if environ is not None else os.environ
    path = _config_path(data_path, project_root)
    document: dict = {}
    if path.is_file():
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid JSON in {path}: {error}") from error
    llm = document.get("llm", {})
    if llm and not isinstance(llm, dict):
        raise ValueError(f"llm must be an object in {path}")

    provider = str(env.get("TURRITOPSIS_LLM_PROVIDER") or llm.get("provider") or "openai").lower().strip()
    aliases = {"compatible": "openai-compatible", "openai_compatible": "openai-compatible"}
    provider = aliases.get(provider, provider)
    if provider not in {"openai", "anthropic", "openai-compatible"}:
        raise ValueError("llm.provider must be openai, anthropic, or openai-compatible")
    model = str(model_override or env.get("TURRITOPSIS_LLM_MODEL") or llm.get("model") or "").strip()
    if not model:
        raise ValueError(
            f"No LLM model configured. Set llm.model in {path} or TURRITOPSIS_LLM_MODEL."
        )
    default_key = "ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY"
    api_key_env = str(env.get("TURRITOPSIS_LLM_API_KEY_ENV") or llm.get("api_key_env") or default_key).strip()
    defaults = {
        "openai": "https://api.openai.com/v1",
        "anthropic": "https://api.anthropic.com/v1",
        "openai-compatible": "",
    }
    base_url = str(env.get("TURRITOPSIS_LLM_BASE_URL") or llm.get("base_url") or defaults[provider]).rstrip("/")
    if not base_url:
        raise ValueError(
            f"No LLM base_url configured for {provider}. Set llm.base_url in {path}."
        )
    timeout = float(env.get("TURRITOPSIS_LLM_TIMEOUT") or llm.get("timeout") or 120)
    max_tokens = int(env.get("TURRITOPSIS_LLM_MAX_TOKENS") or llm.get("max_tokens") or 4096)
    if timeout <= 0 or max_tokens <= 0:
        raise ValueError("llm.timeout and llm.max_tokens must be positive")
    return LLMConfig(provider, model, api_key_env, base_url, timeout, max_tokens)


def discover_data(start: str | os.PathLike[str] | None = None) -> Path:
    """Find .turritopsis/stages.json from *start* upward."""
    env = os.environ.get("TURRITOPSIS_DATA")
    if env:
        path = Path(env).expanduser().resolve()
        if path.is_file():
            return path
        raise FileNotFoundError(f"TURRITOPSIS_DATA does not exist: {path}")

    origin = Path(start or Path.cwd()).expanduser().resolve()
    if origin.is_file():
        origin = origin.parent
    for directory in (origin, *origin.parents):
        candidate = directory / DATA_RELATIVE
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"No {DATA_RELATIVE.as_posix()} found from {origin} upward. "
        "Run 'turritopsis init' or pass --data."
    )


def resolve_data(path: str | os.PathLike[str] | None = None) -> Path:
    if path:
        candidate = Path(path).expanduser().resolve()
        if not candidate.is_file():
            raise FileNotFoundError(f"Data file does not exist: {candidate}")
        return candidate
    return discover_data()
