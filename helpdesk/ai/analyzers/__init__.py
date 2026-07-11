# Copyright (c) 2026, ZeroPointSix and contributors
# For license information, please see license.txt

from __future__ import annotations

from helpdesk.ai.analyzers.base import Analyzer
from helpdesk.ai.analyzers.mock import MockAnalyzer
from helpdesk.ai.config import get_ai_settings


def get_analyzer(source: str | None = None) -> Analyzer:
    """Return analyzer for source. Default respects HD AI Settings / site_config."""
    settings = get_ai_settings()
    normalized = (source or "").strip().lower()

    # Explicit call-site override.
    if normalized in {"mock", "rule", "rule_mock"}:
        return MockAnalyzer()
    if normalized in {"llm", "openai", "real"}:
        from helpdesk.ai.analyzers.llm import LLMAnalyzer

        return LLMAnalyzer(settings)

    # Settings-driven default.
    mode = (settings.get("mode") or "Mock").lower()
    enabled = bool(settings.get("enabled"))
    if enabled and mode == "llm":
        from helpdesk.ai.analyzers.llm import LLMAnalyzer

        return LLMAnalyzer(settings)
    return MockAnalyzer()
