"""BEIJING_AWARE_QUOTE_PARTITION_V1 — admit BJ to the TDX quote lane.

ROOT CAUSE (proven, single line)
---------------------------------
`domain/symbols.py:91`:

    TDX_EXCHANGES = frozenset({"SH", "SZ"})

`is_tdx_servable(symbol)` is `parse_symbol(symbol).exchange in TDX_EXCHANGES`,
so **every** Beijing symbol is judged un-servable by the TDX protocol and is
pushed to the Sina fallback lane (`steps/bars.py:853`).

But TDX *does* serve Beijing, and the pinned source already says so. Measured by
calling the protocol client directly, bypassing the gate:

    fetch_daily_bars(["920000.BJ"], 2025-04-10, 2026-09-24) -> 358 rows
        2025-04-10 .. 2026-09-24, cols: open high low close volume amount
    fetch_daily_bars(["920001.BJ"], ...)                    -> 358 rows
    fetch_daily_bars(["600519.SH"], ...)                    -> 358 rows  (control)
    fetch_daily_bars(["000001.SZ"], ...)                    -> 358 rows  (control)

And `steps/bars.py:1466` `_fetch_bj_history_via_tdx` documents its own reason for
existing: *"Beijing daily history from TDX, which serves it under market id 2."*

So the pipeline contains a Beijing-history function built on a lane that its own
gate excludes Beijing from. `_fetch_bj_history_via_tdx` calls
`fetch_daily_bars_parallel`, which partitions through `split_by_quote_source` →
`is_tdx_servable` → False for BJ → Sina. The gate, not the protocol, is the bug.

WHAT THIS PATCH DOES
--------------------
Adds `"BJ"` to the TDX-servable exchange set, in the sidecar, at runtime.

    BJ  historical -> TDX protocol (market id 2), full range in one call
    BJ  tip        -> unchanged; the BSE snapshot still owns the tip
    SH / SZ        -> byte-for-byte unchanged, same set membership

Nothing else moves: the same `fetch_daily_bars_parallel`, the same staging, the
same manifest/batch bookkeeping, the same compact. No row is written to
`curated` directly.

WHY THIS IS THE MINIMAL CHANGE
------------------------------
It repairs the *partition* -- the layer the round identified as the place that
must change -- and leaves the fetcher untouched. It also makes the pinned
`_fetch_bj_history_via_tdx` start working as designed, instead of replacing it.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

PATCHED = False
ORIGINAL_EXCHANGES: frozenset[str] | None = None


def enable() -> dict[str, Any]:
    """Admit BJ to the TDX quote lane. Idempotent, reversible, auditable."""
    global PATCHED, ORIGINAL_EXCHANGES

    from cnequity.domain import symbols as SY

    if ORIGINAL_EXCHANGES is None:
        ORIGINAL_EXCHANGES = SY.TDX_EXCHANGES

    if PATCHED:
        return {"status": "ALREADY_ENABLED", "tdx_exchanges": sorted(SY.TDX_EXCHANGES)}

    before = tuple(sorted(SY.TDX_EXCHANGES))
    SY.TDX_EXCHANGES = frozenset(SY.TDX_EXCHANGES | {"BJ"})
    after = tuple(sorted(SY.TDX_EXCHANGES))

    # Re-assert the servability predicate against the widened set, in case the
    # module bound its own view.
    probe = {s: SY.is_tdx_servable(s) for s in ("920000.BJ", "600519.SH", "000001.SZ")}
    if not probe["920000.BJ"]:
        SY.TDX_EXCHANGES = ORIGINAL_EXCHANGES
        return {"status": "FAILED_TO_WIDEN", "probe": probe}

    PATCHED = True
    logger.info(
        "sidecar: BEIJING_AWARE_QUOTE_PARTITION_V1 enabled; TDX exchanges %s -> %s",
        before,
        after,
    )
    return {"status": "ENABLED", "before": list(before), "after": list(after), "probe": probe}


def disable() -> dict[str, Any]:
    """Restore the pinned exchange set exactly."""
    global PATCHED
    from cnequity.domain import symbols as SY

    if ORIGINAL_EXCHANGES is not None:
        SY.TDX_EXCHANGES = ORIGINAL_EXCHANGES
    PATCHED = False
    return {"status": "DISABLED", "tdx_exchanges": sorted(SY.TDX_EXCHANGES)}


def diagnose() -> dict[str, Any]:
    from cnequity.domain import symbols as SY

    return {
        "patched": PATCHED,
        "tdx_exchanges": sorted(SY.TDX_EXCHANGES),
        "original_exchanges": sorted(ORIGINAL_EXCHANGES) if ORIGINAL_EXCHANGES else None,
        "probe": {
            s: SY.is_tdx_servable(s) for s in ("920000.BJ", "920001.BJ", "600519.SH", "000001.SZ")
        },
    }
