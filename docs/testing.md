# Testing and quality

`python -m pytest -q -m "not external_runtime"` runs portable numerical contracts,
synthetic evidence, schema, provider and transport regressions. It needs no private
data or credentials. Synthetic HDF5/Parquet fixtures exercise real readers.

`external_runtime` marks permitted private-evidence/frozen-framework tests.
`integration` marks broader environment/data tests and is excluded by default.
`network` additionally identifies explicit online tests. Optional framework directories
are not imported in the portable tier because deselection happens after import.
Test-local lifecycle fixtures stay temporary; engineering never invokes formal one-shot.

When available, run frozen-image ETF acceptance with network disabled, source and
permitted runtime evidence mounted read-only, `ETF_QUANT_EXTERNAL_RUNTIME_ROOT=<runtime-root>`,
and pytest cache under /tmp: `python -m pytest -q tests/etf_quant`. Missing optional
fixtures remain explicit skips. This does not run a market-data backtest.

All active Python receives Ruff lint/format. Mypy uses **staged typing enforcement**:
raw diagnostics remain visible, exact path/code/message baselines reject regressions
and stale allowances, and touched active production modules must be type-clean.
Updates remove resolved debt without adding new allowances.

Frontend tests/types/lint/build and both API suites use synthetic fixtures. APIs test
approval/integrity, bounded reads, strict schemas, origin rules and read-only behavior.
Synthetic scale checks have no fragile timing thresholds. Repository-native static/history
auditing is not external certification. See [reproducibility](reproducibility.md).
