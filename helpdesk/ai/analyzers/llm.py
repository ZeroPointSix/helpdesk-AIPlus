# Copyright (c) 2026, ZeroPointSix and contributors
# For license information, please see license.txt

"""Optional LLM analyzer with transparent Mock fallback (#10)."""

from __future__ import annotations

import json
import re
from typing import Any

import frappe
from frappe import _

from helpdesk.ai.analyzers.mock import MockAnalyzer
from helpdesk.ai.client import LLMClientError, chat_completion, extract_message_text
from helpdesk.ai.config import get_ai_settings
from helpdesk.ai.prompts.ticket_analysis import SYSTEM_PROMPT, build_user_prompt
from helpdesk.ai.types import AnalysisResult


class LLMAnalyzer:
    name = "llm_structured"
    source = "LLM"
    model_name = "configured"

    def __init__(self, settings: dict[str, Any] | None = None):
        self.settings = settings or get_ai_settings()
        self.api_key = self.settings.get("api_key")
        self.model_name = self.settings.get("model") or "gpt-4.1-mini"
        self.base_url = self.settings.get("base_url") or "https://api.openai.com/v1"
        self.timeout = int(self.settings.get("timeout_seconds") or 30)
        self.fallback_to_mock = bool(self.settings.get("fallback_to_mock", True))

    def is_available(self) -> bool:
        return bool(self.api_key)

    def analyze(self, context: dict[str, Any]) -> AnalysisResult:
        if not self.is_available():
            return self._handle_failure(context, reason="missing_api_key")

        try:
            response = chat_completion(
                base_url=self.base_url,
                api_key=self.api_key,
                model=self.model_name,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_user_prompt(context)},
                ],
                timeout=self.timeout,
            )
            content = extract_message_text(response)
            parsed = self._parse_json_content(content)
            result = self._normalize_result(parsed, context)
            # Never persist secrets; keep a short scrubbed snippet only.
            result["raw"] = {
                "provider": self.settings.get("provider"),
                "model": self.model_name,
                "content_preview": content[:2000],
            }
            return result
        except Exception as exc:
            # Avoid logging api_key via str(exc) paths that might include headers.
            safe_reason = str(exc).replace(str(self.api_key or ""), "***")[:300]
            frappe.log_error(
                title="HD AI LLM analysis failed",
                message=safe_reason,
            )
            return self._handle_failure(context, reason=safe_reason)

    def _handle_failure(self, context: dict[str, Any], reason: str) -> AnalysisResult:
        if self.fallback_to_mock:
            return self._degrade(context, reason=reason)
        frappe.throw(
            _("LLM analysis failed: {0}").format(reason[:300]),
            title=_("LLM Unavailable"),
        )

    def _degrade(self, context: dict[str, Any], reason: str) -> AnalysisResult:
        mock = MockAnalyzer()
        result = mock.analyze(context)
        result["raw"] = {
            **(result.get("raw") or {}),
            "requested_source": "LLM",
            "degraded_to": "Mock",
            "degrade_reason": reason[:300],
            "analyzer": "mock_fallback",
        }
        return result

    def _parse_json_content(self, content: str) -> dict[str, Any]:
        text = (content or "").strip()
        if not text:
            raise LLMClientError("Empty model content")
        # Strip optional markdown fences.
        fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if fence:
            text = fence.group(1).strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMClientError("Model did not return valid JSON") from exc
        if not isinstance(data, dict):
            raise LLMClientError("Model JSON root must be an object")
        return data

    def _normalize_result(
        self, data: dict[str, Any], context: dict[str, Any]
    ) -> AnalysisResult:
        confidence = data.get("confidence", 0.5)
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))

        evidence = data.get("evidence") or []
        if not isinstance(evidence, list):
            evidence = []

        missing = data.get("missing_info") or []
        if not isinstance(missing, list):
            missing = []

        auto_handleable = 1 if data.get("auto_handleable") in (True, 1, "1") else 0
        plan = data.get("auto_handle_plan")
        if auto_handleable and not plan:
            auto_handleable = 0

        # Resolve links softly (same spirit as mock analyzer).
        priority = data.get("priority")
        if priority and not frappe.db.exists("HD Ticket Priority", priority):
            priority = None
        team = data.get("suggested_team")
        if team and not frappe.db.exists("HD Team", team):
            team = None
        mapped_type = data.get("mapped_ticket_type") or data.get("category")
        if mapped_type and not frappe.db.exists("HD Ticket Type", mapped_type):
            mapped_type = None

        return {
            "category": str(data.get("category") or "通用咨询")[:140],
            "mapped_ticket_type": mapped_type,
            "priority": priority,
            "summary": str(data.get("summary") or "")[:1000],
            "confidence": confidence,
            "evidence": evidence,
            "suggested_role": data.get("suggested_role"),
            "suggested_team": team,
            "suggested_agent": None,
            "auto_handleable": auto_handleable,
            "auto_handle_plan": plan,
            "missing_info": missing,
            "handoff_reason": data.get("handoff_reason"),
        }
