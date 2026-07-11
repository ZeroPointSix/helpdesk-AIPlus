# Copyright (c) 2026, ZeroPointSix and contributors
# For license information, please see license.txt

from __future__ import annotations

from typing import Any, Protocol


class Analyzer(Protocol):
    """Analyzer protocol: take ticket context, return AnalysisResult-like dict."""

    name: str
    source: str
    model_name: str

    def analyze(self, context: dict[str, Any]) -> dict[str, Any]:
        """Produce a structured analysis result for the ticket context."""
        ...
