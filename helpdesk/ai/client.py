# Copyright (c) 2026, ZeroPointSix and contributors
# For license information, please see license.txt

"""Minimal OpenAI-compatible Chat Completions client (no heavy SDK)."""

from __future__ import annotations

import json
from typing import Any
from urllib import error, request


class LLMClientError(Exception):
    pass


def chat_completion(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    timeout: int = 30,
    temperature: float = 0.1,
) -> dict[str, Any]:
    """Call POST {base_url}/chat/completions and return parsed JSON body.

    Never log api_key. Callers must not put secrets into messages.
    """
    if not api_key:
        raise LLMClientError("API key is missing")
    if not base_url:
        raise LLMClientError("Base URL is missing")

    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            # Cloudflare / bot management often blocks default Python-urllib UA
            # with HTTP 403 error code 1010 (seen on OpenAI-compatible gateways).
            "User-Agent": "Mozilla/5.0 (compatible; HelpdeskAIPlus/1.0)",
            "Accept": "application/json",
        },
    )
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        # Scrub any accidental key echo.
        detail = detail.replace(api_key, "***")
        raise LLMClientError(f"HTTP {exc.code}: {detail}") from None
    except error.URLError as exc:
        raise LLMClientError(f"Network error: {exc.reason}") from None
    except Exception as exc:
        raise LLMClientError(str(exc)[:300]) from None

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise LLMClientError("Provider returned non-JSON body") from exc

    return parsed


def extract_message_text(response: dict[str, Any]) -> str:
    try:
        return response["choices"][0]["message"]["content"]
    except Exception as exc:
        raise LLMClientError("Unexpected provider response shape") from exc
