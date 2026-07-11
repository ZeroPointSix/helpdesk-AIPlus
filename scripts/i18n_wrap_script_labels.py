#!/usr/bin/env python3
"""Wrap label: "English" in Vue script blocks with __()."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path("desk/src")

# Only wrap known UI words / phrases that look like user-facing labels.
# Avoid wrapping fieldnames, routes, API keys, etc.
ALLOW_PREFIXES = ()  # unused

# Always skip these exact values
SKIP = {
    "true",
    "false",
    "name",
    "value",
    "fieldname",
    "doctype",
}


def should_wrap(value: str) -> bool:
    if value in SKIP:
        return False
    if not re.search(r"[A-Za-z]", value):
        return False
    # skip lucide icon names etc
    if value.startswith("lucide"):
        return False
    # skip pure snake_case fieldnames
    if re.fullmatch(r"[a-z][a-z0-9_]*", value):
        return False
    # skip kebab with no spaces that look like ids
    if re.fullmatch(r"[a-z0-9\-]+", value) and "-" in value:
        return False
    # must look like human UI text: starts with letter, may have spaces
    if not re.fullmatch(r"""[A-Za-z][A-Za-z0-9 ,\.\-\'\"\?\!:/%#&\(\)\{\}_]*""", value):
        return False
    # Prefer wrapping Title Case / sentence-like, short operators, weekdays
    return True


def main() -> None:
    found: set[str] = set()
    files_changed = 0
    pat = re.compile(r'(label:\s*)(["\'])([^"\']+)\2')

    for path in ROOT.rglob("*.vue"):
        text = path.read_text(encoding="utf-8")
        m = re.search(r"(<script[\s\S]*?</script>)", text)
        if not m:
            continue
        script = m.group(1)

        def repl(mm: re.Match) -> str:
            prefix, quote, value = mm.group(1), mm.group(2), mm.group(3)
            # already wrapped nearby?
            # if the value itself starts with __( skip
            if value.startswith("__("):
                return mm.group(0)
            if not should_wrap(value):
                return mm.group(0)
            found.add(value)
            esc = value.replace("\\", "\\\\").replace("'", "\\'")
            return f"{prefix}__('{esc}')"

        new_script = pat.sub(repl, script)
        if new_script != script:
            text = text[: m.start(1)] + new_script + text[m.end(1) :]
            path.write_text(text, encoding="utf-8")
            files_changed += 1

    print(f"files_changed={files_changed}")
    print(f"unique={len(found)}")
    import json

    Path("scripts/vue_script_label_strings.json").write_text(
        json.dumps(sorted(found), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for s in sorted(found):
        print(s)


if __name__ == "__main__":
    main()
