"""Komponenten-Engines für Säule 1, Kapital, IRRBB und ICAAP."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from math import sqrt
from typing import Mapping

import numpy as np
import pandas as pd

from . import formulas as f
from .parameters import ParameterStore


def _num(value, default=0.0) -> float:
    if value is None or pd.isna(value):
        return float(default)
    return float(value)


def _bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().upper() in {"TRUE", "1", "YES", "JA"}


def _text(value) -> str:
    return "" if value is None or pd.isna(value) else str(value).strip()


@dataclass
class CalculationContext:
    as_of_date: date
    knowledge_time: datetime
    rule_set_id: str
    parameters: ParameterStore
    reporting_currency: str
    market_regime: str
    output_floor_factor: float
    run_id: str = ""
    formula_version: str = "1.0.0"


@dataclass
class CalculationBundle:
    results: dict[str, pd.DataFrame] = field(default_factory=dict)
    metrics: dict[str, float | str | bool] = field(default_factory=dict)
    controls: list[dict] = field(default_factory=list)

    def add_control(self, code: str, passed: bool, expected, actual, message: str) -> None:
        self.controls.append(
            {
                "control_code": code,
                "passed": bool(passed),
                "expected": expected,
                "actual": actual,
                "difference": _num(actual) - _num(expected)
                if isinstance(actual, (int, float)) and isinstance(expected, (int, float))
                else None,
                "message": message,
            }
        )


def calculate_credit(t: Mapping[str, pd.DataFrame], ctx: CalculationContext, out: CalculationBundle) -> None:
    p = ctx.parameters
    exp_df = t["exposure_lot"].copy()
    sa = t["sa_classification"].copy()
    re_df = t["real_estate_exposure"].copy()
    irb = t["irb_parameter"].copy()
    alloc = t["protection_allocation"].copy()
    merged = exp_df.merge(
        sa.drop(columns=[c for c in sa.columns if c in exp_df.columns and c != "exposure_id"]),
        on="exposure_id",
        how="left",
    )
    re_cols = [
        "exposure_id",
        "property_type",
        "ipre_flag",
        "adc_flag",
        "prudent_property_value",
        "senior_liens",
        "etv",
    ]
    merged = merged.merge(
        re_df[re_cols] if not re_df.empty else pd.DataFrame(columns=re_cols), on="exposure_id", how="left"
    )
    guar = alloc[alloc["protection_type"] == "GUARANTEE"] if not alloc.empty else alloc
    if not guar.empty:
        g = guar.groupby("exposure_id", as_index=False).agg(
            protected_amount=("eligible_value_after_haircut", "sum"),
            substitution_rw=("substitution_risk_weight", "min"),
        )
        merged = merged.merge(g, on="exposure_id", how="left")
    else:
        merged["protected_amount"] = 0.0
        merged["substitution_rw"] = np.nan
    rows = []
    for _, r in merged.iterrows():
        ead_on, ead_off, ead = f.sa_ead(
            gross_carrying_amount=_num(r["gross_carrying_amount"]),
            specific_adjustments=_num(r["specific_credit_adjustments"]),
            additional_valuation_adjustments=_num(r["additional_valuation_adjustments"]),
            other_own_funds_reductions=_num(r["other_own_funds_reductions"]),
            committed_undrawn=_num(r["committed_undrawn"]),
            annex_i_class=str(r["annex_i_class"]),
            data_path=str(r["ead_data_path"]),
            net_carrying_amount_article_111=_num(r["net_carrying_amount_article_111"]),
            params=p,
        )
        coverage = _num(r["specific_credit_adjustments"]) / max(_num(r["gross_carrying_amount"]), 1)
        rw = f.sa_base_risk_weight(
            str(r["exposure_class"]),
            int(_num(r["credit_quality_step"], 0)) or None,
            short_term=_bool(r["short_term_flag"]),
            transactor=_bool(r["transactor_flag"]),
            retail_eligible=_bool(r["retail_eligible_flag"]),
            defaulted=_bool(r["default_flag"]),
            default_coverage_ratio=coverage,
            specialised_lending_type=_text(r.get("specialised_lending_type")),
            params=p,
        )
        segments = []
        if not pd.isna(r.get("property_type")):
            rw, segments = f.real_estate_weighted_rw(
                ead=ead,
                property_value=_num(r["prudent_property_value"]),
                property_type=str(r["property_type"]),
                ipre=_bool(r["ipre_flag"]),
                counterparty_rw=rw,
                senior_liens=_num(r["senior_liens"]),
                adc=_bool(r["adc_flag"]),
                params=p,
            )
        override = r.get("risk_weight_override")
        if not pd.isna(override):
            rw = float(override)
        if _bool(r.get("currency_mismatch_flag", False)):
            rw = min(p.get("CURRENCY_MISMATCH", "MULTIPLIER") * rw, p.get("CURRENCY_MISMATCH", "RW_CAP"))
        protected = min(_num(r.get("protected_amount", 0)), ead)
        unprotected = ead - protected
        sub_rw = _num(r.get("substitution_rw", rw), rw)
        rwea_pre = ead * rw
        rwea_post = unprotected * rw + protected * sub_rw
        sf = _num(r.get("supporting_factor", 1), 1)
        rwea_final = rwea_post * sf
        rows.append(
            {
                "exposure_id": r["exposure_id"],
                "approach": r["approach"],
                "exposure_class": r["exposure_class"],
                "ead_on": ead_on,
                "ead_off": ead_off,
                "ccf": p.get("SA_CCF", str(r["annex_i_class"])),
                "ead": ead,
                "risk_weight": rw,
                "protected_amount": protected,
                "substitution_rw": sub_rw,
                "rwea_pre_crm": rwea_pre,
                "rwea_post_crm": rwea_post,
                "supporting_factor": sf,
                "rwea": rwea_final,
                "actual_rwea": rwea_final if r["approach"] == "KSA" else 0.0,
                "shadow_rwea": rwea_final,
                "segments": str(segments),
                "formula_id": "SA_EAD/SA_RW",
                "formula_version": ctx.formula_version,
            }
        )
    sa_result = pd.DataFrame(rows)
    out.results["SA_Detail"] = sa_result
    out.metrics["RWEA_KSA"] = float(sa_result["actual_rwea"].sum())
    out.metrics["RWEA_KSA_SHADOW_ALL"] = float(sa_result["shadow_rwea"].sum())
    crypto_rows = []
    for _, r in t["crypto_exposure"].iterrows():
        rw = p.get("CRYPTO_RW", str(r["crypto_class"]))
        crypto_rows.append(
            {
                "exposure_id": r["exposure_id"],
                "crypto_class": r["crypto_class"],
                "market_value": _num(r["market_value"]),
                "risk_weight": rw,
                "rwea": _num(r["market_value"]) * rw,
                "tier1_limit_relevant": _bool(r["tier1_limit_relevant_flag"]),
                "formula_id": "CRYPTO_TRANSITIONAL",
            }
        )
    crypto_result = pd.DataFrame(crypto_rows)
    out.results["Crypto_Detail"] = crypto_result
    out.metrics["RWEA_CRYPTO"] = float(crypto_result["rwea"].sum()) if not crypto_result.empty else 0.0

    if irb.empty:
        irb_result = pd.DataFrame(
            columns=["exposure_id", "ead", "pd", "lgd", "r", "m", "k", "rw", "rwea", "el_amount"]
        )
    else:
        base = exp_df.merge(
            irb.drop(columns=[c for c in irb.columns if c in exp_df.columns and c != "exposure_id"]),
            on="exposure_id",
        )
        irows = []
        for _, r in base.iterrows():
            pdv = max(_num(r["pd_estimate"]), _num(r["pd_floor"]))
            lgd = max(_num(r["lgd_estimate"]), _num(r["lgd_floor"]))
            ead = max(_num(r["ead_estimate"]), _num(r["ead_floor"]))
            defaulted = _bool(r["default_flag"])
            subclass = str(r["irb_subclass"])
            retail = subclass.startswith("RETAIL")
            corr = (
                f.retail_correlation(pdv, subclass, params=p)
                if retail
                else f.irb_correlation(
                    pdv,
                    annual_sales_million=_num(r["annual_sales_eur"]) / 1e6
                    if _num(r["annual_sales_eur"])
                    else None,
                    financial_multiplier=_bool(r["financial_multiplier_flag"]),
                    params=p,
                )
            )
            k = f.irb_k(
                pdv,
                lgd,
                corr,
                _num(r["maturity_years"], 1),
                apply_maturity_adjustment=not retail,
                defaulted=defaulted,
                elbe=_num(r["elbe"]),
                params=p,
            )
            rw = p.get("RWA_MULTIPLIER", "PILLAR1") * k
            rwea = ead * rw
            el_rate = _num(r["elbe"]) if defaulted else pdv * lgd
            coverage = _num(r["specific_credit_adjustments"]) + _num(r["general_credit_adjustments"])
            el = ead * el_rate
            irows.append(
                {
                    "exposure_id": r["exposure_id"],
                    "irb_approach": r["irb_approach"],
                    "subclass": subclass,
                    "ead": ead,
                    "pd": pdv,
                    "lgd": lgd,
                    "r": corr,
                    "m": _num(r["maturity_years"]),
                    "k": k,
                    "rw": rw,
                    "rwea": rwea,
                    "el_rate": el_rate,
                    "el_amount": el,
                    "coverage": coverage,
                    "irb_shortfall": max(el - coverage, 0),
                    "irb_excess": max(coverage - el, 0),
                    "formula_id": "IRB_RETAIL_K" if retail else "IRB_CORP_K",
                    "formula_version": ctx.formula_version,
                }
            )
        irb_result = pd.DataFrame(irows)
    out.results["IRB_Detail"] = irb_result
    out.metrics["RWEA_IRB"] = float(irb_result["rwea"].sum()) if not irb_result.empty else 0.0
    out.metrics["IRB_EL"] = float(irb_result["el_amount"].sum()) if not irb_result.empty else 0.0
    out.metrics["IRB_SHORTFALL"] = float(irb_result["irb_shortfall"].sum()) if not irb_result.empty else 0.0
    out.metrics["IRB_EXCESS"] = float(irb_result["irb_excess"].sum()) if not irb_result.empty else 0.0
    out.add_control(
        "CREDIT_SUM",
        True,
        out.metrics["RWEA_KSA"] + out.metrics["RWEA_IRB"],
        float(sa_result["actual_rwea"].sum()) + float(irb_result["rwea"].sum()),
        "KSA+IRB Detailabstimmung",
    )


def calculate_ccr_cva_settlement(
    t: Mapping[str, pd.DataFrame], ctx: CalculationContext, out: CalculationBundle
) -> None:
    p = ctx.parameters
    rwa_factor = p.get("RWA_MULTIPLIER", "PILLAR1")
    ns_rows = []
    for _, r in t["netting_set"].iterrows():
        addon = sum(
            _num(r[x]) for x in ["addon_ird", "addon_fx", "addon_credit", "addon_equity", "addon_commodity"]
        )
        alpha = _num(r["alpha"], p.get("SA_CCR", "ALPHA"))
        rc, mult, pfe, ead = f.sa_ccr_ead(_num(r["V"]), _num(r["C"]), addon, alpha=alpha, params=p)
        ns_rows.append(
            {
                "netting_set_id": r["netting_set_id"],
                "rc": rc,
                "addon": addon,
                "multiplier": mult,
                "pfe": pfe,
                "ead": ead,
                "risk_weight": _num(r["risk_weight"], 1),
                "rwea": ead * _num(r["risk_weight"], 1),
                "formula_id": "SA_CCR",
                "formula_version": ctx.formula_version,
            }
        )
    ccr = pd.DataFrame(ns_rows)
    out.results["CCR_Detail"] = ccr
    out.metrics["RWEA_CCR"] = float(ccr["rwea"].sum()) if not ccr.empty else 0.0

    sft_rows = []
    for _, r in t["sft_trade"].iterrows():
        ead = f.sft_ead(
            _num(r["cash_leg"]), _num(r["security_value"]), _num(r["security_haircut"]), _num(r["fx_haircut"])
        )
        sft_rows.append(
            {
                "trade_id": r["trade_id"],
                "ead": ead,
                "risk_weight": _num(r["risk_weight"]),
                "rwea": ead * _num(r["risk_weight"]),
                "formula_id": "SFT_COMPREHENSIVE",
            }
        )
    sft = pd.DataFrame(sft_rows)
    out.results["SFT_Detail"] = sft
    out.metrics["RWEA_SFT"] = float(sft["rwea"].sum()) if not sft.empty else 0.0

    ccp_rows = []
    for _, r in t["ccp_exposure"].iterrows():
        if _bool(r["qccp_flag"]):
            rw = p.get(
                "CCP_RW", "QCCP_JOINT_DEFAULT" if _bool(r["client_joint_default_flag"]) else "QCCP_MEMBER"
            )
            trade_rwea = _num(r["trade_ead"]) * rw
            df = _num(r["default_fund_contribution"])
            denom = max(_num(r["ccp_default_fund_total"]), 1)
            k = max(
                _num(r["hypothetical_ccp_capital"]) * df / denom,
                p.get("CCP_DF", "FLOOR_CAPITAL_RATE") * p.get("CCP_RW", "QCCP_MEMBER") * df,
            )
            df_rwea = rwa_factor * k
        else:
            rw = p.get("CCP_RW", "NON_QCCP")
            trade_rwea = _num(r["trade_ead"]) * rw
            df_rwea = rwa_factor * _num(r["default_fund_contribution"])
        ccp_rows.append(
            {
                "ccp_exposure_id": r["ccp_exposure_id"],
                "qccp": _bool(r["qccp_flag"]),
                "trade_rwea": trade_rwea,
                "default_fund_rwea": df_rwea,
                "rwea": trade_rwea + df_rwea,
                "formula_id": "CCP",
            }
        )
    ccp = pd.DataFrame(ccp_rows)
    out.results["CCP_Detail"] = ccp
    out.metrics["RWEA_CCP"] = float(ccp["rwea"].sum()) if not ccp.empty else 0.0

    items = []
    for _, r in t["cva_scope_item"].iterrows():
        if not _bool(r["exempt_flag"]):
            items.append(
                (
                    _num(r["cva_risk_weight"]),
                    _num(r["effective_maturity"]),
                    _num(r["ead"]),
                    _num(r["single_name_hedge"]),
                    _num(r["single_hedge_maturity"]),
                    _num(r["hedge_correlation"]),
                    _num(r["index_hedge"]),
                    _num(r["index_hedge_maturity"]),
                    _num(r["index_hedge_risk_weight"]),
                )
            )
    k_cva = f.ba_cva_capital(items, params=p)
    cvas = t["cva_sensitivity"].copy()
    if not cvas.empty:
        cvas["ws"] = pd.to_numeric(cvas["sensitivity"]) * pd.to_numeric(cvas["risk_weight"])
        bucket_rows = []
        for (measure, risk_class, bucket), g in cvas.groupby(["measure", "risk_class", "bucket"]):
            ws = g["ws"].to_numpy(float)
            rho = float(g["correlation"].iloc[0])
            k2 = float(np.sum(ws**2) + rho * (float(np.sum(ws)) ** 2 - float(np.sum(ws**2))))
            bucket_rows.append(
                {
                    "measure": measure,
                    "risk_class": risk_class,
                    "bucket": bucket,
                    "S_b": float(np.sum(ws)),
                    "K_b": sqrt(max(k2, 0)),
                    "formula_id": "SA_CVA",
                }
            )
        cva_buckets = pd.DataFrame(bucket_rows)
        measure_capital = []
        gamma = p.get("SA_CVA", "INTER_BUCKET_CORRELATION")
        for _, g in cva_buckets.groupby(["measure", "risk_class"]):
            kb = g["K_b"].to_numpy(float)
            sb = g["S_b"].to_numpy(float)
            measure_capital.append(
                sqrt(max(float(np.sum(kb**2)) + gamma * (float(np.sum(sb)) ** 2 - float(np.sum(sb**2))), 0))
            )
        k_sa_cva = sum(measure_capital)
    else:
        k_sa_cva = 0.0
        cva_buckets = pd.DataFrame(columns=["measure", "risk_class", "bucket", "S_b", "K_b", "formula_id"])
    out.results["CVA_Buckets"] = cva_buckets
    out.results["CVA_Summary"] = pd.DataFrame(
        [
            {
                "approach": "BA_CVA",
                "counterparties": len(items),
                "k_cva": k_cva,
                "rwea": rwa_factor * k_cva,
                "formula_id": "BA_CVA",
            },
            {
                "approach": "SA_CVA_PARALLEL",
                "counterparties": len(items),
                "k_cva": k_sa_cva,
                "rwea": rwa_factor * k_sa_cva,
                "formula_id": "SA_CVA",
            },
        ]
    )
    out.metrics["K_CVA"] = k_cva
    out.metrics["K_CVA_SA"] = k_sa_cva

    set_rows = []
    for _, r in t["settlement_exposure"].iterrows():
        if _bool(r["free_delivery_flag"]):
            k = max(_num(r["delivered_leg"]) - _num(r["countervalue"]), 0) * _num(
                r["counterparty_risk_weight"]
            )
        else:
            k = _num(r["positive_price_difference"]) * f.settlement_factor(
                int(_num(r["business_days_late"])), params=p
            )
        set_rows.append(
            {
                "settlement_id": r["settlement_id"],
                "capital_requirement": k,
                "rwea": rwa_factor * k,
                "formula_id": "SETTLEMENT",
            }
        )
    settlement = pd.DataFrame(set_rows)
    out.results["Settlement_Detail"] = settlement
    out.metrics["K_SETTLEMENT"] = (
        float(settlement["capital_requirement"].sum()) if not settlement.empty else 0.0
    )
    lex = t["large_exposure_excess"].copy()
    if not lex.empty:
        lex["capital_requirement"] = pd.to_numeric(lex["excess_amount"]) * pd.to_numeric(
            lex["capital_charge_rate"]
        )
        lex["rwea"] = rwa_factor * lex["capital_requirement"]
        lex["formula_id"] = "LARGE_EXPOSURE"
    out.results["Large_Exposure"] = lex
    out.metrics["K_LARGE_EXPOSURE"] = float(lex["capital_requirement"].sum()) if not lex.empty else 0.0


def calculate_securitisation(
    t: Mapping[str, pd.DataFrame], ctx: CalculationContext, out: CalculationBundle
) -> None:
    p = ctx.parameters
    merged = t["securitisation_tranche"].merge(t["securitisation_pool"], on="pool_id", suffixes=("", "_pool"))
    rows = []
    for _, r in merged.iterrows():
        approach = str(r["approach"])
        senior = _bool(r["senior_flag"])
        sts = _bool(r["sts_flag"])
        resecuritisation = _bool(r["resecuritisation_flag"])
        data_sufficient = _bool(r["data_sufficient_flag"])
        p_raw = np.nan
        if approach == "SEC_IRBA":
            ka = f.sec_k_irb(
                _num(r["rwea_pool_irb_ul"]), _num(r["el_pool_irb"]), _num(r["pool_ead"]), params=p
            )
            p_raw, p_factor = f.sec_irba_p(
                pool_type="RETAIL" if str(r["pool_type"]) == "RETAIL" else "NON_RETAIL",
                senior=senior,
                effective_number=_num(r["effective_number_exposures"]),
                pool_k=ka,
                average_lgd=_num(r["average_lgd"]),
                tranche_maturity=_num(r["tranche_maturity"]),
                sts=sts,
                params=p,
            )
        elif approach == "SEC_SA":
            base_ka = f.sec_k_sa(_num(r["rwea_pool_sa"]), _num(r["pool_ead"]), params=p)
            w = _num(r["npe_share"])
            ka = (1.0 - w) * base_ka + w * p.get("SEC_SSFA", "DEFAULTED_POOL_FACTOR")
            p_factor = (
                p.get("SEC_SSFA", "RESECURITISATION_P")
                if resecuritisation
                else p.get("SEC_SSFA", "SA_STS_P")
                if sts
                else p.get("SEC_SSFA", "SA_P")
            )
        else:
            ka = np.nan
            p_factor = np.nan
        override = r["risk_weight_override"]
        if not pd.isna(override):
            rw = float(override)
        elif not data_sufficient:
            rw = p.get("SEC", "RW_CAP")
        elif approach == "SEC_ERBA":
            rw = f.sec_erba_rw(
                int(_num(r["credit_quality_step"])),
                _num(r["tranche_maturity"]),
                senior,
                sts,
                _num(r["attachment"]),
                _num(r["detachment"]),
                params=p,
            )
        else:
            rw = f.securitisation_rw(
                approach,
                ka,
                _num(r["attachment"]),
                _num(r["detachment"]),
                p_factor,
                sts=sts,
                senior=senior,
                resecuritisation=resecuritisation,
                cqs=int(_num(r["credit_quality_step"])),
                params=p,
            )
        rows.append(
            {
                "tranche_id": r["tranche_id"],
                "approach": approach,
                "pool_k": ka,
                "attachment": r["attachment"],
                "detachment": r["detachment"],
                "thickness": _num(r["detachment"]) - _num(r["attachment"]),
                "senior": senior,
                "sts": sts,
                "p_raw": p_raw,
                "p_factor": p_factor,
                "risk_weight": rw,
                "ead": r["ead"],
                "rwea": _num(r["ead"]) * rw,
                "formula_id": "SEC_SSFA" if approach != "SEC_ERBA" else "SEC_ERBA",
            }
        )
    result = pd.DataFrame(rows)
    out.results["SEC_Detail"] = result
    out.metrics["RWEA_SECURITISATION"] = float(result["rwea"].sum()) if not result.empty else 0.0


def calculate_market(t: Mapping[str, pd.DataFrame], ctx: CalculationContext, out: CalculationBundle) -> None:
    p = ctx.parameters
    rwa_factor = p.get("RWA_MULTIPLIER", "PILLAR1")
    pos = t["trading_position"].copy()
    pos["legacy_k"] = pd.to_numeric(pos["legacy_specific_charge"], errors="coerce").fillna(0) + pd.to_numeric(
        pos["legacy_general_charge"], errors="coerce"
    ).fillna(0)
    pos["formula_id"] = "MARKET_LEGACY"
    legacy_k = float(pos["legacy_k"].sum())
    out.results["Market_Legacy"] = pos[
        [
            "position_id",
            "risk_class",
            "market_value",
            "legacy_specific_charge",
            "legacy_general_charge",
            "legacy_k",
            "formula_id",
        ]
    ]
    out.metrics["K_MARKET_LEGACY"] = legacy_k

    sens = t["market_sensitivity"].copy()
    sens["weighted_sensitivity"] = pd.to_numeric(sens["sensitivity"]) * pd.to_numeric(sens["risk_weight"])

    def scenario_corr(base: float, scenario: str) -> float:
        if scenario == "HIGH":
            return min(
                p.get("FRTB_CORRELATION", "HIGH_MULTIPLIER") * base, p.get("FRTB_CORRELATION", "HIGH_CAP")
            )
        if scenario == "LOW":
            return max(
                p.get("FRTB_CORRELATION", "LOW_LINEAR_MULTIPLIER") * base - 1.0,
                p.get("FRTB_CORRELATION", "LOW_FLOOR_MULTIPLIER") * base,
            )
        return base

    def quadratic(values: np.ndarray, correlation: float, *, curvature: bool = False) -> float:
        total = float(np.sum(values**2))
        for i in range(len(values)):
            for j in range(len(values)):
                if i == j:
                    continue
                psi = 0.0 if curvature and values[i] < 0 and values[j] < 0 else 1.0
                total += (correlation**2 if curvature else correlation) * values[i] * values[j] * psi
        return sqrt(max(total, 0.0))

    bucket_rows = []
    class_rows = []
    scenario_capitals = []
    for corr_scenario in ["LOW", "MEDIUM", "HIGH"]:
        scenario_buckets = []
        for (measure, rc, bucket), g in sens.groupby(["measure", "risk_class", "bucket"]):
            rho = scenario_corr(float(g["intra_bucket_correlation"].iloc[0]), corr_scenario)
            gamma = scenario_corr(float(g["inter_bucket_correlation"].iloc[0]), corr_scenario)
            if measure == "CURVATURE":
                grouped = (
                    g.groupby("risk_factor")[["curvature_up", "curvature_down"]].sum().apply(pd.to_numeric)
                )
                up = grouped["curvature_up"].to_numpy(float)
                down = grouped["curvature_down"].to_numpy(float)
                k_up = quadratic(up, rho, curvature=True)
                k_down = quadratic(down, rho, curvature=True)
                row = {
                    "correlation_scenario": corr_scenario,
                    "measure": measure,
                    "risk_class": rc,
                    "bucket": bucket,
                    "S_b_up": float(np.sum(up)),
                    "S_b_down": float(np.sum(down)),
                    "K_b_up": k_up,
                    "K_b_down": k_down,
                    "S_b": 0.0,
                    "K_b": max(k_up, k_down),
                    "rho": rho,
                    "gamma": gamma,
                    "formula_id": "FRTB_SBM",
                }
            else:
                ws = g.groupby("risk_factor")["weighted_sensitivity"].sum().to_numpy(float)
                k = quadratic(ws, rho)
                raw = float(np.sum(ws))
                row = {
                    "correlation_scenario": corr_scenario,
                    "measure": measure,
                    "risk_class": rc,
                    "bucket": bucket,
                    "S_b_up": np.nan,
                    "S_b_down": np.nan,
                    "K_b_up": np.nan,
                    "K_b_down": np.nan,
                    "S_b": f.clip(raw, -k, k),
                    "K_b": k,
                    "rho": rho,
                    "gamma": gamma,
                    "formula_id": "FRTB_SBM",
                }
            scenario_buckets.append(row)
            bucket_rows.append(row)
        scenario_frame = pd.DataFrame(
            scenario_buckets,
            columns=[
                "correlation_scenario",
                "measure",
                "risk_class",
                "bucket",
                "S_b_up",
                "S_b_down",
                "K_b_up",
                "K_b_down",
                "S_b",
                "K_b",
                "rho",
                "gamma",
                "formula_id",
            ],
        )
        scenario_total = 0.0
        for (measure, rc), g in scenario_frame.groupby(["measure", "risk_class"]):
            gamma = float(g["gamma"].iloc[0])
            if measure == "CURVATURE":
                up = g["S_b_up"].to_numpy(float)
                down = g["S_b_down"].to_numpy(float)
                kup = g["K_b_up"].to_numpy(float)
                kdown = g["K_b_down"].to_numpy(float)

                def curvature_class(kb, sb):
                    total = float(np.sum(kb**2))
                    for i in range(len(sb)):
                        for j in range(len(sb)):
                            if i != j:
                                total += gamma**2 * sb[i] * sb[j] * (0.0 if sb[i] < 0 and sb[j] < 0 else 1.0)
                    return sqrt(max(total, 0.0))

                capital = max(curvature_class(kup, up), curvature_class(kdown, down))
            else:
                kb = g["K_b"].to_numpy(float)
                sb = g["S_b"].to_numpy(float)
                capital = sqrt(
                    max(float(np.sum(kb**2)) + gamma * (float(np.sum(sb)) ** 2 - float(np.sum(sb**2))), 0.0)
                )
            class_rows.append(
                {
                    "correlation_scenario": corr_scenario,
                    "measure": measure,
                    "risk_class": rc,
                    "capital": capital,
                    "formula_id": "FRTB_SBM",
                }
            )
            scenario_total += capital
        scenario_capitals.append({"correlation_scenario": corr_scenario, "sbm_capital": scenario_total})
    buckets = pd.DataFrame(
        bucket_rows,
        columns=[
            "correlation_scenario",
            "measure",
            "risk_class",
            "bucket",
            "S_b_up",
            "S_b_down",
            "K_b_up",
            "K_b_down",
            "S_b",
            "K_b",
            "rho",
            "gamma",
            "formula_id",
        ],
    )
    sbm = pd.DataFrame(
        class_rows, columns=["correlation_scenario", "measure", "risk_class", "capital", "formula_id"]
    )
    sbm_scenarios = pd.DataFrame(scenario_capitals)
    sbm_capital = float(sbm_scenarios["sbm_capital"].max()) if not sbm_scenarios.empty else 0.0

    drc_rows = []
    if not pos.empty:
        pos["maturity_scale"] = pd.to_numeric(pos["residual_maturity_years"]).map(
            lambda x: f.clip(x, p.get("FRTB_DRC", "MATURITY_MIN"), p.get("FRTB_DRC", "MATURITY_MAX"))
        )
        pos["scaled_jtd"] = pd.to_numeric(pos["drc_jtd"]) * pos["maturity_scale"]
        net = pos.groupby(
            ["drc_exposure_type", "drc_bucket", "issuer_id", "seniority_class"], as_index=False
        ).agg(
            net_jtd=("scaled_jtd", "sum"),
            drc_risk_weight=("drc_risk_weight", "max"),
            banking_book_securitisation_rw=("banking_book_securitisation_rw", "max"),
        )
        sec_mask = (
            net["drc_exposure_type"].isin(["SEC_NONCTP", "SEC_CTP"])
            & net["banking_book_securitisation_rw"].notna()
        )
        net.loc[sec_mask, "drc_risk_weight"] = p.get("SEC", "CAPITAL_RATE") * pd.to_numeric(
            net.loc[sec_mask, "banking_book_securitisation_rw"]
        )
        for (kind, bucket), g in net.groupby(["drc_exposure_type", "drc_bucket"]):
            long = g[g["net_jtd"] > 0]
            short = g[g["net_jtd"] < 0]
            gross_long = float(long["net_jtd"].sum())
            gross_short = float(-short["net_jtd"].sum())
            hbr = gross_long / (gross_long + gross_short) if gross_long + gross_short else 0.0
            weighted_long = float((long["net_jtd"] * long["drc_risk_weight"]).sum())
            weighted_short = float(((-short["net_jtd"]) * short["drc_risk_weight"]).sum())
            charge = max(weighted_long - hbr * weighted_short, 0.0)
            drc_rows.append(
                {
                    "drc_exposure_type": kind,
                    "drc_bucket": bucket,
                    "gross_long_jtd": gross_long,
                    "gross_short_jtd": gross_short,
                    "hedge_benefit_ratio": hbr,
                    "weighted_long": weighted_long,
                    "weighted_short": weighted_short,
                    "capital": charge,
                    "formula_id": "FRTB_DRC",
                }
            )
        drc = float(sum(row["capital"] for row in drc_rows))
        residual = pos[~pos["rrao_exempt_flag"].map(_bool)].copy()
        residual["applied_rrao_rate"] = (
            residual["rrao_exotic_flag"]
            .map(_bool)
            .map(lambda exotic: p.get("FRTB_RRAO", "EXOTIC_RATE" if exotic else "OTHER_RATE"))
        )
        rrao = float((pd.to_numeric(residual["notional"]).abs() * residual["applied_rrao_rate"]).sum())
    else:
        drc = rrao = 0.0
    frtb_k = sbm_capital + drc + rrao
    out.results["FRTB_Buckets"] = buckets
    out.results["FRTB_Risk_Classes"] = sbm
    out.results["FRTB_DRC"] = pd.DataFrame(drc_rows)
    out.results["FRTB_Summary"] = pd.DataFrame(
        [
            {
                "sbm": sbm_capital,
                "drc": drc,
                "rrao": rrao,
                "k_frtb": frtb_k,
                "rwea": rwa_factor * frtb_k,
                "formula_id": "FRTB_SBM/DRC/RRAO",
            }
        ]
    )
    out.metrics["K_MARKET_FRTB"] = frtb_k
    ima_rows = []
    for _, r in t["frtb_ima_input"].iterrows():
        scale = _num(r["es_stress_reduced"]) / max(_num(r["es_current_reduced"]), 1)
        imcc = max(_num(r["imcc_yesterday"]), _num(r["backtesting_multiplier"]) * _num(r["imcc_60d_average"]))
        ses = max(_num(r["ses_nmrf_yesterday"]), _num(r["nmrf_multiplier"]) * _num(r["ses_nmrf_60d_average"]))
        eligible = _bool(r["ima_permission_flag"]) and bool(p.get("FRTB_PLA_ELIGIBLE", str(r["pla_zone"])))
        k = imcc + ses + _num(r["ima_drc"]) + _num(r["capital_addons"])
        ima_rows.append(
            {
                "desk_id": r["desk_id"],
                "stress_scaling": scale,
                "imcc": imcc,
                "ses_nmrf": ses,
                "ima_drc": _num(r["ima_drc"]),
                "capital_addons": _num(r["capital_addons"]),
                "ima_permission": _bool(r["ima_permission_flag"]),
                "pla_zone": r["pla_zone"],
                "ima_eligible": eligible,
                "k_ima": k,
                "formula_id": "FRTB_IMA",
            }
        )
    ima = pd.DataFrame(ima_rows)
    out.results["FRTB_IMA"] = ima
    out.metrics["K_MARKET_IMA_PARALLEL"] = (
        float(ima.loc[ima["ima_eligible"], "k_ima"].sum()) if not ima.empty else 0.0
    )
    out.metrics["K_MARKET"] = legacy_k if ctx.market_regime.startswith("LEGACY") else frtb_k


def calculate_operational(
    t: Mapping[str, pd.DataFrame], ctx: CalculationContext, out: CalculationBundle
) -> None:
    p = ctx.parameters
    b = t["business_indicator_item"].copy()
    years = sorted(pd.to_numeric(b["financial_year"]).dropna().unique())[
        -int(p.get("BIC", "HISTORY_YEARS")) :
    ]

    def vals(kind):
        x = b[b["bi_item_type"] == kind].set_index("financial_year")["amount"]
        return [_num(x.get(y, 0)) for y in years]

    ildc, sc, fc, bi, bic = f.bic_from_components(
        vals("INTEREST_INCOME"),
        vals("INTEREST_EXPENSE"),
        vals("INTEREST_EARNING_ASSETS"),
        vals("DIVIDEND_INCOME"),
        vals("OTHER_OPERATING_INCOME"),
        vals("OTHER_OPERATING_EXPENSE"),
        vals("FEE_INCOME"),
        vals("FEE_EXPENSE"),
        vals("TRADING_BOOK_PNL"),
        vals("BANKING_BOOK_PNL"),
        params=p,
    )
    ilm = p.get("OPRISK", "EU_ILM")
    result = pd.DataFrame(
        [
            {
                "years": str(years),
                "ildc": ildc,
                "sc": sc,
                "fc": fc,
                "bi": bi,
                "bic": bic,
                "ilm_eu": ilm,
                "capital_requirement": bic * ilm,
                "rwea": p.get("RWA_MULTIPLIER", "PILLAR1") * bic * ilm,
                "formula_id": "OPRISK_BIC",
            }
        ]
    )
    out.results["Operational_Risk"] = result
    out.metrics["K_OPERATIONAL"] = bic


def calculate_trea(ctx: CalculationContext, out: CalculationBundle, *, fully_loaded: bool = False) -> None:
    p = ctx.parameters
    rwa_factor = p.get("RWA_MULTIPLIER", "PILLAR1")
    credit_actual = sum(
        _num(out.metrics.get(k))
        for k in [
            "RWEA_KSA",
            "RWEA_IRB",
            "RWEA_CRYPTO",
            "RWEA_CCR",
            "RWEA_SFT",
            "RWEA_CCP",
            "RWEA_SECURITISATION",
        ]
    )
    credit_shadow = sum(
        _num(out.metrics.get(k))
        for k in [
            "RWEA_KSA_SHADOW_ALL",
            "RWEA_CRYPTO",
            "RWEA_CCR",
            "RWEA_SFT",
            "RWEA_CCP",
            "RWEA_SECURITISATION",
        ]
    )
    k_market = _num(out.metrics["K_MARKET_FRTB"] if fully_loaded else out.metrics["K_MARKET_LEGACY"])
    k_cva = _num(out.metrics["K_CVA_SA"] if fully_loaded else out.metrics["K_CVA"])
    other_k = (
        k_market
        + k_cva
        + _num(out.metrics["K_SETTLEMENT"])
        + _num(out.metrics["K_LARGE_EXPOSURE"])
        + _num(out.metrics["K_OPERATIONAL"])
    )
    u = credit_actual + rwa_factor * other_k
    s = credit_shadow + rwa_factor * other_k
    factor = ctx.output_floor_factor
    trea, uplift, binding = f.output_floor(
        u, s, factor, optional_cap=False, cap_multiplier=p.get("OUTPUT_FLOOR", "OPTIONAL_CAP")
    )
    out.metrics.update(
        {
            "U_TREA": u,
            "S_TREA": s,
            "OUTPUT_FLOOR_FACTOR": factor,
            "TREA": trea,
            "FLOOR_UPLIFT": uplift,
            "FLOOR_BINDING": binding,
        }
    )
    out.results["TREA_Summary"] = pd.DataFrame(
        [
            {
                "view": "FULLY_LOADED" if fully_loaded else "APPLIED",
                "credit_rwea_actual": credit_actual,
                "credit_rwea_shadow": credit_shadow,
                "other_k": other_k,
                "u_trea": u,
                "s_trea": s,
                "floor_factor": factor,
                "floor_base": factor * s,
                "floor_uplift": uplift,
                "floor_binding": binding,
                "trea": trea,
                "formula_id": "OUTPUT_FLOOR",
            }
        ]
    )
    components = {
        "CREDIT": (credit_actual, credit_shadow),
        "MARKET_AND_OTHER": (rwa_factor * other_k, rwa_factor * other_k),
    }
    gaps = {k: max(factor * sv - uv, 0) for k, (uv, sv) in components.items()}
    total_gap = sum(gaps.values())
    out.results["Floor_Allocation"] = pd.DataFrame(
        [
            {
                "component": k,
                "u_trea_component": uv,
                "s_trea_component": sv,
                "positive_gap": gaps[k],
                "allocation_weight": gaps[k] / total_gap if total_gap else 0.0,
                "allocated_floor_uplift": uplift * gaps[k] / total_gap if total_gap else 0.0,
                "formula_id": "OUTPUT_FLOOR",
            }
            for k, (uv, sv) in components.items()
        ]
    )
    out.add_control(
        "OUTPUT_FLOOR",
        abs(trea - max(u, factor * s)) < p.get("CONTROL", "ABSOLUTE_TOLERANCE_EUR"),
        max(u, factor * s),
        trea,
        "Output-Floor-Identität",
    )


def calculate_capital(t: Mapping[str, pd.DataFrame], ctx: CalculationContext, out: CalculationBundle) -> None:
    p = ctx.parameters
    exp = t["exposure_lot"].copy()
    re_df = t["real_estate_exposure"][["exposure_id", "property_type"]].copy()
    npe = exp[exp["npe_flag"].map(_bool)].merge(re_df, on="exposure_id", how="left")
    npe_rows = []
    for _, r in npe.iterrows():
        d = (
            pd.Timestamp(r["npe_classification_date"]).date()
            if not pd.isna(r["npe_classification_date"])
            else ctx.as_of_date
        )
        year = max(int((ctx.as_of_date - d).days / p.get("TIME_CONVENTION", "DAYS_PER_YEAR")) + 1, 1)
        gross = _num(r["gross_carrying_amount"])
        property_secured = not pd.isna(r.get("property_type"))
        secured = gross * p.get("NPE", "PROPERTY_SECURED_SHARE") if property_secured else 0.0
        unsecured = gross - secured
        required = secured * f.npe_secured_factor(
            year, property_secured, params=p
        ) + unsecured * f.npe_unsecured_factor(year, params=p)
        available = sum(
            _num(r[x])
            for x in [
                "specific_credit_adjustments",
                "additional_valuation_adjustments",
                "other_own_funds_reductions",
                "partial_write_offs",
            ]
        )
        shortfall = max(required - available, 0)
        npe_rows.append(
            {
                "exposure_id": r["exposure_id"],
                "npe_year": year,
                "secured_part": secured,
                "unsecured_part": unsecured,
                "required_coverage": required,
                "available_coverage": available,
                "npe_shortfall": shortfall,
                "formula_id": "NPE_BACKSTOP",
            }
        )
    npe_result = pd.DataFrame(npe_rows)
    out.results["NPE_Backstop"] = npe_result
    npe_deduction = float(npe_result["npe_shortfall"].sum()) if not npe_result.empty else 0.0

    ava = t["valuation_adjustment"].copy()
    if ava.empty:
        ava_total = 0.0
    elif set(ava["method"]) == {"SIMPLIFIED"}:
        ava_total = p.get("PRUDENT_VALUATION", "SIMPLIFIED_RATE") * float(
            (pd.to_numeric(ava["fair_value"]).abs() * pd.to_numeric(ava["cet1_impact_share"])).sum()
        )
    else:
        ava_total = float(pd.to_numeric(ava["category_ava"], errors="coerce").fillna(0).sum())
    out.results["Prudent_Valuation"] = pd.DataFrame(
        [
            {
                "method": "CORE" if not ava.empty else "NOT_APPLICABLE",
                "fair_value_scope": float(
                    pd.to_numeric(ava["fair_value"], errors="coerce").fillna(0).abs().sum()
                )
                if not ava.empty
                else 0,
                "ava_total": ava_total,
                "formula_id": "PRUDENT_VALUATION",
            }
        ]
    )
    comp = t["own_funds_component"].copy()
    comp["signed_amount"] = pd.to_numeric(comp["amount"], errors="coerce").fillna(0) * pd.to_numeric(
        comp["sign"], errors="coerce"
    ).fillna(0)
    cet1_components = comp[(comp["capital_class"] == "CET1") & (comp["component_type"] != "DEDUCTION")]
    explicit_deductions = comp[
        (comp["capital_class"] == "CET1")
        & (comp["component_type"] == "DEDUCTION")
        & (comp["component_id"] != "AVA")
    ]
    cet1 = (
        float(cet1_components["signed_amount"].sum() + explicit_deductions["signed_amount"].sum())
        - ava_total
        - _num(out.metrics.get("IRB_SHORTFALL"))
        - npe_deduction
    )
    instruments = t["capital_instrument"]
    at1 = float(
        pd.to_numeric(
            instruments.loc[
                (instruments["capital_class"] == "AT1") & instruments["eligible_flag"].map(_bool),
                "carrying_amount",
            ]
        ).sum()
    )
    t2_amounts = []
    for _, r in instruments[
        (instruments["capital_class"] == "T2") & instruments["eligible_flag"].map(_bool)
    ].iterrows():
        maturity = None if pd.isna(r["maturity_date"]) else pd.Timestamp(r["maturity_date"]).date()
        t2_amounts.append(
            f.t2_eligible_amount(
                _num(r["carrying_amount"]),
                _num(r["first_day_final_five_years_amount"]),
                maturity,
                ctx.as_of_date,
                params=p,
            )
        )
    eligible_general = min(
        float(pd.to_numeric(exp["general_credit_adjustments"], errors="coerce").fillna(0).sum()),
        p.get("T2", "GENERAL_ADJUSTMENT_CAP") * _num(out.metrics.get("RWEA_KSA")),
    )
    eligible_irb_excess = min(
        _num(out.metrics.get("IRB_EXCESS")), p.get("T2", "IRB_EXCESS_CAP") * _num(out.metrics.get("RWEA_IRB"))
    )
    tier2 = sum(t2_amounts) + eligible_general + eligible_irb_excess
    tier1 = cet1 + at1
    total = tier1 + tier2
    trea = max(_num(out.metrics.get("TREA")), 1)

    req = t["capital_requirement"]

    def requirement_rows(kind):
        return req[req["requirement_type"] == kind]

    def rate(kind, default=0.0, basis=None):
        x = requirement_rows(kind)
        if basis is not None:
            x = x[x["basis"].astype(str) == basis]
        return _num(x["rate"].iloc[0], default) if not x.empty else default

    p2r_row = requirement_rows("P2R")
    if p2r_row.empty:
        p2r_amount = 0.0
        p2r = 0.0
        p2r_cet1_share = p.get("P2R_SHARE", "CET1")
        p2r_t1_share = p.get("P2R_SHARE", "TIER1")
    else:
        pr = p2r_row.iloc[0]
        basis = str(pr["basis"])
        p2r_amount = _num(pr["rate"]) * trea if basis in {"TREA", "TREA_RATE"} else _num(pr["fixed_amount"])
        p2r = p2r_amount / trea
        p2r_cet1_share = max(_num(pr["cet1_share"]), p.get("P2R_SHARE", "CET1"))
        p2r_t1_share = max(_num(pr["tier1_share"]), p.get("P2R_SHARE", "TIER1"))
    ccb = rate("CCB", p.get("CAPITAL_BUFFER", "CCB_DEFAULT"))
    ccyb = rate("CCYB")
    osii = rate("OSII")
    gsii = rate("GSII")
    syrb = rate("SYRB")
    p2g = rate("P2G")
    systemic = max(gsii, osii) + syrb
    cbr = ccb + ccyb + systemic
    required_cet1 = (p.get("CAPITAL_RATE", "CET1") + p2r_cet1_share * p2r + cbr) * trea
    required_t1 = (p.get("CAPITAL_RATE", "TIER1") + p2r_t1_share * p2r + cbr) * trea
    required_total = (p.get("CAPITAL_RATE", "TOTAL") + p2r + cbr) * trea
    leverage_exposure = float(
        pd.to_numeric(exp["gross_carrying_amount"], errors="coerce").fillna(0).sum()
        + pd.to_numeric(exp["committed_undrawn"], errors="coerce").fillna(0).sum()
        * p.get("LEVERAGE", "OFF_BALANCE_CCF")
        + _num(out.metrics.get("RWEA_CCR"))
    )
    leverage_ratio = tier1 / max(leverage_exposure, 1)
    eligible_liabilities = float(
        comp.loc[comp["capital_class"] == "ELIGIBLE_LIABILITY", "signed_amount"].sum()
    )
    eligible_mrel = total + eligible_liabilities
    mrel_risk_req = rate("MREL", basis="TREA") * trea
    mrel_lev_req = rate("MREL", basis="LEVERAGE_EXPOSURE") * leverage_exposure
    tlac_risk_req = rate("TLAC", basis="TREA") * trea
    tlac_lev_req = rate("TLAC", basis="LEVERAGE_EXPOSURE") * leverage_exposure
    mrel_headroom = (
        min(eligible_mrel - mrel_risk_req, eligible_mrel - mrel_lev_req)
        if mrel_lev_req
        else eligible_mrel - mrel_risk_req
    )
    tlac_headroom = (
        min(eligible_mrel - tlac_risk_req, eligible_mrel - tlac_lev_req)
        if tlac_lev_req
        else eligible_mrel - tlac_risk_req
    )
    out.metrics.update(
        {
            "CET1": cet1,
            "AT1": at1,
            "T2": tier2,
            "TIER1": tier1,
            "TOTAL_OWN_FUNDS": total,
            "CET1_RATIO": cet1 / trea,
            "TIER1_RATIO": tier1 / trea,
            "TOTAL_CAPITAL_RATIO": total / trea,
            "P2R_RATE": p2r,
            "P2R_AMOUNT": p2r_amount,
            "P2R_CET1_SHARE": p2r_cet1_share,
            "P2R_TIER1_SHARE": p2r_t1_share,
            "CBR_RATE": cbr,
            "P2G_RATE": p2g,
            "CET1_HEADROOM": cet1 - required_cet1,
            "TIER1_HEADROOM": tier1 - required_t1,
            "TOTAL_HEADROOM": total - required_total,
            "LEVERAGE_EXPOSURE": leverage_exposure,
            "LEVERAGE_RATIO": leverage_ratio,
            "MREL_HEADROOM": mrel_headroom,
            "TLAC_HEADROOM": tlac_headroom,
            "P2R_RWA_EQUIVALENT": p2r_amount / p.get("RWA_EQUIVALENT", "REFERENCE_RATE"),
        }
    )
    out.results["Capital_Stack"] = pd.DataFrame(
        [
            {
                "capital_layer": "CET1",
                "available": cet1,
                "required": required_cet1,
                "headroom": cet1 - required_cet1,
                "ratio": cet1 / trea,
            },
            {
                "capital_layer": "TIER1",
                "available": tier1,
                "required": required_t1,
                "headroom": tier1 - required_t1,
                "ratio": tier1 / trea,
            },
            {
                "capital_layer": "TOTAL",
                "available": total,
                "required": required_total,
                "headroom": total - required_total,
                "ratio": total / trea,
            },
            {
                "capital_layer": "P2G_TARGET",
                "available": total,
                "required": required_total + p2g * trea,
                "headroom": total - required_total - p2g * trea,
                "ratio": total / trea,
            },
        ]
    )
    out.results["Capital_Stack"]["formula_id"] = "OWN_FUNDS"
    out.results["Parallel_Constraints"] = pd.DataFrame(
        [
            {
                "constraint": "LEVERAGE",
                "eligible": tier1,
                "requirement": rate("LEVERAGE", p.get("LEVERAGE", "DEFAULT_REQUIREMENT")) * leverage_exposure,
                "headroom": tier1
                - rate("LEVERAGE", p.get("LEVERAGE", "DEFAULT_REQUIREMENT")) * leverage_exposure,
                "ratio": leverage_ratio,
            },
            {
                "constraint": "MREL",
                "eligible": eligible_mrel,
                "requirement": max(mrel_risk_req, mrel_lev_req),
                "headroom": mrel_headroom,
                "ratio": eligible_mrel / trea,
            },
            {
                "constraint": "TLAC",
                "eligible": eligible_mrel,
                "requirement": max(tlac_risk_req, tlac_lev_req),
                "headroom": tlac_headroom,
                "ratio": eligible_mrel / trea,
            },
        ]
    )
    out.results["Parallel_Constraints"]["formula_id"] = "LEVERAGE_MREL_TLAC"
    out.results["RWA_Equivalents"] = pd.DataFrame(
        [
            {
                "equivalent_type": "P2R_EQUIVALENT",
                "capital_amount": p2r_amount,
                "reference_rate": p.get("RWA_EQUIVALENT", "REFERENCE_RATE"),
                "rwa_equivalent": p2r_amount / p.get("RWA_EQUIVALENT", "REFERENCE_RATE"),
                "official": False,
                "additive_to_legal_trea": False,
                "formula_id": "P2R_RWA_EQ",
            }
        ]
    )
    out.add_control(
        "CAPITAL_ORDER", cet1 <= tier1 <= total, True, cet1 <= tier1 <= total, "CET1 <= T1 <= Total"
    )


def _interp_curve(curve: pd.DataFrame, t: float) -> float:
    c = curve.sort_values("tenor_years")
    return float(np.interp(t, pd.to_numeric(c["tenor_years"]), pd.to_numeric(c["zero_rate"])))


def calculate_irrbb(t: Mapping[str, pd.DataFrame], ctx: CalculationContext, out: CalculationBundle) -> None:
    p = ctx.parameters
    cf = t["cashflow"].copy()
    curve = t["yield_curve"]
    scenarios = t["irrbb_scenario"]
    cf["payment_date"] = pd.to_datetime(cf["payment_date"])
    cf["repricing_date"] = pd.to_datetime(cf["repricing_date"])
    asof = pd.Timestamp(ctx.as_of_date)
    cf["t"] = (cf["payment_date"] - asof).dt.days / p.get("TIME_CONVENTION", "DAYS_PER_YEAR")
    cf = cf[cf["t"] > 0].copy()
    cf["signed_cf"] = (
        pd.to_numeric(cf["principal_amount"], errors="coerce").fillna(0)
        + pd.to_numeric(cf["interest_amount"], errors="coerce").fillna(0)
        + pd.to_numeric(cf["fee_margin_amount"], errors="coerce").fillna(0)
    ) * pd.to_numeric(cf["sign"], errors="coerce").fillna(1)
    cf["repricing_t"] = (cf["repricing_date"] - asof).dt.days / p.get("TIME_CONVENTION", "DAYS_PER_YEAR")
    band_edges = sorted(
        pd.to_numeric(t["behavioural_assumption"]["time_band_years"], errors="coerce").dropna().unique()
    )
    if not band_edges:
        band_edges = sorted(pd.to_numeric(curve["tenor_years"], errors="coerce").dropna().unique())

    def assign_band(value: float) -> str:
        edge = next((x for x in band_edges if value <= x), None)
        return f"LE_{edge:g}Y" if edge is not None else f"GT_{band_edges[-1]:g}Y"

    cf["repricing_band"] = cf["repricing_t"].map(assign_band)
    gap_rows = []
    for band, g in cf.groupby("repricing_band", sort=False):
        signed = pd.to_numeric(g["principal_amount"], errors="coerce").fillna(0) * pd.to_numeric(
            g["sign"], errors="coerce"
        ).fillna(0)
        assets = float(signed[signed > 0].sum())
        liabilities = float(-signed[signed < 0].sum())
        gap_rows.append(
            {
                "repricing_band": band,
                "asset_principal": assets,
                "liability_principal": liabilities,
                "net_gap": assets - liabilities,
                "cashflow_count": len(g),
                "behavioural_cashflow_count": int(g["behavioural_flag"].map(_bool).sum()),
                "formula_id": "IRRBB_NII",
            }
        )
    out.results["IRRBB_Repricing_Gap"] = pd.DataFrame(gap_rows)
    base_pv_by_currency = {}
    for currency, g in cf.groupby("currency"):
        currency_curve = curve[curve["currency"].astype(str) == str(currency)]
        if currency_curve.empty:
            raise ValueError(f"IRRBB-Zinskurve fehlt für {currency}")
        base_pv_by_currency[str(currency)] = sum(
            _num(r["signed_cf"])
            * f.discount_factor(_interp_curve(currency_curve, _num(r["t"])), _num(r["t"]))
            for _, r in g.iterrows()
        )
    base_pv = sum(base_pv_by_currency.values())
    currency_rows = []
    nii_band_rows = []
    for _, s in scenarios.iterrows():
        sc = str(s["scenario_type"])
        currency = str(s["currency"])
        currency_cf = cf[cf["currency"].astype(str) == currency]
        if currency_cf.empty:
            continue
        currency_curve = curve[curve["currency"].astype(str) == currency]
        pv = 0.0
        bp_unit = p.get("IRRBB_MODEL", "BASIS_POINTS_PER_UNIT")
        parallel = _num(s["parallel_bp"]) / bp_unit
        short = _num(s["short_bp"]) / bp_unit
        long = _num(s["long_bp"]) / bp_unit
        for _, r in currency_cf.iterrows():
            tv = _num(r["t"])
            base = _interp_curve(currency_curve, tv)
            shock = f.irrbb_shock(sc, tv, parallel, short, long, params=p)
            zr = f.shocked_zero_rate(base, shock, tv, params=p)
            pv += _num(r["signed_cf"]) * f.discount_factor(zr, tv)
        delta = pv - base_pv_by_currency[currency]
        # Einjahres-NII: bis zum Repricing offene Kapitalbeträge mit Restjahresanteil.
        nii_delta = 0.0
        band_contributions = {band: 0.0 for band in currency_cf["repricing_band"].unique()}
        for _, r in currency_cf.iterrows():
            repr_t = max(
                (pd.Timestamp(r["repricing_date"]) - asof).days / p.get("TIME_CONVENTION", "DAYS_PER_YEAR"), 0
            )
            horizon = p.get("IRRBB_MODEL", "HORIZON_YEARS")
            if repr_t <= horizon:
                shock = f.irrbb_shock(sc, max(repr_t, f.EPSILON), parallel, short, long, params=p)
                contribution = (
                    _num(r["principal_amount"]) * _num(r["sign"], 1) * shock * max(horizon - repr_t, 0)
                )
                nii_delta += contribution
                band_contributions[str(r["repricing_band"])] += contribution
        nii_band_rows.extend(
            {
                "scenario": sc,
                "currency": currency,
                "repricing_band": band,
                "delta_nii": value,
                "ear_contribution": max(-value, 0),
                "formula_id": "IRRBB_NII",
            }
            for band, value in band_contributions.items()
        )
        currency_rows.append(
            {
                "scenario": sc,
                "currency": currency,
                "eve_base": base_pv_by_currency[currency],
                "eve_shocked": pv,
                "delta_eve": delta,
                "eve_loss": max(-delta, 0),
                "delta_nii": nii_delta,
                "ear": max(-nii_delta, 0),
                "formula_id": "IRRBB_EVE/IRRBB_NII",
            }
        )
    currency_result = pd.DataFrame(currency_rows)
    result = (
        currency_result.groupby("scenario", as_index=False).agg(
            eve_base=("eve_base", "sum"),
            eve_shocked=("eve_shocked", "sum"),
            delta_eve=("delta_eve", "sum"),
            delta_nii=("delta_nii", "sum"),
        )
        if not currency_result.empty
        else pd.DataFrame()
    )
    if not result.empty:
        result["eve_loss"] = (-result["delta_eve"]).clip(lower=0)
        result["ear"] = (-result["delta_nii"]).clip(lower=0)
        result["formula_id"] = "IRRBB_EVE/IRRBB_NII"
    worst_eve = float(result["eve_loss"].max()) if not result.empty else 0
    parallel = result[result["scenario"].isin(["PARALLEL_UP", "PARALLEL_DOWN"])]
    worst_nii = float(parallel["ear"].max()) if not parallel.empty else 0
    tier1 = max(_num(out.metrics.get("TIER1")), 1)
    # Deterministische stochastische Approximation, separat vom SOT.
    rng = np.random.default_rng(int(p.get("IRRBB_MODEL", "RANDOM_SEED")))
    z = rng.normal(0, p.get("IRRBB_MODEL", "RATE_VOLATILITY"), int(p.get("IRRBB_MODEL", "SIMULATION_PATHS")))
    duration_proxy = sum(
        abs(_num(r["signed_cf"]))
        * _num(r["t"])
        * f.discount_factor(
            _interp_curve(curve[curve["currency"].astype(str) == str(r["currency"])], _num(r["t"])),
            _num(r["t"]),
        )
        for _, r in cf.iterrows()
    )
    losses = np.maximum(z * duration_proxy, 0)
    var = float(np.quantile(losses, p.get("IRRBB_MODEL", "VAR_CONFIDENCE")))
    es = float(losses[losses >= var].mean()) if np.any(losses >= var) else var
    eve_threshold = p.get("IRRBB_SOT", "EVE")
    nii_threshold = p.get("IRRBB_SOT", "NII")
    csrbb_factor = p.get("CSRBB_MODEL", "STRESS_FACTOR")
    out.results["IRRBB_Scenarios"] = result
    out.results["IRRBB_Currency_Scenarios"] = currency_result
    out.results["IRRBB_NII_Bands"] = pd.DataFrame(nii_band_rows)
    out.results["IRRBB_Risk_Measures"] = pd.DataFrame(
        [
            {
                "worst_eve_loss": worst_eve,
                "eve_sot_ratio": worst_eve / tier1,
                "eve_outlier": worst_eve / tier1 > eve_threshold,
                "worst_nii_decline": worst_nii,
                "nii_sot_ratio": worst_nii / tier1,
                "nii_outlier": worst_nii / tier1 > nii_threshold,
                "eve_var_99": var,
                "eve_es_99": es,
                "csrbb_stress_loss": abs(base_pv) * csrbb_factor,
                "formula_id": "IRRBB_EVE/IRRBB_NII",
            }
        ]
    )
    out.metrics.update(
        {
            "WORST_EVE_LOSS": worst_eve,
            "EVE_SOT_RATIO": worst_eve / tier1,
            "WORST_NII_DECLINE": worst_nii,
            "NII_SOT_RATIO": worst_nii / tier1,
            "EVE_VAR_99": var,
            "EVE_ES_99": es,
            "CSRBB_LOSS": abs(base_pv) * csrbb_factor,
        }
    )
    behaviour = t["behavioural_assumption"]
    for (segment, assumption), g in behaviour.groupby(["segment", "assumption_type"]):
        total = float(pd.to_numeric(g["weight"], errors="coerce").sum())
        out.add_control(
            f"BEHAVIOUR_WEIGHTS_{segment}_{assumption}",
            abs(total - 1.0) < p.get("CONTROL", "RATE_TOLERANCE"),
            1.0,
            total,
            "Verhaltensgewichte summieren sich auf eins",
        )


def calculate_icaap(t: Mapping[str, pd.DataFrame], ctx: CalculationContext, out: CalculationBundle) -> None:
    p = ctx.parameters
    ec = t["economic_capital_input"].copy()
    ec["ec_diversifiable"] = (pd.to_numeric(ec["var_loss"]) - pd.to_numeric(ec["provisions"])).clip(
        lower=0
    ) + pd.to_numeric(ec["model_risk_addon"])
    ec["ec_standalone"] = ec["ec_diversifiable"] + pd.to_numeric(ec["non_diversifiable_addon"])
    ids = list(ec["risk_id"])
    caps = list(pd.to_numeric(ec["ec_diversifiable"]))
    corr_in = t["risk_correlation"]
    corr = []
    for a in ids:
        row = []
        for b in ids:
            x = corr_in[(corr_in["risk_id_a"] == a) & (corr_in["risk_id_b"] == b)]["correlation"]
            row.append(_num(x.iloc[0], 1.0 if a == b else 0.0) if not x.empty else (1.0 if a == b else 0.0))
        corr.append(row)
    corr_array = np.asarray(corr, dtype=float)
    symmetric = np.allclose(corr_array, corr_array.T, atol=p.get("CONTROL", "RATE_TOLERANCE"))
    min_eigenvalue = float(np.linalg.eigvalsh((corr_array + corr_array.T) / 2).min())
    out.add_control(
        "ICAAP_CORRELATION_SYMMETRIC", symmetric, True, symmetric, "Korrelationsmatrix ist symmetrisch"
    )
    out.add_control(
        "ICAAP_CORRELATION_PSD",
        min_eigenvalue >= -p.get("CONTROL", "RATE_TOLERANCE"),
        ">=0",
        min_eigenvalue,
        "Korrelationsmatrix ist positiv semidefinit",
    )
    raw = f.correlated_capital(caps, corr)
    linear_diversifiable = sum(caps)
    diversification = min(
        linear_diversifiable - raw, p.get("ICAAP", "DIVERSIFICATION_CAP") * linear_diversifiable
    )
    nondiv = float(pd.to_numeric(ec["non_diversifiable_addon"]).sum())
    linear = float(pd.to_numeric(ec["ec_standalone"]).sum())
    aggregate = linear_diversifiable - diversification + nondiv
    rb = t["risk_bearing_capacity"]
    capacity = (
        float(
            (
                (
                    pd.to_numeric(rb["amount"])
                    * pd.to_numeric(rb["eligibility_factor"])
                    * (1 - pd.to_numeric(rb["haircut"]))
                )
                - pd.to_numeric(rb["management_reserve"])
            ).sum()
        )
        if not rb.empty
        else _num(out.metrics.get("CET1"))
        + p.get("ICAAP", "FALLBACK_AT1_SHARE") * _num(out.metrics.get("AT1"))
        - p.get("ICAAP", "FALLBACK_MANAGEMENT_RESERVE")
    )
    out.results["EC_Standalone"] = ec[
        [
            "risk_id",
            "expected_loss",
            "var_loss",
            "stress_loss",
            "provisions",
            "model_risk_addon",
            "non_diversifiable_addon",
            "ec_diversifiable",
            "ec_standalone",
        ]
    ].copy()
    out.results["EC_Standalone"]["formula_id"] = "ICAAP_EC"
    out.results["EC_Aggregation"] = pd.DataFrame(
        [
            {
                "ec_linear": linear,
                "ec_correlated_raw": raw,
                "recognized_diversification": diversification,
                "ec_aggregate": aggregate,
                "economic_capacity": capacity,
                "economic_headroom": capacity - aggregate,
                "economic_utilisation": aggregate / max(capacity, 1),
                "ec_rwa_equivalent": aggregate / p.get("RWA_EQUIVALENT", "REFERENCE_RATE"),
                "formula_id": "ICAAP_EC",
            }
        ]
    )
    # Normative Projektion je Szenario.
    projections = []
    base_cet1 = _num(out.metrics.get("CET1"))
    base_trea = _num(out.metrics.get("TREA"))
    base_lev = _num(out.metrics.get("LEVERAGE_EXPOSURE"))
    for scenario, g in t["normative_projection"].sort_values("projection_year").groupby("scenario_id"):
        cet1 = base_cet1
        for _, r in g.iterrows():
            cet1 += (
                _num(r["profit_after_tax"])
                - _num(r["distributions"])
                + _num(r["oci_change"])
                + _num(r["cet1_issuance"])
                - _num(r["cet1_redemption"])
            )
            trea = base_trea * _num(r["trea_multiplier"], 1)
            lev = base_lev * _num(r["leverage_exposure_multiplier"], 1)
            required = (
                p.get("CAPITAL_RATE", "CET1")
                + _num(out.metrics.get("P2R_CET1_SHARE")) * _num(out.metrics.get("P2R_RATE"))
                + _num(out.metrics.get("CBR_RATE"))
            ) * trea
            projections.append(
                {
                    "scenario": scenario,
                    "projection_year": int(r["projection_year"]),
                    "cet1": cet1,
                    "trea": trea,
                    "cet1_ratio": cet1 / max(trea, 1),
                    "cet1_required": required,
                    "cet1_headroom": cet1 - required,
                    "leverage_ratio": (_num(out.metrics.get("TIER1")) + cet1 - base_cet1) / max(lev, 1),
                }
            )
    norm = pd.DataFrame(projections)
    norm["formula_id"] = "ICAAP_NORMATIVE"
    out.results["Normative_Projection"] = norm
    out.metrics.update(
        {
            "EC_LINEAR": linear,
            "EC_AGGREGATE": aggregate,
            "ECONOMIC_CAPACITY": capacity,
            "ECONOMIC_HEADROOM": capacity - aggregate,
            "EC_RWA_EQUIVALENT": aggregate / p.get("RWA_EQUIVALENT", "REFERENCE_RATE"),
            "NORMATIVE_MIN_HEADROOM": float(norm["cet1_headroom"].min()) if not norm.empty else 0,
        }
    )
    out.results["RWA_Equivalents"] = pd.concat(
        [
            out.results["RWA_Equivalents"],
            pd.DataFrame(
                [
                    {
                        "equivalent_type": "EC_EQUIVALENT",
                        "capital_amount": aggregate,
                        "reference_rate": p.get("RWA_EQUIVALENT", "REFERENCE_RATE"),
                        "rwa_equivalent": aggregate / p.get("RWA_EQUIVALENT", "REFERENCE_RATE"),
                        "official": False,
                        "additive_to_legal_trea": False,
                        "formula_id": "EC_RWA_EQ",
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    irrbb_management_capital = max(
        _num(out.metrics.get("WORST_EVE_LOSS")),
        _num(out.metrics.get("WORST_NII_DECLINE")),
        _num(out.metrics.get("EVE_ES_99")),
    ) + _num(out.metrics.get("CSRBB_LOSS"))
    reference_rate = p.get("RWA_EQUIVALENT", "REFERENCE_RATE")
    out.results["Pillar2_Bridge"] = pd.DataFrame(
        [
            {
                "measure": "IRRBB_CSRBB_MANAGEMENT_CAPITAL",
                "normative_amount": _num(out.metrics.get("WORST_NII_DECLINE")),
                "economic_amount": max(
                    _num(out.metrics.get("WORST_EVE_LOSS")), _num(out.metrics.get("EVE_ES_99"))
                ),
                "csrbb_amount": _num(out.metrics.get("CSRBB_LOSS")),
                "selected_capital": irrbb_management_capital,
                "supervisory_p2r_amount": _num(out.metrics.get("P2R_AMOUNT")),
                "automatic_p2r_translation": False,
                "formula_id": "PILLAR2_BRIDGE",
            }
        ]
    )
    out.results["RWA_Equivalents"] = pd.concat(
        [
            out.results["RWA_Equivalents"],
            pd.DataFrame(
                [
                    {
                        "equivalent_type": "IRRBB_CSRBB_MANAGEMENT_EQUIVALENT",
                        "capital_amount": irrbb_management_capital,
                        "reference_rate": reference_rate,
                        "rwa_equivalent": irrbb_management_capital / reference_rate,
                        "official": False,
                        "additive_to_legal_trea": False,
                        "formula_id": "IRRBB_RWA_EQ",
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    out.metrics.update(
        {
            "IRRBB_MANAGEMENT_CAPITAL": irrbb_management_capital,
            "IRRBB_RWA_EQUIVALENT": irrbb_management_capital / reference_rate,
        }
    )
    out.add_control(
        "EC_CAPACITY",
        capacity - aggregate >= 0,
        ">=0",
        capacity - aggregate,
        "Ökonomische Risikotragfähigkeit",
    )
