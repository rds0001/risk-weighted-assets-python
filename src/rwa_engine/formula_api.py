"""Granular, public and side-effect-free regulatory formula API.

Copyright (C) 2026 RiskDataScience GmbH.
SPDX-License-Identifier: GPL-3.0-only
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from math import sqrt
from typing import Sequence

import pandas as pd

from . import formulas as _f
from .parameters import ParameterStore


@lru_cache(maxsize=1)
def _default_parameter_store() -> ParameterStore:
    from .synthetic import generate_synthetic_tables

    return ParameterStore(generate_synthetic_tables(bank_profile="KSA_BANK")["regulatory_parameter"])


def _store(parameters: ParameterStore | pd.DataFrame | None) -> ParameterStore:
    if parameters is None:
        return _default_parameter_store()
    if isinstance(parameters, ParameterStore):
        return parameters
    if isinstance(parameters, pd.DataFrame):
        return ParameterStore(parameters)
    raise TypeError("parameters must be None, a pandas DataFrame or ParameterStore")


def sa_exposure_value(
    gross_carrying_amount: float,
    annex_i_class: str,
    *,
    specific_adjustments: float = 0.0,
    additional_valuation_adjustments: float = 0.0,
    other_own_funds_reductions: float = 0.0,
    committed_undrawn: float = 0.0,
    data_path: str = "GROSS_COMPONENTS",
    net_carrying_amount_article_111: float | None = None,
    parameters: ParameterStore | pd.DataFrame | None = None,
) -> tuple[float, float, float]:
    """Return on-balance-sheet, off-balance-sheet and total SA exposure value."""
    return _f.sa_ead(
        gross_carrying_amount=gross_carrying_amount,
        specific_adjustments=specific_adjustments,
        additional_valuation_adjustments=additional_valuation_adjustments,
        other_own_funds_reductions=other_own_funds_reductions,
        committed_undrawn=committed_undrawn,
        annex_i_class=annex_i_class,
        data_path=data_path,
        net_carrying_amount_article_111=net_carrying_amount_article_111,
        params=_store(parameters),
    )


def sa_risk_weight(
    exposure_class: str,
    cqs: int | None = None,
    *,
    short_term: bool = False,
    transactor: bool = False,
    retail_eligible: bool = False,
    defaulted: bool = False,
    default_coverage_ratio: float = 0.0,
    specialised_lending_type: str = "",
    parameters: ParameterStore | pd.DataFrame | None = None,
) -> float:
    """Return the standardised credit-risk weight for one classified exposure."""
    return _f.sa_base_risk_weight(
        exposure_class, cqs, short_term=short_term, transactor=transactor,
        retail_eligible=retail_eligible, defaulted=defaulted,
        default_coverage_ratio=default_coverage_ratio,
        specialised_lending_type=specialised_lending_type, params=_store(parameters),
    )


def real_estate_risk_weight(
    ead: float, property_value: float, property_type: str, ipre: bool,
    counterparty_rw: float, *, senior_liens: float = 0.0, adc: bool = False,
    parameters: ParameterStore | pd.DataFrame | None = None,
) -> tuple[float, list[tuple[str, float, float]]]:
    """Return effective real-estate risk weight and transparent exposure segments."""
    return _f.real_estate_weighted_rw(
        ead=ead, property_value=property_value, property_type=property_type, ipre=ipre,
        counterparty_rw=counterparty_rw, senior_liens=senior_liens, adc=adc,
        params=_store(parameters),
    )


def crm_maturity_factor(t_protection: float, t_exposure: float, *, minimum_t: float = 0.25,
                        maximum_T: float = 5.0) -> float:
    """Return the CRM maturity-mismatch adjustment factor."""
    return _f.crm_maturity_mismatch_factor(t_protection, t_exposure,
                                             minimum_t=minimum_t, maximum_T=maximum_T)


def crm_adjusted_exposure(exposure: float, collateral: float, he: float, hc: float,
                          hfx: float) -> float:
    """Return exposure after comprehensive-method collateral and haircut adjustment."""
    return _f.comprehensive_crm(exposure, collateral, he, hc, hfx)


def irb_asset_correlation(pd: float, *, annual_sales_million: float | None = None,
                          financial_multiplier: bool = False,
                          parameters: ParameterStore | pd.DataFrame | None = None) -> float:
    """Return corporate IRB asset correlation including optional SME adjustment."""
    return _f.irb_correlation(pd, annual_sales_million=annual_sales_million,
                              financial_multiplier=financial_multiplier, params=_store(parameters))


def irb_retail_correlation(pd: float, subclass: str, *,
                           parameters: ParameterStore | pd.DataFrame | None = None) -> float:
    """Return the IRB correlation for the specified retail subclass."""
    return _f.retail_correlation(pd, subclass, params=_store(parameters))


def irb_maturity_coefficient(pd: float, *,
                             parameters: ParameterStore | pd.DataFrame | None = None) -> float:
    """Return the IRB maturity coefficient b(PD)."""
    return _f.irb_maturity_b(pd, params=_store(parameters))


def irb_maturity_factor(pd: float, maturity: float, *,
                        parameters: ParameterStore | pd.DataFrame | None = None) -> float:
    """Return the IRB effective-maturity adjustment factor."""
    return _f.irb_maturity_adjustment(pd, maturity, params=_store(parameters))


def irb_capital_requirement(
    pd: float, lgd: float, correlation: float, maturity: float, *,
    apply_maturity_adjustment: bool = True, defaulted: bool = False, elbe: float = 0.0,
    parameters: ParameterStore | pd.DataFrame | None = None,
) -> float:
    """Return the IRB unexpected-loss capital-requirement rate for one exposure."""
    return _f.irb_k(pd, lgd, correlation, maturity,
                    apply_maturity_adjustment=apply_maturity_adjustment,
                    defaulted=defaulted, elbe=elbe, params=_store(parameters))


def sa_ccr_multiplier_value(V: float, C: float, addon: float, *,
                            parameters: ParameterStore | pd.DataFrame | None = None) -> float:
    """Return the SA-CCR multiplier for value, collateral and aggregate add-on."""
    return _f.sa_ccr_multiplier(V, C, addon, params=_store(parameters))


def sa_ccr_exposure_value(V: float, C: float, addon: float, alpha: float, *,
                          parameters: ParameterStore | pd.DataFrame | None = None
                          ) -> tuple[float, float, float, float]:
    """Return SA-CCR replacement cost, multiplier, PFE and exposure value."""
    return _f.sa_ccr_ead(V, C, addon, alpha=alpha, params=_store(parameters))


def sft_exposure_value(cash_leg: float, security_value: float, security_haircut: float,
                       fx_haircut: float) -> float:
    """Return haircut-adjusted exposure value for a securities-financing transaction."""
    return _f.sft_ead(cash_leg, security_value, security_haircut, fx_haircut)


def securitisation_irb_pool_capital(rwea_pool_irb_ul: float, el_pool_irb: float,
                                    pool_ead: float, *,
                                    parameters: ParameterStore | pd.DataFrame | None = None) -> float:
    """Return SEC-IRBA pool capital ratio K_IRB."""
    return _f.sec_k_irb(rwea_pool_irb_ul, el_pool_irb, pool_ead, params=_store(parameters))


def securitisation_sa_pool_capital(rwea_pool_sa: float, pool_ead: float, *,
                                   parameters: ParameterStore | pd.DataFrame | None = None) -> float:
    """Return SEC-SA pool capital ratio K_SA."""
    return _f.sec_k_sa(rwea_pool_sa, pool_ead, params=_store(parameters))


def securitisation_ssfa_coefficient(ka: float, attachment: float, detachment: float,
                                    p: float) -> float:
    """Return the SSFA exponential tranche coefficient."""
    return _f.ssfa_k(ka, attachment, detachment, p)


def securitisation_ssfa_risk_weight(
    pool_k: float, attachment: float, detachment: float, p: float, floor: float, *,
    parameters: ParameterStore | pd.DataFrame | None = None,
) -> float:
    """Return the floored and capped SSFA securitisation risk weight."""
    return _f.securitisation_ssfa_rw(pool_k, attachment, detachment, p, floor,
                                     params=_store(parameters))


def securitisation_irba_p(
    pool_type: str, senior: bool, effective_number: float, pool_k: float,
    average_lgd: float, tranche_maturity: float, sts: bool, *,
    parameters: ParameterStore | pd.DataFrame | None = None,
) -> tuple[float, float]:
    """Return raw and applicable supervisory p for the SEC-IRBA."""
    return _f.sec_irba_p(pool_type=pool_type, senior=senior, effective_number=effective_number,
                         pool_k=pool_k, average_lgd=average_lgd,
                         tranche_maturity=tranche_maturity, sts=sts, params=_store(parameters))


def securitisation_erba_risk_weight(
    cqs: int, maturity: float, senior: bool, sts: bool, attachment: float,
    detachment: float, *, parameters: ParameterStore | pd.DataFrame | None = None,
) -> float:
    """Return the maturity-interpolated SEC-ERBA risk weight."""
    return _f.sec_erba_rw(cqs, maturity, senior, sts, attachment, detachment,
                          params=_store(parameters))


def securitisation_risk_weight(
    approach: str, pool_k: float, attachment: float, detachment: float, p: float, *,
    sts: bool = False, senior: bool = False, resecuritisation: bool = False, cqs: int = 0,
    parameters: ParameterStore | pd.DataFrame | None = None,
) -> float:
    """Return the approach-specific securitisation risk weight."""
    return _f.securitisation_rw(approach, pool_k, attachment, detachment, p,
                                sts=sts, senior=senior, resecuritisation=resecuritisation,
                                cqs=cqs, params=_store(parameters))


def cva_basic_approach_capital(
    items: Sequence[tuple[float, float, float, float, float, float, float, float, float]], *,
    parameters: ParameterStore | pd.DataFrame | None = None,
) -> float:
    """Return BA-CVA capital for nine-field counterparty and hedge tuples."""
    return _f.ba_cva_capital(items, params=_store(parameters))


def settlement_risk_factor(days_late: int, *,
                           parameters: ParameterStore | pd.DataFrame | None = None) -> float:
    """Return the settlement-risk factor for the number of business days late."""
    return _f.settlement_factor(days_late, params=_store(parameters))


def business_indicator_component(
    il: Sequence[float], ie: Sequence[float], assets: Sequence[float], dividends: Sequence[float],
    oi: Sequence[float], oe: Sequence[float], fi: Sequence[float], fe: Sequence[float],
    trading_pnl: Sequence[float], banking_pnl: Sequence[float], *,
    parameters: ParameterStore | pd.DataFrame | None = None,
) -> tuple[float, float, float, float, float]:
    """Return ILDC, services, financial, business-indicator and BIC amounts."""
    return _f.bic_from_components(il, ie, assets, dividends, oi, oe, fi, fe,
                                  trading_pnl, banking_pnl, params=_store(parameters))


def applicable_output_floor_factor(as_of: date, *, fully_loaded: bool = False,
                                   parameters: ParameterStore | pd.DataFrame | None = None) -> float:
    """Return the transitional or fully-loaded output-floor factor at a date."""
    return _f.output_floor_factor(as_of, fully_loaded, params=_store(parameters))


def apply_output_floor(u_trea: float, s_trea: float, factor: float, *,
                       optional_cap: bool = False, cap_multiplier: float = 1.0
                       ) -> tuple[float, float, bool]:
    """Return final TREA, floor uplift and binding indicator."""
    return _f.output_floor(u_trea, s_trea, factor, optional_cap=optional_cap,
                           cap_multiplier=cap_multiplier)


def npe_unsecured_coverage_factor(year: int, *,
                                  parameters: ParameterStore | pd.DataFrame | None = None) -> float:
    """Return the prudential-backstop factor for an unsecured NPE vintage."""
    return _f.npe_unsecured_factor(year, params=_store(parameters))


def npe_secured_coverage_factor(year: int, *, property_security: bool = True,
                                parameters: ParameterStore | pd.DataFrame | None = None) -> float:
    """Return the prudential-backstop factor for a secured NPE vintage."""
    return _f.npe_secured_factor(year, property_security, params=_store(parameters))


def tier2_eligible_amount(current_amount: float, first_day_amount: float, maturity: date | None,
                          as_of: date, *,
                          parameters: ParameterStore | pd.DataFrame | None = None) -> float:
    """Return eligible Tier-2 amount after final-five-year amortisation."""
    return _f.t2_eligible_amount(current_amount, first_day_amount, maturity, as_of,
                                 params=_store(parameters))


def irrbb_scenario_shock(scenario: str, t: float, parallel: float, short: float, long: float, *,
                         parameters: ParameterStore | pd.DataFrame | None = None) -> float:
    """Return the term-dependent IRRBB shock for one prescribed scenario."""
    return _f.irrbb_shock(scenario, t, parallel, short, long, params=_store(parameters))


def irrbb_shocked_zero_rate(base: float, shock: float, t: float, *,
                            parameters: ParameterStore | pd.DataFrame | None = None) -> float:
    """Return a shocked continuously-compounded zero rate subject to its floor."""
    return _f.shocked_zero_rate(base, shock, t, params=_store(parameters))


def present_value_discount_factor(continuous_zero_rate: float, t: float) -> float:
    """Return the continuous-compounding discount factor exp(-r*t)."""
    return _f.discount_factor(continuous_zero_rate, t)


def aggregate_correlated_capital(capitals: Sequence[float],
                                 correlation: Sequence[Sequence[float]]) -> float:
    """Return square-root aggregation of standalone capital under a correlation matrix."""
    return _f.correlated_capital(capitals, correlation)


def frtb_scenario_correlation(base: float, scenario: str, *,
                              parameters: ParameterStore | pd.DataFrame | None = None) -> float:
    """Return low, medium or high FRTB correlation from a base correlation."""
    params = _store(parameters)
    if scenario == "HIGH":
        return min(params.get("FRTB_CORRELATION", "HIGH_MULTIPLIER") * base,
                   params.get("FRTB_CORRELATION", "HIGH_CAP"))
    if scenario == "LOW":
        return max(params.get("FRTB_CORRELATION", "LOW_LINEAR_MULTIPLIER") * base - 1.0,
                   params.get("FRTB_CORRELATION", "LOW_FLOOR_MULTIPLIER") * base)
    if scenario != "MEDIUM":
        raise ValueError("scenario must be LOW, MEDIUM or HIGH")
    return base


def frtb_quadratic_charge(values: Sequence[float], correlation: float, *,
                          curvature: bool = False) -> float:
    """Return FRTB within-bucket quadratic charge, with optional curvature psi."""
    numeric = [float(value) for value in values]
    total = sum(value * value for value in numeric)
    for i, left in enumerate(numeric):
        for j, right in enumerate(numeric):
            if i == j:
                continue
            psi = 0.0 if curvature and left < 0 and right < 0 else 1.0
            total += (correlation**2 if curvature else correlation) * left * right * psi
    return sqrt(max(total, 0.0))


FORMULA_FUNCTIONS = (
    sa_exposure_value, sa_risk_weight, real_estate_risk_weight, crm_maturity_factor,
    crm_adjusted_exposure, irb_asset_correlation, irb_retail_correlation,
    irb_maturity_coefficient, irb_maturity_factor, irb_capital_requirement,
    sa_ccr_multiplier_value, sa_ccr_exposure_value, sft_exposure_value,
    securitisation_irb_pool_capital, securitisation_sa_pool_capital,
    securitisation_ssfa_coefficient, securitisation_ssfa_risk_weight,
    securitisation_irba_p, securitisation_erba_risk_weight, securitisation_risk_weight,
    cva_basic_approach_capital, settlement_risk_factor, business_indicator_component,
    applicable_output_floor_factor, apply_output_floor, npe_unsecured_coverage_factor,
    npe_secured_coverage_factor, tier2_eligible_amount, irrbb_scenario_shock,
    irrbb_shocked_zero_rate, present_value_discount_factor, aggregate_correlated_capital,
    frtb_scenario_correlation, frtb_quadratic_charge,
)

__all__ = [function.__name__ for function in FORMULA_FUNCTIONS]
