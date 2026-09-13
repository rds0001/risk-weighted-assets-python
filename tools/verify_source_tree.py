#!/usr/bin/env python3
"""Validate the source boundary before building archives."""

from __future__ import annotations

import sys
from pathlib import Path

from rwa_engine.resources import resource_files, verify_packaged_resources


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    package = root / "src" / "rwa_engine"
    controlled_roots = [root / name for name in ("src", "docs", "examples", "tests", "tools")]
    prohibited = [
        path
        for controlled_root in controlled_roots
        for path in controlled_root.rglob("*")
        if path.is_file()
        and (
            path.suffix.lower() in {".pdf", ".doc", ".docx", ".odt"}
            or "scaffold" in {part.lower() for part in path.parts[len(root.parts) :]}
        )
    ]
    if prohibited:
        raise AssertionError(f"forbidden source content: {prohibited[:5]}")
    for path in package.rglob("*.py"):
        content = path.read_text(encoding="utf-8")
        if 'parents[2] / "daten"' in content or 'parents[2] / "Standards"' in content:
            raise AssertionError(f"repository-relative runtime path in {path}")
    inventory = verify_packaged_resources()
    if inventory["datasets"] != 2 or inventory["profile_workbooks"] != 16:
        raise AssertionError(f"incomplete resources: {inventory}")
    if any(name.lower().endswith(".pdf") or "scaffold" in name.lower() for name in resource_files()):
        raise AssertionError("forbidden packaged resource")
    print({"status": "ok", "resources": inventory})
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
