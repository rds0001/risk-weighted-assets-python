#!/usr/bin/env python3
"""Fail-closed validation of the wheel and source distribution."""

from __future__ import annotations

import argparse
import sys
import tarfile
import zipfile
from email.parser import BytesParser
from email.policy import default
from pathlib import Path, PurePosixPath

FORBIDDEN_SUFFIXES = {".pdf", ".doc", ".docx", ".odt"}
FORBIDDEN_PARTS = {"scaffold", "regularien", "downloads", "downloaded-documents"}


def _forbidden(names: set[str]) -> list[str]:
    failures = []
    for name in names:
        path = PurePosixPath(name.lower())
        if path.suffix in FORBIDDEN_SUFFIXES or any(part in FORBIDDEN_PARTS for part in path.parts):
            failures.append(name)
    return sorted(failures)


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def validate_wheel(path: Path) -> dict[str, int]:
    _assert(path.stat().st_size < 100 * 1024 * 1024, "wheel exceeds the PyPI 100 MiB file boundary")
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        _assert(not _forbidden(names), f"forbidden wheel content: {_forbidden(names)[:5]}")
        metadata_names = [name for name in names if name.endswith(".dist-info/METADATA")]
        _assert(len(metadata_names) == 1, "wheel must contain exactly one METADATA file")
        metadata = BytesParser(policy=default).parsebytes(archive.read(metadata_names[0]))
        _assert(metadata["Name"] == "risk-weighted-assets", "unexpected distribution name")
        _assert(metadata["Version"] == "1.2.0", "unexpected distribution version")
        _assert(metadata["License-Expression"] == "GPL-3.0-only", "SPDX license expression missing")
        _assert("riskdatascience@web.de" in str(metadata["Author-email"]), "author email missing")
        project_urls = set(metadata.get_all("Project-URL", []))
        _assert(
            "Imprint, https://riskdatascience.net/impressum/" in project_urls,
            "corporate imprint link missing from package metadata",
        )
        _assert(
            "Privacy Policy, https://riskdatascience.net/datenschutzerklaerung/" in project_urls,
            "privacy-policy link missing from package metadata",
        )
        _assert("rwa_engine/__init__.py" in names, "Python package missing")
        _assert("rwa_engine/formula_api.py" in names, "granular formula API missing")
        _assert("rwa_engine/analyst_api.py" in names, "bank-analyst API missing")
        _assert("rwa_engine/py.typed" in names, "typed-package marker missing")
        _assert("rwa_engine/web/static/index.html" in names, "web application assets missing")
        _assert(
            "rwa_engine/resources/Standards/00_manifest/sources.json" in names,
            "source inventory missing",
        )
        input_books = {
            name
            for name in names
            if name.startswith("rwa_engine/resources/daten/")
            and "/inputs/" in name
            and name.endswith(".xlsx")
        }
        output_books = {
            name
            for name in names
            if name.startswith("rwa_engine/resources/daten/")
            and "/outputs/" in name
            and name.endswith(".xlsx")
        }
        manifests = {name for name in names if name.endswith("/dataset_manifest.json")}
        _assert(len(input_books) == 48, f"expected 48 bundled input workbooks, found {len(input_books)}")
        _assert(len(output_books) == 12, f"expected 12 bundled output workbooks, found {len(output_books)}")
        _assert(len(manifests) == 2, f"expected two dataset manifests, found {len(manifests)}")
        entry_names = [name for name in names if name.endswith(".dist-info/entry_points.txt")]
        _assert(len(entry_names) == 1, "console entry-point metadata missing")
        entries = archive.read(entry_names[0]).decode("utf-8")
        _assert("rwa = rwa_engine.cli:main" in entries, "rwa entry point missing")
        _assert("rwa-web = rwa_engine.web.server:main" in entries, "rwa-web entry point missing")
    return {"files": len(names), "input_workbooks": len(input_books), "output_workbooks": len(output_books)}


def validate_sdist(path: Path) -> dict[str, int]:
    with tarfile.open(path, "r:gz") as archive:
        names = {member.name for member in archive.getmembers() if member.isfile()}
    _assert(not _forbidden(names), f"forbidden sdist content: {_forbidden(names)[:5]}")
    required_endings = {
        "/LICENSE",
        "/README.md",
        "/pyproject.toml",
        "/docs/PYTHON_API.md",
        "/docs/GRANULAR_ANALYST_API.md",
        "/tests/test_granular_analyst_api.py",
        "/tests/test_public_api.py",
        "/tools/validate_distribution.py",
        "/src/rwa_engine/resources/Standards/00_manifest/sources.json",
    }
    for ending in required_endings:
        _assert(any(name.endswith(ending) for name in names), f"sdist member missing: {ending}")
    return {"files": len(names)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dist", type=Path, nargs="?", default=Path("dist"))
    args = parser.parse_args(argv)
    wheels = sorted(args.dist.glob("*.whl"))
    sdists = sorted(args.dist.glob("*.tar.gz"))
    _assert(len(wheels) == 1, f"expected one wheel, found {len(wheels)}")
    _assert(len(sdists) == 1, f"expected one sdist, found {len(sdists)}")
    print({"wheel": validate_wheel(wheels[0]), "sdist": validate_sdist(sdists[0])})
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
