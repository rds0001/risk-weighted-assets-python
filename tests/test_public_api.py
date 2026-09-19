from pathlib import Path

import pytest

import rwa_engine
from rwa_engine import ConfigurationError, calculate_tables, create_workspace, validate_dataset
from rwa_engine.resources import resource_files, verify_packaged_resources
from rwa_engine.synthetic import generate_synthetic_dataset, generate_synthetic_tables


def test_public_api_is_explicit_and_versioned():
    assert rwa_engine.__version__ == "1.2.0"
    assert {"calculate_dataset", "calculate_tables", "validate_dataset", "create_workspace"}.issubset(
        rwa_engine.__all__
    )


def test_all_expected_reference_resources_are_bundled():
    names = resource_files()
    inventory = verify_packaged_resources()
    assert inventory["profile_workbooks"] == 16
    assert inventory["datasets"] == 2
    assert sum(name.endswith(".xlsx") and "/inputs/" in name for name in names) == 48
    assert sum(name.endswith(".xlsx") and "/outputs/" in name for name in names) == 12
    assert not any("scaffold" in name.lower() or name.lower().endswith(".pdf") for name in names)


def test_workspace_export_and_packaged_dataset_validation(tmp_path: Path):
    workspace = create_workspace(tmp_path / "workspace")
    dataset = workspace.runs_root / "2026-08-31" / "v1.0.0"
    assert (workspace.root / "workspace_manifest.json").is_file()
    assert len(list((dataset / "inputs").glob("RWA_IN_*.xlsx"))) == 16
    assert validate_dataset(dataset).valid


def test_in_memory_api_returns_structured_successful_result():
    tables = generate_synthetic_tables(bank_profile="KSA_BANK", seed=919)
    result = calculate_tables(tables, run_id="API-TEST")
    assert result.run_id == "API-TEST"
    assert result.status == "CALCULATED"
    assert result.metrics["TREA"] > 0
    assert result.controls_passed == result.control_count
    assert result.successful
    assert "TREA_Summary" in result.results
    assert "TREA_Summary" in result.parallel_results


def test_dataset_generation_requires_explicit_overwrite(tmp_path: Path):
    generate_synthetic_dataset(tmp_path, bank_profile="KSA_BANK")
    with pytest.raises(ConfigurationError, match="existiert bereits"):
        generate_synthetic_dataset(tmp_path, bank_profile="KSA_BANK")
    assert generate_synthetic_dataset(tmp_path, bank_profile="KSA_BANK", overwrite=True).is_dir()
