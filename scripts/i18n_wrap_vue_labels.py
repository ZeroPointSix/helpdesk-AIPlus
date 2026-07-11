#!/usr/bin/env python3
"""Wrap hardcoded label/placeholder/title attrs in Vue with __()."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path("desk/src")

# attribute names to wrap when value is plain English UI text
ATTRS = ("label", "placeholder", "title", "back-label")

SKIP_VALUES = {
    "",
    "true",
    "false",
}


def should_wrap(value: str) -> bool:
    if value in SKIP_VALUES:
        return False
    # already expression-like
    if value.startswith("__(") or "{{" in value:
        return False
    # must contain letters
    if not re.search(r"[A-Za-z]", value):
        return False
    # allow spaces/punctuation typical of UI
    if not re.fullmatch(r"""[A-Za-z0-9 ,\.\-\'\"\?\!:/%#&\(\)\{\}_]+""", value):
        return False
    return True


def escape_js_string(s: str) -> str:
    return s.replace("\\", "\\\\").replace("'", "\\'")


def process_file(path: Path) -> tuple[int, set[str]]:
    text = path.read_text(encoding="utf-8")
    original = text
    found: set[str] = set()

    def repl(m: re.Match) -> str:
        attr = m.group(1)
        quote = m.group(2)
        value = m.group(3)
        # only plain attribute, not already bound with :
        # check previous char isn't :
        if not should_wrap(value):
            return m.group(0)
        found.add(value)
        return f":{attr}=\"__('{escape_js_string(value)}')\""

    # negative lookbehind for : so :label= is skipped; also skip v-bind:label
    pattern = re.compile(
        r'(?<![:\w-])(' + "|".join(ATTRS) + r')=(["\'])([^"\']*)\2'
    )
    text = pattern.sub(repl, text)

    changed = 0
    if text != original:
        path.write_text(text, encoding="utf-8")
        changed = 1
    return changed, found


def main() -> None:
    total_files = 0
    all_strings: set[str] = set()
    for path in ROOT.rglob("*.vue"):
        changed, found = process_file(path)
        total_files += changed
        all_strings |= found
    print(f"files_changed={total_files}")
    print(f"unique_strings={len(all_strings)}")
    out = Path("scripts/vue_label_strings.json")
    import json

    out.write_text(
        json.dumps(sorted(all_strings), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"wrote {out}")
    for s in sorted(all_strings):
        print(s)


if __name__ == "__main__":
    main()
