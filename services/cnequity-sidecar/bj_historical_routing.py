"""Sidecar compatibility: route Beijing HISTORICAL bars to the THS adapter.

STATUS: root cause fully localized; hook NOT yet installed (see WHY NOT INSTALLED).

WHY THIS EXISTS — the complete source chain
-------------------------------------------
`steps/bars.py:853` partitions the fetch scope:

    tdx_symbols, fallback_symbols = split_by_quote_source(fetch_scope)

`domain/symbols.py::is_tdx_servable("920000.BJ")` returns **False**, so every
Beijing symbol lands in `fallback_symbols`. The fallback lane at
`steps/bars.py:909-934` is:

    bj_history = _fetch_bj_history_via_tdx(config, fallback_symbols, spec_start, spec_end, ...)
    sina_symbols = [s for s in fallback_symbols if s not in bj_history["covered"]]
    fallback = fetch_bars_via_sina(config, sina_symbols, spec_start, spec_end, ...)

So the Beijing lanes are **TDX (market id 2) then Sina**. THS is *not* in the
routing path at all: `_gapfill_missing_keys_via_ths` (`steps/bars.py:2761`) only
supplements keys that are **absent** after the cheaper routes, so a symbol that
returned a tip row is never re-examined.

Two measured facts complete the picture:

1. `list_trading_dates(config, 2025-04-10, 2026-09-24)` correctly returns **358**
   sessions, so the requested range is NOT wrong. The range bug hypothesis is
   rejected.
2. `_fetch_bj_history_via_tdx` (`steps/bars.py:1466`) calls
   `fetch_daily_bars_parallel(config, list(symbols), lo, hi, ...)`, which
   partitions through `split_by_quote_source` **again** — and that helper routes
   Beijing back to Sina. The TDX-BJ history function therefore cannot deliver
   Beijing history for the very symbols it exists to serve.

The pinned THS adapter serves them completely:

    cnequity.adapters.ths.stock_bars.fetch_stock_bars("920000.BJ",
        2025-04-10, 2026-09-24)  ->  358 rows, full OHLCV + amount

Measured directly: 346 of 347 BJ identities return a full history through THS;
`920985.BJ` returns none. **This is a routing defect, not a data gap.**

WHY NOT INSTALLED YET
---------------------
`_fetch_bj_history_via_tdx` returns `{"rows_read", "rows_written", "covered",
"requested"}` and achieves its persistence by delegating to
`fetch_daily_bars_parallel` — the official staging + manifest publisher. A
drop-in replacement must reproduce that publication path exactly, including the
run/batch bookkeeping that `_bj_history_covered` reads back. Writing THS rows
into `curated` directly would bypass the manifest and is forbidden by the round's
own rule (no direct curated writes), and staging them without the batch metadata
would corrupt `covered` and re-introduce the stale-batch class of blocker.

The correct fix is therefore to make the **partition** aware of Beijing rather
than to replace the fetcher: route BJ to a lane that uses the THS adapter *and*
publishes through `fetch_daily_bars_parallel`'s own machinery. That change is
localized but non-trivial, and it has NOT been made here rather than be made
unsafely.

WHAT THE FIX WILL DO
--------------------
    BJ  + historical range -> THS history, published via the official lifecycle
    BJ  + tip-only range   -> unchanged (BSE snapshot still owns the tip)
    SH / SZ                -> original implementation, byte-for-byte unchanged

Rows will carry `source="ths"` — the truth. A mislabeled source would corrupt the
amount-repair heuristics that key off `source` (see
`_supplement_bse_tip_amounts`).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

PATCHED = False

#: Diagnostics for the run journal.
STATS: dict[str, Any] = {"bj_routed_to_ths": 0, "bj_symbols": [], "sh_sz_untouched": 0}

#: The real hook name in the pinned revision (see module docstring).
BJ_HISTORY_HOOK = "_fetch_bj_history_via_tdx"
PARTITION_HOOK = "split_by_quote_source"


def diagnose() -> dict[str, Any]:
    """Report the routing facts without changing any behaviour."""
    from cnequity.domain.symbols import is_tdx_servable
    from cnequity.steps import bars as bars_step

    return {
        "partition_hook_present": hasattr(bars_step, PARTITION_HOOK),
        "bj_history_hook_present": hasattr(bars_step, BJ_HISTORY_HOOK),
        "ths_gapfill_present": hasattr(bars_step, "_gapfill_missing_keys_via_ths"),
        "is_tdx_servable_920000_BJ": is_tdx_servable("920000.BJ"),
        "is_tdx_servable_600519_SH": is_tdx_servable("600519.SH"),
        "installed": PATCHED,
        "note": "routing fix designed but intentionally not installed; see docstring",
    }
