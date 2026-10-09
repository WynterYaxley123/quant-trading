# SWL1 real-data source qualification

Decision: **C / DATA_SOURCE_NOT_READY**. This audit examined 12 source roles,
requested 19 specific public document endpoints, hashed 17 responses and verified
limited claims in 15 exact responses. Two responses were page shells. The SWS
classification PDF returned 403; its official announcement page was unavailable
(a separately authenticated public intermediate restored TLS, but returned 508).
Search-indexed official material is a discovery reference, not a byte-verified
historical receipt. No access-control workaround was used.

The [evidence snapshot](../../config/research/swl1-source-qualification-evidence.json)
records URLs, publishers, retrieval instants, hashes, versions, supported claims,
confidence and scope. Original responses were processed in memory and not retained
or published. There were no market-data requests, account logins, vendor messages,
contracts accepted, purchases, production keys or numerical quality runs.

## Actual source lineage

| Source role | Origin and qualification result |
| --- | --- |
| SWCLASS2021 hierarchy | SWS official taxonomy; current/historical grant and exact archived release unverified |
| Membership history | SWS effective-dated workbook through pinned CNEquity; contemporaneous receipts absent |
| Official SWL1 price index | Official indexed explanation describes industry indices; an authorized price series is not established |
| Daily stock bars | TDX primary route, documented alternative routes; endpoint-specific owner grant absent |
| Adjustment factors | Sina hfq endpoint; reuse scope requires written confirmation |
| Corporate actions | **TDX xdxr**, schema 2; Sina is not the corporate-actions adapter |
| Listing/delisting | BaoStock basics; supported fields do not prove full exchange coverage |
| Adjusted-price fallback | BaoStock raw/back-adjusted closes; method equivalence is not certified |
| Derived factors | CNEquity combines factor sources with provenance; upstream rights remain necessary |
| Calendar | CNEquity seed plus bar fallback; SSE closures are a methodology reference |
| Derived industry returns | CNEquity membership and adjusted-stock construction, not official index prices |
| Project SWL1 series | Frozen explicit L2-to-L1 equal-weight reconstruction, not a newly admitted source |

CNEquity remains external, read-only and pinned to
1650e384a3fd1f67a70144a489acc91432f1df27. Its Apache-2.0 software licence does
not grant the providers' dataset rights. Twelve actual source-file hashes are
recorded. The newer role inventory clarifies the prior Sina/corporate-action label;
PR34 reports and all frozen evidence remain unchanged.

## Rights and public evidence

The [rights matrix](../../reports/research/swl1_source_qualification/rights-matrix.json)
separates access, local storage, internal research, automation, derivation,
backtesting, commercial use, redisplay, redistribution, retention and revisions.
No owner-specific complete dataset grant has been verified.

BaoStock's [official platform description](https://www.baostock.com/mainContent?file=home.md)
expressly describes free API access and local analysis/storage. These are recorded
as conditional documentation support, not an unrestricted sublicence. Its
[lifecycle documentation](https://www.baostock.com/mainContent?file=stockBasic.md)
specifies listed/delisted status and dates. The [industry interface](https://www.baostock.com/mainContent?file=stockIndustry.md)
illustrates CSRC classification, not Shenwan membership.

TDX's [general terms](https://www.tdx.com.cn/about/yhxy/index.html?tabindex=0)
restrict unapproved third-party access and reuse. The exact terms-bearing static
asset was hashed and read without executing JavaScript. Its
[exchange-licence list](https://www.tdx.com.cn/article/license.html) concerns the
provider; it is not this owner's permission. The
[data product](https://www.tdx.com.cn/tdxdata.html) provides a lawful enquiry route.

Sina's [copyright statement](https://corp.sina.com.cn/chn/copyright.html) and
[finance-app terms](https://finance.sina.cn/app/SFAuser.shtml) contain reuse
restrictions. Applicability to the hfq endpoint and a dataset-specific research
grant require provider/legal review. SSE's [legal statement](https://www.sse.com.cn/home/legal/)
allows conditional noncommercial browsing/download and restricts specified
commercial reuse; it does not certify unrestricted use of the numerical lake.
Terms observed now are not assumed to govern every historical period.

## PIT and factual quality

The [official indexed 2021 explanation](https://wxweb.swsresearch.com/swsreport/2021_08/328340.pdf)
distinguishes classification release from later index adjustment. Its exact bytes
were inaccessible. No complete contemporaneous constituent snapshot, historical
receipt or revision chain was acquired. The pinned membership adapter renames an
update column but emits only symbol, start date and industry code; it cannot
supply the missing publication/observation evidence. Effective, publication,
observation, ingestion and revision times remain distinct.

The reader multiplies raw prices by stored hfq factors and derives qfq by an
in-scope anchor. The BaoStock fallback normalizes the ratio of adjusted/raw closes.
Source formulas are verified, numerical accuracy is not. The
[factor-field documentation](https://www.baostock.com/mainContent?file=factorInfo.md)
and [adjustment PDF](https://www.baostock.com/helpdocs/pdf/BaoStock%E5%A4%8D%E6%9D%83%E5%AD%90%E7%AE%80%E4%BB%8B.pdf)
express reciprocal ratios under forward/backward labels; clarification is needed.
The provider documents suspension placeholders and later corrections. Neither
current returned history nor mathematical continuity establishes PIT.

An [SSE delisting notice](https://www.sse.com.cn/disclosure/announcement/listing/stock/c/c_20260629_10823832.shtml)
provides a dated individual event, not complete SH/SZ/BJ reconciliation. The
[2026 closure schedule](https://www.sse.com.cn/disclosure/dealinstruc/closed/)
does not finalize future price facts. No independent numerical comparison was
authorized or run. Coverage, company-action accuracy and delisting/suspension
completeness remain NOT_ESTABLISHED; absent numerical metrics are null.

## Admission and next action

Four supported industry/taxonomy candidates exercised the existing PR34 registry
with **zero minted factual proofs** and remained SOURCE_UNREVIEWED. Other roles
are input components outside that registry's direct kind contract; they were not
relabelled as industry indices. Public-review status is separate from authenticated
admission. Source hashes identify qualification metadata, not numerical snapshots.
REAL_SOURCES_ADMITTED=0. Synthetic qualification tests cannot establish production
identity, and no parallel registry or production promotion path was added.

The new preflight checks dataset-specific scope, expiry/conflicts, signal-time
availability, taxonomy identity, revisions, complete blind QA and independent
upstream origin. It returns SYNTHETIC_ONLY even for a complete synthetic packet.
The source reader, numeric views, worker isolation and ledger from PR34 are reused.

Use the [acquisition plan](swl1-source-acquisition-plan.md),
[remediation matrix](../../reports/research/swl1_source_qualification/remediation-matrix.json)
and four unsent provider packets. First obtain SWS research/storage/automation
rights and contemporaneous archives; then qualify price/event rights and blind
independent QA. The owner must approve the production admission identity, controlled
key management and durable external receipts. No ephemeral HMAC is a substitute.

V1/V2 stay FAILED_VALIDATION, Final OOS unopened, V3 not created. Historical
isolation stays NOT_CERTIFIED and certified unseen sessions=0. Linux Docker
synthetic isolation passed previously and is included in regression; Windows
native quantitative isolation remains NOT_ESTABLISHED. No live state changed.

[Chinese report](swl1-real-data-source-qualification.zh-CN.md) ·
[Acceptance](../engineering/real-source-admission-acceptance.md)
