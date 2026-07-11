# Copyright (c) 2026, ZeroPointSix and Contributors
# See license.txt

from __future__ import annotations

import json

import frappe
from frappe.tests import IntegrationTestCase

from helpdesk.helpdesk.doctype.hd_ai_analysis.hd_ai_analysis import (
    create_from_result,
    create_pending,
    get_latest_for_ticket,
    list_for_ticket,
)


def _make_ticket(subject: str = "AI model test ticket") -> str:
    ticket = frappe.get_doc(
        {
            "doctype": "HD Ticket",
            "subject": subject,
            "description": "Cannot login and password reset email never arrives.",
        }
    )
    ticket.insert(ignore_permissions=True)
    return ticket.name


def _sample_payload(**overrides):
    payload = {
        "category": "登录问题",
        "priority": "High" if frappe.db.exists("HD Ticket Priority", "High") else None,
        "summary": "用户无法登录且未收到重置邮件",
        "confidence": 0.86,
        "evidence": [
            {
                "claim": "用户提到无法登录",
                "quote": "Cannot login",
                "source": "description",
                "weight": 0.8,
            }
        ],
        "suggested_role": "技术支持",
        "suggested_team": None,
        "suggested_agent": None,
        "auto_handleable": 1,
        "auto_handle_plan": {
            "steps": ["验证账号状态", "触发密码重置邮件"],
            "simulated": True,
        },
        "missing_info": [],
        "handoff_reason": None,
    }
    payload.update(overrides)
    return payload


class TestHDAIAnalysis(IntegrationTestCase):
    def setUp(self):
        self.ticket = _make_ticket()

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.delete("HD AI Analysis", {"ticket": self.ticket})
        if frappe.db.exists("HD Ticket", self.ticket):
            frappe.delete_doc("HD Ticket", self.ticket, force=True)

    def test_create_from_result_persists_seven_fields(self):
        doc = create_from_result(
            self.ticket,
            _sample_payload(),
            source="Mock",
            analyzer="rule_mock",
            model_name="mock-v1",
        )

        self.assertEqual(doc.status, "Completed")
        self.assertEqual(doc.ticket, self.ticket)
        self.assertEqual(doc.category, "登录问题")
        self.assertEqual(doc.summary, "用户无法登录且未收到重置邮件")
        self.assertAlmostEqual(float(doc.confidence), 0.86, places=3)
        self.assertEqual(doc.suggested_role, "技术支持")
        self.assertEqual(cint_safe(doc.auto_handleable), 1)
        self.assertEqual(doc.source, "Mock")
        self.assertEqual(doc.analyzer, "rule_mock")

        evidence = json.loads(doc.evidence) if isinstance(doc.evidence, str) else doc.evidence
        self.assertIsInstance(evidence, list)
        self.assertGreaterEqual(len(evidence), 1)
        self.assertIn("claim", evidence[0])

        original = (
            json.loads(doc.original_result)
            if isinstance(doc.original_result, str)
            else doc.original_result
        )
        self.assertEqual(original["category"], "登录问题")
        self.assertAlmostEqual(float(original["confidence"]), 0.86, places=3)

    def test_multiple_analyses_per_ticket_and_latest_query(self):
        first = create_from_result(
            self.ticket, _sample_payload(summary="first"), analyzer="rule_mock"
        )
        second = create_from_result(
            self.ticket, _sample_payload(summary="second"), analyzer="rule_mock"
        )

        latest = get_latest_for_ticket(self.ticket)
        self.assertIsNotNone(latest)
        self.assertEqual(latest.name, second.name)
        self.assertEqual(latest.summary, "second")

        rows = list_for_ticket(self.ticket, limit=10)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["name"], second.name)
        self.assertEqual(rows[1]["name"], first.name)

    def test_confidence_out_of_range_rejected(self):
        doc = create_pending(self.ticket)
        doc.confidence = 1.5
        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)

        doc.reload()
        doc.confidence = -0.1
        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)

    def test_invalid_json_rejected(self):
        doc = create_pending(self.ticket)
        doc.evidence = "{not-json"
        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)

    def test_status_transition_and_terminal_immutability(self):
        doc = create_from_result(self.ticket, _sample_payload())
        self.assertEqual(doc.status, "Completed")

        # Completed -> Confirmed is allowed.
        doc.status = "Confirmed"
        doc.confirmed_by = "Administrator"
        doc.confirmed_at = frappe.utils.now_datetime()
        doc.save(ignore_permissions=True)
        doc.reload()
        self.assertEqual(doc.status, "Confirmed")

        # Terminal: cannot edit result fields.
        doc.summary = "should not change"
        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)

        # Terminal: cannot go back to Completed.
        doc.reload()
        doc.status = "Completed"
        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)

    def test_original_result_not_overwritten_after_edit(self):
        doc = create_from_result(self.ticket, _sample_payload(summary="ai original"))
        original_before = doc.original_result

        doc.summary = "human edited"
        doc.is_edited = 1
        doc.save(ignore_permissions=True)
        doc.reload()

        self.assertEqual(doc.summary, "human edited")
        self.assertEqual(cint_safe(doc.is_edited), 1)
        # original_result must remain the frozen AI snapshot.
        original = (
            json.loads(doc.original_result)
            if isinstance(doc.original_result, str)
            else doc.original_result
        )
        self.assertEqual(original["summary"], "ai original")
        # Attempt explicit overwrite is ignored / restored.
        doc.original_result = frappe.as_json({"summary": "tampered"})
        doc.save(ignore_permissions=True)
        doc.reload()
        original_after = (
            json.loads(doc.original_result)
            if isinstance(doc.original_result, str)
            else doc.original_result
        )
        self.assertEqual(original_after["summary"], "ai original")
        self.assertEqual(
            (
                json.loads(original_before)
                if isinstance(original_before, str)
                else original_before
            )["summary"],
            "ai original",
        )

    def test_mark_failed(self):
        doc = create_pending(self.ticket)
        doc.mark_failed("mock analyzer boom")
        doc.save(ignore_permissions=True)
        doc.reload()
        self.assertEqual(doc.status, "Failed")
        self.assertIn("boom", doc.error_message)

        # Failed is terminal.
        doc.summary = "nope"
        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)

    def test_pending_to_completed_via_apply_result(self):
        doc = create_pending(self.ticket, source="Mock", analyzer="rule_mock")
        self.assertEqual(doc.status, "Pending")
        doc.apply_result(_sample_payload(), mark_completed=True)
        doc.save(ignore_permissions=True)
        doc.reload()
        self.assertEqual(doc.status, "Completed")
        self.assertTrue(doc.original_result)


def cint_safe(value) -> int:
    return int(value or 0)
