# 11. Governance, Kontrollen, Tests und Abnahme

## Drei Verteidigungslinien

Die erste Linie verantwortet korrekte, vollständige und termingerechte
Quelldaten. Risikocontrolling und Meldewesen verantworten Methoden,
Regelparameter, Reconciliation und Official-Freigabe. Unabhängige Validierung
und Revision beurteilen Modellrisiko, Kontrolldesign, Änderungsprozess und
Nachvollziehbarkeit. IT verantwortet Verfügbarkeit, Berechtigungen, Backup,
Logging und sichere Laufzeit.

## Änderungs- und Freigabeprozess

1. Änderung fachlich klassifizieren: Recht, Parameter, Datenmodell,
   Algorithmus, Mapping oder reine Darstellung.
2. Rechtsreferenz, Anwendungsdatum und betroffene Regelsätze dokumentieren.
3. Neue Version statt Überschreibung erzeugen.
4. Golden Cases und vollständige Regression ausführen.
5. Referenzprofile rechnen und Reconciliations prüfen.
6. Fachreview und Vier-Augen-Freigabe protokollieren.
7. Official-Designation erst nach erfolgreicher Freigabe setzen.

## Testpyramide

- Unit- und Golden-Case-Tests für konkrete Formeln.
- Property-Tests für Monotonie und mathematische Invarianten.
- Datenvertrags-, Wertebereichs- und Referenztests.
- Negative Tests für fehlende/mehrdeutige Parameter und Rechtsquellen.
- End-to-End-Tests für Universalbank und KSA-Bank.
- HTTP-Tests für Katalog, Pfadsicherheit, Run-Button und Excel-Download.
- Manuelle beziehungsweise institutsbezogene COREP-Reconciliation vor
  Produktivfreigabe.

## Technischer Abnahme- und Fortsetzungsstand

**Stand:** 01.09.2026  
**Engine-Version:** 1.1.0
**Referenzstichtag:** 31.08.2026

## Abgenommener technischer Stand

- Ein CLI-Lauf erzeugt beziehungsweise übernimmt 16 kanonische Input-Workbooks,
  selektiert den bitemporalen Official-Snapshot, berechnet alle implementierten
  Komponenten und schreibt sechs strukturierte Output-Workbooks.
- Geschäfts-, Markt-, Szenario-, Generator- und Regelwerte befinden sich nicht
  im Python-Code. Sie liegen in externen Excel-/YAML-Dateien.
- Der Regelkatalog wird in `RWA_IN_14_Rules_Parameters.xlsx` materialisiert und
  vom `ParameterStore` ohne fachliche Fallbackwerte gelesen. Das aktuelle
  Regelprofil materialisiert **418 atomare, historisierbare Parameterzeilen**.
- Das vollständige Referenzprofil und das KSA-Profil verwenden dieselbe Engine.
- Alle Ergebniszeilen tragen Lauf-ID, Ergebnisversion, Stichtag,
  Kenntniszeitpunkt, Regelsatz, Sicht und Official-Flag.
- Inputdateien, lokale Rechtsquellen und Python-Quellen werden gehasht. Der
  Calculation Fingerprint verbindet Input-, Code- und Engine-Version.
- Schema-, Pflichtwert-, Intervall-, Wertebereichs-, Referenz-, Parameter- und
  Rechtsquellenfehler führen zu kontrollierter Ablehnung.
- Periodische IRRBB-Ergebnisse enthalten Repricing-Gaps und NII-Beiträge je
  Laufzeitband; die barwertige Sicht enthält EVE, sechs Standardzinsschocks,
  Mehrwährungsaggregation, VaR und Expected Shortfall.
- FRTB-SA rechnet Delta, Vega und Curvature in Low-/Medium-/High-
  Korrelationsszenarien sowie DRC für Non-Securitisation, Non-CTP und CTP und
  das RRAO. Die IMA-Parallelrechnung verwendet Yesterday-/60-Tage-IMCC und
  SES/NMRF, Multiplikatoren, DRC, Add-ons und PLA-Zulässigkeit.
- BA-CVA berücksichtigt Single-Name- und Index-Hedges einschließlich
  Laufzeit- und Hedge-Mismatch; SA-CVA wird nach Risikoklasse und Bucket
  aggregiert.
- SEC-IRBA/SEC-SA verwenden die SSFA auch für den die K_A-Grenze schneidenden
  Tranchenteil. SEC-ERBA verwendet die vollständigen externen 17-Stufen-
  Tabellen mit Laufzeitinterpolation, Seniorität und STS-Behandlung.
- P2R, Puffer, P2G, Leverage, MREL/TLAC, IRRBB-/CSRBB-Managementkapital und die
  isolierten RWA-Äquivalenzsichten werden getrennt ausgewiesen; Kontrollen
  verhindern eine Addition der Äquivalenzsicht zum legalen TREA.

## Fachlicher Freigabestatus

Die Lösung ist eine lauffähige, reproduzierbare Referenzimplementierung und ein
belastbares Fundament für die institutsindividuelle Umsetzung. Sie ist ohne
fachliche Modellvalidierung und aufsichtliche Freigabe **keine Meldesoftware**.

Vor einem produktiven regulatorischen Einsatz bleiben folgende
**Freigabe- und Institutsparametrisierungsaufgaben**. Sie sind bewusst keine
verdeckten Annahmen im Code:

1. Die externen FRTB-/SA-CVA-Bucket-, Tenor-, Risiko- und
   Korrelationsparameter sind je gültigem Rechtsstand vollständig zu beladen
   und gegen die institutseigene COREP-Abstimmung freizugeben. Das
   Referenzprofil deckt die Rechenpfade ab, ersetzt aber keinen Meldebestand.
2. FRTB-IMA übernimmt validierte IMCC-/SES-/DRC-Ergebnisse je Desk. Eine
   vollständige interne Pricing-, Liquiditätshorizont- und
   Stressperiodenmodellierung ist Bestandteil des genehmigten Bankmodells und
   nicht dieses generischen RWA-Kerns.
3. Verbriefungs-SRT, Ansatzberechtigung, Due-Diligence und gegebenenfalls
   transaktionsspezifische Caps müssen vor der Übergabe an den Rechenkern
   rechtlich entschieden und versioniert angeliefert werden.
4. Beteiligungs-, DTA- und sonstige Schwellenabzüge, Minderheitsanteile und
   Grandfathering werden als explizit freigegebene Eigenmittelkomponenten
   angeliefert; die Engine berechnet daraus den Kapital-Stack und die
   Instrumentenamortisation, ersetzt aber kein Beteiligungs-Konsolidierungssystem.
5. IRRBB-NMD-, Prepayment-, Early-Redemption-, Commercial-Margin- und
   dynamische-Bilanz-Annahmen sind bankindividuelle Modelle. Die Engine
   historisiert sie und verarbeitet die daraus gelieferten Cashflows und
   Verhaltensgewichte periodisch und barwertig.
6. P2R bleibt eine SREP-Entscheidung. IRRBB-/CSRBB- und EC-RWA-Äquivalente sind
   ausdrücklich Managementsichten und dürfen nicht additiv zum legalen TREA
   doppelt gezählt werden.

## Empfohlener nächster Arbeitsblock

1. Die vorhandenen Formel-Golden-Cases um institutsspezifisch freigegebene
   COREP-Beispielfälle ergänzen.
2. COREP-Reconciliation und institutsindividuelle Sign-off-Matrix ergänzen.
3. Rollen-/Berechtigungskonzept und Vier-Augen-Freigabe für Official-Snapshots
   an die Zielplattform anbinden.
4. Performance-, Parallelitäts-, Backup-, Recovery- und Deploymenttests
   für die Zielumgebung durchführen.

## Reproduktionsbefehle

```bash
python3 -m pytest
rwa run --dataset ./rwa-workspace/daten/rechenlaeufe/2026-08-31/v1.0.0
rwa run --dataset ./rwa-workspace/daten/rechenlaeufe/2026-08-31/v1.0.0-ksa
```

## Letzte verifizierte Läufe

- Testsuite: **44 bestanden, 0 fehlgeschlagen**. Darin enthalten sind
  Formel-Golden-Cases sowie negative Schema-, Referenz-, Parameter-,
  Rechtsquellen- und Official-Snapshot-Tests.
- Universalbank: gebündelter Referenzlauf unter `daten/rechenlaeufe/2026-08-31/v1.0.0/outputs/`,
  **12/12 Kontrollen bestanden**, **0 Validierungsfehler**. Transitional 55 %:
  TREA 8.691.246.387,71 EUR, Floor nicht bindend. Fully loaded 72,5 %:
  TREA 8.931.912.591,86 EUR, Floor bindend, Uplift 61.863.913,84 EUR.
- KSA-Bank: gebündelter Referenzlauf unter `daten/rechenlaeufe/2026-08-31/v1.0.0-ksa/outputs/`,
  **12/12 Kontrollen bestanden**, **0 Validierungsfehler**. Die 17
  Audit-Warnungen kennzeichnen ausschließlich leere, für dieses Profil nicht
  anwendbare Module; IRB, CVA, Verbriefung und Marktrisiko ergeben jeweils null.

## Formelversionierung und harte Abnahmekriterien

## Formel- und Ergebnisversionierung

Jede vorstehende Formel erhält eine `formula_definition`:

| Feld | Inhalt |
|---|---|
| `formula_id` | stabile fachliche ID, z. B. `IRB_CORP_K` |
| `formula_version` | monotone Version |
| `expression_language` | `PYTHON_LIKE_DECIMAL` |
| `expression` | kanonischer Ausdruck |
| `input_contract` | Feld, Typ, Einheit, Nullability, Wertebereich |
| `output_contract` | Ergebnisfeld, Typ, Einheit |
| `effective_from/to` | fachliche Gültigkeit |
| `known_from/to` | Kenntniszeit |
| `rule_set_id`, `provision_id` | Rechtsbindung |
| `rounding_rule` | nur Output-Rundung |
| `is_official` | Default `true`, historisierte Designation |

```python
calculation_result.formula_version_id = selected_formula_version.record_id
calculation_result.input_hash = hash(all_ordered_input_record_ids_and_values)
calculation_result.result_hash = hash(canonical_result)
```

Damit ist nicht nur der Datenstand, sondern auch die Rechenlogik „as known then“ reproduzierbar.

## Harte Validierungen und Abnahmekriterien

```python
assert exactly_one_official_version_per_business_key_as_of_date()
assert all_results_link_to_rule_formula_parameter_and_input_versions()
assert no_missing_currency_or_unit()
assert no_CRM_double_allocation()
assert exactly_one_primary_exposure_class_and_approach_per_exposure()
assert 0 <= PD <= 1 and 0 <= LGD <= 1 and CCF >= 0
assert 0 <= A < D <= 1
assert correlation_matrices_are_valid()
assert output_floor_identity_holds()
assert capital_stack_quality_constraints_hold()
assert no_P2R_or_EC_RWA_equivalent_double_count()
assert official_2026_market_run_uses_legacy_regime()
assert EU_operational_risk_does_not_apply_ILM()
```

Ein fehlender Pflichtinput führt zu `REJECTED` oder zu einer ausdrücklich genehmigten, versionierten Fallbackregel. Stilles Nullsetzen, Verwendung der jüngsten statt stichtagsgültigen Version und nachträgliches Überschreiben eines offiziellen Ergebnisses sind unzulässig.

## Primäre lokale Rechtsgrundlagen

- CRR in der konsolidierten Fassung vom 26. Juni 2026: insbesondere Artikel 92, 111–134, 151–166, 223–230, 248–269, 274–282, 305–310, 312–319, 325 ff., 378–386 und 465.
- CRD in der konsolidierten Fassung vom 11. Juli 2026: insbesondere Artikel 73, 97–104b und 128–142.
- Delegierte Verordnungen (EU) 2024/856 und 2024/857 für IRRBB-SOT und Standardmethode.
- Delegierte Verordnung (EU) 2025/1496 für den FRTB-Aufschub.
- EBA/GL/2022/03 SREP, EBA/GL/2022/14 IRRBB/CSRBB, ECB Guide to ICAAP.
- Die in `docs/REGULATORY_SOURCES.md` aufgeführten Level-2-Rechtsakte für IRB, CRM, SA-CCR, FRTB, OpRisk, Verbriefung und prudent valuation.

Bei späteren Stichtagen muss vor einem offiziellen Lauf ein neuer `rule_set` erzeugt werden; die Formeln dieses Dokuments werden nicht stillschweigend auf einen neuen Rechtsstand fortgeschrieben.
