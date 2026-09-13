#!/usr/bin/env python3
"""Smoke test intended to run only against an installed distribution."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from rwa_engine import __version__, calculate_tables, create_workspace, validate_dataset
from rwa_engine.resources import verify_packaged_resources
from rwa_engine.synthetic import generate_synthetic_tables


def main() -> int:
    assert __version__ == "1.0.0"
    assert verify_packaged_resources()["datasets"] == 2
    scripts = Path(sys.executable).parent
    subprocess.run([scripts / "rwa", "--version"], check=True)
    subprocess.run([scripts / "rwa-web", "--help"], check=True, stdout=subprocess.DEVNULL)
    with tempfile.TemporaryDirectory(prefix="rwa-wheel-smoke-") as temporary:
        workspace = create_workspace(Path(temporary) / "workspace")
        dataset = workspace.runs_root / "2026-08-31" / "v1.0.0-ksa"
        assert validate_dataset(dataset).valid
    result = calculate_tables(generate_synthetic_tables(bank_profile="KSA_BANK", seed=77), run_id="SMOKE")
    assert result.successful and result.metrics["TREA"] > 0
    print(json.dumps({"status": "ok", "version": __version__, "controls": result.control_count}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
