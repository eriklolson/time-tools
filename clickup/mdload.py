#!/usr/bin/env python3
"""Import a Markdown checklist into ClickUp as category tasks with subtasks.

Script:
    mdload.py
Project:
    ./timetools
Env:
    .env (CLICKUP_TOKEN, CLICKUP_LIST_ID, CLICKUP_CLOSED_STATUS)

Usage:
    python -m clickup.mdload [--md PATH|-] [--list-id ID]
                             [--root-parent TITLE] [--prefix STR]
                             [--dry-run]

Options:
    --md PATH|-          Path to the Markdown file; use '-' to read from stdin.
                         Default: input/tasks.md
    --list-id ID         Override the ClickUp List ID from environment.
    --root-parent TITLE  Optional top-level parent task to nest all categories under.
    --prefix STR         Prefix for each category task name. Default: 'Packing - '
    --dry-run            Print the actions without calling the ClickUp API.

Examples:
    # Import from file into a single top-level parent
    python -m clickup.mdload --md input/tasks.md \
        --root-parent "Philly Wake Trip - Packing" \
        --prefix "Packing - "

    # Preview without creating anything (reads from stdin)
    cat input/tasks.md | python -m clickup.mdload --md - --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Iterable

import requests

from clickup.config import CLICKUP_TOKEN, CLICKUP_LIST_ID, CLOSED_STATUS

API = "https://api.clickup.com/api/v2"
HEADERS = {"Authorization": CLICKUP_TOKEN, "Content-Type": "application/json"}

TOP_RE = re.compile(r"^\s*-\s*\[( |x|X)\]\s*(.+?)\s*$")
SUB_RE = re.compile(r"^\s{2,}-\s*\[( |x|X)\]\s*(.+?)\s*$")


def clean_text(s: str) -> str:
    s = s.strip()
    s = re.sub(r"^\*+|\*+$", "", s)      # strip italics markers
    s = re.sub(r"\s{2,}", " ", s)        # collapse spaces
    return s


def parse_markdown(md: str):
    """Return: [{'category': str, 'items': [(text, checked), ...]}, ...]"""
    blocks: list[dict] = []
    current: dict | None = None
    for raw in md.splitlines():
        line = raw.rstrip()
        if not line:
            continue
        m_top = TOP_RE.match(line)
        if m_top and not line.startswith("  "):
            current = {"category": clean_text(m_top.group(2)), "items": []}
            blocks.append(current)
            continue
        m_sub = SUB_RE.match(line)
        if m_sub and current:
            checked = m_sub.group(1).lower() == "x"
            current["items"].append((clean_text(m_sub.group(2)), checked))
    return blocks


def cu_create_task(list_id: str, name: str, description: str = "", parent: str | None = None) -> str:
    payload = {"name": name, "description": description}
    if parent:
        payload["parent"] = parent
    r = requests.post(f"{API}/list/{list_id}/task", headers=HEADERS, data=json.dumps(payload), timeout=30)
    r.raise_for_status()
    return r.json()["id"]


def cu_set_status(task_id: str, status: str) -> None:
    if not status:
        return
    r = requests.put(f"{API}/task/{task_id}", headers=HEADERS, data=json.dumps({"status": status}), timeout=30)
    if r.status_code >= 300:
        sys.stderr.write(f"[WARN] Could not set status '{status}' on {task_id}: {r.status_code} {r.text}\n")


def main(argv: Iterable[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Create ClickUp subtasks from a Markdown checklist.")
    ap.add_argument("--md", default="input/tasks.md", help="Path to Markdown file (default: input/tasks.md).")
    ap.add_argument("--list-id", default=CLICKUP_LIST_ID, help="Override ClickUp List ID.")
    ap.add_argument("--root-parent", default="", help="Optional top-level parent task title.")
    ap.add_argument("--prefix", default="Packing - ", help="Prefix for each category task name.")
    ap.add_argument("--dry-run", action="store_true", help="Print actions without calling the API.")
    args = ap.parse_args(list(argv) if argv is not None else None)

    with open(args.md, "r", encoding="utf-8") as f:
        md = f.read()

    blocks = parse_markdown(md)
    if not blocks:
        raise SystemExit("No categories/items parsed from the Markdown input.")

    def create_task(name: str, desc: str = "", parent: str | None = None) -> str:
        if args.dry_run:
            print(f"[DRY] create task: {name} (parent={parent})")
            return f"DRY::{name}"
        return cu_create_task(args.list_id, name, desc, parent)

    def set_status(task_id: str, status: str) -> None:
        if args.dry_run:
            print(f"[DRY] set status: {status} on {task_id}")
            return
        cu_set_status(task_id, status)

    root_parent_id: str | None = None
    if args.root_parent:
        root_parent_id = create_task(args.root_parent, "Auto-created parent for imported checklist.")

    for block in blocks:
        parent_name = f"{args.prefix}{block['category']}"
        parent_desc = f"Generated from {os.path.basename(args.md)}."
        parent_id = create_task(parent_name, parent_desc, parent=root_parent_id)

        for item_text, is_checked in block["items"]:
            sub_id = create_task(item_text, parent=parent_id)
            if is_checked and CLOSED_STATUS:
                set_status(sub_id, CLOSED_STATUS)

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
