# Granular bank-analyst API

Copyright © 2026 RiskDataScience GmbH. Licensed under GPL-3.0-only.

## Purpose and control model

Version 1.2.0 exposes the calculation building blocks that a bank analyst needs to
inspect, independently reproduce and sensitivity-test the engine. The public surface is
not limited to an end-to-end calculation: it provides 38 atomic regulatory formulae,
nine domain views, the complete parameter and formula inventories, bitemporal selection,
table contracts, detailed results and individual controls.

Rates, risk weights, probabilities and correlations are decimals. Monetary values use
one caller-selected currency consistently. Formulae do not round; reporting layers decide
presentation precision. A `parameters=` argument accepts `None`, a
`pandas.DataFrame`, or `ParameterStore`. `None` uses the bundled versioned regulatory
parameter table. Analysts should pass an explicit reviewed table for governed production
use.

## Governed parameter workflow

```python
import pandas as pd
from rwa_engine import (
    calculate_tables,
    override_regulatory_parameters,
    parameter_overrides,
    regulatory_parameter,
)
from rwa_engine.synthetic import generate_synthetic_tables

tables = generate_synthetic_tables(bank_profile="KSA_BANK")
overrides = pd.DataFrame([{
    "parameter_key": "RWA_MULTIPLIER",
    "dimension_1": "PILLAR1",
    "dimension_2": "",
    "parameter_value": 13.0,
}])

changed = override_regulatory_parameters(
    tables, overrides, reason="Sensitivity", approved_by="Model Risk"
)
result = calculate_tables(changed)
print(parameter_overrides(result))
```

The operation copies every table and cannot mutate the caller's data. Each override must
identify exactly one existing key/dimension tuple, be numeric and carry non-empty reason
and approver fields. The audit contains sequence, key, dimensions, old value, new value,
reason and approver. `calculate_tables(..., parameter_overrides=..., override_reason=...,
override_approved_by=...)` provides the same controlled operation in one call.

## Formula API: 38 public functions

### Standardised credit risk and CRM

| Function | Controlled result |
|---|---|
| `sa_exposure_value(...)` | on-balance, off-balance and total SA exposure value |
| `sa_risk_weight(...)` | SA risk weight after class, CQS, default and special-lending rules |
| `real_estate_risk_weight(...)` | effective weight plus privileged/remainder or whole-loan segments |
| `crm_maturity_factor(...)` | maturity-mismatch adjustment factor |
| `crm_adjusted_exposure(...)` | comprehensive-method exposure after collateral and haircuts |

### Internal-ratings-based credit risk

| Function | Controlled result |
|---|---|
| `irb_asset_correlation(...)` | corporate asset correlation, with SME and financial options |
| `irb_retail_correlation(...)` | retail-subclass asset correlation |
| `irb_maturity_coefficient(...)` | maturity coefficient `b(PD)` |
| `irb_maturity_factor(...)` | bounded effective-maturity multiplier |
| `irb_capital_requirement(...)` | unexpected-loss capital rate, including defaulted treatment |

### Credit supporting factors (1.2.0)

| Function | Controlled result |
|---|---|
| `sme_supporting_factor(...)` | Article 501 weighted factor from E* in EUR |
| `infrastructure_supporting_factor(...)` | configured Article 501a factor |
| `apply_credit_supporting_factors(...)` | pre-support RWEA times independently selected factors |
| `irb_risk_weighted_assets(...)` | EAD times multiplier times K times factors |

See [supporting factors](SUPPORTING_FACTORS.md) for eligibility and input/output fields.

### Counterparty, SFT, securitisation, CVA and settlement risk

| Function | Controlled result |
|---|---|
| `sa_ccr_multiplier_value(...)` | SA-CCR supervisory multiplier |
| `sa_ccr_exposure_value(...)` | replacement cost, multiplier, PFE and EAD |
| `sft_exposure_value(...)` | haircut-adjusted SFT exposure |
| `securitisation_irb_pool_capital(...)` | `K_IRB` pool capital ratio |
| `securitisation_sa_pool_capital(...)` | `K_SA` pool capital ratio |
| `securitisation_ssfa_coefficient(...)` | SSFA exponential tranche coefficient |
| `securitisation_ssfa_risk_weight(...)` | floored/capped SSFA risk weight |
| `securitisation_irba_p(...)` | raw and applicable SEC-IRBA supervisory `p` |
| `securitisation_erba_risk_weight(...)` | maturity-interpolated SEC-ERBA risk weight |
| `securitisation_risk_weight(...)` | approach-dispatched tranche risk weight |
| `cva_basic_approach_capital(...)` | BA-CVA capital across counterparty/hedge tuples |
| `settlement_risk_factor(...)` | factor for settlement-delay band |

The BA-CVA `items` rows contain, in order: counterparty risk weight, maturity, EAD,
single-name hedge amount, hedge maturity, hedge correlation, index hedge amount, index
maturity and index risk weight.

### Operational risk, output floor, NPE and own funds

| Function | Controlled result |
|---|---|
| `business_indicator_component(...)` | ILDC, services, financial, BI and BIC amounts |
| `applicable_output_floor_factor(...)` | date-dependent or fully-loaded floor factor |
| `apply_output_floor(...)` | final TREA, uplift and binding flag |
| `npe_unsecured_coverage_factor(...)` | unsecured NPE vintage factor |
| `npe_secured_coverage_factor(...)` | property/other secured NPE vintage factor |
| `tier2_eligible_amount(...)` | Tier-2 amount after final-five-year amortisation |

### IRRBB, FRTB and economic capital

| Function | Controlled result |
|---|---|
| `irrbb_scenario_shock(...)` | term-dependent prescribed scenario shock |
| `irrbb_shocked_zero_rate(...)` | shocked zero rate subject to regulatory floor |
| `present_value_discount_factor(...)` | continuous-compounding discount factor |
| `aggregate_correlated_capital(...)` | square-root aggregation under a correlation matrix |
| `frtb_scenario_correlation(...)` | low, medium or high correlation transform |
| `frtb_quadratic_charge(...)` | within-bucket delta/vega or curvature charge |

The implementations invoked here are the same numerical functions used by the complete
engine. The only exception is the public extraction of the two FRTB aggregation helpers:
their equations are kept identical to the market-risk calculation path and tested for
parity.

## Parameter, rule, formula and data-contract access

| Function | Purpose |
|---|---|
| `regulatory_parameters(tables=None)` | complete parameter inventory as a defensive copy |
| `regulatory_parameter(key, d1="", d2="", parameters=None)` | fail-closed lookup of one value |
| `override_regulatory_parameters(...)` | exact, non-mutating, governed override |
| `parameter_overrides(x)` | override audit from tables or result |
| `formula_catalog(tables=None)` | versioned formula-definition table |
| `available_rule_sets(tables=None)` | selectable rule-set inventory |
| `select_rule_set(tables, rule_set_id)` | non-mutating `run_config` selection |
| `table_dictionary()` | all 68 logical tables and their workbook/sheet assignments |
| `table_schema(table)` | full columns, primary key and physical Excel contract |
| `official_snapshot(...)` | official bitemporal records at business and knowledge time |

## Result and control access

`CalculationResult` now retains `metrics`, `controls` and `results` for the applied view,
and `parallel_metrics`, `parallel_controls` and `parallel_results` for the fully-loaded
view. It also carries `parameter_override_audit`.

| Function | Purpose |
|---|---|
| `rwa_metrics(result, view)` | tidy inventory of metrics and inferred units |
| `rwa_metric(result, metric, view)` | one explicit metric; unknown names fail closed |
| `rwa_result_tables(result, view)` | defensive copies of detailed tables |
| `rwa_result_table(result, table, view)` | one detailed result table |
| `rwa_table_names(result, view)` | available result-table names |
| `rwa_controls(result, view)` | all reconciliations and governance controls |
| `failed_controls(result, view)` | only non-passing controls |
| `rwa_validation(result)` | immutable input-validation report |
| `compare_calculation_views(result)` | applied/fully-loaded values and differences |
| `rwa_summary(result)` | core metrics, run identity, controls and overrides |

## Nine bank-analysis domains

Each function accepts canonical tables or an existing `CalculationResult` and returns a
`DomainAnalysis`. Reusing a result avoids recalculation. Its `metrics`, `tables` and
`controls` are filtered to the selected domain while `run_id`, `view` and parameter audit
retain traceability.

| Function | Scope |
|---|---|
| `analyze_credit_risk(...)` | SA, IRB and cryptoasset credit risk |
| `analyze_counterparty_risk(...)` | CCR, SFT, CCP, CVA, settlement and large exposures |
| `analyze_securitisation(...)` | securitisation approaches and tranche evidence |
| `analyze_market_risk(...)` | legacy market risk and FRTB SBM, DRC and IMA |
| `analyze_operational_risk(...)` | BI/BIC and operational-risk capital |
| `analyze_output_floor(...)` | standardised, unfloored and floored TREA |
| `analyze_capital_adequacy(...)` | own funds, ratios, leverage and MREL/TLAC |
| `analyze_irrbb(...)` | EVE, NII, CSRBB, currencies and scenarios |
| `analyze_icaap(...)` | economic and normative perspectives and Pillar-2 bridge |

```python
from rwa_engine import analyze_credit_risk, compare_calculation_views

credit = analyze_credit_risk(result, view="fully_loaded")
print(credit.metrics)
print(credit.tables["SA_Detail"])
print(compare_calculation_views(result))
```

## Validation and limitations

The public formula count, names, docstrings and executable examples are release-gated.
Tests also run a complete synthetic KSA-bank calculation, assert 63 metrics and 34 result
tables in both views, exercise all nine domains, verify override non-mutation and build
then install both wheel and sdist in clean environments.

The library is a transparent reference and validation implementation, not an approved
bank model or regulatory reporting submission. Institutions remain responsible for legal
interpretation, data lineage, model governance, permissions, national discretions and
independent validation.
