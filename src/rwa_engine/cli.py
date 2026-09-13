"""Command-line interface for the installable RWA library.

Copyright (C) 2026 RiskDataScience GmbH.
SPDX-License-Identifier: GPL-3.0-only
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from . import __version__
from .api import calculate_dataset, validate_dataset
from .contracts import TABLE_SPECS
from .excel_io import write_input_workbooks
from .exceptions import RwaError
from .resources import verify_packaged_resources
from .synthetic import generate_synthetic_dataset
from .workspace import (
    create_workspace,
    default_workspace,
    list_reference_datasets,
    list_reference_profiles,
    regulatory_sources,
)


def _date(value: str) -> date:
    return date.fromisoformat(value)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(prog="rwa", description="CRR III, RWA, capital, IRRBB and ICAAP library")
    value.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = value.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="export a complete writable reference workspace")
    init.add_argument("path", type=Path, nargs="?", default=default_workspace().root)
    init.add_argument("--force", action="store_true", help="replace conflicting resource files")
    template = commands.add_parser("templates", help="create empty canonical Excel templates")
    template.add_argument("--output", type=Path, default=Path("templates/v1.0.0"))
    generate = commands.add_parser("generate", help="generate a synthetic bank dataset")
    _generation_arguments(generate)
    run = commands.add_parser("run", help="validate and calculate an existing dataset")
    run.add_argument("--dataset", type=Path, required=True)
    run.add_argument("--json", action="store_true", dest="as_json")
    validate = commands.add_parser("validate", help="validate an existing dataset without writing outputs")
    validate.add_argument("--dataset", type=Path, required=True)
    validate.add_argument("--json", action="store_true", dest="as_json")
    all_command = commands.add_parser("all", help="generate and calculate in one operation")
    _generation_arguments(all_command)
    data = commands.add_parser("data", help="inspect or export packaged reference data")
    data_commands = data.add_subparsers(dest="data_command", required=True)
    data_commands.add_parser("list", help="list packaged profiles and datasets")
    export = data_commands.add_parser("export", help="export all packaged resources to a workspace")
    export.add_argument("path", type=Path)
    export.add_argument("--force", action="store_true")
    commands.add_parser("sources", help="show machine-linked official source metadata")
    commands.add_parser("doctor", help="verify installation, dependencies and packaged resources")
    web = commands.add_parser("web", help="start the local browser application")
    web.add_argument("--data-root", type=Path, default=default_workspace().runs_root)
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8080)
    return value


def _generation_arguments(command: argparse.ArgumentParser) -> None:
    command.add_argument("--data-root", type=Path, default=default_workspace().runs_root)
    command.add_argument("--as-of-date", type=_date)
    command.add_argument("--version")
    command.add_argument("--seed", type=int)
    command.add_argument("--bank-profile", default="MID_SIZE_UNIVERSAL")
    command.add_argument("--config-root", type=Path)
    command.add_argument("--force", action="store_true", help="replace an existing dataset version")


def _generate(args: argparse.Namespace) -> Path:
    return generate_synthetic_dataset(
        args.data_root,
        as_of=args.as_of_date,
        version=args.version,
        seed=args.seed,
        bank_profile=args.bank_profile,
        config_root=args.config_root,
        overwrite=args.force,
    )


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "init":
            print(create_workspace(args.path, overwrite=args.force).root)
        elif args.command == "templates":
            tables = {name: pd.DataFrame(columns=spec.all_columns) for name, spec in TABLE_SPECS.items()}
            print(f"{len(write_input_workbooks(args.output, tables))} templates: {args.output.resolve()}")
        elif args.command == "generate":
            print(_generate(args))
        elif args.command == "run":
            result = calculate_dataset(args.dataset)
            if args.as_json:
                print(
                    json.dumps(
                        {
                            "status": result.status,
                            "run_id": result.run_id,
                            "output_dir": str(result.output_dir),
                            "metrics": result.metrics,
                            "controls_passed": result.controls_passed,
                            "control_count": result.control_count,
                        },
                        ensure_ascii=False,
                    )
                )
            else:
                print(result.output_dir)
        elif args.command == "validate":
            report = validate_dataset(args.dataset)
            payload = {
                "valid": report.valid,
                "errors": len(report.errors),
                "warnings": len(report.warnings),
                "messages": [item.__dict__ for item in report.messages],
            }
            print(json.dumps(payload, indent=2 if args.as_json else None, ensure_ascii=False))
            return 0 if report.valid else 2
        elif args.command == "all":
            print(calculate_dataset(_generate(args)).output_dir)
        elif args.command == "data":
            if args.data_command == "list":
                print(
                    json.dumps(
                        {"profiles": list_reference_profiles(), "datasets": list_reference_datasets()},
                        indent=2,
                        ensure_ascii=False,
                    )
                )
            else:
                print(create_workspace(args.path, overwrite=args.force).root)
        elif args.command == "sources":
            print(json.dumps(regulatory_sources(), indent=2, ensure_ascii=False))
        elif args.command == "doctor":
            resources = verify_packaged_resources()
            print(
                json.dumps(
                    {
                        "status": "ok",
                        "engine_version": __version__,
                        "python": platform.python_version(),
                        "numpy": np.__version__,
                        "pandas": pd.__version__,
                        "resources": resources,
                    },
                    indent=2,
                )
            )
        elif args.command == "web":
            from .web.server import main as web_main

            return int(
                web_main(["--data-root", str(args.data_root), "--host", args.host, "--port", str(args.port)])
                or 0
            )
        return 0
    except RwaError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
