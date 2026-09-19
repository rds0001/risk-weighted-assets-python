#!/usr/bin/env python3
"""Smoke test intended to run only against an installed distribution."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from rwa_engine import (
    __version__,
    analyze_credit_risk,
    calculate_tables,
    create_workspace,
    frtb_quadratic_charge,
    irb_risk_weighted_assets,
    regulatory_parameter,
    sme_supporting_factor,
    validate_dataset,
)
from rwa_engine.resources import verify_packaged_resources
from rwa_engine.synthetic import generate_synthetic_tables


def main() -> int:
    assert __version__ == "1.2.0"
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
    assert analyze_credit_risk(result).tables
    assert regulatory_parameter("RWA_MULTIPLIER", "PILLAR1") == 12.5
    assert frtb_quadratic_charge([3, 4], 0) == 5
    assert abs(sme_supporting_factor(5e6) - .80595) < 1e-12
    assert irb_risk_weighted_assets(1e6, .08, infrastructure_factor=.75) == 750000
    print(json.dumps({"status": "ok", "version": __version__, "controls": result.control_count}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
