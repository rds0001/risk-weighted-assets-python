# Risk-Weighted Assets

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10–3.14-blue.svg)](pyproject.toml)
[![CI](https://github.com/rds0001/risk-weighted-assets-python/actions/workflows/ci.yml/badge.svg)](https://github.com/rds0001/risk-weighted-assets-python/actions/workflows/ci.yml)

`risk-weighted-assets` is an institution-neutral, auditable Python reference engine for
CRR III risk-weighted assets, regulatory capital, IRRBB and ICAAP. It combines a stable
Python API, a command-line interface, a local browser application, canonical Excel
contracts, realistic synthetic portfolios and reproducible reference calculations.

The distribution is intended for research, education, prototyping and independent model
validation. It is not regulatory, legal, accounting or investment advice and is not a
certified regulatory reporting system. Read the [disclaimer](DISCLAIMER.md) before use.

## Functional scope

- CRR III credit risk under SA and IRB, credit-risk mitigation and output-floor views
- counterparty credit risk, SFT, CCP, securitisation, CVA and crypto exposures
- settlement, large exposures, market risk with parallel FRTB views, and operational risk
- own funds, buffers, leverage, MREL/TLAC and capital headroom
- IRRBB/CSRBB and ICAAP economic and normative perspectives
- deterministic fingerprints, lineage, reconciliations and calculation controls
- 34 public atomic regulatory formulae with explicit, analyst-controlled parameters
- nine focused risk-domain analyses plus granular metric, table and control access
- non-mutating parameter sensitivities with mandatory rationale, approver and audit trail
- 16 canonical input and six output workbooks per persisted calculation

## Installation

Python 3.10 or newer is required. Install a locally built wheel with:

```bash
python -m pip install dist/risk_weighted_assets-1.1.0-py3-none-any.whl
```

Install the latest published release from PyPI with:

```bash
python -m pip install risk-weighted-assets
```

For development from this source tree:

```bash
python -m pip install -e '.[test,build]'
```

## First calculation

Create an isolated, writable workspace from the immutable package resources and run the
supplied universal-bank dataset:

```bash
rwa init ./rwa-workspace
rwa run --dataset ./rwa-workspace/daten/rechenlaeufe/2026-08-31/v1.0.0
```

Or generate a deterministic synthetic dataset and calculate it in one step:

```bash
rwa all \
  --data-root ./rwa-workspace/daten/rechenlaeufe \
  --as-of-date 2026-08-31 \
  --version v1.0.1 \
  --seed 5752026 \
  --bank-profile MID_SIZE_UNIVERSAL
```

Set `RWA_WORKSPACE=/absolute/path` to change the default workspace used by the CLI and web
application. Package resources are never modified in place.

## Python API

```python
from pathlib import Path

from rwa_engine import calculate_dataset, create_workspace, validate_dataset

workspace = create_workspace(Path("rwa-workspace"))
dataset = workspace.runs_root / "2026-08-31" / "v1.0.0"

validation = validate_dataset(dataset)
if validation.valid:
    result = calculate_dataset(dataset)
    print(result.status, result.run_id, result.metrics)
```

For integration without Excel I/O, use `calculate_tables(tables)` with the canonical
`dict[str, pandas.DataFrame]` contract. It returns the same structured `CalculationResult`
without persisting output workbooks.

For formula-by-formula control and focused analysis:

```python
from rwa_engine import (
    analyze_credit_risk,
    compare_calculation_views,
    irb_capital_requirement,
    regulatory_parameter,
)

print(regulatory_parameter("RWA_MULTIPLIER", "PILLAR1"))
print(irb_capital_requirement(0.01, 0.45, 0.20, 2.5))
credit = analyze_credit_risk(result)
print(credit.metrics, credit.tables, credit.controls)
print(compare_calculation_views(result))
```

## CLI and local app

```bash
rwa --help
rwa doctor
rwa data list
rwa sources
rwa-web --data-root ./rwa-workspace/daten/rechenlaeufe
```

The web server binds to `127.0.0.1:8080` by default and invokes the same calculation
pipeline as the API and CLI. It has no authentication or TLS and is intended for a trusted
local workstation only.

## Bundled data and source boundary

The wheel includes both complete synthetic profiles (`MID_SIZE_UNIVERSAL` and `KSA_BANK`),
their two calculation-ready datasets, retained reference outputs, configuration and the
machine-readable inventory of official sources. Use `rwa data export PATH` or
`create_workspace(PATH)` to obtain editable copies.

No downloaded regulation, standard, PDF or other third-party publication is redistributed.
Official links and archival checksums are available through `rwa sources` and the
[regulatory source catalogue](docs/REGULATORY_SOURCES.md). The original construction
scaffold is not part of this distribution.

## Documentation and verification

- [documentation map](docs/README.md)
- [public API](docs/PYTHON_API.md)
- [granular bank-analyst API and all 34 formulae](docs/GRANULAR_ANALYST_API.md)
- [installation and troubleshooting](docs/INSTALLATION_AND_TROUBLESHOOTING.md)
- [architecture](docs/ARCHITECTURE.md)
- [methodology](docs/PILLAR_1_METHODOLOGY.md)
- [governance, controls and acceptance](docs/GOVERNANCE_CONTROLS_AND_ACCEPTANCE.md)
- [package provenance](UPSTREAM.md)

Run the complete local verification suite with:

```bash
python -m pytest
python -m ruff check src tests tools
python -m build
python -m twine check dist/*
python tools/validate_distribution.py dist
```

## Legal and privacy

This project is published by RiskDataScience GmbH. The legally binding company
information is available in the [imprint](https://riskdatascience.net/impressum/), and
information about the processing of personal data is provided in the
[privacy policy](https://riskdatascience.net/datenschutzerklaerung/).

The installed library contains no telemetry, analytics or tracking and does not transmit
portfolio, calculation or usage data to RiskDataScience GmbH. The optional browser
application communicates only with the locally started RWA server. Interactions performed
on GitHub or PyPI are additionally subject to the terms and privacy practices of those
platforms.

## License

Copyright © 2026 RiskDataScience GmbH. Original content is licensed under the
[GNU General Public License, version 3 only](LICENSE). External publications remain subject
to their respective rights and are not included. See [third-party notices](THIRD_PARTY_NOTICES.md).
