# Production Candidate snapshot — final admission audit v2

**Verdict: BLOCKED. No `PRODUCTION_CANDIDATE` was published.** The fixed
cutoff is 2026-09-24. This record supersedes the older, pre-repair candidate
blocker measurements without overwriting them.

The pinned CNEquity 0.11.0 export at
`D:\QuantForge\runtime\etf-quant-v1\codex-final-completion\engineering-exports\c085168103a7e8206009018e9b0cbc7f1e74b0e03dfed6c9f4ad12896af48995`
is an **immutable engineering export**, not a production candidate. Its
manifest SHA-256 is
`4deb4c71da68fef9f6a0a37f77f39c23ac9027b15ffe04ade7f3e2474052d595`.
All seven CSV SHA-256 values and streamed row counts were independently
rechecked against that manifest: stock bars 2,124,486, membership 419,972,
instruments 8,053, calendar 2,459, CSI300 358, ETF bars **0**, trading
status **0**. File integrity passed; production admission did not.

The final external coverage matrix has 40,800/57,996 strict valid L2
industry-days, 38,684 recursively usable levels, and 107/162 cutoff-ready
industries. All 19 frozen factors are finite for the same 107 cutoff codes.
Three actual Ridge fits on a 107-code *retrospective engineering* universe
have 128/119/118 mature training dates for H10/H40/H120. The full 162-code
cross-section has zero complete training dates. CSI300 is 358/358. These
are measured advances, not proof that a formal signal was knowable on the
historical cutoff.

Admission remains blocked by distinct semantics:

1. Historical Shenwan membership publication/availability is unknown:
   `HISTORICAL_MEMBERSHIP_PIT_UNPROVEN`, `available_at=null`,
   `source_published_at=null`. As-of membership is not a publication clock.
2. The engineering research universe is four-digit L2 (107 admitted for
   retrospective use); production `build_industry_series` and mapping keys
   are six-digit L3. No approved L2→L3 policy or equivalent L3 complete
   training audit is present. Prefix compatibility does not solve this.
3. The export contains no verified ETF scope, no ETF bars and no trading
   status. Mapping/liquidity admission is downstream and must not be inferred.
4. The export was observed 2026-09-28. The production prediction gate
   requires a signal date equal to the snapshot cutoff and signal time no
   earlier than creation. Backdating a 2026-09-24 signal would violate that
   gate. This export is appropriate for retrospective engineering inspection,
   not a forward signal available on 2026-09-24.
5. `SOURCE_LICENSING_UNRESOLVED` remains a review flag; no legal conclusion
   is asserted.

No candidate ID or candidate hash exists; `SNAPSHOT_INTEGRITY_PASS` is **not
claimed for a production candidate**. The old smoke-scope snapshot remains
unchanged. No Shadow epoch, order intent, fill, holdings, NAV or performance
was created. Next safe work requires an explicit, frozen-rule-compatible
universe/timing admission decision and evidence-backed ETF scope, rather than
renaming this export or manufacturing availability timestamps.
