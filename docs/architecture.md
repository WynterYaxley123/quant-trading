# Architecture

The project contains historical Shenwan sector-rotation research, frozen ETF-Quant V1,
independent ETF-Quant V2 Research, shared data/runner/API infrastructure and the observation
dashboard. V2 primitives reuse the frozen numerical solver and factor vocabulary; V1
does not import V2. V2 admission is blocked and no runtime/candidate migration exists.
See the [V2 protocol](etf-quant-v2-protocol.md) and [glossary](glossary.md).

External pinned CNEquity produces normalized immutable factual exports. This repository
owns evidence admission, research/model logic, ETF-Quant policy/runtime, two read-only
APIs and the dashboard. The README contains the compact data-flow diagram.

`strategies/etf_quant/` is the self-contained current product. Evidence separates sources,
weight completeness, classifications and derived exposure; `evidence/schema.py` keeps
the public facade. Runtime owns forward lifecycle and artifact integrity. `src/` supplies
data/provider infrastructure; `research/` and `sw_sector_rotation` preserve research lineage.

CNEquity sidecar is external transport/adaptation. Runner validates input and builds
Docker argv; quantitative implementation executes in Docker. The developer image is
independent of deployed services. No cleanup requires restarting the frozen runtime.

Research API requires approval of exact Development artifact hashes and excludes sealed
phases. ETF API verifies immutable runtime generations and public-view integrity. These
distinct trust contracts justify two services. Both are local and read-only; dashboard
and launcher observe them without invoking a formal cycle.

`reports/etf_quant/` retains historical metadata; active source integrity is versioned
separately. See [reproducibility](reproducibility.md) and [data and PIT](data-and-pit.md).
