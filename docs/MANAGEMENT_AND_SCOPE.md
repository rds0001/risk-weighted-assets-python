# 1. Management Summary, Zielbild und Geltungsbereich

## Zweck des Dokuments

Diese Gesamtdokumentation beschreibt die fachliche, mathematische, technische
und operative Ausgestaltung der RWA-Gesamtlösung. Sie ist zugleich
Methodenhandbuch, Datenkatalog, Betriebsanleitung und nachvollziehbare
Entwicklungsakte. Adressaten sind Marktfolge, Risikocontrolling, Meldewesen,
Finanzen, ICAAP-Verantwortliche, interne Revision, Modellvalidierung,
IT-Betrieb und externe Prüfer.

Die Lösung berechnet in einem reproduzierbaren Lauf die Säule-1-Risikopositionen
und TREA, den regulatorischen Kapital-Stack, IRRBB/CSRBB in periodischer und
barwertiger Perspektive sowie ICAAP- und RWA-Äquivalenzsichten. Input und
Output bleiben bewusst Excel-basiert. Die Python-Engine bildet die
deterministische Rechen-, Validierungs- und Orchestrierungsschicht; die lokale
Browser-App dient als schlanke Bedien- und Ergebnissicht.

## Leistungsumfang

- Kreditrisiko-Standardansatz einschließlich EAD, CCF, CRM,
  Immobiliensplitting, ETV/LTV und KSA-Shadow-Rechnung.
- IRB-Ansätze mit PD, LGD, Laufzeit, Korrelation, Maturity Adjustment,
  Input-Floors, Expected Loss und Shortfall/Excess.
- SA-CCR, SFT, CCP, CVA, Settlement, Free Delivery und
  Großkreditüberschreitungen.
- Verbriefungen nach SEC-IRBA, SEC-SA und SEC-ERBA einschließlich SSFA,
  Seniorität, STS, NPE und Wiederverbriefung.
- Marktrisiko im für 2026 anwendbaren Regime sowie FRTB-SA und FRTB-IMA als
  getrennte fully-loaded beziehungsweise genehmigungsabhängige Sicht.
- Operationelles Risiko nach EU-CRR-III-BIC/SMA-Logik.
- U-TREA, S-TREA, transitional und fully-loaded Output Floor.
- CET1, AT1, T2, P2R, Kapitalpuffer, P2G, Leverage, MREL und TLAC.
- IRRBB-EVE, sechs Standardzinsschocks, NII/EaR, VaR, Expected Shortfall,
  Mehrwährungsaggregation und CSRBB.
- ICAAP-Risikotaxonomie, normative Projektion, ökonomisches Kapital,
  Diversifikation, Risikodeckungsmasse und Double-Count-Kontrollen.

## Verbindliche Sichten

Die rechtliche Säule-1-Sicht, aufsichtliche Säule-2-Anforderungen und interne
ökonomische Steuerung werden getrennt gehalten. Ein P2R- oder
IRRBB-RWA-Äquivalent ist eine Übersetzung eines Kapitalbetrags in eine
8-%-Bezugsgröße. Es ist kein zusätzliches legales TREA. Die Engine kontrolliert,
dass Kapitalbetrag und zugehöriges RWA-Äquivalent nicht doppelt aggregiert
werden.

## Referenzstand und Nachweis

Der dokumentierte Referenzstichtag ist der 31. August 2026, der
Dokumentationsstand der 1. September 2026. Das Universalbankprofil und das
KSA-Profil verwenden dieselbe Engine. Die finale Testsuite umfasst 44 Tests.
Beide Referenzläufe erreichen 12 von 12 Reconciliation-Kontrollen ohne
Validierungsfehler; beim KSA-Profil werden leere, nicht anwendbare Module als
transparente Warnungen ausgewiesen.

## Abgrenzung und Freigabe

Die Anwendung ist eine produktionsnahe Referenzimplementierung, aber ohne
institutsindividuelle fachliche Freigabe keine aufsichtsrechtliche
Meldesoftware. Rechtsstand, nationale Optionen, SREP-Bescheid,
Modellgenehmigungen, Waiver, MREL-Entscheidung, bankeigene Mappings und
Verhaltensmodelle müssen vor einem offiziellen Einsatz durch die zuständigen
Funktionen freigegeben werden. Der Official-Status ist eine kontrollierte
Designation pro Stichtag und Version, kein Ersatz für das Vier-Augen-Prinzip.

## End-to-End-Verarbeitung

```text
Versionierten Datensatz auswählen
→ 16 Excel-Workbooks laden
→ Schema, Referenzen, Wertebereiche und Rechtsquellen validieren
→ bitemporalen Official-Snapshot selektieren
→ sämtliche Fachmodule berechnen
→ U-/S-TREA und Output Floor aggregieren
→ Kapital-, IRRBB- und ICAAP-Sichten erzeugen
→ Reconciliations und Lineage prüfen
→ sechs Output-Workbooks und Run-Manifest schreiben
```
