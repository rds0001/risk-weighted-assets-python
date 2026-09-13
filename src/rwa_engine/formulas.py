"""Reine Formeln ohne eingebettete Fach- oder Geschäftsdaten.

Aufsichtsrechtliche Koeffizienten werden explizit aus dem ParameterStore
bezogen. Quoten sind Dezimalzahlen; Rundung erfolgt erst im Reporting.
"""

from __future__ import annotations

from datetime import date
from math import exp, log, sqrt
from statistics import NormalDist
from typing import Sequence

from .parameters import ParameterStore

NORM = NormalDist()
EPSILON = 1e-12


def clip(x: float, lo: float, hi: float) -> float:
    return min(max(float(x), lo), hi)


def normal_cdf(x: float) -> float:
    return NORM.cdf(x)


def normal_ppf(p: float) -> float:
    return NORM.inv_cdf(clip(p, EPSILON, 1.0 - EPSILON))


def sa_ead(
    *,
    gross_carrying_amount: float,
    specific_adjustments: float,
    additional_valuation_adjustments: float,
    other_own_funds_reductions: float,
    committed_undrawn: float,
    annex_i_class: str,
    data_path: str,
    net_carrying_amount_article_111: float | None,
    params: ParameterStore,
) -> tuple[float, float, float]:
    if data_path == "NET_ARTICLE_111":
        if net_carrying_amount_article_111 is None:
            raise ValueError("Nettodatenpfad verlangt net_carrying_amount_article_111")
        ead_on = max(float(net_carrying_amount_article_111), 0.0)
    else:
        ead_on = max(
            float(gross_carrying_amount)
            - float(specific_adjustments)
            - float(additional_valuation_adjustments)
            - float(other_own_funds_reductions),
            0.0,
        )
    ccf = params.get("SA_CCF", annex_i_class)
    ead_off = max(float(committed_undrawn) - float(specific_adjustments), 0.0) * ccf
    return ead_on, ead_off, ead_on + ead_off


def sa_base_risk_weight(
    exposure_class: str,
    cqs: int | None,
    *,
    short_term: bool,
    transactor: bool,
    retail_eligible: bool,
    defaulted: bool,
    default_coverage_ratio: float,
    specialised_lending_type: str,
    params: ParameterStore,
) -> float:
    if defaulted:
        threshold = params.get("SA_RW_DEFAULT", "COVERAGE_THRESHOLD")
        return params.get(
            "SA_RW_DEFAULT", "ABOVE_THRESHOLD" if default_coverage_ratio >= threshold else "BELOW_THRESHOLD"
        )
    if specialised_lending_type:
        return params.get("SPECIALISED_RW", specialised_lending_type)
    if exposure_class in {"RETAIL", "RETAIL_REAL_ESTATE"}:
        kind = "RETAIL_TRANSACTOR" if transactor else "RETAIL_ELIGIBLE" if retail_eligible else "RETAIL_OTHER"
        return params.get("SA_RW_FIXED", kind)
    if exposure_class in {"CENTRAL_BANK", "CENTRAL_GOVERNMENT"}:
        exposure_class = "CENTRAL_GOVERNMENT"
    key = "SA_RW_SHORT" if exposure_class == "INSTITUTION" and short_term else "SA_RW"
    quality = f"CQS_{int(cqs)}" if cqs else "UNRATED"
    if params.has(key, exposure_class, quality):
        return params.get(key, exposure_class, quality)
    fixed = exposure_class if params.has("SA_RW_FIXED", exposure_class) else "OTHER"
    return params.get("SA_RW_FIXED", fixed)


def real_estate_weighted_rw(
    *,
    ead: float,
    property_value: float,
    property_type: str,
    ipre: bool,
    counterparty_rw: float,
    senior_liens: float,
    adc: bool,
    params: ParameterStore,
) -> tuple[float, list[tuple[str, float, float]]]:
    if ead <= 0:
        return 0.0, []
    if adc:
        rw = params.get("RE_SPLIT", "ADC_RW")
        return rw, [("ADC", ead, rw)]
    value = max(float(property_value), EPSILON)
    etv = (float(ead) + float(senior_liens)) / value
    if ipre:
        if property_type == "RESIDENTIAL":
            bounds = [params.get("RE_IPRE_BOUND", property_type, f"BAND_{i}") for i in range(1, 6)]
            labels = ["ETV_LE_050", "ETV_LE_060", "ETV_LE_080", "ETV_LE_090", "ETV_LE_100"]
            band = next((label for bound, label in zip(bounds, labels) if etv <= bound), "ETV_GT_100")
        else:
            bounds = [params.get("RE_IPRE_BOUND", property_type, f"BAND_{i}") for i in range(1, 3)]
            band = "ETV_LE_060" if etv <= bounds[0] else "ETV_LE_080" if etv <= bounds[1] else "ETV_GT_080"
        rw = params.get("RE_IPRE_RW", property_type, band)
        return rw, [("WHOLE_LOAN", ead, rw)]
    capacity = max(params.get("RE_SPLIT", "PRIVILEGED_VALUE_SHARE") * value - float(senior_liens), 0.0)
    privileged = min(float(ead), capacity)
    remainder = max(float(ead) - privileged, 0.0)
    privileged_rw = params.get("RE_SPLIT", f"{property_type}_RW")
    segments = [("PRIVILEGED", privileged, privileged_rw), ("REMAINDER", remainder, counterparty_rw)]
    return sum(amount * rw for _, amount, rw in segments) / ead, segments


def crm_maturity_mismatch_factor(
    t_protection: float, t_exposure: float, *, minimum_t: float, maximum_T: float
) -> float:
    t = min(max(t_protection, 0.0), max(t_exposure, 0.0))
    T = min(max(t_exposure, 0.0), maximum_T)
    if t < minimum_t or T <= minimum_t:
        return 0.0
    return clip((t - minimum_t) / (T - minimum_t), 0.0, 1.0)


def comprehensive_crm(exposure: float, collateral: float, he: float, hc: float, hfx: float) -> float:
    return max(exposure * (1.0 + he) - collateral * (1.0 - hc - hfx), 0.0)


def irb_correlation(
    pd: float, *, annual_sales_million: float | None, financial_multiplier: bool, params: ParameterStore
) -> float:
    decay = params.get("IRB_CORP", "DECAY")
    weight = (1.0 - exp(-decay * pd)) / (1.0 - exp(-decay))
    result = params.get("IRB_CORP", "R_LOW") * weight + params.get("IRB_CORP", "R_HIGH") * (1.0 - weight)
    if annual_sales_million is not None:
        low, high = params.get("IRB_CORP", "SME_SALES_MIN_M"), params.get("IRB_CORP", "SME_SALES_MAX_M")
        sales = clip(annual_sales_million, low, high)
        result -= params.get("IRB_CORP", "SME_ADJUSTMENT") * (1.0 - (sales - low) / (high - low))
    return result * (params.get("IRB_CORP", "FINANCIAL_MULTIPLIER") if financial_multiplier else 1.0)


def retail_correlation(pd: float, subclass: str, *, params: ParameterStore) -> float:
    if subclass == "RETAIL_RESIDENTIAL":
        return params.get("IRB_RETAIL", "RESIDENTIAL_R")
    if subclass == "RETAIL_QRRE":
        return params.get("IRB_RETAIL", "QRRE_R")
    decay = params.get("IRB_RETAIL", "DECAY")
    weight = (1.0 - exp(-decay * pd)) / (1.0 - exp(-decay))
    return params.get("IRB_RETAIL", "R_LOW") * weight + params.get("IRB_RETAIL", "R_HIGH") * (1.0 - weight)


def irb_maturity_b(pd: float, *, params: ParameterStore) -> float:
    return (params.get("IRB_MATURITY", "A") - params.get("IRB_MATURITY", "B") * log(max(pd, EPSILON))) ** 2


def irb_maturity_adjustment(pd: float, maturity: float, *, params: ParameterStore) -> float:
    b = irb_maturity_b(pd, params=params)
    m = clip(maturity, params.get("IRB_MATURITY", "MIN_YEARS"), params.get("IRB_MATURITY", "MAX_YEARS"))
    return (1.0 + (m - params.get("IRB_MATURITY", "CENTER")) * b) / (
        1.0 - params.get("IRB_MATURITY", "DENOMINATOR_FACTOR") * b
    )


def irb_k(
    pd: float,
    lgd: float,
    correlation: float,
    maturity: float,
    *,
    apply_maturity_adjustment: bool,
    defaulted: bool,
    elbe: float,
    params: ParameterStore,
) -> float:
    if defaulted or pd >= 1.0:
        return max(lgd - elbe, 0.0)
    if pd <= 0:
        return 0.0
    z = normal_ppf(pd) / sqrt(1.0 - correlation) + sqrt(correlation / (1.0 - correlation)) * normal_ppf(
        params.get("IRB", "CONFIDENCE_LEVEL")
    )
    ul = lgd * normal_cdf(z) - pd * lgd
    ma = irb_maturity_adjustment(pd, maturity, params=params) if apply_maturity_adjustment else 1.0
    return max(ul * ma, 0.0)


def sa_ccr_multiplier(V: float, C: float, addon: float, *, params: ParameterStore) -> float:
    if addon <= 0:
        return 1.0
    floor = params.get("SA_CCR", "MULTIPLIER_FLOOR")
    return min(1.0, floor + (1.0 - floor) * exp((V - C) / (2.0 * (1.0 - floor) * addon)))


def sa_ccr_ead(
    V: float, C: float, addon: float, *, alpha: float, params: ParameterStore
) -> tuple[float, float, float, float]:
    rc = max(V - C, 0.0)
    multiplier = sa_ccr_multiplier(V, C, addon, params=params)
    pfe = multiplier * addon
    return rc, multiplier, pfe, alpha * (rc + pfe)


def sft_ead(cash_leg: float, security_value: float, security_haircut: float, fx_haircut: float) -> float:
    return max(cash_leg - security_value * (1.0 - security_haircut - fx_haircut), 0.0)


def sec_k_irb(
    rwea_pool_irb_ul: float, el_pool_irb: float, pool_ead: float, *, params: ParameterStore
) -> float:
    return (
        (params.get("SEC", "CAPITAL_RATE") * rwea_pool_irb_ul + el_pool_irb) / pool_ead if pool_ead else 0.0
    )


def sec_k_sa(rwea_pool_sa: float, pool_ead: float, *, params: ParameterStore) -> float:
    return params.get("SEC", "CAPITAL_RATE") * rwea_pool_sa / pool_ead if pool_ead else 0.0


def ssfa_k(ka: float, attachment: float, detachment: float, p: float) -> float:
    if ka <= 0:
        return 0.0
    a = -1.0 / (p * ka)
    upper, lower = detachment - ka, max(attachment - ka, 0.0)
    return (
        exp(a * upper)
        if abs(upper - lower) < EPSILON
        else (exp(a * upper) - exp(a * lower)) / (a * (upper - lower))
    )


def securitisation_ssfa_rw(
    pool_k: float, attachment: float, detachment: float, p: float, floor: float, *, params: ParameterStore
) -> float:
    """SSFA einschließlich einer den K_A-Punkt schneidenden Tranche."""
    cap = params.get("SEC", "RW_CAP")
    mult = params.get("RWA_MULTIPLIER", "PILLAR1")
    if not 0.0 <= attachment < detachment <= 1.0:
        raise ValueError("Verbriefung verlangt 0 <= A < D <= 1")
    if detachment <= pool_k:
        rw = cap
    elif attachment >= pool_k:
        rw = mult * ssfa_k(pool_k, attachment, detachment, p)
    else:
        thickness = detachment - attachment
        rw = ((pool_k - attachment) / thickness) * cap + ((detachment - pool_k) / thickness) * mult * ssfa_k(
            pool_k, attachment, detachment, p
        )
    return clip(rw, floor, cap)


def sec_irba_p(
    *,
    pool_type: str,
    senior: bool,
    effective_number: float,
    pool_k: float,
    average_lgd: float,
    tranche_maturity: float,
    sts: bool,
    params: ParameterStore,
) -> tuple[float, float]:
    threshold = params.get("SEC_IRBA", "GRANULARITY_THRESHOLD")
    retail = pool_type == "RETAIL"
    granular = effective_number >= threshold
    if retail and not granular:
        raise ValueError(f"SEC-IRBA Retail-Koeffizienten verlangen N >= {threshold:g}")
    key = ("RETAIL" if retail else "NON_RETAIL") + ("_SENIOR" if senior else "_NONSENIOR") + "_NGE25"
    if not retail and not granular:
        key = key.replace("NGE25", "NLT25")
    coefficients = {letter: params.get("SEC_IRBA_COEFF", key, letter) for letter in "ABCDE"}
    raw = (
        coefficients["A"]
        + coefficients["B"] / effective_number
        + coefficients["C"] * pool_k
        + coefficients["D"] * average_lgd
        + coefficients["E"] * tranche_maturity
    )
    floor = params.get("SEC_SSFA", "P_FLOOR")
    p = max(floor, params.get("SEC_SSFA", "STS_P_MULTIPLIER") * raw if sts else raw)
    return raw, p


def sec_erba_rw(
    cqs: int,
    maturity: float,
    senior: bool,
    sts: bool,
    attachment: float,
    detachment: float,
    *,
    params: ParameterStore,
) -> float:
    quality = str(cqs) if params.has("SEC_ERBA_LONG", str(cqs), "NORMAL_SENIOR_1Y") else "OTHER"
    prefix = "STS" if sts else "NORMAL"
    rank = "SENIOR" if senior else "NONSENIOR"
    one = params.get("SEC_ERBA_LONG", quality, f"{prefix}_{rank}_1Y")
    five = params.get("SEC_ERBA_LONG", quality, f"{prefix}_{rank}_5Y")
    minimum = params.get("SEC_ERBA", "MATURITY_MIN")
    maximum = params.get("SEC_ERBA", "MATURITY_MAX")
    bounded = clip(maturity, minimum, maximum)
    rw = one + (bounded - minimum) / (maximum - minimum) * (five - one)
    if not senior:
        thickness = detachment - attachment
        rw *= 1.0 - min(thickness, params.get("SEC_ERBA", "THICKNESS_CAP"))
        hypothetical_one = params.get("SEC_ERBA_LONG", quality, f"{prefix}_SENIOR_1Y")
        hypothetical_five = params.get("SEC_ERBA_LONG", quality, f"{prefix}_SENIOR_5Y")
        hypothetical = hypothetical_one + (bounded - minimum) / (maximum - minimum) * (
            hypothetical_five - hypothetical_one
        )
        rw = max(rw, params.get("SEC_FLOOR", "NON_STS"), hypothetical)
    return min(rw, params.get("SEC", "RW_CAP"))


def securitisation_rw(
    approach: str,
    pool_k: float,
    attachment: float,
    detachment: float,
    p: float,
    *,
    sts: bool,
    senior: bool,
    resecuritisation: bool,
    cqs: int,
    params: ParameterStore,
) -> float:
    if approach in {"SEC_IRBA", "SEC_SA"}:
        floor_key = (
            "RESECURITISATION"
            if resecuritisation
            else "STS"
            if sts and senior
            else "STS_NONSENIOR"
            if sts
            else "NON_STS"
        )
        floor = params.get("SEC_FLOOR", floor_key)
        return securitisation_ssfa_rw(pool_k, attachment, detachment, p, floor, params=params)
    return sec_erba_rw(
        cqs, params.get("SEC_ERBA", "MATURITY_MIN"), True, sts, attachment, detachment, params=params
    )


def ba_cva_capital(
    items: Sequence[tuple[float, float, float, float, float, float, float, float, float]],
    *,
    params: ParameterStore,
) -> float:
    rho = params.get("BA_CVA", "RHO")
    discount_rate = params.get("BA_CVA", "DISCOUNT_RATE")
    alpha = params.get("BA_CVA", "ALPHA")
    scva_values = []
    net_values = []
    index_hedge_total = 0.0
    hedge_mismatch = 0.0
    for (
        rw,
        maturity,
        ead,
        single,
        single_maturity,
        hedge_correlation,
        index,
        index_maturity,
        index_rw,
    ) in items:
        df = (1.0 - exp(-discount_rate * maturity)) / (discount_rate * maturity) if maturity > 0 else 1.0
        scva = rw * maturity * ead * df / alpha
        single_df = (
            (1.0 - exp(-discount_rate * single_maturity)) / (discount_rate * single_maturity)
            if single_maturity > 0
            else 1.0
        )
        index_df = (
            (1.0 - exp(-discount_rate * index_maturity)) / (discount_rate * index_maturity)
            if index_maturity > 0
            else 1.0
        )
        hma = rw * single_maturity * single * single_df / alpha
        single_hedge = hedge_correlation * hma
        index_hedge = index_rw * index_maturity * index * index_df / alpha
        scva_values.append(scva)
        net_values.append(scva - single_hedge)
        index_hedge_total += index_hedge
        hedge_mismatch += max(hma**2 - single_hedge**2, 0.0)
    unhedged = sqrt((rho * sum(scva_values)) ** 2 + (1.0 - rho**2) * sum(x**2 for x in scva_values))
    hedged = sqrt(
        max(
            (rho * sum(net_values) - index_hedge_total) ** 2
            + (1.0 - rho**2) * sum(x**2 for x in net_values)
            + hedge_mismatch,
            0.0,
        )
    )
    unhedged_weight = params.get("BA_CVA", "UNHEDGED_WEIGHT")
    return (
        unhedged_weight * unhedged + params.get("BA_CVA", "HEDGED_WEIGHT") * (1.0 - unhedged_weight) * hedged
    )


def settlement_factor(days_late: int, *, params: ParameterStore) -> float:
    bounds = [int(params.get("SETTLEMENT_BOUND", f"BAND_{i}")) for i in range(1, 5)]
    band = (
        "DAYS_0_4"
        if days_late <= bounds[0]
        else "DAYS_5_15"
        if days_late <= bounds[1]
        else "DAYS_16_30"
        if days_late <= bounds[2]
        else "DAYS_31_45"
        if days_late <= bounds[3]
        else "DAYS_46_PLUS"
    )
    return params.get("SETTLEMENT_FACTOR", band)


def bic_from_components(
    il: Sequence[float],
    ie: Sequence[float],
    assets: Sequence[float],
    dividends: Sequence[float],
    oi: Sequence[float],
    oe: Sequence[float],
    fi: Sequence[float],
    fe: Sequence[float],
    trading_pnl: Sequence[float],
    banking_pnl: Sequence[float],
    *,
    params: ParameterStore,
) -> tuple[float, float, float, float, float]:
    def average(values: Sequence[float]) -> float:
        return sum(values) / len(values)
    ildc = min(
        average([abs(a - b) for a, b in zip(il, ie)]), params.get("BIC", "ASSET_CAP") * average(assets)
    ) + average(dividends)
    sc = max(average(oi), average(oe)) + max(average(fi), average(fe))
    fc = average([abs(x) for x in trading_pnl]) + average([abs(x) for x in banking_pnl])
    bi = ildc + sc + fc
    billion = params.get("UNIT_SCALE", "EUR_BILLION")
    x, first, second = (
        bi / billion,
        params.get("BIC", "BUCKET_1_LIMIT_BN"),
        params.get("BIC", "BUCKET_2_LIMIT_BN"),
    )
    bic = (
        params.get("BIC", "COEFFICIENT_1") * min(x, first)
        + params.get("BIC", "COEFFICIENT_2") * min(max(x - first, 0.0), second - first)
        + params.get("BIC", "COEFFICIENT_3") * max(x - second, 0.0)
    ) * billion
    return ildc, sc, fc, bi, bic


def output_floor_factor(as_of: date, fully_loaded: bool, *, params: ParameterStore) -> float:
    if fully_loaded:
        return params.get("OUTPUT_FLOOR", "FULLY_LOADED")
    year = str(as_of.year)
    return params.get("OUTPUT_FLOOR", year if params.has("OUTPUT_FLOOR", year) else "FULLY_LOADED")


def output_floor(
    u_trea: float, s_trea: float, factor: float, *, optional_cap: bool, cap_multiplier: float
) -> tuple[float, float, bool]:
    uncapped = max(u_trea, factor * s_trea)
    final = min(uncapped, cap_multiplier * u_trea) if optional_cap else uncapped
    return final, final - u_trea, final > u_trea


def npe_unsecured_factor(year: int, *, params: ParameterStore) -> float:
    last = int(params.get("NPE_MILESTONE", "UNSECURED_LAST_INITIAL_YEAR"))
    return params.get("NPE_UNSECURED", f"YEAR_{year}" if year <= last else f"YEAR_{last + 1}_PLUS")


def npe_secured_factor(year: int, property_security: bool, *, params: ParameterStore) -> float:
    key = "NPE_SECURED_PROPERTY" if property_security else "NPE_SECURED_OTHER"
    initial = int(params.get("NPE_MILESTONE", "SECURED_INITIAL_YEARS"))
    last = int(
        params.get("NPE_MILESTONE", "PROPERTY_LAST_YEAR" if property_security else "OTHER_SECURED_LAST_YEAR")
    )
    band = (
        f"YEAR_1_{initial}"
        if year <= initial
        else f"YEAR_{year}"
        if year <= last
        else f"YEAR_{last + 1}_PLUS"
    )
    return params.get(key, band)


def t2_eligible_amount(
    current_amount: float,
    first_day_amount: float,
    maturity: date | None,
    as_of: date,
    *,
    params: ParameterStore,
) -> float:
    if maturity is None:
        return current_amount
    remaining = max((maturity - as_of).days, 0)
    period_days = round(
        params.get("T2", "AMORTISATION_YEARS") * params.get("TIME_CONVENTION", "DAYS_PER_YEAR")
    )
    return current_amount if remaining > period_days else first_day_amount / period_days * remaining


def irrbb_shock(
    scenario: str, t: float, parallel: float, short: float, long: float, *, params: ParameterStore
) -> float:
    decay = params.get("IRRBB_SHOCK", "DECAY_YEARS")
    short_component, long_component = short * exp(-t / decay), long * (1.0 - exp(-t / decay))
    return {
        "PARALLEL_UP": parallel,
        "PARALLEL_DOWN": -parallel,
        "SHORT_UP": short_component,
        "SHORT_DOWN": -short_component,
        "STEEPENER": params.get("IRRBB_SHOCK", "STEEPENER_SHORT_WEIGHT") * abs(short_component)
        + params.get("IRRBB_SHOCK", "STEEPENER_LONG_WEIGHT") * abs(long_component),
        "FLATTENER": params.get("IRRBB_SHOCK", "FLATTENER_SHORT_WEIGHT") * abs(short_component)
        + params.get("IRRBB_SHOCK", "FLATTENER_LONG_WEIGHT") * abs(long_component),
    }[scenario]


def shocked_zero_rate(base: float, shock: float, t: float, *, params: ParameterStore) -> float:
    floor = min(params.get("IRRBB_FLOOR", "BASE") + params.get("IRRBB_FLOOR", "SLOPE") * t, 0.0)
    return max(base + shock, min(base, floor))


def discount_factor(continuous_zero_rate: float, t: float) -> float:
    return exp(-continuous_zero_rate * t)


def correlated_capital(capitals: Sequence[float], correlation: Sequence[Sequence[float]]) -> float:
    total = sum(ci * correlation[i][j] * cj for i, ci in enumerate(capitals) for j, cj in enumerate(capitals))
    return sqrt(max(total, 0.0))
