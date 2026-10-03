# ETF-Quant V2 research and forward protocol

V2's authorized evidence-tier policy supersedes the previous strict-PIT-only
admission decision. The original prerequisite certificate/report remain immutable.
V1 numerical contracts and its sealed results remain unchanged and unread.

Tier A requires independent official historical availability evidence. Tier B uses
real effective-dated spells after the 2021 taxonomy publication and ≥95% independent
annual stock-roster symbol coverage, but can lack historical publication instants.
Tier C is explicitly weaker/retrospective historical reconstruction. Unsupported
assignments are Tier D and excluded. Never backfill current membership without
real historical effective intervals. Scheme publication does not establish
publication of each reconstructed assignment.

The unchanged external CNEquity commit is `1650e384a3fd1f67a70144a489acc91432f1df27`.
Public source routes supply normalized TDX stock bars, Sina adjustment events,
SWS effective intervals, annual Baostock stock rosters and the supplied calendar.
Full hashes, symbol failures, rows and caches stay in private external storage.
Only concise non-reconstructive aggregates/configuration enter Git.

Development signals span 2022-01-27–2024-09-02, with a later high-confidence common
comparison start for window/maturity history. Purge/maturity isolation is 120 sessions.
Validation is 2025-03-10–2025-07-04 (80 signal dates). Final OOS is
**2025-12-30–2026-04-02**, sealed; its 120-session maturity tail extends into the
factual cutoff. Normalizing later prices does not authorize OOS labels. The phase
gate rejects OOS computation. Development labels end before the V1 sealed period.
Universe selection ends before the first Development signal.

Stage 1 fixes four horizon/fusion families, five alphas (0.001/.01/.1/1/10), three
calendar windows (6/12/24 months) and raw/training-only standardized features:
120 specifications. Frozen V1 factors are used without factor mining. At T, training
ends at T−h, with at least 30 complete mature cross sections. No future asset selection,
gap bridging, future scaling, guessed prices or mock response is permitted.

Selection requires ≥160 observed H40 signals, ≥30 per fold, positive aggregate IC
and spread, three positive folds, worst IC ≥−.05, positive-fold concentration ≤60%,
norm CV ≤1, and included long-horizon incremental IC ≥.005. Stage 1 used equal
calendar blocks. One focused Stage 2 declared observability-balanced contiguous
calendar blocks before its results, retained gates, and tested 36 specifications:
baseline fusion versus no H120, alphas 3/10/30, windows 9/12/18, raw/standardized.
Exact executed policies: [Stage 1](../config/research/etf-quant-v2-stage1-protocol.json),
[Stage 2](../config/research/etf-quant-v2-stage2-protocol.json).

After candidate freeze, a hash-bound exclusive Validation gate opened once.
The fixed model was evaluated without retuning and failed. The single authorized
[revision policy](../config/research/etf-quant-v2-revision-protocol.json) returned to
Development with unchanged specifications, all-fold positivity, norm CV ≤.2 and
worst-fold priority. No second Validation or other OOS slice was opened. The candidate
is Validation-informed, not independently validated. Moving-block diagnostics preserve
calendar gaps (120-session blocks, 1,000 draws, seed 20261004). ESS/uncertainty are
assumption-dependent, not independent proof.

Recovery checkpoints validate symbol-file hashes and the source pin. Completed
coverage/panel checkpoints are digest-verified. Component caches are addressed by
data/protocol/phase/fit-code/horizon/window/alpha/scaling. Diagnostic/grid/freeze
artifacts persist externally; immutable freeze/access artifacts cannot be replaced.
An early window-feasibility bug was corrected before Validation; its superseded
Development grid is preserved by hash as engineering evidence. Only the corrected
grid governs selection.

V2 reuses unchanged verified industry mapping, 40% proxy/cash fallback, capped
softmax, executable-member rebalance and T+1 accounting primitives. Its independent
`strategies.etf_quant_v2` path is input-driven and deterministic.
`python -m strategies.etf_quant_v2.runtime --candidate strategies/etf_quant_v2/config/candidate.json --readiness-only`
checks configuration without state. A future one-shot additionally needs human
launch authorization, finalized normalized facts/admitted mappings, an external
root named `etf-quant-v2` and explicit unvalidated-research acknowledgement.
It rejects V1/repository namespaces, historical launch dates and competing dates.
The read-only endpoint `/api/etf-quant/v2/research` binds candidate, aggregate report
and current certificate. Shadow remains unstarted.
