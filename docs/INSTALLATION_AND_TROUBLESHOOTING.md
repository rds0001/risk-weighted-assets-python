# Installation, Betriebsvoraussetzungen und Troubleshooting

## Unterstützte Umgebung

- CPython 3.10 bis 3.14 auf Linux, Windows oder macOS
- pandas, NumPy, openpyxl, PyYAML und XlsxWriter gemäß `pyproject.toml`
- Schreibrechte ausschließlich im frei wählbaren Workspace
- JavaScript-fähiger Browser für die optionale lokale Web-App

Die Library benötigt kein bestimmtes Checkout-Verzeichnis und verändert ihre installierten
Paketressourcen nicht. Geschäfts- und Ergebnisdaten werden in einem expliziten Workspace
verwaltet.

## Installation aus den geprüften Artefakten

In einer neuen virtuellen Umgebung:

```bash
python -m venv .venv
source .venv/bin/activate              # Windows PowerShell: .venv\\Scripts\\Activate.ps1
python -m pip install --upgrade pip
python -m pip install dist/risk_weighted_assets-1.0.0-py3-none-any.whl
rwa doctor
```

Alternativ kann das sdist installiert werden:

```bash
python -m pip install dist/risk_weighted_assets-1.0.0.tar.gz
```

Die Veröffentlichung auf PyPI ist ein separater, nachgelagerter Freigabeschritt. Bis dahin
ist keine Installation unter diesem Projektnamen aus einem öffentlichen Package Index
autorisiert.

## Workspace initialisieren

```bash
rwa init ./rwa-workspace
export RWA_WORKSPACE="$PWD/rwa-workspace"   # optional
rwa data list
rwa validate --dataset "$RWA_WORKSPACE/daten/rechenlaeufe/2026-08-31/v1.0.0"
```

`rwa init` exportiert Konfiguration, beide synthetischen Profile, beide Referenzdatensätze,
deren Referenzoutputs und Quellenmetadaten. Ohne `RWA_WORKSPACE` wird
`./rwa-workspace` relativ zum aktuellen Arbeitsverzeichnis verwendet.

## Installationsdiagnose

`rwa doctor` prüft Importierbarkeit, Versionsstände und Integrität der versiegelten
Ressourcen. Zusätzlich sind folgende Prüfungen hilfreich:

```bash
python -c "import rwa_engine; print(rwa_engine.__version__)"
rwa --version
rwa data list
```

## Typische Fehlerbilder

### `ModuleNotFoundError: rwa_engine`

Prüfen, ob die virtuelle Umgebung aktiv und das Wheel dort installiert ist:

```bash
python -m pip show risk-weighted-assets
python -c "import sys; print(sys.executable)"
```

### Port bereits belegt

```bash
rwa-web --port 8081
```

Dann `http://127.0.0.1:8081` öffnen. Der Health Check liegt unter `/api/health`.

### Datensatz fehlt in der Web-Auswahl

`--data-root` muss auf den Ordner zeigen, der die Struktur
`YYYY-MM-DD/version/inputs` enthält, beispielsweise:

```bash
rwa-web --data-root ./rwa-workspace/daten/rechenlaeufe
```

### Lauf wird `REJECTED`

Das erzeugte `*_REJECTED.xlsx` öffnen und das Blatt `Validation_Issues` auswerten.
Häufige Ursachen sind fehlende Workbooks, Sheets oder Spalten, ungültige Wertebereiche,
doppelte Official-Datensätze, gebrochene Referenzen, fehlende Parameter oder nicht passende
SHA-256-Werte lokal bereitgestellter Rechtsquellen.

### Vorhandener Workspace wird nicht überschrieben

Das ist der sichere Standard. Ein neues Ziel wählen oder nach vorheriger Kontrolle
`rwa init PATH --force` verwenden. `--force` ersetzt gleichnamige Paketressourcen, entfernt
aber keine zusätzlichen Benutzerdateien.

### Excel-Datei ist gesperrt

Die Datei in Excel schließen und Schreibrechte des Dataset-Outputordners prüfen. `run`
verändert Inputs nicht; `generate` und `all` erzeugen neue Dataset-Versionen und lehnen ein
bereits vorhandenes Ziel ab.

### NumPy-/pandas-Binärfehler

Eine neue virtuelle Umgebung anlegen und die definierten Abhängigkeiten durch pip auflösen
lassen. Gemischte System-, User-Site- und venv-Installationen vermeiden. Danach
`rwa doctor` und die vollständige Testsuite ausführen.

## Backup und Recovery

Für betriebliche Nutzung ist der komplette Workspace zu sichern. Zur Reproduktion werden
mindestens Input-Workbooks, Regelkonfiguration, institutionell bereitgestellte lokale
Rechtsquellen, Engine-Version und Run-Manifest benötigt. Installierte Wheels sind
unveränderliche Softwareartefakte und werden getrennt versioniert. Recovery ist durch
Neuberechnung und Vergleich des Calculation Fingerprint zu testen.
