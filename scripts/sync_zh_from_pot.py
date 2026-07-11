#!/usr/bin/env python3
"""Sync zh.po with main.pot: add missing msgids from pot, keep existing translations."""
from __future__ import annotations

import re
from pathlib import Path

POT = Path("helpdesk/locale/main.pot")
PO = Path("helpdesk/locale/zh.po")


def split_entries(content: str) -> list[str]:
    content = content.replace("\r\n", "\n")
    return [e for e in re.split(r"\n\n+", content) if e.strip()]


def is_header(block: str) -> bool:
    return bool(re.match(r'msgid ""\s*\nmsgstr', block.strip()))


def extract_msgid(block: str) -> str | None:
    parts: list[str] = []
    collecting = False
    for line in block.splitlines():
        if line.startswith("msgid "):
            collecting = True
            rest = line[6:]
            if rest.startswith('"') and rest.endswith('"'):
                parts.append(rest[1:-1])
            continue
        if collecting:
            if line.startswith('"') and line.endswith('"'):
                parts.append(line[1:-1])
            else:
                break
    if not collecting:
        return None
    return "".join(parts)


def pot_to_po_entry(block: str) -> str:
    if "msgstr" in block:
        return block
    return block + '\nmsgstr ""'


def main() -> None:
    pot_entries = split_entries(POT.read_text(encoding="utf-8"))
    po_entries = split_entries(PO.read_text(encoding="utf-8"))

    po_header = next(e for e in po_entries if is_header(e))
    po_by_id: dict[str, str] = {}
    for e in po_entries:
        if is_header(e):
            continue
        mid = extract_msgid(e)
        if mid is None:
            continue
        # keep first occurrence
        po_by_id.setdefault(mid, e)

    ordered: list[str] = [po_header]
    added = 0
    kept = 0
    for e in pot_entries:
        if is_header(e):
            continue
        mid = extract_msgid(e)
        if mid is None:
            continue
        if mid in po_by_id:
            ordered.append(po_by_id[mid])
            kept += 1
        else:
            ordered.append(pot_to_po_entry(e))
            added += 1

    obsolete = set(po_by_id) - {
        extract_msgid(e)
        for e in pot_entries
        if not is_header(e) and extract_msgid(e) is not None
    }
    PO.write_text("\n\n".join(ordered) + "\n", encoding="utf-8")
    print(f"kept={kept} added={added} obsolete_dropped={len(obsolete)}")
    for o in sorted(x for x in obsolete if x)[:30]:
        print(" obsolete:", repr(o[:100]))


if __name__ == "__main__":
    main()
