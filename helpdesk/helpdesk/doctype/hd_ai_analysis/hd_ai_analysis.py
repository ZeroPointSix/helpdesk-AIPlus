# Copyright (c) 2026, ZeroPointSix and contributors
# For license information, please see license.txt

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, now_datetime

# Allowed status transitions for HD AI Analysis.
# Pending -> Completed / Failed
# Completed -> Confirmed / Rejected
# Confirmed / Rejected / Failed are terminal (no further edits via normal save paths).
ALLOWED_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "Pending": {"Pending", "Completed", "Failed"},
    "Completed": {"Completed", "Confirmed", "Rejected"},
    "Failed": {"Failed"},
    "Confirmed": {"Confirmed"},
    "Rejected": {"Rejected"},
}

TERMINAL_STATUSES = frozenset({"Confirmed", "Rejected", "Failed"})
EDITABLE_STATUSES = frozenset({"Pending", "Completed"})

# Result fields that may be written from an analyzer payload.
RESULT_FIELDS = (
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
)

# Snapshot fields frozen into original_result when analysis completes.
ORIGINAL_RESULT_FIELDS = (
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
    "source",
    "analyzer",
    "model_name",
)

JSON_FIELDS = ("evidence", "auto_handle_plan", "missing_info", "original_result", "raw_response")


class HDAIAnalysis(Document):
    # begin: auto-generated types
    # This code is auto-generated. Do not modify anything in this block.

    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from frappe.types import DF

        analyzer: DF.Data | None
        auto_handle_plan: DF.JSON | None
        auto_handleable: DF.Check
        category: DF.Data | None
        confidence: DF.Float
        confirmed_at: DF.Datetime | None
        confirmed_by: DF.Link | None
        error_message: DF.SmallText | None
        evidence: DF.JSON | None
        handoff_reason: DF.SmallText | None
        is_edited: DF.Check
        mapped_ticket_type: DF.Link | None
        missing_info: DF.JSON | None
        model_name: DF.Data | None
        original_result: DF.JSON | None
        priority: DF.Link | None
        raw_response: DF.JSON | None
        rejection_reason: DF.SmallText | None
        source: DF.Literal["Mock", "LLM"]
        status: DF.Literal["Pending", "Completed", "Failed", "Confirmed", "Rejected"]
        suggested_agent: DF.Link | None
        suggested_role: DF.Data | None
        suggested_team: DF.Link | None
        summary: DF.SmallText | None
        ticket: DF.Link
    # end: auto-generated types

    def validate(self):
        self._normalize_json_fields()
        self._validate_confidence()
        self._validate_status_transition()
        self._validate_terminal_immutability()
        self._freeze_original_result_on_complete()
        self._protect_original_result()

    def before_save(self):
        # Ensure check defaults are numeric for comparisons.
        self.is_edited = cint(self.is_edited)
        self.auto_handleable = cint(self.auto_handleable)

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def _normalize_json_fields(self):
        for field in JSON_FIELDS:
            value = self.get(field)
            if value in (None, ""):
                continue
            if isinstance(value, (dict, list)):
                # Store as JSON string so Frappe JSON fields stay consistent.
                self.set(field, frappe.as_json(value))
            elif isinstance(value, str):
                try:
                    parsed = json.loads(value)
                except (TypeError, ValueError):
                    frappe.throw(
                        _("{0} must be valid JSON").format(self.meta.get_label(field)),
                        title=_("Invalid JSON"),
                    )
                # Re-serialize to canonical form.
                self.set(field, frappe.as_json(parsed))
            else:
                frappe.throw(
                    _("{0} must be valid JSON").format(self.meta.get_label(field)),
                    title=_("Invalid JSON"),
                )

    def _validate_confidence(self):
        if self.confidence in (None, ""):
            return
        confidence = flt(self.confidence)
        if confidence < 0 or confidence > 1:
            frappe.throw(
                _("Confidence must be between 0 and 1 (got {0})").format(confidence),
                title=_("Invalid Confidence"),
            )
        self.confidence = confidence

    def _validate_status_transition(self):
        if self.is_new():
            if self.status not in ALLOWED_STATUS_TRANSITIONS:
                frappe.throw(
                    _("Invalid status: {0}").format(self.status),
                    title=_("Invalid Status"),
                )
            return

        previous = self.get_doc_before_save()
        if not previous:
            return

        old_status = previous.status
        new_status = self.status
        allowed = ALLOWED_STATUS_TRANSITIONS.get(old_status, set())
        if new_status not in allowed:
            frappe.throw(
                _("Cannot change AI analysis status from {0} to {1}").format(
                    old_status, new_status
                ),
                title=_("Invalid Status Transition"),
            )

    def _validate_terminal_immutability(self):
        """Terminal records cannot be edited (except system-level force paths)."""
        if self.is_new():
            return

        previous = self.get_doc_before_save()
        if not previous:
            return

        if previous.status not in TERMINAL_STATUSES:
            return

        # Allow no-op saves (status stays terminal, no field changes that matter).
        if self.status != previous.status:
            # Transition validation already covers illegal moves; extra guard.
            frappe.throw(
                _("AI analysis in status {0} is immutable").format(previous.status),
                title=_("Immutable Analysis"),
            )

        mutable_fields = [
            *RESULT_FIELDS,
            "source",
            "analyzer",
            "model_name",
            "error_message",
            "raw_response",
            "rejection_reason",
            "confirmed_by",
            "confirmed_at",
            "is_edited",
            "ticket",
        ]
        for field in mutable_fields:
            if self.has_value_changed(field):
                frappe.throw(
                    _("AI analysis in status {0} cannot be modified").format(
                        previous.status
                    ),
                    title=_("Immutable Analysis"),
                )

    def _freeze_original_result_on_complete(self):
        """When entering Completed, freeze the first AI snapshot if empty."""
        if self.status != "Completed":
            return

        previous = None if self.is_new() else self.get_doc_before_save()
        just_completed = self.is_new() or (
            previous and previous.status != "Completed" and self.status == "Completed"
        )
        if not just_completed and self.original_result:
            return

        if self.original_result:
            return

        self.original_result = frappe.as_json(self._build_result_snapshot())

    def _protect_original_result(self):
        """Once original_result is set, do not allow overwriting it."""
        if self.is_new():
            return

        previous = self.get_doc_before_save()
        if not previous or not previous.original_result:
            return

        if self.has_value_changed("original_result"):
            # Restore previous value instead of silently accepting overwrite.
            self.original_result = previous.original_result

    def _build_result_snapshot(self) -> dict[str, Any]:
        snapshot: dict[str, Any] = {}
        for field in ORIGINAL_RESULT_FIELDS:
            value = self.get(field)
            if field in JSON_FIELDS and isinstance(value, str) and value:
                try:
                    value = json.loads(value)
                except (TypeError, ValueError):
                    pass
            snapshot[field] = value
        return snapshot

    # ------------------------------------------------------------------
    # Public helpers used by AI service layer (#3 / #4)
    # ------------------------------------------------------------------

    def apply_result(
        self,
        payload: dict[str, Any],
        *,
        source: str | None = None,
        analyzer: str | None = None,
        model_name: str | None = None,
        raw_response: Any | None = None,
        mark_completed: bool = True,
    ) -> "HDAIAnalysis":
        """Apply analyzer payload onto this document.

        When mark_completed is True, status becomes Completed and original_result
        is frozen (if not already set).
        """
        if self.status in TERMINAL_STATUSES:
            frappe.throw(
                _("AI analysis in status {0} cannot accept new results").format(
                    self.status
                ),
                title=_("Immutable Analysis"),
            )

        for field in RESULT_FIELDS:
            if field in payload:
                self.set(field, payload[field])

        if source:
            self.source = source
        if analyzer is not None:
            self.analyzer = analyzer
        if model_name is not None:
            self.model_name = model_name
        if raw_response is not None:
            self.raw_response = raw_response

        if mark_completed:
            self.status = "Completed"
            if not self.original_result:
                self.original_result = frappe.as_json(self._build_result_snapshot())

        return self

    def mark_failed(self, error_message: str) -> "HDAIAnalysis":
        """Move analysis to Failed with a safe error summary."""
        if self.status in {"Confirmed", "Rejected"}:
            frappe.throw(
                _("Cannot mark a {0} analysis as Failed").format(self.status),
                title=_("Invalid Status Transition"),
            )
        self.status = "Failed"
        # Keep message short and free of secrets.
        self.error_message = (error_message or _("Unknown analysis error"))[:500]
        return self

    def mark_edited(self) -> "HDAIAnalysis":
        self.is_edited = 1
        return self

    def as_api_dict(self) -> dict[str, Any]:
        """Serialize for API responses used by #3/#4/#5."""
        data = self.as_dict()
        for field in JSON_FIELDS:
            value = data.get(field)
            if isinstance(value, str) and value:
                try:
                    data[field] = json.loads(value)
                except (TypeError, ValueError):
                    pass
        return data


# ----------------------------------------------------------------------
# Factory / query helpers (consumed by helpdesk.ai.service)
# ----------------------------------------------------------------------


def create_pending(
    ticket: str,
    *,
    source: str = "Mock",
    analyzer: str | None = None,
    model_name: str | None = None,
) -> HDAIAnalysis:
    """Create a Pending analysis row for a ticket."""
    if not frappe.db.exists("HD Ticket", ticket):
        frappe.throw(_("Ticket {0} not found").format(ticket), frappe.DoesNotExistError)

    doc = frappe.get_doc(
        {
            "doctype": "HD AI Analysis",
            "ticket": ticket,
            "status": "Pending",
            "source": source or "Mock",
            "analyzer": analyzer,
            "model_name": model_name,
        }
    )
    doc.insert(ignore_permissions=True)
    return doc


def create_from_result(
    ticket: str,
    payload: dict[str, Any],
    *,
    source: str = "Mock",
    analyzer: str | None = None,
    model_name: str | None = None,
    raw_response: Any | None = None,
) -> HDAIAnalysis:
    """Create a Completed analysis from an analyzer payload (sync path helper)."""
    doc = create_pending(
        ticket, source=source, analyzer=analyzer, model_name=model_name
    )
    doc.apply_result(
        payload,
        source=source,
        analyzer=analyzer,
        model_name=model_name,
        raw_response=raw_response,
        mark_completed=True,
    )
    doc.save(ignore_permissions=True)
    return doc


def get_latest_for_ticket(
    ticket: str,
    *,
    statuses: list[str] | None = None,
) -> HDAIAnalysis | None:
    """Return the newest analysis for a ticket, optionally filtered by status."""
    filters: dict[str, Any] = {"ticket": ticket}
    if statuses:
        filters["status"] = ("in", statuses)

    name = frappe.db.get_value(
        "HD AI Analysis",
        filters,
        "name",
        order_by="creation desc",
    )
    if not name:
        return None
    return frappe.get_doc("HD AI Analysis", name)


def get_pending_for_ticket(ticket: str) -> HDAIAnalysis | None:
    """Return an existing Pending analysis if one is still open."""
    return get_latest_for_ticket(ticket, statuses=["Pending"])


def list_for_ticket(ticket: str, limit: int = 20) -> list[dict[str, Any]]:
    """List analyses for a ticket, newest first."""
    limit = max(1, min(cint(limit) or 20, 100))
    rows = frappe.get_all(
        "HD AI Analysis",
        filters={"ticket": ticket},
        fields=[
            "name",
            "ticket",
            "status",
            "source",
            "analyzer",
            "model_name",
            "category",
            "priority",
            "summary",
            "confidence",
            "suggested_role",
            "suggested_team",
            "auto_handleable",
            "is_edited",
            "creation",
            "modified",
        ],
        order_by="creation desc",
        limit_page_length=limit,
    )
    return rows
