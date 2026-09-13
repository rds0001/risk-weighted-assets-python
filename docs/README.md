# Documentation map

Copyright © 2026 RiskDataScience GmbH. Licensed under GPL-3.0-only.

The documentation separates public library operation, regulatory methodology, data
contracts and governance evidence so that each can be reviewed independently.

## Library use

- [Installation and troubleshooting](INSTALLATION_AND_TROUBLESHOOTING.md): wheel/source
  installation, workspace setup, dependency diagnosis, backup and recovery.
- [Python API](PYTHON_API.md): stable entry points, result objects, exceptions and examples.
- [CLI and web application](CLI_AND_WEBAPP.md): command reference, local UI and security.
- [Resources and workspaces](RESOURCES_AND_WORKSPACES.md): immutable package data,
  writable exports, environment variables and reproducibility.
- [Architecture](ARCHITECTURE.md): package layers, dependencies and calculation modules.

## Regulatory and quantitative methodology

- [Management and scope](MANAGEMENT_AND_SCOPE.md): objectives, supported views,
  boundaries and end-to-end processing.
- [Pillar 1 methodology](PILLAR_1_METHODOLOGY.md): SA/IRB credit risk, CRM, CCR/SFT/CCP,
  securitisation, CVA, settlement, market and operational risk, own funds and output floor.
- [Pillar 2, IRRBB and ICAAP](PILLAR_2_IRRBB_ICAAP.md): EVE/NII, CSRBB, economic-capital
  aggregation, normative projections and RWA equivalents.
- [Regulatory source catalogue](REGULATORY_SOURCES.md): reporting-date qualifications and
  official links; referenced publications are external and are not redistributed.
- [Sources and intellectual property](SOURCES_AND_INTELLECTUAL_PROPERTY.md): provenance,
  checksums, synthetic-data boundary and third-party rights.

## Data, controls and verification

- [Data model and history](DATA_MODEL_AND_HISTORY.md): canonical entities, temporal axes,
  keys, lineage and versioning.
- [Excel data household](EXCEL_DATA_HOUSEHOLD.md): all 16 input and six output workbooks.
- [Reference profiles and testing](REFERENCE_PROFILES_AND_TESTING.md): supplied synthetic
  cases and expected evidence.
- [Governance, controls and acceptance](GOVERNANCE_CONTROLS_AND_ACCEPTANCE.md): change
  governance, test pyramid, release gates and institution-specific sign-offs.
- [Packaging and release](PACKAGING_AND_RELEASE.md): deterministic build, archive boundary
  and pre-publication checks.
- [Glossary and appendix](GLOSSARY_AND_APPENDIX.md): terms, metrics and reproducibility.

The detailed German methodology is the fachlich/technical reference for version 1.0.0.
Root-level English documents define the public package, licensing and contribution boundary.
