from __future__ import annotations

import json
import re
from typing import Any

import httpx

from .config import LLMConfig


class LLMError(RuntimeError):
    pass


def _json_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(
            str(item.get("text", "")) for item in value
            if isinstance(item, dict) and item.get("type") in {"text", "output_text"}
        )
    return ""


def _parse_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.I)
    if fenced:
        cleaned = fenced.group(1).strip()
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end <= start:
            raise LLMError("LLM response did not contain a JSON object")
        try:
            value = json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError as error:
            raise LLMError(f"LLM returned invalid JSON: {error}") from error
    if not isinstance(value, dict):
        raise LLMError("LLM response must be a JSON object")
    return value


def validate_json(value: Any, schema: dict[str, Any], path: str = "$") -> None:
    """Validate the small JSON Schema subset used by Turritopsis prompts."""
    expected = schema.get("type")
    checks = {
        "object": lambda item: isinstance(item, dict),
        "array": lambda item: isinstance(item, list),
        "string": lambda item: isinstance(item, str),
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "boolean": lambda item: isinstance(item, bool),
    }
    if expected in checks and not checks[expected](value):
        raise LLMError(f"Invalid LLM JSON at {path}: expected {expected}")
    if "enum" in schema and value not in schema["enum"]:
        raise LLMError(f"Invalid LLM JSON at {path}: expected one of {schema['enum']}")
    if expected == "object":
        properties = schema.get("properties", {})
        missing = [key for key in schema.get("required", []) if key not in value]
        if missing:
            raise LLMError(f"Invalid LLM JSON at {path}: missing {', '.join(missing)}")
        if schema.get("additionalProperties") is False:
            extra = sorted(set(value) - set(properties))
            if extra:
                raise LLMError(f"Invalid LLM JSON at {path}: unexpected {', '.join(extra)}")
        for key, child in value.items():
            if key in properties:
                validate_json(child, properties[key], f"{path}.{key}")
    elif expected == "array":
        for index, child in enumerate(value):
            validate_json(child, schema.get("items", {}), f"{path}[{index}]")


class LLMClient:
    def __init__(self, config: LLMConfig, transport: httpx.BaseTransport | None = None):
        self.config = config
        self._transport = transport

    def complete_json(
        self,
        system: str,
        prompt: str,
        schema: dict[str, Any],
        schema_name: str,
    ) -> dict[str, Any]:
        provider = self.config.provider
        key = self.config.api_key()
        headers = {"content-type": "application/json"}
        if provider == "anthropic":
            url = f"{self.config.base_url}/messages"
            headers.update({"x-api-key": key, "anthropic-version": "2023-06-01"})
            payload = {
                "model": self.config.model,
                "max_tokens": self.config.max_tokens,
                "system": system,
                "messages": [{"role": "user", "content": prompt + "\n\nReturn only the requested JSON object."}],
            }
        elif provider == "openai-compatible":
            url = f"{self.config.base_url}/chat/completions"
            headers["authorization"] = f"Bearer {key}"
            payload = {
                "model": self.config.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt + "\n\nReturn only a JSON object matching the requested contract."},
                ],
                "response_format": {"type": "json_object"},
            }
        else:
            url = f"{self.config.base_url}/responses"
            headers["authorization"] = f"Bearer {key}"
            payload = {
                "model": self.config.model,
                "instructions": system,
                "input": prompt,
                "store": False,
                "text": {"format": {
                    "type": "json_schema", "name": schema_name,
                    "schema": schema, "strict": True,
                }},
            }
        try:
            with httpx.Client(timeout=self.config.timeout, transport=self._transport) as client:
                response = client.post(url, headers=headers, json=payload)
                if provider == "openai-compatible" and response.status_code in {400, 422}:
                    fallback = dict(payload)
                    fallback.pop("response_format", None)
                    response = client.post(url, headers=headers, json=fallback)
                response.raise_for_status()
                document = response.json()
        except httpx.HTTPStatusError as error:
            detail = error.response.text[:500].replace(key, "[redacted]")
            raise LLMError(f"{provider} API returned {error.response.status_code}: {detail}") from error
        except (httpx.HTTPError, json.JSONDecodeError) as error:
            raise LLMError(f"{provider} API request failed: {error}") from error

        if provider == "anthropic":
            text = _json_text(document.get("content"))
        elif provider == "openai-compatible":
            choices = document.get("choices") or []
            text = _json_text(choices[0].get("message", {}).get("content")) if choices else ""
        else:
            text = str(document.get("output_text") or "")
            if not text:
                text = "".join(
                    _json_text(item.get("content")) for item in document.get("output", [])
                    if isinstance(item, dict) and item.get("type") == "message"
                )
        result = _parse_json(text)
        validate_json(result, schema)
        return result
