from datetime import date
from pathlib import Path

import pandas as pd
import pytest
from hypothesis import given
from hypothesis import strategies as st

from rwa_engine import formulas as f
from rwa_engine.config_io import load_regulatory_config, regulatory_parameter_items
from rwa_engine.excel_io import validate_tables
from rwa_engine.parameters import ParameterError, ParameterStore
from rwa_engine.pipeline import _validate_legal_files
from rwa_engine.synthetic import generate_synthetic_tables

LEGAL_URLS = (
    "https://riskdatascience.net/impressum/",
    "https://riskdatascience.net/datenschutzerklaerung/",
)


def parameter_store() -> ParameterStore:
    config = load_regulatory_config("daten/konfiguration/regulatory/crr3_eu_2026_v1.yaml")
    return ParameterStore(
        pd.DataFrame(
            [
                {
                    "parameter_key": x["key"],
                    "dimension_1": str(x.get("d1", "")),
                    "dimension_2": str(x.get("d2", "")),
                    "parameter_value": x["value"],
                }
                for x in regulatory_parameter_items(config)
            ]
        )
    )


def test_missing_and_duplicate_parameters_fail_closed():
    with pytest.raises(ParameterError):
        ParameterStore(
            pd.DataFrame(
                [
                    {"parameter_key": "X", "dimension_1": "", "dimension_2": "", "parameter_value": 1},
                    {"parameter_key": "X", "dimension_1": "", "dimension_2": "", "parameter_value": 2},
                ]
            )
        )
    with pytest.raises(ParameterError):
        parameter_store().get("DOES_NOT_EXIST")


def test_no_business_dataset_is_embedded_in_python_generator():
    source = (Path(__file__).resolve().parents[1] / "src" / "rwa_engine" / "synthetic.py").read_text(
        encoding="utf-8"
    )
    prohibited = (
        "np.random",
        "lognormal",
        "24_000_000_000",
        "Synthetische Mittelstandsbank AG",
        'INTEREST_INCOME": [',
        "portfolio_choices",
    )
    assert not [token for token in prohibited if token in source]


def test_profile_date_shift_preserves_legal_publication_dates():
    base = generate_synthetic_tables(as_of=date(2026, 8, 31))
    shifted = generate_synthetic_tables(as_of=date(2027, 8, 31))
    assert set(pd.to_datetime(shifted["exposure_lot"]["as_of_date"]).dt.date) == {date(2027, 8, 31)}
    assert list(pd.to_datetime(base["legal_source"]["publication_date"]).dt.date) == list(
        pd.to_datetime(shifted["legal_source"]["publication_date"]).dt.date
    )
    delta = (
        pd.to_datetime(shifted["product_contract"]["maturity_date"])
        - pd.to_datetime(base["product_contract"]["maturity_date"])
    ).dt.days
    assert set(delta.dropna()) == {365}


def test_validation_rejects_invalid_pd_and_missing_business_key():
    tables = generate_synthetic_tables()
    tables["irb_parameter"].loc[tables["irb_parameter"].index[0], "pd_estimate"] = 1.01
    tables["party"].loc[tables["party"].index[0], "business_key"] = None
    codes = {issue.code for issue in validate_tables(tables) if issue.severity == "ERROR"}
    assert {"VALUE_OUT_OF_RANGE", "MISSING_REQUIRED_VALUE"}.issubset(codes)


def test_legal_sources_are_local_or_have_verified_external_provenance():
    assert not _validate_legal_files(generate_synthetic_tables())


def test_canonical_legal_links_are_visible_in_metadata_readme_and_app():
    root = Path(__file__).resolve().parents[1]
    public_surfaces = (
        root / "pyproject.toml",
        root / "README.md",
        root / "src" / "rwa_engine" / "web" / "static" / "index.html",
    )
    for path in public_surfaces:
        content = path.read_text(encoding="utf-8")
        assert all(url in content for url in LEGAL_URLS), f"legal link missing from {path.name}"


@given(
    gross=st.floats(min_value=0, max_value=1e10, allow_nan=False, allow_infinity=False),
    undrawn_a=st.floats(min_value=0, max_value=1e10, allow_nan=False, allow_infinity=False),
    increment=st.floats(min_value=0, max_value=1e10, allow_nan=False, allow_infinity=False),
)
def test_sa_ead_is_monotone_in_undrawn(gross, undrawn_a, increment):
    params = parameter_store()

    def ead(undrawn):
        return f.sa_ead(
            gross_carrying_amount=gross,
            specific_adjustments=0,
            additional_valuation_adjustments=0,
            other_own_funds_reductions=0,
            committed_undrawn=undrawn,
            annex_i_class="CLASS_3",
            data_path="GROSS",
            net_carrying_amount_article_111=None,
            params=params,
        )[2]

    assert ead(undrawn_a + increment) >= ead(undrawn_a)


@given(
    u=st.floats(min_value=0, max_value=1e12, allow_nan=False, allow_infinity=False),
    s=st.floats(min_value=0, max_value=1e12, allow_nan=False, allow_infinity=False),
    factor=st.floats(min_value=0, max_value=1, allow_nan=False, allow_infinity=False),
)
def test_output_floor_never_reduces_unfloored_trea(u, s, factor):
    trea, uplift, _ = f.output_floor(u, s, factor, optional_cap=False, cap_multiplier=1)
    assert trea >= u and uplift >= 0
