"""Writable workspace management separated from immutable package resources.

Copyright (C) 2026 RiskDataScience GmbH.
SPDX-License-Identifier: GPL-3.0-only
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from . import __version__
from .exceptions import ResourceError
from .resources import export_tree, read_json, resource

WORKSPACE_ENVIRONMENT_VARIABLE = "RWA_WORKSPACE"


@dataclass(frozen=True)
class Workspace:
    """Filesystem locations controlled by the caller."""

    root: Path

    @property
    def data_root(self) -> Path:
        return self.root / "daten"

    @property
    def runs_root(self) -> Path:
        return self.data_root / "rechenlaeufe"

    @property
    def configuration_root(self) -> Path:
        return self.data_root / "konfiguration"

    @property
    def standards_root(self) -> Path:
        return self.root / "Standards"


def default_workspace() -> Workspace:
    configured = os.environ.get(WORKSPACE_ENVIRONMENT_VARIABLE)
    root = Path(configured).expanduser() if configured else Path.cwd() / "rwa-workspace"
    return Workspace(root.resolve())


def create_workspace(path: str | Path, *, overwrite: bool = False) -> Workspace:
    """Export the complete bundled reference environment to *path*."""
    root = Path(path).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    existing = [item for item in root.iterdir() if item.name != "workspace_manifest.json"]
    if existing and not overwrite:
        raise ResourceError(f"Workspace is not empty: {root}")
    export_tree("daten", destination=root / "daten", overwrite=overwrite)
    export_tree("Standards", destination=root / "Standards", overwrite=overwrite)
    manifest = {
        "schema_version": "1.0",
        "engine_version": __version__,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "contains": [
            "configuration",
            "synthetic_reference_profiles",
            "reference_datasets",
            "reference_outputs",
            "source_metadata",
        ],
    }
    (root / "workspace_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return Workspace(root)


def list_reference_profiles() -> tuple[dict[str, Any], ...]:
    profiles = resource("daten", "konfiguration", "profiles")
    values = []
    for item in sorted(profiles.iterdir(), key=lambda entry: entry.name):
        if item.is_file() and item.name.endswith(".yaml"):
            payload = yaml.safe_load(item.read_text(encoding="utf-8"))
            values.append(
                {
                    "profile_id": payload["profile_id"],
                    "profile_version": str(payload["profile_version"]),
                    "description": payload.get("description", ""),
                    "default_dataset_version": payload.get("default_dataset_version"),
                }
            )
    return tuple(values)


def list_reference_datasets() -> tuple[dict[str, Any], ...]:
    root = resource("daten", "rechenlaeufe")
    values = []
    for day in sorted(root.iterdir(), key=lambda item: item.name):
        if not day.is_dir():
            continue
        for dataset in sorted(day.iterdir(), key=lambda item: item.name):
            manifest = dataset.joinpath("dataset_manifest.json")
            if manifest.is_file():
                payload = json.loads(manifest.read_text(encoding="utf-8"))
                values.append(
                    {
                        "id": f"{day.name}/{dataset.name}",
                        "profile": payload.get("bank_profile"),
                        "as_of_date": payload.get("as_of_date"),
                        "version": payload.get("dataset_version"),
                    }
                )
    return tuple(values)


def regulatory_sources() -> tuple[dict[str, Any], ...]:
    return tuple(read_json("Standards", "00_manifest", "sources.json").get("sources", []))
