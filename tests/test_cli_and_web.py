import json
from pathlib import Path

from rwa_engine.cli import main
from rwa_engine.web.catalog import CatalogError, DataCatalog
from rwa_engine.workspace import create_workspace


def test_cli_lists_data_as_machine_readable_json(capsys):
    assert main(["data", "list"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert {profile["profile_id"] for profile in payload["profiles"]} == {
        "KSA_BANK",
        "MID_SIZE_UNIVERSAL",
    }
    assert len(payload["datasets"]) == 2


def test_cli_init_and_doctor(tmp_path: Path, capsys):
    target = tmp_path / "workspace"
    assert main(["init", str(target)]) == 0
    capsys.readouterr()
    assert main(["doctor"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok"
    assert payload["resources"]["datasets"] == 2


def test_catalog_reads_exported_resources_and_rejects_traversal(tmp_path: Path):
    workspace = create_workspace(tmp_path / "workspace")
    catalog = DataCatalog(workspace.runs_root)
    rows = catalog.datasets()
    assert {row["id"] for row in rows} == {
        "2026-08-31/v1.0.0",
        "2026-08-31/v1.0.0-ksa",
    }
    detail = catalog.detail("2026-08-31/v1.0.0")
    assert len(detail["inputs"]) == 16
    assert detail["manifest"]["missing_inputs"] == []
    try:
        catalog.dataset_path("../../outside")
    except CatalogError:
        pass
    else:
        raise AssertionError("path traversal was accepted")
