# Copyright (c) 2026, ZeroPointSix and contributors
# For license information, please see license.txt

"""Post-analyzer validation shared by Mock and LLM paths."""

from __future__ import annotations

import re
from typing import Any

from helpdesk.ai.analyzers.mock import LOGIN_KEYWORDS, REFUND_KEYWORDS
from helpdesk.ai.types import DEFAULT_CONFIDENCE_THRESHOLD


def apply_validators(result: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Mutate and return analysis result after deterministic checks."""
    text = context.get("combined_text") or ""
    text_lower = context.get("combined_text_lower") or text.lower()

    result = dict(result or {})
    result.setdefault("evidence", [])
    result.setdefault("missing_info", [])
    result.setdefault("auto_handleable", 0)

    _ensure_evidence(result, context)
    _validate_refund_missing_order(result, text, text_lower)
    _validate_login_tech_support(result, text_lower)
    _clamp_confidence(result)
    _normalize_missing_info(result)
    _normalize_auto_handleable(result)
    return result


def _ensure_evidence(result: dict[str, Any], context: dict[str, Any]) -> None:
    evidence = result.get("evidence") or []
    if evidence:
        result["evidence"] = evidence
        return

    subject = context.get("subject") or ""
    description = context.get("description") or ""
    quote = (description or subject or "（无正文）")[:240]
    result["evidence"] = [
        {
            "claim": "基于工单主题/描述生成摘要",
            "quote": quote,
            "source": "description" if description else "subject",
            "weight": 0.3,
            "rule": "fallback_evidence",
        }
    ]


def _validate_refund_missing_order(
    result: dict[str, Any], text: str, text_lower: str
) -> None:
    is_refund = (result.get("category") or "") in {"退款", "Refund"} or any(
        k.lower() in text_lower for k in REFUND_KEYWORDS
    )
    if not is_refund:
        return

    if _has_order_reference(text):
        return

    confidence = float(result.get("confidence") or 0)
    result["confidence"] = min(confidence, 0.45)
    result["auto_handleable"] = 0
    result["auto_handle_plan"] = None

    missing = list(result.get("missing_info") or [])
    if not _missing_contains(missing, "order_id"):
        missing.append(
            {
                "field": "order_id",
                "label": "订单号",
                "reason": "退款处理需要可定位的订单号",
            }
        )
    result["missing_info"] = missing
    result["handoff_reason"] = (
        result.get("handoff_reason")
        or "缺少订单号，无法自动处理退款，建议转人工并补充信息"
    )

    evidence = list(result.get("evidence") or [])
    evidence.append(
        {
            "claim": "补充验证：退款意图缺少订单号",
            "quote": (text or "")[:120],
            "source": "validator",
            "weight": 0.9,
            "rule": "refund_missing_order",
        }
    )
    result["evidence"] = evidence


def _validate_login_tech_support(result: dict[str, Any], text_lower: str) -> None:
    is_login = (result.get("category") or "") in {"登录问题", "Login"} or any(
        k.lower() in text_lower for k in LOGIN_KEYWORDS
    )
    if not is_login:
        return

    result["suggested_role"] = result.get("suggested_role") or "技术支持"
    # Keep team only if already a valid link or leave None for service layer.
    if not result.get("suggested_team"):
        result["suggested_team"] = "Technical Support"


def _clamp_confidence(result: dict[str, Any]) -> None:
    try:
        confidence = float(result.get("confidence") if result.get("confidence") is not None else 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    result["confidence"] = max(0.0, min(1.0, confidence))


def _normalize_missing_info(result: dict[str, Any]) -> None:
    missing = result.get("missing_info") or []
    normalized = []
    for item in missing:
        if isinstance(item, str):
            normalized.append({"field": item, "label": item, "reason": ""})
        elif isinstance(item, dict):
            normalized.append(item)
    result["missing_info"] = normalized


def _normalize_auto_handleable(result: dict[str, Any]) -> None:
    value = result.get("auto_handleable")
    result["auto_handleable"] = 1 if value in (True, 1, "1") else 0
    if result["auto_handleable"] and not result.get("auto_handle_plan"):
        # Auto-handleable without a plan is unsafe; demote.
        result["auto_handleable"] = 0


def _missing_contains(missing: list, field: str) -> bool:
    for item in missing:
        if isinstance(item, str) and item == field:
            return True
        if isinstance(item, dict) and item.get("field") == field:
            return True
    return False


def _has_order_reference(text: str) -> bool:
    if not text:
        return False
    patterns = (
        r"订单\s*[:：#]?\s*\w+",
        r"order\s*(id|no\.?|number)?\s*[:#]?\s*\w+",
        r"#\d{4,}",
        r"\b[A-Z]{0,3}\d{6,}\b",
    )
    for pattern in patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return True
    return False


def decide_branch(
    result: dict[str, Any],
    *,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> dict[str, Any]:
    """Pure branch decision used by #6 and API enrichment.

    Priority:
    1. missing_info non-empty -> missing_info / handoff
    2. confidence below threshold -> handoff
    3. auto_handleable with plan -> auto_handle
    4. else manual
    """
    missing = result.get("missing_info") or []
    confidence = float(result.get("confidence") or 0)
    auto_handleable = result.get("auto_handleable") in (True, 1, "1")
    plan = result.get("auto_handle_plan")

    if missing:
        return {
            "branch": "missing_info",
            "label": "信息不足 / 转人工",
            "reason": result.get("handoff_reason") or "需要补充关键信息后再处理",
            "confidence_threshold": confidence_threshold,
        }
    if confidence < confidence_threshold:
        return {
            "branch": "low_confidence",
            "label": "低置信度 / 转人工",
            "reason": result.get("handoff_reason")
            or f"置信度 {confidence:.2f} 低于阈值 {confidence_threshold:.2f}",
            "confidence_threshold": confidence_threshold,
        }
    if auto_handleable and plan:
        return {
            "branch": "auto_handle",
            "label": "可自动处理（建议/模拟）",
            "reason": "置信度充足且存在自动处理计划（仅建议，不执行真实副作用）",
            "confidence_threshold": confidence_threshold,
        }
    return {
        "branch": "manual",
        "label": "建议人工处理",
        "reason": result.get("handoff_reason") or "需要坐席人工判断与处理",
        "confidence_threshold": confidence_threshold,
    }
