# 7. Aufbau des Programms, Komponenten und Libraries

## Architekturüberblick

Die Anwendung ist eine installierbare, modular aufgebaute Python-Library. Der Rechenkern
unter `src/rwa_engine` umfasst Fachalgorithmen, Datenverträge, Validierung,
Parameterzugriff und Orchestrierung. Die Web-App unter `rwa_engine.web` ist eine additive
HTTP-Schicht und ruft dieselbe Dataset-Pipeline wie API und CLI auf. Excel bleibt der
führende persistierte Ein- und Ausgabekanal; für Integrationen steht zusätzlich eine
In-Memory-DataFrame-API bereit.

```text
Browser
  → lokaler Python-HTTP-Server
    → Datensatzkatalog und sichere Downloads
    → calculate_dataset / run_dataset
      → Excel-Import und Validierung
      → Fachengines und Aggregationen
      → Excel-Export, Audit und Manifest

Python / CLI
  → öffentliche API beziehungsweise installierter `rwa`-Entry-Point
    → immutable Paketressourcen oder expliziter Workspace
      → identischer Rechenkern
```

## Python-Komponenten

| Komponente | Verantwortung |
|---|---|
| `config_io.py` | YAML-Profile, Regelsätze und Parametermatrizen laden |
| `contracts.py` | kanonische Tabellen-, Spalten- und Schlüsselverträge |
| `excel_io.py` | Excel-Import/-Export, Templates und Validierung |
| `parameters.py` | fail-closed Zugriff auf externe regulatorische Parameter |
| `formulas.py` | atomare, möglichst pure Rechenfunktionen |
| `engines.py` | risikomodulweise Berechnung und Aggregation |
| `pipeline.py` | End-to-End-Orchestrierung, Fingerprints, Outputs und Audit |
| `synthetic.py` | Integritätsprüfung und Materialisierung externer Profile |
| `cli.py` | Kommandozeilenschnittstelle |
| `api.py` | stabile Dataset- und In-Memory-Python-API |
| `models.py` | strukturierte Ergebnis- und Validierungsobjekte |
| `resources/` | lesender Zugriff auf unveränderliche Wheel-Ressourcen |
| `workspace.py` | Export und Verwaltung beschreibbarer Arbeitsbereiche |
| `web/catalog.py` | Datensatz-, Lauf- und Dateikatalog |
| `web/server.py` | lokale HTTP-API und Run-Button |

## Verwendete Libraries

- Python 3.10 oder höher als Laufzeit.
- pandas ab 2.2 (unterhalb 3) für tabellarische Verarbeitung und Excel-Integration.
- NumPy ab 1.26 (unterhalb 3) für Vektor-, Matrix- und Korrelationsrechnungen.
- openpyxl als Excel-Engine und für strukturierte Workbooks.
- PyYAML für externe Regelsatz- und Profilkonfiguration.
- `statistics.NormalDist` aus der Python-Standardbibliothek für Verteilungsfunktionen.
- pytest und Hypothesis ausschließlich für Tests.
- Python-Standardbibliothek `http.server` für die lokale Browser-App.

Es wurden für die Web-App keine zusätzlichen Pakete installiert. Die lokale
Bindung an `127.0.0.1` vermeidet eine unbeabsichtigte Netzfreigabe. Für einen
Mehrbenutzerbetrieb sind Reverse Proxy, TLS, Authentisierung und
Rollenberechtigungen vorgeschaltet bereitzustellen.

## Source- und Laufzeitstruktur

```text
src/rwa_engine/               installierbarer Rechenkern, API, CLI und Web-App
src/rwa_engine/resources/     synthetische Daten, Konfiguration und Quellenmetadaten
tests/                        Fach-, Vertrags-, API- und End-to-End-Tests
docs/                         Methodik, Betrieb, Governance und Quellenkatalog
tools/                        Build- und Distributionsprüfungen
dist/                         lokal erzeugte Wheel- und sdist-Artefakte

<workspace>/
├── daten/rechenlaeufe/       versionierte Excel-Inputs und -Outputs
├── daten/referenzprofile/    exportierte synthetische Ausgangsdaten
├── daten/konfiguration/      Bankprofile und regulatorische YAML-Parameter
└── Standards/                Metadaten zu externen amtlichen Quellen
```

## Einstiegspunkte

```bash
rwa --help
rwa-web --help
python -m pytest
```

Code und Web-App sind regulär installierte Entry-Points. Ressourcen werden über
`importlib.resources` adressiert; veränderliche Daten ausschließlich über explizite oder
durch `RWA_WORKSPACE` konfigurierte Pfade.

## Operationalisierter Implementierungsstand

**Version:** 1.1.0
**Referenzstichtag:** 31.08.2026

**Daten-/Regeltrennung:** Geschäfts-, Markt-, Szenario-, Generator- und
Regelwerte liegen ausschließlich in versionierten YAML-/Excel-Datenquellen.
Der Python-Code enthält nur Rechenalgorithmen, Schema, Validierung und
Orchestrierung. Referenzprofile und Rechenläufe sind per SHA-256 nachvollziehbar.

| Bereich | Implementiert | Atomarer Output | Parallel-/Kontrollsicht |
|---|---:|---|---|
| KSA EAD/CCF/RW | ja | `SA_Detail` | KSA-Shadow für S-TREA |
| Immobilien/ETV/Loan Splitting | ja | Segmente in `SA_Detail` | Pre-/Post-CRM |
| CRM/Substitution | ja | Schutzbetrag und Substitutions-RW | Allokationsprüfung |
| IRB Corporate/Retail/Floors/EL | ja | `IRB_Detail` | Shortfall/Excess |
| Crypto-Übergang | ja | `Crypto_Detail` | Tier-1-Limitkennzeichen |
| SA-CCR/SFT | ja | `CCR_Detail`, `SFT_Detail` | S-TREA |
| CCP | ja | `CCP_Detail` | QCCP/NQCCP |
| Verbriefung | ja | `SEC_Detail` | exakte SSFA-Grenztranche, SEC-IRBA/SA/ERBA, STS/NPE/Resec |
| CVA | ja | `CVA_Summary`, `CVA_Buckets` | BA-CVA mit Hedge-Mismatch und SA-CVA parallel |
| Settlement/Free Delivery | ja | `Settlement_Detail` | – |
| Großkreditüberschreitung | ja | `Large_Exposure` | – |
| Markt Legacy | ja | `Market_Legacy` | offizieller 2026-Ansatz |
| FRTB-SA | ja | `FRTB_Buckets`, `FRTB_Risk_Classes`, `FRTB_DRC`, `FRTB_Summary` | drei Korrelationsszenarien, DRC und RRAO; fully-loaded |
| FRTB-IMA | ja | `FRTB_IMA` | Yesterday/60-Tage IMCC/SES, PLA, DRC/Add-ons; genehmigungsabhängig |
| Operationelles Risiko BIC | ja | `Operational_Risk` | ILM-Kontrolle |
| U-/S-TREA und Output Floor | ja | `TREA_Summary` | `Floor_Allocation` |
| AVA/NPE-Backstop | ja | `Prudent_Valuation`, `NPE_Backstop` | CET1-Abzug |
| CET1/AT1/T2 | ja | `Capital_Stack` | explizite Abzüge/Amortisation |
| P2R/Puffer/P2G | ja | `Capital_Stack` | Kapitalqualitäten |
| Leverage/MREL/TLAC | ja | `Parallel_Constraints` | getrennte Restriktionen |
| IRRBB EVE/sechs Schocks/SOT | ja | `IRRBB_Scenarios`, `IRRBB_Currency_Scenarios` | Mehrwährung, VaR/ES |
| NII/EaR/NII-SOT | ja | `IRRBB_Repricing_Gap`, `IRRBB_NII_Bands`, `IRRBB_Scenarios` | periodisch/Constant Balance |
| CSRBB | ja | `IRRBB_Risk_Measures` | Stressverlust |
| ICAAP Economic Capital | ja | `EC_Standalone`, `EC_Aggregation` | Korrelation/Diversifikation |
| ICAAP normative Perspektive | ja | `Normative_Projection` | Base/Adverse |
| P2R-/EC-/IRRBB-RWA-Äquivalent | ja | `RWA_Equivalents`, `Pillar2_Bridge` | Double-Count-Control |
| Bitemporal/Official | ja | Audit/Run-Metadaten | Official-Designation |
| Lineage/Reconciliation | ja | Audit-Workbook | Formelregister/Input-, Code- und Lauf-Fingerprint |

Die Tabelle bezeichnet die operationalisierte Rechenschicht, nicht automatisch
die fachliche Produktivfreigabe jeder CRR-Sonderkonstellation. Der genaue
Abnahmeumfang und die institutsbezogenen Freigabepunkte stehen in
`docs/GOVERNANCE_CONTROLS_AND_ACCEPTANCE.md`. Instituts- oder rechtsstandsabhängige Parameter
bleiben versionierte Eingabedaten und müssen vor einem offiziellen Einsatz
freigegeben werden.

Der aktuelle externe Regelkatalog umfasst 418 materialisierte Parameterzeilen.
Die automatisierte Testsuite umfasst 44 Tests; die beiden Referenzprofile
erreichen jeweils 12 von 12 Laufkontrollen ohne Validierungsfehler.
