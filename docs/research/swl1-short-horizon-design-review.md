# SWL1 short-horizon exploratory design review

The [design manifest](../../config/research/swl1-short-horizon-exploratory-design.json)
is locked before this round's new H5/H10 performance diagnostics. Its Git commit
records engineering order only: prior V1/V2 failure evidence was already known,
so neither this lock nor the rolling analysis is independent preregistration.

The six structures are zero scores, existing REV5, existing REV10, their equal
population-z combination, one fixed two-feature Ridge, and already recorded V2
H10 predictions. The frozen factor implementation defines `rev5` and `rev10` as
negative **arithmetic means of daily returns** through the signal close, not
negative compounded trailing returns. Subtracting the same cross-sectional mean
changes their level but cannot change the ranks. The target, separately for H5
and H10, compounds exact subsequent sessions and centers across the same 30
industries. No horizon fusion, replacement factors or parameter search is allowed.

Ridge uses two relative reversal features, 24 calendar months, penalty 10 per
training industry row, training-only population scaling and mature labels. These
choices reuse the existing V2 training conventions without selecting parameters
from this round's results. S5 has no H5 counterpart and is never retrained.
Comparison with S5 uses only identical H10 dates, series, universe and targets.

Four fixed calendar blocks, all 30 leave-one-industry-out evaluations, turnover,
selection concentration and coefficient signs must be shown. A 20-session circular
block bootstrap is descriptive, assumes approximate local stationarity and cannot
establish independent evidence. Four fixed trend/dispersion states are post-hoc
descriptions, not a strategy filter. The decision predicates are fixed in the
manifest; a poor result is published without adding a seventh structure.

The owner explicitly authorizes reuse of consumed historical data, while vendor
rights, historical PIT membership and prospective source admission remain
unresolved. This scope is not a vendor licence or production approval. Only the
hash-pinned existing panel and two consumed prediction records are admitted;
the bounded decoder stops returns at 2026-09-29. No new provider is contacted.
The full original panel has one later row, which must never be numerically decoded.

Existing V1/V2 remain FAILED_VALIDATION. Original source, lifecycle claims,
artifacts, sealed OOS and SWL2 contracts remain untouched. Numerical payloads
stay in task-specific private scratch under QuantForge; public output consists
of aggregate JSON, explanatory documents and six watermarked scientific charts.
