# Copyright (c) 2026, ZeroPointSix and contributors
# For license information, please see license.txt

"""Build analysis input context from an HD Ticket."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cstr, strip_html


def get_ticket_context(ticket: str) -> dict[str, Any]:
    """Load ticket fields used by analyzers.

    Raises DoesNotExistError if the ticket is missing.
    """
    if not ticket:
        frappe.throw(_("Ticket is required"), frappe.ValidationError)

    if not frappe.db.exists("HD Ticket", ticket):
        frappe.throw(_("Ticket {0} not found").format(ticket), frappe.DoesNotExistError)

    doc = frappe.get_doc("HD Ticket", ticket)
    subject = cstr(doc.subject or "")
    description_html = cstr(doc.description or "")
    description = strip_html(description_html).strip()

    return {
        "name": doc.name,
        "subject": subject,
        "description": description,
        "description_html": description_html,
        "priority": doc.priority,
        "ticket_type": doc.ticket_type,
        "agent_group": doc.agent_group,
        "status": doc.status,
        "raised_by": doc.raised_by,
        "customer": getattr(doc, "customer", None),
        "combined_text": f"{subject}\n{description}".strip(),
        "combined_text_lower": f"{subject}\n{description}".strip().lower(),
    }
