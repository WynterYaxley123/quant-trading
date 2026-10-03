"""Production PIT evidence registry builder for ETF-Quant V1.

Runs entirely outside the Git work tree. Reads already-captured official raw bytes,
produces immutable evidence packages, derives benchmark L2 exposure, applies the
frozen B40 rule, emits the evidence book the existing runtime adapter consumes, and
writes a small metadata registry that *is* safe to commit.

It never contacts the network: collection is a separate, auditable step, and a
build that silently re-fetched would destroy reproducibility.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

# Explicit external roots support other machines; existing deployment defaults
# remain compatible. This builder is not part of the portable demo/test flow.
from scripts.etf_quant.production_pit_settings import CSI_REVERSE, PRIOR, REPORTS
from scripts.etf_quant.production_pit_settings import REPO as REPO
from strategies.etf_quant.evidence import (  # noqa: E402
    sha256_bytes,
)


def latest_real_retrieval() -> tuple[str, str]:
    """The latest instant at which any pinned byte stream was actually retrieved.

    A build may never claim to have observed evidence earlier than the moment the
    last raw byte came back from the provider. That would be exactly the historical
    backfill this task forbids, committed by the builder instead of by a strategy.
    The value is derived from the collection ledgers, never typed in by hand.
    """
    candidates: list[tuple[str, str]] = []
    sws_ledger = REPORTS / "sws_harvest_ledger.jsonl"
    if sws_ledger.exists():
        for line in sws_ledger.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            moment = row.get("retrieved_at")
            if isinstance(moment, str) and moment:
                candidates.append((moment, f"sws:{row.get('file')}"))
    csi_ledger = PRIOR / "official-sources" / "raw" / "csi_reverse"
    if csi_ledger.exists():
        newest = max((path.stat().st_mtime for path in csi_ledger.glob("*.json")), default=None)
        if newest is not None:
            moment = (
                datetime.fromtimestamp(newest, timezone.utc)
                .astimezone()
                .isoformat(timespec="seconds")
            )
            candidates.append((moment, "csi_reverse:filesystem_mtime_of_newest_response"))
    if not candidates:
        raise SystemExit("no collection ledger found; cannot establish an observation instant")
    moment, origin = max(candidates, key=lambda item: parse_for_order(item[0]))
    return moment, origin


def parse_for_order(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def assert_observed_after_every_retrieval(observed_at: str) -> tuple[str, str]:
    """Bound the claimed observation instant from both sides.

    It may not precede the last real retrieval (that would be history backfill) and
    it may not sit in the future (that would overstate how long the evidence has
    been usable). Both are the same class of error: a timestamp this system is not
    entitled to assert.
    """
    moment, origin = latest_real_retrieval()
    claimed = parse_for_order(observed_at)
    if claimed < parse_for_order(moment):
        raise SystemExit(
            f"REFUSING TO BACKDATE: --observed-at {observed_at} precedes the real "
            f"retrieval at {moment} ({origin}). Pass an instant at or after {moment}."
        )
    wall_clock = datetime.now(timezone.utc).astimezone()
    if claimed > wall_clock + timedelta(minutes=2):
        raise SystemExit(
            f"REFUSING A FUTURE OBSERVATION: --observed-at {observed_at} is later than "
            f"the real wall clock {wall_clock.isoformat(timespec='seconds')}. Evidence "
            "cannot claim to have been observed at an instant that has not happened."
        )
    return moment, origin


def csi_reverse_lineage(
    scope: frozenset[str] | None,
) -> tuple[dict[str, tuple[str, str]], dict[str, tuple[str, ...]]]:
    """Per-security and per-benchmark lineage back to the verbatim CSI responses.

    Returns ``(by_security, by_index)`` where each value is ``(file_name, sha256)``.
    Every rebuilt weight vector can therefore name the exact official byte streams
    it was assembled from, instead of merely asserting an endpoint.
    """
    by_security: dict[str, tuple[str, str]] = {}
    by_index: dict[str, set[str]] = {}
    for path in sorted(CSI_REVERSE.glob("*.json")):
        try:
            body = path.read_bytes()
            doc = json.loads(body)
        except Exception:
            continue
        if doc.get("error"):
            continue
        digest = sha256_bytes(body)
        by_security[path.stem] = (path.name, digest)
        for row in doc.get("data") or []:
            index_code = str(row.get("indexCode") or "").strip()
            if not index_code or (scope is not None and index_code not in scope):
                continue
            by_index.setdefault(index_code, set()).add(path.name)
    resolved = {code: tuple(sorted(names)) for code, names in by_index.items()}
    return by_security, resolved


def lineage_payload(
    names, by_security: dict[str, tuple[str, str]], *, limit: int = 400
) -> tuple[dict, ...]:
    """The upstream capture list for one extraction, capped and counted."""
    items = []
    for name in sorted(names)[:limit]:
        digest = next((value[1] for value in by_security.values() if value[0] == name), None)
        items.append({"capture": name, "sha256": digest})
    return tuple(items)
