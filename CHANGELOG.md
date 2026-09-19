# Changelog

All notable public changes are documented here. Dates use ISO 8601.

## 1.2.0 — 2026-09-19

- Added explicit, auditable IRB SME/infrastructure support and combined application.
- Added four public formula helpers (38 total), optional compatible input fields,
  before/after RWA and SA-comparison diagnostics; K and EL remain unchanged.
- Retained historical SA arithmetic with an explicit unverified-legacy warning.
- Added targeted formula, eligibility, floor, Excel and cross-language regressions.

## 1.1.0 — 2026-09-14

- Added 34 individually callable, parameter-controlled regulatory formula functions,
  matching the granular formula surface of the R library.
- Added nine focused bank-analyst domain views for credit, counterparty, securitisation,
  market, operational, output-floor, capital, IRRBB and ICAAP analysis.
- Added fail-closed parameter, rule-set, formula-catalogue, bitemporal snapshot and all
  68 canonical table-schema accessors.
- Added non-mutating regulatory parameter overrides with mandatory rationale, approver
  and old/new-value audit trail.
- Extended calculation results with fully-loaded metrics and controls, granular result
  accessors and applied/fully-loaded comparisons.
- Added complete analyst API documentation, executable coverage of all public formulae
  and installed-distribution release gates.

## 1.0.0 — 2026-09-13

- Converted the approved upstream reference implementation into the installable
  `risk-weighted-assets` distribution with a modern `src` layout.
- Added stable dataset and in-memory APIs, structured results and exception hierarchy.
- Added installed `rwa` and `rwa-web` entry points and repository-independent paths.
- Bundled both complete synthetic profiles, calculation-ready datasets, reference outputs,
  configuration and source metadata as immutable package resources.
- Added writable workspaces, resource export and installed-artifact verification.
- Added package, archive and clean-environment smoke tests and library documentation.
- Added directly accessible corporate imprint and privacy information to the package
  metadata, project documentation and local browser application.

## Upstream 1.0.0 — 2026-09-10

- Initial public release candidate of the RWA reference engine and local web application.
- Added canonical Excel contracts and two realistic synthetic reference datasets.
- Included reproducible reference calculations with six output workbooks per dataset.
- Added CRR III, capital, IRRBB and ICAAP methodology and operating documentation.
- Added metadata-only regulatory source provenance; third-party publications are not bundled.
- Licensed original repository content under GPL-3.0-only.
