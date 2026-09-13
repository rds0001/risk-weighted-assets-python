# Security Policy

Copyright (C) 2026 RiskDataScience GmbH. Licensed under GPL-3.0-only.

## Supported version

Security fixes are currently targeted at the latest published release.

## Reporting a vulnerability

Please do not disclose a suspected vulnerability in a public issue. Report it privately to
`riskdatascience@web.de` with the affected version, reproduction steps, impact and any
suggested mitigation. Receipt should be acknowledged within seven calendar days when
possible. Coordinated disclosure will be arranged after triage and remediation.

Do not include real bank, customer or counterparty data in a report. The bundled local web
server is designed for loopback use. Exposing it to a network requires an independently
reviewed deployment layer providing TLS, authentication, authorization, request limits,
logging and operational monitoring.
