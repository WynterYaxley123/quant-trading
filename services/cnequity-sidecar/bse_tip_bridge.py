"""Sidecar compatibility: let the pinned instruments step see the Beijing board.

WHY THIS EXISTS
---------------
The pinned source discovers Beijing through
`steps/reference.py::_merge_bse_instruments(config, df, trade_date)`, which calls
`adapters.bse.instruments.fetch_bse_instruments(trade_date)`. The BSE board is a
CURRENT-STATE snapshot: it answers for the current Shanghai date and returns an
empty frame for any earlier session. The instruments step passes the *run's*
trade date, so every historical run gets an empty board.

The merge is deliberately "additive only, best effort" and returns the frame
unchanged when the board is empty, so the failure is silent:

    if board.is_empty():
        return df

Consequence in this lake: `curated/instruments` held 7,702 rows with zero BJ,
so `universe="all_a"` resolved to two exchanges out of three, and the daily-bar
step had no BJ symbol to route even though the pinned history adapter serves
346 of 347 BJ identities over the production window.

WHAT THIS PATCH DOES
--------------------
It wraps `fetch_bse_instruments` so that a *historical* date is served from the
board read at the **current tip**, while recording the true observation time.
It does not modify the pinned checkout, does not invent a historical board read,
and does not stamp any historical date onto the identity.

PIT CONTRACT (see docs/etf_quant/bj_identity_routing_admission_v1.md)
--------------------------------------------------------------------
A BJ row admitted this way is a ROUTING IDENTITY and nothing more:

  * `list_date`      stays NULL   -- the board's `hqssrq` is null by design, and
                                     the observation date must never fill it.
  * `delist_date`    stays NULL.
  * the observation time is preserved out-of-band in the provenance registry,
    because the pinned instruments schema has no field able to carry it.

Historical existence is proven separately, by real bars. The candidate cutoff is
never rewritten.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

#: Provenance for every identity admitted through this shim, keyed by symbol.
_REGISTRY: dict[str, dict[str, Any]] = {}
_REGISTRY_PATH: Path | None = None

PATCHED = False


def enable(*, registry_path: Path | None = None, board_session: dt.date | None = None) -> dict[str, Any]:
    """Install the tip-board shim. Idempotent.

    Returns a summary describing what was installed, for the run journal.
    """
    global PATCHED, _REGISTRY_PATH
    if registry_path is not None:
        _REGISTRY_PATH = Path(registry_path)

    from cnequity.adapters.bse import instruments as bse_instruments
    from cnequity.domain.market_time import shanghai_today

    original = bse_instruments.fetch_bse_instruments
    if getattr(original, "__cnequity_sidecar_tip__", False):
        return {"status": "ALREADY_ENABLED", "identities": len(_REGISTRY)}

    def fetch_bse_instruments_tip(trade_date: dt.date, *, client=None, config=None):
        """Serve a historical request from the current tip board, honestly."""
        observed_at = shanghai_today()
        snapshot_session = board_session or observed_at
        if snapshot_session > observed_at:
            raise ValueError("FUTURE_BSE_IDENTITY_SNAPSHOT_REJECTED")
        if trade_date == snapshot_session:
            board = original(snapshot_session, client=client, config=config)
            source = "BSE_TIP_BOARD_SAME_DAY"
        else:
            board = original(snapshot_session, client=client, config=config)
            source = "BSE_TIP_BOARD"
            if board.height:
                logger.info(
                    "sidecar: BSE board is tip-only; served %s from the %s read "
                    "(%d identities). effective_from=UNKNOWN, not stamped.",
                    trade_date, observed_at, board.height,
                )
        if board.height:
            for symbol in board["symbol"].to_list():
                _REGISTRY[symbol] = {
                    "symbol": symbol,
                    "exchange": "BJ",
                    "asset_type": "stock",
                    "identity_source": source,
                    "identity_observed_at": observed_at.isoformat(),
                    "source_snapshot_session": snapshot_session.isoformat(),
                    "requested_trade_date": trade_date.isoformat(),
                    "effective_from": "UNKNOWN",
                    "historical_pit_proven": False,
                    "identity_back_stamped": False,
                    "list_date": None,
                    "delist_date": None,
                }
        return board

    fetch_bse_instruments_tip.__cnequity_sidecar_tip__ = True  # type: ignore[attr-defined]
    fetch_bse_instruments_tip.__wrapped__ = original  # type: ignore[attr-defined]
    bse_instruments.fetch_bse_instruments = fetch_bse_instruments_tip

    # `steps.reference` imports the name at call time, but a module already
    # imported may hold its own binding; patch both to be safe.
    try:
        from cnequity.steps import reference as _reference

        _reference.fetch_bse_instruments = fetch_bse_instruments_tip  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 — reference imports lazily inside the function
        pass

    PATCHED = True
    return {"status": "ENABLED", "observed_at": shanghai_today().isoformat()}


def registry() -> dict[str, dict[str, Any]]:
    return dict(_REGISTRY)


def write_registry(path: Path | None = None) -> dict[str, Any]:
    """Persist the provenance registry so identity observations survive the run."""
    target = Path(path) if path is not None else _REGISTRY_PATH
    if target is None:
        raise ValueError("REGISTRY_PATH_REQUIRED")
    payload = {
        "registry": "BJ_ROUTING_IDENTITY_REGISTRY_V1",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "contract": "BJ_IDENTITY_ROUTING_ADMISSION_V1",
        "usage": "ROUTING_IDENTITY_ONLY",
        "not_historical_pit_evidence": True,
        "identities": sorted(_REGISTRY.values(), key=lambda r: r["symbol"]),
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    import hashlib

    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    return {"path": str(target), "identities": len(_REGISTRY), "sha256": digest}


def back_stamp_count() -> int:
    """Contract check: must always be 0."""
    return sum(1 for r in _REGISTRY.values() if r["identity_back_stamped"])
