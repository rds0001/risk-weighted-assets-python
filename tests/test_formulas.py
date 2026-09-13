from datetime import date
from math import isclose

import pandas as pd
import pytest

from rwa_engine import formulas as f
from rwa_engine.config_io import load_regulatory_config, regulatory_parameter_items
from rwa_engine.parameters import ParameterStore


@pytest.fixture(scope="module")
def params() -> ParameterStore:
    config = load_regulatory_config("daten/konfiguration/regulatory/crr3_eu_2026_v1.yaml")
    rows = [
        {
            "parameter_key": item["key"],
            "dimension_1": str(item.get("d1", "")),
            "dimension_2": str(item.get("d2", "")),
            "parameter_value": item["value"],
        }
        for item in regulatory_parameter_items(config)
    ]
    return ParameterStore(pd.DataFrame(rows))


@pytest.mark.parametrize(
    "cls,expected", [("CLASS_1", 1.0), ("CLASS_2", 0.5), ("CLASS_3", 0.4), ("CLASS_4", 0.2), ("CLASS_5", 0.1)]
)
def test_sa_ccf_classes(cls, expected, params):
    _, off, total = f.sa_ead(
        gross_carrying_amount=100,
        specific_adjustments=0,
        additional_valuation_adjustments=0,
        other_own_funds_reductions=0,
        committed_undrawn=50,
        annex_i_class=cls,
        data_path="GROSS",
        net_carrying_amount_article_111=None,
        params=params,
    )
    assert off == 50 * expected
    assert total == 100 + off


def test_sa_net_path_does_not_double_deduct(params):
    on, _, _ = f.sa_ead(
        gross_carrying_amount=100,
        specific_adjustments=20,
        additional_valuation_adjustments=0,
        other_own_funds_reductions=0,
        committed_undrawn=0,
        annex_i_class="CLASS_1",
        data_path="NET_ARTICLE_111",
        net_carrying_amount_article_111=80,
        params=params,
    )
    assert on == 80


def test_irb_reference_formula(params):
    r = f.irb_correlation(0.01, annual_sales_million=None, financial_multiplier=False, params=params)
    k = f.irb_k(0.01, 0.40, r, 2.5, apply_maturity_adjustment=True, defaulted=False, elbe=0, params=params)
    assert isclose(r, 0.192783679165516, rel_tol=1e-12)
    assert isclose(k, 0.06564750321212547, rel_tol=1e-12)
    assert isclose(params.get("RWA_MULTIPLIER", "PILLAR1") * k, 0.8205937901515684, rel_tol=1e-12)


def test_irb_retail_has_no_maturity_adjustment(params):
    r = f.retail_correlation(0.01, "RETAIL_RESIDENTIAL", params=params)
    args = dict(
        pd=0.01,
        lgd=0.20,
        correlation=r,
        apply_maturity_adjustment=False,
        defaulted=False,
        elbe=0,
        params=params,
    )
    assert f.irb_k(maturity=1, **args) == f.irb_k(maturity=5, **args)


def test_sa_ccr_identity(params):
    rc, mult, pfe, ead = f.sa_ccr_ead(10, 4, 20, alpha=params.get("SA_CCR", "ALPHA"), params=params)
    assert rc == 6
    assert params.get("SA_CCR", "MULTIPLIER_FLOOR") <= mult <= 1
    assert isclose(ead, params.get("SA_CCR", "ALPHA") * (rc + pfe))


def test_ssfa_and_securitisation_caps(params):
    rw = f.securitisation_rw(
        "SEC_SA", 0.08, 0.10, 0.20, 0.5, sts=False, senior=False, resecuritisation=False, cqs=6, params=params
    )
    assert params.get("SEC_FLOOR", "NON_STS") <= rw <= params.get("SEC", "RW_CAP")
    assert f.securitisation_rw(
        "SEC_SA", 0.08, 0.01, 0.05, 0.5, sts=False, senior=False, resecuritisation=False, cqs=6, params=params
    ) == params.get("SEC", "RW_CAP")


def test_ssfa_crossing_tranche_blends_1250_and_ssfa(params):
    rw = f.securitisation_ssfa_rw(0.08, 0.05, 0.15, 0.5, params.get("SEC_FLOOR", "NON_STS"), params=params)
    assert params.get("SEC_FLOOR", "NON_STS") < rw < params.get("SEC", "RW_CAP")
    with pytest.raises(ValueError):
        f.securitisation_ssfa_rw(0.08, 0.20, 0.10, 0.5, 0.15, params=params)


def test_sec_erba_long_term_interpolation_and_thickness(params):
    senior = f.sec_erba_rw(1, 3.0, True, False, 0, 0.1, params=params)
    non_senior = f.sec_erba_rw(1, 3.0, False, False, 0, 0.1, params=params)
    assert isclose(senior, 0.175)
    assert non_senior >= senior


def test_ba_cva_single_counterparty_golden_case(params):
    rw, maturity, ead = 0.05, 2.0, 1_000_000
    capital = f.ba_cva_capital([(rw, maturity, ead, 0, 0, 0, 0, 0, 0)], params=params)
    discount_rate = params.get("BA_CVA", "DISCOUNT_RATE")
    discount = (1 - __import__("math").exp(-discount_rate * maturity)) / (discount_rate * maturity)
    scva = rw * maturity * ead * discount / params.get("BA_CVA", "ALPHA")
    unhedged_weight = params.get("BA_CVA", "UNHEDGED_WEIGHT")
    expected = (unhedged_weight + params.get("BA_CVA", "HEDGED_WEIGHT") * (1 - unhedged_weight)) * scva
    assert isclose(capital, expected, rel_tol=1e-12)


def test_bic_three_buckets(params):
    _, _, _, bi, bic = f.bic_from_components(
        [2e9] * 3,
        [1e9] * 3,
        [40e9] * 3,
        [0] * 3,
        [0.2e9] * 3,
        [0.2e9] * 3,
        [0.3e9] * 3,
        [0.1e9] * 3,
        [0] * 3,
        [0] * 3,
        params=params,
    )
    assert bi == 1.4e9
    assert bic == 0.12e9 + 0.15 * 0.4e9


@pytest.mark.parametrize(
    "year,factor", [(2025, 0.5), (2026, 0.55), (2027, 0.6), (2028, 0.65), (2029, 0.7), (2030, 0.725)]
)
def test_output_floor_transition(year, factor, params):
    assert f.output_floor_factor(date(year, 12, 31), False, params=params) == factor


def test_output_floor_binding(params):
    trea, uplift, binding = f.output_floor(
        100, 200, 0.725, optional_cap=False, cap_multiplier=params.get("OUTPUT_FLOOR", "OPTIONAL_CAP")
    )
    assert trea == 145 and uplift == 45 and binding


def test_npe_factors(params):
    assert [f.npe_unsecured_factor(y, params=params) for y in [1, 2, 3, 4]] == [0, 0, 0.35, 1]
    assert [f.npe_secured_factor(y, True, params=params) for y in [4, 5, 6, 7, 8, 9, 10]] == [
        0.25,
        0.35,
        0.55,
        0.70,
        0.80,
        0.85,
        1,
    ]


def test_irrbb_shock_shapes(params):
    assert f.irrbb_shock("PARALLEL_UP", 10, 0.02, 0.025, 0.01, params=params) == 0.02
    assert f.irrbb_shock("SHORT_UP", 0.1, 0.02, 0.025, 0.01, params=params) > f.irrbb_shock(
        "SHORT_UP", 20, 0.02, 0.025, 0.01, params=params
    )
    assert f.shocked_zero_rate(-0.03, -0.02, 1, params=params) >= -0.03


def test_correlated_capital():
    assert isclose(f.correlated_capital([3, 4], [[1, 0], [0, 1]]), 5)
    assert isclose(f.correlated_capital([3, 4], [[1, 1], [1, 1]]), 7)
