# Copyright (c) 2026, ZeroPointSix and contributors
# For license information, please see license.txt

"""Prompt builders for structured ticket analysis."""

from __future__ import annotations

import json
from typing import Any

SYSTEM_PROMPT = """You are a helpdesk ticket analysis assistant.
Return ONLY a single JSON object (no markdown) with these keys:
- category (string)
- priority (string: one of High, Medium, Low, Urgent when possible)
- summary (string, concise Chinese or English matching the ticket language)
- confidence (number 0..1)
- evidence (array of {claim, quote, source, weight})
- suggested_role (string)
- suggested_team (string or null)
- suggested_agent (null)
- auto_handleable (boolean)
- auto_handle_plan (object with title, steps[], simulated_result, simulated=true, warnings[] or null)
- missing_info (array of {field, label, reason})
- handoff_reason (string or null)

Rules:
- Evidence quotes MUST be substrings of the provided subject/description.
- Do not invent order IDs, emails, or facts not present in the ticket.
- If information is insufficient, lower confidence, set auto_handleable=false, and fill missing_info.
- Never claim real actions were executed; auto_handle_plan is suggestion/simulation only.
"""


def build_user_prompt(context: dict[str, Any]) -> str:
    subject = (context.get("subject") or "")[:500]
    description = (context.get("description") or "")[:4000]
    payload = {
        "ticket": context.get("name"),
        "subject": subject,
        "description": description,
        "current_priority": context.get("priority"),
        "current_ticket_type": context.get("ticket_type"),
        "current_agent_group": context.get("agent_group"),
    }
    return (
        "Analyze this support ticket and produce the JSON object.\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )
