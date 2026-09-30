# Third-party software and market data

- CNEquity official https://github.com/rootSunc/CNEquity, pinned
  1650e384a3fd1f67a70144a489acc91432f1df27 (0.11.0), Apache-2.0 software.
  Source/dependencies stay in the external sidecar, never vendored here.
  Preserve upstream notices with that external source.
- Dashboard adaptations/licenses: dashboard/THIRD_PARTY_NOTICES.md. Existing
  direct dependency versions are unchanged.
- Scientific/framework notices remain in unchanged Docker distributions.
  ETF API uses built-in Node modules only.

Software licenses do not grant market-data redistribution rights. Source
licensing remains unresolved. No lake/export/raw data, ETF bars, account state,
holdings/NAV/trades/logs are included in Git or authorized GitHub sync. Clearly
synthetic unit fixtures are neither market data nor formal forward results.

No new repository-wide license is assigned to user research/code. Ownership,
licensing and historic documentation privacy require review before third-party
reuse. No investment advice, promised returns or live trading.
