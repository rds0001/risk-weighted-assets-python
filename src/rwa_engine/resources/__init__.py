"""Access and export immutable resources shipped inside the wheel.

Copyright (C) 2026 RiskDataScience GmbH.
SPDX-License-Identifier: GPL-3.0-only
"""

from __future__ import annotations

import json
from hashlib import sha256
from importlib.resources import files
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from typing import Any, Iterable

from ..exceptions import ResourceError

_MATERIALIZE_LOCK = Lock()
_MATERIALIZED_DIRECTORY: TemporaryDirectory[str] | None = None
_MATERIALIZED_ROOT: Path | None = None


def resource(*parts: str):
    """Return a Traversable below the package resource root."""
    value = files(__name__)
    for part in parts:
        if not part or part in {".", ".."} or "/" in part or "\\" in part:
            raise ResourceError(f"Invalid resource path component: {part!r}")
        value = value.joinpath(part)
    return value


def read_text(*parts: str) -> str:
    value = resource(*parts)
    if not value.is_file():
        raise ResourceError(f"Packaged resource does not exist: {'/'.join(parts)}")
    return value.read_text(encoding="utf-8")


def read_json(*parts: str) -> dict[str, Any]:
    try:
        value = json.loads(read_text(*parts))
    except json.JSONDecodeError as exc:
        raise ResourceError(f"Packaged JSON is invalid: {'/'.join(parts)}") from exc
    if not isinstance(value, dict):
        raise ResourceError(f"Packaged JSON root is not an object: {'/'.join(parts)}")
    return value


def _walk(node, relative: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], Any]]:
    for child in sorted(node.iterdir(), key=lambda item: item.name):
        child_relative = (*relative, child.name)
        if child.is_dir():
            yield from _walk(child, child_relative)
        elif child.is_file() and child.name != "__init__.py" and not child.name.endswith((".pyc", ".pyo")):
            yield child_relative, child


def resource_files(*parts: str) -> tuple[str, ...]:
    node = resource(*parts) if parts else files(__name__)
    if not node.is_dir():
        raise ResourceError(f"Packaged resource directory does not exist: {'/'.join(parts)}")
    return tuple("/".join(relative) for relative, _ in _walk(node))


def export_tree(*parts: str, destination: Path, overwrite: bool = False) -> tuple[Path, ...]:
    """Recursively copy a packaged resource tree to a writable directory."""
    source = resource(*parts) if parts else files(__name__)
    if not source.is_dir():
        raise ResourceError(f"Packaged resource directory does not exist: {'/'.join(parts)}")
    destination = Path(destination)
    entries = tuple(_walk(source))
    conflicts = [
        destination.joinpath(*relative)
        for relative, _ in entries
        if destination.joinpath(*relative).exists() and not overwrite
    ]
    if conflicts:
        preview = ", ".join(str(path) for path in conflicts[:5])
        raise ResourceError(f"Destination already contains packaged resources: {preview}")
    written: list[Path] = []
    for relative, item in entries:
        target = destination.joinpath(*relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(item.read_bytes())
        written.append(target)
    return tuple(written)


def materialized_resource_root() -> Path:
    """Return a process-local filesystem copy for legacy path-based adapters."""
    global _MATERIALIZED_DIRECTORY, _MATERIALIZED_ROOT
    with _MATERIALIZE_LOCK:
        if _MATERIALIZED_ROOT is None:
            _MATERIALIZED_DIRECTORY = TemporaryDirectory(prefix="rwa-engine-resources-")
            _MATERIALIZED_ROOT = Path(_MATERIALIZED_DIRECTORY.name)
            export_tree(destination=_MATERIALIZED_ROOT, overwrite=True)
        return _MATERIALIZED_ROOT


def source_inventory() -> dict[str, Any]:
    return read_json("Standards", "00_manifest", "sources.json")


def verify_packaged_resources() -> dict[str, int]:
    """Verify reference manifests and return compact inventory counts."""
    root = materialized_resource_root()
    profile_manifest = root / "daten/referenzprofile/MID_SIZE_UNIVERSAL/profile_manifest.json"
    payload = json.loads(profile_manifest.read_text(encoding="utf-8"))
    expected = payload.get("sha256", {})
    inputs = profile_manifest.parent / "inputs"
    mismatches = [
        name
        for name, digest in expected.items()
        if not (inputs / name).is_file() or sha256((inputs / name).read_bytes()).hexdigest() != digest
    ]
    if mismatches:
        raise ResourceError(f"Packaged reference profile integrity failed: {mismatches}")
    datasets = list((root / "daten/rechenlaeufe/2026-08-31").glob("*/dataset_manifest.json"))
    return {"files": len(resource_files()), "profile_workbooks": len(expected), "datasets": len(datasets)}
