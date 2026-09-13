# Paketressourcen und Workspaces

## Trennungsprinzip

Installierte Wheels können schreibgeschützt oder als Zip-Importer bereitgestellt sein.
Deshalb liest die Library gebündelte Referenzdaten über `importlib.resources` und schreibt
niemals in das Installationsverzeichnis. Alle veränderlichen Inputs und Ergebnisse liegen in
einem vom Anwender kontrollierten Workspace.

```text
immutable wheel resources
  ├── daten/konfiguration
  ├── daten/referenzprofile
  ├── daten/rechenlaeufe
  └── Standards/00_manifest/sources.json
                 │ export
                 ▼
writable workspace
  ├── daten/konfiguration
  ├── daten/referenzprofile
  ├── daten/rechenlaeufe/YYYY-MM-DD/version/{inputs,outputs}
  ├── Standards/00_manifest
  └── workspace_manifest.json
```

## Wahl des Workspace

1. expliziter Pfad in Python oder CLI hat Vorrang;
2. sonst wird `RWA_WORKSPACE` verwendet;
3. ohne Umgebungsvariable gilt `./rwa-workspace` im aktuellen Arbeitsverzeichnis.

Ein Workspace ist kein Teil des Wheels. Er darf bankspezifische Daten enthalten und muss
entsprechend klassifiziert, berechtigt, protokolliert und gesichert werden.

## Enthaltene synthetische Daten

- `MID_SIZE_UNIVERSAL`: breites Profil mit SA, IRB, CCR, CVA, Verbriefung, Markt,
  Operationellem Risiko, IRRBB und ICAAP
- `KSA_BANK`: fokussiertes SA-Profil ohne interne Kreditrisikomodelle
- je Profil 16 versiegelte Referenz-Inputworkbooks
- zwei berechnungsfertige Datasets zum Stichtag 31.08.2026
- je Dataset ein zurückbehaltener erfolgreicher Referenzlauf mit sechs Outputworkbooks
- versionierte Profile, Generator- und Regulatory-Konfiguration

## Integrität und externe Quellen

Alle Daten sind synthetisch. Profile und Datasets besitzen SHA-256-Manifeste. Der Befehl
`rwa doctor` validiert die versiegelten Ressourcen. Das Quelleninventar enthält offizielle
Links und Archivprüfsummen, aber keine heruntergeladenen Drittveröffentlichungen.
