# IRB default correction — version 1.2.1

## Regulatory rule and scope

CRR Article 153(1)(ii) distinguishes supervisory LGD from own estimates;
Article 154 governs retail, and Article 158(5) governs expected loss.
For a defaulted supervisory-LGD (FIRB) exposure, K, RW and RWEA are zero,
while EL = effective PD × LGD × EAD = LGD × EAD. ELBE is irrelevant.
For own LGD estimates (AIRB and supported retail), K = max(LGD − ELBE, 0)
and EL = ELBE × EAD. Supporting-factor eligibility rules are unchanged.

Source: [CRR consolidated text, Articles 153, 154 and 158](https://eur-lex.europa.eu/eli/reg/2013/575/2026-01-01/eng).
This implements the previously documented distinction, not a new regulatory assumption.

## Input and API contract

The portfolio resolves LGD treatment from irb_approach and irb_subclass:
FIRB → SUPERVISORY; AIRB → OWN_ESTIMATES. Non-retail subclasses supported
by this formula path are CORPORATE, INSTITUTION and SOVEREIGN.
RETAIL_RESIDENTIAL, RETAIL_QRRE and RETAIL_OTHER require AIRB / OWN_ESTIMATES.
This mapping is a calculation contract, not a certification of regulatory
permission to use AIRB. Institution-specific approach permissions, LGD input
values and existing floors remain the user's responsibility.

Unknown approaches/subclasses and FIRB-retail combinations fail closed.
SLOTTING is not implemented as a separate calculation path in this library:
it is now explicitly rejected instead of silently using the corporate formula.
No slotting factors, correlations or maturity rules are introduced by this fix.
Performing maturity adjustments and the retail no-maturity-adjustment rule remain unchanged.

default_flag must be a recognised explicit boolean. If true, effective PD is
1 regardless of the supplied PD (which must still be in [0,1]).
If false, PD = 1 (including after a PD floor) is rejected. Detail results retain
pd_input alongside effective pd, defaulted and lgd_treatment. Caller data are
not modified.

The public irb_capital_requirement() adds the optional lgd_treatment argument.
For defaulted calls it is **required**, with value SUPERVISORY or OWN_ESTIMATES.
Missing/unknown values raise an error rather than guessing. Existing performing
calls retain their signatures/defaults and arithmetic; R appends the argument
after parameters to preserve positional compatibility.
The helper returns K, not total capital or a regulatory eligibility decision.

## Independent acceptance cases

For LGD .40, EAD 1,000,000, default true, supporting factor 1:

| Treatment | ELBE | K | RW | RWEA | EL |
|---|---:|---:|---:|---:|---:|
| FIRB | .10 | 0 | 0 | 0 | 400,000 |
| FIRB | .80 | 0 | 0 | 0 | 400,000 |
| AIRB / retail | .10 | .30 | 3.75 | 3,750,000 | 100,000 |
| AIRB / retail | .40 | 0 | 0 | 0 | 400,000 |
| AIRB / retail | .50 | 0 | 0 | 0 | 500,000 |

With eligible coverage 250,000, the FIRB case has shortfall 150,000 and excess 0.
Coverage comes from exposure_lot, not duplicate ad-hoc IRB columns.
Tests exercise the public calculate_tables() path in both applied and fully-loaded
views, EL/RWEA aggregates, CET1 shortfall deduction and the TREA/output-floor chain.
Both languages use these independently specified values, plus normal-distribution
reference calculations for performing FIRB/AIRB and retail.

## Reference data and migration

Synthetic input resources remain unchanged; they are not rewritten to conceal
the defect. Historical bundled outputs are historical snapshots, not new-version
acceptance evidence. Recalculate affected default portfolios with version 1.2.1.
The intentional differences from 1.2.0 are supervisory-default RWEA and EL,
their capital consequences, normalised default PD, additive audit columns and
rejection of ambiguous/unsupported inputs. Existing aggregation and own-funds
rules are retained; this patch does not redesign the coverage allocation model.
