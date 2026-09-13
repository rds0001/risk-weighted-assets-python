# 5. Fachliches Datenmodell, Historisierung und Versionierung

## Zielsetzung

Das kanonische Modell trennt Bankbezeichnungen von regulatorischer Semantik.
Bankeigene Produkte, Konten und Ratings werden über Mappings übersetzt. Jede
fachliche Tabelle verwendet gemeinsame bitemporale Metadaten. Damit können
historische Stichtage reproduziert, nachträgliche Erkenntnisse getrennt und
mehrere Versionen desselben Geschäfts ohne Überschreibung geführt werden.

Der `is_official`-Status ist standardmäßig aktiv, kann aber durch eine
versionierte Official-Designation gezielt auf einen freigegebenen Datensatz
gelenkt werden. Ergebnisse erhalten zusätzlich Lauf-ID, Engine-Version,
Regelsatz, Sicht und Calculation Fingerprint.

**Stand:** 31. August 2026  
**Charakter:** logisches, technologieunabhängiges Fachmodell; keine Datenbank- oder Softwarearchitektur.

## Modellierungsgrundsätze

### Atomarität

Jeder Wert wird auf der niedrigsten fachlich verursachenden Ebene gespeichert. Beispiele sind einzelne Ziehung, Sicherheitenallokation, Derivatetransaktion, Cashflow, Risikofaktor-Sensitivität, operationelles Verlustereignis und Kapitalinstrument. Aggregationen sind reproduzierbare Ergebnisobjekte und keine Überschreibung atomarer Werte.

### Keine Überschreibung

Fachliche Datensätze sind append-only. Eine Korrektur erzeugt eine neue Version mit Verweis auf die ersetzte Version. Gelöschte oder stornierte Sachverhalte werden durch Statusversionen beendet, nicht physisch entfernt.

### Drei Zeitachsen

Jeder versionierte Datensatz verwendet mindestens:

| Feld | Bedeutung |
|---|---|
| `as_of_date` | Bewertungs-/Meldestichtag, für den der Wert gilt |
| `valid_from`, `valid_to` | fachlicher Gültigkeitszeitraum des Sachverhalts |
| `known_from`, `known_to` | technischer Kenntniszeitraum im System |

Damit sind sowohl rückwirkende Korrekturen als auch „Was wusste man damals?“-Reproduktionen möglich. `valid_to` und `known_to` sind halboffene Intervallenden; `NULL` bedeutet offen.

Zusätzliche fachliche Daten – etwa Handelstag, Valuta, Ausfalltag, Veröffentlichungsdatum oder Inkrafttreten – werden nicht durch `as_of_date` ersetzt.

### Version und Official-Designation

Jeder fachliche Datensatz enthält:

| Feld | Regel |
|---|---|
| `record_id` | global eindeutige unveränderliche Versions-ID |
| `business_key` | stabiler fachlicher Schlüssel über alle Versionen |
| `version_no` | monoton je `business_key` |
| `supersedes_record_id` | direkte Vorgängerversion, falls Korrektur |
| `is_official` | gewünschtes Flag je `as_of_date`; Default `true` |
| `record_status` | `ACTIVE`, `CORRECTED`, `SUPERSEDED`, `CANCELLED`, `PROVISIONAL`, `SIMULATED` |

Ein Boolean allein wäre nicht revisionssicher, weil eine spätere offizielle Korrektur das bisherige Flag verändern müsste. Deshalb gibt es zusätzlich `official_designation`:

| Feld | Bedeutung |
|---|---|
| `object_type` | Typ des bezeichneten Objekts |
| `business_key` | fachlicher Schlüssel |
| `as_of_date` | Datum, für das die Version offiziell ist |
| `designated_record_id` | offiziell ausgewählte Version |
| `designation_reason` | Erstmeldung, Korrektur, Abschluss, Aufsichtsanweisung usw. |
| `known_from`, `known_to` | Historie der offiziellen Designation |
| `approved_by`, `approved_at` | Freigabe |

In einer aktuellen Nutzersicht wird `is_official = true` genau für die aktuell designierte Version ausgegeben. Beim ersten Import gilt die eingehende Version standardmäßig als offiziell, sofern sie nicht ausdrücklich als Simulation, Entwurf oder vorläufig markiert ist. Pro Kombination aus `object_type`, `business_key`, `as_of_date` und Kenntniszeitpunkt darf höchstens eine offizielle Version existieren.

### Gemeinsame Metadaten

Alle Stamm-, Bewegungs-, Parameter- und Ergebnisobjekte führen:

- `legal_entity_id`, soweit zurechenbar;
- `consolidation_scope_id` und `calculation_scope` (`SOLO`, `SUB_CONSOLIDATED`, `CONSOLIDATED`);
- `source_system_id`, `source_record_id`, `ingestion_batch_id`;
- `rule_set_id`, `model_version_id`, `parameter_set_id`, soweit verwendet;
- `scenario_id`, wobei `BASE_ACTUAL` der offizielle Ist-Sachverhalt ist;
- `currency`, `unit`, `scale` für numerische Werte;
- `quality_status`, `validation_status`, `approval_status`;
- `lineage_hash` sowie Erstellungs-/Freigabeinformationen.

## Rechts-, Regel- und Parametermodell

### `legal_source`

Rechtsakt oder Aufsichtsquelle mit `source_id`, CELEX/EBA-/BaFin-Kennung, Titel, Normtyp, Jurisdiktion, Normhierarchie, Veröffentlichungsdatum, Inkrafttreten, Anwendungsbeginn/-ende, amtlicher URL, lokaler Dateireferenz und Prüfsumme.

### `legal_provision`

Atomare Regelstelle mit `provision_id`, `source_id`, Artikel/Absatz/Buchstabe/Textziffer, Regelgegenstand, Anwendungsbedingungen und Verweis auf ersetzte Vorgängerregel.

### `rule_set`

Versionierter Rechenrechtsstand:

- `rule_set_id`, Name und Jurisdiktion;
- `calculation_type` (`APPLIED`, `FULLY_LOADED`, `STRESS`, `MANAGEMENT`);
- `effective_from/to`, `known_from/to`;
- CRR-/CRD-/nationaler Stichtag;
- FRTB-Regime, Output-Floor-Phase und Übergangsoptionen;
- Liste der verwendeten `legal_provision_id`;
- Status und Official-Designation.

### `regulatory_parameter`

Einheitliches Long-Format für Risikogewichte, CCF, Floors, Haircuts, Korrelationen, Schocks, Bucket-Grenzen, Kapitalquoten und Übergangssätze:

- `parameter_key`, `parameter_value`, Datentyp, Einheit;
- Dimensionen wie Risikoklasse, Bonitätsstufe, Laufzeitband, Währung, Produkt, Bucket;
- `rule_set_id`, `provision_id`, Gültigkeits-/Kenntniszeit;
- Official-Designation und Freigabestatus.

Regelparameter dürfen nicht hart im Geschäft gespeichert werden. Ein Ergebnis hält die tatsächlich verwendete Parameterversion über `calculation_input_link` fest.

## Organisations-, Konsolidierungs- und Gegenparteimodell

### `legal_entity`

Juristische Einheiten mit LEI, Sitz, Institutsart, Lizenz, SI/LSI/G-SII/O-SII-Status, Rechnungslegungsstandard, Melde- und Basiswährung.

### `consolidation_scope` und `scope_membership`

Versionierte Berechnungskreise. Mitgliedschaften enthalten Konsolidierungsmethode, Beteiligungsquote, aufsichtsrechtliche Behandlung, Minderheitenanteile, Waiver und Eliminierungskennzeichen.

### `party`

Schuldner, Kontrahent, Emittent, Sicherungsgeber, Einleger oder Dienstleister mit Rechtsform, Land, Sektor, Größenmerkmalen, Umsatz/Bilanzsumme und regulatorischem Gegenparteityp.

### `connected_client_group` und `group_membership`

Historisierte Gruppen verbundener Kunden mit Kontroll-/wirtschaftlicher Abhängigkeit, Gültigkeit und Begründung.

### `external_assessment`

ECAI-/Exportkreditbeurteilungen mit Agentur, Skala, Rating, Long-/Short-Term, Issue-/Issuer-Bezug, Bonitätsstufe, Veröffentlichungs-/Gültigkeitszeit und Nominated-Flag.

## Vertrags-, Positions- und Bilanzmodell

### `product_contract`

Vertraglicher Rahmen mit Produkttyp, Gegenparteien, Abschluss-, Start-, Fälligkeits- und Kündigungsdaten, Währung, Accounting Book, Regulatory Book, Zins-/Gebührenbedingungen, eingebetteten Optionen und Rechtsordnung.

### `facility`

Kreditlinie/Zusage mit Limit, zugesagtem und kündbarem Anteil, Unterklasse nach Anhang I, CCF-Kategorie, Kündigungsrechten und Zweckerfassung.

### `exposure_lot`

Atomarer bilanzieller oder außerbilanzieller Risikoposten:

- `exposure_id`, Vertrag/Fazilität/Ziehung;
- Schuldner, wirtschaftlicher Träger, Emittent und Gegenpartei;
- Bruttobuchwert vor Kreditrisikoanpassungen, Nettobuchwert nach Artikel 111, Nominalwert, Marktwert, aufgelaufene Zinsen und Kennzeichen des verwendeten EAD-Datenpfads;
- spezifische/allgemeine Kreditrisikoanpassung, Teilabschreibung, prudent valuation, sonstiger Eigenmittelabzug;
- Bilanz-/außerbilanzielles Kennzeichen und Anhang-I-Unterklasse;
- Accounting Classification, Stage, NPE/Forborne/Default;
- Buch, Portfolio, Land, Sektor, Produkt und Währung;
- Restlaufzeit, Ursprungslaufzeit und Seniorität.

### `accounting_measure`

Long-Format für GuV-, Bilanz- und Kapitalwerte mit Kontenplan, IFRS/HGB-Kategorie, Betrag, Währung, Konsolidierungseliminierung und FINREP-Zuordnung.

### `cashflow`

Vertraglicher oder modellierter Cashflow:

- Vertrag/Position, Cashflow-Typ, Zahlungsdatum und Repricing-Datum;
- Kapital, Zins, Gebühr, Marge und Optionskomponente;
- Währung, Betrag, Vorzeichen und Kurvenzuordnung;
- `cashflow_nature` (`CONTRACTUAL`, `BEHAVIOURAL`, `NEW_BUSINESS`, `HEDGE`);
- Modell-/Szenario-/Versionsreferenz und Wahrscheinlichkeit.

## Kreditrisikominderung

### `collateral_asset`

Sicherheit mit Typ, Eigentümer, Rang, Währung, Markt-/Beleihungswert, Bewertungsdatum/-methode, Liquidierbarkeit, Haircut-Klasse, Immobilienart, Energie-/ESG-Merkmalen, Standort und Versicherungsstatus.

### `property_valuation`

Unveränderliche Immobilienbewertung mit Markt-/Beleihungswert, nachhaltigem Wert, Gutachter, Bewertungsmethode, Indexierung, Fertigstellungsstatus, Einkommenserzeugung und unabhängiger Prüfung.

### `unfunded_protection`

Garantie/Kreditderivat mit Sicherungsgeber, geschütztem Betrag, Währung, Laufzeit, Rang, Trigger, Unwiderruflichkeit, direktem Anspruch und Eligibility.

### `protection_allocation`

Many-to-many-Allokation zwischen Exposures und Sicherheiten/Protection:

- allokierter Nominal-/Marktwert;
- Senioritäts-/Wasserfallrang;
- Währungs- und Laufzeitinkongruenz;
- verwendeter Haircut und nach CRM anrechenbarer Betrag;
- Ansatz (`SIMPLE`, `COMPREHENSIVE`, `SUBSTITUTION`, `DOUBLE_DEFAULT`);
- Eindeutigkeitsregel gegen Mehrfachbelegung.

## KSA-Datenmodell

### `sa_classification`

Je `exposure_id` und Stichtag:

- CRR-Risikopositionsklasse und Unterklasse;
- Gegenparteistatus, Bonitätsstufe und Ratingquelle;
- Due-Diligence-Override;
- ursprüngliche/Restlaufzeit;
- Retail-Kriterien, Granularität und natürliche Person/KMU;
- Transactor-/Revolverstatus;
- Default-/NPE-Status und Deckungsquote;
- Seniorität, Covered-Bond-, CIU-, Equity-, ADC- und Spezialfinanzierungsmerkmale;
- ausgewählte Risikogewichtsregel und Begründung.

### `real_estate_exposure`

Objekt-/Finanzierungsmerkmale:

- Wohn-/Gewerbeimmobilie, fertig/unfertig, ADC;
- IPRE/Non-IPRE und wesentliche Abhängigkeit vom Objekt-Cashflow;
- Exposure-to-Value-Zähler, vorsichtiger Immobilienwert und vorrangige Pfandrechte;
- LTV/ETV, LTV-Band und Loan-Splitting-Segment;
- Währungsinkongruenz, Erstwohnsitz, Anzahl Objekte/Einheiten;
- Eligibility nach Art. 124/125/126/126a.

### `sa_result`

Je atomarem Segment: EAD vor/nach CRM, CCF, Risikogewicht, RWEA vor/nach KMU-/Infrastruktur-Unterstützungsfaktor, Faktorart/-wert, angewandte Rule-/Parameter-Version und Aggregationsdimensionen.

### `crypto_exposure`

Kryptowert, Token-/DLT-Kennung, MiCA-Status, Emittent, Referenzvermögen, Abhängigkeit von anderen Kryptowerten, regulatorische Übergangsklasse, Markt-/Buchwert, Long-/Short, Verwahrung, Hedging-Beziehung, 1-%-Tier-1-Limitrelevanz und Ergebnis der Limitprüfung.

## IRB-Datenmodell

### `rating_assignment`

Obligor-/Facility-Rating mit Rating-System, Grade/Pool, Ratingdatum, Reviewdatum, PD, Defaultstatus, Override und Genehmigungsbereich.

### `irb_parameter`

Je Exposure/Pool:

- Ansatz `FIRB`, `AIRB`, `SLOTTING`;
- regulatorische und geschätzte PD, LGD, CCF/EAD, M;
- Downturn-/Default-LGD, ELBE;
- Input Floor vor/nach Floor, Margin of Conservatism;
- Korrelation R, Maturity-Faktor b, SME-Größe S;
- Garantie-/Double-Default-Parameter;
- Parameterschätzung, Kalibrierungssegment, Modellversion und Genehmigungs-ID.

### `irb_result`

K, RW, RWEA, EL-Satz, EL-Betrag, Wertberichtigung, EL-Shortfall/Excess und CET1/T2-Wirkung je Position/Pool.

## Gegenparteiausfallrisiko und CCP

### `netting_agreement` und `netting_set`

Rechtliche Netting-Vereinbarung, Jurisdiktion, Legal Opinion, Gegenpartei, Produktumfang, Margin Agreement, Schwellen/MTA, Margin Period of Risk und Netting-Eligibility.

### `derivative_trade`

Trade-ID, Produkt, Underlying/Risikotreiber, Long/Short, Nominal, Marktwert, Start/Ende, Zahlungsfrequenz, Optionstyp, Strike, Preis, Volatilität, Besicherung, Clearingstatus und CCP/Client-Clearing-Rolle.

### `sft_trade`

Repo/Securities Lending/Margin Lending mit Cash-/Wertpapierleg, Haircut, Fälligkeit, täglichem Margining und Master Agreement.

### `margin_collateral`

Variation/Initial Margin, unabhängig/separiert, Wert, Währung, Haircut, Gegenpartei/CCP und Wiederverwendbarkeit.

### `sa_ccr_risk_position`

Je Trade/Risikokategorie: primärer Risikotreiber, Hedging Set, Supervisory Delta, Adjusted Notional, Maturity Factor und Supervisory Factor.

### `ccr_result`

Je Netting Set: V, C, NICA, TH, MTA, RC, Add-on je Risikokategorie, PFE-Multiplier, PFE, Alpha, EAD und nachgelagertes KSA-/IRB-RWEA.

### `ccp_exposure`

QCCP/NQCCP, Trade Exposure, Default-Fund-Beitrag, hypothetisches CCP-Kapital, prefunded/unfunded Contribution, Clearing-Member-/Client-Struktur und Ergebnis.

## Verbriefungsmodell

### `securitisation_transaction`

Traditionell/synthetisch, Originator/Sponsor/Investor, STS, SRT, Pool, Tranchierungs-/Wasserfallstruktur, Clean-up Call, Early Amortisation und NPE-Flag.

### `securitisation_pool`

Pool-EAD, KIRB, KSA, W, N, effektive Anzahl Positionen, LGD, Delinquencies, NPE-Anteil, Pooltyp und Datenvollständigkeit.

### `securitisation_tranche`

Attachment A, Detachment D, Seniorität, Nominal/EAD, Rating/Bonitätsstufe, Laufzeit, Tranchendicke, Senior-/Mezzanine-/First-Loss-Kennzeichen.

### `securitisation_result`

Ansatzhierarchieentscheidung, p/KSSFA beziehungsweise SEC-IRBA-Parameter, Tranche-RW, Floors/Caps, RWEA, erwarteter Verlust und Abzugsbehandlung.

## CVA- und Settlement-Modell

### `cva_scope_item`

CCR-Netting Set, regulatorischer/Accounting-CVA, Ausnahmegrund, Hedge-Beziehung, Counterparty Spread, Reference Spread, Rating, Maturity und BA-/SA-CVA-Zuordnung.

### `cva_sensitivity`

Delta/Vega nach Risikofaktor, Bucket, Tenor, Währung, Betrag und Hedge-/Exposure-Kennzeichen.

### `cva_result`

Komponente, Bucket-Kapital, aggregiertes K_CVA, 12,5-Konversion und TREA-Beitrag.

### `settlement_exposure`

Geschäft, vereinbarter/aktueller Settlement-Tag, positive Preisdifferenz, gezahlter/gelieferter Leg, Gegenwert, Geschäftstage Verzug und Free-Delivery-Stufe.

## Marktrisikomodell

### `trading_position`

Instrument, Handelstisch, Trading-/Banking-Book, Fair Value, Nominal, Long/Short, Underlying, Emittent, Seniorität, Rating, Restlaufzeit, Option-/Verbriefungsmerkmale und interne Hedge-Beziehung.

### `market_risk_factor`

Risikoklasse, Bucket, Kurve/Name/Commodity, Tenor, Währung, Basis-/Inflationskennzeichen, Modellierbarkeit und Liquiditätshorizont.

### `market_sensitivity`

Position, Risikofaktor, Delta/Vega/Curvature-Szenarioverlust, Berechnungsschritt, Preisquelle und Validierung.

### `frtb_sa_result`

Weighted Sensitivity, Bucket-Sb/Kb, Szenario low/medium/high, Delta-/Vega-/Curvature-Kapital, DRC, RRAO und Gesamt-SA-Kapital.

### `frtb_ima_result`

Handelstisch, modellierbare/nicht modellierbare Risikofaktoren, ES je Liquiditätshorizont, Reduced-Factor-Set, Stressskalierung, NMRF-SSR, DRC, Backtesting-Ausnahmen, PLA-Zone, Multiplikator und IMA-Kapital.

### `legacy_market_result`

Bis FRTB-Anwendung: Positions-, Fremdwährungs-, Warenpositions-, Options- und interne-Modell-Anforderung nach der am 08.07.2024 geltenden CRR-Fassung.

## Operationelles Risiko

### `business_indicator_item`

Rechnungslegungsposten je Jahr, BI-Komponente, positiver/negativer Betrag, Absolut-/Netting-Regel, M&A-/Disposal-Anpassung und geprüfte Kontenzuordnung.

### `operational_loss_event`

Ereignis, Entdeckungs-/Eintritts-/Buchungsdatum, Bruttoverlust, Recovery, Versicherung, Nettverlust, Ereignistyp, Geschäftslinie, Prozess, Ursache, Schwellenrelevanz und verbundene Ereignisgruppe.

### `operational_risk_result`

ILDC, SC, FC, BI, marginale Bucket-Anteile, BIC, Eigenmittelanforderung und RWA-Äquivalent. Verlustdaten wirken in der EU nicht als ILM-Multiplikator.

## Eigenmittel, Abzüge und Kapitalinstrumente

### `capital_instrument`

Instrument, Emittent, Investor, CET1/AT1/T2-Klasse, Nominal/Buchwert, Ausgabe/Fälligkeit, Call, Coupon, Rang, Loss-Absorption, Grandfathering und regulatorische Eligibility.

### `own_funds_component`

Long-Format für positives Element, prudentiellen Filter, Abzug, Schwellenwertbehandlung oder Minderheitenanteil mit Kapitalart, Brutto-/anrechenbarem Betrag und Rechtsregel.

### `valuation_adjustment`

Bewertungsposition/Portfolio, Fair Value, CET1-Wirkungsanteil, vereinfachter/Kern-/Fallback-Ansatz, AVA-Kategorie, 90-%-Konfidenz- beziehungsweise Exit-Price-Inputs, Diversifikations-/Aggregationsschritt, kategorieweiser AVA-Betrag und CET1-Abzug. Der Datensatz referenziert Markt-, Bewertungsmodell-, Parameter- und RTS-Version.

### `npe_coverage_result`

Notleidende Position, NPE-Einstufungsdatum, prudenzielle Jahresklasse, besicherter/unbesicherter Teil, Sicherheitenart, Grundfaktor, Forbearance-/Garantie-/Exportagentur-Override, erforderliche Deckung, anrechenbare Einzelkomponenten, Unterdeckung und CET1-Abzug.

### `capital_requirement`

Anforderungsart (`P1_CET1`, `P1_T1`, `P1_TOTAL`, `P2R`, `CCB`, `CCYB`, `GSII`, `OSII`, `SYRB`, `P2G`, `LR_P2R`, `LR_P2G`, `MREL`, `TLAC`), Quote/Betrag, Bemessungsgrundlage, Kapitalqualitätsanteile, Behörde, Bescheid und Gültigkeit.

### `capital_stack_result`

Verfügbare CET1/T1/Total/Eligible Liabilities, Soll je Stufe, Headroom, bindende Restriktion, MDA-Schwelle und Managementpuffer.

## Output Floor und TREA-Aggregation

### `risk_measure_result`

Generisches, additives Ergebnisobjekt:

- Risikoart, Teilkomponente, Ansatz und Measure (`EAD`, `RWEA`, `K`, `EL`, `EVE`, `NII`, `EC`);
- atomare Ursache oder Aggregationsknoten;
- Betrag, Währung, Einheit;
- Pre-/Post-CRM, Pre-/Post-Floor, U-TREA/S-TREA-Kennzeichen;
- Rule-/Model-/Parameter-/Scenario-Version;
- Official-Designation.

### `trea_result`

U-TREA-Komponenten a–g, S-TREA-Komponenten a–g, Output-Floor-Faktor, Floor-Basis, Floor-Aufschlag und finaler TREA.

### `floor_allocation`

Management-Allokation des Floor-Aufschlags auf Risikoart, Portfolio, Einheit oder Position mit Methode, Treiber, Allokationsgewicht und vollständiger Summengleichheit. Sie ist keine zusätzliche regulatorische Risikoart.

## IRRBB/CSRBB

### `interest_rate_term`

Index, Fix-/Float, Coupon/Marge, nächstes Repricing, Reset-Lag, Day Count, Floor/Cap, Kundenoption und Zinsweitergabe.

### `behavioural_assumption`

NMD-Core-Anteil, Repricing-/Laufzeitverteilung, Prepayment, Early Redemption, Drawdown, Pass-through, Beta, Floor-Verhalten und Kalibrierungssegment mit Modellversion.

### `yield_curve` und `curve_point`

Kurvenart, Währung, Bewertungsdatum, Tenor, Zero-/Forward-/Discount Rate, Interpolation, Compounding, Floor, Quelle und Official-Designation.

### `irrbb_scenario`

Baseline oder Parallel Up/Down, Steepener, Flattener, Short Up/Down; Schock je Währung/Tenor, Floor und Aggregationsregel. Interne Szenarien sind als nicht offiziell-regulatorisch zu kennzeichnen.

### `irrbb_result`

Je Cashflow/Position/Währung/Szenario:

- Baseline- und Schock-PV, Delta-EVE;
- Baseline- und Schock-NII, Delta-NII/EaR;
- Laufzeitband-Gap, Duration/PV01 optional;
- EVE-/NII-SOT-Numerator, Tier-1-Denominator und Outlier-Flag;
- CSRBB-Spreadkomponente;
- konstante/dynamische Bilanz und Margenbehandlung.

## ICAAP und ökonomisches Kapital

### `risk_taxonomy`

Offene hierarchische Taxonomie mit Risikoart, Unterrisiko, Säule-1-Abdeckung, Kapitalisierbarkeit, verantwortlicher Einheit und Wesentlichkeitskriterien.

### `materiality_assessment`

Risiko, qualitative/quantitative Indikatoren, Schwellen, Brutto-/Nettorisiko, Säule-1-Unterdeckung, Entscheidung, Begründung und Genehmigung.

### `icaap_scenario`

Baseline/advers/reverse, Horizont, Pfade makroökonomischer und Marktrisikofaktoren, Bilanzannahme, Management Actions und Eintrittswahrscheinlichkeit, soweit verwendet.

### `normative_projection`

Per Jahr/Quartal und Szenario: Bilanz/GuV, Kreditverluste, TREA-Komponenten, Output Floor, Eigenmittel, Kapitalanforderungen, Leverage, MREL/TLAC und Headroom.

### `economic_capital_result`

Risikoart, Verteilung/Quantil, Horizont, Konfidenzniveau, Expected Loss, Unexpected Loss/EC, Stress-Add-on, Modellrisiko-Add-on, Diversifikation und allokiertes EC.

### `risk_bearing_capacity`

Interne Risikodeckungsmasse je Komponente, Bewertungsanpassung, Verfügbarkeit, Fungibilität, Transferierbarkeit und Haircut.

### `rwa_equivalent_result`

Quellkapitalbetrag, Typ (`P2R_EQUIVALENT`, `EC_EQUIVALENT`), Referenzkapitalquote, äquivalenter RWA-Betrag, Aggregationsumfang und Double-Count-Control.

## Szenarien, Modelle und Marktparameter

### `scenario` und `scenario_path`

Szenariotyp, Basisdatum, Horizont, Wahrscheinlichkeit, regulatorisch/intern, Variable, Zeitpunkt und Wert. `BASE_ACTUAL` ist Default für offizielle Ist-Rechnungen.

### `model_registry`

Modell-ID, Zweck, Risikoart, Methodik, Owner, Validierung, Genehmigung, Materialität, Gültigkeit, Trainings-/Kalibrierungsdaten, Limitationen und Aufschläge.

### `market_observation`

Preis, Spread, Volatilität, FX, Index oder makroökonomischer Wert mit Marktdatum/-zeit, Quelle, Bid/Ask/Mid, Qualität und Official-Designation.

## Berechnungslauf, Lineage und Aggregation

### `formula_definition`

Versionierte fachliche Rechenregel mit stabiler `formula_id`, `formula_version`, kanonischem Python-nahem Ausdruck, Input-/Output-Vertrag, Einheit, Wertebereich, Rundungsregel, `rule_set_id`, `provision_id`, fachlicher Gültigkeits- und Kenntniszeit sowie Official-Designation. Eine Ergebniszeile verweist immer auf genau die verwendete Formelversion.

### `calculation_run`

Run-ID, Stichtag, Scope, Rule Set, Szenario, Daten-Cut-off, Official-/Draft-Status, Start/Ende, Freigabe und Reproduktionshash.

### `calculation_input_link`

Verknüpft jedes Ergebnis mit allen verwendeten Input-Versionen, Regelstellen, Parametern, Modellen und Vorresultaten einschließlich Verwendungsrolle.

### `aggregation_node` und `aggregation_edge`

Versionierte Hierarchien für Rechtseinheit, Portfolio, Produkt, Land, Branche, Risikoklasse, Ansatz, Währung, Handelstisch und Laufzeitband. Eine Position kann in mehreren getrennten Hierarchien liegen; jede Hierarchie muss je Stichtag vollständig und überschneidungsfrei sein, sofern keine Mehrfachsicht beabsichtigt ist.

### `aggregation_result`

Speichert Summe, Maximum, Minimum, Quantil, korrelierte Aggregation oder Allokation. `aggregation_method` und `aggregation_formula_id` sind Pflichtfelder. Nichtadditive Größen wie Quoten dürfen nicht summiert werden; Zähler und Nenner werden separat aggregiert und die Quote danach neu berechnet.

### `double_count_control`

Dokumentiert für zwei Ergebnis- oder Risikokomponenten, ob sie denselben Verlusttreiber, Kapitalbetrag oder RWA-Effekt enthalten. Pflichtfelder sind `component_a_id`, `component_b_id`, `overlap_type`, `overlap_amount`, `treatment` (`EXCLUDE_A`, `EXCLUDE_B`, `NET`, `MAX`, `KEEP_BOTH_WITH_JUSTIFICATION`), Genehmigung und Version. Besonders zwingend für P2R/RWA-Äquivalent, EVE/EaR, Kredit-/Konzentrationsrisiko, CSRBB/Kreditspread sowie normative CET1-Verluste/ökonomisches Kapital.

### `reconciliation_result`

Kontrollergebnis mit `left_measure_id`, `right_measure_id`, Formel, Soll-/Ist-Differenz, Toleranz, Status, Ursache, Bearbeitung und Freigabe. Reconciliations sind selbst versionierte, historisierte und offiziell designierbare Ergebnisse.

## Pflichtkontrollen

1. **Temporal:** keine überlappenden aktiven Gültigkeitsintervalle derselben fachlichen Version; genau eine aktuelle Official-Designation je Schlüssel/Stichtag.
2. **Einheit/Währung:** keine Aggregation unterschiedlicher Einheiten ohne explizite Konversion und FX-Version.
3. **Bilanz:** Exposure-Bruttowerte und Anpassungen stimmen zu Accounting/FINREP ab.
4. **CRM:** anrechenbare Sicherheitenallokation überschreitet weder verfügbaren Sicherheitenwert noch Exposure; keine Mehrfachbelegung.
5. **Klassifikation:** je Exposure genau eine primäre regulatorische Risikoklasse und ein Ansatz je Rule Set.
6. **RWEA:** Summe atomarer Ergebnisse entspricht allen Hierarchieaggregaten und COREP.
7. **Kapital:** CET1 ≤ T1 ≤ Total Own Funds; Abzüge und Minderheitenanteile sind eindeutig.
8. **Output Floor:** finaler TREA entspricht dem Maximum aus U-TREA und Floor-Betrag; Floor-Allokation summiert exakt zum Floor-Aufschlag.
9. **IRRBB:** Cashflow-Summen stimmen zu Positionen; Währungsergebnisse und zulässige Aggregation stimmen zum SOT.
10. **Double Count:** P2R, P2G, EC und interne RWA-Äquivalente werden nicht gleichzeitig als Kapitalaufschlag und RWA-Aufschlag verwendet.
11. **Reproduktion:** ein freigegebener Run ist mit seinem Daten-Cut-off, Rule Set und allen Input-Versionen unverändert wiederholbar.
