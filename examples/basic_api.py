"""Minimal persisted calculation using the public API."""

from pathlib import Path

from rwa_engine import calculate_dataset, create_workspace

workspace = create_workspace(Path("rwa-workspace"))
dataset = workspace.runs_root / "2026-08-31" / "v1.0.0"
result = calculate_dataset(dataset)
print(result.run_id, result.metrics["TREA"], result.output_dir)
