#!/usr/bin/env python3
from pathlib import Path
import re

FILES = [
    "desk/src/components/Settings/Holiday/RecurringHolidaysList.vue",
    "desk/src/components/Settings/Holiday/Modals/AddHolidayModal.vue",
    "desk/src/components/Settings/Sla/SlaPriorityList.vue",
    "desk/src/components/Settings/Sla/Modals/EditResponseResolutionModal.vue",
    "desk/src/components/telephony/TwilioCallUI.vue",
    "desk/src/components/ticket/TicketAgentFields.vue",
    "desk/src/pages/knowledge-base/Article.vue",
    "desk/src/pages/ticket/TicketTextEditor.vue",
]

# toast.success("...") or toast.error('...')
PAT = re.compile(r'(toast\.(?:success|error|warning|info)\()(["\'])([^"\']+)\2(\))')


def main() -> None:
    found = set()
    for fp in FILES:
        p = Path(fp)
        text = p.read_text(encoding="utf-8")

        def repl(m: re.Match) -> str:
            prefix, quote, s, suffix = m.group(1), m.group(2), m.group(3), m.group(4)
            # already wrapped?
            # not needed
            found.add(s)
            esc = s.replace("\\", "\\\\").replace("'", "\\'")
            return f"{prefix}__('{esc}'){suffix}"

        new = PAT.sub(repl, text)
        if new != text:
            p.write_text(new, encoding="utf-8")
            print("updated", fp)
        else:
            print("nochange", fp)
    print("strings:")
    for s in sorted(found):
        print("-", s)


if __name__ == "__main__":
    main()
