# Copyright (c) 2026, ZeroPointSix and contributors
# For license information, please see license.txt

"""AI workbench orchestration: analyze, read, update, confirm, reject."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import now_datetime

from helpdesk.ai.analyzers import get_analyzer
from helpdesk.ai.config import get_ai_settings
from helpdesk.ai.context import get_ticket_context
from helpdesk.ai.validators import apply_validators, decide_branch
from helpdesk.helpdesk.doctype.hd_ai_analysis.hd_ai_analysis import (
    HDAIAnalysis,
    create_pending,
    get_latest_for_ticket,
    get_pending_for_ticket,
    list_for_ticket,
)
from helpdesk.helpdesk.doctype.hd_ticket_activity.hd_ticket_activity import (
    log_ticket_activity,
)

# Fields agents may edit via update_analysis / confirm patch.
EDITABLE_FIELDS = frozenset(
    {
        "category",
        "mapped_ticket_type",
        "priority",
        "summary",
        "confidence",
        "evidence",
        "suggested_role",
        "suggested_team",
        "suggested_agent",
        "auto_handleable",
        "auto_handle_plan",
        "missing_info",
        "handoff_reason",
    }
)

# Mapping from analysis field -> ticket field for selective apply.
APPLY_FIELD_MAP = {
    "mapped_ticket_type": "ticket_type",
    "priority": "priority",
    "summary": "summary",
    "suggested_team": "agent_group",
}


def _assert_ticket_permission(ticket: str, ptype: str = "read") -> None:
    if not frappe.db.exists("HD Ticket", ticket):
        frappe.throw(_("Ticket {0} not found").format(ticket), frappe.DoesNotExistError)
    frappe.has_permission("HD Ticket", ptype, doc=ticket, throw=True)


def _assert_analysis_ticket_permission(analysis: HDAIAnalysis, ptype: str = "read") -> None:
    _assert_ticket_permission(analysis.ticket, ptype)


def _serialize(doc: HDAIAnalysis) -> dict[str, Any]:
    data = doc.as_api_dict()
    threshold = get_ai_settings().get("confidence_threshold")
    data["branch"] = decide_branch(
        data,
        confidence_threshold=threshold
        if threshold is not None
        else 0.70,
    )
    return data


def _resolve_source(source: str | None) -> str:
    if source:
        normalized = source.strip().lower()
        if normalized in {"llm", "openai", "real"}:
            return "LLM"
        if normalized in {"mock", "rule", "rule_mock"}:
            return "Mock"
    settings = get_ai_settings()
    if settings.get("enabled") and str(settings.get("mode") or "").lower() == "llm":
        return "LLM"
    return "Mock"


def run_analysis(ticket: str, source: str | None = None) -> dict[str, Any]:
    """Create (or reuse Pending) analysis, run analyzer+validators, persist result."""
    _assert_ticket_permission(ticket, "read")
    # Writing analysis history also requires write on the ticket for P0 safety.
    _assert_ticket_permission(ticket, "write")

    resolved_source = _resolve_source(source)
    existing_pending = get_pending_for_ticket(ticket)
    if existing_pending:
        analysis = existing_pending
    else:
        analysis = create_pending(ticket, source=resolved_source)

    context = get_ticket_context(ticket)

    try:
        analyzer = get_analyzer(resolved_source)
        raw_result = analyzer.analyze(context)
        # If LLM degraded to mock, reflect actual source used.
        actual_source = getattr(analyzer, "source", resolved_source)
        if isinstance(raw_result.get("raw"), dict) and raw_result["raw"].get(
            "degraded_to"
        ):
            actual_source = "Mock"

        settings = get_ai_settings()
        validated = apply_validators(raw_result, context)
        # Strip non-persisted helper key before apply.
        payload = {k: v for k, v in validated.items() if k != "raw"}

        # Honest analyzer label when degraded.
        analyzer_name = getattr(analyzer, "name", None)
        raw_meta = validated.get("raw") or raw_result.get("raw") or {}
        if isinstance(raw_meta, dict) and raw_meta.get("degraded_to"):
            analyzer_name = raw_meta.get("analyzer") or "mock_fallback"
            actual_source = "Mock"

        # Never persist secrets in raw_response.
        safe_raw = _scrub_raw_response(raw_meta)

        analysis.apply_result(
            payload,
            source=actual_source,
            analyzer=analyzer_name,
            model_name=getattr(analyzer, "model_name", None)
            or settings.get("model"),
            raw_response=safe_raw,
            mark_completed=True,
        )
        analysis.error_message = None
        analysis.save(ignore_permissions=True)
    except Exception as exc:
        frappe.log_error(
            title=f"HD AI Analysis failed for ticket {ticket}",
            message=frappe.get_traceback(),
        )
        try:
            analysis.reload()
            analysis.mark_failed(str(exc))
            analysis.save(ignore_permissions=True)
        except Exception:
            frappe.log_error(
                title=f"HD AI Analysis failed to persist Failed state for {ticket}",
                message=frappe.get_traceback(),
            )
        # Re-raise a clean validation error for the API consumer.
        frappe.throw(
            _("AI analysis failed: {0}").format(cstr_safe(exc)[:300]),
            title=_("Analysis Failed"),
        )

    return _serialize(analysis)


def get_latest_analysis(ticket: str, statuses: list[str] | None = None) -> dict[str, Any] | None:
    _assert_ticket_permission(ticket, "read")
    doc = get_latest_for_ticket(ticket, statuses=statuses)
    if not doc:
        return None
    return _serialize(doc)


def list_analyses(ticket: str, limit: int = 20) -> list[dict[str, Any]]:
    _assert_ticket_permission(ticket, "read")
    return list_for_ticket(ticket, limit=limit)


def update_analysis_fields(name: str, fields: dict[str, Any] | None) -> dict[str, Any]:
    if not fields:
        frappe.throw(_("No fields provided"), frappe.ValidationError)

    doc = frappe.get_doc("HD AI Analysis", name)
    _assert_analysis_ticket_permission(doc, "write")

    if doc.status != "Completed":
        frappe.throw(
            _("Only Completed analyses can be edited (current: {0})").format(doc.status),
            title=_("Invalid Status"),
        )

    changed = False
    for key, value in fields.items():
        if key not in EDITABLE_FIELDS:
            frappe.throw(
                _("Field {0} is not editable").format(key),
                title=_("Invalid Field"),
            )
        if doc.get(key) != value:
            doc.set(key, value)
            changed = True

    if changed:
        doc.mark_edited()
        doc.save(ignore_permissions=True)

    return _serialize(doc)


def confirm_analysis(
    name: str,
    apply_fields: list[str] | None = None,
    fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Confirm analysis and selectively write back to HD Ticket.

    apply_fields: list of analysis field names to apply, e.g.
      ["mapped_ticket_type", "priority", "summary", "suggested_team", "suggested_agent"]
    If None, defaults to type/priority/summary/team (not agent).
    """
    doc = frappe.get_doc("HD AI Analysis", name)
    _assert_analysis_ticket_permission(doc, "write")

    # Idempotent: already confirmed -> return current state without re-applying.
    if doc.status == "Confirmed":
        ticket = frappe.get_doc("HD Ticket", doc.ticket)
        return {
            "analysis": _serialize(doc),
            "applied_fields": [],
            "warnings": [_("Analysis already confirmed")],
            "ticket": _ticket_snapshot(ticket),
            "idempotent": True,
        }

    if doc.status != "Completed":
        frappe.throw(
            _("Only Completed analyses can be confirmed (current: {0})").format(
                doc.status
            ),
            title=_("Invalid Status"),
        )

    # Optional last-minute field patch before confirm.
    if fields:
        for key, value in fields.items():
            if key not in EDITABLE_FIELDS:
                frappe.throw(
                    _("Field {0} is not editable").format(key),
                    title=_("Invalid Field"),
                )
            if doc.get(key) != value:
                doc.set(key, value)
                doc.mark_edited()

    if apply_fields is None:
        apply_fields = [
            "mapped_ticket_type",
            "priority",
            "summary",
            "suggested_team",
        ]

    ticket = frappe.get_doc("HD Ticket", doc.ticket)

    # Apply ticket field changes first. If ticket save fails, analysis stays
    # Completed so the agent can retry (request transaction rolls back).
    applied, warnings = _apply_to_ticket(doc, ticket, apply_fields)
    if applied:
        ticket.save()

    doc.status = "Confirmed"
    doc.confirmed_by = frappe.session.user
    doc.confirmed_at = now_datetime()
    doc.save(ignore_permissions=True)

    activity_bits = ", ".join(applied) if applied else "no ticket fields"
    log_ticket_activity(
        doc.ticket,
        f"AI analysis confirmed ({doc.name}): {activity_bits}",
    )
    _maybe_add_confirm_comment(doc, ticket, applied)

    ticket.reload()
    doc.reload()
    return {
        "analysis": _serialize(doc),
        "applied_fields": applied,
        "warnings": warnings,
        "ticket": _ticket_snapshot(ticket),
        "idempotent": False,
    }


def simulate_auto_handle(name: str) -> dict[str, Any]:
    """Return a simulated auto-handle preview without side effects."""
    doc = frappe.get_doc("HD AI Analysis", name)
    _assert_analysis_ticket_permission(doc, "read")

    data = doc.as_api_dict()
    branch = decide_branch(data)
    if branch.get("branch") != "auto_handle":
        frappe.throw(
            _("This analysis is not suitable for auto-handle simulation"),
            title=_("Not Auto-Handleable"),
        )

    plan = data.get("auto_handle_plan") or {}
    if isinstance(plan, str):
        import json

        try:
            plan = json.loads(plan)
        except Exception:
            plan = {"title": plan}

    simulated = plan.get("simulated_result") or plan.get("simulated_result_message")
    if isinstance(simulated, dict):
        result = simulated
    else:
        result = {
            "status": "success",
            "message": simulated
            or _("Simulated auto-handle completed (no real side effects)"),
            "would_update_ticket_status": None,
        }

    return {
        "analysis": name,
        "branch": branch,
        "plan": plan,
        "simulated_result": result,
        "side_effects": False,
        "note": _(
            "Simulation only. No ticket, email, password, or refund changes were made."
        ),
        "simulated_at": now_datetime(),
    }


def reject_analysis(name: str, reason: str | None = None) -> dict[str, Any]:
    doc = frappe.get_doc("HD AI Analysis", name)
    _assert_analysis_ticket_permission(doc, "write")

    if doc.status == "Rejected":
        return {"analysis": _serialize(doc), "idempotent": True}

    if doc.status != "Completed":
        frappe.throw(
            _("Only Completed analyses can be rejected (current: {0})").format(
                doc.status
            ),
            title=_("Invalid Status"),
        )

    doc.status = "Rejected"
    doc.rejection_reason = (reason or "").strip()[:500]
    doc.save(ignore_permissions=True)

    log_ticket_activity(
        doc.ticket,
        f"AI analysis rejected ({doc.name})"
        + (f": {doc.rejection_reason}" if doc.rejection_reason else ""),
    )
    return {"analysis": _serialize(doc), "idempotent": False}


def _apply_to_ticket(
    analysis: HDAIAnalysis,
    ticket,
    apply_fields: list[str],
) -> tuple[list[str], list[str]]:
    applied: list[str] = []
    warnings: list[str] = []

    for analysis_field in apply_fields:
        if analysis_field == "suggested_agent":
            agent = analysis.suggested_agent
            if not agent:
                warnings.append(_("suggested_agent is empty; skipped assignment"))
                continue
            if not frappe.db.exists("HD Agent", agent):
                warnings.append(
                    _("Suggested agent {0} does not exist; skipped").format(agent)
                )
                continue
            # HD Agent name is typically the user email / user link target.
            agent_user = frappe.db.get_value("HD Agent", agent, "user") or agent
            if hasattr(ticket, "assign_agent"):
                ticket.assign_agent(agent_user)
                applied.append("suggested_agent")
            else:
                warnings.append(_("Ticket does not support assign_agent; skipped"))
            continue

        ticket_field = APPLY_FIELD_MAP.get(analysis_field)
        if not ticket_field:
            warnings.append(
                _("Unknown apply field {0}; skipped").format(analysis_field)
            )
            continue

        value = analysis.get(analysis_field)
        if value in (None, ""):
            warnings.append(
                _("{0} is empty; skipped write-back").format(analysis_field)
            )
            continue

        # Validate Link targets before write-back.
        if analysis_field == "mapped_ticket_type":
            if not frappe.db.exists("HD Ticket Type", value):
                warnings.append(
                    _("Ticket type {0} does not exist; skipped").format(value)
                )
                continue
        elif analysis_field == "priority":
            if not frappe.db.exists("HD Ticket Priority", value):
                warnings.append(
                    _("Priority {0} does not exist; skipped").format(value)
                )
                continue
        elif analysis_field == "suggested_team":
            if not frappe.db.exists("HD Team", value):
                warnings.append(_("Team {0} does not exist; skipped").format(value))
                continue

        ticket.set(ticket_field, value)
        applied.append(analysis_field)

    return applied, warnings


def _ticket_snapshot(ticket) -> dict[str, Any]:
    return {
        "name": ticket.name,
        "subject": ticket.subject,
        "status": ticket.status,
        "priority": ticket.priority,
        "ticket_type": ticket.ticket_type,
        "summary": getattr(ticket, "summary", None),
        "agent_group": ticket.agent_group,
        "_assign": ticket.get("_assign"),
    }


def _maybe_add_confirm_comment(
    analysis: HDAIAnalysis, ticket, applied: list[str]
) -> None:
    try:
        content = (
            f"<p><b>AI 分析已确认</b> ({analysis.name})</p>"
            f"<ul>"
            f"<li>分类: {frappe.utils.escape_html(analysis.category or '-')}</li>"
            f"<li>优先级: {frappe.utils.escape_html(analysis.priority or '-')}</li>"
            f"<li>摘要: {frappe.utils.escape_html(analysis.summary or '-')}</li>"
            f"<li>置信度: {analysis.confidence}</li>"
            f"<li>写回字段: {frappe.utils.escape_html(', '.join(applied) or '无')}</li>"
            f"<li>确认人: {frappe.utils.escape_html(analysis.confirmed_by or '')}</li>"
            f"</ul>"
            f"<p><i>自动处理仅为建议/模拟，不会产生真实副作用。</i></p>"
        )
        frappe.get_doc(
            {
                "doctype": "HD Ticket Comment",
                "reference_ticket": ticket.name,
                "content": content,
                "commented_by": frappe.session.user,
            }
        ).insert(ignore_permissions=True)
    except Exception:
        # Comment is best-effort; do not fail confirm.
        frappe.log_error(
            title=f"AI confirm comment failed for {analysis.name}",
            message=frappe.get_traceback(),
        )


def cstr_safe(value: Any) -> str:
    try:
        return str(value)
    except Exception:
        return ""


def _scrub_raw_response(raw: Any) -> Any:
    """Drop anything that might accidentally contain secrets."""
    if raw is None:
        return None
    if isinstance(raw, str):
        return raw[:2000]
    if isinstance(raw, dict):
        blocked = {"api_key", "authorization", "password", "token", "secret"}
        cleaned = {}
        for key, value in raw.items():
            if str(key).lower() in blocked:
                continue
            if isinstance(value, str):
                cleaned[key] = value[:2000]
            elif isinstance(value, (int, float, bool)) or value is None:
                cleaned[key] = value
            elif isinstance(value, (list, dict)):
                cleaned[key] = value
            else:
                cleaned[key] = cstr_safe(value)[:500]
        return cleaned
    return cstr_safe(raw)[:2000]
