# Copyright (c) 2026, ZeroPointSix and contributors
# For license information, please see license.txt

"""Shared analysis result contract for mock / LLM analyzers."""

from __future__ import annotations

from typing import Any, TypedDict


class EvidenceItem(TypedDict, total=False):
    claim: str
    quote: str
    source: str
    weight: float
    rule: str


class AutoHandlePlan(TypedDict, total=False):
    title: str
    steps: list[str]
    simulated_result: str
    simulated: bool
    warnings: list[str]


class MissingInfoItem(TypedDict, total=False):
    field: str
    label: str
    reason: str


class AnalysisResult(TypedDict, total=False):
    """Unified analyzer output written into HD AI Analysis."""

    category: str
    mapped_ticket_type: str | None
    priority: str | None
    summary: str
    confidence: float
    evidence: list[EvidenceItem]
    suggested_role: str | None
    suggested_team: str | None
    suggested_agent: str | None
    auto_handleable: bool | int
    auto_handle_plan: AutoHandlePlan | dict[str, Any] | None
    missing_info: list[MissingInfoItem] | list[str]
    handoff_reason: str | None
    raw: dict[str, Any]


# Default confidence threshold used by branch logic (#6) and validators.
DEFAULT_CONFIDENCE_THRESHOLD = 0.70
