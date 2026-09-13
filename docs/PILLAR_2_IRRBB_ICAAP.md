# 4. Methodik der Säule 2, IRRBB, CSRBB und ICAAP

## Perspektiven und Aggregationslogik

Die normative Perspektive projiziert GuV, Kapital und TREA über den
Planungshorizont. Die ökonomische Perspektive bewertet unerwartete Verluste
gegen eine definierte Risikodeckungsmasse. IRRBB wird sowohl barwertig über EVE
als auch periodisch über NII/EaR gemessen. Diese Perspektiven ergänzen sich,
werden aber nicht mechanisch addiert. SREP-P2R bleibt eine aufsichtliche
Entscheidung; interne Risikokapitalindikatoren werden als Managementsicht
gekennzeichnet.

Verhaltensannahmen für Sichteinlagen, Prepayment, Early Redemption,
Commercial Margins und dynamische Bilanz sind bankindividuelle, versionierte
Modellinputs. Die generische Engine verarbeitet die gelieferten Cashflows,
Gewichte, Szenarien und Korrelationen deterministisch.

## IRRBB – Cashflow-Zerlegung und Zinsschocks

### Scope und signierte Cashflows

Einbezogen werden alle zinssensitiven Banking-Book-Positionen, relevante kleine Handelsbuchtätigkeiten, Optionen sowie Pensionsverpflichtungen/-vermögen, soweit nicht anderweitig erfasst. CET1 und andere unbefristete Eigenmittel ohne Kündigungstermin werden ausgeschlossen.

```python
NPE_ratio = NPE_debt_loans_advances / gross_debt_loans_advances
include_NPE_cashflows = NPE_ratio >= 0.02

CF_i_t = (
    principal_cashflow_i_t
    + interest_cashflow_i_t
    + fee_or_margin_cashflow_if_in_scope_i_t
    + option_adjusted_cashflow_i_t
)
```

Für Assets ist Zufluss positiv, für Liabilities Abfluss negativ; Derivate werden in ihre Zahlungslegs zerlegt. Zahlungsdatum und nächstes Repricing-Datum sind getrennte Felder.

### Verhalten und Kundenoptionen

```python
behavioural_principal_CF_t = contractual_principal * behavioural_runoff_weight_t
assert is_close(sum(behavioural_runoff_weight_t), 1.0)

prepayment_rate_s_t = clip(model_prepayment(features, scenario_s, t), 0.0, 1.0)
early_redemption_rate_s_t = clip(model_redemption(features, scenario_s, t), 0.0, 1.0)

customer_rate_s_t = clip(
    customer_rate_base_t + pass_through_beta * (reference_rate_s_t - reference_rate_base_t),
    contractual_or_behavioural_floor,
    contractual_cap,
)
```

Für Non-Maturity Deposits (NMD):

```python
NMD_stable = balance * stable_share
NMD_core = NMD_stable * core_share
NMD_non_core = balance - NMD_core

CF_NMD_t = NMD_core * core_repricing_weight_t + NMD_non_core * non_core_repricing_weight_t
assert is_close(sum(CF_NMD_t), balance)
```

Core-Anteil, durchschnittliche/maximale Laufzeit, Repricing-Gewichte, Beta und Floor-Verhalten werden je Segment und Szenario versioniert und gegen die Grenzen der Standardmethode geprüft. Automatische und verhaltensabhängige Optionen werden je Szenario neu bewertet, nicht nur im Baseline-Cashflow belassen.

### Materielle Währungen

```python
share_c = {
    c: max(financial_assets[c] / total_financial_assets,
           financial_liabilities[c] / total_financial_liabilities)
    for c in currencies
}
material_currencies = {c for c in currencies if share_c[c] >= 0.05}

if covered_assets_or_liabilities(material_currencies) < 0.90:
    material_currencies |= add_largest_remaining_until_coverage(0.90)
```

### Sechs EU-Zinsschocks

Für Währung `c` und Mittelpunkt `t` eines Laufzeitbands in Jahren:

```python
R_parallel = P("IRRBB_PARALLEL_SHOCK_BP", dims={"currency": c},
               as_of_date=as_of_date, knowledge_time=knowledge_time,
               rule_set_id=rule_set_id) / 10_000
R_short = P("IRRBB_SHORT_SHOCK_BP", dims={"currency": c},
            as_of_date=as_of_date, knowledge_time=knowledge_time,
            rule_set_id=rule_set_id) / 10_000
R_long = P("IRRBB_LONG_SHOCK_BP", dims={"currency": c},
           as_of_date=as_of_date, knowledge_time=knowledge_time,
           rule_set_id=rule_set_id) / 10_000

shock = {
    "PARALLEL_UP":   +R_parallel,
    "PARALLEL_DOWN": -R_parallel,
    "SHORT_UP":      +R_short * exp(-t / 4.0),
    "SHORT_DOWN":    -R_short * exp(-t / 4.0),
    "STEEPENER":     -0.65 * abs(R_short * exp(-t / 4.0))
                     +0.90 * abs(R_long * (1.0 - exp(-t / 4.0))),
    "FLATTENER":     +0.80 * abs(R_short * exp(-t / 4.0))
                     -0.60 * abs(R_long * (1.0 - exp(-t / 4.0))),
}[scenario]
```

Für EUR sind `(parallel, short, long) = (200, 250, 100)` Basispunkte. Nicht im RTS-Anhang genannte Währungen werden mindestens alle fünf Jahre kalibriert:

```python
raw_parallel = 0.60 * historical_average_rate
raw_short = 0.85 * historical_average_rate
raw_long = 0.40 * historical_average_rate

R_parallel_bp = round_to_50bp(clip(raw_parallel_bp, 100, 400))
R_short_bp = round_to_50bp(clip(raw_short_bp, 100, 500))
R_long_bp = round_to_50bp(clip(raw_long_bp, 100, 300))
```

Nachschock-Floor:

```python
regulatory_floor_t = min(-0.015 + 0.0003 * t, 0.0)
effective_floor_t = min(base_zero_rate_t, regulatory_floor_t)
shocked_zero_rate_t = max(base_zero_rate_t + shock_t, effective_floor_t)
```

### Kurven und Abzinsung

Alle Kurvenpunkte werden vor der Rechnung in eine einheitliche kontinuierliche Zero-Rate-Notation transformiert:

```python
continuous_zero = m * log(1.0 + nominal_rate / m)   # m-fache Verzinsung
def DF_s_c(t): return exp(-continuous_zero_s_c(t) * t)
```

Interpolation geschieht auf log-Discountfaktoren; Extrapolation, Day Count und Kurvenquelle sind versioniert. Die EVE-SOT-Kurve ist eine allgemeine risikofreie Kurve ohne instrumenten-, sektor- oder unternehmensspezifische Kredit-/Liquiditätsspreads.

## IRRBB – ökonomische/barwertige Perspektive

### EVE je Position, Währung und Szenario

```python
PV_i_s = sum(CF_i_t_s * DF_s_c(t) for t in payment_times_i)
EVE_c_s = sum(PV_i_s for i in currency_c)
delta_EVE_c_s = EVE_c_s - EVE_c_base
EVE_loss_c_s = max(-delta_EVE_c_s, 0.0)
```

Margen-/Spread-Cashflows werden gemäß dokumentierter interner IRRBB-Steuerung konsistent ein- oder ausgeschlossen. Beide Sichten können parallel gerechnet werden; die SOT-Designation bezeichnet genau eine offizielle Sicht.

### Währungsaggregation nach EU-RTS

```python
delta_c = convert_to_reporting_ccy(delta_EVE_c_s, official_ECB_spot_c)
losses = sum(min(delta_c, 0.0) for c in material_currencies)

gain_weight_c = 0.80 if narrow_band_ERM2_currency(c) else 0.50
weighted_gains = sum(gain_weight_c * max(delta_c, 0.0) for c in material_currencies)

core = {reporting_currency} | narrow_band_ERM2_currencies
core_losses_abs = abs(sum(min(delta_c, 0.0) for c in core))
core_positive_half = 0.50 * sum(max(delta_c, 0.0) for c in core)
gain_recognition_cap = max(core_losses_abs, core_positive_half)
recognized_gains = min(weighted_gains, gain_recognition_cap)

delta_EVE_aggregate_s = losses + recognized_gains
EVE_loss_aggregate_s = max(-delta_EVE_aggregate_s, 0.0)
```

Die Zwischengrößen werden gespeichert, weil ein bloßer Gesamtbetrag die gesetzliche Gain-Cap nicht prüfbar macht.

### EVE-Ausreißertest

```python
worst_EVE_loss = max(EVE_loss_aggregate_s for s in six_supervisory_scenarios)
EVE_SOT_ratio = worst_EVE_loss / Tier1_reference_amount
EVE_outlier = EVE_SOT_ratio > 0.15
```

Die Referenz ist das zum SOT-Stichtag anrechenbare Kernkapital. Ein Überschreiten ist ein Aufsichtsindikator, keine automatische Kapitalfestsetzung.

### Interner Value-at-Risk und Expected Shortfall für EVE

Aus historischer Simulation, Monte Carlo oder parametrischem Modell entstehen gemeinsame Zinsfaktorpfade. Für jeden Pfad wird das gesamte Portfolio einschließlich Optionalität voll neu bewertet:

```python
delta_EVE_path_m = EVE_path_m - EVE_base
loss_m = -delta_EVE_path_m

VaR_EVE_q = max(quantile(loss_m, q), 0.0)
ES_EVE_q = mean([loss for loss in loss_m if loss >= VaR_EVE_q])
```

Bei parametrischer Delta-Gamma-Näherung:

```python
delta_V_m = delta_vector @ shock_m + 0.5 * shock_m.T @ gamma_matrix @ shock_m
```

Das Vollbewertungsmodell ist für wesentliche Optionalität führend. Horizont, Konfidenz, Haltedauer, Volatilitäts-/Korrelationsschätzung, Stresstails und Backtesting sind Teil von `model_version`.

### CSRBB

```python
PV_spread_i_s = sum(CF_i_t * exp(-(risk_free_zero_t + spread_i_t + spread_shock_i_t_s) * t) for t in times_i)
delta_CSRBB_s = sum(PV_spread_i_s - PV_spread_i_base for i in CSRBB_scope)
CSRBB_loss_s = max(-delta_CSRBB_s, 0.0)
```

Idiosynkratische, sektorale, marktweite, Liquiditäts- und Migrationseffekte werden getrennt gekennzeichnet. Spreadanteile, die bereits im Kredit- oder Marktrisiko-Economic-Capital enthalten sind, werden per `double_count_control` ausgeschlossen.

### Barwert-Datenobjekte

`product_contract`, `interest_rate_term`, `cashflow`, `behavioural_assumption`, `yield_curve`, `curve_point`, `irrbb_scenario`, `irrbb_result`, `market_observation`, `model_registry`, `risk_measure_result`.

## IRRBB – normative/periodische Perspektive

### Repricing Gap

```python
gap_band_b = (
    sum(repricing_principal_asset_i for i in band_b)
    - sum(repricing_principal_liability_i for i in band_b)
    + sum(delta_equivalent_derivative_leg_i for i in band_b)
)
cumulative_gap_b = sum(gap_band[j] for j in bands if j <= b)

approx_delta_NII_b = gap_band_b * delta_rate_b * accrual_fraction_within_horizon_b
```

Die Gap-Näherung ist Kontroll- und Erklärungsgröße; das offizielle NII wird cashflow-/accrualbasiert gerechnet.

### Einjahres-NII mit konstanter Bilanz

Regulatorischer Horizont `H=1 Jahr`. Fällige oder neu bepreiste Geschäfte werden durch Neugeschäft gleicher Währung, Höhe und Repricing-Periode ersetzt; neue Margen entsprechen aktuellen vergleichbaren Produktmargen.

```python
interest_income_s = sum(
    outstanding_asset_i_d_s * effective_customer_rate_i_d_s * day_fraction_d
    for i, d in horizon_days
)
interest_expense_s = sum(
    outstanding_liability_i_d_s * effective_customer_rate_i_d_s * day_fraction_d
    for i, d in horizon_days
)
derivative_interest_s = sum(net_interest_leg_i_d_s * day_fraction_d for i, d in horizon_days)
NII_s = interest_income_s - interest_expense_s + derivative_interest_s

delta_NII_s = NII_s - NII_base
EaR_s = max(NII_base - NII_s, 0.0)
```

Kommerzielle Margen und Spreadkomponenten sind zwingend enthalten. Sichteinlagen-Floor/Beta:

```python
deposit_rate_s_d = max(
    deposit_rate_floor,
    min(deposit_rate_cap, deposit_rate_base_d + beta * delta_reference_rate_s_d),
)
```

Ein „Bodensatzeinfrieren“ ist damit kein pauschales Nullsetzen des Marktschocks: Der Referenzzins wird geschockt, aber die Kundenrate bleibt am Floor, solange die Weitergabeformel keinen höheren Satz ergibt.

### NII-SOT und internes Earnings-at-Risk

```python
worst_NII_decline = max(EaR_s for s in ["PARALLEL_UP", "PARALLEL_DOWN"])
NII_SOT_ratio = worst_NII_decline / Tier1_reference_amount
NII_outlier = NII_SOT_ratio > 0.05
```

Internes stochastisches EaR:

```python
delta_NII_path_m = NII_path_m - NII_base
EaR_q = max(-quantile(delta_NII_path_m, 1.0 - q), 0.0)
NII_tail_cutoff = quantile(delta_NII_path_m, 1.0 - q)
ES_NII_q = mean([-delta for delta in delta_NII_path_m if delta <= NII_tail_cutoff])
```

Für dynamische Bilanzplanung wird separat gerechnet:

```python
NII_dynamic_s = NII_existing_book_s + NII_new_business_plan_s
```

Sie darf die regulatorische Constant-Balance-SOT-Rechnung nicht ersetzen.

### Periodische Datenobjekte

`product_contract`, `interest_rate_term`, `cashflow`, `behavioural_assumption`, `accounting_measure`, `normative_projection`, `yield_curve`, `irrbb_scenario`, `irrbb_result`, `scenario_path`, `model_registry`.

## ICAAP – vollständiges Risikoquantifizierungsmodell

### Universelle ökonomische Kapitaldefinition

Für jede materielle Risikoart `r` wird eine Verlustvariable `L_r` in positiver Verlustnotation erzeugt:

```python
EL_r = expected_value(L_r)
UL_r_q = max(quantile(L_r, q) - EL_r, 0.0)
EC_r = UL_r_q + stress_addon_r + model_risk_addon_r
```

Ist Expected Loss bereits vollständig durch Wertberichtigungen/Preisstellung gedeckt, wird `UL` kapitalisiert. Andernfalls:

```python
EC_r = max(quantile(L_r, q) - eligible_loss_absorbing_provisions_r, 0.0) + addons_r
```

Horizont und Konfidenzniveau sind gruppenweit konsistent oder werden über eine explizite Laufzeittransformation harmonisiert.

### Kredit-, Migrations- und Konzentrationsrisiko

```python
loss_credit_m = sum(
    EAD_i_m * LGD_i_m * default_indicator_i_m
    + migration_MtM_loss_i_m
    - eligible_recovery_i_m
    for i in credit_portfolio
)
EC_credit = capital_quantile(loss_credit_m)
```

Abhängigkeitsstruktur über gemeinsame systematische Faktoren:

```python
latent_i_m = sqrt(asset_corr_i) * systematic_factor_segment_m \
           + sqrt(1.0 - asset_corr_i) * idiosyncratic_i_m
default_indicator_i_m = 1 if latent_i_m < G(PD_i) else 0
```

Name-/Sektor-/Länder-Konzentration wird entweder bereits in der Vollsimulation erfasst oder als separater Benchmark-Aufschlag:

```python
EC_concentration = max(EC_actual_portfolio - EC_granular_diversified_reference, 0.0)
HHI = sum((EAD_i / sum(EAD))**2 for i in obligors_or_segments)
```

`HHI` ist Indikator, nicht selbst Kapital. Wird `EC_actual_portfolio` im Gesamt-Kredit-EC verwendet, ist `EC_concentration` auf null zu setzen, um Doppelzählung zu vermeiden.

### Markt-, Beteiligungs- und Immobilienpreisrisiko

```python
loss_market_m = -(full_revaluation_portfolio(factors_m) - value_base)
VaR_market_q = max(quantile(loss_market_m, q), 0.0)
ES_market_q = mean([loss for loss in loss_market_m if loss >= VaR_market_q])
EC_market = selected_tail_measure + stress_addon + NMRF_or_illiquidity_addon
```

Banking-Book-Beteiligungen und direkt gehaltene Immobilien werden analog voll neu bewertet und separat ausgewiesen, soweit nicht bereits in Kredit-, Markt- oder RWA-Risiko enthalten.

### Operationelles, Rechts-, Conduct-, Cyber- und IKT-Risiko

```python
N_m = frequency_distribution.sample(path_m)
LDA_loss_m = sum(severity_distribution.sample() for _ in range(N_m))
scenario_loss_m = scenario_overlay(path_m)
insurance_recovery_m = eligible_recovery_model(path_m)
loss_operational_m = max(LDA_loss_m + scenario_loss_m - insurance_recovery_m, 0.0)
EC_operational = capital_quantile(loss_operational_m)
```

Rechts-, Conduct-, Cyber-, IKT-, Outsourcing-, Fraud- und Modellprozessverluste sind OpRisk-Unterrisiken. Separate EC-Aufschläge sind nur für nachweislich nicht in Frequenz/Severity/Szenarien erfasste Residualrisiken zulässig.

### IRRBB und CSRBB im ökonomischen Kapital

```python
EC_IRRBB = selected_measure([VaR_EVE_q, ES_EVE_q, worst_internal_EVE_stress_loss])
EC_CSRBB = selected_measure([VaR_CSRBB_q, ES_CSRBB_q, worst_CSRBB_stress_loss])
```

`selected_measure` ist eine genehmigte Modellregel, nicht automatisch das Maximum. Wird konservativ das Maximum gewählt:

```python
EC_IRRBB = max(VaR_EVE_q, worst_internal_EVE_stress_loss)
```

Periodisches EaR darf nicht untransformiert zu barwertigem EC addiert werden. Eine Kapitalisierung erfolgt nur als Barwert nicht bereits im EVE enthaltener Ergebnisverluste:

```python
capitalised_EaR = sum(
    max(NII_base_y - NII_stress_y, 0.0) * after_tax_factor_y * discount_factor_y
    for y in capitalisation_horizon
    if loss_component_y_not_already_in_EVE
)
EC_IRRBB_combined = max(EC_EVE, capitalised_EaR)  # konservative Managementregel
```

### Liquiditäts-/Fundingrisiko

Liquiditätsrisiko ist grundsätzlich durch Liquiditätspuffer zu steuern; eine ökonomische Kapitalisierung ersetzt LCR/NSFR/ILAAP nicht. Messung:

```python
net_CF_t_s = capped_inflows_t_s - stressed_outflows_t_s
cumulative_liquidity_t_s = (
    opening_liquidity
    + sum(net_CF[u, s] for u in horizon if u <= t)
    + usable_counterbalancing_capacity[t, s]
)
max_liquidity_shortfall_s = max(0.0, -min(cumulative_liquidity_t_s for t in horizon))

funding_cost_loss_s = sum(
    emergency_funding_amount_t_s * stressed_funding_spread_t_s * accrual_t
    + liquidation_amount_t_s * liquidation_haircut_t_s
    for t in horizon
)
EC_liquidity_if_capitalised = capital_quantile(funding_cost_loss_s)
```

### Geschäfts-, strategisches und Reputationsrisiko

```python
business_loss_s = sum(
    max(baseline_pre_tax_profit_t - stressed_pre_tax_profit_t_s, 0.0) * DF_t
    for t in planning_horizon
)

reputation_loss_s = (
    direct_remediation_and_legal_cost_s
    + PV(funding_spread_increase_s)
    + PV(customer_attrition_margin_loss_s)
)

EC_business = selected_tail_or_stress_measure(business_loss_s)
EC_reputation = selected_tail_or_stress_measure(reputation_loss_s)
```

Ergebnisverluste, die bereits im normativen Planstress CET1 reduzieren, dürfen in einer kombinierten Solvenzsicht nicht zusätzlich als EC vom selben CET1 abgezogen werden.

### Pensions-, Versicherungs-, Steuer-, Länder-/Transfer- und sonstige Risiken

```python
pension_loss_s = max(
    (PBO_s - fair_value_plan_assets_s) - (PBO_base - fair_value_plan_assets_base),
    0.0,
)

tax_loss_s = additional_tax_cashflows_s + lost_DTA_value_s
country_transfer_loss_s = sum(EAD_i * transfer_blockage_LGD_i_s for i in affected_country)
insurance_residual_loss_s = claims_s + reserve_deterioration_s - eligible_reinsurance_recovery_s

EC_other_r = selected_tail_or_stress_measure(loss_r_s)
```

ESG-/Klima-, geopolitische und Modellrisiken wirken primär als Treiber bestehender Risikoarten. Nur der nach Integration verbleibende, messbare Rest wird additiv kapitalisiert:

```python
EC_ESG_residual = max(EC_with_ESG_drivers - EC_without_ESG_drivers - ESG_effect_already_allocated, 0.0)
EC_model = max(benchmark_capital - production_model_capital, 0.0) + limitation_addons
```

### Risikoabdeckung und Materialität

```python
for risk in risk_taxonomy:
    assert materiality_assessment_exists(risk, as_of_date)
    if risk.is_material:
        assert quantitative_measure_or_approved_qualitative_treatment_exists(risk)
        assert coverage_is_complete(
            assessed_risk,
            pillar1_coverage,
            pillar2_coverage,
            risk_mitigation,
        )
```

Offene Pflichtrisikotaxonomie: Kredit/Ausfall/Migration/Verwässerung, Konzentration, Gegenpartei, CVA, Verbriefung, Markt, IRRBB, CSRBB, FX/Commodity im Anlagebuch, operationell einschließlich IKT/Cyber/Conduct/Recht/Outsourcing, Liquidität/Funding, Geschäfts/Strategie/Reputation, Pension, Beteiligung/Immobilienpreis, Länder/Transfer, Versicherungs-/Steuer-/Modellrisiko, ESG/Klima/Geopolitik, Leverage und sonstige institutsspezifische Risiken.

### ICAAP-Risikodatenobjekte

`risk_taxonomy`, `materiality_assessment`, `icaap_scenario`, `scenario_path`, `economic_capital_result`, `model_registry`, `operational_loss_event`, `market_observation`, `cashflow`, `risk_measure_result`, `double_count_control`.

## ICAAP-Aggregation: normative und ökonomische Perspektive

### Normative Perspektive

Für jedes Szenario `s` und jede Periode `t` wird die gesamte Säule-1- und Kapitalrechnung erneut ausgeführt:

```python
CET1_t = (
    CET1_t_minus_1
    + profit_after_tax_t
    - distributions_t
    + OCI_change_t
    + eligible_CET1_issuance_t
    - CET1_redemption_t
    - change_in_CET1_deductions_t
)
AT1_t = AT1_t_minus_1 + eligible_AT1_issuance_t - AT1_redemption_or_ineligibility_t
T2_t = T2_t_minus_1 + eligible_T2_issuance_t - T2_redemption_amortisation_or_ineligibility_t

U_TREA_t = trea_from_components(stressed_actual_approach_components_t)
S_TREA_t = trea_from_components(stressed_standard_components_t)
TREA_t = output_floor(U_TREA_t, S_TREA_t, t, projected_rule_set_t)

CET1_ratio_t = CET1_t / TREA_t
Tier1_ratio_t = (CET1_t + AT1_t) / TREA_t
Total_ratio_t = (CET1_t + AT1_t + T2_t) / TREA_t
leverage_ratio_t = (CET1_t + AT1_t) / leverage_exposure_t
```

Anforderungen werden periodengerecht neu bestimmt:

```python
required_CET1_t = (0.045 + P2R_CET1_share_t * P2R_rate_t + CBR_rate_t) * TREA_t
required_Tier1_t = (0.060 + P2R_Tier1_share_t * P2R_rate_t + CBR_rate_t) * TREA_t
required_Total_t = (0.080 + P2R_rate_t + CBR_rate_t) * TREA_t

headroom_t = min(
    CET1_t - required_CET1_t,
    CET1_t + AT1_t - required_Tier1_t,
    CET1_t + AT1_t + T2_t - required_Total_t,
    Tier1_t - leverage_requirement_amount_t,
    MREL_headroom_t,
    TLAC_headroom_t,
)

normative_shortfall_s = max(0.0, -min(headroom_t for t in horizon))
```

Management Actions werden einmal ohne und einmal mit Maßnahmen gerechnet. Nur rechtlich und operativ glaubwürdige Maßnahmen mit Ausführungs-Lag, Kosten und Volumenlimit dürfen im offiziellen ICAAP-Szenario wirken.

### Ökonomische Risikodeckungsmasse

```python
economic_risk_bearing_capacity = (
    eligible_CET1_resources
    + eligible_additional_internal_resources
    - valuation_adjustments_not_already_in_CET1
    - foreseeable_distributions
    - fungibility_and_transferability_haircuts
    - management_reserve
)
```

AT1/T2 werden nur einbezogen, wenn ihre Verlustabsorptionsfähigkeit innerhalb des gewählten Fortführungs-/Liquidationskonzepts nachgewiesen ist.

### Ökonomische Risikoaggregation

Konservative Summe ohne Diversifikation:

```python
EC_linear = sum(EC_r for r in material_risks)
```

Varianz-Kovarianz-Aggregation, nur für kompatible Horizonte/Quantile und validierte Abhängigkeiten:

```python
assert correlation_matrix_is_symmetric(Corr)
assert min_eigenvalue(Corr) >= -numerical_tolerance

EC_correlated_raw = sqrt(max(EC_vector.T @ Corr @ EC_vector, 0.0))
raw_diversification = sum(EC_vector) - EC_correlated_raw
recognized_diversification = min(raw_diversification, diversification_cap_amount)

EC_aggregate = (
    sum(EC_vector)
    - recognized_diversification
    + sum(non_diversifiable_addons)
)
```

Bei gemeinsamer Simulation ist die Verteilung führend:

```python
L_total_m = sum(L_r_m for r in material_risks) + non_diversifiable_loss_m
EC_joint = max(quantile(L_total_m, q) - expected_value(L_total_m), 0.0)
EC_aggregate = max(EC_joint + model_addons, approved_stress_floor)
```

Euler-Allokation für die Wurzelaggregation:

```python
EC_alloc_i = EC_i * sum(Corr[i,j] * EC_j for j in risks) / EC_correlated_raw
assert is_close(sum(EC_alloc_i), EC_correlated_raw)
```

Risikotragfähigkeit:

```python
economic_headroom = economic_risk_bearing_capacity - EC_aggregate
economic_utilisation = EC_aggregate / economic_risk_bearing_capacity
```

### Konsistenz beider Perspektiven

```python
combined_breach = normative_shortfall_s > 0 or economic_headroom < 0
```

Normative und ökonomische Größen werden nicht addiert: Sie sind zwei Perspektiven auf dasselbe Institut. Ein Risiko kann beide Perspektiven belasten, aber eine gemeinsame Gesamtkapitalzahl darf denselben Verlust nicht einmal als CET1-Reduktion und ein zweites Mal als EC-Abzug erfassen.

### Datenobjekte

`icaap_scenario`, `scenario_path`, `normative_projection`, `economic_capital_result`, `risk_bearing_capacity`, `capital_stack_result`, `trea_result`, `model_registry`, `aggregation_result`, `double_count_control`.

## P2R und RWA-Äquivalente

### Regulatorische Wahrheit

P2R entsteht aus dem SREP-Bescheid. Es gibt keine CRD-Formel

```python
P2R_IRRBB = max(EVE_loss, NII_loss)
```

und weder 15-%-EVE- noch 5-%-NII-Überschreitung erzeugt automatisch einen bestimmten Zuschlag. Für den offiziellen Kapital-Stack gilt ausschließlich:

```python
P2R_amount_official = (
    supervisory_P2R_rate * TREA
    if supervisory_decision_basis == "TREA_RATE"
    else supervisory_fixed_P2R_amount
)
```

Eine risikospezifische P2R-Zuordnung ist nur offiziell, wenn sie aus Bescheid/aufsichtlicher Kommunikation stammt. Eine interne Allokation wird so gekennzeichnet:

```python
weight_r = approved_risk_driver_r / sum(approved_risk_driver)
P2R_amount_r_management = P2R_amount_official * weight_r
assert sum(P2R_amount_r_management) == P2R_amount_official
```

### Interner IRRBB-Kapitalindikator

Für die interne Steuerung, nicht als regulatorische P2R-Prognose:

```python
after_tax_factor_y = 1.0 - effective_tax_rate_y
capitalised_EaR_not_already_in_EVE = sum(
    max(NII_base_y - NII_stress_y, 0.0)
    * after_tax_factor_y
    * discount_factor_y
    * (1.0 - EVE_overlap_share_y)
    for y in approved_capitalisation_horizon
)

IRRBB_internal_capital_indicator = max(
    EC_EVE,
    capitalised_EaR_not_already_in_EVE,
)
```

Alternativ kann ein validiertes gemeinsames Modell beide Ergebnisdimensionen in einer Verlustverteilung erfassen. Die gewählte Regel wird als `model_version` geführt.

### Isoliertes P2R-RWA-Äquivalent

Mit expliziter Referenzquote `q_ref`:

```python
q_ref = 0.08  # Default: Säule-1-Gesamtkapitalquote
P2R_RWA_equivalent = P2R_amount_official / q_ref

# wenn P2R als Quote auf TREA festgesetzt ist:
P2R_RWA_equivalent = (P2R_rate * TREA) / q_ref
```

Risikospezifisch, etwa IRRBB:

```python
IRRBB_P2R_RWA_equivalent = P2R_amount_IRRBB_official / q_ref
```

Ökonomisches Kapital:

```python
EC_RWA_equivalent = EC_aggregate / q_ref
EC_RWA_equivalent_r = EC_r / q_ref
```

### Zulässige Sichten und Double-Count-Regel

Rechtliche Sicht:

```python
legal_total_capital_requirement = (
    0.08 * TREA
    + P2R_amount_official
    + CBR_amount
)
# P2G/Managementpuffer separat oberhalb OCR
```

Reine 8-%-Äquivalenzsicht:

```python
equivalent_TREA_for_P1_plus_P2R = TREA + P2R_amount_official / 0.08
equivalent_capital_at_8pct = 0.08 * equivalent_TREA_for_P1_plus_P2R
assert equivalent_capital_at_8pct == 0.08 * TREA + P2R_amount_official
```

Verbotene Mischsicht:

```python
assert not (
    P2R_amount_is_added_to_capital_requirement
    and P2R_RWA_equivalent_is_added_to_TREA
)
```

Puffer, P2G, MREL/TLAC und Leverage werden nur dann ebenfalls in Äquivalenz-RWA transformiert, wenn die Auswertung ausdrücklich eine reine Äquivalenzsicht ist; sie bleiben sonst separate Kapitalrestriktionen.

### Datenobjekte

`capital_requirement`, `rwa_equivalent_result`, `economic_capital_result`, `irrbb_result`, `capital_stack_result`, `double_count_control`, `risk_measure_result`.

## Aggregationsmodell für sämtliche Komponenten

### Operatoren

```python
def ADD(values): return sum(values)                         # Geldbeträge/RWEA/K
def RATIO(numerators, denominators): return sum(numerators) / sum(denominators)
def WEIGHTED(values, weights): return sum(v*w for v, w in zip(values, weights)) / sum(weights)
def WORST_LOSS(deltas): return max(-delta for delta in deltas)
def CORRELATED(capitals, corr): return sqrt(capitals.T @ corr @ capitals)
def QUANTILE(losses, q): return ordered_quantile(losses, q)
```

Quoten, RW, PD, LGD, CCF, ETV/LTV und Laufzeiten werden niemals ungewichtet summiert. RW auf Aggregatebene ist ausschließlich:

```python
effective_RW = sum(RWEA_i) / sum(EAD_i)
```

### Körnung, Schlüssel und Additivität

| Komponente | Atomare Ergebniskörnung | Ergebnisobjekt | Aggregation |
|---|---|---|---|
| KSA | Exposure × CRM-/Immobiliensegment | `sa_result` | `sum(RWEA)` |
| IRB | Exposure/Pool × Parametersatz | `irb_result` | `sum(RWEA)`, EL separat |
| CCR | Netting-Satz × Gegenpartei | `ccr_result` | erst Netting-Satz, dann Kredit-RW, dann Summe |
| CCP | CCP × Trade/Default-Fund-Beitrag | `ccp_exposure` | Summe ohne QCCP/NQCCP-Netting |
| Verbriefung | Tranche × Ansatz | `securitisation_result` | `sum(EAD*RW)` |
| CVA | Sensitivität/Bucket bzw. Gegenpartei | `cva_result` | vorgeschriebene Korrelation, dann Summe der Ansätze |
| Settlement | nicht abgewickeltes Geschäft | `settlement_exposure` | `sum(K)` bzw. `sum(RWEA)` |
| Markt Altregime | Position × Risikotyp/Währung/Markt | `legacy_market_result` | Methodenwasserfall, dann `sum(K)` |
| FRTB-SA | Sensitivität × Faktor/Bucket | `frtb_sa_result` | Bucket-Korrelation, Szenario-Maximum, dann SBM+DRC+RRAO |
| FRTB-IMA | Desk × Modell/LH | `frtb_ima_result` | Desk-K, keine SA-/IMA-Diversifikation |
| OpRisk | Scope × Dreijahresfenster | `operational_risk_result` | BIC am aufsichtsrechtlichen Scope, nicht Summe von Tochter-BIC ohne Erlaubnis |
| Output Floor | Konsolidierungsscope | `trea_result` | `max(U_TREA, x*S_TREA)` |
| IRRBB | Position × Cashflow × Währung × Szenario | `irrbb_result` | PV-Summe, Währungs-Gain-Cap, Szenario-Worst |
| Economic Capital | Risiko × Scope × Szenario/Quantil | `economic_capital_result` | linear, korreliert oder gemeinsame Simulation |
| Kapital | Instrument/Komponente × Kapitalart | `capital_stack_result` | Eligibility/Abzug zuerst, danach Summen/Quoten |

### Hierarchieaggregation

```python
for hierarchy in [entity, consolidation_scope, portfolio, product, country, sector,
                  exposure_class, approach, currency, desk, maturity_band]:
    result[parent] = sum(result[child] * ownership_or_elimination_weight(child) for child in children(parent))
```

Konsolidierungseliminierungen sind eigene signierte Ergebniszeilen. Eine Position darf innerhalb derselben exklusiven Hierarchie genau einem Blatt angehören; Mehrfachsichten sind getrennte Hierarchien.

### Reconciliation

```python
assert is_close(sum(atomic_RWEA), reported_RWEA)
assert is_close(sum(U_TREA_components), U_TREA)
assert is_close(sum(S_TREA_components), S_TREA)
assert is_close(TREA, max_or_transition_capped(U_TREA, floor_factor * S_TREA))
assert CET1 <= Tier1 <= Total_Own_Funds
assert is_close(sum(floor_allocations), floor_uplift)
assert is_close(sum(EC_allocations), EC_aggregate_before_nonallocable_addons)
```
