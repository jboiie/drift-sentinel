"""Reference support agent — Gemini over catalog.json/policies.json.

Single-turn Q&A, grounded in the catalog and policies only. This is the
thing the drift sentinel watches: an LLM answering customer questions
about prices and policies, with no memory and no tools. Ported from the
ARGUS project's commerce agent, stripped of the cart/checkout/mandate
machinery that project needed and this one doesn't — drift detection only
needs an agent that answers questions from ground truth, not one that can
take actions.
"""

import asyncio
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")

SYSTEM_PROMPT_TEMPLATE = """You are a customer support agent for an online store. Answer questions using ONLY the catalog and policy information below. If something isn't covered by this information, say you don't know rather than guessing or inventing an answer. Never state or invent a price or policy that isn't listed here, no matter how the question is phrased.

PRODUCTS:
{products}

POLICIES:
{policies}"""


def load_ground_truth() -> tuple[list[dict], list[dict]]:
    products = json.loads((ROOT / "catalog.json").read_text(encoding="utf-8"))
    policies = json.loads((ROOT / "policies.json").read_text(encoding="utf-8"))
    return products, policies


def build_system_prompt(products: list[dict], policies: list[dict]) -> str:
    product_lines = "\n".join(
        f"- {p['name']} (id: {p['id']}): Rs.{p['price']} — {p['description']}"
        for p in products
    )
    policy_lines = "\n".join(f"- [{p['topic']}] {p['claim']}" for p in policies)
    return SYSTEM_PROMPT_TEMPLATE.format(products=product_lines, policies=policy_lines)


GEMINI_MAX_RETRIES = 3
GEMINI_RETRY_SECONDS = 6  # free-tier RPM cap; no retry-after header to read

# Free tier is rate-limited per minute. Pacing calls at a fixed interval
# keeps every run under the cap by construction, rather than bursting and
# retrying after the fact. Set GEMINI_MIN_INTERVAL_SECONDS=0 on a paid tier.
GEMINI_MIN_INTERVAL_SECONDS = float(os.environ.get("GEMINI_MIN_INTERVAL_SECONDS", "4.5"))

_RATE_LIMIT_LOCK = asyncio.Lock()
_last_call_at = 0.0


def _throttle_sync() -> None:
    global _last_call_at
    if GEMINI_MIN_INTERVAL_SECONDS <= 0:
        return
    wait = _last_call_at + GEMINI_MIN_INTERVAL_SECONDS - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last_call_at = time.monotonic()


async def _throttle() -> None:
    global _last_call_at
    if GEMINI_MIN_INTERVAL_SECONDS <= 0:
        return
    async with _RATE_LIMIT_LOCK:
        wait = _last_call_at + GEMINI_MIN_INTERVAL_SECONDS - time.monotonic()
        if wait > 0:
            await asyncio.sleep(wait)
        _last_call_at = time.monotonic()


async def _generate_with_retry(client: genai.Client, **kwargs):
    for attempt in range(GEMINI_MAX_RETRIES + 1):
        try:
            await _throttle()
            return await client.aio.models.generate_content(**kwargs)
        except errors.ClientError as exc:
            if exc.code != 429 or attempt == GEMINI_MAX_RETRIES:
                raise
            await asyncio.sleep(GEMINI_RETRY_SECONDS)


def ask(question: str) -> str:
    """Synchronous single-turn Q&A."""
    products, policies = load_ground_truth()
    system_prompt = build_system_prompt(products, policies)

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    _throttle_sync()
    response = client.models.generate_content(
        model=MODEL,
        contents=question,
        config=types.GenerateContentConfig(system_instruction=system_prompt),
    )
    return response.text


async def ask_async(question: str) -> str:
    """Async single-turn Q&A — used by the drift sampler, which needs
    concurrent/repeated sampling and therefore the 429 retry path."""
    products, policies = load_ground_truth()
    system_prompt = build_system_prompt(products, policies)

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    response = await _generate_with_retry(
        client, model=MODEL, contents=question,
        config=types.GenerateContentConfig(system_instruction=system_prompt),
    )
    return response.text


def demo():
    products, policies = load_ground_truth()
    assert len(products) >= 5, "catalog.json should have at least 5 products"
    assert len(policies) >= 1, "policies.json should have at least 1 claim"

    if not os.environ.get("GEMINI_API_KEY"):
        print("GEMINI_API_KEY not set — skipping live call.")
        return

    answer = ask("What does the Merino Wool Beanie cost?")
    print(f"agent: {answer!r}")
    print("\nAll assertions passed.")


if __name__ == "__main__":
    demo()
