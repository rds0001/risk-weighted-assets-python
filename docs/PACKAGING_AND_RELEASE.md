# Packaging und Release

## Distributionsgrenze

Das Paket enthält Engine, API, CLI, Web-App, synthetische Daten, Referenzoutputs,
Konfiguration, Quellenmetadaten und Dokumentation. Scaffold, heruntergeladene Dokumente,
Caches, virtuelle Umgebungen und Nutzer-Workspaces sind ausgeschlossen.

## Lokaler Releasekandidat

```bash
python -m pytest
python -m ruff check src tests tools
python -m build
python -m twine check dist/*
python tools/validate_distribution.py dist
```

Der Build erzeugt ein Wheel und ein Source-Archiv. `SHA256SUMS` dokumentiert deren Hashes.
Beide Artefakte müssen in neuen virtuellen Umgebungen installiert und mit dem enthaltenen
Smoke-Test geprüft werden.

## Version und Freigabe

Die Distributionsversion steht in `pyproject.toml`; `rwa_engine.__version__` wird im
installierten Zustand aus den Metadaten gelesen. Breaking API-Änderungen erfordern eine neue
Major-Version. Ein publiziertes Artefakt wird nie überschrieben.

## Automatisierte Veröffentlichung

`.github/workflows/publish.yml` wird ausschließlich durch ein publiziertes GitHub Release
ausgelöst. Der Workflow prüft, dass ein Tag `vX.Y.Z` exakt zur Version in `pyproject.toml`
passt, wiederholt Quellen-, Lint- und Testprüfungen, baut Wheel und Source-Archiv und
validiert beide Distributionen. Build und Publishing laufen in getrennten Jobs.

Der Publish-Job verwendet PyPI Trusted Publishing (OIDC), das GitHub-Environment `pypi`
und keine langlebigen API-Token. Nach erfolgreicher PyPI-Veröffentlichung werden Wheel,
Source-Archiv und `SHA256SUMS` an das GitHub Release angehängt.

Vor dem ersten Release muss auf PyPI einmalig ein Pending Trusted Publisher mit folgenden
Werten eingerichtet werden:

- PyPI project name: `risk-weighted-assets`
- GitHub owner: `rds0001`
- GitHub repository: `risk-weighted-assets-python`
- Workflow filename: `publish.yml`
- Environment name: `pypi`

Für diese Erweiterung darf erst danach das Release `v1.1.0` publiziert werden. Ein publiziertes Artefakt wird
niemals überschrieben; jede weitere Veröffentlichung benötigt eine neue Paketversion und
einen dazu passenden Tag.
