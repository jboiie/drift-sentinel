"""Groq-backed judge model for structured LLM-as-judge calls.

Groq's API is OpenAI-compatible, so this wraps the openai SDK pointed at
Groq's base URL rather than adding a second HTTP client dependency. Ported
from the ARGUS project's red-team harness, trimmed to drop the DeepTeam/
DeepEval base-class dependency — nothing here needs that framework, just
`generate`/`a_generate` with optional structured (schema) output.
"""

import asyncio
import os
import re
import time

from dotenv import load_dotenv
from openai import AsyncOpenAI, BadRequestError, OpenAI, RateLimitError
from pydantic import BaseModel

load_dotenv()

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
# gpt-oss-20b: fits Groq's free-tier TPM budget, supports strict
# json_schema structured outputs (needed for _to_strict_schema below).
DEFAULT_MODEL = os.environ.get("GROQ_JUDGE_MODEL", "openai/gpt-oss-20b")

MAX_COMPLETION_TOKENS = 4096

# All Groq calls on a free-tier key share one TPM budget regardless of how
# many checks run concurrently. Without this, concurrent callers each hit
# 429, each independently retry, and pile back onto the same
# still-recovering budget. One process-wide semaphore serializes actual
# requests, decoupling caller-side concurrency from real API concurrency.
_REQUEST_LOCK = asyncio.Semaphore(1)


def _to_strict_schema(model: type[BaseModel]) -> dict:
    """Pydantic's default model_json_schema() doesn't satisfy Groq's strict
    json_schema requirements (every property in `required`, `additionalProperties:
    false` on every object) — normalize recursively."""
    schema = model.model_json_schema()

    def normalize(node: dict) -> None:
        if node.get("type") == "object" or "properties" in node:
            props = node.get("properties", {})
            node["required"] = list(props.keys())
            node["additionalProperties"] = False
            for prop in props.values():
                normalize(prop)
        if "items" in node:
            normalize(node["items"])
        for variant in node.get("anyOf", []):
            normalize(variant)
        for definition in node.get("$defs", {}).values():
            normalize(definition)

    normalize(schema)
    return schema


_RETRY_AFTER_RE = re.compile(r"try again in ([\d.]+)s", re.IGNORECASE)
MAX_RETRIES = 2


def _is_empty_generation(exc: BadRequestError) -> bool:
    """True for the transient case: Groq's strict-schema mode occasionally
    returns 400 json_validate_failed with a genuinely EMPTY completion — a
    one-off flake worth retrying, not a real refusal. A real refusal also
    fails schema validation but leaves refusal text in failed_generation,
    which must surface as an error, not be retried away."""
    body = exc.body if isinstance(exc.body, dict) else {}
    return body.get("code") == "json_validate_failed" and not (body.get("failed_generation") or "").strip()


def _retry_after_seconds(exc: RateLimitError, default: float = 30.0) -> float:
    header = exc.response.headers.get("retry-after") if exc.response is not None else None
    if header:
        try:
            return float(header)
        except ValueError:
            pass
    match = _RETRY_AFTER_RE.search(str(exc))
    if match:
        return float(match.group(1))
    return default


class GroqModel:
    def __init__(self, model: str = DEFAULT_MODEL):
        self.model_name = model
        api_key = os.environ["GROQ_API_KEY"]
        self._client = OpenAI(api_key=api_key, base_url=GROQ_BASE_URL)
        self._aclient = AsyncOpenAI(api_key=api_key, base_url=GROQ_BASE_URL)

    def _kwargs(self, schema: type[BaseModel] | None) -> dict:
        kwargs = {
            "model": self.model_name,
            "max_tokens": MAX_COMPLETION_TOKENS,
            "extra_body": {"reasoning_format": "hidden"},
        }
        if schema is not None:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": schema.__name__,
                    "strict": True,
                    "schema": _to_strict_schema(schema),
                },
            }
        return kwargs

    def generate(self, prompt: str, schema: type[BaseModel] | None = None):
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = self._client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    **self._kwargs(schema),
                )
                break
            except RateLimitError as exc:
                if attempt == MAX_RETRIES:
                    raise
                time.sleep(_retry_after_seconds(exc) + 1)
            except BadRequestError as exc:
                if attempt == MAX_RETRIES or not _is_empty_generation(exc):
                    raise
        content = response.choices[0].message.content or ""
        return schema.model_validate_json(content) if schema else content

    async def a_generate(self, prompt: str, schema: type[BaseModel] | None = None):
        for attempt in range(MAX_RETRIES + 1):
            try:
                async with _REQUEST_LOCK:
                    response = await self._aclient.chat.completions.create(
                        messages=[{"role": "user", "content": prompt}],
                        **self._kwargs(schema),
                    )
                break
            except RateLimitError as exc:
                if attempt == MAX_RETRIES:
                    raise
                await asyncio.sleep(_retry_after_seconds(exc) + 1)
            except BadRequestError as exc:
                if attempt == MAX_RETRIES or not _is_empty_generation(exc):
                    raise
        content = response.choices[0].message.content or ""
        return schema.model_validate_json(content) if schema else content

    def get_model_name(self) -> str:
        return f"groq/{self.model_name}"


def demo():
    if not os.environ.get("GROQ_API_KEY"):
        print("GROQ_API_KEY not set — skipping live call.")
        return
    model = GroqModel()
    answer = model.generate("Reply with exactly one word: 'ok'.")
    assert answer, "expected a non-empty response"
    print(f"Groq judge model ({model.get_model_name()}) responded:", answer)


if __name__ == "__main__":
    demo()
