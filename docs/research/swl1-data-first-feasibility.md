# SWL1 data-first feasibility

Status: DATA_SOURCE_NOT_READY. Engineering acceptance uses synthetic facts only.
This audit reads adapter source and local revision metadata, not market panels,
sealed results or provider refreshes. Both SWL1 generations remain FAILED_VALIDATION;
Final OOS stays unopened. No next-generation protocol or candidate exists.

## What exists

| Candidate | Established identity | Missing admission evidence |
| --- | --- | --- |
| SWCLASS2021 hierarchy | SWS taxonomy workbook; 2021-07-31 version boundary | Dataset-specific research/redistribution rights |
| Historical stock membership | Effective-dated SWS workbook through pinned CNEquity | Contemporaneous publication/receipt proof, rights |
| Stock prices/actions/lifecycle | TDX, Sina, Baostock routes; revision metadata | Rights, independently verified adjustment/retired/suspended coverage |
| Exchange spine | Existing calendar revision; future announced sessions | Approved calendar contract and versioned correction receipts |
| CNEquity industry_index | Derived member/adjusted-stock returns | Official index-price identity is not established |
| Frozen SWL1 equal-weight history | Existing published audit range 2021-08-02–2026-09-30 | Reconstructed Tier C; not newly admitted or recomputed |
| Official SWL1 index price | No authorized local price adapter established | Identity, methodology, historical availability and licence |

CNEquity is pinned at 1650e384a3fd1f67a70144a489acc91432f1df27.
Its [Apache software licence](https://github.com/rootSunc/CNEquity/blob/1650e384a3fd1f67a70144a489acc91432f1df27/LICENSE)
does not grant rights in provider datasets. The [SSE legal notice](https://www.sse.com.cn/home/legal/)
contains conditional site-use terms; it is not a licence for SWS/TDX/Sina/Baostock
prices or reconstruction. The [SWS index portal](https://www.swsresearch.com/swindex/)
was not retrievable by the audit tool; local NOT_ESTABLISHED does not prove global
nonexistence. No unauthorized price download substitutes for missing evidence.

## PIT and quality conclusion

Historically effective spells are not proof of contemporaneous availability.
Canonical historical Tier A=0, Tier B=0, Tier C=reconstructed remains unchanged.
The upstream derived index describes a prefix hierarchy; frozen SWL1 construction
uses explicit L2-to-L1 relations. Neither source comments nor ingestion watermarks
upgrade historical PIT. Effective, published, observed, ingested and revised times
have distinct meanings. Corporate-action accuracy, delisting/suspension completeness
and full constituent coverage were not independently established by metadata.

The four [public reports](../../reports/research/swl1_data_first/source-inventory.json)
contain aggregate source identities and gaps only. See the
[PIT assessment](../../reports/research/swl1_data_first/pit-evidence-assessment.json),
[admission summary](../../reports/research/swl1_data_first/source-admission-summary.json)
and [readiness](../../reports/research/swl1_data_first/prospective-readiness.json).

## Executable decision

Choose C: pause model research and complete source admission. Obtain dated,
dataset-specific research-use evidence, contemporaneous membership receipts or a
new legally approved reconstruction tier, and verified corporate-action/lifecycle
coverage. Admit a versioned exchange spine. Establish a reviewed production signing
identity and future protocol-only GitHub anchor before any formal activation.
A is permitted only after those factual requirements pass; B requires documented
partial admission with named remaining gaps. D applies to any deployment platform
without tested process isolation. Linux Docker synthetic containment passes;
Windows native process isolation is NOT_ESTABLISHED, so use the tested Docker route.
No data purchase is required to finish this engineering delivery.

Historical access remains NOT_CERTIFIED with zero certified historically unseen
sessions. New isolation cannot certify past full-panel access or establish human
viewing/causal target leakage. See the frozen
[access clarification](../engineering/swl1-forensics-access-clarification.md).

[中文](swl1-data-first-feasibility.zh-CN.md) ·
[Architecture](../engineering/prospective-evidence-architecture.md)
