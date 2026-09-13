# 3. Methodik der Säule 1 und regulatorischer Kapitalbedarf

## Methodischer Rahmen

Die Säule-1-Rechnung ist positionsorientiert. Jede atomare Position wird
zunächst validiert, dann einem Ansatz und einer Risikoklasse zugeordnet, auf
EAD beziehungsweise Kapitalanforderung verdichtet und erst anschließend über
Portfolio, Rechtseinheit, Konsolidierungskreis und Gesamtsicht aggregiert.
Nicht additive Größen wie Quoten, Risikogewichte oder Korrelationen werden nie
ungewichtet summiert. Sämtliche regulatorischen Zahlenwerte stammen aus dem
versionierten Parameter-Workbook; der Code enthält ausschließlich Algorithmen.

Die folgenden Abschnitte dokumentieren die konkrete Python-nahe
Formelspezifikation einschließlich Eingangsgrößen, Floors, Caps,
Ansatzhierarchien und Ergebnisobjekten.

## Verbindliche Rechen- und Versionskonventionen

### Rechtsstand

Für einen offiziellen Lauf ist genau ein `rule_set` auszuwählen. Es bestimmt nicht nur Parameter, sondern auch die anwendbare Methodenfassung. Zum Fachkonzeptstichtag gilt insbesondere:

- CRR-III-Regelwerk einschließlich Output-Floor-Übergangsfaktor `0.55` für 2026;
- EU-OpRisk ist `BIC`, ohne Internal Loss Multiplier;
- die FRTB-Eigenmittelanforderung ist bis 1. Januar 2027 aufgeschoben; der offizielle 2026-Lauf verwendet deshalb das in Artikel 325 CRR bezeichnete Altregime, FRTB wird parallel als zukünftiger/Management-Run gerechnet;
- IRRBB-SOT-Schwellen von 15 % EVE und 5 % NII sind Aufsichtsindikatoren, keine automatische P2R-Formel.

### Bitemporale Official-Selektion

```python
def official_version(object_type, business_key, as_of_date, knowledge_time):
    designations = official_designation.where(
        object_type=object_type,
        business_key=business_key,
        as_of_date=as_of_date,
        known_from__le=knowledge_time,
        known_to__gt_or_null=knowledge_time,
    )
    assert len(designations) == 1
    return record(designations[0].designated_record_id)
```

Beim ersten nicht als `PROVISIONAL` oder `SIMULATED` bezeichneten Import wird `is_official=True` unterstellt. Eine Korrektur überschreibt nicht, sondern erzeugt eine neue Record-Version und eine neue zeitlich gültige `official_designation`.

### Parameterauswahl

```python
def P(key, *, dims, as_of_date, knowledge_time, rule_set_id):
    candidates = regulatory_parameter.where(
        parameter_key=key,
        dimensions=dims,
        rule_set_id=rule_set_id,
        valid_from__le=as_of_date,
        valid_to__gt_or_null=as_of_date,
        known_from__le=knowledge_time,
        known_to__gt_or_null=knowledge_time,
    )
    official = select_current_official(candidates, knowledge_time)
    assert len(official) == 1
    return official[0].parameter_value
```

Kein fachlicher Parameter darf stillschweigend aus einer jüngeren Rechtsfassung gezogen werden. Jeder Ergebnisdatensatz hält über `calculation_input_link` die tatsächlich verwendeten Input-, Rechts-, Modell- und Parameterversionen fest.

### Einheiten, Vorzeichen, Rundung

```python
RATE = decimal_fraction       # 8 % == 0.08
MONEY = reporting_currency
RWEA = MONEY
K = MONEY                     # Eigenmittel-/Kapitalanforderung
YEARS = actual_days / 365.25  # sofern die Spezialregel nichts anderes bestimmt

asset_cashflow     > 0
liability_cashflow < 0
gain               > 0
loss               < 0
```

Intern wird ohne Zwischenrundung gerechnet. Melderundung geschieht nur am Ausgabeobjekt. Jede Aggregation erfolgt zunächst in Originalwährung, dann mit dem offiziell versionierten Stichtags-FX-Kurs.

### Standardfunktionen

```python
def clip(x, lo, hi): return min(max(x, lo), hi)
def positive(x): return max(x, 0.0)
def negative(x): return min(x, 0.0)
def N(x): return standard_normal_cdf(x)
def G(p): return standard_normal_inverse_cdf(p)
def safe_div(a, b): return a / b if b != 0 else controlled_exception
```

### Generisches Ergebnis

Jede nachfolgende Funktion erzeugt mindestens ein `risk_measure_result` mit `source_object_id`, `measure`, `amount`, `unit`, `currency`, `approach`, `component`, `pre_post_crm`, `pre_post_floor`, `rule_set_id`, `parameter_set_id`, `model_version_id`, `scenario_id`, `calculation_run_id`, `as_of_date` und Official-Designation. Aggregationen werden als eigene `aggregation_result` gespeichert; sie ersetzen die atomaren Ergebnisse nicht.

## Gesamtrechenkette

```python
K_credit = K_credit_sa_irb + K_securitisation + K_ccr_ccp
K_market = market_capital_requirement(rule_set.market_regime)
K_settlement = settlement_capital_requirement()
K_cva = cva_capital_requirement()
K_operational = operational_risk_BIC()
K_large_exposure_excess = permitted_large_exposure_excess_charge()

U_TREA = (
    RWEA_credit_non_trading
    + RWEA_ccr_trading
    + 12.5 * (
        K_market
        + K_large_exposure_excess
        + K_settlement
        + K_cva
        + K_operational
    )
)

S_TREA = same_components_recomputed_without_internal_approaches()
TREA = output_floor(U_TREA, S_TREA, as_of_date, rule_set)
```

`K_credit` dient hier nur als Kontrollsicht (`RWEA / 12.5`); die CRR-Aggregation nutzt für Kreditrisiko direkt RWEA und für die in Artikel 92 Absatz 4 Buchstaben b–f genannten Komponenten `12.5 * K`.

**Datenobjekte:** `risk_measure_result`, `trea_result`, `calculation_run`, `aggregation_node`, `aggregation_edge`, `aggregation_result`, `calculation_input_link`.

## Kreditrisiko-Standardansatz (KSA)

### Positionswert und CCF

```python
EAD_on = max(
    gross_carrying_amount_before_credit_risk_adjustments
    - specific_credit_risk_adjustments
    - additional_valuation_adjustments
    - other_own_funds_reductions,
    0.0,
)

CCF = {
    "ANNEX_I_CLASS_1": 1.00,
    "ANNEX_I_CLASS_2": 0.50,
    "ANNEX_I_CLASS_3": 0.40,
    "ANNEX_I_CLASS_4": 0.20,
    "ANNEX_I_CLASS_5": 0.10,
}[annex_i_class]

available_undrawn = min(committed_undrawn, contractual_availability_limit)
EAD_off = max(available_undrawn - specific_credit_risk_adjustments, 0.0) * CCF
EAD_pre_CRM = EAD_on + EAD_off
```

`gross_carrying_amount_before_credit_risk_adjustments` ist hier ausdrücklich der Buchwert **vor** den in der Formel abgezogenen Größen. Wird aus einem Quellsystem bereits der verbleibende Nettobuchwert nach Artikel 111 angeliefert, gilt stattdessen `EAD_on = max(net_carrying_amount_article_111, 0.0)`; beide Datenpfade dürfen nie gleichzeitig abziehen.

Bei einer Zusage für einen anderen außerbilanziellen Posten wird der niedrigere der beiden einschlägigen CCF verwendet. Die gesetzlich ausdrücklich mit 0 % behandelten vertraglichen Vereinbarungen werden als eigene `annex_i_subclass` parametrisiert, nicht als manuelle Nullsetzung.

### Allgemeine Risikogewichtszuordnung

```python
RW = sa_risk_weight(
    exposure_class=sa_classification.exposure_class,
    subclass=sa_classification.subclass,
    cqs=external_assessment.credit_quality_step,
    maturity=exposure_lot.residual_maturity,
    counterparty_features=party.regulatory_attributes,
    collateral_features=protection_allocation,
    property_features=real_estate_exposure,
    default_features=sa_classification,
    authority_override=P(
        "SA_RW_OVERRIDE",
        dims=jurisdiction_and_segment,
        as_of_date=as_of_date,
        knowledge_time=knowledge_time,
        rule_set_id=rule_set_id,
    ),
)

RWEA_segment = EAD_post_CRM_segment * RW_segment
RWEA_exposure = sum(s.RWEA_segment for s in exposure.segments)
RWEA_KSA = sum(e.RWEA_exposure for e in KSA_scope)
```

Die wesentlichen Basistabellen lauten:

```python
RW_sovereign_by_CQS    = [0.00, 0.20, 0.50, 1.00, 1.00, 1.50]
RW_corporate_by_CQS    = [0.20, 0.50, 0.75, 1.00, 1.50, 1.50]
RW_institution_rated   = [0.20, 0.30, 0.50, 1.00, 1.00, 1.50]
RW_institution_short   = [0.20, 0.20, 0.20, 0.50, 0.50, 1.50]
RW_MDB_rated           = [0.20, 0.30, 0.50, 1.00, 1.00, 1.50]
RW_short_term_rating   = [0.20, 0.50, 1.00, 1.50, 1.50, 1.50]
RW_covered_bond_rated  = [0.10, 0.20, 0.20, 0.50, 0.50, 1.00]

RW_corporate_unrated = 1.00
RW_retail = 0.75
RW_retail_transactor = 0.45
RW_natural_person_failed_retail_criteria = 1.00
RW_salary_or_pension_assignment_if_eligible = 0.35
RW_subordinated_debt = 1.50
RW_ADC = 1.50
RW_ADC_residential_if_eligible = 1.00
RW_equity_general = 2.50
RW_equity_speculative_unlisted = 4.00
RW_equity_central_bank = 0.00
RW_other_assets = 1.00
RW_cash_or_matching_gold = 0.00
RW_cash_items_in_collection = 0.20
RW_CIU_fallback = 12.50
```

Weitere Gegenparteitabellen:

```python
RW_RGLA_or_PSE_rated = [0.20, 0.50, 0.50, 1.00, 1.00, 1.50][CQS - 1]
RW_RGLA_or_PSE_unrated_by_sovereign_CQS = [0.20, 0.50, 1.00, 1.00, 1.00, 1.50][sovereign_CQS - 1]
RW_MDB_rated = [0.20, 0.30, 0.50, 1.00, 1.00, 1.50][CQS - 1]
RW_MDB_unrated = 0.50
RW_listed_preferred_MDB = 0.00
RW_listed_international_organisation = 0.00

RW_covered_bond_unrated = {
    0.20: 0.10,
    0.30: 0.15,
    0.40: 0.20,
    0.50: 0.25,
    0.75: 0.35,
    1.00: 0.50,
    1.50: 1.00,
}[RW_issuing_institution]
```

Sonderbehandlungen von Zentralstaaten/Zentralbanken in eigener Währung, EU/EZB, anerkannten MDB/internationalen Organisationen und gleichgestellten RGLA/PSE werden nur bei erfülltem Tatbestand auf `0 %` gesetzt. Die Listen sind Rechtsparameter mit eigener Gültigkeitszeit; eine bloße Bezeichnung als „öffentlich“ genügt nicht.

Unbeurteilte Institute werden stufenbasiert gerechnet:

```python
RW_institution_unrated = {
    "A": {"short": 0.20, "general": 0.40},
    "B": {"short": 0.50, "general": 0.75},
    "C": {"short": 1.50, "general": 1.50},
}[institution_grade][term_class]

if institution_grade == "A" and cet1_ratio >= 0.14 and leverage_ratio >= 0.05 and not short:
    RW_institution_unrated = 0.30
```

Spezialfinanzierungen ohne direkt anwendbares ECAI-Rating:

```python
RW_specialised_lending = {
    "OBJECT_FINANCE": 1.00,
    "COMMODITIES_FINANCE": 1.00,
    "PROJECT_PRE_OPERATIONAL": 1.30,
    "PROJECT_OPERATIONAL_HIGH_QUALITY": 0.80,
    "PROJECT_OPERATIONAL_OTHER": 1.00,
}[specialised_lending_type]
```

Ausgefallene unbesicherte Teile:

```python
coverage_ratio = safe_div(
    specific_credit_adjustments + article_36_1_m_deductions,
    unsecured_value_before_these_adjustments,
)
RW_default_unsecured = 1.00 if coverage_ratio >= 0.20 else 1.50
RW_default_non_IPRE_real_estate = 1.00
```

Währungsinkongruenz für natürliche Personen/Mengengeschäft:

```python
if currency_mismatch and hedge_coverage_of_each_instalment < 0.90 and not EUR_ERM2_exemption:
    RW = min(1.5 * RW, 1.50)
```

ECAI-, Exportkredit-, Zentralstaat-, RGLA-, PSE-, MDB-, internationale-Organisation-, Instituts-, Covered-Bond- und CIU-Ausnahmen werden als versionierte Entscheidungsregeln mit genau den vorstehenden beziehungsweise in `regulatory_parameter` gespeicherten vollständigen Tabellen ausgeführt. Ein fehlender Lookup ist ein harter Fehler, kein Default auf 100 %.

CIU-Rechnung:

```python
# Look-through approach
RWEA_CIU_LTA = ownership_share * sum(RWEA_underlying_j for j in underlying_positions)

# Mandate-based approach: Belegung in absteigender Kapitalintensität
remaining_NAV = CIU_NAV
RWEA_CIU_MBA = 0.0
for permitted_class in sorted(mandate_classes, key=worst_case_RW, reverse=True):
    assumed_EAD = min(remaining_NAV, permitted_class.maximum_exposure)
    RWEA_CIU_MBA += assumed_EAD * worst_case_RW(permitted_class)
    remaining_NAV -= assumed_EAD
RWEA_CIU_MBA *= maximum_leverage_factor

# Berechnung durch anerkannten Dritten
RWEA_CIU_third_party = RWEA_CIU_calculated_by_third_party * (1.0 if full_access else 1.20)

RWEA_CIU = min(selected_CIU_RWEA, EAD_CIU * 12.50)
```

Außerbilanzielle CIU-Position:

```python
RW_CIU_off_balance = (RWEA_CIU / EAD_CIU) * (CIU_assets / CIU_equity)
RW_CIU_off_balance = min(RW_CIU_off_balance, 12.50)
RWEA_CIU_off_balance = EAD_off_balance * RW_CIU_off_balance
```

Unterlassene Due Diligence oder nicht anwendbare Transparenz-/Mandatsmethode führt zu `RW=12.50`.

### Immobilien: ETV und Loan Splitting

```python
gross_exposure_for_ETV = (
    gross_carrying_amount_before_credit_risk_adjustments
    + committed_undrawn_that_would_increase_property_exposure
    + equal_or_higher_ranking_third_party_liens_if_subordinate_lien
)
ETV = gross_exposure_for_ETV / prudent_property_value
```

Spezifische Kreditrisikoanpassungen, AVA, Abzüge und andere CRM werden im ETV-Zähler nicht abgezogen. Für das privilegierte Segment eines eigenen Pfandrechts:

```python
base_capacity = max(0.55 * property_value - senior_liens_not_held_by_bank, 0.0)
pari_passu_reduction = max(
    0.55 * property_value - all_senior_liens,
    0.0,
) * safe_div(pari_passu_liens_not_held_by_bank, all_pari_passu_liens)

eligible_55_capacity = max(base_capacity - pari_passu_reduction, 0.0)
preferred_segment = min(EAD_secured_by_lien, eligible_55_capacity)
remainder_segment = EAD_secured_by_lien - preferred_segment
```

Nicht-IPRE-Wohnimmobilie und privilegierte IPRE-Wohnimmobilie:

```python
RWEA_property = preferred_segment * 0.20 + remainder_segment * RW_counterparty_unsecured
```

Nicht-IPRE-Gewerbeimmobilie:

```python
RWEA_property = preferred_segment * 0.60 + remainder_segment * RW_counterparty_unsecured
```

Nicht privilegierte Wohn-IPRE wird als Whole-Loan behandelt:

```python
RW_residential_IPRE = bucket_lookup(
    ETV,
    bounds=[0.50, 0.60, 0.80, 0.90, 1.00, float("inf")],
    values=[0.30, 0.35, 0.45, 0.60, 0.75, 1.05],
)
RWEA_property = EAD_secured_by_lien * RW_residential_IPRE
```

Gewerbe-IPRE:

```python
RW_commercial_IPRE = bucket_lookup(
    ETV,
    bounds=[0.60, 0.80, float("inf")],
    values=[0.70, 0.90, 1.10],
)
RWEA_property = EAD_secured_by_lien * RW_commercial_IPRE
```

Nicht anrechenbare Nicht-IPRE-Teile erhalten das unbesicherte Gegenpartei-RW, nicht anrechenbare IPRE-Teile `1.50`. Behörden-Overrides dürfen RW erhöhen oder ETV-/55-%-Grenzen absenken und werden nach Belegenheitsstaat und Immobiliensegment versioniert.

### Kreditrisikominderung (CRM)

Einfache Methode/Substitution:

```python
protected_EAD = min(EAD, eligible_protection_amount_after_mismatch)
unprotected_EAD = EAD - protected_EAD
RWEA = protected_EAD * RW_protection_provider_or_collateral + unprotected_EAD * RW_obligor
```

Umfassende Methode für Finanzsicherheiten:

```python
E_VA = E * (1.0 + H_E)
C_VAM = C * (1.0 - H_C - H_FX)
E_star = max(E_VA - C_VAM, 0.0)
```

Haircuts werden auf die vorgeschriebene Haltedauer skaliert:

```python
H_T = H_M * sqrt((N_R + T_M - 1) / T_M)
```

mit `N_R` tatsächlichen Geschäftstagen zwischen Neubewertungen und `T_M` der regulatorischen Mindesthaltedauer. Laufzeitinkongruenz:

```python
t = min(protection_residual_maturity_years, exposure_residual_maturity_years)
T = min(exposure_residual_maturity_years, 5.0)
P_a = P * max(t - 0.25, 0.0) / max(T - 0.25, epsilon)
```

Nur gesetzlich anrechenbare Protection wird alloziert. `sum(allocated_protection) <= eligible_protection_value` und `sum(protected_EAD) <= EAD` gelten zwingend.

### Unterstützungsfaktoren und Kryptowerte

Die Faktoren werden erst auf die vollständig berechneten, nicht ausgefallenen RWEA angewandt:

```python
if eligible_SME and not defaulted and not ADC:
    E_star_SME = total_group_exposure_excluding_qualifying_residential_property
    if E_star_SME == 0:
        E_star_SME = qualifying_residential_property_exposure
    SME_factor = (
        min(E_star_SME, 2_500_000) * 0.7619
        + max(E_star_SME - 2_500_000, 0.0) * 0.85
    ) / E_star_SME
    RWEA_after_SME_factor = RWEA_before_supporting_factors * SME_factor

if eligible_infrastructure:
    RWEA_after_infrastructure_factor = RWEA_before_infrastructure_factor * 0.75
```

Zulässigkeit und Reihenfolge mehrerer Faktoren werden als Rechtsregel validiert. Übergangsbehandlung für Kryptowerte bis zum speziellen EU-Rechtsakt:

```python
RW_crypto = {
    "TOKENISED_TRADITIONAL_ASSET": RW_of_represented_traditional_asset,
    "MICA_COMPLIANT_ASSET_REFERENCED_TOKEN": 2.50,
    "OTHER_CRYPTO": 12.50,
}[crypto_class]
RWEA_crypto = exposure_value_crypto * RW_crypto

other_crypto_limit = 0.01 * Tier1
crypto_limit_breach = exposure_value_other_crypto > other_crypto_limit
```

Ein von anderen Kryptowerten abhängiger tokenisierter Vermögenswert fällt in `OTHER_CRYPTO`. Der Limitverstoß wird zusätzlich als Compliance-Ereignis gespeichert.

### KSA-Datenobjekte

`exposure_lot`, `facility`, `party`, `external_assessment`, `sa_classification`, `real_estate_exposure`, `property_valuation`, `collateral_asset`, `unfunded_protection`, `protection_allocation`, `regulatory_parameter`, `sa_result`, `risk_measure_result`.

## Internal Ratings-Based Approach (IRBA)

### Input-Floors

```python
PD = max(PD_estimate, PD_floor)

PD_floor = {
    "SOVEREIGN_RGLA_PSE": 0.0003,
    "CORPORATE_INSTITUTION": 0.0005,
    "RETAIL_QRRE": 0.0010,
    "RETAIL_OTHER": 0.0005,
}[irb_exposure_subclass]

if defaulted:
    PD = 1.0
```

Für garantierte Teile durch anrechenbare Zentralstaaten, Zentralbanken oder EZB gelten die Input-Floors nach Artikel 159a nicht. AIRB-LGD-Floor für teilweise besicherte Non-Retail-Positionen:

```python
LGD_floor = (LGD_U_floor * E_U + LGD_S_floor * E_S) / E

LGD_U_floor = 0.25
LGD_S_floor = {
    "FINANCIAL_COLLATERAL": 0.00,
    "RECEIVABLES": 0.10,
    "RESIDENTIAL_OR_COMMERCIAL_RE": 0.10,
    "OTHER_PHYSICAL": 0.15,
}[collateral_type]
LGD = max(LGD_estimate, LGD_floor)
```

Für Non-Financial-Corporates ohne FCP gilt zusätzlich der 5-%-Floor gemäß Artikel 161 Absatz 5. Retail:

```python
LGD_floor = {
    "RESIDENTIAL_RETAIL": 0.05,
    "QRRE_UNSECURED": 0.50,
    "OTHER_RETAIL_UNSECURED": 0.30,
    "OTHER_RETAIL_FINANCIAL_COLLATERAL": 0.00,
    "OTHER_RETAIL_RECEIVABLES": 0.10,
    "OTHER_RETAIL_RE": 0.10,
    "OTHER_RETAIL_OTHER_PHYSICAL": 0.15,
}[retail_collateral_class]
LGD = max(LGD_estimate, LGD_floor)
```

FIRB-Regelwerte:

```python
LGD_FIRB = {
    "SENIOR_FINANCIAL_SOVEREIGN_RGLA_PSE_UNSECURED": 0.45,
    "SENIOR_NON_FINANCIAL_CORPORATE_UNSECURED": 0.40,
    "SUBORDINATED_UNSECURED": 0.75,
    "ELIGIBLE_COVERED_BOND": 0.1125,
    "PURCHASED_SENIOR_CORPORATE_RECEIVABLE": 0.40,
    "PURCHASED_SUBORDINATED_CORPORATE_RECEIVABLE": 1.00,
    "DILUTION": 1.00,
}[facility_class]
```

CCF-Input-Floor für zulässige eigene CCF bei revolvierenden Zusagen:

```python
EAD_floor = drawn_amount + 0.50 * (undrawn_amount * SA_CCF)
EAD = max(drawn_amount + undrawn_amount * IRB_CCF, EAD_floor)
```

### Laufzeit

```python
M_cashflow = clip(
    sum(t * CF_t for t, CF_t in contractual_cashflows) / sum(CF_t for _, CF_t in contractual_cashflows),
    1.0,
    5.0,
)
```

FIRB verwendet grundsätzlich `M=2.5`, für SFT `M=0.5`, sofern nicht die genehmigte effektive Laufzeitmethode angewandt wird. Spezialuntergrenzen von 5/10/20 Geschäftstagen werden durch `days/365.25` umgesetzt.

### Corporate/Sovereign/Institution-Risikofunktion

```python
def corporate_R(PD, annual_sales_million=None, financial_multiplier=False):
    f = (1.0 - exp(-50.0 * PD)) / (1.0 - exp(-50.0))
    R = 0.12 * f + 0.24 * (1.0 - f)
    if annual_sales_million is not None:
        S = clip(annual_sales_million, 5.0, 50.0)
        R -= 0.04 * (1.0 - (S - 5.0) / 45.0)
    if financial_multiplier:
        R *= 1.25
    return R

def maturity_b(PD):
    return (0.11852 - 0.05478 * log(PD)) ** 2

def maturity_adjustment(PD, M):
    b = maturity_b(PD)
    return (1.0 + (M - 2.5) * b) / (1.0 - 1.5 * b)

def irb_K_non_default(PD, LGD, R, M, apply_MA=True):
    z = G(PD) / sqrt(1.0 - R) + sqrt(R / (1.0 - R)) * G(0.999)
    UL = LGD * N(z) - PD * LGD
    MA = maturity_adjustment(PD, M) if apply_MA else 1.0
    return max(UL * MA, 0.0)

K = irb_K_non_default(PD, LGD, R, M)
RW = 12.5 * K
RWEA = EAD * RW
```

Für `PD==0`, `RW=0`. Für ausgefallene Positionen:

```python
RW_default_FIRB = 0.0
RW_default_AIRB = max(0.0, 12.5 * (LGD - ELBE))
```

### Retail-Risikofunktion

```python
def retail_R(PD, subclass):
    if subclass == "RESIDENTIAL":
        return 0.15
    if subclass == "QRRE":
        return 0.04
    f = (1.0 - exp(-35.0 * PD)) / (1.0 - exp(-35.0))
    return 0.03 * f + 0.16 * (1.0 - f)

R = retail_R(PD, retail_subclass)
K = irb_K_non_default(PD, LGD, R, M=1.0, apply_MA=False)
RW = 12.5 * K
RWEA = EAD * RW
```

### Slotting und erwarteter Verlust

```python
RW_slotting = {
    "LT_2_5Y": [0.50, 0.70, 1.15, 2.50, 0.00],
    "GE_2_5Y": [0.70, 0.90, 1.15, 2.50, 0.00],
}[maturity_band][slotting_category - 1]

EL_rate_slotting = {
    "LT_2_5Y": [0.000, 0.004, 0.028, 0.080, 0.500],
    "GE_2_5Y": [0.004, 0.008, 0.028, 0.080, 0.500],
}[maturity_band][slotting_category - 1]
```

Ansonsten:

```python
EL_rate = ELBE if defaulted and AIRB else PD * LGD
EL_amount = EL_rate * EAD

coverage = general_adjustments + specific_adjustments + eligible_AVA + other_own_funds_reductions
IRB_excess = max(coverage - EL_amount, 0.0)
IRB_shortfall = max(EL_amount - coverage, 0.0)
```

Shortfall wird gemäß Eigenmittelregeln vom CET1 abgezogen; anrechenbarer Excess wird innerhalb der T2-Grenzen behandelt. Verbriefungspositionen werden aus dieser Shortfall-/Excess-Rechnung ausgeschlossen.

### IRB-Datenobjekte

`rating_assignment`, `irb_parameter`, `exposure_lot`, `cashflow`, `protection_allocation`, `model_registry`, `regulatory_parameter`, `irb_result`, `own_funds_component`, `risk_measure_result`.

## Gegenparteiausfallrisiko (CCR), SFT und CCP

### SA-CCR: Netting-Satz

```python
EAD_CCR = alpha * (RC + PFE)
alpha = 1.4

RC_unmargined = max(CMV - NICA, 0.0)
RC_margined = max(CMV - VM - NICA, TH + MTA - NICA, 0.0)
```

Für mehrere Netting-Sätze unter einer Nachschussvereinbarung:

```python
RC = max(
    sum(max(CMV_i, 0.0) for i in sets) - max(VM_MA + NICA_MA, 0.0),
    0.0,
) + max(
    sum(min(CMV_i, 0.0) for i in sets) - min(VM_MA + NICA_MA, 0.0),
    0.0,
)
```

```python
AddOn_total = sum(AddOn[a] for a in risk_categories)
z = CMV - NICA if unmargined else CMV - VM - NICA
y = 2.0 * (1.0 - 0.05) * AddOn_total

multiplier = 1.0 if z >= 0 else min(
    1.0,
    0.05 + 0.95 * exp(z / y),
)
PFE = multiplier * AddOn_total
```

Wenn `AddOn_total==0`, ist `PFE=0`. Der margined EAD wird zusätzlich auf den fiktiven unmargined EAD gedeckelt.

### SA-CCR: Transaktionsrisikoposition

```python
supervisory_duration = (exp(-0.05 * S) - exp(-0.05 * E)) / 0.05

AdjNot_IR_or_credit = contractual_notional * supervisory_duration
AdjNot_FX = selected_payment_leg_notional_in_reporting_currency
AdjNot_equity_or_commodity = spot_price * number_of_units

MF_unmargined = sqrt(min(max(M, 10 / business_days_per_year), 1.0))
MF_margined = 1.5 * sqrt(MPOR / business_days_per_year)
position = supervisory_delta * AdjNot * MF
```

Optionen außerhalb der besonderen IR-/Commodity-RTS-Formel:

```python
d = (log(P / K) + 0.5 * sigma**2 * T) / (sigma * sqrt(T))
supervisory_delta = sign * N(option_type * d)

sign = -1 if sold_call_or_bought_put else 1
option_type = -1 if put else 1
```

Synthetische Tranche/n-th-to-default:

```python
supervisory_delta = sign * 15.0 / ((1.0 + 14.0 * A) * (1.0 + 14.0 * D))
sign = 1 if protection_bought else -1
```

Lineare Geschäfte verwenden `+1` für Long und `-1` für Short im primären Risikotreiber.

### SA-CCR: Add-ons

```python
# Zinsrisiko, je Währung/Hedging-Set
D1 = sum(position_l for l in maturity_bucket_0_to_1y)
D2 = sum(position_l for l in maturity_bucket_1_to_5y)
D3 = sum(position_l for l in maturity_bucket_over_5y)
EffNot_IR = sqrt(D1**2 + D2**2 + D3**2 + 1.4*D1*D2 + 1.4*D2*D3 + 0.6*D1*D3)
AddOn_IR_j = epsilon_j * 0.005 * EffNot_IR
AddOn_IR = sum(AddOn_IR_j)

# FX, je Währungspaar
EffNot_FX_j = sum(position_l for l in fx_hedging_set_j)
AddOn_FX = sum(epsilon_j * 0.04 * abs(EffNot_FX_j) for j in fx_hedging_sets)

# Sonstige Risiken
AddOn_other = sum(epsilon_j * 0.08 * abs(sum(position_l for l in set_j)) for j in sets)
```

Kredit, Aktien und Waren werden mit identischer Einzelfaktor-/Systematik-Aggregation gerechnet:

```python
entity_addon_k = supervisory_factor_k * sum(position_l for l in entity_k)
hedging_set_addon = epsilon_j * sqrt(
    (sum(rho_k * entity_addon_k for k in entities))**2
    + sum((1.0 - rho_k**2) * entity_addon_k**2 for k in entities)
)
```

Dabei sind für Kredit/Aktien `rho=0.50` bei Einzeladressen und `rho=0.80` bei Multi-Name-Indizes. Aktien-SF sind `0.32` für Einzeladressen und `0.20` für Indizes. Kredit-SF nach CQS sind `[0.0038, 0.0042, 0.0054, 0.0106, 0.0160, 0.0600]`; der unrated KSA-Wert ist grundsätzlich `0.0054`, nachrangig `0.0160`. Commodity verwendet dieselbe Form mit `rho=0.40`; SF und Elektrizitäts-Sonderwert werden aus dem versionierten Rechtsparameter gezogen.

```python
RWEA_CCR = credit_risk_function(EAD_CCR, counterparty, approach="KSA_OR_IRB")
```

### Simplified SA-CCR und Original Exposure Method

Simplified SA-CCR setzt `multiplier=1`, lineare Deltas auf `+/-1`, `MF_unmargined=1`, `MF_margined=0.42` und verwendet die vorgeschriebenen konservativen Add-on-Aggregationen.

Original Exposure Method:

```python
RC = TH + MTA if margined else max(CMV, 0.0)
PFE_trade = notional * {
    "INTEREST_RATE": 0.005 * maturity_years,
    "CREDIT": 0.06 * maturity_years,
    "FX": 0.04,
    "GOLD_OR_COMMODITY_EX_ELECTRICITY": 0.18,
    "ELECTRICITY": 0.40,
    "EQUITY": 0.32,
}[category]
PFE = sum(PFE_trade)
if margined:
    PFE *= 0.42
EAD = 1.4 * (RC + PFE)
```

SFT werden je zugelassener Methode gerechnet. Bei umfassender Finanzsicherheitenmethode gilt positionsweise `E_star`; bei anerkanntem Master-Netting:

```python
E_star = max(sum(E_i) - sum(C_j) + net_fx_or_security_volatility_addon, 0.0)
```

Die konkrete VaR-/IMM-Methode ist nur mit aufsichtlicher Erlaubnis zulässig und wird als eigene `model_version` geführt.

### CCP

```python
RWEA_QCCP_trade = EAD_trade * 0.02
RWEA_QCCP_client_if_joint_default_not_protected = EAD_trade * 0.04
RWEA_NQCCP_trade = EAD_trade * RW_standard_approach_counterparty

K_prefunded_QCCP_i = max(
    K_CCP * DF_i / (DF_CCP + DF_CM),
    0.08 * 0.02 * DF_i,
)
RWEA_prefunded_QCCP_i = 12.5 * K_prefunded_QCCP_i

K_default_fund_NQCCP = DF_prefunded + UC_unfunded
RWEA_default_fund_NQCCP = 12.5 * K_default_fund_NQCCP
K_unfunded_QCCP = 0.0
```

### CCR-/CCP-Datenobjekte

`netting_agreement`, `netting_set`, `derivative_trade`, `sft_trade`, `margin_collateral`, `sa_ccr_risk_position`, `ccr_result`, `ccp_exposure`, `protection_allocation`, `regulatory_parameter`, `risk_measure_result`.

## Verbriefungsrisiko

### Pool- und Tranchengrößen

```python
K_IRB = (
    0.08 * RWEA_pool_IRB_UL
    + EL_pool_IRB
) / EAD_pool
K_SA = 0.08 * RWEA_pool_SA / EAD_pool_before_adjustments

A = max((pool_balance - balance_senior_or_pari_passu_to_tranche) / pool_balance, 0.0)
D = max((pool_balance - balance_strictly_senior_to_tranche) / pool_balance, 0.0)
T = D - A
assert 0.0 <= A < D <= 1.0

M_T_cashflow = sum(t * CF_t for t, CF_t in tranche_cashflows) / sum(CF_t for _, CF_t in tranche_cashflows)
M_T_legal = 1.0 + 0.80 * (legal_final_maturity - 1.0)
M_T = clip(selected_M_T, 1.0, 5.0)
```

### Einheitliche SSFA-Funktion

```python
def K_SSFA(K_A, A, D, p):
    a = -1.0 / (p * K_A)
    u = D - K_A
    l = max(A - K_A, 0.0)
    if is_close(u, l):
        return exp(a * u)                 # Grenzwert
    return (exp(a * u) - exp(a * l)) / (a * (u - l))

def securitisation_RW(K_A, A, D, p, floor):
    if D <= K_A:
        rw = 12.50
    elif A >= K_A:
        rw = 12.5 * K_SSFA(K_A, A, D, p)
    else:
        rw = ((K_A - A) / (D - A)) * 12.5 \
           + ((D - K_A) / (D - A)) * 12.5 * K_SSFA(K_A, A, D, p)
    return min(max(rw, floor), 12.50)
```

### SEC-IRBA

```python
N = sum(EAD_i for i in obligors)**2 / sum(EAD_i**2 for i in obligors)
LGD_pool = sum(LGD_i * EAD_i for i in obligors) / sum(EAD_i for i in obligors)

coeff = coeff_table[pool_type, senior, N >= 25]
p_raw = (
    coeff.A
    + coeff.B * (1.0 / N)
    + coeff.C * K_IRB
    + coeff.D * LGD_pool
    + coeff.E * M_T
)
p = max(0.30, p_raw)

if STS:
    p = max(0.30, 0.50 * p_raw)
    floor = 0.10 if senior else 0.15
else:
    floor = 0.15

RW = securitisation_RW(K_IRB, A, D, p, floor)
RWEA = EAD_tranche * RW
```

Die vollständige Koeffiziententabelle:

```python
coeff_table = {
  ("NON_RETAIL", True,  True):  (0.00, 3.56, -1.85, 0.55, 0.07),
  ("NON_RETAIL", True,  False): (0.11, 2.61, -2.91, 0.68, 0.07),
  ("NON_RETAIL", False, True):  (0.16, 2.87, -1.03, 0.21, 0.07),
  ("NON_RETAIL", False, False): (0.22, 2.35, -2.46, 0.48, 0.07),
  ("RETAIL",     True,  True):  (0.00, 0.00, -7.48, 0.71, 0.24),
  ("RETAIL",     False, True):  (0.00, 0.00, -5.78, 0.55, 0.27),
}
```

### SEC-SA, SEC-ERBA und Wiederverbriefung

```python
W = defaulted_pool_nominal / total_pool_nominal
K_A = (1.0 - W) * K_SA + W * 0.50
p = 0.50 if STS else 1.00
floor = 0.10 if STS and senior else 0.15
RW_SEC_SA = securitisation_RW(K_A, A, D, p, floor)
```

Bei Wiederverbriefung wird SEC-SA mit den Artikel-269-Modifikationen, insbesondere `p=1.5`, ausgeführt; nicht erfüllte Daten-/Ansatzvoraussetzungen führen zu `RW=12.50`.

SEC-ERBA:

```python
RW_1y = ERBA_TABLE[cqs, seniority, 1]
RW_5y = ERBA_TABLE[cqs, seniority, 5]
RW_maturity = RW_1y + (M_T - 1.0) / 4.0 * (RW_5y - RW_1y)

if not senior:
    RW = RW_maturity * (1.0 - min(T, 0.50))
    RW = max(RW, 0.15, RW_hypothetical_senior_same_CQS_M)
else:
    RW = RW_maturity
RW = min(RW, 12.50)
```

Die 17×4 SEC-ERBA- und STS-Tabellen werden vollständig als `regulatory_parameter` mit Dimensionen `CQS`, `seniority`, `M_T_anchor`, `STS` gespeichert; die Kurzzeittabellen lauten normal `[0.15, 0.50, 1.00, 12.50]` und STS `[0.10, 0.30, 0.60, 12.50]`.

Ansatzhierarchie:

```python
approach = first_applicable([
    "SEC_IRBA",
    "SEC_SA",
    "SEC_ERBA_IF_PERMITTED_AND_RATED",
    "IAA_FOR_ELIGIBLE_ABCP_IF_APPROVED",
    "RW_1250",
])
```

### Verbriefungs-Datenobjekte

`securitisation_transaction`, `securitisation_pool`, `securitisation_tranche`, `securitisation_result`, `external_assessment`, `regulatory_parameter`, `risk_measure_result`.

## CVA-Risiko

### Scope

```python
CVA_scope = all_OTC_derivatives + material_fair_value_SFT
CVA_scope -= QCCP_transactions
CVA_scope -= qualifying_client_clearing
CVA_scope -= CRR_article_382_exemptions
```

Ausgenommene Geschäfte bleiben für die Pflicht-Parallelrechnung separat erhalten.

### BA-CVA ohne Hedges

```python
DF_NS = (1.0 - exp(-0.05 * M_NS)) / (0.05 * M_NS)
SCVA_c = (1.0 / 1.4) * RW_c * sum(M_NS * EAD_NS * DF_NS for NS in counterparty_c)

BA_CVA_unhedged = sqrt(
    (0.50 * sum(SCVA_c for c in counterparties))**2
    + (1.0 - 0.50**2) * sum(SCVA_c**2 for c in counterparties)
)
```

`RW_c` ist der exakte Sektor-/Bonitätslookup aus Artikel 384 Tabelle 1, z. B. Sovereign `0.5 %/2 %`, Financials `5 %/12 %`, Other `5 %/12 %` für CQS 1–3 beziehungsweise CQS 4–6/unrated.

### BA-CVA mit Hedges

```python
DF_h = (1.0 - exp(-0.05 * M_h)) / (0.05 * M_h)
SNH_c = (1.0 / 1.4) * RW_c * sum(r_hc * M_h * notional_h * DF_h for h in single_name_hedges_c)
HMA_c = (1.0 / 1.4) * RW_c * sum(M_h * notional_h * DF_h for h in single_name_hedges_c)
IH = (1.0 / 1.4) * sum(RW_i * M_i * notional_i * DF_i for i in index_hedges)

BA_CVA_hedged = sqrt(max(
    (0.50 * sum(SCVA_c - SNH_c for c in counterparties) - IH)**2
    + (1.0 - 0.50**2) * sum((SCVA_c - SNH_c)**2 for c in counterparties)
    + sum(max(HMA_c**2 - SNH_c**2, 0.0) for c in counterparties),
    0.0,
))

K_CVA_BA = 0.25 * BA_CVA_unhedged + 0.65 * (1.0 - 0.25) * BA_CVA_hedged
```

### SA-CVA und vereinfachter Ansatz

SA-CVA nutzt Delta und Vega, nicht Curvature:

```python
WS_k = RW_k * net_sensitivity_k
K_b = sqrt(max(
    sum(WS[k]**2 for k in risk_factors_b)
    + sum(rho[k,l] * WS[k] * WS[l]
          for k in risk_factors_b for l in risk_factors_b if k != l),
    0.0,
))
S_b = sum(WS_k)
K_risk_class = sqrt(max(
    sum(K[b]**2 for b in buckets)
    + sum(gamma[b,c] * S[b] * S[c] for b in buckets for c in buckets if b != c),
    0.0,
))
K_CVA_SA = sum(K_delta_risk_class) + sum(K_vega_risk_class)
```

Die sechs Risikoklassen, Buckets, Tenöre, RW und Korrelationen werden im versionierten Parameterobjekt gespeichert. Vereinfachter Ansatz:

```python
K_CVA_simplified = RWEA_CCR_for_CVA_scope / 12.5
RWEA_CVA = 12.5 * selected_K_CVA
```

### CVA-Datenobjekte

`cva_scope_item`, `cva_sensitivity`, `cva_result`, `netting_set`, `derivative_trade`, `sft_trade`, `ccr_result`, `regulatory_parameter`, `risk_measure_result`.

## Abwicklungs-, Liefer- und Großkreditrisiko

```python
potential_loss = max(
    agreed_settlement_price - current_market_value if bank_buys else
    current_market_value - agreed_settlement_price,
    0.0,
)

settlement_factor = bucket_lookup(
    business_days_late,
    bounds=[15, 30, 45, float("inf")],
    lower_inclusive_start=5,
    values=[0.08, 0.50, 0.75, 1.00],
)
K_settlement = potential_loss * settlement_factor
```

Vorleistungen:

```python
if before_first_contractual_leg:
    K_free_delivery = 0.0
elif days_after_second_leg <= 4:
    RWEA_free_delivery = positive_exposure * counterparty_RW
else:
    RWEA_free_delivery = positive_exposure * 12.50
```

Zulässige Überschreitungen der Großkreditgrenze im Handelsbuch:

```python
K_large_exposure_excess = sum(
    excess_slice * specific_risk_factor(slice) * escalation_factor(days_and_size_band)
    for slice in exposure_excess_waterfall
)
```

Die Wasserfallreihenfolge, Halteperioden- und Eskalationsfaktoren sind versionierte Parameter nach CRR Teil 4; Überschreitungen außerhalb der gesetzlichen Erlaubnis sind kein Rechenergebnis, sondern ein Compliance-Verstoß.

**Datenobjekte:** `settlement_exposure`, `trading_position`, `party`, `connected_client_group`, `regulatory_parameter`, `risk_measure_result`.

## Marktrisiko

### Regimeauswahl

```python
if as_of_date < date(2027, 1, 1) and rule_set.jurisdiction == "EU":
    K_market = legacy_market_requirement()
else:
    K_market = frtb_SA_or_IMA_requirement()
```

Ein paralleler FRTB-Lauf vor 2027 erhält `calculation_type="MANAGEMENT"` oder `FUTURE_REGIME` und darf nicht in den offiziellen TREA-Lauf einfließen.

### 2026 anwendbarer vereinfachter Standardansatz

Schuldtitel – spezifisches Risiko:

```python
specific_factor_debt = {
    "SA_RW_0": 0.00,
    "SA_RW_20_OR_50_LE_6M": 0.0025,
    "SA_RW_20_OR_50_6_TO_24M": 0.0100,
    "SA_RW_20_OR_50_GT_24M": 0.0160,
    "SA_RW_100": 0.0800,
    "SA_RW_150": 0.1200,
}[debt_category]
K_debt_specific = sum(abs(net_position_i) * specific_factor_debt_i for i in debt_positions)
```

Verbriefungspositionen im Handelsbuch:

```python
K_securitisation_specific = sum(abs(net_position_i) * 0.08 * banking_book_securitisation_RW_i)
```

Allgemeines Zinsrisiko – Laufzeitmethode:

```python
weighted_position_i = net_position_i * maturity_weight_i
matched_band_b = min(sum(long_weighted_b), abs(sum(short_weighted_b)))
unmatched_band_b = sum(long_weighted_b) + sum(short_weighted_b)  # signed after matching

matched_zone_z, unmatched_zone_z = sequential_match(unmatched_band_b, zone_z)
matched_12, residual_1, residual_2 = match_opposite(unmatched_zone_1, unmatched_zone_2)
matched_23, residual_2, residual_3 = match_opposite(residual_2, unmatched_zone_3)
matched_13, residual_1, residual_3 = match_opposite(residual_1, residual_3)

K_debt_general = (
    0.10 * sum(matched_band_b)
    + 0.40 * matched_zone_1
    + 0.30 * matched_zone_2
    + 0.30 * matched_zone_3
    + 0.40 * (matched_12 + matched_23)
    + 1.50 * matched_13
    + abs(residual_1) + abs(residual_2) + abs(residual_3)
)
```

Die vollständigen Laufzeitbänder und Gewichte `[0, 0.20 %, 0.40 %, 0.70 %, 1.25 %, 1.75 %, 2.25 %, 2.75 %, 3.25 %, 3.75 %, 4.50 %, 5.25 %, 6.00 %, 8.00 %, 12.50 %]` werden nach Couponklasse und Laufzeit versioniert. Alternative Durationsmethode:

```python
duration = sum(t * CF_t / (1 + y)**t for t, CF_t in cashflows) / sum(CF_t / (1 + y)**t for t, CF_t in cashflows)
modified_duration = duration / (1.0 + y)
duration_weighted_position = market_value * modified_duration * assumed_rate_change_by_zone

K_duration = (
    0.02 * sum(matched_within_zone)
    + 0.40 * (matched_12 + matched_23)
    + 1.50 * matched_13
    + sum(abs(residual_by_zone))
)
```

Aktien:

```python
gross_equity_position = sum(abs(net_position_by_instrument))
net_equity_position_by_market = abs(sum(net_position_i for i in market))
K_equity_specific = 0.08 * gross_equity_position
K_equity_general = 0.08 * sum(net_equity_position_by_market)
```

FX und Gold:

```python
net_ccy_c = cash_c + forward_c + certain_guarantees_c + option_delta_equivalent_c + other_options_c
total_long_FX = sum(max(convert_to_reporting_ccy(net_ccy[c]), 0.0)
                    for c in currencies if c != reporting_ccy)
total_short_FX = sum(abs(min(convert_to_reporting_ccy(net_ccy[c]), 0.0))
                     for c in currencies if c != reporting_ccy)
total_net_FX = max(total_long_FX, total_short_FX)
FX_base = total_net_FX + abs(net_gold_reporting_ccy)
K_FX = 0.08 * FX_base if FX_base > 0.02 * total_own_funds else 0.0
```

Eng verbundene Währungen werden, soweit zulässig, auf dem matched part mit `4 %`, WKM-II-Währungen mit `1.6 %` behandelt; nur der nicht ausgeglichene Teil geht in `total_net_FX` ein.

Waren – vereinfachte Methode:

```python
K_commodity_c = spot_c * (0.15 * abs(net_units_c) + 0.03 * gross_units_c)
K_commodity = sum(K_commodity_c)
```

Waren – Laufzeitbandmethode:

```python
K_commodity_c = spot_c * (
    0.015 * sum(matched_within_band_units)
    + 0.006 * sum(matched_carried_units * number_of_bands_carried)
    + 0.15 * abs(final_unmatched_units)
)
```

Die erweiterte Methode ersetzt `(spread, carry, outright)` nach Warenklasse durch `(1.0 %,0.3 %,8 %)`, `(1.2 %,0.5 %,10 %)`, `(1.5 %,0.6 %,12 %)` oder `(1.5 %,0.6 %,15 %)`. Optionen gehen zunächst mit `delta * underlying`; Gamma/Vega und sonstige Non-Delta-Risiken werden nach der lokal vorliegenden Options-RTS als Szenario-/Delta-plus-Aufschlag ergänzt.

```python
K_market_legacy = (
    K_debt_specific + K_debt_general
    + K_equity_specific + K_equity_general
    + K_CTP_specific
    + K_FX + K_commodity + K_option_non_delta
)
```

### FRTB-SA: Sensitivitäten

FRTB kennt als getrennte Charges Delta, Vega und Curvature; Gamma ist kein eigener regulatorischer Charge.

```python
s_k = sum(position_sensitivity_i_k for i in positions)
WS_k = RW_k * s_k

def bucket_charge(WS, rho):
    return sqrt(max(
        sum(WS[k]**2 for k in WS)
        + sum(rho[k,l] * WS[k] * WS[l] for k in WS for l in WS if k != l),
        0.0,
    ))

K_b = bucket_charge(WS_b, rho_b)
S_b_raw = sum(WS_b.values())
```

Falls der Radikand der klassenübergreifenden Aggregation negativ würde:

```python
S_b = clip(S_b_raw, -K_b, K_b)
K_risk_class = sqrt(max(
    sum(K_b**2 for b in buckets)
    + sum(gamma[b,c] * S[b] * S[c]
          for b in buckets for c in buckets if b != c),
    0.0,
))
```

Curvature pro Risikofaktor:

```python
CVR_up_k = -sum(V_i(x_k + RW_k) - V_i(x_k) - RW_k * s_i_k for i in positions_with_k)
CVR_down_k = -sum(V_i(x_k - RW_k) - V_i(x_k) + RW_k * s_i_k for i in positions_with_k)

def psi(x, y): return 0.0 if x < 0.0 and y < 0.0 else 1.0

K_b_up = sqrt(max(
    sum(CVR_up_k**2)
    + sum(rho[k,l]**2 * CVR_up[k] * CVR_up[l] * psi(CVR_up[k], CVR_up[l])
          for k in risk_factors_b for l in risk_factors_b if k != l),
    0.0,
))
K_b_down = sqrt(max(
    sum(CVR_down[k]**2 for k in risk_factors_b)
    + sum(rho[k,l]**2 * CVR_down[k] * CVR_down[l] * psi(CVR_down[k], CVR_down[l])
          for k in risk_factors_b for l in risk_factors_b if k != l),
    0.0,
))
K_b_curvature = max(K_b_up, K_b_down)
```

Die Bucket-Aggregation verwendet für Curvature `gamma_bc**2` und dieselbe `psi`-Logik. Jede Delta-, Vega- und Curvature-Rechnung wird in drei Korrelationsszenarien wiederholt:

```python
rho_high = min(1.25 * rho, 1.0)
rho_medium = rho
rho_low = max(2.0 * rho - 1.0, 0.75 * rho)

K_SBM = max(
    sum(K_delta_rc[s] + K_vega_rc[s] + K_curvature_rc[s] for rc in risk_classes)
    for s in ["LOW", "MEDIUM", "HIGH"]
)
```

### FRTB-SA: DRC und RRAO

```python
JTD_long = max(LGD * notional + PnL_long + adjustment_long, 0.0)
JTD_short = min(LGD * signed_notional_short + PnL_short + adjustment_short, 0.0)

LGD = {"SUBORDINATED": 1.00, "SENIOR": 0.75, "COVERED_BOND": 0.25, "EQUITY": 1.00}[class_]
maturity_scale = clip(maturity_years, 0.25, 1.0)
net_JTD_obligor = eligible_seniority_netting(sum(JTD * maturity_scale))

default_RW = {
    1: 0.005, 2: 0.03, 3: 0.06, 4: 0.15,
    5: 0.30, 6: 0.50, "UNRATED": 0.15, "DEFAULTED": 1.00,
}[credit_quality]

WtS_b = sum(net_JTD_i for i in long_b) / (
    sum(net_JTD_i for i in long_b) + sum(abs(net_JTD_i) for i in short_b)
)
DRC_b = max(
    sum(default_RW_i * net_JTD_i for i in long_b)
    - WtS_b * sum(default_RW_i * abs(net_JTD_i) for i in short_b),
    0.0,
)
K_DRC_non_securitisation = sum(DRC_b)
```

Für Verbriefungen wird `default_RW = 0.08 * banking_book_securitisation_RW`; Non-CTP- und CTP-DRC werden ohne Diversifikation zum Non-Securitisation-DRC addiert.

```python
K_RRAO = sum(
    abs(gross_notional_i) * (0.01 if exotic_underlying_i else 0.001)
    for i in residual_risk_positions
    if not statutory_exemption_i
)

K_FRTB_SA = K_SBM + K_DRC_nonsec + K_DRC_nonCTP + K_DRC_CTP + K_RRAO
```

### FRTB-IMA

Für jeden genehmigten Desk und jedes Liquiditätshorizont-Subset:

```python
ES_LH = sqrt(
    ES_10d_all**2
    + sum(ES_10d_subset_j**2 * (LH_j - LH_prev_j) / 10.0 for j in LH_buckets[1:])
)

stress_scaling = ES_reduced_stress / ES_reduced_current
IMCC_full = ES_full_current * stress_scaling

IMCC = 0.50 * IMCC_full + 0.50 * sum(IMCC_risk_class_i for i in broad_risk_classes)

K_IMA_desk = (
    max(IMCC_yesterday, mc * average(IMCC_last_60_business_days))
    + max(SES_NMRF_yesterday, ms * average(SES_NMRF_last_60_business_days))
    + K_DRC_IMA
    + capital_addons
)
```

`mc`/`ms`, Modellierbarkeit, Liquiditätshorizonte, Stressperiode, Backtesting- und PLA-Zonen sind versionierte Parameter/Ergebnisse. Nicht genehmigte oder disqualifizierte Desks fallen in den FRTB-SA; keine Diversifikation zwischen SA- und IMA-Desks.

### Marktrisiko-Datenobjekte

`trading_position`, `market_risk_factor`, `market_sensitivity`, `market_observation`, `derivative_trade`, `frtb_sa_result`, `frtb_ima_result`, `legacy_market_result`, `model_registry`, `regulatory_parameter`, `risk_measure_result`.

## Operationelles Risiko (EU-CRR-III-BIC)

### Dreijahreskomponenten

```python
def avg3(values):
    assert len(values) == 3
    return sum(values) / 3.0

IC = avg3([abs(interest_income[y] - interest_expense[y]) for y in last_three_financial_years])
AC = avg3([interest_earning_assets_at_year_end[y] for y in last_three_financial_years])
DC = avg3([dividend_income[y] for y in last_three_financial_years])
ILDC = min(IC, 0.0225 * AC) + DC

OI = avg3([other_operating_income[y] for y in last_three_financial_years])
OE = avg3([other_operating_expense_and_oprisk_losses[y] for y in last_three_financial_years])
FI = avg3([fee_income[y] for y in last_three_financial_years])
FE = avg3([fee_expense[y] for y in last_three_financial_years])
SC = max(OI, OE) + max(FI, FE)

TC = avg3([abs(net_PnL_trading_book[y]) for y in last_three_financial_years])
BC = avg3([abs(net_PnL_banking_book[y]) for y in last_three_financial_years])
FC = TC + BC

BI = ILDC + SC + FC
```

M&A werden rückwirkend in die drei Jahre einbezogen; veräußerte Aktivitäten nur mit Erlaubnis herausgerechnet. Institute mit weniger als drei Jahren verwenden genehmigte Forward-Schätzungen.

### BIC

```python
BI_billion = BI / 1_000_000_000.0
BIC_billion = (
    0.12 * min(BI_billion, 1.0)
    + 0.15 * min(max(BI_billion - 1.0, 0.0), 29.0)
    + 0.18 * max(BI_billion - 30.0, 0.0)
)
BIC = BIC_billion * 1_000_000_000.0
K_operational = BIC
RWEA_operational = 12.5 * K_operational
```

Es gilt ausdrücklich:

```python
ILM_EU = 1.0
K_operational_EU = BIC       # nicht BIC * ILM
```

Interne Verluste werden gleichwohl gepflegt:

```python
net_loss_event = gross_loss_event - cash_recoveries_received
annual_loss_y = sum(net_loss_event for event in y if net_loss_event >= threshold)
```

Pflichtdatensatz grundsätzlich ab `BI >= 750m`, vorbehaltlich der gesetzlichen Ausnahme bis `BI <= 1bn`; Default-Schwelle `20,000 EUR`, erhöhte Schwelle nur bei erfüllten Rechtsbedingungen.

### OpRisk-Datenobjekte

`accounting_measure`, `business_indicator_item`, `operational_loss_event`, `operational_risk_result`, `regulatory_parameter`, `risk_measure_result`.

## Output Floor und finale Säule-1-Aggregation

### U-TREA und S-TREA

```python
def trea_from_components(c):
    return (
        c.RWEA_credit_nontrading
        + c.RWEA_CCR_trading
        + 12.5 * (
            c.K_market
            + c.K_large_exposure_excess
            + c.K_settlement
            + c.K_CVA
            + c.K_operational
        )
    )

U_TREA = trea_from_components(actual_approach_components)
S_TREA = trea_from_components(standardised_recomputed_components)
```

Für `S_TREA` unzulässig sind insbesondere IRB, IMM/Modell-Netting, SEC-IRBA/IAA und FRTB-IMA. OpRisk, Settlement und andere ohnehin standardisierte Komponenten werden dennoch neu in der S-TREA-Sicht materialisiert, damit die Abstimmung vollständig ist.

### Floor-Formel und Übergang

```python
floor_factor = {
    2025: 0.50,
    2026: 0.55,
    2027: 0.60,
    2028: 0.65,
    2029: 0.70,
}.get(as_of_date.year, 0.725 if as_of_date.year >= 2030 else None)
if floor_factor is None:
    raise RuleNotApplicable("Output Floor ist vor 2025 nicht anwendbar")

floor_base = floor_factor * S_TREA
TREA_uncapped = max(U_TREA, floor_base)

if as_of_date <= date(2029, 12, 31) and rule_set.use_optional_25pct_floor_increase_cap:
    TREA = min(TREA_uncapped, 1.25 * U_TREA)
else:
    TREA = TREA_uncapped

floor_uplift = TREA - U_TREA
floor_binding = floor_uplift > 0.0
```

Übergangsregeln für unrated Corporates, Wohnimmobilien und SA-CCR-Alpha werden nur in `S_TREA` angewandt, wenn alle gesetzlichen Voraussetzungen und die einschlägige nationale Option erfüllt sind; die Auswahl wird im `rule_set` festgehalten.

### Floor-Allokation

Der Output Floor ist eine Gesamtuntergrenze, keine zusätzliche Risikoart. Eine Management-Allokation ist nur mit Summengleichheit zulässig, beispielsweise marginal/proportional:

```python
positive_gap_j = max(S_TREA_j * floor_factor - U_TREA_j, 0.0)
weight_j = positive_gap_j / sum(positive_gap_j)
allocated_floor_uplift_j = floor_uplift * weight_j
assert is_close(sum(allocated_floor_uplift_j), floor_uplift)
```

Diese Allokation ändert weder TREA noch aufsichtsrechtliche Einzel-RWEA.

### Datenobjekte

`risk_measure_result`, `trea_result`, `floor_allocation`, `sa_result`, `irb_result`, `securitisation_result`, `ccr_result`, `cva_result`, `frtb_sa_result`, `frtb_ima_result`, `legacy_market_result`, `operational_risk_result`.

## Eigenmittel und vollständiger regulatorischer Kapital-Stack

### CET1, AT1, T2

```python
CET1_before_deductions = (
    eligible_paid_in_common_equity
    + share_premium_CET1
    + retained_earnings
    + accumulated_OCI
    + other_reserves
    + funds_for_general_banking_risk
    + eligible_interim_or_year_end_profit
)

CET1 = (
    CET1_before_deductions
    + prudential_filters_CET1_signed
    - intangible_assets_net_of_related_DTL
    - deferred_tax_assets_relying_on_future_profit_non_temporary
    - cash_flow_hedge_reserve_deduction_signed
    - own_CET1_instruments
    - reciprocal_cross_holdings_CET1
    - significant_and_non_significant_financial_sector_holding_deductions
    - IRB_shortfall
    - defined_benefit_pension_assets_deduction
    - securitisation_and_other_1250pct_items_elected_for_deduction
    - NPE_prudential_backstop_deduction
    - other_CRR_CET1_deductions
    + eligible_minority_interests_CET1
)

AT1 = (
    eligible_AT1_instruments + AT1_share_premium
    - own_AT1_instruments - reciprocal_AT1_holdings
    - financial_sector_AT1_holding_deductions
    - other_AT1_deductions
    + eligible_minority_interests_AT1
)

T2 = (
    eligible_T2_instruments_after_amortisation + T2_share_premium
    + eligible_general_credit_risk_adjustments
    + eligible_IRB_excess
    - own_T2_instruments - reciprocal_T2_holdings
    - financial_sector_T2_holding_deductions
    - other_T2_deductions
    + eligible_minority_interests_T2
)

Tier1 = CET1 + AT1
Total_Own_Funds = Tier1 + T2
```

Zusätzliche Bewertungsanpassungen (AVA) nach Artikel 34/105 CRR werden vor der CET1-Summe positions- und methodenkonsistent berechnet:

```python
fair_value_scope = sum(
    abs(position.fair_value) * position.CET1_valuation_impact_share
    for position in fair_valued_assets_and_liabilities
    if not position.is_exactly_offset_and_RTS_excludable
)

if prudent_valuation_method == "SIMPLIFIED":
    assert fair_value_scope < 15_000_000_000
    AVA_total = 0.001 * fair_value_scope
else:
    AVA_fallback_i = (
        unrealised_net_gain_i
        + (
            0.10 * derivative_nominal_i
            if instrument_type_i == "DERIVATIVE"
            else 0.25 * abs(fair_value_i - unrealised_net_gain_i)
        )
    ) if fallback_method_applies_i else 0.0

    AVA_total = (
        AVA_market_price_uncertainty
        + AVA_close_out_costs
        + AVA_model_risk
        + AVA_unearned_credit_spreads
        + AVA_investing_and_funding_costs
        + AVA_concentrated_positions
        + AVA_future_administrative_costs
        + AVA_early_termination
        + sum(AVA_fallback_i for i in fallback_positions)
    )

additional_valuation_adjustments = max(AVA_total, 0.0)
```

Innerhalb der Kernansatz-Kategorien werden die in der Prudent-Valuation-RTS vorgeschriebenen 90-%-Konfidenz-, Exit-Price- und Diversifikationsregeln ausgeführt; deren Inputs und Zwischenresultate werden je Bewertungsposition gespeichert. `additional_valuation_adjustments` ist CET1-Abzug und darf weder als Marktrisiko-Kapitalanforderung noch ein zweites Mal im KSA-EAD abgezogen werden, falls das Quellsystem bereits den Nettobuchwert nach Artikel 111 liefert.

Der prudenzielle NPE-Backstop wird je notleidender Position gerechnet:

```python
def npe_unsecured_factor(year_after_npe_classification):
    if year_after_npe_classification <= 2:
        return 0.00
    if year_after_npe_classification == 3:
        return 0.35
    return 1.00

def npe_secured_factor(year_after_npe_classification, security_type):
    if year_after_npe_classification <= 3:
        return 0.00
    if year_after_npe_classification == 4:
        return 0.25
    if year_after_npe_classification == 5:
        return 0.35
    if year_after_npe_classification == 6:
        return 0.55
    if security_type == "IMMOVABLE_PROPERTY_OR_ELIGIBLE_HOME_GUARANTEE":
        return {7: 0.70, 8: 0.80, 9: 0.85}.get(year_after_npe_classification, 1.00)
    return 0.80 if year_after_npe_classification == 7 else 1.00

required_NPE_coverage_i = (
    unsecured_part_i * npe_unsecured_factor(npe_year_i)
    + secured_part_i * npe_secured_factor(npe_year_i, security_type_i)
)

available_NPE_coverage_i = (
    specific_credit_risk_adjustments_i
    + additional_valuation_adjustments_i
    + other_own_funds_reductions_i
    + allocated_IRB_EL_deduction_i
    + purchase_price_discount_i
    + partial_write_offs_since_NPE_i
)

NPE_shortfall_i = max(required_NPE_coverage_i - available_NPE_coverage_i, 0.0)
NPE_prudential_backstop_deduction = sum(NPE_shortfall_i for i in NPE_exposures)
```

Die erste einschlägige Forbearance kann den Faktor nach Artikel 47c Absatz 6 um ein Jahr einfrieren. Für qualifizierte 0-%-Sovereign-Garantien gilt bis einschließlich Jahr 7 grundsätzlich Faktor `0`, danach `1`, sofern der Sicherungsgeber nicht vertragsplangemäß vollständig leistet; der export agency-versicherte Teil ist ausgenommen. Diese Abweichungen überschreiben die Tabellenfunktion über eine versionierte `npe_factor_override`-Regel.

Dabei gelten die quantitativen Grenzen:

```python
eligible_general_credit_risk_adjustments = min(
    general_credit_risk_adjustments_KSA,
    0.0125 * RWEA_KSA_subject_to_cap,
)
eligible_IRB_excess = min(
    IRB_excess,
    0.0060 * RWEA_IRB_subject_to_cap,
)

remaining_days = max((maturity_date - as_of_date).days, 0)
if remaining_days > days_in_final_five_year_period:
    eligible_T2_instrument_amount = current_eligible_carrying_amount
else:
    eligible_T2_instrument_amount = (
        carrying_amount_on_first_day_of_final_five_year_period
        / days_in_final_five_year_period
        * remaining_days
    )
```

Schwellenwertbehandlungen werden vor der Summierung trancheweise berechnet:

```python
threshold_10 = 0.10 * CET1_after_unconditional_deductions
deduct_non_significant_holdings = max(non_significant_holdings - threshold_10, 0.0)
deduct_significant_CET1 = max(significant_CET1_holdings - threshold_10, 0.0)
deduct_DTA_temporary = max(DTA_temporary - threshold_10, 0.0)

combined_threshold_base = CET1_after_other_deductions
combined_threshold = 0.1765 * combined_threshold_base
deduct_combined_excess = max(
    remaining_significant_CET1_holdings + remaining_DTA_temporary - combined_threshold,
    0.0,
)
```

Nicht abgezogene Schwellenbeträge werden mit dem jeweils gesetzlich vorgeschriebenen RW, regelmäßig `250 %`, in Kredit-RWEA aufgenommen. T2-Instrumente werden in den letzten fünf Jahren linear regulatorisch amortisiert; genaue Eligibility, Grandfathering, Minderheiten- und Überschusskapitalformeln werden je Instrument/Tochter als versionierte Regel ausgeführt.

### Kapitalquoten und Säule 1

```python
CET1_ratio = CET1 / TREA
Tier1_ratio = Tier1 / TREA
Total_capital_ratio = Total_Own_Funds / TREA

P1_CET1_amount = 0.045 * TREA
P1_Tier1_amount = 0.060 * TREA
P1_Total_amount = 0.080 * TREA
```

### P2R, Kapitalpuffer, OCR und P2G

```python
P2R_amount = P2R_rate * TREA if decision_basis == "TREA_RATE" else P2R_fixed_amount

P2R_CET1_share = 0.5625 if supervisory_CET1_share is None else max(supervisory_CET1_share, 0.5625)
P2R_Tier1_share = 0.75 if supervisory_Tier1_share is None else max(supervisory_Tier1_share, 0.75)

P2R_CET1_amount = P2R_amount * P2R_CET1_share
P2R_Tier1_amount = P2R_amount * P2R_Tier1_share
```

Puffer:

```python
CCB_rate = 0.025
CCyB_rate = sum(RWEA_geo_j * CCyB_rate_j for j in geo_exposures) / sum(RWEA_geo_j)
systemic_rate = max(GSII_rate, OSII_rate) + SyRB_additive_rate_after_stacking_rules
CBR_rate = CCB_rate + CCyB_rate + systemic_rate
CBR_amount = CBR_rate * TREA
```

Die CRD-Stapelregeln für O-SII/G-SII/SyRB werden vor `systemic_rate` als explizite Entscheidungsfunktion ausgeführt; ein blindes Addieren ist unzulässig.

```python
TSCR_total_rate = 0.08 + P2R_rate
OCR_total_rate = TSCR_total_rate + CBR_rate

required_CET1_rate = 0.045 + P2R_CET1_share * P2R_rate + CBR_rate
required_Tier1_rate = 0.060 + P2R_Tier1_share * P2R_rate + CBR_rate
required_Total_rate = 0.080 + P2R_rate + CBR_rate

CET1_headroom_to_OCR = CET1 - required_CET1_rate * TREA
Tier1_headroom_to_OCR = Tier1 - required_Tier1_rate * TREA
Total_headroom_to_OCR = Total_Own_Funds - required_Total_rate * TREA
binding_OCR_headroom = min(CET1_headroom_to_OCR, Tier1_headroom_to_OCR, Total_headroom_to_OCR)
```

P2G liegt oberhalb des OCR und wird nicht in OCR/CBR oder MDA-Schwelle eingerechnet:

```python
capital_target_rate = OCR_total_rate + P2G_rate + management_buffer_rate
capital_target_amount = capital_target_rate * TREA
```

Beim erstmaligen Binden des Output Floors ist P2R nominal zunächst nicht allein deswegen zu erhöhen und danach auf Doppelzählung zu prüfen.

### Leverage Ratio

```python
leverage_exposure = (
    on_balance_exposure_after_leverage_adjustments
    + derivative_exposure_measure
    + SFT_exposure_measure
    + off_balance_nominal * leverage_CCF
    + other_adjustments
)
leverage_ratio = Tier1 / leverage_exposure
LR_min_amount = 0.03 * leverage_exposure
GSII_LR_buffer_amount = 0.50 * GSII_buffer_rate * leverage_exposure
```

Ein etwaiger leverage-bezogener P2R/P2G wird separat auf die Leverage Exposure Measure angewandt und nicht in TREA umgerechnet.

### MREL/TLAC und sonstige bindende Kapitalrestriktionen

```python
eligible_MREL = own_funds_eligible_for_MREL + eligible_liabilities_after_deductions
MREL_risk_ratio = eligible_MREL / TREA
MREL_leverage_ratio = eligible_MREL / leverage_exposure

eligible_TLAC = own_funds_eligible_for_TLAC + eligible_TLAC_liabilities_after_deductions
TLAC_risk_ratio = eligible_TLAC / TREA
TLAC_leverage_ratio = eligible_TLAC / leverage_exposure

MREL_headroom = min(
    eligible_MREL - MREL_risk_requirement_rate * TREA,
    eligible_MREL - MREL_leverage_requirement_rate * leverage_exposure,
)
TLAC_headroom = min(
    eligible_TLAC - TLAC_risk_requirement_rate * TREA,
    eligible_TLAC - TLAC_leverage_requirement_rate * leverage_exposure,
)
```

MREL/TLAC sind keine RWA-Komponenten. Sie werden als parallele bindende Restriktionen einschließlich Subordination, Resolution Entity/Internal MREL und Übergangsquoten geführt.

### Kapital-Datenobjekte

`capital_instrument`, `own_funds_component`, `valuation_adjustment`, `npe_coverage_result`, `capital_requirement`, `capital_stack_result`, `consolidation_scope`, `scope_membership`, `trea_result`, `risk_measure_result`, `regulatory_parameter`.
