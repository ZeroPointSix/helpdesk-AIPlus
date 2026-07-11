#!/usr/bin/env python3
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
for e in re.split(r"\n\n+", content):
    if "msgid " not in e:
        continue
    mid = parse_msg(e, "msgid")
    mstr = parse_msg(e, "msgstr")
    if not mstr:
        continue
    if (
        "代理" in mstr
        or mid == "Account"
        or "分辨" in mstr
        or "票务" in mstr
        or mstr == "科目"
    ):
        print(f"{mid[:100]!r} => {mstr[:100]!r}")
