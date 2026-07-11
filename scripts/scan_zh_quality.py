#!/usr/bin/env python3
"""Scan zh.po for more quality issues."""
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


content = Path("helpdesk/locale/zh.po").read_text(encoding="utf-8")
issues = []
for e in re.split(r"\n\n+", content):
    if "msgid " not in e or re.match(r'msgid ""\s*\nmsgstr', e.strip()):
        continue
    mid = parse_msg(e, "msgid")
    mstr = parse_msg(e, "msgstr")
    if not mstr:
        continue
    # English leftover in short UI strings
    if len(mid) < 40 and re.search(r"[A-Za-z]{4,}", mstr) and not re.search(
        r"(SLA|API|ERPNext|Twilio|Exotel|Desk|PNG|JPG|ICO|URL|ID|JSON|HD|KB|Bcc|Cc)",
        mstr,
    ):
        if re.fullmatch(r"[A-Za-z0-9 _\-\.\,\!\?\'\"\#\{\}\(\)/%&:]+", mid):
            # chinese translation that still looks mostly english
            if len(re.findall(r"[一-鿿]", mstr)) == 0 and mstr != mid:
                issues.append(("still-english", mid, mstr))
    # common wrong ERP terms
    for bad, note in [
        ("代理商", "agent"),
        ("代理列表", "agents"),
        ("科目", "account"),
        ("分辨率", "resolution"),
        ("分辨时间", "resolution time"),
        ("票务", "ticket"),
        ("单据", "maybe doc"),
    ]:
        if bad in mstr and any(
            k in mid.lower()
            for k in ["agent", "account", "resolution", "ticket"]
        ):
            issues.append((note, mid, mstr))
    # identical to english for long meaningful strings (likely untranslated but filled?)
    if mid == mstr and len(mid) > 15 and re.search(r"[A-Za-z]{5}", mid):
        # skip brand/product and code-like
        if not re.search(r"(ERPNext|Frappe|Twilio|Exotel|API|JSON|HTML)", mid):
            issues.append(("same-as-en", mid[:100], mstr[:100]))

print(f"issues={len(issues)}")
for t, a, b in issues[:80]:
    print(f"[{t}] {a!r} => {b!r}")
