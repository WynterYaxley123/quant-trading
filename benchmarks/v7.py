"""Synthetic V7 profiles; timings are observations, never acceptance thresholds."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from time import perf_counter

import numpy as np
import polars as pl

from strategies.etf_quant_v2.facts import MembershipLookup


def profile() -> dict[str, object]:
    days = tuple(date(2020, 1, 1) + timedelta(days=i) for i in range(2200))
    rows = [days[i] for i in range(1100, 1400) for _ in range(124)]
    start = perf_counter()
    before = [days.index(day) + 120 for day in rows]
    old = perf_counter() - start
    start = perf_counter()
    positions = {day: i for i, day in enumerate(days)}
    after = [positions[day] + 120 for day in rows]
    new = perf_counter() - start
    assert before == after
    frame = pl.DataFrame(
        {
            "symbol": [str(i % 5000) for i in range(100000)],
            "as_of_date": [days[i // 5000] for i in range(100000)],
            "industry_code": [str(i % 124) for i in range(100000)],
        }
    )
    start = perf_counter()
    for i in range(5):
        frame.filter(pl.col("as_of_date") <= days[100 + i]).sort("as_of_date").unique(
            "symbol", keep="last"
        )
    membership = perf_counter() - start
    start = perf_counter()
    lookup = MembershipLookup(frame)
    actuals = [lookup.visible(days[100 + i]) for i in range(5)]
    indexed = perf_counter() - start
    start = perf_counter()
    for i in range(5):
        actual = actuals[i]
        expected = (
            frame.filter(pl.col("as_of_date") <= days[100 + i])
            .sort("as_of_date")
            .unique("symbol", keep="last")
            .sort("symbol")
        )
        assert actual.to_dicts() == expected.to_dicts()
    checked = perf_counter() - start
    sample = pl.DataFrame({"symbol": [str(i) for i in range(400)], "as_of_date": [days[0]] * 400})
    rng = np.random.default_rng(1704)
    returns = dict(zip(sample["symbol"].to_list(), rng.normal(0, 0.01, 400), strict=True))
    prior_means, stable_means = set(), set()
    for _ in range(30):
        old_symbols = sample.sort("as_of_date").unique("symbol", keep="last")["symbol"].to_list()
        new_symbols = MembershipLookup(sample).visible(days[0])["symbol"].to_list()
        prior_means.add(np.asarray([np.mean([returns[s] for s in old_symbols])]).tobytes())
        stable_means.add(np.asarray([np.mean([returns[s] for s in new_symbols])]).tobytes())
    assert len(stable_means) == 1
    start = perf_counter()
    reference = {(r["symbol"], r["as_of_date"]): r for r in frame.to_dicts()}
    materialized = perf_counter() - start
    start = perf_counter()
    streamed = {(r["symbol"], r["as_of_date"]): r for r in frame.iter_rows(named=True)}
    streaming = perf_counter() - start
    assert reference == streamed
    state = {
        "signals": [
            {"day": str(days[i]), "models": [{"coef": list(range(19))}] * 3} for i in range(1000)
        ]
    }
    start = perf_counter()
    raw = json.dumps(state, sort_keys=True, separators=(",", ":")).encode()
    again = json.dumps(state, sort_keys=True, separators=(",", ":")).encode()
    twice = perf_counter() - start
    start = perf_counter()
    once = json.dumps(state, sort_keys=True, separators=(",", ":")).encode()
    single = perf_counter() - start
    assert raw == again == once
    return {
        "synthetic_only": True,
        "session_lookup": {"rows": len(rows), "before_seconds": old, "after_seconds": new},
        "membership_5_dates_seconds": membership,
        "membership_index": {
            "after_seconds": indexed,
            "equivalence_check_seconds": checked,
            "view_builds": lookup.builds,
            "rows_equal": True,
            "canonical_symbol_order": True,
            "prior_mean_hashes_on_identical_inputs": len(prior_means),
            "current_mean_hashes_on_identical_inputs": len(stable_means),
            "prior_repetitions": 30,
        },
        "stock_rows": {
            "rows": len(frame),
            "before_seconds": materialized,
            "after_seconds": streaming,
            "removed_full_intermediate_list": True,
        },
        "state_json": {"bytes": len(raw), "before_seconds": twice, "after_seconds": single},
        "exact_output_equivalence": True,
        "timing_is_not_a_gate": True,
    }


if __name__ == "__main__":
    Path("/tmp/v7-profile.json").write_text(json.dumps(profile(), indent=2) + "\n")
