# Copyright (c) 2026, ZeroPointSix and contributors
# For license information, please see license.txt

"""Resolve AI runtime configuration.

Priority:
1. HD AI Settings (Single DocType) when the DocType exists
2. frappe.conf / site_config keys
3. Safe defaults (Mock)
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import cint, flt

from helpdesk.ai.types import DEFAULT_CONFIDENCE_THRESHOLD


def get_ai_settings() -> dict[str, Any]:
    """Return a plain dict of effective AI settings (never includes raw key in logs)."""
    settings: dict[str, Any] = {
        "enabled": False,
        "mode": "Mock",
        "provider": "openai_compatible",
        "model": "gpt-4.1-mini",
        "base_url": "https://api.openai.com/v1",
        "timeout_seconds": 30,
        "fallback_to_mock": True,
        "confidence_threshold": DEFAULT_CONFIDENCE_THRESHOLD,
        "api_key": None,
        "source": "default",
    }

    conf = frappe.conf or {}
    if conf.get("helpdesk_ai_provider"):
        settings["mode"] = (
            "LLM"
            if str(conf.get("helpdesk_ai_provider")).lower()
            in {"llm", "openai", "real"}
            else "Mock"
        )
        settings["source"] = "site_config"
    if conf.get("helpdesk_ai_enabled") is not None:
        settings["enabled"] = bool(cint(conf.get("helpdesk_ai_enabled")))
        settings["source"] = "site_config"
    if conf.get("helpdesk_ai_model"):
        settings["model"] = conf.get("helpdesk_ai_model")
    if conf.get("helpdesk_ai_base_url"):
        settings["base_url"] = conf.get("helpdesk_ai_base_url")
    if conf.get("helpdesk_ai_timeout") is not None:
        settings["timeout_seconds"] = int(conf.get("helpdesk_ai_timeout") or 30)
    if conf.get("helpdesk_ai_fallback_to_mock") is not None:
        settings["fallback_to_mock"] = bool(
            cint(conf.get("helpdesk_ai_fallback_to_mock"))
        )
    if conf.get("helpdesk_ai_confidence_threshold") is not None:
        settings["confidence_threshold"] = flt(
            conf.get("helpdesk_ai_confidence_threshold")
        )
    if conf.get("helpdesk_ai_api_key"):
        settings["api_key"] = conf.get("helpdesk_ai_api_key")

    # DocType overrides site_config when present.
    if frappe.db and frappe.db.exists("DocType", "HD AI Settings"):
        try:
            doc = frappe.get_single("HD AI Settings")
            settings["enabled"] = bool(cint(doc.enabled))
            settings["mode"] = doc.mode or "Mock"
            settings["provider"] = doc.provider or settings["provider"]
            settings["model"] = doc.model or settings["model"]
            settings["base_url"] = doc.base_url or settings["base_url"]
            settings["timeout_seconds"] = int(
                doc.timeout_seconds or settings["timeout_seconds"]
            )
            settings["fallback_to_mock"] = bool(cint(doc.fallback_to_mock))
            if doc.confidence_threshold not in (None, ""):
                settings["confidence_threshold"] = flt(doc.confidence_threshold)
            key = doc.get_password("api_key") if doc.api_key else None
            if key:
                settings["api_key"] = key
            settings["source"] = "hd_ai_settings"
        except Exception:
            # Settings may not be migrated yet; keep conf/defaults.
            pass

    # Clamp threshold.
    thr = flt(settings["confidence_threshold"])
    if thr <= 0 or thr > 1:
        thr = DEFAULT_CONFIDENCE_THRESHOLD
    settings["confidence_threshold"] = thr
    return settings


def public_ai_settings() -> dict[str, Any]:
    """Settings safe to return to desk (no secrets)."""
    s = get_ai_settings()
    return {
        "enabled": s["enabled"],
        "mode": s["mode"],
        "provider": s["provider"],
        "model": s["model"],
        "base_url": s["base_url"],
        "timeout_seconds": s["timeout_seconds"],
        "fallback_to_mock": s["fallback_to_mock"],
        "confidence_threshold": s["confidence_threshold"],
        "has_api_key": bool(s.get("api_key")),
        "source": s["source"],
    }
