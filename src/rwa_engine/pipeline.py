"""End-to-End-Orchestrierung und Output-Paket."""

from __future__ import annotations

import json
import platform
from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Mapping

import numpy as np
import pandas as pd

from . import __version__
from .engines import (
    CalculationBundle,
    CalculationContext,
    calculate_capital,
    calculate_ccr_cva_settlement,
    calculate_credit,
    calculate_icaap,
    calculate_irrbb,
    calculate_market,
    calculate_operational,
    calculate_securitisation,
    calculate_trea,
)
from .excel_io import (
    ValidationIssue,
    read_input_workbooks,
    select_official_as_of,
    validate_tables,
    write_result_workbook,
)
from .exceptions import CalculationError
from .parameters import ParameterError, ParameterStore
from .resources import source_inventory


class RunRejected(CalculationError):
    pass


def _input_hash(input_dir: Path) -> str:
    h = sha256()
    for path in sorted(input_dir.glob("*.xlsx")):
        h.update(path.name.encode())
        h.update(path.read_bytes())
    return h.hexdigest()


def _code_hash() -> str:
    digest = sha256()
    for path in sorted(Path(__file__).resolve().parent.glob("*.py")):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _workspace_root(dataset_dir: Path) -> Path:
    resolved = dataset_dir.resolve()
    for parent in (resolved, *resolved.parents):
        if parent.name == "daten":
            return parent.parent
    return resolved.parent


def _validate_legal_files(
    tables: Mapping[str, pd.DataFrame], project_root: Path | None = None
) -> list[ValidationIssue]:
    issues = []
    root = Path(project_root).resolve() if project_root is not None else Path.cwd().resolve()
    inventory_path = root / "Standards" / "00_manifest" / "sources.json"
    inventory_payload = {}
    if inventory_path.is_file():
        try:
            inventory_payload = json.loads(inventory_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, AttributeError):
            inventory_payload = {}
    if not inventory_payload:
        try:
            inventory_payload = source_inventory()
        except Exception:
            inventory_payload = {}
    inventory = {str(item.get("source_id", "")): item for item in inventory_payload.get("sources", [])}
    sources = tables.get("legal_source", pd.DataFrame())
    for _, row in sources.iterrows():
        record = str(row.get("record_id", ""))
        source_id = str(row.get("source_id", "")).strip()
        local = str(row.get("local_file", "")).strip()
        official_url = str(row.get("official_url", "")).strip()
        expected = str(row.get("sha256", "")).strip().lower()
        if not local:
            external = inventory.get(source_id, {})
            if (
                external.get("redistributed") is False
                and external.get("official_url") == official_url
                and external.get("archival_sha256") == expected
            ):
                continue
            issues.append(
                ValidationIssue(
                    "ERROR",
                    "MISSING_SOURCE_PROVENANCE",
                    "legal_source",
                    record,
                    "local_file",
                    "Lokale Quelle oder passender externer Provenienznachweis fehlt",
                )
            )
            continue
        path = Path(local)
        path = path if path.is_absolute() else root / path
        if not path.is_file():
            external = inventory.get(source_id, {})
            if (
                external.get("redistributed") is False
                and external.get("official_url") == official_url
                and external.get("archival_sha256") == expected
            ):
                continue
            issues.append(
                ValidationIssue(
                    "ERROR", "MISSING_LEGAL_FILE", "legal_source", record, "local_file", str(path)
                )
            )
            continue
        actual = sha256(path.read_bytes()).hexdigest()
        if not expected or actual != expected:
            issues.append(
                ValidationIssue(
                    "ERROR",
                    "LEGAL_FILE_HASH_MISMATCH",
                    "legal_source",
                    record,
                    "sha256",
                    f"erwartet={expected}, tatsächlich={actual}",
                )
            )
    return issues


def _config(tables: Mapping[str, pd.DataFrame]) -> dict[str, str]:
    frame = tables["run_config"]
    return {str(r["config_key"]): str(r["config_value"]) for _, r in frame.iterrows()}


def _rule_context(tables: Mapping[str, pd.DataFrame], rule_set_id: str) -> tuple[str, float, str]:
    selected = tables["rule_set"][tables["rule_set"]["rule_set_id"].astype(str) == rule_set_id]
    if len(selected) != 1:
        raise RunRejected(f"Regelsatz fehlt oder ist mehrdeutig: {rule_set_id}")
    row = selected.iloc[0]
    return str(row["market_regime"]), float(row["output_floor_factor"]), str(row["reporting_currency"])


def _run_one(
    tables: Mapping[str, pd.DataFrame], ctx: CalculationContext, *, fully_loaded: bool
) -> CalculationBundle:
    out = CalculationBundle()
    calculate_credit(tables, ctx, out)
    calculate_ccr_cva_settlement(tables, ctx, out)
    calculate_securitisation(tables, ctx, out)
    calculate_market(tables, ctx, out)
    calculate_operational(tables, ctx, out)
    calculate_trea(ctx, out, fully_loaded=fully_loaded)
    calculate_capital(tables, ctx, out)
    calculate_irrbb(tables, ctx, out)
    calculate_icaap(tables, ctx, out)
    registry = set(tables["formula_definition"]["formula_id"].dropna().astype(str))
    used = set()
    for frame in out.results.values():
        if "formula_id" in frame:
            used.update(frame["formula_id"].dropna().astype(str))
    missing = sorted(used - registry)
    out.add_control(
        "FORMULA_REGISTRY",
        not missing,
        "no missing",
        ",".join(missing),
        "Alle Ergebnisformeln sind versioniert registriert",
    )
    tolerance = ctx.parameters.get("CONTROL", "ABSOLUTE_TOLERANCE_EUR")
    expected_market = (
        out.metrics["K_MARKET_LEGACY"]
        if ctx.market_regime.startswith("LEGACY")
        else out.metrics["K_MARKET_FRTB"]
    )
    out.add_control(
        "OFFICIAL_MARKET_REGIME",
        abs(out.metrics["K_MARKET"] - expected_market) < tolerance,
        expected_market,
        out.metrics["K_MARKET"],
        "Marktrisiko entspricht dem im Regelsatz gewählten Regime",
    )
    expected_ilm = ctx.parameters.get("OPRISK", "EU_ILM")
    out.add_control(
        "EU_OPRISK_ILM",
        float(out.results["Operational_Risk"]["ilm_eu"].iloc[0]) == expected_ilm,
        expected_ilm,
        out.results["Operational_Risk"]["ilm_eu"].iloc[0],
        "EU-BIC ohne ILM-Aufschlag",
    )
    out.add_control(
        "RWA_EQUIVALENT_NO_DOUBLE_COUNT",
        not out.results["RWA_Equivalents"]["additive_to_legal_trea"].map(bool).any(),
        False,
        out.results["RWA_Equivalents"]["additive_to_legal_trea"].map(bool).any(),
        "P2R/EC-Äquivalente werden nicht zu legalem TREA addiert",
    )
    out.add_control(
        "FLOOR_ALLOCATION",
        abs(
            float(out.results["Floor_Allocation"]["allocated_floor_uplift"].sum())
            - float(out.metrics["FLOOR_UPLIFT"])
        )
        < tolerance,
        out.metrics["FLOOR_UPLIFT"],
        float(out.results["Floor_Allocation"]["allocated_floor_uplift"].sum()),
        "Floor-Allokation summengleich",
    )
    view = "FULLY_LOADED" if fully_loaded else "APPLIED"
    for frame in out.results.values():
        frame.insert(0, "result_is_official", not fully_loaded)
        frame.insert(0, "result_view", view)
        frame.insert(0, "result_rule_set_id", ctx.rule_set_id)
        frame.insert(0, "result_knowledge_time", ctx.knowledge_time)
        frame.insert(0, "result_as_of_date", ctx.as_of_date)
        frame.insert(0, "result_version", ctx.formula_version)
        frame.insert(0, "calculation_run_id", ctx.run_id)
    return out


def _apply_official_designations(
    raw: Mapping[str, pd.DataFrame], snapshot: dict[str, pd.DataFrame]
) -> dict[str, pd.DataFrame]:
    designations = snapshot.get("official_designation", pd.DataFrame())
    if designations.empty:
        return snapshot
    for _, d in designations.iterrows():
        object_type = str(d["object_type"])
        record_id = str(d["designated_record_id"])
        if object_type not in raw:
            continue
        selected = raw[object_type][raw[object_type]["record_id"].astype(str) == record_id]
        if selected.empty:
            continue
        business_key = str(d["designated_business_key"])
        current = snapshot[object_type]
        snapshot[object_type] = pd.concat(
            [current[current["business_key"].astype(str) != business_key], selected], ignore_index=True
        )
    return snapshot


def _summary_frame(bundle: CalculationBundle, view: str, metadata: Mapping[str, object]) -> pd.DataFrame:
    ordering = [
        "RWEA_KSA",
        "RWEA_IRB",
        "RWEA_CRYPTO",
        "RWEA_CCR",
        "RWEA_SFT",
        "RWEA_CCP",
        "RWEA_SECURITISATION",
        "K_CVA",
        "K_CVA_SA",
        "K_SETTLEMENT",
        "K_LARGE_EXPOSURE",
        "K_MARKET",
        "K_MARKET_IMA_PARALLEL",
        "K_OPERATIONAL",
        "U_TREA",
        "S_TREA",
        "OUTPUT_FLOOR_FACTOR",
        "FLOOR_UPLIFT",
        "TREA",
        "CET1",
        "AT1",
        "T2",
        "TIER1",
        "TOTAL_OWN_FUNDS",
        "CET1_RATIO",
        "TIER1_RATIO",
        "TOTAL_CAPITAL_RATIO",
        "P2R_RATE",
        "P2R_AMOUNT",
        "CBR_RATE",
        "P2G_RATE",
        "CET1_HEADROOM",
        "TIER1_HEADROOM",
        "TOTAL_HEADROOM",
        "LEVERAGE_RATIO",
        "MREL_HEADROOM",
        "TLAC_HEADROOM",
        "WORST_EVE_LOSS",
        "EVE_SOT_RATIO",
        "WORST_NII_DECLINE",
        "NII_SOT_RATIO",
        "EVE_VAR_99",
        "EVE_ES_99",
        "EC_LINEAR",
        "EC_AGGREGATE",
        "ECONOMIC_CAPACITY",
        "ECONOMIC_HEADROOM",
        "NORMATIVE_MIN_HEADROOM",
        "P2R_RWA_EQUIVALENT",
        "EC_RWA_EQUIVALENT",
        "IRRBB_MANAGEMENT_CAPITAL",
        "IRRBB_RWA_EQUIVALENT",
    ]
    return pd.DataFrame(
        [
            {
                "calculation_run_id": metadata["run_id"],
                "result_version": metadata["engine_version"],
                "as_of_date": metadata["as_of_date"],
                "rule_set_id": metadata["rule_set_id"]
                if view == "APPLIED"
                else metadata["parallel_rule_set_id"],
                "is_official": view == "APPLIED",
                "view": view,
                "metric": k,
                "value": bundle.metrics.get(k),
                "unit": "RATE" if any(x in k for x in ["RATIO", "RATE", "FACTOR"]) else "EUR",
            }
            for k in ordering
            if k in bundle.metrics
        ]
    )


def _lineage_frame(bundle: CalculationBundle, run_id: str, rule_set_id: str) -> pd.DataFrame:
    rows = []
    for name, frame in bundle.results.items():
        formula_ids = sorted(set(frame["formula_id"].dropna().astype(str))) if "formula_id" in frame else []
        rows.append(
            {
                "calculation_run_id": run_id,
                "result_table": name,
                "row_count": len(frame),
                "formula_ids": ",".join(formula_ids),
                "rule_set_id": rule_set_id,
                "source": "canonical_official_snapshot",
            }
        )
    return pd.DataFrame(rows)


def _write_outputs(
    output_dir: Path,
    bundle: CalculationBundle,
    parallel: CalculationBundle,
    issues: list[ValidationIssue],
    *,
    metadata: dict[str, object],
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written = []
    summary = pd.concat(
        [_summary_frame(bundle, "APPLIED", metadata), _summary_frame(parallel, "FULLY_LOADED", metadata)],
        ignore_index=True,
    )
    executive = pd.DataFrame(
        [
            {
                "official_status": "APPROVED"
                if not any(i.severity == "ERROR" for i in issues)
                and all(c["passed"] for c in bundle.controls)
                else "REVIEW",
                "as_of_date": metadata["as_of_date"],
                "trea": bundle.metrics["TREA"],
                "floor_binding": bundle.metrics["FLOOR_BINDING"],
                "cet1_ratio": bundle.metrics["CET1_RATIO"],
                "total_capital_ratio": bundle.metrics["TOTAL_CAPITAL_RATIO"],
                "leverage_ratio": bundle.metrics["LEVERAGE_RATIO"],
                "eve_sot_ratio": bundle.metrics["EVE_SOT_RATIO"],
                "nii_sot_ratio": bundle.metrics["NII_SOT_RATIO"],
                "economic_headroom": bundle.metrics["ECONOMIC_HEADROOM"],
            }
        ]
    )
    p = output_dir / f"RWA_OUT_{metadata['as_of_date']}_{metadata['run_id']}_00_Summary.xlsx"
    write_result_workbook(
        p,
        {
            "Executive_Summary": executive,
            "Metrics": summary,
            "Applied_TREA": bundle.results["TREA_Summary"],
            "Fully_Loaded_TREA": parallel.results["TREA_Summary"],
        },
        metadata=metadata,
    )
    written.append(p)
    pillar1 = {
        k: v
        for k, v in bundle.results.items()
        if k
        in {
            "SA_Detail",
            "IRB_Detail",
            "Crypto_Detail",
            "CCR_Detail",
            "SFT_Detail",
            "CCP_Detail",
            "CVA_Summary",
            "CVA_Buckets",
            "Settlement_Detail",
            "Large_Exposure",
            "SEC_Detail",
            "Market_Legacy",
            "FRTB_Buckets",
            "FRTB_Risk_Classes",
            "FRTB_DRC",
            "FRTB_Summary",
            "FRTB_IMA",
            "Operational_Risk",
            "TREA_Summary",
            "Floor_Allocation",
        }
    }
    p = output_dir / f"RWA_OUT_{metadata['as_of_date']}_{metadata['run_id']}_01_Pillar1.xlsx"
    write_result_workbook(p, pillar1, metadata=metadata)
    written.append(p)
    p = output_dir / f"RWA_OUT_{metadata['as_of_date']}_{metadata['run_id']}_02_Capital.xlsx"
    write_result_workbook(
        p,
        {
            k: bundle.results[k]
            for k in [
                "Prudent_Valuation",
                "NPE_Backstop",
                "Capital_Stack",
                "Parallel_Constraints",
                "RWA_Equivalents",
            ]
        },
        metadata=metadata,
    )
    written.append(p)
    p = output_dir / f"RWA_OUT_{metadata['as_of_date']}_{metadata['run_id']}_03_IRRBB.xlsx"
    write_result_workbook(
        p,
        {
            k: bundle.results[k]
            for k in [
                "IRRBB_Repricing_Gap",
                "IRRBB_NII_Bands",
                "IRRBB_Currency_Scenarios",
                "IRRBB_Scenarios",
                "IRRBB_Risk_Measures",
            ]
        },
        metadata=metadata,
    )
    written.append(p)
    p = output_dir / f"RWA_OUT_{metadata['as_of_date']}_{metadata['run_id']}_04_ICAAP.xlsx"
    write_result_workbook(
        p,
        {
            k: bundle.results[k]
            for k in ["EC_Standalone", "EC_Aggregation", "Normative_Projection", "Pillar2_Bridge"]
        },
        metadata=metadata,
    )
    written.append(p)
    issue_df = pd.DataFrame(
        [vars(x) for x in issues], columns=["severity", "code", "table", "row_ref", "field", "message"]
    )
    controls = pd.DataFrame(bundle.controls)
    lineage = pd.concat(
        [
            _lineage_frame(bundle, str(metadata["run_id"]), str(metadata["rule_set_id"])),
            _lineage_frame(parallel, str(metadata["run_id"]), "CRR3-EU-FL"),
        ],
        ignore_index=True,
    )
    p = output_dir / f"RWA_OUT_{metadata['as_of_date']}_{metadata['run_id']}_05_Audit.xlsx"
    write_result_workbook(
        p, {"Validation_Issues": issue_df, "Reconciliations": controls, "Lineage": lineage}, metadata=metadata
    )
    written.append(p)
    return written


def run_dataset(dataset_dir: Path) -> Path:
    dataset_dir = Path(dataset_dir).expanduser().resolve()
    input_dir = dataset_dir / "inputs"
    raw, issues = read_input_workbooks(input_dir)
    issues.extend(validate_tables(raw))
    issues.extend(_validate_legal_files(raw, _workspace_root(dataset_dir)))
    fatal = [i for i in issues if i.severity == "ERROR"]
    now = datetime.now(timezone.utc)
    if not raw.get("run_config") is not None or raw.get("run_config", pd.DataFrame()).empty:
        raise RunRejected("Run-Konfiguration fehlt")
    cfg = _config(raw)
    as_of = date.fromisoformat(cfg["as_of_date"])
    knowledge = datetime.fromisoformat(cfg["knowledge_time"])
    snapshot = {name: select_official_as_of(frame, as_of, knowledge) for name, frame in raw.items()}
    snapshot = _apply_official_designations(raw, snapshot)
    digest = _input_hash(input_dir)
    code_digest = _code_hash()
    fingerprint = sha256(f"{digest}:{code_digest}:{__version__}".encode("utf-8")).hexdigest()
    run_id = f"RUN-{as_of.strftime('%Y%m%d')}-{fingerprint[:10].upper()}"
    output_dir = dataset_dir / "outputs" / run_id
    existing_manifest = output_dir / "run_manifest.json"
    if existing_manifest.is_file():
        existing = json.loads(existing_manifest.read_text(encoding="utf-8"))
        if existing.get("status") == "CALCULATED" and existing.get("calculation_fingerprint") == fingerprint:
            return output_dir
    if fatal:
        metadata = {
            "run_id": run_id,
            "as_of_date": as_of.isoformat(),
            "status": "REJECTED",
            "input_hash": digest,
            "code_hash": code_digest,
            "calculation_fingerprint": fingerprint,
            "engine_version": __version__,
            "created_at": now.isoformat(),
            "rule_set_id": cfg.get("rule_set_id", ""),
        }
        write_result_workbook(
            output_dir / f"RWA_OUT_{as_of}_{run_id}_REJECTED.xlsx",
            {"Validation_Issues": pd.DataFrame([vars(x) for x in issues])},
            metadata=metadata,
        )
        raise RunRejected(f"Inputvalidierung fehlgeschlagen: {len(fatal)} Fehler; Report in {output_dir}")
    try:
        params = ParameterStore(snapshot["regulatory_parameter"])
        applied_regime, applied_floor, applied_currency = _rule_context(snapshot, cfg["rule_set_id"])
        ctx = CalculationContext(
            as_of,
            knowledge,
            cfg["rule_set_id"],
            params,
            applied_currency,
            applied_regime,
            applied_floor,
            run_id,
        )
        applied = _run_one(snapshot, ctx, fully_loaded=False)
        fl_regime, fl_floor, fl_currency = _rule_context(snapshot, "CRR3-EU-FL")
        fl_ctx = CalculationContext(
            as_of, knowledge, "CRR3-EU-FL", params, fl_currency, fl_regime, fl_floor, run_id
        )
        parallel = _run_one(snapshot, fl_ctx, fully_loaded=True)
    except (ParameterError, KeyError, ValueError, ZeroDivisionError) as exc:
        failure = ValidationIssue("ERROR", "CALCULATION_REJECTED", "calculation", "", "", str(exc))
        metadata = {
            "run_id": run_id,
            "as_of_date": as_of.isoformat(),
            "status": "REJECTED",
            "input_hash": digest,
            "code_hash": code_digest,
            "calculation_fingerprint": fingerprint,
            "engine_version": __version__,
            "created_at": now.isoformat(),
            "rule_set_id": cfg.get("rule_set_id", ""),
        }
        write_result_workbook(
            output_dir / f"RWA_OUT_{as_of}_{run_id}_REJECTED.xlsx",
            {"Validation_Issues": pd.DataFrame([vars(failure)])},
            metadata=metadata,
        )
        raise RunRejected(f"Berechnung kontrolliert abgelehnt: {exc}") from exc
    metadata = {
        "run_id": run_id,
        "as_of_date": as_of.isoformat(),
        "knowledge_time": knowledge.isoformat(),
        "status": "CALCULATED",
        "input_hash": digest,
        "code_hash": code_digest,
        "calculation_fingerprint": fingerprint,
        "engine_version": __version__,
        "python_version": platform.python_version(),
        "pandas_version": pd.__version__,
        "numpy_version": np.__version__,
        "created_at": now.isoformat(),
        "rule_set_id": ctx.rule_set_id,
        "parallel_rule_set_id": "CRR3-EU-FL",
        "reporting_currency": ctx.reporting_currency,
    }
    files = _write_outputs(output_dir, applied, parallel, issues, metadata=metadata)
    manifest = {
        **metadata,
        "output_files": [p.name for p in files],
        "control_count": len(applied.controls),
        "controls_passed": sum(bool(c["passed"]) for c in applied.controls),
        "metrics": {
            k: (
                bool(v)
                if isinstance(v, (np.bool_,))
                else float(v)
                if isinstance(v, (np.floating, np.integer))
                else v
            )
            for k, v in applied.metrics.items()
        },
    }
    (output_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return output_dir
