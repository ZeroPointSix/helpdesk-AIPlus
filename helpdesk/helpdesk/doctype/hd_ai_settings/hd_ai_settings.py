# Copyright (c) 2026, ZeroPointSix and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class HDAISettings(Document):
    def validate(self):
        if self.confidence_threshold not in (None, ""):
            value = flt(self.confidence_threshold)
            if value < 0 or value > 1:
                frappe.throw(
                    _("Confidence threshold must be between 0 and 1"),
                    title=_("Invalid Threshold"),
                )
            self.confidence_threshold = value

        if self.mode == "LLM" and self.enabled:
            # Soft warning only: fallback may still allow demo without a key.
            if not self.get_password("api_key") and not self.fallback_to_mock:
                frappe.msgprint(
                    _(
                        "LLM mode is enabled without an API key and fallback is off. "
                        "Analysis requests will fail until a key is configured."
                    ),
                    indicator="orange",
                    alert=True,
                )
