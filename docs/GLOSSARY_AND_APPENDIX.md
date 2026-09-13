# 12. Glossar, Kennzahlenkatalog und Anhänge

## Glossar

| Begriff | Bedeutung |
|---|---|
| AT1 | Additional Tier 1 Capital |
| BA-CVA | Basic Approach für Credit Valuation Adjustment Risk |
| BIC | Business Indicator Component |
| CBR | Combined Buffer Requirement |
| CCR | Counterparty Credit Risk |
| CET1 | Common Equity Tier 1 |
| CCF | Credit Conversion Factor |
| CRM | Credit Risk Mitigation |
| CSRBB | Credit Spread Risk in the Banking Book |
| DRC | Default Risk Charge |
| EAD | Exposure at Default |
| EaR | Earnings at Risk |
| EC | Economic Capital |
| EL | Expected Loss |
| ERBA | External Ratings-Based Approach für Verbriefungen |
| ETV/LTV | Exposure-/Loan-to-Value |
| EVE | Economic Value of Equity |
| FRTB | Fundamental Review of the Trading Book |
| ICAAP | Internal Capital Adequacy Assessment Process |
| ILM | Internal Loss Multiplier |
| IMCC | Internal Models Capital Charge |
| IRB/IRBA | Internal Ratings-Based Approach |
| IRRBB | Interest Rate Risk in the Banking Book |
| KSA | Kreditrisiko-Standardansatz |
| LGD | Loss Given Default |
| MREL | Minimum Requirement for Own Funds and Eligible Liabilities |
| NII | Net Interest Income |
| NMD | Non-Maturity Deposit |
| OCR | Overall Capital Requirement |
| PD | Probability of Default |
| P2G | Pillar 2 Guidance |
| P2R | Pillar 2 Requirement |
| PLA | Profit and Loss Attribution Test |
| RRAO | Residual Risk Add-on |
| RWA/RWEA | Risk-Weighted Assets/Risk Exposure Amounts |
| SA-CCR | Standardised Approach for Counterparty Credit Risk |
| SA-CVA | Standardised Approach for CVA Risk |
| SBM | Sensitivities-Based Method |
| SEC-IRBA/SA | Verbriefungsansatz auf IRB-/Standardbasis |
| SES | Stress Scenario Risk Measure für NMRF |
| SFT | Securities Financing Transaction |
| SMA | Standardised Measurement Approach für operationelles Risiko |
| SOT | Supervisory Outlier Test |
| SREP | Supervisory Review and Evaluation Process |
| SSFA | Simplified Supervisory Formula Approach |
| T2 | Tier 2 Capital |
| TLAC | Total Loss-Absorbing Capacity |
| TREA | Total Risk Exposure Amount |
| U-/S-TREA | Unfloored-/Standardised-TREA im Output Floor |
| VaR/ES | Value at Risk/Expected Shortfall |

## Zentrale Kennzahlen und Einheiten

Geldbeträge werden in der Reporting Currency, im Referenzprofil EUR,
geführt. Quoten werden intern als Dezimalzahl gespeichert und in der
Oberfläche als Prozent formatiert. TREA und RWEA sind Geldbeträge; eine
Kapitalanforderung `K` wird grundsätzlich mit dem Faktor 12,5 in RWEA
übersetzt, soweit der jeweilige Ansatz dies vorsieht. EVE- und NII-SOT sind
Verhältnisse zum jeweils regulatorisch definierten Nenner.

## Reproduktionsbefehle

```bash
rwa init ./rwa-workspace
rwa all --data-root ./rwa-workspace/daten/rechenlaeufe --bank-profile MID_SIZE_UNIVERSAL --version v1.0.1
rwa all --data-root ./rwa-workspace/daten/rechenlaeufe --bank-profile KSA_BANK --version v1.0.1-ksa
rwa-web --data-root ./rwa-workspace/daten/rechenlaeufe
python3 -m pytest
```

## Dokumenten- und Quellenorte

- Quellenmetadaten: `rwa sources`; lokal beschaffte Rechtsquellen verbleiben im geschützten Workspace
- Formel- und Datenmodellquellen: `docs/PILLAR_1_METHODOLOGY.md`, `docs/PILLAR_2_IRRBB_ICAAP.md` und `docs/DATA_MODEL_AND_HISTORY.md`
- Rechenkern: installiertes Paket `rwa_engine`
- Web-App: Modul `rwa_engine.web`
- Versionierte Daten: `<workspace>/daten/rechenlaeufe/`
- Referenzprofile: unveränderliche Paketressourcen und `<workspace>/daten/referenzprofile/`
- Regulatorische Parameter: `<workspace>/daten/konfiguration/regulatory/`
- Dokumentation: `docs/`

## Auslegungsvorbehalt

Diese Dokumentation bildet den implementierten und getesteten Stand ab. Sie
ist bei jeder materiellen Rechts-, Methoden-, Datenmodell- oder
Softwareänderung zu versionieren. Die lokale Quellensammlung und das
Quellenmanifest sind regelmäßig auf Aktualität zu prüfen. Institutsbezogene
Entscheidungen bleiben in den geschützten Governance-Prozessen der jeweiligen
Bank zu ergänzen.

## Bestehende Engine-Betriebsbeschreibung

Institutsneutrale Python-Gesamtlösung für CRR-III-RWEA, regulatorischen Kapital-Stack, IRRBB und ICAAP. Die Engine verwendet die Fachdefinitionen aus:

- `docs/PILLAR_1_METHODOLOGY.md`
- `docs/PILLAR_2_IRRBB_ICAAP.md`
- `docs/DATA_MODEL_AND_HISTORY.md`

## Python-Umgebung

Die unterstützten Python- und Abhängigkeitsversionen stehen in `pyproject.toml`. Für jeden
Betrieb wird eine eigene virtuelle Umgebung empfohlen; `rwa doctor` prüft die aktive
Installation und die enthaltenen Referenzressourcen.

## Ein vollständiger Lauf

Synthetische Daten erzeugen und sämtliche Rechnungen ausführen:

```bash
rwa all \
  --data-root ./rwa-workspace/daten/rechenlaeufe \
  --as-of-date 2026-08-31 \
  --version v1.0.0 \
  --seed 5752026
```

Ein zweites, bewusst weniger komplexes Profil demonstriert die
Institutsneutralität:

```bash
rwa all --data-root ./rwa-workspace/daten/rechenlaeufe --bank-profile KSA_BANK
```

Nur synthetische Inputs erzeugen:

```bash
rwa generate --data-root ./rwa-workspace/daten/rechenlaeufe --as-of-date 2026-08-31 --version v1.0.1
```

Vorhandene oder real befüllte Inputs rechnen:

```bash
rwa run --dataset ./rwa-workspace/daten/rechenlaeufe/2026-08-31/v1.0.0
```

Leere Excel-Templates erzeugen:

```bash
rwa templates --output ./rwa-workspace/daten/templates/v1.0.0
```

Tests:

```bash
python3 -m pytest
```

## Verzeichnis- und Versionslogik

```text
<workspace>/daten/rechenlaeufe/
└── YYYY-MM-DD/
    └── vMAJOR.MINOR.PATCH/
        ├── dataset_manifest.json
        ├── inputs/
        │   ├── RWA_IN_00_Run_Control.xlsx
        │   ├── ...
        │   └── RWA_IN_15_Bank_Mappings.xlsx
        └── outputs/
            └── RUN-YYYYMMDD-<INPUT_HASH>/
                ├── run_manifest.json
                ├── RWA_OUT_..._00_Summary.xlsx
                ├── RWA_OUT_..._01_Pillar1.xlsx
                ├── RWA_OUT_..._02_Capital.xlsx
                ├── RWA_OUT_..._03_IRRBB.xlsx
                ├── RWA_OUT_..._04_ICAAP.xlsx
                └── RWA_OUT_..._05_Audit.xlsx
```

Der Run-Identifier enthält einen Hash sämtlicher Input-Workbooks. Inputs und Outputs unterschiedlicher Stichtage oder Datenvertragsversionen werden nicht überschrieben.

Zusätzlich enthält der Run-Identifier den Hash der tatsächlich ausgeführten
Python-Quellen und die Engine-Version. Ein identischer Input mit identischer
Engine ist idempotent; eine Codeänderung erzeugt einen neuen, revisionssicher
unterscheidbaren Lauf.

## Keine Daten im Code

Die Trennung ist strikt:

- `rwa_engine` enthält Algorithmen, Datenverträge, Validierung und Orchestrierung.
- Paketressource `daten/konfiguration/regulatory/crr3_eu_2026_v1.yaml` enthält sämtliche verwendeten regulatorischen Koeffizienten, Schwellenwerte und internen Modellparameter. Die kompakten Tabellen werden beim Erzeugen zu derzeit **418 atomaren Parameterzeilen** in `RWA_IN_14_Rules_Parameters.xlsx` materialisiert.
- Paketressource `daten/referenzprofile/*/inputs/` enthält synthetische Geschäftsbestände, Markt- und Szenariodaten als kanonische Excel-Dateien.
- Paketressource `daten/konfiguration/profiles/*.yaml` bestimmt, welches externe Profil verwendet und wie es materialisiert wird.
- `profile_manifest.json` versiegelt jedes Referenzpaket per SHA-256. Manipulierte Referenzdateien werden vor der Verarbeitung abgelehnt.

Es gibt keine regulatorischen Fallbackwerte im `ParameterStore`: Fehlende,
nichtnumerische oder mehrdeutige Parameter beenden den Lauf kontrolliert.

## Excel-Vertrag

Jedes Input-Workbook enthält:

- `README`
- `DATA_DICTIONARY`
- ausgeblendete `_LOOKUPS`
- `CHANGELOG`
- fachliche Sheets mit strukturierten `tbl_in_*`-Tabellen

Gemeinsame Metadaten jeder Tabelle:

```text
record_id, business_key, version_no, as_of_date,
valid_from, valid_to, known_from, known_to,
is_official, record_status
```

Spalten- und Tabellennamen sind der stabile Datenvertrag. Bankeigene Produkte, Konten und Ratings werden in `RWA_IN_15_Bank_Mappings.xlsx` auf das kanonische Modell abgebildet. Berechnungsentscheidungen hängen nicht von bankindividuellen Bezeichnungen ab.

## Rechenreihenfolge

```text
Excel Load
→ Schema-/Referenzvalidierung
→ bitemporale Official-Selektion
→ KSA/IRB/CRM
→ CCR/SFT/CCP/CVA/Settlement/Großkredit
→ Verbriefung
→ Legacy-Markt + FRTB-SA/IMA-Parallelrechnung
→ Operationelles Risiko
→ U-TREA/S-TREA/Output Floor
→ Eigenmittel/Kapital/Leverage/MREL/TLAC
→ IRRBB/CSRBB
→ ICAAP normativ/ökonomisch
→ RWA-Äquivalenzsichten
→ Reconciliations, Lineage und Excel-Export
```

Der IRRBB-Output umfasst sowohl die periodische Sicht (`IRRBB_Repricing_Gap`,
`IRRBB_NII_Bands`, EaR/NII) als auch die barwertige Sicht
(`IRRBB_Scenarios`, `IRRBB_Currency_Scenarios`, EVE, VaR und Expected
Shortfall). `Pillar2_Bridge` hält den Übergang von aufsichtlich vorgegebenem
P2R und internem IRRBB-/CSRBB-Kapital zu den strikt isolierten
RWA-Äquivalenzsichten fest.

Ein offizieller 2026-Lauf verwendet das Legacy-Marktrisikoregime. FRTB wird mit demselben Input-Snapshot als getrennte fully-loaded Sicht gerechnet.

## Fehlerbehandlung

Fehlende Workbooks, Sheets, Pflichtspalten oder Pflichtwerte, doppelte Schlüssel
und Parameter, ungültige Wertebereiche, fehlerhafte Gültigkeitsintervalle oder
gebrochene Referenzen führen zu einem abgelehnten Lauf. Auch dann wird ein
strukturiertes `REJECTED`-Workbook mit allen Befunden erzeugt. Leere optionale
Module werden dagegen transparent als `NOT_APPLICABLE` behandelt.

Leere, für ein Institut nicht anwendbare Module werden als Warnung beziehungsweise `NOT_APPLICABLE` behandelt und benötigen keine Dummy-Geschäfte.

## Verifizierter Referenzstand

- 44 automatisierte Tests bestanden, 0 fehlgeschlagen.
- Universalbanklauf `RUN-20260831-B24BAAAB20`: 12/12 Kontrollen,
  0 Validierungsfehler.
- KSA-Banklauf `RUN-20260831-1E80913B9B`: 12/12 Kontrollen,
  0 Validierungsfehler; leere, nicht anwendbare Module werden als 17 explizite
  Warnungen ausgewiesen.

Die vollständigen Abnahmewerte und die verbleibenden institutsbezogenen
Freigabeaufgaben stehen in `docs/GOVERNANCE_CONTROLS_AND_ACCEPTANCE.md`.

## Fachlicher Betriebshinweis

Der synthetische Datensatz ist ein Test- und Referenzprofil, keine aufsichtsrechtliche Meldung. Vor Verwendung realer Daten müssen Rule Set, Parameter, Modellgenehmigungen, nationale Optionen und institutsindividuelle SREP-Anforderungen fachlich freigegeben werden. Ein RWA-Äquivalent ist eine Managementsicht und wird nie gleichzeitig mit dem zugrunde liegenden Kapitalbetrag zum legalen TREA addiert.
