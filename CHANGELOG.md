# Changelog

All notable public changes are documented here. Dates use ISO 8601.

## 1.0.0 — 2026-09-13

- Converted the approved upstream reference implementation into the installable
  `risk-weighted-assets` distribution with a modern `src` layout.
- Added stable dataset and in-memory APIs, structured results and exception hierarchy.
- Added installed `rwa` and `rwa-web` entry points and repository-independent paths.
- Bundled both complete synthetic profiles, calculation-ready datasets, reference outputs,
  configuration and source metadata as immutable package resources.
- Added writable workspaces, resource export and installed-artifact verification.
- Added package, archive and clean-environment smoke tests and library documentation.

## Upstream 1.0.0 — 2026-09-10

- Initial public release candidate of the RWA reference engine and local web application.
- Added canonical Excel contracts and two realistic synthetic reference datasets.
- Included reproducible reference calculations with six output workbooks per dataset.
- Added CRR III, capital, IRRBB and ICAAP methodology and operating documentation.
- Added metadata-only regulatory source provenance; third-party publications are not bundled.
- Licensed original repository content under GPL-3.0-only.
