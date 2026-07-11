#!/usr/bin/env python3
"""Find suspect mistranslations in zh.po"""
import re
from pathlib import Path


def unescape(raw: str) -> str:
    out = []
    i = 0
    while i < len(raw):
        if raw[i] == "\\" and i + 1 < len(raw):
            n = raw[i + 1]
            out.append({"n": "\n", "t": "\t", '"': '"', "\\": "\\"}.get(n, n))
            i += 2
        else:
            out.append(raw[i])
            i += 1
    return "".join(out)


def parse_msg(block: str, key: str) -> str:
    parts = []
    collecting = False
    for line in block.splitlines():
        if line.startswith(key + " "):
            collecting = True
            rest = line[len(key) + 1 :]
            if rest.startswith('"') and rest.endswith('"'):
                parts.append(rest[1:-1])
            continue
        if collecting:
            if line.startswith('"') and line.endswith('"'):
                parts.append(line[1:-1])
            else:
                break
    return unescape("".join(parts))


def main():
    content = Path("helpdesk/locale/zh.po").read_text(encoding="utf-8")
    entries = re.split(r"\n\n+", content)
    suspects = []
    for e in entries:
        if "msgid " not in e or re.match(r'msgid ""\s*\nmsgstr', e.strip()):
            continue
        mid = parse_msg(e, "msgid")
        mstr = parse_msg(e, "msgstr")
        if not mstr:
            continue
        reasons = []
        if re.search(r"\bAgent\b", mid) and "代理商" in mstr:
            reasons.append("Agent->代理商")
        if mid == "Agent" and mstr != "客服":
            reasons.append(f"Agent->{mstr}")
        if mid == "Agents" and "代理" in mstr:
            reasons.append(f"Agents->{mstr}")
        if mid == "Account" and mstr == "科目":
            reasons.append("Account->科目")
        if mid == "Acknowledgement" and "确认" in mstr:
            pass
        if "Ticket" in mid and "票" in mstr and "工单" not in mstr:
            reasons.append("Ticket->票")
        if reasons:
            suspects.append((mid, mstr, reasons))

    print(f"suspects={len(suspects)}")
    for mid, mstr, reasons in suspects:
        print("---")
        print("reasons:", ", ".join(reasons))
        print("msgid:", mid[:120])
        print("msgstr:", mstr[:120])


if __name__ == "__main__":
    main()
