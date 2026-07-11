#!/usr/bin/env python3
"""Analyze and list untranslated entries in zh.po"""
import re
import json
from pathlib import Path

PO_PATH = Path("helpdesk/locale/zh.po")
OUT_PATH = Path("scripts/zh_untranslated.json")


def unescape_po(s: str) -> str:
    return (
        s.replace("\\n", "\n")
        .replace("\\t", "\t")
        .replace('\\"', '"')
        .replace("\\\\", "\\")
    )


def parse_msgid(block: str) -> str:
    # match msgid "..." or multiline msgid ""\n"..."\n
    m = re.search(r'^msgid (""(?:\n"[^"]*")*|".*")$', block, re.M)
    if not m:
        # try looser
        lines = block.splitlines()
        collecting = False
        parts = []
        for line in lines:
            if line.startswith("msgid "):
                collecting = True
                rest = line[len("msgid ") :]
                if rest.startswith('"') and rest.endswith('"'):
                    parts.append(rest[1:-1])
                continue
            if collecting:
                if line.startswith('"') and line.endswith('"'):
                    parts.append(line[1:-1])
                elif line.startswith("msgid_plural") or line.startswith("msgstr"):
                    break
                else:
                    break
        return unescape_po("".join(parts))
    raw = m.group(1)
    parts = re.findall(r'"([^"]*)"', raw)
    return unescape_po("".join(parts))


def is_translated(block: str) -> bool:
    if "msgid_plural" in block:
        msgs = re.findall(r'msgstr\[\d+\] "(.*?)"', block, re.S)
        return any(m.strip() for m in msgs)
    # single msgstr
    m = re.search(r'^msgstr "(.*)"$', block, re.M)
    if m and m.group(1).strip():
        return True
    # multiline
    ms = re.search(r'^msgstr ""\n((?:"[^"]*"\n?)+)', block, re.M)
    if ms:
        text = re.sub(r'["\n]', "", ms.group(1))
        return bool(text.strip())
    return False


def main():
    content = PO_PATH.read_text(encoding="utf-8")
    entries = re.split(r"\n\n+", content)
    untranslated = []
    total = translated = 0
    for e in entries:
        if "msgid " not in e:
            continue
        if re.match(r'msgid ""\s*\nmsgstr', e.strip()):
            continue
        total += 1
        if is_translated(e):
            translated += 1
            continue
        msgid = parse_msgid(e)
        ctx_m = re.search(r'^msgctxt "(.*)"$', e, re.M)
        untranslated.append(
            {
                "msgid": msgid,
                "msgctxt": ctx_m.group(1) if ctx_m else None,
            }
        )
    print(f"total={total} translated={translated} untranslated={len(untranslated)}")
    print(f"coverage={100*translated/total:.1f}%")
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(untranslated, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"wrote {OUT_PATH}")
    for i, u in enumerate(untranslated, 1):
        ctx = f" [{u['msgctxt']}]" if u["msgctxt"] else ""
        mid = u["msgid"].replace("\n", "\\n")
        print(f"{i}|{ctx}|{mid[:200]}")


if __name__ == "__main__":
    main()
