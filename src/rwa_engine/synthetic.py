"""Materialisierung externer synthetischer Referenzprofile.

Das Modul enthält weder Geschäftsbestände noch Verteilungen, Szenarien,
Marktdaten oder regulatorische Werte. Referenzdaten liegen als kanonische
Excel-Pakete vor; Regelwerte stammen aus einer versionierten YAML-Quelle und
werden in die Excel-Parametertabelle materialisiert.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from typing import Any

import pandas as pd

from .config_io import ConfigurationError, load_profile, load_regulatory_config, regulatory_parameter_items
from .contracts import COMMON_COLUMNS, TABLE_SPECS
from .excel_io import read_input_workbooks, validate_tables, write_input_workbooks
from .resources import materialized_resource_root


def _profile_resource_root(config_root: Path | None) -> Path:
    if config_root is None:
        return materialized_resource_root()
    resolved = Path(config_root).expanduser().resolve()
    for candidate in (resolved, *resolved.parents):
        if candidate.name == "daten":
            return candidate.parent
    return resolved


def _resolve(path: str | Path, resource_root: Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else resource_root / value


def _file_hash(path: Path) -> str:
    digest = sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _verify_profile(profile: dict[str, Any], resource_root: Path) -> tuple[Path, Path]:
    source = _resolve(profile["source_inputs"], resource_root)
    manifest_path = _resolve(profile["integrity_manifest"], resource_root)
    if not source.is_dir() or not manifest_path.is_file():
        raise ConfigurationError(f"Referenzprofil unvollständig: {source}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = manifest.get("sha256", {})
    actual_names = {path.name for path in source.glob("*.xlsx")}
    if actual_names != set(expected):
        raise ConfigurationError(
            "Dateimenge des Referenzprofils stimmt nicht mit dem Integritätsmanifest überein"
        )
    mismatches = [name for name, digest in expected.items() if _file_hash(source / name) != digest]
    if mismatches:
        raise ConfigurationError(f"Integritätsprüfung des Referenzprofils fehlgeschlagen: {mismatches}")
    return source, manifest_path


@lru_cache(maxsize=None)
def _load_reference_cached(source_text: str, manifest_digest: str) -> dict[str, pd.DataFrame]:
    """Pro Prozess einmal lesen; Manifest-Digest invalidiert geänderte Profile."""
    tables, issues = read_input_workbooks(Path(source_text))
    errors = [issue for issue in issues if issue.severity == "ERROR"]
    if errors:
        raise ConfigurationError(f"Referenzprofil nicht lesbar: {errors}")
    return tables


def _shift_temporal_columns(
    tables: dict[str, pd.DataFrame], profile: dict[str, Any], target_as_of: date
) -> None:
    base = date.fromisoformat(str(profile["base_as_of_date"]))
    delta = target_as_of - base
    shift = profile.get("shift_columns", {})
    immutable = set(shift.get("immutable_date_columns", []))
    date_columns = set(shift.get("date", [])) - immutable
    datetime_columns = set(shift.get("datetime", []))
    for frame in tables.values():
        for column in date_columns & set(frame.columns):
            parsed = pd.to_datetime(frame[column], errors="coerce")
            mask = parsed.notna()
            frame.loc[mask, column] = (parsed.loc[mask] + pd.Timedelta(days=delta.days)).dt.date
        for column in datetime_columns & set(frame.columns):
            parsed = pd.to_datetime(frame[column], errors="coerce")
            mask = parsed.notna()
            frame.loc[mask, column] = parsed.loc[mask] + pd.Timedelta(days=delta.days)


def _common_metadata(template: pd.Series, key: str, as_of: date, sequence: int) -> dict[str, Any]:
    values = {column: template.get(column) for column in COMMON_COLUMNS}
    values.update(record_id=f"{key}::v1", business_key=key, version_no=1, as_of_date=as_of)
    return values


def _materialize_rules(
    tables: dict[str, pd.DataFrame], profile: dict[str, Any], as_of: date, resource_root: Path
) -> None:
    config = load_regulatory_config(_resolve(profile["regulatory_config"], resource_root))
    parameter_template = tables["regulatory_parameter"].iloc[0]
    rows: list[dict[str, Any]] = []
    for sequence, item in enumerate(regulatory_parameter_items(config), 1):
        key, d1, d2 = str(item["key"]), str(item.get("d1", "")), str(item.get("d2", ""))
        row = _common_metadata(parameter_template, f"PARAM-{sequence:04d}-{key}-{d1}-{d2}", as_of, sequence)
        row.update(
            parameter_key=key,
            dimension_1=d1,
            dimension_2=d2,
            parameter_value=item["value"],
            unit=item["unit"],
            rule_set_id=config["metadata"]["rule_set_id"],
            legal_reference=item["ref"],
        )
        rows.append(row)
    tables["regulatory_parameter"] = pd.DataFrame(
        rows, columns=TABLE_SPECS["regulatory_parameter"].all_columns
    )

    formula_template = tables["formula_definition"].iloc[0]
    formulas: list[dict[str, Any]] = []
    for formula_id, component in config["formula_registry"].items():
        row = _common_metadata(formula_template, f"FORMULA-{formula_id}", as_of, len(formulas) + 1)
        row.update(
            formula_id=formula_id,
            formula_version=config["metadata"]["version"],
            component=component,
            expression_language="PYTHON_FLOAT",
            legal_reference="SCHRITT_1_FORMELKATALOG",
            description=f"Implementierte Formel {formula_id}",
        )
        formulas.append(row)
    tables["formula_definition"] = pd.DataFrame(
        formulas, columns=TABLE_SPECS["formula_definition"].all_columns
    )


def _update_run_control(tables: dict[str, pd.DataFrame], *, as_of: date, seed: int, profile_id: str) -> None:
    updates = {
        "as_of_date": as_of.isoformat(),
        "knowledge_time": f"{as_of.isoformat()}T23:59:59",
        "random_seed": str(seed),
        "institution_profile": profile_id,
    }
    frame = tables["run_config"]
    for key, value in updates.items():
        mask = frame["config_key"].astype(str) == key
        if mask.sum() != 1:
            raise ConfigurationError(f"run_config-Schlüssel fehlt oder ist mehrdeutig: {key}")
        frame.loc[mask, "config_value"] = value
    if "random_seed" in tables["model_registry"].columns:
        tables["model_registry"]["random_seed"] = seed


def _apply_transformations(tables: dict[str, pd.DataFrame], profile: dict[str, Any]) -> None:
    """Wende ausschließlich im Profil deklarierte, generische Transformationen an."""
    transformations = profile.get("transformations", {})
    for table_name in transformations.get("empty_tables", []):
        if table_name not in tables:
            raise ConfigurationError(f"Transformation referenziert unbekannte Tabelle: {table_name}")
        tables[table_name] = tables[table_name].iloc[0:0].copy()
    for table_name, assignments in transformations.get("set_columns", {}).items():
        if table_name not in tables:
            raise ConfigurationError(f"Transformation referenziert unbekannte Tabelle: {table_name}")
        for column, value in assignments.items():
            if column not in tables[table_name].columns:
                raise ConfigurationError(
                    f"Transformation referenziert unbekannte Spalte: {table_name}.{column}"
                )
            tables[table_name][column] = value


def generate_synthetic_tables(
    *,
    as_of: date | None = None,
    seed: int | None = None,
    bank_profile: str = "MID_SIZE_UNIVERSAL",
    config_root: Path | None = None,
) -> dict[str, pd.DataFrame]:
    """Lade und materialisiere ein externes, unveränderliches Referenzprofil."""
    profile = load_profile(bank_profile, config_root=config_root)
    resource_root = _profile_resource_root(config_root)
    source, manifest_path = _verify_profile(profile, resource_root)
    target_as_of = as_of or date.fromisoformat(str(profile["base_as_of_date"]))
    effective_seed = int(profile["default_seed"] if seed is None else seed)
    base = _load_reference_cached(str(source), _file_hash(manifest_path))
    tables = {name: frame.copy(deep=True) for name, frame in base.items()}
    _shift_temporal_columns(tables, profile, target_as_of)
    _materialize_rules(tables, profile, target_as_of, resource_root)
    _update_run_control(tables, as_of=target_as_of, seed=effective_seed, profile_id=bank_profile)
    _apply_transformations(tables, profile)
    errors = [issue for issue in validate_tables(tables) if issue.severity == "ERROR"]
    if errors:
        raise ConfigurationError(f"Referenzprofil verletzt Datenvertrag: {errors[:10]}")
    return tables


def generate_synthetic_dataset(
    root: Path,
    *,
    as_of: date | None = None,
    version: str | None = None,
    seed: int | None = None,
    bank_profile: str = "MID_SIZE_UNIVERSAL",
    config_root: Path | None = None,
    overwrite: bool = False,
) -> Path:
    profile = load_profile(bank_profile, config_root=config_root)
    target_as_of = as_of or date.fromisoformat(str(profile["base_as_of_date"]))
    dataset_version = version or str(profile["default_dataset_version"])
    effective_seed = int(profile["default_seed"] if seed is None else seed)
    dataset = root / target_as_of.isoformat() / dataset_version
    input_dir = dataset / "inputs"
    if dataset.exists() and any(dataset.iterdir()) and not overwrite:
        raise ConfigurationError(f"Datensatz existiert bereits: {dataset}; explizit overwrite=True verwenden")
    input_dir.mkdir(parents=True, exist_ok=True)
    tables = generate_synthetic_tables(
        as_of=target_as_of, seed=effective_seed, bank_profile=bank_profile, config_root=config_root
    )
    files = write_input_workbooks(input_dir, tables)
    manifest = {
        "dataset_version": dataset_version,
        "as_of_date": target_as_of.isoformat(),
        "bank_profile": bank_profile,
        "profile_version": profile["profile_version"],
        "random_seed": effective_seed,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_workbooks": [path.name for path in files],
        "input_sha256": {path.name: _file_hash(path) for path in files},
        "table_row_counts": {name: int(len(frame)) for name, frame in tables.items()},
    }
    (dataset / "dataset_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return dataset
