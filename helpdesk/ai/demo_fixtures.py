# Copyright (c) 2026, ZeroPointSix and contributors
# For license information, please see license.txt

"""Fixed demo ticket fixtures shared by seed script and automated tests.

IMPORTANT: Keep subject/description keywords aligned with MockAnalyzer rules.
Do not invent real personal data; use example.com only.
"""

from __future__ import annotations

DEMO_PREFIX = "[AI-Demo]"
DEMO_RAISED_BY = "ai-demo-customer@example.com"

# Expected branch values align with helpdesk.ai.validators.decide_branch
DEMO_TICKETS: list[dict] = [
    {
        "id": "D1",
        "subject": f"{DEMO_PREFIX} 无法登录账号 / Cannot login",
        "description": (
            "我无法登录系统，已经尝试重置密码两次，但一直没有收到 password reset 邮件。"
            "账号是 demo.user@example.com，浏览器为 Chrome。"
            "请协助排查登录异常。"
        ),
        "raised_by": DEMO_RAISED_BY,
        "expected": {
            "scenario": "login",
            "category": "登录问题",
            "branch": "auto_handle",
            "auto_handleable": 1,
            "min_confidence": 0.70,
            "suggested_role": "技术支持",
            "evidence_keywords": ["登录", "login", "password"],
            "apply_fields": ["priority", "summary"],
        },
    },
    {
        "id": "D2",
        "subject": f"{DEMO_PREFIX} 申请退款",
        "description": (
            "您好，我要申请退款 / refund。"
            "商品有质量问题，希望尽快处理。"
            "（注意：本样例故意不提供订单号，用于信息不足分支演示）"
        ),
        "raised_by": DEMO_RAISED_BY,
        "expected": {
            "scenario": "refund",
            "category": "退款",
            "branch": "missing_info",
            "auto_handleable": 0,
            "max_confidence": 0.45,
            "missing_info_field": "order_id",
            "evidence_keywords": ["退款", "refund"],
            "apply_fields": ["priority", "summary"],
        },
    },
    {
        "id": "D3",
        "subject": f"{DEMO_PREFIX} 我想了解一下产品",
        "description": "随便问问，没有具体问题。",
        "raised_by": DEMO_RAISED_BY,
        "expected": {
            "scenario": "generic",
            "category": "通用咨询",
            "branch": "low_confidence",
            "auto_handleable": 0,
            "max_confidence": 0.50,
            "evidence_keywords": [],
            "apply_fields": ["summary"],
        },
    },
    {
        "id": "D4",
        "subject": f"{DEMO_PREFIX} 需要开具发票",
        "description": "请帮我开具 invoice / 发票，公司抬头为 Example Tech Co.",
        "raised_by": DEMO_RAISED_BY,
        "expected": {
            "scenario": "invoice",
            "category": "发票",
            "branch": "manual",
            "auto_handleable": 0,
            "min_confidence": 0.50,
            "evidence_keywords": ["发票", "invoice"],
            "apply_fields": ["summary"],
        },
    },
    {
        "id": "D5",
        "subject": f"{DEMO_PREFIX} 快递一周未送达",
        "description": "物流显示停更，shipping / 快递已经一周没有更新，请帮忙查一下。",
        "raised_by": DEMO_RAISED_BY,
        "expected": {
            "scenario": "shipping",
            "category": "物流",
            "branch": "manual",
            "auto_handleable": 0,
            "min_confidence": 0.50,
            "evidence_keywords": ["物流", "shipping", "快递"],
            "apply_fields": ["summary"],
        },
    },
]


def get_fixture(demo_id: str) -> dict:
    for item in DEMO_TICKETS:
        if item["id"] == demo_id:
            return item
    raise KeyError(demo_id)
