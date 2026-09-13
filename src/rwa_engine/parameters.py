"""Strikte Laufzeitabfrage versionierter fachlicher Parameter."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping

import pandas as pd

from .exceptions import ConfigurationError


class ParameterError(ConfigurationError):
    """Ein benötigter Fachparameter fehlt oder ist nicht eindeutig."""


def _dimension(value: object) -> str:
    return "" if value is None or pd.isna(value) else str(value).strip()


@dataclass(frozen=True)
class ParameterStore:
    """Eindeutiger Zugriff auf die offizielle Parametertabelle eines Laufs.

    Es gibt absichtlich keine fachlichen Defaultwerte. Fehlende Regeln führen
    zu einem kontrollierten Abbruch statt zu einer stillen Annahme.
    """

    frame: pd.DataFrame
    _values: Mapping[tuple[str, str, str], float] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        required = {"parameter_key", "dimension_1", "dimension_2", "parameter_value"}
        missing = required - set(self.frame.columns)
        if missing:
            raise ParameterError(f"Spalten in regulatory_parameter fehlen: {sorted(missing)}")
        normalized = self.frame.copy()
        normalized["parameter_key"] = normalized["parameter_key"].map(_dimension)
        normalized["dimension_1"] = normalized["dimension_1"].map(_dimension)
        normalized["dimension_2"] = normalized["dimension_2"].map(_dimension)
        keys = ["parameter_key", "dimension_1", "dimension_2"]
        duplicates = normalized.duplicated(keys, keep=False)
        if duplicates.any():
            examples = normalized.loc[duplicates, keys].drop_duplicates().head().to_dict("records")
            raise ParameterError(f"Mehrdeutige Fachparameter: {examples}")
        object.__setattr__(self, "frame", normalized)
        values: dict[tuple[str, str, str], float] = {}
        for _, row in normalized.iterrows():
            value = pd.to_numeric(pd.Series([row["parameter_value"]]), errors="coerce").iloc[0]
            if pd.isna(value):
                raise ParameterError(
                    "Parameter ist nicht numerisch: "
                    f"{row['parameter_key']}[{row['dimension_1']},{row['dimension_2']}]"
                )
            values[(row["parameter_key"], row["dimension_1"], row["dimension_2"])] = float(value)
        object.__setattr__(self, "_values", values)

    def get(self, key: str, dimension_1: object = "", dimension_2: object = "") -> float:
        d1, d2 = _dimension(dimension_1), _dimension(dimension_2)
        lookup = (str(key), d1, d2)
        if lookup not in self._values:
            raise ParameterError(f"Parameter nicht eindeutig vorhanden: {key}[{d1},{d2}]")
        return self._values[lookup]

    def has(self, key: str, dimension_1: object = "", dimension_2: object = "") -> bool:
        d1, d2 = _dimension(dimension_1), _dimension(dimension_2)
        return (str(key), d1, d2) in self._values

    def require(self, keys: Iterable[tuple[str, object, object]]) -> None:
        missing = [(k, _dimension(d1), _dimension(d2)) for k, d1, d2 in keys if not self.has(k, d1, d2)]
        if missing:
            raise ParameterError(f"Benötigte Fachparameter fehlen: {missing}")
