# CLI und lokale Web-App

Die installierten Befehle `rwa` und `rwa-web` sind unabhängig von einem Repository-Checkout.
Alle Berechnungspfade verwenden denselben Rechenkern.

## Kommandoreferenz

| Befehl | Zweck |
|---|---|
| `rwa init [PATH]` | vollständigen, beschreibbaren Referenz-Workspace exportieren |
| `rwa doctor` | Installation und Integrität der Paketressourcen prüfen |
| `rwa data list` | enthaltene Profile und Datensätze auflisten |
| `rwa data export PATH` | vollständigen Ressourcenexport erzeugen |
| `rwa sources` | maschinenlesbares Inventar offizieller Quellen ausgeben |
| `rwa templates --output PATH` | 16 leere kanonische Input-Workbooks erzeugen |
| `rwa generate [Optionen]` | synthetischen Datensatz materialisieren |
| `rwa validate --dataset PATH` | Dataset ohne Berechnung validieren |
| `rwa run --dataset PATH` | vorhandenes Dataset validieren und berechnen |
| `rwa all [Optionen]` | Dataset erzeugen und unmittelbar berechnen |
| `rwa web [Optionen]` | lokale Browseroberfläche starten |

Für alle Detailoptionen dient `rwa BEFEHL --help` als verbindliche Referenz.

## Beispiele

```bash
rwa init ./rwa-workspace
rwa run --dataset ./rwa-workspace/daten/rechenlaeufe/2026-08-31/v1.0.0
rwa run --dataset ./rwa-workspace/daten/rechenlaeufe/2026-08-31/v1.0.0 --json
rwa all --bank-profile KSA_BANK --version v1.0.1-ksa
rwa templates --output ./rwa-workspace/daten/templates/v1.0.0
```

Die Generatorparameter sind `--data-root`, `--as-of-date`, `--version`, `--seed`,
`--bank-profile` und optional `--config-root`. Fehlende Werte stammen aus dem gewählten,
versionierten Profil.

## Exit Codes

- `0`: erfolgreich oder Validierung ohne Fehler
- `2`: fachlich/technisch ungültige Eingabe oder behandelter Library-Fehler
- andere Werte: unerwarteter Laufzeit- oder Umgebungsfehler

Automationen sollten bei `run --json` neben dem Exit Code mindestens `status`, `run_id`,
`controls_passed`, `control_count` und `output_dir` auswerten.

## Web-App

```bash
rwa-web \
  --data-root ./rwa-workspace/daten/rechenlaeufe \
  --host 127.0.0.1 \
  --port 8080
```

Alternativ: `rwa web` mit denselben Optionen. Anschließend
`http://127.0.0.1:8080` öffnen.

Die App bietet:

- Auswahl aus `YYYY-MM-DD/version` unter dem angegebenen Data Root
- Anzeige von Input- und Outputdateien sowie Dataset-/Run-Metadaten
- Start einer Berechnung über dieselbe `run_dataset`-Pipeline
- Download einzelner Excel-Ergebnisse
- Sperre gegen parallele Doppelläufe desselben Datasets

## HTTP-Schnittstelle

| Methode/Pfad | Funktion |
|---|---|
| `GET /api/health` | Liveness-Status |
| `GET /api/datasets` | Dataset-Katalog |
| `GET /api/dataset?dataset=...` | Detailansicht eines Datasets |
| `POST /api/run` | Berechnung; JSON-Body `{"dataset": "..."}` |
| `GET /files?...` | geprüfter Download einer katalogisierten Datei |

Der Katalog normalisiert alle Pfade und verhindert Traversal außerhalb des konfigurierten
Data Root. HTTP-Fehler werden als JSON zurückgegeben; Tracebacks werden nicht an den Browser
ausgeliefert.

## Sicherheitsgrenze

Der Server hat bewusst keine Benutzerverwaltung, Authentisierung, Autorisierung oder TLS.
Er bindet standardmäßig ausschließlich an `127.0.0.1` und ist für einen vertrauenswürdigen
Einzelplatz bestimmt. Eine Bindung an externe Interfaces erfordert eine separate
Betriebsfreigabe sowie vorgeschaltete Schutzmechanismen.
