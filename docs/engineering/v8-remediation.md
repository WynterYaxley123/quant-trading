# V8 remediation

Base: `f134704` (V7 merge). Inventory comes from an external adversarial review of
that commit. The parent certificate stays
`reports/engineering/shadow-task-installation-integrity.json`; the superseded V7
delta is byte-pinned as a new file of the cumulative V8 delta and keeps its reasons.

| ID | Finding | Verified classification and resolution |
| --- | --- | --- |
| 01 | `classify()` returns PASS_STRONG with null bootstrap ESS and zero Tier A | CONFIRMED_SCIENTIFIC_GATE_GAP. Every new freeze declares `strong_evidence`; PASS_STRONG then also requires a dependence-aware ESS and independent Tier A membership rows, otherwise PASS_WEAK. The consumed gate predates the rule and its published decision still reproduces exactly; it is not re-evaluated. |
| 02 | Same release object carried `classification=PASS_STRONG` beside a provisional current status | CONFIRMED_SCIENTIFIC_LABELING_ISSUE. `current_release()` removes `classification` and exposes it only as `historical_classification`; Python runtime, runner and API share the projection. |
| 03 | API `final_oos.decision.scientific_status` leaked HISTORICALLY_VALIDATED_STRONG | CONFIRMED_SCIENTIFIC_LABELING_ISSUE. API output renames decision status fields to `historical_scientific_status` / `historical_product_status`; dashboard schemas reject a decision carrying a current status, and fixtures match the real payload. |
| 04 | Overlay merge had no key allowlist | CONFIRMED_BUG. The overlay must contain exactly the six certified label keys in Python and JS; it cannot replace release identity fields. |
| 05 | Dashboard README spacing | CONFIRMED_DOCUMENTATION_DEFECT. Corrected; V7 row 20 claimed it was fixed. |
| 06 | Edit Final-OOS report / release JSON to PASS_WEAK | REJECTED. They are sealed historical byte truth bound by hashes and the single-open freeze; rewriting an opened gate decision would itself be a post-hoc relabel. |
| 07 | `STRONG_POSITIVE` directional label | NOT_CHANGED. It lives in the certified overlay under `config/research`; replacing it needs a new owner-certified assessment, not an engineering edit. |
| 08 | Missed-session NAV gap after recovery | INTENTIONAL_CONSTRAINT. Recovery never writes retroactive marks; the gap is the honest record of an unobserved session. |

Validation results are recorded in the pull request; absent runs are not claimed here.
