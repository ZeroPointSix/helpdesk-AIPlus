# Copyright (c) 2026, ZeroPointSix and contributors
# For license information, please see license.txt

"""Idempotent demo ticket seeder for AI workbench demos.

Usage:
  bench --site <site> execute helpdesk.ai.seed_demo.run
  bench --site <site> execute helpdesk.ai.seed_demo.run --kwargs "{'reset': True}"
  bench --site <site> execute helpdesk.ai.seed_demo.run --kwargs "{'with_analysis': True}"
"""

from __future__ import annotations

from typing import Any

import frappe

from helpdesk.ai.demo_fixtures import DEMO_PREFIX, DEMO_RAISED_BY, DEMO_TICKETS
from helpdesk.ai.service import run_analysis


def run(reset: bool = False, with_analysis: bool = False) -> dict[str, Any]:
    """Create (or recreate) demo tickets. Does not run on install by default."""
    ensure_demo_contact()

    if reset:
        _cleanup_demo_tickets()

    created: list[dict[str, Any]] = []
    for spec in DEMO_TICKETS:
        ticket_name = create_or_update_ticket(spec)
        analysis_name = None
        if with_analysis:
            result = run_analysis(ticket_name, source="Mock")
            analysis_name = result.get("name")
        created.append(
            {
                "id": spec["id"],
                "ticket": ticket_name,
                "subject": spec["subject"],
                "expected_branch": spec["expected"]["branch"],
                "analysis": analysis_name,
            }
        )

    frappe.db.commit()  # nosemgrep - explicit seed script entrypoint
    return {
        "count": len(created),
        "tickets": created,
        "hint": "Open each ticket in agent desk → AI Workbench → Run AI analysis",
    }


def ensure_demo_contact() -> None:
    email = DEMO_RAISED_BY
    if not frappe.db.exists("User", email):
        # Contact path does not require a full User; tickets mainly need raised_by email.
        pass
    if not frappe.db.exists("Contact", {"email_id": email}):
        # Prefer simple contact if module available; ignore failures.
        try:
            contact = frappe.get_doc(
                {
                    "doctype": "Contact",
                    "first_name": "AI",
                    "last_name": "Demo Customer",
                    "email_ids": [{"email_id": email, "is_primary": 1}],
                }
            )
            contact.insert(ignore_permissions=True)
        except Exception:
            frappe.clear_last_message()


def create_or_update_ticket(spec: dict[str, Any]) -> str:
    existing = frappe.db.get_value(
        "HD Ticket",
        {"subject": spec["subject"], "raised_by": spec.get("raised_by") or DEMO_RAISED_BY},
        "name",
    )
    if existing:
        doc = frappe.get_doc("HD Ticket", existing)
        doc.description = spec["description"]
        doc.save(ignore_permissions=True)
        return doc.name

    doc = frappe.get_doc(
        {
            "doctype": "HD Ticket",
            "subject": spec["subject"],
            "description": spec["description"],
            "raised_by": spec.get("raised_by") or DEMO_RAISED_BY,
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name


def _cleanup_demo_tickets() -> None:
    names = frappe.get_all(
        "HD Ticket",
        filters={"subject": ("like", f"{DEMO_PREFIX}%")},
        pluck="name",
    )
    for name in names:
        frappe.db.delete("HD AI Analysis", {"ticket": name})
        frappe.delete_doc("HD Ticket", name, force=True, ignore_permissions=True)
