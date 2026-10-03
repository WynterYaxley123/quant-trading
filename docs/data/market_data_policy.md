# Market data policy and data-rights matrix

Reviewed 2026-10-04. Software licensing, data ownership, private research and public
redistribution are separate. Accessible endpoints are not inferred licences.
CNEquity remains external at commit `1650e384a3fd1f67a70144a489acc91432f1df27`.
No private credentials, substitute quantitative provider, upstream edit or raw dataset
is included in Git. Unknown redistribution rights require private storage.

| Source / data | Code licence | Data ownership | Private research | Redistribution | Evidence / confidence | Project action |
| --- | --- | --- | --- | --- | --- | --- |
| Project source and synthetic fixtures | MIT | Project code | PERMITTED | PERMITTED (source only) | [MIT](../../LICENSE); high | Publish code; licence excludes datasets |
| External CNEquity adapter code | Apache-2.0 | Upstream software; no data grant established | PERMITTED (code) | PERMITTED (code with notices) | [Pinned licence](https://github.com/rootSunc/CNEquity/blob/1650e384a3fd1f67a70144a489acc91432f1df27/LICENSE); high | Keep external and unchanged |
| CNEquity → SWS effective-dated classification workbook | Apache-2.0 adapter | SWS/provider material | UNKNOWN | UNKNOWN | [Pinned adapter](https://github.com/rootSunc/CNEquity/blob/1650e384a3fd1f67a70144a489acc91432f1df27/src/cnequity/adapters/sw/industry_history.py), public official endpoint; high source identity, low rights clearance | User-authorized private reconstruction; retain raw workbook externally; publish only counts/hashes |
| CNEquity → TDX stock bars | Apache-2.0 adapter | Feed/provider/exchange facts | UNKNOWN | UNKNOWN | [Pinned adapter tree](https://github.com/rootSunc/CNEquity/tree/1650e384a3fd1f67a70144a489acc91432f1df27/src/cnequity/adapters); high route identity, low clearance | Private bounded/paced recovery; no raw/curated redistribution |
| CNEquity → Sina adjustment events | Apache-2.0 adapter | Provider/issuer facts | UNKNOWN | UNKNOWN | Pinned adapter/cache provenance; high route identity, low clearance | Private event-date joins; no fabricated adjustments |
| CNEquity → Baostock annual historical rosters / retired bars | Apache-2.0 adapter | Mixed exchange/provider facts | UNKNOWN | UNKNOWN | Pinned normalized public SDK route; high identity, low clearance | Private roster completeness check; public aggregates only |
| CNEquity calendar routes/seeds | Apache-2.0 code | Calendar facts and upstream rights | UNKNOWN | UNKNOWN | Pinned calendar adapter and factual hashes; medium | Keep calendar externally; announced sessions do not prove finalized prices |
| SSE website disclosures | No dataset software grant | Exchange/issuer | PERMITTED (conditional noncommercial browsing/download only) | REVIEW_REQUIRED | [SSE legal statement](https://www.sse.com.cn/home/legal/), checked 2026-10-04; high for statement, dataset-specific scope unresolved | No licence inference for other providers; no raw redistribution |
| Existing ETF official mapping/weights and liquidity evidence | Project/Pinned adapter licences only | Exchange/issuer/provider | UNKNOWN | REVIEW_REQUIRED | Existing immutable V1 admission registries; high provenance, low clearance | Reuse privately for prospective mapping; never backstamp availability |

No source was marked PERMITTED for private dataset use merely because it was reachable.
`UNKNOWN` does not mean PROHIBITED. Under the user's explicit instruction, unresolved
redistribution does not automatically block private research. Any explicit contrary
terms require source exclusion. Commercial distribution needs dataset-specific review.

Git contains code, schemas, synthetic fixtures, hashes, ranges/counts and concise
non-reconstructive aggregate research evidence. Full grids, model rows, source dumps,
raw/curated facts, credentials, runtime databases and Shadow payloads remain private.
The source/history security audit omits sealed performance content. See
[data evidence](../data-and-pit.md) and [V2 protocol](../etf-quant-v2-protocol.md).
