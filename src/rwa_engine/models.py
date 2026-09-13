"""Stable result models exposed by the public API.

Copyright (C) 2026 RiskDataScience GmbH.
SPDX-License-Identifier: GPL-3.0-only
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class ValidationMessage:
    severity: str
    code: str
    table: str
    row_ref: str
    field: str
    message: str


@dataclass(frozen=True)
class ValidationReport:
    messages: tuple[ValidationMessage, ...] = ()

    @property
    def errors(self) -> tuple[ValidationMessage, ...]:
        return tuple(item for item in self.messages if item.severity == "ERROR")

    @property
    def warnings(self) -> tuple[ValidationMessage, ...]:
        return tuple(item for item in self.messages if item.severity == "WARNING")

    @property
    def valid(self) -> bool:
        return not self.errors


@dataclass(frozen=True)
class CalculationResult:
    status: str
    run_id: str
    engine_version: str
    rule_set_id: str
    metrics: Mapping[str, Any]
    controls: tuple[Mapping[str, Any], ...]
    validation: ValidationReport
    output_dir: Path | None = None
    output_files: tuple[Path, ...] = ()
    results: Mapping[str, Any] = field(default_factory=dict, repr=False)
    parallel_results: Mapping[str, Any] = field(default_factory=dict, repr=False)

    @property
    def controls_passed(self) -> int:
        return sum(bool(control.get("passed")) for control in self.controls)

    @property
    def control_count(self) -> int:
        return len(self.controls)

    @property
    def successful(self) -> bool:
        return (
            self.status == "CALCULATED"
            and self.validation.valid
            and self.controls_passed == self.control_count
        )
