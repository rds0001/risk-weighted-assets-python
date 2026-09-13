from datetime import date, datetime

from rwa_engine.contracts import COMMON_COLUMNS, TABLE_SPECS, WORKBOOKS
from rwa_engine.engines import CalculationContext
from rwa_engine.excel_io import select_official_as_of, validate_tables
from rwa_engine.parameters import ParameterStore
from rwa_engine.pipeline import _run_one
from rwa_engine.synthetic import generate_synthetic_tables


def test_contract_names_are_excel_safe_and_unique_per_workbook():
    seen = {}
    for name, spec in TABLE_SPECS.items():
        assert len(spec.sheet) <= 31
        assert spec.table_name.startswith("tbl_in_")
        assert len(set(spec.all_columns)) == len(spec.all_columns)
        assert set(COMMON_COLUMNS).issubset(spec.all_columns)
        seen.setdefault(spec.workbook, set())
        assert spec.table_name not in seen[spec.workbook]
        seen[spec.workbook].add(spec.table_name)
    assert len(WORKBOOKS) == 16


def test_synthetic_tables_cover_contract_and_references():
    tables = generate_synthetic_tables(as_of=date(2026, 8, 31), seed=5752026)
    assert set(tables) == set(TABLE_SPECS)
    assert len(tables["exposure_lot"]) == 1000
    assert set(tables["exposure_lot"]["approach"]) >= {"KSA", "FIRB", "AIRB"}
    assert not [i for i in validate_tables(tables) if i.severity == "ERROR"]


def test_official_selection_is_as_of_and_append_only():
    tables = generate_synthetic_tables(as_of=date(2026, 8, 31), seed=1)
    selected = select_official_as_of(tables["rule_set"], date(2026, 8, 31), datetime(2026, 8, 31, 23, 59))
    assert len(selected) == 2
    assert selected["is_official"].all()


def test_same_engine_accepts_ksa_bank_without_market_or_complex_products():
    tables = generate_synthetic_tables(as_of=date(2026, 8, 31), seed=2, bank_profile="KSA_BANK")
    ctx = CalculationContext(
        date(2026, 8, 31),
        datetime(2026, 8, 31, 23, 59),
        "CRR3-EU-2026",
        ParameterStore(tables["regulatory_parameter"]),
        "EUR",
        "LEGACY_2026",
        0.55,
    )
    result = _run_one(tables, ctx, fully_loaded=False)
    assert result.metrics["RWEA_IRB"] == 0
    assert result.metrics["K_MARKET"] == 0
    assert result.metrics["TREA"] > 0
    assert all(c["passed"] for c in result.controls)
