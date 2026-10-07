"""Canonical, fail-closed interpretation of regulatory boolean inputs."""
from numbers import Real

import numpy as np


def normalise_exposure_defaults(tables):
    """Return a non-mutating snapshot shared by both reporting views."""
    result = dict(tables)
    exposure = tables["exposure_lot"].copy()
    if exposure["default_flag"].dtype != bool:
        exposure["default_flag"] = exposure["default_flag"].map(
            lambda value: regulatory_bool(value, "default_flag")
        ).astype(bool)
    result["exposure_lot"] = exposure
    return result


def regulatory_bool(value, field_name):
    """Accept explicit boolean/0/1 scalars and documented text equivalents."""
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, Real) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().upper()
        if text in {"TRUE", "1", "1.0", "YES", "JA"}:
            return True
        if text in {"FALSE", "0", "0.0", "NO", "NEIN"}:
            return False
    raise ValueError(f"{field_name} must be an explicit boolean")
