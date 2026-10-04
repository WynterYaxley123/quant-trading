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
**2025-12-30–2026-04-02**; its 120-session maturity tail extends into the
factual cutoff. Normalizing later prices does not authorize OOS labels. The phase
gate rejects ordinary OOS computation; the separately frozen finalization entry opened it once. Development labels end before the V1 sealed period.
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
was Validation-informed before its single Final-OOS test. Moving-block diagnostics preserve
calendar gaps (120-session blocks, 1,000 draws, seed 20261004). ESS/uncertainty are
assumption-dependent, not independent proof.

Recovery checkpoints validate symbol-file hashes and the source pin. Completed
coverage/panel checkpoints are digest-verified. Component caches are addressed by
data/protocol/phase/fit-code/horizon/window/alpha/scaling. Diagnostic/grid/freeze
artifacts persist externally; immutable freeze/access artifacts cannot be replaced.
An early window-feasibility bug was corrected before Validation; its superseded
Development grid is preserved by hash as engineering evidence. Only the corrected
grid governs selection.

The [Final-OOS freeze](../config/research/etf-quant-v2-final-oos-freeze.json) was committed
before access. Ridge alpha 30, raw features, 12 calendar months, H10/H40/H120,
0.25/0.50/0.25 fusion and 5/19/19 factors are unchanged. Four fixed 15-session
blocks test direction, chronology, concentration, degradation and numerical stability.
The [single result](../reports/engineering/etf-quant-v2-final-oos.json) is PASS_STRONG:
60 signals, mean RankIC 0.133704, mean H40 industry spread 0.056796, all four blocks
positive. This is industry-model evidence, not an ETF backtest. Sixty overlapping
H40 observations cannot support the registered 120-session block uncertainty estimate;
bootstrap confidence intervals and ESS are null. Tier A remains zero. No model retuning,
second Final OOS or second Validation occurred. Future revisions require a new generation.

The [independent V2 registry](../strategies/etf_quant_v2/config/mapping-registry.json)
binds complete primary exchange/index-provider evidence and current observed SW
classification. The [30/40/50 study](../reports/engineering/etf-quant-v2-mapping-study.json)
selects 40% without historical profitability: 22/124 industries (3 direct, 19 proxy),
189 candidate ETFs, 183 liquidity-admitted at 2026-09-30. At 30% coverage is 29;
at 50% it is 16. Source files unavailable or unsupported classifications remain
unmapped. Current weight dates span 2026-08-31–2026-09-30. At each signal, weights
must be at most 62 days old and membership at most 45 days old, with actual
availability no later than the decision. Expired evidence fails to cash. V1's
registry and selector stay frozen. V2 ranks direct then proxy candidates by highest
valid 20-session amount, then ETF code; collisions try the next candidate before cash.
The original Top5 weights are retained, with a 35% cap and no cash redistribution.

The shared `services/etf-quant-runner/one_shot.py` entry dispatches explicitly by
`strategy_version`. V2 uses `versioned.py` inside the independent developer image,
verified factual exports, the frozen warmup prefix and its separate release manifest.
Both ledgers start with CNY 10,000. T-close persists a target intent; finalized T+1
prices determine 100-share lot-rounded fills using 3bp commission/5bp per-side slippage,
no stamp duty/minimum commission. Economic open and actual delayed accounting times
are recorded separately. Only a changed final executable ETF set causes rebalancing.
No signal or epoch can be backfilled before the actual model/mapping freeze.

The public read-only `/api/etf-quant/v2/research` exposes final science and mapping;
`/api/etf-quant/v2/current` exposes the independent bounded/hash-verified live ledger.
The dashboard version selector shows Top5, mappings, cash, intent state, NAV, CSI 300,
turnover and V1/V2 date-aligned observations. Unstarted ledgers have empty NAV and zero
business counts. PASS_STRONG maps to HISTORICALLY_VALIDATED_STRONG, PASS_WEAK to
HISTORICALLY_VALIDATED_WEAK; FAIL must stay visibly experimental even in Shadow.

Formal launch uses merged CI-validated main. If the current date is ineligible,
the same entry persists arming metadata and the next eligible announced session,
without inventing any business record. The October 4 freeze is after the latest
September 30 finalized data; the next announced trading session is October 8.
