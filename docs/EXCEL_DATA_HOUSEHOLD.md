# 8. Datenstruktur, Input- und Output-Dateien

## Versionierter Datensatz

Ein Datensatz liegt unter
`daten/rechenlaeufe/YYYY-MM-DD/version/`. `inputs/` enthält genau 16
kanonische Workbooks; `outputs/RUN-.../` enthält je Calculation Fingerprint
einen unveränderbaren Ergebnisstand. `dataset_manifest.json` versiegelt die
Inputs, `run_manifest.json` dokumentiert Engine-, Code- und Inputhash,
Regelsatz, Laufzeitumgebung, Kontrollen und Kernkennzahlen.

## Gemeinsamer Excel-Vertrag

Jedes Input-Workbook enthält `README`, `DATA_DICTIONARY`, `_LOOKUPS`,
`CHANGELOG` und fachliche Excel-Tabellen. Gemeinsame Metadaten sind
`record_id`, `business_key`, `version_no`, `as_of_date`, `valid_from`,
`valid_to`, `known_from`, `known_to`, `is_official` und `record_status`.
Spalten- und Tabellennamen dürfen nicht geändert werden. Neue Zeilen werden
innerhalb der strukturierten Excel-Tabelle ergänzt.

## Die 16 Input-Workbooks

| Nr. | Workbook | Inhalt |
|---:|---|---|
| 00 | `RWA_IN_00_Run_Control.xlsx` | Laufsteuerung, Regelsätze, Official-Designation |
| 01 | `RWA_IN_01_Entities_Scopes.xlsx` | Rechtseinheiten, Konsolidierung, Genehmigungen |
| 02 | `RWA_IN_02_Parties_Ratings.xlsx` | Gegenparteien, Gruppen, externe/interne Ratings |
| 03 | `RWA_IN_03_Accounting.xlsx` | GuV-, Bilanz- und FINREP-nahe Größen |
| 04 | `RWA_IN_04_Credit_Exposures.xlsx` | Verträge, Fazilitäten, Exposures, KSA/IRB, Immobilien |
| 05 | `RWA_IN_05_Collateral_CRM.xlsx` | Sicherheiten, Bewertungen, Garantien, Allokationen |
| 06 | `RWA_IN_06_CCR_CVA_CCP.xlsx` | Netting Sets, Derivate, SFT, CCP, CVA, Settlement |
| 07 | `RWA_IN_07_Securitisations.xlsx` | Pools, Transaktionen und Tranchen |
| 08 | `RWA_IN_08_Market_Risk.xlsx` | Positionen, Risikofaktoren, Sensitivitäten, FRTB-IMA |
| 09 | `RWA_IN_09_Operational_Risk.xlsx` | Business Indicator und Verlustereignisse |
| 10 | `RWA_IN_10_Own_Funds_Reqs.xlsx` | Eigenmittel, Instrumente, AVA, Kapitalanforderungen |
| 11 | `RWA_IN_11_IRRBB.xlsx` | Zinskonditionen, Cashflows, Verhalten, Schocks |
| 12 | `RWA_IN_12_ICAAP_Scenarios.xlsx` | Risikotaxonomie, EC, Korrelation, Planung, Szenarien |
| 13 | `RWA_IN_13_Market_Data.xlsx` | Zinskurven und Marktbeobachtungen |
| 14 | `RWA_IN_14_Rules_Parameters.xlsx` | 418 Regelparameter, Formeln und Rechtsquellen |
| 15 | `RWA_IN_15_Bank_Mappings.xlsx` | Produkt-, Konto- und Rating-Mappings |

## Die sechs Output-Workbooks

| Nr. | Workbook | Zentrale Sheets |
|---:|---|---|
| 00 | `..._00_Summary.xlsx` | Run Info, Executive Summary, Metrics, TREA-Sichten |
| 01 | `..._01_Pillar1.xlsx` | KSA, IRB, CCR/CVA, Verbriefung, Markt, OpRisk, Floor |
| 02 | `..._02_Capital.xlsx` | AVA/NPE, Kapital-Stack, parallele Restriktionen, Äquivalente |
| 03 | `..._03_IRRBB.xlsx` | Gap, NII-Bänder, Währungen, Szenarien, Risikomaße |
| 04 | `..._04_ICAAP.xlsx` | Stand-alone EC, Aggregation, normative Projektion, P2 Bridge |
| 05 | `..._05_Audit.xlsx` | Validierung, Reconciliations und vollständige Lineage |

## Bearbeitungsregeln

- Vor Bearbeitung eine neue Version anlegen; alte Version nicht überschreiben.
- Datums-, Prozent- und Währungsformate gemäß Datenwörterbuch verwenden.
- `business_key` stabil halten und neue fachliche Version über `version_no`
  sowie Gültigkeits-/Kenntnisintervall abbilden.
- Pro Objekt und Auswahlzeitpunkt genau eine Official-Version sicherstellen.
- Keine Formeln, Pivot-Tabellen oder Hilfsspalten in kanonischen Datentabellen
  ergänzen; bankeigene Vorverarbeitung außerhalb oder über Mappings abbilden.
- Nach Änderung Browseransicht aktualisieren. „Bearbeitet“ zeigt an, dass der
  Input vom ursprünglichen synthetischen Manifest abweicht; der Lauf hasht
  stets den tatsächlichen Inhalt.
