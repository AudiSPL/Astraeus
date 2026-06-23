"""Astraeus agent. Calls the deterministic calc API, enforces the validation
gate IN CODE (the LLM is never asked to police itself), then sends the validated
packet to an LLM for interpretation.

Env:
  ASTRAEUS_CALC_URL   default http://localhost:8080
  ASTRAEUS_API_KEY    only if the calc service has auth enabled
  ASTRAEUS_LLM        anthropic | openai   (default anthropic)
  ASTRAEUS_MODEL      model id (default claude-sonnet-4-6 / gpt-4o)
  ANTHROPIC_API_KEY / OPENAI_API_KEY   provider key
"""
import os
import json

import httpx

from .prompt import SYSTEM_PROMPT

CALC_URL = os.environ.get("ASTRAEUS_CALC_URL", "http://localhost:8080")
CALC_KEY = os.environ.get("ASTRAEUS_API_KEY")


class NotValidated(Exception):
    """Raised when the packet is not safe to interpret. Carries the reasons so
    the surface can tell the user exactly what is missing."""
    def __init__(self, reasons):
        self.reasons = reasons or ["chart not validated"]
        super().__init__("; ".join(self.reasons))


def fetch_packet(payload: dict) -> dict:
    headers = {}
    if CALC_KEY:
        headers["Authorization"] = f"Bearer {CALC_KEY}"
    r = httpx.post(f"{CALC_URL}/v1/chart-packet", json=payload, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()


def get_reading(payload: dict, question: str | None = None) -> dict:
    """Returns {"reading": str, "packet": dict}. Raises NotValidated if the gate
    fails (LLM is NOT called in that case)."""
    packet = fetch_packet(payload)
    v = packet["validation"]

    # ---- HARD GATE (code, not prompt) ----
    if not v["validated_for_interpretation"]:
        raise NotValidated(v.get("reasons", []))

    user_msg = "Here is the validated chart packet. Interpret it.\n\n"
    if question:
        user_msg += f"The person's question: {question}\n\n"
    user_msg += "```json\n" + json.dumps(packet, ensure_ascii=False, indent=2) + "\n```"

    reading = call_llm(SYSTEM_PROMPT, user_msg)
    return {"reading": reading, "packet": packet}


# ---- LLM provider (swap here) ----
def call_llm(system: str, user: str) -> str:
    provider = os.environ.get("ASTRAEUS_LLM", "anthropic")

    if provider == "anthropic":
        from anthropic import Anthropic
        client = Anthropic()  # reads ANTHROPIC_API_KEY
        resp = client.messages.create(
            model=os.environ.get("ASTRAEUS_MODEL", "claude-sonnet-4-6"),
            max_tokens=2000,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in resp.content if b.type == "text")

    if provider == "openai":
        from openai import OpenAI
        client = OpenAI()  # reads OPENAI_API_KEY
        resp = client.chat.completions.create(
            model=os.environ.get("ASTRAEUS_MODEL", "gpt-4o"),
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
        )
        return resp.choices[0].message.content

    raise ValueError(f"unknown ASTRAEUS_LLM provider: {provider}")
