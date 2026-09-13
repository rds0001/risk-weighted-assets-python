# Contributing

Copyright (C) 2026 RiskDataScience GmbH. Licensed under GPL-3.0-only.

Contributions that improve correctness, transparency, test coverage or documentation are
welcome. Open an issue before substantial changes so that scope, regulatory assumptions
and data-contract implications can be discussed.

## Development setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -e '.[dev]'
python3 -m pytest
python3 -m ruff check src tests tools
python3 -m build
python3 -m twine check dist/*
python3 tools/validate_distribution.py dist
```

Changes to formulas, parameters or data contracts should include:

- the applicable reporting date and official source link;
- a concise explanation of the interpretation and any alternatives considered;
- focused unit tests and, where relevant, an end-to-end calculation test;
- updates to methodology, data-model and release documentation;
- regenerated synthetic reference data only when the contract or expected result changes.

Never commit confidential or personal data, credentials, downloaded regulatory PDFs,
third-party office documents, or material for which redistribution rights are unclear.

## Sign-off and licensing

All commits must carry a Developer Certificate of Origin sign-off:

```bash
git commit -s -m "Describe the change"
```

By contributing, you certify the statement at <https://developercertificate.org/> and agree
that your contribution is licensed under GPL-3.0-only. Preserve copyright and attribution
notices. Do not copy code or data under an incompatible license.
