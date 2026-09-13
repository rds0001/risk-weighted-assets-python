# Reference profiles, reproducibility and testing

Copyright (C) 2026 RiskDataScience GmbH. Licensed under GPL-3.0-only.

## Purpose of the supplied data

All workbooks in `daten/` contain synthetic data. They are designed to make calculation
paths, validation behavior, lineage and outputs reviewable without access to confidential
bank data. The values are plausible test fixtures, not a calibrated model of a particular
institution and not regulatory benchmarks.

The reference date is 31 August 2026 and the random seed is recorded in each dataset
manifest. Regulatory and bank-profile values remain externalized in versioned YAML and
Excel tables.

## Supplied profiles

| Dataset | Profile | Intended coverage |
|---|---|---|
| `v1.0.0` | `MID_SIZE_UNIVERSAL` | broad end-to-end case across SA, IRB, CCR, SFT, CCP, securitisation, CVA, market risk, capital, IRRBB and ICAAP |
| `v1.0.0-ksa` | `KSA_BANK` | simpler SA-focused case; non-applicable complex modules are intentionally empty and produce controlled warnings |

Each dataset contains exactly 16 input workbooks, `dataset_manifest.json`, and one retained
calculated reference run. Each retained run contains six output workbooks and a
`run_manifest.json`. Both manifests report 12 of 12 successful calculation controls and no
fatal input-validation error.

The KSA profile derives from the sealed universal synthetic source profile by deterministic
profile transformations. Its intentionally empty modules test that absence of non-applicable
positions is handled explicitly instead of silently inventing exposure.

## Integrity model

`dataset_manifest.json` records dataset identity, reporting date, profile, generator seed,
input filenames, SHA-256 checksums and table row counts. The calculation run adds:

- an input fingerprint over the 16 workbooks;
- a code fingerprint over the engine modules;
- engine and library versions;
- applied and fully loaded rule-set identifiers;
- output inventory, control counts and headline metrics.

The run identifier is derived from the calculation fingerprint. Repeating the same input,
code and engine version is idempotent and returns the existing calculated run. A code or
input change creates a distinct run directory.

The retained reference outputs were created with the published engine code. Repeating the
calculation without modifying engine or inputs resolves idempotently to the same run;
changes preserve lineage by creating a new run rather than overwriting historical evidence.

## Verification layers

The automated suite covers contracts, synthetic-data integrity, formulas, end-to-end
calculation, quality gates and the local web application. Property-based tests supplement
fixed examples for numerical invariants.

Run the complete verification from the package source root:

```bash
python3 -m pip install -e '.[test,build]'
python3 -m pytest
python3 tools/verify_source_tree.py
python3 -m build
python3 -m twine check dist/*
python3 tools/validate_distribution.py dist
```

The release validator additionally enforces the public boundary, required metadata,
synthetic dataset hashes, workbook counts, retained run status and the absence of bundled
regulatory or office documents. CI repeats these checks on pushes and pull requests.

## Interpretation of successful tests

A green technical suite demonstrates consistency with the implemented contracts and test
expectations. It does not establish legal correctness for every exposure type, authorize an
internal-model approach, validate institution-specific data or replace independent model
validation. Production acceptance must follow the gates in
`GOVERNANCE_CONTROLS_AND_ACCEPTANCE.md`.
