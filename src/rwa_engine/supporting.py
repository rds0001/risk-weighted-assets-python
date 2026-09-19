"""CRR 501/501a support: explicit eligibility, transparent factors, legacy SA compatibility."""
# Copyright (C) 2026 RiskDataScience GmbH. SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

from math import isclose, isfinite

import pandas as pd

SUPPORT_FIELDS = {
    "sme_supporting_eligible": None,
    "infrastructure_supporting_eligible": None,
    "sme_total_amount_owed_eur": None,
    "supporting_factor_reference": "",
    "supporting_factor_approved_by": "",
}
IRB_SUPPORT_FIELDS = {"supporting_factor_type": "NONE", "supporting_factor": None, **SUPPORT_FIELDS}


def normalise_support_columns(frame, table):
    """Copy and add only additive optional columns; never repair invalid supplied values."""
    defaults = IRB_SUPPORT_FIELDS if table == "irb_parameter" else SUPPORT_FIELDS if table == "sa_classification" else {}
    if not defaults:
        return frame
    frame = frame.copy()
    for field, default in defaults.items():
        if field not in frame:
            frame[field] = default
    return frame


def _text(value):
    return "" if value is None or pd.isna(value) else str(value).strip()


def _flag(value):
    text = _text(value).upper()
    if text in {"", "FALSE", "0", "0.0", "NO", "NEIN"}:
        return False
    if text in {"TRUE", "1", "1.0", "YES", "JA"}:
        return True
    raise ValueError("Eligibility flags must be explicit booleans")


def _number(value, name, *, positive=False):
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number")
    try:
        result = float(value)
    except (ValueError, TypeError):
        raise ValueError(f"{name} must be a finite number") from None
    if not isfinite(result) or result < 0 or (positive and result == 0):
        raise ValueError(f"{name} must be finite and {'positive' if positive else 'non-negative'}")
    return result


def _factor(value):
    value = _number(value, "supporting factor", positive=True)
    if value > 1:
        raise ValueError("supporting factor must be in (0, 1]")
    return value


def sme_factor(amount, params):
    amount = _number(amount, "Article 501 E*", positive=True)
    threshold = _number(params.get("SUPPORTING_FACTOR", "SME_THRESHOLD_EUR"), "SME threshold", positive=True)
    low = _factor(params.get("SUPPORTING_FACTOR", "SME_LOWER"))
    high = _factor(params.get("SUPPORTING_FACTOR", "SME_UPPER"))
    return (min(amount, threshold) * low + max(amount - threshold, 0) * high) / amount


def infrastructure_factor(params):
    return _factor(params.get("SUPPORTING_FACTOR", "INFRASTRUCTURE"))


def apply_factors(rwea, sme=1.0, infrastructure=1.0):
    return _number(rwea, "RWEA") * _factor(sme) * _factor(infrastructure)


def irb_rwea(ead, k, params, sme=1.0, infrastructure=1.0):
    base = _number(ead, "EAD") * _number(k, "K") * _number(
        params.get("RWA_MULTIPLIER", "PILLAR1"), "RWA multiplier", positive=True)
    return apply_factors(base, sme, infrastructure)


def resolve_support(row, params, *, approach):
    """Eligibility flags attest ALL legal criteria; documentary evidence remains bank-owned."""
    sme = _flag(row.get("sme_supporting_eligible"))
    infra = _flag(row.get("infrastructure_supporting_eligible"))
    reference = _text(row.get("supporting_factor_reference"))
    approver = _text(row.get("supporting_factor_approved_by"))
    declared = _text(row.get("supporting_factor_type")).upper() or "NONE"
    supplied = row.get("supporting_factor")
    supplied = None if not _text(supplied) else _factor(supplied)
    evidence_present = any(_text(row.get(name)) for name in SUPPORT_FIELDS)
    sf = inf = 1.0
    status = "NONE"
    effective_type = "NONE"
    if sme or infra:
        if _flag(row.get("default_flag")):
            raise ValueError("Supporting factors are not allowed on defaulted exposures")
        if not reference or not approver:
            raise ValueError("Supporting factor requires reference and approved_by")
        cls = _text(row.get("irb_subclass") if approach == "IRB" else row.get("exposure_class"))
        if sme:
            allowed = cls.startswith("RETAIL") or cls in {"CORPORATE", "REAL_ESTATE"}
            if not allowed or _flag(row.get("adc_flag")):
                raise ValueError("Exposure class/ADC is not eligible for SME support")
            sales = row.get("annual_sales_eur")
            if sales is not None and _text(sales):
                ceiling = _number(params.get("SUPPORTING_FACTOR", "SME_SALES_MAX_EUR"), "SME turnover ceiling", positive=True)
                if _number(sales, "annual sales") > ceiling:
                    raise ValueError("SME turnover exceeds the regulatory ceiling")
            sf = sme_factor(row.get("sme_total_amount_owed_eur"), params)
        if infra:
            if cls not in {"CORPORATE", "CORPORATE_SME", "SPECIALISED_LENDING"}:
                raise ValueError("Infrastructure support requires an eligible corporate exposure class")
            inf = infrastructure_factor(params)
        effective_type = "SME_INFRASTRUCTURE" if sme and infra else "SME" if sme else "INFRASTRUCTURE"
        if declared not in {"NONE", effective_type}:
            raise ValueError("Declared supporting_factor_type conflicts with eligibility flags")
        if supplied is not None and not isclose(supplied, sf * inf, rel_tol=1e-10, abs_tol=1e-12):
            raise ValueError("Supplied supporting_factor differs from the calculated factor")
        status = "VERIFIED_INPUT"
    elif approach == "SA" and not evidence_present:
        # Existing SA inputs remain reproducible, not retrospectively certified.
        sf = supplied if supplied is not None else 1.0
        effective_type = declared
        status = "LEGACY_SA_UNVERIFIED" if sf != 1 else "NONE"
    elif (supplied is not None and supplied != 1) or declared != "NONE":
        raise ValueError("A supporting-factor reduction requires explicit eligibility")
    return {
        "sme_supporting_factor": sf if status != "LEGACY_SA_UNVERIFIED" else 1.0,
        "infrastructure_supporting_factor": inf,
        "supporting_factor": sf * inf,
        "supporting_factor_type": effective_type,
        "supporting_factor_status": status,
        "supporting_factor_reference": reference,
        "supporting_factor_approved_by": approver,
        "supporting_factor_formula_id": "CRR_501_501A" if status == "VERIFIED_INPUT" else status,
    }


def support_issues(tables):
    """Return structured issues without changing input frames; exposure checks repeat after snapshot."""
    from .parameters import ParameterStore
    issues = []
    params = None
    for name, approach in (("sa_classification", "SA"), ("irb_parameter", "IRB")):
        frame = tables.get(name)
        if frame is None:
            continue
        legacy_count = 0
        for _, row in frame.iterrows():
            try:
                if _flag(row.get("sme_supporting_eligible")) or _flag(row.get("infrastructure_supporting_eligible")):
                    if params is None:
                        params = ParameterStore(tables["regulatory_parameter"])
                detail = resolve_support(row, params, approach=approach)
                legacy_count += detail["supporting_factor_status"] == "LEGACY_SA_UNVERIFIED"
            except (ValueError, TypeError, KeyError) as exc:
                issues.append(("ERROR", "INVALID_SUPPORTING_FACTOR", name, _text(row.get("record_id")), "supporting_factor", str(exc)))
        if legacy_count:
            issues.append(("WARNING", "LEGACY_SA_SUPPORTING_FACTOR", name, "", "supporting_factor",
                           f"{legacy_count} legacy SA rows use supplied factors without eligibility evidence; not transferred to IRB"))
    return issues


def resolve_for_exposure(tables, row, params, *, approach):
    if _flag(row.get("sme_supporting_eligible")) or _flag(row.get("infrastructure_supporting_eligible")):
        context = support_context(tables, row["exposure_id"])
        context.update(row.to_dict())
        row = context
    return resolve_support(row, params, approach=approach)


def support_context(tables, exposure_id):
    """Resolve context from the selected snapshot only."""
    result = {}
    exp = tables["exposure_lot"]
    match = exp[exp["exposure_id"] == exposure_id]
    if len(match) == 1:
        result.update(match.iloc[0].to_dict())
        party = tables.get("party")
        if party is not None:
            parties = party[party["party_id"] == result.get("party_id")]
            if len(parties) == 1:
                result["annual_sales_eur"] = parties.iloc[0].get("annual_sales_eur")
    re = tables.get("real_estate_exposure")
    if re is not None:
        selected = re[re["exposure_id"] == exposure_id]
        if len(selected) == 1:
            result["adc_flag"] = selected.iloc[0].get("adc_flag")
    return result
