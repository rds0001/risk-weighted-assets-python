# Python API

## Stabilitätszusage

Die in `rwa_engine.__all__` exportierten Namen bilden die öffentliche API der Version 1.x.
Module mit führendem Unterstrich und nicht exportierte Pipeline-Helfer sind intern. Für neue
Minor-Versionen bleiben öffentliche Signaturen rückwärtskompatibel; Breaking Changes
erfordern eine neue Major-Version.

## Dataset-orientierte API

```python
from rwa_engine import calculate_dataset, validate_dataset

report = validate_dataset("rwa-workspace/daten/rechenlaeufe/2026-08-31/v1.0.0")
for message in report.messages:
    print(message.severity, message.code, message.message)

if report.valid:
    result = calculate_dataset("rwa-workspace/daten/rechenlaeufe/2026-08-31/v1.0.0")
    print(result.run_id, result.metrics, result.output_files)
```

`validate_dataset()` ist schreibfrei. `calculate_dataset()` erzeugt den unveränderlichen
Laufordner mit sechs Ergebnisworkbooks, Auditdaten und Run-Manifest.

## In-Memory-API

```python
from rwa_engine import calculate_tables
from rwa_engine.synthetic import generate_synthetic_tables

tables = generate_synthetic_tables(bank_profile="KSA_BANK")
result = calculate_tables(tables)

print(result.metrics)
print(result.results["TREA_Summary"])
```

`calculate_tables()` erwartet die kanonische Zuordnung von Tabellennamen zu
`pandas.DataFrame`. Es kopiert die Inputs, validiert vollständig und schreibt keine Dateien.
`results` enthält die angewandte 2026-Sicht, `parallel_results` die Fully-loaded-Sicht.

## Ressourcen und Workspace

```python
from rwa_engine import (
    create_workspace,
    list_reference_datasets,
    list_reference_profiles,
    regulatory_sources,
)

workspace = create_workspace("rwa-workspace")
print(workspace.runs_root)
print(list_reference_profiles())
print(list_reference_datasets())
print(regulatory_sources())
```

## Ergebnisobjekte

`CalculationResult` ist ein unveränderliches Dataclass-Objekt mit:

- `status`, `run_id`, `engine_version`, `rule_set_id`
- `metrics` und `controls`
- `validation` als `ValidationReport`
- bei Dataset-Läufen `output_dir` und `output_files`
- bei In-Memory-Läufen `results` und `parallel_results`
- Komfortwerten `controls_passed`, `control_count` und `successful`

`ValidationReport` bietet `messages`, `errors`, `warnings` und `valid`. Eine einzelne
`ValidationMessage` enthält Severity, Code, Tabelle, Zeilenreferenz, Feld und Meldung.

## Exceptions

Alle erwartbaren Library-Fehler leiten von `RwaError` ab:

| Typ | Bedeutung |
|---|---|
| `ConfigurationError` | fehlerhafte oder fehlende Konfiguration/Parameter |
| `ResourceError` | Paketressource oder Workspace kann nicht gelesen/exportiert werden |
| `ValidationError` | kanonischer Tabellenvertrag ist verletzt |
| `CalculationError` | kontrolliert abgebrochene Berechnung |

Integrationen können entweder spezifische Typen oder die gemeinsame Basisklasse fangen.
