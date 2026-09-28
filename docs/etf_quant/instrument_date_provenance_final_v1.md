# `920201.BJ` listing-date provenance audit

Status: **EXTERNALLY CORROBORATED DATE; FIELD-LEVEL LAKE LINEAGE UNKNOWN**.
No pinned upstream source, lake row or frozen strategy rule was modified.

The pinned BSE board adapter emits `list_date=null` because the board field
`hqssrq` is absent. `steps/reference.py` subsequently calls
`enrich_instrument_list_dates`, which can fill nulls from EastMoney `f26`;
`storage/instruments.py` can also carry an earlier non-null value forward.
The single curated `instruments` row reports `source=bse`,
`list_date=2026-09-24`, `fetched_at=2026-09-28T04:13:24Z`, but its `source`
is **row-level**, not proof that this date came from BSE. The pin does not
persist field-level provenance for `list_date`.

Independent primary public evidence now corroborates the *date itself*:
the Changzhou National High-Tech District / Xinbei government [publication
dated 2026-09-24](https://www.cznd.gov.cn/html/cznd/2026/HFFLILLK_0924/578823.html)
states that 百瑞吉 (`920201`) listed on the Beijing Stock Exchange on
September 24, 2026. This is an observed **current** official publication,
not a claim that the exact same field was present in CNEquity or known before
that publication. The earlier handoff's “cutoff echo could be a guessed
listing date” remains a valid caution about lake lineage, but is no longer
evidence that the *calendar date* itself is false.

Pinned TDX historical bars for this code remain absent in the fixed window.
A listing-day bar is not synthesized from the date, another provider's price,
or a following session. In the Source-C matrix, the date was diagnostic only:
no prelisting exclusion, constituent deletion or denominator change occurred.
Historical market-data recovery, if ever attempted, must use an official
supported path and the normal staging/compact lifecycle; a listing notice
alone is not price evidence.
