"""Focused support-factor regressions; no web or external publication dependencies."""
import math
from copy import deepcopy
from datetime import date, datetime

import pandas as pd
import pytest

from rwa_engine.config_io import load_regulatory_config, regulatory_parameter_items
from rwa_engine.engines import CalculationBundle, CalculationContext, calculate_credit, calculate_trea
from rwa_engine.excel_io import select_official_as_of
from rwa_engine.parameters import ParameterStore
from rwa_engine.supporting import (
    apply_factors,
    infrastructure_factor,
    irb_rwea,
    normalise_support_columns,
    resolve_support,
    sme_factor,
    support_issues,
)
from rwa_engine.synthetic import generate_synthetic_tables


@pytest.fixture(scope="module")
def params():
    config = load_regulatory_config("daten/konfiguration/regulatory/crr3_eu_2026_v1.yaml")
    return ParameterStore(pd.DataFrame([{
        "parameter_key": item["key"], "dimension_1": item.get("d1", ""),
        "dimension_2": item.get("d2", ""), "parameter_value": item["value"],
    } for item in regulatory_parameter_items(config)]))


@pytest.mark.parametrize("amount,expected", [(1e6,.7619),(2.5e6,.7619),(5e6,.80595)])
def test_sme_weighted_formula(amount, expected, params):
    assert sme_factor(amount, params) == pytest.approx(expected, abs=1e-12)
    assert irb_rwea(1e6, .08, params, expected, .75) == pytest.approx(1e6 * expected * .75)


@pytest.mark.parametrize("bad", [0,-1,math.nan,math.inf,"bad",True])
def test_invalid_amounts(bad, params):
    with pytest.raises(ValueError):
        sme_factor(bad, params)


@pytest.mark.parametrize("bad", [0,-.1,1.01,math.nan,math.inf,True])
def test_invalid_factors(bad):
    with pytest.raises(ValueError):
        apply_factors(100, bad)


def request_row(**changes):
    row = dict(exposure_id="TEST", irb_subclass="CORPORATE", exposure_class="CORPORATE",
               default_flag=False, annual_sales_eur=20e6, adc_flag=False,
               sme_supporting_eligible=True, infrastructure_supporting_eligible=True,
               sme_total_amount_owed_eur=5e6, supporting_factor_reference="SYNTHETIC-ELIGIBILITY-001",
               supporting_factor_approved_by="Synthetic Model Risk")
    row.update(changes)
    return row


def test_combination_and_evidence(params):
    detail = resolve_support(request_row(), params, approach="IRB")
    assert detail["supporting_factor"] == pytest.approx(.6044625)
    assert detail["supporting_factor_type"] == "SME_INFRASTRUCTURE"
    assert detail["supporting_factor_reference"] == "SYNTHETIC-ELIGIBILITY-001"
    assert infrastructure_factor(params) == .75


@pytest.mark.parametrize("changes", [
    {"default_flag":True}, {"adc_flag":True}, {"annual_sales_eur":50e6+1},
    {"supporting_factor_reference":""}, {"supporting_factor_approved_by":""},
    {"irb_subclass":"INSTITUTION"}, {"supporting_factor":.75},
    {"sme_supporting_eligible":"maybe"}, {"sme_total_amount_owed_eur":None},
    {"supporting_factor_type":"INFRASTRUCTURE"},
])
def test_invalid_eligibility(changes, params):
    with pytest.raises(ValueError):
        resolve_support(request_row(**changes), params, approach="IRB")


def test_legacy_is_explicit_and_never_transferred(params):
    row = {"supporting_factor":.7619, "supporting_factor_type":"SME"}
    assert resolve_support(row, params, approach="SA")["supporting_factor_status"] == "LEGACY_SA_UNVERIFIED"
    with pytest.raises(ValueError):
        resolve_support(row, params, approach="IRB")
    assert resolve_support({}, None, approach="IRB")["supporting_factor"] == 1
    old = pd.DataFrame({"exposure_id":["X"]})
    normalized = normalise_support_columns(old, "irb_parameter")
    assert "supporting_factor" not in old
    assert resolve_support(normalized.iloc[0], None, approach="IRB")["supporting_factor"] == 1


@pytest.fixture(scope="module")
def credit_tables():
    raw = generate_synthetic_tables(bank_profile="MID_SIZE_UNIVERSAL")
    tables = {name: select_official_as_of(frame, date(2026,8,31), datetime(2026,8,31,23,59,59))
              for name, frame in raw.items()}
    eid = "EXP-000001"
    for name in ("exposure_lot","sa_classification","irb_parameter","real_estate_exposure"):
        tables[name] = tables[name].loc[tables[name].exposure_id == eid].copy()
    for name in ("crypto_exposure","protection_allocation"):
        tables[name] = tables[name].iloc[:0].copy()
    return tables


def credit(tables, params):
    context = CalculationContext(date(2026,8,31), datetime(2026,8,31,23,59,59),
                                 "CRR3-EU-2026", params, "EUR", "LEGACY", .55)
    bundle = CalculationBundle()
    calculate_credit(tables, context, bundle)
    return context, bundle


def test_irb_fix_leaves_k_el_and_shadow_unchanged(credit_tables, params):
    tables = deepcopy(credit_tables)
    _, baseline = credit(tables, params)
    row = tables["irb_parameter"].index[0]
    tables["irb_parameter"].loc[row, "infrastructure_supporting_eligible"] = True
    tables["irb_parameter"].loc[row, "supporting_factor_reference"] = "SYNTHETIC-501A"
    tables["irb_parameter"].loc[row, "supporting_factor_approved_by"] = "Synthetic Model Risk"
    _, supported = credit(tables, params)
    before = baseline.results["IRB_Detail"].iloc[0]
    after = supported.results["IRB_Detail"].iloc[0]
    assert after.rwea == pytest.approx(before.rwea * .75)
    for field in ("k","pd","lgd","ead","el_amount","irb_shortfall","irb_excess","rw"):
        assert after[field] == before[field]
    assert after.effective_rw == pytest.approx(before.rw * .75)
    assert supported.metrics["RWEA_KSA_SHADOW_ALL"] == baseline.metrics["RWEA_KSA_SHADOW_ALL"]
    assert after.supporting_factor_relief == pytest.approx(before.rwea * .25)
    tables["exposure_lot"].loc[:, "default_flag"] = True
    with pytest.raises(ValueError, match="defaulted"):
        credit(tables, params)


@pytest.mark.parametrize("floor", [.1, 1.0])
@pytest.mark.parametrize("fully_loaded", [False,True])
def test_floor_uses_adjusted_paths_once(credit_tables, params, floor, fully_loaded):
    tables = deepcopy(credit_tables)
    for name in ("irb_parameter","sa_classification"):
        tables[name]["infrastructure_supporting_eligible"] = True
        tables[name]["supporting_factor_reference"] = "SYNTHETIC-501A"
        tables[name]["supporting_factor_approved_by"] = "Synthetic Model Risk"
        tables[name]["supporting_factor_type"] = "INFRASTRUCTURE"
        tables[name]["supporting_factor"] = .75
    ctx, bundle = credit(tables, params)
    ctx.output_floor_factor = floor
    bundle.metrics.update({name:0 for name in ("K_MARKET_FRTB","K_MARKET_LEGACY","K_CVA_SA","K_CVA",
                           "K_SETTLEMENT","K_LARGE_EXPOSURE","K_OPERATIONAL")})
    calculate_trea(ctx, bundle, fully_loaded=fully_loaded)
    u = bundle.metrics["RWEA_IRB"]
    s = bundle.results["SA_Detail"].rwea.sum()
    assert bundle.metrics["U_TREA"] == u
    assert bundle.metrics["S_TREA"] == s
    assert bundle.metrics["TREA"] == pytest.approx(max(u, floor*s))
    assert bundle.metrics["FLOOR_BINDING"] == (floor == 1.0)


def test_governed_parameter_override(params):
    changed = params.frame.copy()
    changed.loc[(changed.parameter_key=="SUPPORTING_FACTOR") &
                (changed.dimension_1=="INFRASTRUCTURE"),"parameter_value"] = .8
    assert infrastructure_factor(ParameterStore(changed)) == .8
    assert infrastructure_factor(params) == .75


def test_invalid_input_is_a_validation_issue(params):
    row = request_row(supporting_factor_reference="")
    issues = support_issues({"irb_parameter":pd.DataFrame([row]),"regulatory_parameter":params.frame})
    assert issues[0][0:2] == ("ERROR","INVALID_SUPPORTING_FACTOR")

def test_supported_inputs_survive_excel_roundtrip(tmp_path, credit_tables, params):
    from rwa_engine.excel_io import read_input_workbooks, write_input_workbooks
    tables = deepcopy(credit_tables)
    for name in ("sa_classification", "irb_parameter"):
        tables[name]["supporting_factor_type"] = "INFRASTRUCTURE"
        tables[name]["supporting_factor"] = .75
        tables[name]["infrastructure_supporting_eligible"] = True
        tables[name]["supporting_factor_reference"] = "SYNTHETIC-XLSX-501A"
        tables[name]["supporting_factor_approved_by"] = "Synthetic Model Risk"
    _, expected = credit(tables, params)
    write_input_workbooks(tmp_path, tables)
    loaded, issues = read_input_workbooks(tmp_path)
    assert not issues
    _, actual = credit(loaded, params)
    for name in ("SA_Detail", "IRB_Detail"):
        assert actual.results[name].rwea.iloc[0] == pytest.approx(expected.results[name].rwea.iloc[0])
        assert actual.results[name].supporting_factor_status.iloc[0] == "VERIFIED_INPUT"
        assert actual.results[name].supporting_factor_reference.iloc[0] == "SYNTHETIC-XLSX-501A"
    assert not bool(actual.results["IRB_Detail"].supporting_factor_path_difference.iloc[0])

def test_public_calculation_reconciles_with_explicit_irb_support():
    from rwa_engine import calculate_tables
    tables = generate_synthetic_tables(bank_profile="MID_SIZE_UNIVERSAL")
    mask = tables["irb_parameter"].exposure_id == "EXP-000001"
    tables["irb_parameter"].loc[mask, "infrastructure_supporting_eligible"] = True
    tables["irb_parameter"].loc[mask, "supporting_factor_reference"] = "SYNTHETIC-PUBLIC-501A"
    tables["irb_parameter"].loc[mask, "supporting_factor_approved_by"] = "Synthetic Model Risk"
    result = calculate_tables(tables)
    assert result.successful
    for frames in (result.results, result.parallel_results):
        row = frames["IRB_Detail"].set_index("exposure_id").loc["EXP-000001"]
        assert row.rwea == pytest.approx(row.rwea_pre_supporting_factor * .75)
