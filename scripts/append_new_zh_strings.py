#!/usr/bin/env python3
"""Append new frontend i18n strings to zh.po if missing."""
from __future__ import annotations

import re
from pathlib import Path

from zh_translations_vue_labels import TRANSLATIONS as VUE_LABELS
from zh_translations_script_labels import TRANSLATIONS as SCRIPT_LABELS

PO = Path("helpdesk/locale/zh.po")

NEW = {
    "Apps": "应用",
    "These articles may already cover what you are looking for": "这些文章可能已经涵盖了你要查找的内容",
    "(View All)": "（查看全部）",
    "No answers found": "未找到答案",
    "Rephrase the question and try again with some keywords": "请换个问法，并用一些关键词再试一次",
    "Please wait while we search for the answers": "正在搜索答案，请稍候",
    "This will move all articles of the {0} category to the selected category. This change is irreversible!": "这将把分类 {0} 下的所有文章移动到所选分类。此操作不可撤销！",
    "Rating": "评分",
    "Feedback": "反馈",
    "Comment": "评论",
    "via": "通过",
    "Email": "邮件",
    "Portal": "门户",
    "First Response": "首次响应",
    "Resolution": "解决",
    "Call Logs": "通话记录",
    "Knowledge Base": "知识库",
    "View Name": "视图名称",
    "Ticket details": "工单详情",
    "Activity": "活动",
    "Status": "状态",
    "Priority": "优先级",
    "No items in the list": "列表中没有项目",
    "No priorities in the list": "列表中没有优先级",
    "No workdays in the list": "列表中没有工作日",
    "Default": "默认",
    "Select time": "选择时间",
    "Select parent field value": "选择父字段值",
    "Where": "条件",
    "Add": "添加",
    "Add Recurring Holiday": "添加重复假期",
    "Edit Recurring Holiday": "编辑重复假期",
    "Please select start and end date first": "请先选择开始和结束日期",
    "Merge": "合并",
    "Searching...": "搜索中…",
    "Width can be in number, pixel or rem (eg. 3, 30px, 10rem)": "宽度可以是数字、像素或 rem（例如 3、30px、10rem）",
    **VUE_LABELS,
    **SCRIPT_LABELS,
}


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


def escape_po(s: str) -> str:
    return (
        s.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )


def extract_msgid(block: str) -> str | None:
    parts = []
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
    return unescape("".join(parts))


def is_translated(block: str) -> bool:
    m = re.search(r'^msgstr "(.*)"$', block, re.M)
    if m and m.group(1).strip():
        return True
    ms = re.search(r'^msgstr ""\n((?:"[^"]*"\n?)+)', block, re.M)
    if ms and re.sub(r'["\n]', "", ms.group(1)).strip():
        return True
    return False


def main() -> None:
    content = PO.read_text(encoding="utf-8").replace("\r\n", "\n")
    entries = re.split(r"\n\n+", content)
    existing: dict[str, int] = {}
    for i, e in enumerate(entries):
        mid = extract_msgid(e)
        if mid is not None:
            existing[mid] = i

    added = 0
    updated = 0
    for mid, zh in NEW.items():
        if mid in existing:
            idx = existing[mid]
            block = entries[idx]
            if not is_translated(block):
                # fill empty
                if re.search(r'^msgstr ""\s*$', block, re.M):
                    entries[idx] = re.sub(
                        r'^msgstr ""\s*$',
                        f'msgstr "{escape_po(zh)}"',
                        block,
                        count=1,
                        flags=re.M,
                    )
                    updated += 1
            continue
        # append new entry
        entries.append(
            f'#: desk/src (manual i18n)\nmsgid "{escape_po(mid)}"\nmsgstr "{escape_po(zh)}"'
        )
        added += 1

    PO.write_text("\n\n".join(e for e in entries if e.strip()) + "\n", encoding="utf-8")
    print(f"added={added} updated_empty={updated}")


if __name__ == "__main__":
    main()
