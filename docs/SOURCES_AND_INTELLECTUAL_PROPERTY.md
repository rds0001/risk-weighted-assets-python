# Sources, provenance and intellectual property

Copyright (C) 2026 RiskDataScience GmbH. Licensed under GPL-3.0-only.

## Distribution boundary

The Python distribution contains original source code, documentation, configuration and
synthetic Excel data. It does not contain downloaded regulatory PDFs, standards, guidelines
or office-document manuals. Referenced publications remain external works under the rights
and terms of their publishers.

The source model has two layers:

1. The packaged `Standards/00_manifest/sources.json` resource contains the exact URL and archival SHA-256 for the
   two documents linked from the canonical `Legal_Sources` input table. The calculation
   pipeline accepts this matching external-provenance record when the archival PDF is absent.
2. `docs/REGULATORY_SOURCES.md` provides the broader research catalogue and official links
   used to establish the methodological perimeter.

The package validator enforces that `Standards/` remains metadata-only. It does not download
anything and therefore works offline.

## Reproducing the evidence boundary

Obtain a required document directly from the recorded official URL. Compare its SHA-256
with `archival_sha256` if reconstructing the historical development evidence. A mismatch
does not by itself prove a defective source: official publishers may replace or reissue a
file. In that case, preserve both versions where legally permitted, record retrieval times,
assess the change, and version the source and affected parameters.

The reporting-date legal status must always be reviewed independently. A checksum proves
byte identity only; it does not prove legal applicability, completeness or authenticity.

## Synthetic data

All published Excel portfolios are artificial and designed to exercise calculation paths.
They carry no rights or confidentiality claims of a bank, customer or counterparty. Names,
identifiers, values and combinations must not be interpreted as real-world observations.

## Software dependencies

Direct package dependencies and their upstream licenses are listed in
`THIRD_PARTY_NOTICES.md`. They are resolved by the user's package installer and are not
vendored in this distribution.
