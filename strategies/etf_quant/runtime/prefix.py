"""Content-addressed economic prefix cache with the original row identity contract.

The key authenticates every economic value on every call. Neither file metadata nor
provider identity can authorize a hit. Cache entries are generated here and remain
private in memory; external manifests cannot supply unchecked row hashes.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from .exports import KEYS
from .storage import digest, json_bytes

Prefix = dict[str, dict[str, str | None]]


class SourcePrefixIndex:
    """Bounded one-entry-per-dataset cache; mutation invalidates its SHA256 key."""

    def __init__(self) -> None:
        self._entries: dict[str, tuple[str, Prefix]] = {}

    def table(self, name: str, frame: pd.DataFrame, cutoff: date) -> Prefix | None:
        date_key = (
            "list_date"
            if name == "instruments"
            else "as_of_date"
            if name == "industry_membership"
            else "trade_date"
        )
        if date_key not in frame:
            return None
        columns = list(frame.columns)
        day_index = columns.index(date_key)
        key_indices = [columns.index(k) for k in KEYS[name]]
        economic_columns = [(i, c) for i, c in enumerate(columns) if c != "fetched_at"]
        records: dict[str, tuple[str | None, dict[str, str]]] = {}
        for row in frame.itertuples(index=False, name=None):
            day = row[day_index]
            if day is not None and day > cutoff:
                continue
            key = "|".join(str(row[i]) for i in key_indices)
            records[key] = (
                str(day) if day is not None else None,
                {c: str(row[i]) for i, c in economic_columns},
            )
        # Order-independent, cryptographic and content-only, like the original mapping.
        # Encode column names once rather than repeating them in every cache-key
        # row. Names, identities, dates and every value are still authenticated.
        authenticated = digest(
            json_bytes(
                {
                    "columns": [c for _, c in economic_columns],
                    "records": [
                        (key, day, tuple(economic.values()))
                        for key, (day, economic) in sorted(records.items())
                    ],
                }
            )
        )
        cached = self._entries.get(name)
        if cached is not None and cached[0] == authenticated:
            return {key: row.copy() for key, row in cached[1].items()}
        prefix = {
            key: {"date": day, "hash": digest(json_bytes(economic))}
            for key, (day, economic) in records.items()
        }
        self._entries[name] = (authenticated, prefix)
        return {key: row.copy() for key, row in prefix.items()}


_INDEX = SourcePrefixIndex()


def source_prefix(provider, *, index: SourcePrefixIndex | None = None) -> dict[str, Prefix]:
    """Authenticate mutable input anew, reuse row hashes only after an exact content hit."""
    cache = _INDEX if index is None else index
    result: dict[str, Prefix] = {}
    for name, frame in provider.tables.items():
        prefix = cache.table(name, frame, provider.cutoff)
        if prefix is not None:
            result[name] = prefix
    return result
