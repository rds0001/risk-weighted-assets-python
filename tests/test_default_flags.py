"""Shared Python/R vectors through public KSA and binding-floor calculations."""
import csv
from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest

from rwa_engine import CalculationError, calculate_tables, official_snapshot
from rwa_engine.booleans import regulatory_bool
from rwa_engine.synthetic import generate_synthetic_tables


def cases():
    with (Path(__file__).parent / "fixtures/regulatory_boolean_cases.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    decode = {"bool":lambda x: x == "1", "int":int, "float":float,
              "str":str, "null":lambda x: None, "nan":lambda x: float("nan"),
              "na":lambda x: pd.NA}
    return [(r["id"],decode[r["kind"]](r["value"]),r["expected"]) for r in rows]


@pytest.mark.parametrize("name,value,expected", cases())
def test_shared_scalar_contract(name,value,expected):
    if expected == "ERROR":
        with pytest.raises(ValueError,match="default_flag must be an explicit boolean"):
            regulatory_bool(value,"default_flag")
    else:
        assert regulatory_bool(value,"default_flag") is (expected == "TRUE")


@pytest.fixture(scope="module")
def sources():
    return {p: official_snapshot(generate_synthetic_tables(bank_profile=p,seed=5752026))
            for p in ("KSA_BANK","MID_SIZE_UNIVERSAL")}


def portfolio(sources,values,irb):
    t = deepcopy(sources["KSA_BANK"])
    n = len(values)
    for name in ("exposure_lot","sa_classification","irb_parameter"):
        original = sources["MID_SIZE_UNIVERSAL"] if name == "irb_parameter" else t
        row = original[name].loc[original[name].exposure_id == "EXP-000001"].iloc[[0]]
        t[name] = pd.concat([row]*n,ignore_index=True)
        for i in range(n):
            eid = f"BOOL-{i:03d}"
            t[name].loc[i,["exposure_id","business_key","record_id"]] = [eid,eid,eid+"::v1"]
    exp = t["exposure_lot"]
    exp["default_flag"] = pd.Series(values,dtype=object)
    for k,v in dict(approach="IRB" if irb else "KSA",gross_carrying_amount=1e6,
                    net_carrying_amount_article_111=1e6,ead_data_path="GROSS",
                    specific_credit_adjustments=0.,general_credit_adjustments=0.,
                    additional_valuation_adjustments=0.,other_own_funds_reductions=0.,
                    committed_undrawn=0.).items():
        exp[k]=v
    sa = t["sa_classification"]
    for k,v in dict(exposure_class="CORPORATE",credit_quality_step=3,
                    short_term_flag=False,transactor_flag=False,retail_eligible_flag=False,
                    specialised_lending_type="",risk_weight_override=float("nan"),
                    currency_mismatch_flag=False,supporting_factor=1.,supporting_factor_type="NONE",
                    sme_supporting_eligible=False,infrastructure_supporting_eligible=False).items():
        sa[k]=v
    for k,v in dict(irb_approach="FIRB",irb_subclass="CORPORATE",pd_estimate=.0005,
                    pd_floor=0.,lgd_estimate=.4,lgd_floor=0.,ead_estimate=1e6,ead_floor=0.,elbe=.1).items():
        t["irb_parameter"][k]=v
    if not irb:
        t["irb_parameter"]=t["irb_parameter"].iloc[:0].copy()
    for name in ("real_estate_exposure","protection_allocation","crypto_exposure"):
        t[name]=t[name].iloc[:0].copy()
    t["business_indicator_item"]["amount"]=0.
    t["rule_set"]["output_floor_factor"]=.725
    return t


@pytest.mark.parametrize("irb", [False,True],ids=["KSA","IRB_FLOOR"])
@pytest.mark.parametrize("expected", [True,False])
def test_public_representation_invariance(sources,irb,expected,monkeypatch):
    from rwa_engine import booleans
    calls=[]
    original=booleans.regulatory_bool
    def counted(value,field):
        calls.append(field)
        return original(value,field)
    monkeypatch.setattr(booleans,"regulatory_bool",counted)
    values=[v for _,v,e in cases() if e == ("TRUE" if expected else "FALSE")]
    t=portfolio(sources,values,irb)
    before=t["exposure_lot"].default_flag.copy(deep=True)
    mixed=calculate_tables(t)
    assert calls == ["default_flag"]*len(values)
    canonical=calculate_tables(portfolio(sources,[expected]*len(values),irb))
    pd.testing.assert_series_equal(t["exposure_lot"].default_flag,before)
    assert mixed.successful and canonical.successful
    rw=1.5 if expected else .75
    for frames,m,reference in [(mixed.results,mixed.metrics,canonical.metrics),
                               (mixed.parallel_results,mixed.parallel_metrics,canonical.parallel_metrics)]:
        sa=frames["SA_Detail"]
        assert sa.defaulted.eq(expected).all()
        assert sa.risk_weight.eq(rw).all()
        assert sa.rwea.eq(1e6*rw).all()
        assert sa.shadow_rwea.eq(1e6*rw).all()
        for field in ("RWEA_KSA","RWEA_IRB","IRB_EL","U_TREA","S_TREA","TREA","FLOOR_UPLIFT"):
            assert m[field] == reference[field], field
        assert m["S_TREA"] == len(values)*1e6*rw
        if irb:
            detail=frames["IRB_Detail"]
            assert detail.defaulted.eq(expected).all()
            assert detail.pd.eq(1. if expected else .0005).all()
            if expected:
                assert detail.k.eq(0).all()
                assert detail.el_amount.eq(400000).all()
            assert m["FLOOR_BINDING"]
            assert m["TREA"] == .725*m["S_TREA"]
        else:
            assert frames["IRB_Detail"].empty
            assert m["RWEA_KSA"] == m["U_TREA"] == m["TREA"] == len(values)*1e6*rw


@pytest.mark.parametrize("irb", [False,True])
def test_invalid_flags_fail_public_calculation(sources,irb):
    for name,value,expected in cases():
        if expected == "ERROR":
            with pytest.raises(CalculationError,match="default_flag must be an explicit boolean"):
                calculate_tables(portfolio(sources,[value],irb))
