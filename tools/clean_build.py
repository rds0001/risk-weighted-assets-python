#!/usr/bin/env python3
"""Remove only local packaging artefacts from this source tree."""

import shutil
from pathlib import Path

root = Path(__file__).resolve().parents[1]
for relative in ("build", "dist", "src/risk_weighted_assets.egg-info"):
    target = (root / relative).resolve()
    target.relative_to(root)
    if target.is_dir():
        shutil.rmtree(target)
