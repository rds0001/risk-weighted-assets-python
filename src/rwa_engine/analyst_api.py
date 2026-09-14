"""Bank-analyst access to parameters, rules, results, controls and domains.

Copyright (C) 2026 RiskDataScience GmbH.
SPDX-License-Identifier: GPL-3.0-only
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Mapping

import pandas as pd

from .contracts import TABLE_SPECS
from .excel_io import select_official_as_of
from .exceptions import CalculationError, ConfigurationError
from .models import CalculationResult, ValidationReport
from .parameters import ParameterStore

_AUDIT_COLUMNS = (
    "sequence", "parameter_key", "dimension_1", "dimension_2", "old_value",
    "new_value", "reason", "approved_by",
)


class ControlledTables(dict[str, pd.DataFrame]):
    """Copied canonical tables carrying a governed parameter-override audit trail."""

    def __init__(self, tables: Mapping[str, pd.DataFrame], audit: pd.DataFrame | None = None) -> None:
        super().__init__((name, frame.copy(deep=True)) for name, frame in tables.items())
        self.parameter_override_audit = _empty_audit() if audit is None else audit.copy(deep=True)


@dataclass(frozen=True)
class DomainAnalysis:
    """Focused calculation view containing one risk domain's evidence."""

    domain: str
    view: str
    run_id: str
    metrics: pd.DataFrame
    tables: Mapping[str, pd.DataFrame]
    controls: pd.DataFrame
    parameter_overrides: pd.DataFrame


def _empty_audit() -> pd.DataFrame:
    return pd.DataFrame(columns=_AUDIT_COLUMNS)


def _reference_tables() -> dict[str, pd.DataFrame]:
    from .synthetic import generate_synthetic_tables

    return generate_synthetic_tables(bank_profile="KSA_BANK")


def _parameter_store(parameters: ParameterStore | pd.DataFrame | None) -> ParameterStore:
    if parameters is None:
        return ParameterStore(regulatory_parameters())
    if isinstance(parameters, ParameterStore):
        return parameters
    if isinstance(parameters, pd.DataFrame):
        return ParameterStore(parameters)
    raise ConfigurationError("parameters must be None, a pandas DataFrame or ParameterStore")


def regulatory_parameters(tables: Mapping[str, pd.DataFrame] | None = None) -> pd.DataFrame:
    """Return a copy of the effective inventory of regulatory weights and coefficients."""
    source = _reference_tables() if tables is None else tables
    if "regulatory_parameter" not in source:
        raise ConfigurationError("tables must contain regulatory_parameter")
    return source["regulatory_parameter"].copy(deep=True)


def regulatory_parameter(key: str, dimension_1: object = "", dimension_2: object = "", *,
                         parameters: ParameterStore | pd.DataFrame | None = None) -> float:
    """Return exactly one regulatory parameter identified by key and dimensions."""
    return _parameter_store(parameters).get(key, dimension_1, dimension_2)


def override_regulatory_parameters(
    tables: Mapping[str, pd.DataFrame], overrides: pd.DataFrame, reason: str, approved_by: str,
) -> ControlledTables:
    """Return copied tables with exact, numeric and fully audited parameter overrides."""
    if "regulatory_parameter" not in tables:
        raise ConfigurationError("tables must contain regulatory_parameter")
    required = {"parameter_key", "parameter_value"}
    if not isinstance(overrides, pd.DataFrame) or not required.issubset(overrides.columns):
        raise ConfigurationError("overrides must contain parameter_key and parameter_value")
    if not str(reason).strip() or not str(approved_by).strip():
        raise ConfigurationError("reason and approved_by must be non-empty")
    copied = ControlledTables(tables, getattr(tables, "parameter_override_audit", None))
    if overrides.empty:
        return copied
    candidate = overrides.copy(deep=True)
    for column in ("dimension_1", "dimension_2"):
        if column not in candidate:
            candidate[column] = ""
    values = pd.to_numeric(candidate["parameter_value"], errors="coerce")
    if values.isna().any():
        raise ConfigurationError("Every override value must be numeric")
    frame = copied["regulatory_parameter"]
    rows: list[dict[str, Any]] = []
    for sequence, (_, item) in enumerate(candidate.iterrows(), 1):
        key = "" if pd.isna(item["parameter_key"]) else str(item["parameter_key"]).strip()
        d1 = "" if pd.isna(item["dimension_1"]) else str(item["dimension_1"]).strip()
        d2 = "" if pd.isna(item["dimension_2"]) else str(item["dimension_2"]).strip()
        hit = (
            frame["parameter_key"].fillna("").astype(str).str.strip().eq(key)
            & frame["dimension_1"].fillna("").astype(str).str.strip().eq(d1)
            & frame["dimension_2"].fillna("").astype(str).str.strip().eq(d2)
        )
        if int(hit.sum()) != 1:
            raise ConfigurationError(f"Override must identify exactly one parameter: {key}[{d1},{d2}]")
        old = float(pd.to_numeric(frame.loc[hit, "parameter_value"]).iloc[0])
        new = float(values.loc[item.name])
        frame.loc[hit, "parameter_value"] = new
        rows.append({
            "sequence": sequence, "parameter_key": key, "dimension_1": d1,
            "dimension_2": d2, "old_value": old, "new_value": new,
            "reason": str(reason), "approved_by": str(approved_by),
        })
    previous = copied.parameter_override_audit
    added = pd.DataFrame(rows, columns=_AUDIT_COLUMNS)
    copied.parameter_override_audit = (
        added.reset_index(drop=True)
        if previous.empty
        else pd.concat([previous, added], ignore_index=True)
    )
    return copied


def parameter_overrides(x: Mapping[str, pd.DataFrame] | CalculationResult) -> pd.DataFrame:
    """Return a defensive copy of the parameter-override governance trail."""
    audit = x.parameter_override_audit if isinstance(x, CalculationResult) else getattr(
        x, "parameter_override_audit", None
    )
    return _empty_audit() if audit is None else audit.copy(deep=True)


def formula_catalog(tables: Mapping[str, pd.DataFrame] | None = None) -> pd.DataFrame:
    """Return the versioned formula catalogue from canonical reference tables."""
    source = _reference_tables() if tables is None else tables
    if "formula_definition" not in source:
        raise ConfigurationError("tables must contain formula_definition")
    return source["formula_definition"].copy(deep=True)


def available_rule_sets(tables: Mapping[str, pd.DataFrame] | None = None) -> pd.DataFrame:
    """Return the available applied and fully-loaded regulatory rule sets."""
    source = _reference_tables() if tables is None else tables
    if "rule_set" not in source:
        raise ConfigurationError("tables must contain rule_set")
    return source["rule_set"].copy(deep=True)


def select_rule_set(tables: Mapping[str, pd.DataFrame], rule_set_id: str) -> ControlledTables:
    """Return copied canonical tables configured for a selected known rule set."""
    if rule_set_id not in set(available_rule_sets(tables)["rule_set_id"].astype(str)):
        raise ConfigurationError(f"Unknown rule_set_id: {rule_set_id}")
    copied = ControlledTables(tables, getattr(tables, "parameter_override_audit", None))
    frame = copied["run_config"]
    hit = frame["config_key"].astype(str).eq("rule_set_id")
    if int(hit.sum()) != 1:
        raise ConfigurationError("run_config must contain exactly one rule_set_id")
    frame.loc[hit, "config_value"] = rule_set_id
    return copied


def table_dictionary() -> pd.DataFrame:
    """Return the canonical table, workbook, sheet, Excel-name and size inventory."""
    return pd.DataFrame([
        {"table": name, "workbook": spec.workbook, "sheet": spec.sheet,
         "excel_table": spec.table_name, "required": spec.required,
         "column_count": len(spec.all_columns)}
        for name, spec in TABLE_SPECS.items()
    ])


def table_schema(table: str) -> dict[str, Any]:
    """Return the complete schema contract for one canonical logical table."""
    if table not in TABLE_SPECS:
        raise ConfigurationError(f"Unknown canonical table: {table}")
    spec = TABLE_SPECS[table]
    return {"table": table, "workbook": spec.workbook, "sheet": spec.sheet,
            "excel_table": spec.table_name, "required": spec.required,
            "primary_key": spec.primary_key, "columns": spec.all_columns}


def official_snapshot(
    tables: Mapping[str, pd.DataFrame], *, as_of_date: date | None = None,
    knowledge_time: datetime | None = None,
) -> dict[str, pd.DataFrame]:
    """Return the bitemporal official snapshot effective at business and knowledge time."""
    from .pipeline import _apply_official_designations, _config

    cfg = _config(tables)
    effective_date = as_of_date or date.fromisoformat(cfg["as_of_date"])
    effective_time = knowledge_time or datetime.fromisoformat(cfg["knowledge_time"])
    snapshot = {
        name: select_official_as_of(frame.copy(deep=True), effective_date, effective_time)
        for name, frame in tables.items()
    }
    return _apply_official_designations(tables, snapshot)


def _as_result(x: Mapping[str, pd.DataFrame] | CalculationResult) -> CalculationResult:
    if isinstance(x, CalculationResult):
        return x
    if isinstance(x, Mapping) and all(isinstance(frame, pd.DataFrame) for frame in x.values()):
        from .api import calculate_tables

        return calculate_tables(x)
    raise CalculationError("x must be canonical tables or a CalculationResult")


def _view(result: CalculationResult, view: str, applied: str, parallel: str) -> Any:
    if view not in {"applied", "fully_loaded"}:
        raise ValueError("view must be 'applied' or 'fully_loaded'")
    return getattr(result, applied if view == "applied" else parallel)


def rwa_metrics(result: CalculationResult, view: str = "applied") -> pd.DataFrame:
    """Return tidy metric, numeric value, unit and regulatory-view columns."""
    values = _view(_as_result(result), view, "metrics", "parallel_metrics")
    return pd.DataFrame([
        {"metric": key, "value": value,
         "unit": "RATE" if re.search(r"RATIO|RATE|FACTOR", key) else "EUR",
         "view": view.upper()}
        for key, value in values.items()
    ])


def rwa_metric(result: CalculationResult, metric: str, view: str = "applied") -> Any:
    """Return one named metric from the selected regulatory view."""
    values = _view(_as_result(result), view, "metrics", "parallel_metrics")
    if metric not in values:
        raise CalculationError(f"Unknown metric: {metric}")
    return values[metric]


def rwa_result_tables(result: CalculationResult, view: str = "applied") -> dict[str, pd.DataFrame]:
    """Return defensive copies of all detailed result tables for a view."""
    values = _view(_as_result(result), view, "results", "parallel_results")
    return {name: frame.copy(deep=True) for name, frame in values.items()}


def rwa_result_table(result: CalculationResult, table: str, view: str = "applied") -> pd.DataFrame:
    """Return a defensive copy of one named detailed result table."""
    values = rwa_result_tables(result, view)
    if table not in values:
        raise CalculationError(f"Unknown result table: {table}")
    return values[table]


def rwa_table_names(result: CalculationResult, view: str = "applied") -> tuple[str, ...]:
    """Return the ordered names of detailed calculation result tables."""
    return tuple(rwa_result_tables(result, view))


def rwa_controls(result: CalculationResult, view: str = "applied") -> pd.DataFrame:
    """Return calculation reconciliation and governance controls as a data frame."""
    values = _view(_as_result(result), view, "controls", "parallel_controls")
    return pd.DataFrame([dict(value) for value in values])


def failed_controls(result: CalculationResult, view: str = "applied") -> pd.DataFrame:
    """Return only controls that did not pass in the selected regulatory view."""
    controls = rwa_controls(result, view)
    if controls.empty or "passed" not in controls:
        return controls
    passed = controls["passed"].map(lambda value: value is True or str(value).upper() in {"TRUE", "PASS", "OK"})
    return controls.loc[~passed].copy()


def rwa_validation(result: CalculationResult) -> ValidationReport:
    """Return the immutable input-validation report attached to a calculation."""
    return _as_result(result).validation


def compare_calculation_views(result: CalculationResult) -> pd.DataFrame:
    """Return applied and fully-loaded metrics with their arithmetic difference."""
    applied = rwa_metrics(result, "applied")[["metric", "value"]].rename(columns={"value": "applied"})
    loaded = rwa_metrics(result, "fully_loaded")[["metric", "value"]].rename(
        columns={"value": "fully_loaded"}
    )
    compared = applied.merge(loaded, how="outer", on="metric", sort=True)
    compared["difference"] = compared["fully_loaded"] - compared["applied"]
    return compared


def rwa_summary(result: CalculationResult) -> dict[str, Any]:
    """Return run identity, core prudential metrics, controls and parameter overrides."""
    value = _as_result(result)
    core = ("TREA", "CET1_RATIO", "TOTAL_CAPITAL_RATIO", "LEVERAGE_RATIO",
            "EVE_SOT_RATIO", "NII_SOT_RATIO", "ECONOMIC_HEADROOM")
    return {"run_id": value.run_id, "rule_set_id": value.rule_set_id,
            "metrics": {key: value.metrics[key] for key in core if key in value.metrics},
            "controls": {"passed": value.controls_passed, "total": value.control_count},
            "parameter_overrides": parameter_overrides(value)}


_DOMAIN_SPECS = {
    "credit": (r"^(?:RWEA_KSA|RWEA_IRB|RWEA_CRYPTO|IRB_)",
               ("SA_Detail", "IRB_Detail", "Crypto_Detail"), r"IRB|CREDIT|CRYPTO"),
    "counterparty": (r"^(?:RWEA_CCR|RWEA_SFT|RWEA_CCP|K_CVA|K_SETTLEMENT|K_LARGE)",
                     ("CCR_Detail", "SFT_Detail", "CCP_Detail", "CVA_Summary", "CVA_Buckets",
                      "Settlement_Detail", "Large_Exposure"), r"CCR|CVA|SFT|CCP|SETTLEMENT|LARGE"),
    "securitisation": (r"SECURITISATION", ("SEC_Detail",), r"SEC|FORMULA"),
    "market": (r"MARKET", ("Market_Legacy", "FRTB_Buckets", "FRTB_Risk_Classes", "FRTB_DRC",
                             "FRTB_Summary", "FRTB_IMA"), r"MARKET|FRTB"),
    "operational": (r"OPERATIONAL", ("Operational_Risk",), r"OPRISK"),
    "floor": (r"TREA|FLOOR", ("TREA_Summary", "Floor_Allocation"), r"FLOOR"),
    "capital": (r"CET1|TIER1|TOTAL_|AT1|T2|P2R|CBR|P2G|LEVERAGE|MREL|TLAC",
                ("Prudent_Valuation", "NPE_Backstop", "Capital_Stack", "Parallel_Constraints",
                 "RWA_Equivalents"), r"CAPITAL|OWN_FUNDS|NPE|LEVERAGE|MREL|TLAC"),
    "irrbb": (r"EVE|NII|CSRBB|IRRBB", ("IRRBB_Repricing_Gap", "IRRBB_NII_Bands",
                                        "IRRBB_Currency_Scenarios", "IRRBB_Scenarios",
                                        "IRRBB_Risk_Measures"), r"IRRBB|BEHAVIOUR"),
    "icaap": (r"EC_|ECONOMIC|NORMATIVE", ("EC_Standalone", "EC_Aggregation",
                                           "Normative_Projection", "Pillar2_Bridge"), r"ICAAP|EC_"),
}


def _analyze(x: Mapping[str, pd.DataFrame] | CalculationResult, domain: str, view: str) -> DomainAnalysis:
    result = _as_result(x)
    metric_pattern, table_names, control_pattern = _DOMAIN_SPECS[domain]
    metrics = rwa_metrics(result, view)
    metrics = metrics[metrics["metric"].str.contains(metric_pattern, regex=True)].reset_index(drop=True)
    available = rwa_result_tables(result, view)
    tables = {name: available[name] for name in table_names if name in available}
    controls = rwa_controls(result, view)
    if not controls.empty and "control_code" in controls:
        controls = controls[controls["control_code"].astype(str).str.contains(control_pattern, regex=True)]
    return DomainAnalysis(domain, view, result.run_id, metrics, tables,
                          controls.reset_index(drop=True), parameter_overrides(result))


def analyze_credit_risk(x: Mapping[str, pd.DataFrame] | CalculationResult,
                        view: str = "applied") -> DomainAnalysis:
    """Analyse standardised, IRB and cryptoasset credit risk."""
    return _analyze(x, "credit", view)


def analyze_counterparty_risk(x: Mapping[str, pd.DataFrame] | CalculationResult,
                              view: str = "applied") -> DomainAnalysis:
    """Analyse CCR, SFT, CCP, CVA, settlement and large-exposure results."""
    return _analyze(x, "counterparty", view)


def analyze_securitisation(x: Mapping[str, pd.DataFrame] | CalculationResult,
                           view: str = "applied") -> DomainAnalysis:
    """Analyse securitisation capital and supporting tranche results."""
    return _analyze(x, "securitisation", view)


def analyze_market_risk(x: Mapping[str, pd.DataFrame] | CalculationResult,
                        view: str = "applied") -> DomainAnalysis:
    """Analyse legacy market risk and FRTB sensitivities, DRC and IMA."""
    return _analyze(x, "market", view)


def analyze_operational_risk(x: Mapping[str, pd.DataFrame] | CalculationResult,
                             view: str = "applied") -> DomainAnalysis:
    """Analyse business-indicator and operational-risk capital results."""
    return _analyze(x, "operational", view)


def analyze_output_floor(x: Mapping[str, pd.DataFrame] | CalculationResult,
                         view: str = "applied") -> DomainAnalysis:
    """Analyse standardised TREA, unfloored TREA and output-floor allocation."""
    return _analyze(x, "floor", view)


def analyze_capital_adequacy(x: Mapping[str, pd.DataFrame] | CalculationResult,
                             view: str = "applied") -> DomainAnalysis:
    """Analyse own funds, capital ratios, leverage and MREL/TLAC constraints."""
    return _analyze(x, "capital", view)


def analyze_irrbb(x: Mapping[str, pd.DataFrame] | CalculationResult,
                  view: str = "applied") -> DomainAnalysis:
    """Analyse IRRBB EVE, NII, CSRBB, currency and scenario results."""
    return _analyze(x, "irrbb", view)


def analyze_icaap(x: Mapping[str, pd.DataFrame] | CalculationResult,
                  view: str = "applied") -> DomainAnalysis:
    """Analyse ICAAP economic and normative perspectives and Pillar-2 bridge."""
    return _analyze(x, "icaap", view)


__all__ = [
    "ControlledTables", "DomainAnalysis", "regulatory_parameters", "regulatory_parameter",
    "override_regulatory_parameters", "parameter_overrides", "formula_catalog",
    "available_rule_sets", "select_rule_set", "table_dictionary", "table_schema",
    "official_snapshot", "rwa_metrics", "rwa_metric", "rwa_result_tables", "rwa_result_table",
    "rwa_table_names", "rwa_controls", "failed_controls", "rwa_validation",
    "compare_calculation_views", "rwa_summary", "analyze_credit_risk",
    "analyze_counterparty_risk", "analyze_securitisation", "analyze_market_risk",
    "analyze_operational_risk", "analyze_output_floor", "analyze_capital_adequacy",
    "analyze_irrbb", "analyze_icaap",
]
