# Canonical default flags — 1.2.2

The technical representation of a default must never change its regulatory result.
This patch replaces the inconsistent SA and IRB interpretation with one internal,
fail-closed regulatory boolean contract in both Python and native R.

## Accepted scalar values

| Meaning | Native inputs | Text inputs (case-insensitive; whitespace trimmed) |
|---|---|---|
| True | boolean true, integer 1, floating-point 1.0 | TRUE, 1, 1.0, YES, JA |
| False | boolean false, integer 0, floating-point 0.0 | FALSE, 0, 0.0, NO, NEIN |

Missing values (None/NULL/NA/NaN), empty strings, UNKNOWN, DEFAULT, Y, N,
2, -1 and non-finite numbers fail with
`default_flag must be an explicit boolean`; they are not treated as performing.

## One status for all calculation paths

After official bitemporal selection and designations, exposure_lot.default_flag
is normalised on a copy of the selected snapshot, before either reporting view
is run. SA, IRB, expected loss and supporting-factor eligibility use that same
boolean. Credit calculations invoked internally without the public snapshot
preparation use the same normalisation helper; already canonical flags are reused.

No caller-owned table or historical input workbook is mutated.
The normalised result drives actual KSA, the IRB SA-shadow, Standardised TREA
and the output floor. SA_Detail now includes the additive boolean `defaulted`,
matching IRB_Detail. Other convenience booleans are outside this patch.

## Regression evidence and independent references

Both languages consume byte-identical `regulatory_boolean_cases.csv` test vectors,
including native boolean/integer/float, text, missing and invalid groups.
Tests use explicit 2026-08-31 / 23:59:59 UTC snapshot times.

Public calculate_tables() tests compare mixed-representation portfolios with
canonical-boolean portfolios in both applied and fully-loaded views.
Every test exposure has corporate CQS 3, EAD EUR 1,000,000, no adjustments,
no CRM and supporting factor 1. Other capital modules are neutralised in these
reference cases so that the credit and floor expectations are independent:

- Default: SA RW 1.50; SA RWEA and shadow RWEA EUR 1,500,000 per exposure.
- Performing: SA RW .75; SA RWEA and shadow RWEA EUR 750,000 per exposure.
- Pure KSA: RWEA_KSA = U_TREA = TREA = sum of the exposure RWEA.
- FIRB default with LGD .40: K/RW/RWEA = 0; effective PD = 1; EL EUR 400,000.
- Binding floor at .725: default TREA EUR 1,087,500 per exposure.
  The former representation-only discrepancy of EUR 543,750 disappears.
- The performing IRB cases also bind the floor and retain effective PD .0005.
- Every invalid vector is rejected through the public API in both KSA and IRB cases.
- A Python call-count assertion verifies one raw-status normalisation per exposure
  shared by both reporting views, not one interpretation per credit path.

The prior FIRB, AIRB, performing, retail and complete-profile tests remain release
gates. Input resources and reference parameters are unchanged; no golden values
are relaxed to conceal a discrepancy.

## Migration

No public function signature changes and no new dependencies.
Use the same canonical exposure input column. Replace missing/ambiguous flags
with a documented true/false value before calculation. Existing accepted values
remain accepted. Version 1.2.1's explicit default `lgd_treatment` formula contract
is unchanged. Recompute portfolios that previously used decimal-number or
decimal-string default flags; historical bundled outputs remain historical.
