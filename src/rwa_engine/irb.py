"""Shared, fail-closed IRB default and LGD-treatment contract."""
from math import isfinite


def default_flag(value):
    text = str(value).strip().upper()
    if text in {"TRUE", "1", "1.0", "YES", "JA"}:
        return True
    if text in {"FALSE", "0", "0.0", "NO", "NEIN"}:
        return False
    raise ValueError("default_flag must be an explicit boolean")


def rate(value, name):
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite rate in [0, 1]")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite rate in [0, 1]") from exc
    if not isfinite(number) or not 0 <= number <= 1:
        raise ValueError(f"{name} must be a finite rate in [0, 1]")
    return number


def effective_pd(pd, defaulted, floor=0):
    if not isinstance(defaulted, bool):
        raise ValueError("defaulted must be a boolean")
    value = max(rate(pd, "pd"), rate(floor, "pd_floor"))
    if not defaulted and value == 1:
        raise ValueError("PD = 1 contradicts defaulted=False")
    return 1.0 if defaulted else value


def treatment_for(approach, subclass):
    retail = subclass in {"RETAIL_RESIDENTIAL", "RETAIL_QRRE", "RETAIL_OTHER"}
    if approach not in {"FIRB", "AIRB"}:
        raise ValueError("Unsupported irb_approach; SLOTTING requires a separate implementation")
    if not retail and subclass not in {"CORPORATE", "INSTITUTION", "SOVEREIGN"}:
        raise ValueError(f"Unsupported irb_subclass: {subclass}")
    if retail and approach != "AIRB":
        raise ValueError("Retail IRB requires AIRB / OWN_ESTIMATES, not FIRB")
    return "SUPERVISORY" if approach == "FIRB" else "OWN_ESTIMATES"


def resolve(pd, lgd, defaulted, elbe, treatment):
    """Return the same effective PD, default K and EL rate to both callers."""
    pd = effective_pd(pd, defaulted)
    lgd = rate(lgd, "lgd")
    if treatment is not None and (not isinstance(treatment, str) or
                                  treatment not in {"SUPERVISORY", "OWN_ESTIMATES"}):
        raise ValueError("lgd_treatment must be SUPERVISORY or OWN_ESTIMATES")
    if defaulted:
        if treatment is None:
            raise ValueError("lgd_treatment is required for defaulted exposures")
        if treatment == "SUPERVISORY":
            return pd, 0.0, pd * lgd
        elbe = rate(elbe, "elbe")
        return pd, max(lgd - elbe, 0.0), elbe
    return pd, None, pd * lgd
