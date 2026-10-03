# Market data policy and data-rights matrix

Reviewed 2026-10-04. Source-code licensing is separate from data ownership and
redistribution. This is the project's canonical rights inventory; it records evidence
and unresolved clearance rather than granting legal permission.

Formal ETF/V2 market data uses only the existing external CNEquity pin. Record the
actual internal provider route; do not call substitute market-data packages or move
lake/export/curated data into Git. Private research storage and public redistribution
are separate decisions. An unresolved redistribution licence does not require
discarding private research observations.

| Component | Source/provider | Code licence | Data ownership / clearance | Redistribution status | Evidence / confidence | Project action |
| --- | --- | --- | --- | --- | --- | --- |
| Project source | quant-trading | MIT | Code licence excludes upstream datasets | PERMITTED (code only) | [Project licence](../../LICENSE); high | Publish source and synthetic fixtures with notices |
| Pinned CNEquity software | rootSunc/CNEquity | Apache-2.0 | No market-data grant established | PERMITTED (code only) | [Pinned licence](https://github.com/rootSunc/CNEquity/blob/1650e384a3fd1f67a70144a489acc91432f1df27/LICENSE); local byte verification, high | Keep source external and pin unchanged; preserve notices |
| Industry classification / constituents | CNEquity → SWS Research workbook | Adapter covered by Apache-2.0 | SWS Research claims website copyright; no dataset redistribution grant verified | REVIEW_REQUIRED | [Pinned adapter and URL](https://github.com/rootSunc/CNEquity/blob/1650e384a3fd1f67a70144a489acc91432f1df27/src/cnequity/adapters/sw/industry_history.py), [official index site](https://www.swsresearch.com/institute_sw/allIndex/announcementIndex); medium | External private storage; historical availability/completeness remain separate admission blockers |
| Stock/ETF/index bars | CNEquity → recorded `tdx_protocol`, `ths`, `sina`, `bse` routes | CNEquity adapter code: Apache-2.0 | Feed/venue/provider rights; no grant verified for the stored datasets | REVIEW_REQUIRED | [Pinned adapters](https://github.com/rootSunc/CNEquity/tree/1650e384a3fd1f67a70144a489acc91432f1df27/src/cnequity/adapters), audit source fields; high for route labels, low for clearance | Do not redistribute raw or curated rows; do not equate an accessible endpoint with a licence |
| Adjustments / corporate actions | CNEquity → `sina`, `eastmoney`, `tdx_protocol` | CNEquity adapter code: Apache-2.0 | Provider/issuer rights; no grant verified | REVIEW_REQUIRED | Pinned adapter tree and factual audit source labels; low for clearance | Keep external; exactness and historical publication require independent evidence |
| Identities / listing boundaries / status | CNEquity → `baostock`, `bse`, `tdx_protocol`, exchange and derived status routes | CNEquity adapter code: Apache-2.0 | Mixed provider facts; derived gaps do not prove genuine historical status | REVIEW_REQUIRED | Pinned adapter tree and factual audit source labels; low for clearance | Keep private; do not infer listing/delisting or halts from missing bars |
| Exchange website information | SSE and relevant exchange/issuer disclosures accessed through permitted adapters | Not a dataset software licence | SSE asserts rights, allows conditional noncommercial browsing/download and requires written permission for specified commercial use | REVIEW_REQUIRED | [SSE legal statement](https://www.sse.com.cn/home/legal/); high for statement, dataset-specific clearance unresolved | No public row-level redistribution; obtain dataset-specific permission before any distribution |
| Trading calendar | CNEquity exchange-calendar route and seeds | CNEquity code: Apache-2.0 | Calendar facts and upstream publication rights not independently cleared | REVIEW_REQUIRED | [Pinned calendar adapter](https://github.com/rootSunc/CNEquity/tree/1650e384a3fd1f67a70144a489acc91432f1df27/src/cnequity/adapters/calendar); low for clearance | Store dated provenance externally; future announced sessions are not finalized prices |

`UNKNOWN` never becomes `PERMITTED` by inference. `REVIEW_REQUIRED` means clearance
is unresolved for redistribution; it is not a claim that all private research is prohibited.
No legal authorization is requested or supplied by this engineering task.

Public Git may contain code, schemas, synthetic fixtures, hashes, range/count metadata
and approved non-reconstructive Development aggregates. It must not contain credentials,
raw/curated market data, runtime databases, Shadow payloads, private source dumps or
sealed performance. The security audit checks paths/content/history without printing
secrets or reading sealed performance.

Data admission rules are in [data and PIT](../data-and-pit.md): no fabricated missing
prices/amounts, no guessed halts/listing boundaries, no retrospective membership,
exact stock adjustment evidence and genuine future finalized T/T+1 execution.
The earlier eight-ETF import-session policy remains recoverable from Git history;
it does not describe the current CNEquity/V1/V2 data boundary.
