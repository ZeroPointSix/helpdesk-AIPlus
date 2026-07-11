#!/usr/bin/env python3
"""Apply Chinese translations to helpdesk/locale/zh.po"""
from __future__ import annotations

import re
from pathlib import Path

from zh_translations import TRANSLATIONS as BASE
from zh_translations_extra import TRANSLATIONS as EXTRA

TRANSLATIONS = {**BASE, **EXTRA}

PO_PATH = Path("helpdesk/locale/zh.po")


def escape_po(s: str) -> str:
    return (
        s.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )


def unescape_po(s: str) -> str:
    out = []
    i = 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            nxt = s[i + 1]
            if nxt == "n":
                out.append("\n")
            elif nxt == "t":
                out.append("\t")
            elif nxt == '"':
                out.append('"')
            elif nxt == "\\":
                out.append("\\")
            else:
                out.append(nxt)
            i += 2
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


def extract_msgid(block: str) -> str | None:
    lines = block.splitlines()
    parts: list[str] = []
    collecting = False
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
            else:
                break
    if not parts and not collecting:
        return None
    return unescape_po("".join(parts))


def is_header(block: str) -> bool:
    return bool(re.match(r'msgid ""\s*\nmsgstr', block.strip()))


def is_translated(block: str) -> bool:
    if "msgid_plural" in block:
        msgs = re.findall(r'msgstr\[\d+\] "(.*?)"', block, re.S)
        return any(m.strip() for m in msgs)
    m = re.search(r'^msgstr "(.*)"$', block, re.M)
    if m and m.group(1).strip():
        return True
    ms = re.search(r'^msgstr ""\n((?:"[^"]*"\n?)+)', block, re.M)
    if ms:
        text = re.sub(r'["\n]', "", ms.group(1))
        return bool(text.strip())
    return False


def format_msgstr(translation: str) -> str:
    # Keep single-line msgstr for simplicity; escape newlines as \n
    return f'msgstr "{escape_po(translation)}"'


def apply_translation(block: str, translation: str) -> str:
    # Replace empty msgstr "" or msgstr "" with multiline empty
    # Prefer replacing the msgstr section only
    if re.search(r'^msgstr ""\s*$', block, re.M) and not re.search(
        r'^msgstr ""\n"', block, re.M
    ):
        return re.sub(r'^msgstr ""\s*$', format_msgstr(translation), block, count=1, flags=re.M)
    # multiline empty msgstr
    if re.search(r'^msgstr ""\n((?:"[^"]*"\n?)+)', block, re.M):
        return re.sub(
            r'^msgstr ""\n((?:"[^"]*"\n?)+)',
            format_msgstr(translation) + "\n",
            block,
            count=1,
            flags=re.M,
        )
    # empty single already handled; if msgstr with empty content
    if re.search(r'^msgstr ""$', block, re.M):
        return re.sub(r'^msgstr ""$', format_msgstr(translation), block, count=1, flags=re.M)
    return block


def main() -> None:
    content = PO_PATH.read_text(encoding="utf-8")
    # Normalize line endings
    content = content.replace("\r\n", "\n")
    entries = re.split(r"\n\n+", content)
    applied = 0
    missing_keys: list[str] = []
    already = 0
    new_entries: list[str] = []

    for block in entries:
        if "msgid " not in block or is_header(block):
            new_entries.append(block)
            continue
        if is_translated(block):
            already += 1
            new_entries.append(block)
            continue
        msgid = extract_msgid(block)
        if msgid is None:
            new_entries.append(block)
            continue
        # Try exact match first
        translation = TRANSLATIONS.get(msgid)
        if translation is None:
            # Try with normalized curly quotes / apostrophes variants
            alt = (
                msgid.replace("’", "'")
                .replace("‘", "'")
                .replace("“", '"')
                .replace("”", '"')
            )
            translation = TRANSLATIONS.get(alt)
        if translation is None:
            missing_keys.append(msgid)
            new_entries.append(block)
            continue
        new_block = apply_translation(block, translation)
        if new_block != block and is_translated(new_block):
            applied += 1
            new_entries.append(new_block)
        else:
            # force replace msgstr line(s)
            lines = block.splitlines()
            out_lines = []
            i = 0
            replaced = False
            while i < len(lines):
                line = lines[i]
                if line.startswith("msgstr ") and not replaced:
                    out_lines.append(format_msgstr(translation))
                    replaced = True
                    i += 1
                    # skip continuation lines of old msgstr
                    while i < len(lines) and lines[i].startswith('"'):
                        i += 1
                    continue
                out_lines.append(line)
                i += 1
            new_block = "\n".join(out_lines)
            if is_translated(new_block):
                applied += 1
            else:
                missing_keys.append(f"[apply-fail]{msgid}")
            new_entries.append(new_block)

    # Join with blank lines; preserve trailing newline
    result = "\n\n".join(new_entries)
    if not result.endswith("\n"):
        result += "\n"
    PO_PATH.write_text(result, encoding="utf-8")

    print(f"already_translated_blocks={already}")
    print(f"applied={applied}")
    print(f"missing={len(missing_keys)}")
    for m in missing_keys[:30]:
        print(" MISSING:", repr(m[:120]))


if __name__ == "__main__":
    main()
