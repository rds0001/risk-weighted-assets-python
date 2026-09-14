"""Contract tests for the granular bank-analyst API."""

from __future__ import annotations

import inspect
from datetime import date

import pandas as pd
import pytest

import rwa_engine as rwa
from rwa_engine.formula_api import FORMULA_FUNCTIONS
from rwa_engine.synthetic import generate_synthetic_tables


@pytest.fixture(scope="module")
def tables():
    return generate_synthetic_tables(bank_profile="KSA_BANK", seed=929)


@pytest.fixture(scope="module")
def result(tables):
    return rwa.calculate_tables(tables, run_id="GRANULAR-API-TEST")


def test_exactly_34_public_documented_formulae_execute():
    calls = {
        "sa_exposure_value": lambda: rwa.sa_exposure_value(100, "CLASS_2", committed_undrawn=40),
        "sa_risk_weight": lambda: rwa.sa_risk_weight("CENTRAL_GOVERNMENT", 1),
        "real_estate_risk_weight": lambda: rwa.real_estate_risk_weight(80, 100, "RESIDENTIAL", True, 1),
        "crm_maturity_factor": lambda: rwa.crm_maturity_factor(2, 5),
        "crm_adjusted_exposure": lambda: rwa.crm_adjusted_exposure(100, 80, .1, .05, .08),
        "irb_asset_correlation": lambda: rwa.irb_asset_correlation(.01),
        "irb_retail_correlation": lambda: rwa.irb_retail_correlation(.01, "OTHER_RETAIL"),
        "irb_maturity_coefficient": lambda: rwa.irb_maturity_coefficient(.01),
        "irb_maturity_factor": lambda: rwa.irb_maturity_factor(.01, 2.5),
        "irb_capital_requirement": lambda: rwa.irb_capital_requirement(.01, .4, .2, 2.5),
        "sa_ccr_multiplier_value": lambda: rwa.sa_ccr_multiplier_value(10, 4, 20),
        "sa_ccr_exposure_value": lambda: rwa.sa_ccr_exposure_value(10, 4, 20, 1.4),
        "sft_exposure_value": lambda: rwa.sft_exposure_value(100, 90, .1, .08),
        "securitisation_irb_pool_capital": lambda: rwa.securitisation_irb_pool_capital(1000, 20, 2000),
        "securitisation_sa_pool_capital": lambda: rwa.securitisation_sa_pool_capital(1000, 2000),
        "securitisation_ssfa_coefficient": lambda: rwa.securitisation_ssfa_coefficient(.08, .1, .2, .5),
        "securitisation_ssfa_risk_weight": lambda: rwa.securitisation_ssfa_risk_weight(.08, .1, .2, .5, .15),
        "securitisation_irba_p": lambda: rwa.securitisation_irba_p("NON_RETAIL", True, 30, .08, .4, 3, False),
        "securitisation_erba_risk_weight": lambda: rwa.securitisation_erba_risk_weight(3, 3, False, False, .1, .3),
        "securitisation_risk_weight": lambda: rwa.securitisation_risk_weight("SEC_SA", .08, .1, .2, .5),
        "cva_basic_approach_capital": lambda: rwa.cva_basic_approach_capital([(.05, 2, 1e6, 0, 0, 0, 0, 0, 0)]),
        "settlement_risk_factor": lambda: rwa.settlement_risk_factor(20),
        "business_indicator_component": lambda: rwa.business_indicator_component(
            [2e9] * 3, [1e9] * 3, [40e9] * 3, [0] * 3, [.2e9] * 3,
            [.2e9] * 3, [.3e9] * 3, [.1e9] * 3, [0] * 3, [0] * 3,
        ),
        "applicable_output_floor_factor": lambda: rwa.applicable_output_floor_factor(date(2026, 12, 31)),
        "apply_output_floor": lambda: rwa.apply_output_floor(100, 180, .725),
        "npe_unsecured_coverage_factor": lambda: rwa.npe_unsecured_coverage_factor(3),
        "npe_secured_coverage_factor": lambda: rwa.npe_secured_coverage_factor(7, property_security=True),
        "tier2_eligible_amount": lambda: rwa.tier2_eligible_amount(100, 100, date(2028, 8, 31), date(2026, 8, 31)),
        "irrbb_scenario_shock": lambda: rwa.irrbb_scenario_shock("PARALLEL_UP", 5, .02, .025, .01),
        "irrbb_shocked_zero_rate": lambda: rwa.irrbb_shocked_zero_rate(.01, -.02, 1),
        "present_value_discount_factor": lambda: rwa.present_value_discount_factor(.03, 5),
        "aggregate_correlated_capital": lambda: rwa.aggregate_correlated_capital([3, 4], [[1, 0], [0, 1]]),
        "frtb_scenario_correlation": lambda: rwa.frtb_scenario_correlation(.25, "HIGH"),
        "frtb_quadratic_charge": lambda: rwa.frtb_quadratic_charge([1, -2], .5),
    }
    assert len(FORMULA_FUNCTIONS) == len(calls) == 34
    assert set(calls) == {function.__name__ for function in FORMULA_FUNCTIONS}
    assert all(name in rwa.__all__ for name in calls)
    assert all(inspect.getdoc(function) for function in FORMULA_FUNCTIONS)
    assert all(calls[name]() is not None for name in calls)


def test_parameter_control_is_non_mutating_exact_and_audited(tables):
    original = rwa.regulatory_parameter("RWA_MULTIPLIER", "PILLAR1",
                                        parameters=rwa.regulatory_parameters(tables))
    override = pd.DataFrame([{
        "parameter_key": "RWA_MULTIPLIER", "dimension_1": "PILLAR1",
        "dimension_2": "", "parameter_value": 13.0,
    }])
    changed = rwa.override_regulatory_parameters(tables, override, "Sensitivity", "Model Risk")
    assert original == 12.5
    assert rwa.regulatory_parameter("RWA_MULTIPLIER", "PILLAR1",
                                    parameters=rwa.regulatory_parameters(changed)) == 13
    assert rwa.regulatory_parameter("RWA_MULTIPLIER", "PILLAR1",
                                    parameters=rwa.regulatory_parameters(tables)) == 12.5
    assert rwa.parameter_overrides(changed).iloc[0].to_dict() == {
        "sequence": 1, "parameter_key": "RWA_MULTIPLIER", "dimension_1": "PILLAR1",
        "dimension_2": "", "old_value": 12.5, "new_value": 13.0,
        "reason": "Sensitivity", "approved_by": "Model Risk",
    }
    with pytest.raises(rwa.ConfigurationError, match="reason and approved_by"):
        rwa.override_regulatory_parameters(tables, override, "", "Model Risk")


def test_granular_result_views_and_nine_domains(result):
    assert len(result.parallel_metrics) == 63
    assert len(result.parallel_results) == 34
    assert rwa.failed_controls(result).empty
    assert list(rwa.compare_calculation_views(result)) == [
        "metric", "applied", "fully_loaded", "difference"
    ]
    analyses = (
        rwa.analyze_credit_risk(result), rwa.analyze_counterparty_risk(result),
        rwa.analyze_securitisation(result), rwa.analyze_market_risk(result),
        rwa.analyze_operational_risk(result), rwa.analyze_output_floor(result),
        rwa.analyze_capital_adequacy(result), rwa.analyze_irrbb(result), rwa.analyze_icaap(result),
    )
    assert all(isinstance(value, rwa.DomainAnalysis) for value in analyses)
    assert all(not value.metrics.empty for value in analyses)
    assert rwa.rwa_metric(result, "TREA") == result.metrics["TREA"]
    pd.testing.assert_frame_equal(rwa.rwa_result_table(result, "Capital_Stack"),
                                  result.results["Capital_Stack"])


def test_rule_schema_snapshot_and_documentation_surface(tables):
    assert len(rwa.table_dictionary()) == 68
    assert "exposure_id" in rwa.table_schema("exposure_lot")["columns"]
    assert len(rwa.available_rule_sets(tables)) == 2
    assert not rwa.formula_catalog(tables).empty
    selected = rwa.select_rule_set(tables, "CRR3-EU-FL")
    value = selected["run_config"].loc[
        selected["run_config"]["config_key"] == "rule_set_id", "config_value"
    ].iloc[0]
    assert value == "CRR3-EU-FL"
    assert all(isinstance(frame, pd.DataFrame) for frame in rwa.official_snapshot(tables).values())
    undocumented = [
        name for name in rwa.__all__ if callable(getattr(rwa, name)) and not inspect.getdoc(getattr(rwa, name))
    ]
    assert undocumented == []
