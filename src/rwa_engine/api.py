"""Stable, high-level Python API for dataset and in-memory calculations.

Copyright (C) 2026 RiskDataScience GmbH.
SPDX-License-Identifier: GPL-3.0-only
"""

from __future__ import annotations

import json
from datetime import date, datetime
from hashlib import sha256
from pathlib import Path
from typing import Mapping

import pandas as pd

from . import __version__
from .engines import CalculationContext
from .excel_io import ValidationIssue, read_input_workbooks, select_official_as_of, validate_tables
from .exceptions import CalculationError, ValidationError
from .models import CalculationResult, ValidationMessage, ValidationReport
from .parameters import ParameterStore
from .pipeline import (
    _apply_official_designations,
    _code_hash,
    _config,
    _rule_context,
    _run_one,
    _validate_legal_files,
    _workspace_root,
)
from .pipeline import (
    run_dataset as _run_dataset,
)


def _message(issue: ValidationIssue | Mapping[str, object]) -> ValidationMessage:
    def value(name: str) -> str:
        raw = getattr(issue, name, None) if not isinstance(issue, Mapping) else issue.get(name)
        return "" if raw is None or pd.isna(raw) else str(raw)

    return ValidationMessage(
        *(value(name) for name in ("severity", "code", "table", "row_ref", "field", "message"))
    )


def validate_dataset(dataset: str | Path) -> ValidationReport:
    """Validate a canonical dataset without calculating or writing outputs."""
    dataset_path = Path(dataset).expanduser().resolve()
    tables, issues = read_input_workbooks(dataset_path / "inputs")
    issues.extend(validate_tables(tables))
    issues.extend(_validate_legal_files(tables, _workspace_root(dataset_path)))
    return ValidationReport(tuple(_message(issue) for issue in issues))


def calculate_dataset(dataset: str | Path) -> CalculationResult:
    """Validate and calculate an Excel dataset and return structured run metadata."""
    dataset_path = Path(dataset).expanduser().resolve()
    output_dir = _run_dataset(dataset_path)
    manifest = json.loads((output_dir / "run_manifest.json").read_text(encoding="utf-8"))
    output_files = tuple(output_dir / name for name in manifest.get("output_files", []))
    audit = next((path for path in output_files if path.name.endswith("_05_Audit.xlsx")), None)
    controls: tuple[Mapping[str, object], ...] = ()
    messages: tuple[ValidationMessage, ...] = ()
    if audit is not None:
        control_frame = pd.read_excel(audit, sheet_name="Reconciliations", engine="openpyxl")
        controls = tuple(control_frame.where(control_frame.notna(), None).to_dict("records"))
        issue_frame = pd.read_excel(audit, sheet_name="Validation_Issues", engine="openpyxl")
        messages = tuple(
            _message(row) for row in issue_frame.where(issue_frame.notna(), None).to_dict("records")
        )
    return CalculationResult(
        status=str(manifest["status"]),
        run_id=str(manifest["run_id"]),
        engine_version=str(manifest["engine_version"]),
        rule_set_id=str(manifest["rule_set_id"]),
        metrics=dict(manifest.get("metrics", {})),
        controls=controls,
        validation=ValidationReport(messages),
        output_dir=output_dir,
        output_files=output_files,
    )


def _tables_hash(tables: Mapping[str, pd.DataFrame]) -> str:
    digest = sha256()
    for name, frame in sorted(tables.items()):
        digest.update(name.encode("utf-8"))
        digest.update(frame.to_json(orient="split", date_format="iso", default_handler=str).encode("utf-8"))
    return digest.hexdigest()


def calculate_tables(
    tables: Mapping[str, pd.DataFrame], *, run_id: str | None = None,
    project_root: str | Path | None = None,
    parameter_overrides: pd.DataFrame | None = None,
    override_reason: str | None = None,
    override_approved_by: str | None = None,
) -> CalculationResult:
    """Calculate canonical tables, optionally applying governed parameter overrides.

    Overrides never mutate caller data and require both a business reason and an
    approver. The returned result carries the complete old/new-value audit trail.
    """
    source: Mapping[str, pd.DataFrame] = tables
    if parameter_overrides is not None:
        from .analyst_api import override_regulatory_parameters

        source = override_regulatory_parameters(
            tables, parameter_overrides, override_reason or "", override_approved_by or ""
        )
    audit = getattr(source, "parameter_override_audit", None)
    raw = {name: frame.copy(deep=True) for name, frame in source.items()}
    issues = validate_tables(raw)
    issues.extend(_validate_legal_files(raw, Path(project_root) if project_root else None))
    report = ValidationReport(tuple(_message(issue) for issue in issues))
    if not report.valid:
        raise ValidationError(f"Input validation failed with {len(report.errors)} error(s)", report.errors)
    try:
        cfg = _config(raw)
        as_of = date.fromisoformat(cfg["as_of_date"])
        knowledge = datetime.fromisoformat(cfg["knowledge_time"])
        snapshot = {name: select_official_as_of(frame, as_of, knowledge) for name, frame in raw.items()}
        snapshot = _apply_official_designations(raw, snapshot)
        fingerprint = sha256(f"{_tables_hash(raw)}:{_code_hash()}:{__version__}".encode("utf-8")).hexdigest()
        effective_run_id = run_id or f"RUN-{as_of.strftime('%Y%m%d')}-{fingerprint[:10].upper()}"
        parameters = ParameterStore(snapshot["regulatory_parameter"])
        regime, floor, currency = _rule_context(snapshot, cfg["rule_set_id"])
        context = CalculationContext(
            as_of, knowledge, cfg["rule_set_id"], parameters, currency, regime, floor, effective_run_id
        )
        applied = _run_one(snapshot, context, fully_loaded=False)
        fl_regime, fl_floor, fl_currency = _rule_context(snapshot, "CRR3-EU-FL")
        parallel_context = CalculationContext(
            as_of, knowledge, "CRR3-EU-FL", parameters, fl_currency, fl_regime, fl_floor, effective_run_id
        )
        parallel = _run_one(snapshot, parallel_context, fully_loaded=True)
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
        raise CalculationError(f"In-memory calculation failed: {exc}") from exc
    return CalculationResult(
        status="CALCULATED",
        run_id=effective_run_id,
        engine_version=__version__,
        rule_set_id=context.rule_set_id,
        metrics=dict(applied.metrics),
        controls=tuple(dict(control) for control in applied.controls),
        validation=report,
        results=dict(applied.results),
        parallel_results=dict(parallel.results),
        parallel_metrics=dict(parallel.metrics),
        parallel_controls=tuple(dict(control) for control in parallel.controls),
        parameter_override_audit=None if audit is None else audit.copy(deep=True),
    )
