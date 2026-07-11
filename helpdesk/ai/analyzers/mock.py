# Copyright (c) 2026, ZeroPointSix and contributors
# For license information, please see license.txt

"""Deterministic rule-based mock analyzer for P0 demos (no API key required)."""

from __future__ import annotations

import re
from typing import Any

import frappe

from helpdesk.ai.types import AnalysisResult


LOGIN_KEYWORDS = (
    "登录",
    "登陆",
    "login",
    "password",
    "passwd",
    "密码",
    "验证码",
    "reset password",
    "password reset",
    "无法登录",
    "can't log in",
    "cannot login",
    "cannot log in",
    "sign in",
    "signin",
)

REFUND_KEYWORDS = (
    "退款",
    "退货",
    "refund",
    "return",
    "chargeback",
    "money back",
)

INVOICE_KEYWORDS = ("发票", "invoice", "receipt", "开票")
SHIPPING_KEYWORDS = ("物流", "快递", "shipping", "delivery", "tracking", "运单")


class MockAnalyzer:
    name = "rule_mock"
    source = "Mock"
    model_name = "mock-v1"

    def analyze(self, context: dict[str, Any]) -> AnalysisResult:
        text = context.get("combined_text") or ""
        text_lower = context.get("combined_text_lower") or text.lower()
        subject = context.get("subject") or ""
        description = context.get("description") or ""

        scenario = self._detect_scenario(text_lower)
        if scenario == "login":
            result = self._login_result(subject, description, text)
        elif scenario == "refund":
            result = self._refund_result(subject, description, text)
        elif scenario == "invoice":
            result = self._invoice_result(subject, description, text)
        elif scenario == "shipping":
            result = self._shipping_result(subject, description, text)
        else:
            result = self._generic_result(subject, description, text)

        result["mapped_ticket_type"] = self._resolve_ticket_type(result.get("category"))
        result["priority"] = self._resolve_priority(result.get("priority"))
        result["suggested_team"] = self._resolve_team(result.get("suggested_team"))
        result["raw"] = {
            "scenario": scenario,
            "analyzer": self.name,
            "model_name": self.model_name,
        }
        return result

    # ------------------------------------------------------------------
    # Scenario detection (deterministic keyword order)
    # ------------------------------------------------------------------

    def _detect_scenario(self, text_lower: str) -> str:
        if self._contains_any(text_lower, LOGIN_KEYWORDS):
            return "login"
        if self._contains_any(text_lower, REFUND_KEYWORDS):
            return "refund"
        if self._contains_any(text_lower, INVOICE_KEYWORDS):
            return "invoice"
        if self._contains_any(text_lower, SHIPPING_KEYWORDS):
            return "shipping"
        return "generic"

    @staticmethod
    def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
        return any(k.lower() in text for k in keywords)

    # ------------------------------------------------------------------
    # Scenario templates
    # ------------------------------------------------------------------

    def _login_result(self, subject: str, description: str, text: str) -> AnalysisResult:
        quote = self._pick_quote(text, LOGIN_KEYWORDS) or subject or description[:120]
        return {
            "category": "登录问题",
            "priority": "High",
            "summary": "用户反馈登录异常或密码重置失败，信息相对完整，建议技术支持跟进。",
            "confidence": 0.88,
            "evidence": [
                {
                    "claim": "工单内容命中登录/密码相关关键词",
                    "quote": quote[:240],
                    "source": "description" if description else "subject",
                    "weight": 0.85,
                    "rule": "login_keywords",
                }
            ],
            "suggested_role": "技术支持",
            "suggested_team": "Technical Support",
            "suggested_agent": None,
            "auto_handleable": 1,
            "auto_handle_plan": {
                "title": "登录异常自动处理建议（模拟）",
                "steps": [
                    "校验账号是否存在且未锁定",
                    "触发密码重置邮件（模拟，不真实发送）",
                    "引导用户清理缓存后重试登录",
                    "若仍失败则升级人工排查会话/SSO",
                ],
                "simulated_result": "模拟：已生成重置指引，未对真实账号执行任何变更",
                "simulated": True,
                "warnings": ["本计划仅为建议/模拟，不会真实改密或发信"],
            },
            "missing_info": [],
            "handoff_reason": None,
        }

    def _refund_result(self, subject: str, description: str, text: str) -> AnalysisResult:
        quote = self._pick_quote(text, REFUND_KEYWORDS) or subject or description[:120]
        has_order = self._has_order_reference(text)
        if has_order:
            return {
                "category": "退款",
                "priority": "Medium",
                "summary": "用户申请退款，已提供可识别订单线索，建议客服审核后退款流程。",
                "confidence": 0.72,
                "evidence": [
                    {
                        "claim": "工单命中退款意图，并包含订单相关线索",
                        "quote": quote[:240],
                        "source": "description" if description else "subject",
                        "weight": 0.7,
                        "rule": "refund_keywords+order_ref",
                    }
                ],
                "suggested_role": "客服专员",
                "suggested_team": "Customer Support",
                "suggested_agent": None,
                "auto_handleable": 0,
                "auto_handle_plan": None,
                "missing_info": [],
                "handoff_reason": "退款涉及资金操作，需人工审核",
            }

        return {
            "category": "退款",
            "priority": "Medium",
            "summary": "用户申请退款，但缺少订单号等关键信息，置信度降低，建议补充信息后转人工。",
            "confidence": 0.42,
            "evidence": [
                {
                    "claim": "工单命中退款意图，但未发现订单号模式",
                    "quote": quote[:240],
                    "source": "description" if description else "subject",
                    "weight": 0.6,
                    "rule": "refund_keywords-missing_order",
                }
            ],
            "suggested_role": "客服专员",
            "suggested_team": "Customer Support",
            "suggested_agent": None,
            "auto_handleable": 0,
            "auto_handle_plan": None,
            "missing_info": [
                {
                    "field": "order_id",
                    "label": "订单号",
                    "reason": "退款处理需要可定位的订单号",
                }
            ],
            "handoff_reason": "缺少订单号，无法自动处理退款，建议转人工并补充信息",
        }

    def _invoice_result(self, subject: str, description: str, text: str) -> AnalysisResult:
        quote = self._pick_quote(text, INVOICE_KEYWORDS) or subject or description[:120]
        return {
            "category": "发票",
            "priority": "Low",
            "summary": "用户咨询发票/开票相关问题，建议财务或客服处理。",
            "confidence": 0.7,
            "evidence": [
                {
                    "claim": "工单命中发票相关关键词",
                    "quote": quote[:240],
                    "source": "description" if description else "subject",
                    "weight": 0.65,
                    "rule": "invoice_keywords",
                }
            ],
            "suggested_role": "财务支持",
            "suggested_team": "Finance",
            "suggested_agent": None,
            "auto_handleable": 0,
            "auto_handle_plan": None,
            "missing_info": [],
            "handoff_reason": "发票开具需人工核对抬头与金额",
        }

    def _shipping_result(self, subject: str, description: str, text: str) -> AnalysisResult:
        quote = self._pick_quote(text, SHIPPING_KEYWORDS) or subject or description[:120]
        return {
            "category": "物流",
            "priority": "Medium",
            "summary": "用户咨询物流/配送进度，建议物流支持跟进。",
            "confidence": 0.72,
            "evidence": [
                {
                    "claim": "工单命中物流相关关键词",
                    "quote": quote[:240],
                    "source": "description" if description else "subject",
                    "weight": 0.65,
                    "rule": "shipping_keywords",
                }
            ],
            "suggested_role": "物流支持",
            "suggested_team": "Logistics",
            "suggested_agent": None,
            "auto_handleable": 0,
            "auto_handle_plan": None,
            "missing_info": [],
            "handoff_reason": "物流查询通常需要人工对接承运商信息",
        }

    def _generic_result(self, subject: str, description: str, text: str) -> AnalysisResult:
        quote = (description or subject or text or "（无正文）")[:240]
        return {
            "category": "通用咨询",
            "priority": "Medium",
            "summary": "未命中明确业务规则，给出通用摘要与人工处理建议，不伪造高置信度。",
            "confidence": 0.35,
            "evidence": [
                {
                    "claim": "未命中登录/退款等专用规则，使用兜底分类",
                    "quote": quote,
                    "source": "description" if description else "subject",
                    "weight": 0.3,
                    "rule": "generic_fallback",
                }
            ],
            "suggested_role": "客服专员",
            "suggested_team": "Customer Support",
            "suggested_agent": None,
            "auto_handleable": 0,
            "auto_handle_plan": None,
            "missing_info": [],
            "handoff_reason": "意图不明确，建议人工分类与处理",
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _pick_quote(text: str, keywords: tuple[str, ...]) -> str:
        if not text:
            return ""
        lower = text.lower()
        for keyword in keywords:
            idx = lower.find(keyword.lower())
            if idx >= 0:
                start = max(0, idx - 40)
                end = min(len(text), idx + len(keyword) + 80)
                return text[start:end].strip()
        return text[:120].strip()

    @staticmethod
    def _has_order_reference(text: str) -> bool:
        if not text:
            return False
        patterns = (
            r"订单\s*[:：#]?\s*\w+",
            r"order\s*(id|no\.?|number)?\s*[:#]?\s*\w+",
            r"#\d{4,}",
            r"\b[A-Z]{0,3}\d{6,}\b",
        )
        lower = text.lower()
        if "订单号" in text or "order id" in lower or "order number" in lower:
            # Presence of the label alone is not enough; still check digits nearby.
            pass
        for pattern in patterns:
            if re.search(pattern, text, flags=re.IGNORECASE):
                return True
        return False

    @staticmethod
    def _resolve_priority(name: str | None) -> str | None:
        if not name:
            return None
        if frappe.db.exists("HD Ticket Priority", name):
            return name
        # Soft fallbacks commonly present in Helpdesk installs.
        for candidate in (name, "Medium", "High", "Low", "Urgent"):
            if candidate and frappe.db.exists("HD Ticket Priority", candidate):
                return candidate
        return None

    @staticmethod
    def _resolve_ticket_type(category: str | None) -> str | None:
        if not category:
            return None
        if frappe.db.exists("HD Ticket Type", category):
            return category
        # Try a few common English aliases; never invent links.
        aliases = {
            "登录问题": ["Login", "Account", "Technical"],
            "退款": ["Refund", "Billing"],
            "发票": ["Invoice", "Billing"],
            "物流": ["Shipping", "Delivery"],
            "通用咨询": ["General", "Other", "Query"],
        }
        for candidate in aliases.get(category, []):
            if frappe.db.exists("HD Ticket Type", candidate):
                return candidate
        return None

    @staticmethod
    def _resolve_team(name: str | None) -> str | None:
        if not name:
            return None
        if frappe.db.exists("HD Team", name):
            return name
        return None
