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

Die Einrichtung eines separaten GitHub-Repositories, Trusted Publishing sowie TestPyPI-
und PyPI-Uploads gehören bewusst zu den nachgelagerten Schritten 11–13.
