"""llm.py — single place for Claude API calls + robust JSON parsing.

Key is read from env var ANTHROPIC_API_KEY or .streamlit/secrets.toml.
(The old ai_engine.py sent NO api key, so every call failed outside claude.ai artifacts.)
"""
from __future__ import annotations
import json
import os
import re
import urllib.request

MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")


def _api_key() -> str | None:
    key = os.getenv("ANTHROPIC_API_KEY")
    if key:
        return key
    try:
        import streamlit as st
        return st.secrets.get("ANTHROPIC_API_KEY")
    except Exception:
        return None


def llm_available() -> bool:
    return bool(_api_key())


def call_claude(prompt: str, system: str = "", max_tokens: int = 1500) -> str:
    key = _api_key()
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set (env var or .streamlit/secrets.toml)")
    body = json.dumps({
        "model": MODEL,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read())
    return "".join(b.get("text", "") for b in data["content"] if b.get("type") == "text")


def parse_json(raw: str):
    """Extract the first JSON object/array from a model reply (handles ``` fences)."""
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    m = re.search(r"[\[{]", raw)
    if not m:
        raise ValueError("No JSON found in model reply")
    end = max(raw.rfind("}"), raw.rfind("]"))
    return json.loads(raw[m.start(): end + 1])
