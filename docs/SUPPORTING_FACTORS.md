# Credit supporting factors — version 1.2.0

Copyright (C) 2026 RiskDataScience GmbH. GPL-3.0-only.

## Scope and calculation

The SA and IRB paths can apply Article 501 SME and Article 501a infrastructure
support separately or together. IRB calculation is:

`RWEA_before = EAD * RWA_MULTIPLIER[PILLAR1] * K`
`RWEA_after = RWEA_before * SME_factor * infrastructure_factor`

K, PD, LGD, EAD, expected loss, shortfall and excess are not reduced by this step.
The pre-existing SME correlation adjustment is a different mechanism.

The SME helper uses the weighted Article 501 formula: the first EUR 2.5 million
of E* at 0.7619 and the remainder at 0.85, divided by E*. E* must be positive
and determined under the Article's institution-group/connected-client rules,
including residential collateral exclusions and the fallback when the initially
calculated amount is zero. Do not substitute individual EAD or annual turnover.
Infrastructure support is 0.75 by default. Both factors can apply together.

Values are in the versioned SUPPORTING_FACTOR parameter rows:
SME_THRESHOLD_EUR, SME_LOWER, SME_UPPER, SME_SALES_MAX_EUR, INFRASTRUCTURE.
Use existing controlled parameter overrides for sensitivities; do not edit code.
An older dataset needs these explicit parameter rows only if claiming new support.
They are materialized automatically when generating a new dataset.

## Public formula functions

- `sme_supporting_factor(total_amount_owed_eur, parameters=...)`: weighted factor.
- `infrastructure_supporting_factor(parameters=...)`: configured infrastructure rate.
- `apply_credit_supporting_factors(rwea, sme_factor=1, infrastructure_factor=1)`:
  applies both components once.
- `irb_risk_weighted_assets(ead, capital_requirement, ..., parameters=...)`:
  complete RWA amount from unadjusted K.

Python uses keyword-only optional arguments. R allows named arguments.
These are numeric building blocks, NOT eligibility certificates. Amounts supplied
to the SME helper are EUR. Other pure amount calculations preserve the input unit.

## Input contract and eligibility

Optional additive fields on both `sa_classification` and `irb_parameter`:

| Field | Meaning |
|---|---|
| sme_supporting_eligible | Explicit attestation that ALL applicable Article 501 conditions hold |
| infrastructure_supporting_eligible | Explicit attestation that ALL applicable Article 501a conditions hold |
| sme_total_amount_owed_eur | Reviewed E* in EUR; required when SME support is requested |
| supporting_factor_reference | Non-empty bank-owned evidence/checklist reference |
| supporting_factor_approved_by | Non-empty governance approval reference |

`irb_parameter` additionally accepts `supporting_factor_type` and
`supporting_factor`, already present in the SA input contract.
The type can be NONE (derive from flags), SME, INFRASTRUCTURE or SME_INFRASTRUCTURE.
Leave the numeric factor blank to derive it. If supplied, it must match the
calculated product; it is not an unrestricted discount override.

The engine rejects defaulted exposures, invalid/missing numeric values and
unsupported classes for requested relief. SME support excludes ADC and checks
available turnover against the configured SME ceiling. Infrastructure support
requires an eligible corporate class. Context is checked again against the
selected exposure snapshot, including party and real-estate data.

A flag attests all remaining qualitative criteria, including the applicable
environmental conditions for newer infrastructure lending. The engine cannot
verify bank contracts or external legal evidence. Approval text is an audit
reference, not an authentication/authorization system. Institutions remain
responsible for independent eligibility review and their own access controls.

SA comparison and IRB inputs are independent: never silently copy a supplied SA
factor to IRB. Populate both eligible paths explicitly when both qualify.

## Compatibility and audit output

Old Excel workbooks remain readable: only the new columns are filled if absent.
Old IRB inputs receive no reduction. Invalid explicitly supplied values are not
silently replaced. Historical SA factors without new eligibility data retain
their old arithmetic, with status LEGACY_SA_UNVERIFIED and a validation WARNING
LEGACY_SA_SUPPORTING_FACTOR. This preserves reference results without claiming
that historical eligibility has been established. Do not use this compatibility
path as a substitute for reviewing new production eligibility.

SA_Detail and IRB_Detail expose the overall factor, component factors, type,
status, evidence and approver, support formula ID, pre-support RWEA and relief.
Legacy SA factors are not decomposed into falsely certified component factors.
IRB's existing rw remains pre-support; effective_rw includes the factor.
IRB_Detail also exposes sa_comparison_supporting_factor and
supporting_factor_path_difference. A difference is diagnostic, not an automatic
error: eligibility may differ by approach and legacy SA data can be unverified.

U-TREA uses adjusted actual IRB/SA RWEA. S-TREA uses the independently adjusted
SA comparison. The existing output floor is then applied once. Neither TREA nor
the floor uplift is multiplied again by a support factor. A binding floor can
absorb some or all of an IRB-only reduction. Applied and fully-loaded views use
the same controlled exposure data with their respective rule contexts.

The input tables retain their bitemporal metadata. New disclosures are additive;
no tables or metrics are removed. Historical bundled workbooks/output runs remain
unchanged reference artifacts, not recomputed 1.2.0 runs. Generated new workbooks
use the extended effective schema.

## Verification and limits

Focused tests cover numeric boundaries and non-finite values, combined factors,
missing evidence, ineligible/defaulted/ADC exposures, unchanged K/EL, old inputs,
parameter sensitivity, Excel round trips and both floor regimes/views.
Existing portfolio golden results remain regression evidence with no new relief.
Synthetic eligibility references are fictional examples, never customer evidence.

## Primary sources

- [CRR, Articles 501 and 501a, consolidated 2026-01-01](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:02013R0575-20260101)
- [EBA Q&A 2020_5551: both factors may apply when both sets of conditions hold](https://www.eba.europa.eu/single-rule-book-qa/qna/view/publicId/2020_5551)

Source documents are not bundled. This correction does not automatically explain
differences to a particular bank's published RWA.
