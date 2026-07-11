# Copyright (c) 2026, ZeroPointSix and Contributors
# See license.txt

from __future__ import annotations

import frappe
from frappe.tests import IntegrationTestCase

from helpdesk.ai.demo_fixtures import DEMO_TICKETS, get_fixture
from helpdesk.ai.service import (
    confirm_analysis,
    reject_analysis,
    run_analysis,
    simulate_auto_handle,
    update_analysis_fields,
)
from helpdesk.ai.validators import decide_branch
from helpdesk.test_utils import create_agent


def _create_ticket(subject: str, description: str) -> str:
    doc = frappe.get_doc(
        {
            "doctype": "HD Ticket",
            "subject": subject,
            "description": description,
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name


class TestAIWorkbenchAPI(IntegrationTestCase):
    def setUp(self):
        self.agent_email = "ai_agent@example.com"
        create_agent(self.agent_email)
        self.tickets: list[str] = []

    def tearDown(self):
        frappe.set_user("Administrator")
        for ticket in self.tickets:
            frappe.db.delete("HD AI Analysis", {"ticket": ticket})
            if frappe.db.exists("HD Ticket", ticket):
                frappe.delete_doc("HD Ticket", ticket, force=True)
        if frappe.db.exists("User", self.agent_email):
            # leave user/agent; create_agent is idempotent-ish across tests
            pass

    def _track(self, ticket: str) -> str:
        self.tickets.append(ticket)
        return ticket

    def test_mock_login_auto_handle_branch(self):
        fixture = get_fixture("D1")
        ticket = self._track(
            _create_ticket(fixture["subject"], fixture["description"])
        )
        result = run_analysis(ticket, source="Mock")

        self.assertEqual(result["status"], "Completed")
        self.assertEqual(result["source"], "Mock")
        self.assertEqual(result["category"], fixture["expected"]["category"])
        self.assertGreaterEqual(
            float(result["confidence"]), fixture["expected"]["min_confidence"]
        )
        self.assertEqual(int(result["auto_handleable"] or 0), 1)
        self.assertTrue(result.get("auto_handle_plan"))
        self.assertEqual(result["branch"]["branch"], "auto_handle")
        self.assertTrue(result.get("evidence"))

    def test_mock_refund_missing_order_branch(self):
        fixture = get_fixture("D2")
        ticket = self._track(
            _create_ticket(fixture["subject"], fixture["description"])
        )
        result = run_analysis(ticket, source="Mock")

        self.assertEqual(result["status"], "Completed")
        self.assertEqual(result["category"], "退款")
        self.assertLessEqual(
            float(result["confidence"]), fixture["expected"]["max_confidence"]
        )
        self.assertEqual(int(result["auto_handleable"] or 0), 0)
        missing = result.get("missing_info") or []
        self.assertTrue(any(
            (isinstance(m, dict) and m.get("field") == "order_id")
            or m == "order_id"
            or m == "订单号"
            for m in missing
        ))
        self.assertEqual(result["branch"]["branch"], "missing_info")

    def test_mock_generic_low_confidence(self):
        fixture = get_fixture("D3")
        ticket = self._track(
            _create_ticket(fixture["subject"], fixture["description"])
        )
        result = run_analysis(ticket, source="Mock")
        self.assertEqual(result["category"], "通用咨询")
        self.assertLessEqual(
            float(result["confidence"]), fixture["expected"]["max_confidence"]
        )
        self.assertIn(result["branch"]["branch"], {"low_confidence", "manual"})

    def test_evidence_comes_from_real_input(self):
        subject = "Cannot login to portal"
        description = "I reset password twice but no email arrived"
        ticket = self._track(_create_ticket(subject, description))
        result = run_analysis(ticket)
        evidence = result.get("evidence") or []
        self.assertTrue(evidence)
        blob = " ".join(
            f"{e.get('claim', '')} {e.get('quote', '')}" for e in evidence
        ).lower()
        self.assertTrue(
            "login" in blob
            or "password" in blob
            or "登录" in blob
            or "password" in description.lower()
        )

    def test_pending_reuse_on_duplicate_request(self):
        fixture = get_fixture("D1")
        ticket = self._track(
            _create_ticket(fixture["subject"], fixture["description"])
        )
        # Force a pending row then ensure run_analysis reuses it.
        pending = frappe.get_doc(
            {
                "doctype": "HD AI Analysis",
                "ticket": ticket,
                "status": "Pending",
                "source": "Mock",
            }
        ).insert(ignore_permissions=True)

        result = run_analysis(ticket)
        self.assertEqual(result["name"], pending.name)
        self.assertEqual(result["status"], "Completed")

        # Second full analysis creates a new row (re-analyze path).
        result2 = run_analysis(ticket)
        self.assertNotEqual(result2["name"], result["name"])
        self.assertEqual(result2["status"], "Completed")

    def test_update_confirm_reject_flow(self):
        fixture = get_fixture("D1")
        ticket = self._track(
            _create_ticket(fixture["subject"], fixture["description"])
        )
        analysis = run_analysis(ticket)
        name = analysis["name"]

        updated = update_analysis_fields(
            name, {"summary": "人工修订后的摘要", "category": "登录问题"}
        )
        self.assertEqual(updated["summary"], "人工修订后的摘要")
        self.assertEqual(int(updated["is_edited"] or 0), 1)
        original = updated.get("original_result") or {}
        if isinstance(original, str):
            import json

            original = json.loads(original)
        self.assertNotEqual(original.get("summary"), "人工修订后的摘要")

        # Confirm with selective fields (summary only by default list may include more).
        confirmed = confirm_analysis(name, apply_fields=["summary"])
        self.assertEqual(confirmed["analysis"]["status"], "Confirmed")
        self.assertIn("summary", confirmed["applied_fields"])
        ticket_doc = frappe.get_doc("HD Ticket", ticket)
        self.assertEqual(ticket_doc.summary, "人工修订后的摘要")

        # Idempotent re-confirm
        again = confirm_analysis(name, apply_fields=["summary"])
        self.assertTrue(again.get("idempotent"))

        # Terminal cannot reject
        with self.assertRaises(frappe.ValidationError):
            reject_analysis(name, reason="too late")

        # New analysis then reject without writing ticket business fields
        analysis2 = run_analysis(ticket)
        before_priority = frappe.db.get_value("HD Ticket", ticket, "priority")
        rejected = reject_analysis(analysis2["name"], reason="不准确")
        self.assertEqual(rejected["analysis"]["status"], "Rejected")
        self.assertEqual(
            frappe.db.get_value("HD Ticket", ticket, "priority"), before_priority
        )

    def test_simulate_auto_handle_no_side_effects(self):
        fixture = get_fixture("D1")
        ticket = self._track(
            _create_ticket(fixture["subject"], fixture["description"])
        )
        analysis = run_analysis(ticket)
        ticket_before = frappe.get_doc("HD Ticket", ticket).as_dict()
        sim = simulate_auto_handle(analysis["name"])
        self.assertFalse(sim.get("side_effects"))
        self.assertEqual(sim["branch"]["branch"], "auto_handle")
        ticket_after = frappe.get_doc("HD Ticket", ticket)
        self.assertEqual(ticket_after.status, ticket_before.status)
        self.assertEqual(ticket_after.priority, ticket_before.priority)
        # Analysis remains Completed (not confirmed by simulate)
        self.assertEqual(
            frappe.db.get_value("HD AI Analysis", analysis["name"], "status"),
            "Completed",
        )

    def test_ticket_not_found(self):
        with self.assertRaises(frappe.DoesNotExistError):
            run_analysis("NO-SUCH-TICKET")

    def test_decide_branch_priority(self):
        self.assertEqual(
            decide_branch(
                {
                    "missing_info": [{"field": "order_id"}],
                    "confidence": 0.9,
                    "auto_handleable": 1,
                    "auto_handle_plan": {"steps": ["x"]},
                }
            )["branch"],
            "missing_info",
        )
        self.assertEqual(
            decide_branch(
                {
                    "missing_info": [],
                    "confidence": 0.2,
                    "auto_handleable": 0,
                    "auto_handle_plan": None,
                }
            )["branch"],
            "low_confidence",
        )
        self.assertEqual(
            decide_branch(
                {
                    "missing_info": [],
                    "confidence": 0.9,
                    "auto_handleable": 1,
                    "auto_handle_plan": {"steps": ["x"]},
                }
            )["branch"],
            "auto_handle",
        )

    def test_all_demo_fixtures_have_expected_keys(self):
        for item in DEMO_TICKETS:
            self.assertIn("subject", item)
            self.assertIn("description", item)
            self.assertIn("expected", item)
            self.assertIn("branch", item["expected"])

    def test_default_settings_are_mock_safe(self):
        from helpdesk.ai.config import get_ai_settings, public_ai_settings

        settings = get_ai_settings()
        self.assertIn(settings["mode"], {"Mock", "LLM"})
        # Without enabling LLM, run_analysis stays Mock.
        fixture = get_fixture("D3")
        ticket = self._track(
            _create_ticket(fixture["subject"], fixture["description"])
        )
        result = run_analysis(ticket)
        self.assertEqual(result["source"], "Mock")

        public = public_ai_settings()
        self.assertNotIn("api_key", public)
        self.assertIn("has_api_key", public)

    def test_llm_missing_key_fallback_to_mock(self):
        from helpdesk.ai.analyzers.llm import LLMAnalyzer

        fixture = get_fixture("D1")
        context = {
            "name": "T1",
            "subject": fixture["subject"],
            "description": fixture["description"],
            "combined_text": fixture["subject"] + "\n" + fixture["description"],
            "combined_text_lower": (
                fixture["subject"] + "\n" + fixture["description"]
            ).lower(),
        }
        analyzer = LLMAnalyzer(
            {
                "api_key": None,
                "model": "gpt-test",
                "base_url": "https://example.com/v1",
                "timeout_seconds": 5,
                "fallback_to_mock": True,
                "provider": "openai_compatible",
            }
        )
        result = analyzer.analyze(context)
        self.assertTrue(result.get("raw", {}).get("degraded_to") == "Mock")
        self.assertIn("category", result)
