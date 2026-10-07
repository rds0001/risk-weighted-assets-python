"""Independent CRR 153/154/158 default and capital-chain regressions."""
from copy import deepcopy
from math import exp, log, sqrt
from statistics import NormalDist

import pytest

from rwa_engine import calculate_tables, irb_capital_requirement, irb_retail_correlation
from rwa_engine.synthetic import generate_synthetic_tables


@pytest.fixture(scope="module")
def reference():
    return generate_synthetic_tables(bank_profile="MID_SIZE_UNIVERSAL", seed=5752026)


def scenario(reference, approach="FIRB", pd=.02, elbe=.1, default=True, subclass="CORPORATE"):
    t = deepcopy(reference)
    mask = t["irb_parameter"].exposure_id == "EXP-000001"
    for key, value in dict(irb_approach=approach, irb_subclass=subclass, pd_estimate=pd,
                           lgd_estimate=.4, lgd_floor=0., ead_estimate=1e6, ead_floor=0.,
                           elbe=elbe, specific_credit_adjustments=250000.,
                           general_credit_adjustments=0.).items():
        t["irb_parameter"].loc[mask, key] = value
    t["exposure_lot"].loc[t["exposure_lot"].exposure_id == "EXP-000001", "default_flag"] = default
    for key, value in {"specific_credit_adjustments":250000., "general_credit_adjustments":0.}.items():
        t["exposure_lot"].loc[t["exposure_lot"].exposure_id == "EXP-000001", key] = value
    return t


@pytest.mark.parametrize("approach,elbe,k,el", [
    ("FIRB",.1,0.,400000.), ("FIRB",.8,0.,400000.),
    ("AIRB",.1,.3,100000.), ("AIRB",.4,0.,400000.), ("AIRB",.5,0.,500000.),
])
def test_public_default_and_capital_chain(reference, approach, elbe, k, el):
    input_pd = 1. if approach == "FIRB" and elbe == .1 else .02
    source = scenario(reference, approach, pd=input_pd, elbe=elbe)
    result = calculate_tables(source)
    assert result.successful
    assert source["irb_parameter"].query('exposure_id == "EXP-000001"').pd_estimate.eq(input_pd).all()
    for frames, metrics in [(result.results,result.metrics),
                            (result.parallel_results,result.parallel_metrics)]:
        detail = frames["IRB_Detail"]
        row = detail.loc[detail.exposure_id == "EXP-000001"].iloc[0]
        assert row.pd == 1 and row.pd_input == input_pd
        assert row.lgd_treatment == ("SUPERVISORY" if approach == "FIRB" else "OWN_ESTIMATES")
        assert row.k == pytest.approx(k)
        assert row.rw == pytest.approx(12.5*k)
        assert row.rwea == pytest.approx(12500000*k)
        assert row.el_rate == pytest.approx(el/1e6)
        assert row.el_amount == pytest.approx(el)
        assert row.irb_shortfall == pytest.approx(max(el-250000,0))
        assert row.irb_excess == pytest.approx(max(250000-el,0))
        for metric, field in [("RWEA_IRB","rwea"),("IRB_EL","el_amount"),
                              ("IRB_SHORTFALL","irb_shortfall"),("IRB_EXCESS","irb_excess")]:
            assert metrics[metric] == pytest.approx(detail[field].sum())
        assert metrics["TREA"] == pytest.approx(max(metrics["U_TREA"],metrics["OUTPUT_FLOOR_FACTOR"]*metrics["S_TREA"]))


def test_capital_deltas(reference):
    firb = calculate_tables(scenario(reference))
    airb = calculate_tables(scenario(reference,"AIRB"))
    for a,b in [(firb.metrics,airb.metrics),(firb.parallel_metrics,airb.parallel_metrics)]:
        assert a["IRB_EL"]-b["IRB_EL"] == pytest.approx(300000)
        assert a["IRB_SHORTFALL"]-b["IRB_SHORTFALL"] == pytest.approx(150000)
        assert a["CET1"]-b["CET1"] == pytest.approx(-150000)
        assert a["U_TREA"]-b["U_TREA"] == pytest.approx(-3750000)
        assert a["S_TREA"] == b["S_TREA"]
        excess_delta = min(a["IRB_EXCESS"],.006*a["RWEA_IRB"])-min(b["IRB_EXCESS"],.006*b["RWEA_IRB"])
        assert a["T2"]-b["T2"] == pytest.approx(excess_delta)


@pytest.mark.parametrize("subclass", ["RETAIL_RESIDENTIAL","RETAIL_QRRE","RETAIL_OTHER"])
def test_retail_default(reference, subclass):
    result = calculate_tables(scenario(reference,"AIRB",subclass=subclass))
    row = result.results["IRB_Detail"].query('exposure_id == "EXP-000001"').iloc[0]
    assert row.k == pytest.approx(.3)
    assert row.el_amount == 100000


@pytest.mark.parametrize("treatment", [None,"UNKNOWN",""])
def test_default_requires_explicit_treatment(treatment):
    with pytest.raises(ValueError,match="lgd_treatment"):
        irb_capital_requirement(1,.4,.2,2.5,defaulted=True,elbe=.1,lgd_treatment=treatment)


def test_direct_contract():
    for elbe in (.1,.4,.8):
        assert irb_capital_requirement(.02,.4,.2,2.5,defaulted=True,elbe=elbe,
                                     lgd_treatment="SUPERVISORY") == 0
    assert irb_capital_requirement(.02,.4,.2,2.5,defaulted=True,elbe=.1,
                                 lgd_treatment="OWN_ESTIMATES") == pytest.approx(.3)
    with pytest.raises(ValueError,match="contradicts"):
        irb_capital_requirement(1,.4,.2,2.5)
    with pytest.raises(ValueError,match="subclass"):
        irb_retail_correlation(.01,"RETAIL_TYPO")
    for bad in (float("nan"),float("inf"),-.1,1.1):
        with pytest.raises(ValueError,match="pd"):
            irb_capital_requirement(bad,.4,.2,2.5,defaulted=True,lgd_treatment="SUPERVISORY")
    with pytest.raises(ValueError,match="boolean"):
        irb_capital_requirement(.01,.4,.2,2.5,defaulted="False")


@pytest.mark.parametrize("approach,subclass,pd,default", [
    ("UNKNOWN","CORPORATE",.01,False),("SLOTTING","CORPORATE",.01,False),
    ("FIRB","RETAIL_OTHER",.01,False),("AIRB","RETAIL_TYPO",.01,False),
    ("FIRB","CORPORATE",1.,False),
])
def test_invalid_portfolio_contract(reference,approach,subclass,pd,default):
    with pytest.raises(Exception,match="Unsupported|requires|contradicts"):
        calculate_tables(scenario(reference,approach,pd=pd,default=default,subclass=subclass))


@pytest.mark.parametrize("treatment", ["SUPERVISORY","OWN_ESTIMATES"])
def test_performing_independent_normal_formula(treatment):
    n = NormalDist()
    pd=.01
    lgd=.4
    r=.2
    b=(.11852-.05478*log(pd))**2
    expected=(lgd*n.cdf((n.inv_cdf(pd)+sqrt(r)*n.inv_cdf(.999))/sqrt(1-r))-pd*lgd)/(1-1.5*b)
    assert irb_capital_requirement(pd,lgd,r,2.5,lgd_treatment=treatment) == pytest.approx(expected)
    r=.03*(1-exp(-35*pd))/(1-exp(-35))+.16*(1-(1-exp(-35*pd))/(1-exp(-35)))
    assert irb_retail_correlation(pd,"RETAIL_OTHER") == pytest.approx(r)
    expected=lgd*n.cdf((n.inv_cdf(pd)+sqrt(r)*n.inv_cdf(.999))/sqrt(1-r))-pd*lgd
    for maturity in (1,5):
        assert irb_capital_requirement(pd,lgd,r,maturity,apply_maturity_adjustment=False,
                                      lgd_treatment="OWN_ESTIMATES") == pytest.approx(expected)
