"""Optional LLM client (backend only). The simulator works fully without it.

Configure in backend/.env (never in the frontend):
    LLM_PROVIDER=anthropic        # "anthropic", "openai" (any OpenAI-compatible API) or "none"
    LLM_API_KEY=...               # your key
    LLM_MODEL=...                 # model name for that provider
    LLM_BASE_URL=                 # optional, only for OpenAI-compatible providers
    LLM_TIMEOUT_SECONDS=15

Uses only the Python standard library (urllib), so no extra package is needed.
complete() NEVER raises: on any problem (no key, timeout, HTTP error, bad JSON) it returns None
and the caller uses its deterministic fallback.
"""
import json
import logging
import os
import urllib.error
import urllib.request
from typing import Optional

log = logging.getLogger("twinmate.llm")

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
OPENAI_DEFAULT_BASE = "https://api.openai.com/v1"


def _settings() -> dict:
    return {
        "provider": os.getenv("LLM_PROVIDER", "none").strip().lower(),
        "api_key": os.getenv("LLM_API_KEY", "").strip(),
        "model": os.getenv("LLM_MODEL", "").strip(),
        "base_url": os.getenv("LLM_BASE_URL", "").strip(),
        "timeout": float(os.getenv("LLM_TIMEOUT_SECONDS", "15") or 15),
    }


def is_configured() -> bool:
    s = _settings()
    return s["provider"] in ("anthropic", "openai") and bool(s["api_key"]) and bool(s["model"])


def model_name() -> Optional[str]:
    return _settings()["model"] if is_configured() else None


def _post(url: str, headers: dict, body: dict, timeout: float) -> dict:
    request = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def complete(system: str, user: str, max_tokens: int = 500) -> Optional[str]:
    """Send one prompt, return the reply text, or None if the LLM is unavailable for any reason."""
    if not is_configured():
        return None
    s = _settings()
    try:
        if s["provider"] == "anthropic":
            data = _post(
                ANTHROPIC_URL,
                {"content-type": "application/json", "x-api-key": s["api_key"], "anthropic-version": "2023-06-01"},
                {"model": s["model"], "max_tokens": max_tokens, "temperature": 0,
                 "system": system, "messages": [{"role": "user", "content": user}]},
                s["timeout"],
            )
            return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip() or None

        base = (s["base_url"] or OPENAI_DEFAULT_BASE).rstrip("/")
        data = _post(
            f"{base}/chat/completions",
            {"content-type": "application/json", "authorization": f"Bearer {s['api_key']}"},
            {"model": s["model"], "max_tokens": max_tokens, "temperature": 0,
             "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]},
            s["timeout"],
        )
        return (data["choices"][0]["message"]["content"] or "").strip() or None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError, IndexError, TypeError) as exc:
        log.warning("LLM unavailable, using fallback: %s", exc.__class__.__name__)
        return None


def extract_json(text: Optional[str]) -> Optional[dict]:
    """Pull the first {...} object out of an LLM reply (it may wrap it in ```json fences). None if invalid."""
    if not text:
        return None
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        value = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None
