# Copyright (c) 2026, ZeroPointSix and contributors
# For license information, please see license.txt

"""Whitelisted AI workbench APIs for agent desk."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from helpdesk.ai import service as ai_service
from helpdesk.utils import agent_only


@frappe.whitelist()
@agent_only
def analyze_ticket(ticket: str, source: str | None = None) -> dict[str, Any]:
    """Run AI analysis for a ticket (default: deterministic Mock)."""
    if not ticket:
        frappe.throw(_("Ticket is required"))
    return ai_service.run_analysis(ticket, source=source)


@frappe.whitelist()
@agent_only
def get_latest_analysis(
    ticket: str, statuses: str | list[str] | None = None
) -> dict[str, Any] | None:
    """Return the latest analysis for a ticket."""
    if not ticket:
        frappe.throw(_("Ticket is required"))
    status_list = _parse_statuses(statuses)
    return ai_service.get_latest_analysis(ticket, statuses=status_list)


# Backwards-friendly alias used in early design notes.
@frappe.whitelist()
@agent_only
def get_analysis(
    ticket: str, statuses: str | list[str] | None = None
) -> dict[str, Any] | None:
    return get_latest_analysis(ticket, statuses=statuses)


@frappe.whitelist()
@agent_only
def list_analyses(ticket: str, limit: int = 20) -> list[dict[str, Any]]:
    """List analysis history for a ticket (newest first, capped)."""
    if not ticket:
        frappe.throw(_("Ticket is required"))
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 20
    return ai_service.list_analyses(ticket, limit=limit)


@frappe.whitelist()
@agent_only
def update_analysis(name: str, fields: dict | str | None = None) -> dict[str, Any]:
    """Save human edits on a Completed analysis (does not write ticket)."""
    if not name:
        frappe.throw(_("Analysis name is required"))
    parsed_fields = _parse_dict(fields)
    return ai_service.update_analysis_fields(name, parsed_fields)


@frappe.whitelist()
@agent_only
def confirm_analysis(
    name: str,
    apply_fields: list[str] | str | None = None,
    fields: dict | str | None = None,
) -> dict[str, Any]:
    """Confirm analysis and selectively write fields back to HD Ticket.

    Does NOT change ticket status; agents use existing status controls.
    """
    if not name:
        frappe.throw(_("Analysis name is required"))
    return ai_service.confirm_analysis(
        name,
        apply_fields=_parse_list(apply_fields),
        fields=_parse_dict(fields),
    )


@frappe.whitelist()
@agent_only
def reject_analysis(name: str, reason: str | None = None) -> dict[str, Any]:
    """Reject a Completed analysis without writing ticket business fields."""
    if not name:
        frappe.throw(_("Analysis name is required"))
    return ai_service.reject_analysis(name, reason=reason)


@frappe.whitelist()
@agent_only
def simulate_auto_handle(name: str) -> dict[str, Any]:
    """Preview auto-handle plan simulation without real side effects."""
    if not name:
        frappe.throw(_("Analysis name is required"))
    return ai_service.simulate_auto_handle(name)


@frappe.whitelist()
@agent_only
def get_ai_settings_public() -> dict[str, Any]:
    """Return non-secret AI settings for desk display."""
    from helpdesk.ai.config import public_ai_settings

    return public_ai_settings()


def _parse_statuses(statuses: str | list[str] | None) -> list[str] | None:
    if statuses is None or statuses == "":
        return None
    if isinstance(statuses, str):
        # Accept JSON list or comma-separated values.
        try:
            import json

            parsed = json.loads(statuses)
            if isinstance(parsed, list):
                return [str(s) for s in parsed]
        except Exception:
            pass
        return [s.strip() for s in statuses.split(",") if s.strip()]
    if isinstance(statuses, (list, tuple)):
        return [str(s) for s in statuses]
    return None


def _parse_dict(value: dict | str | None) -> dict | None:
    if value is None or value == "":
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        import json

        try:
            parsed = json.loads(value)
        except Exception:
            frappe.throw(_("fields must be a JSON object"))
        if not isinstance(parsed, dict):
            frappe.throw(_("fields must be a JSON object"))
        return parsed
    frappe.throw(_("fields must be a JSON object"))


def _parse_list(value: list | str | None) -> list | None:
    if value is None or value == "":
        return None
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        import json

        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
        return [v.strip() for v in value.split(",") if v.strip()]
    return None
