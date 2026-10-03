"""Single-pass economic prefix hashes for a fresh daily-cycle process.

Every consumed row is authenticated directly. No metadata, provider identity or
process-local cache can replace hashing its economic values.
"""

from __future__ import annotations

from .exports import KEYS
from .storage import digest, json_bytes

Prefix = dict[str, dict[str, str | None]]


def source_prefix(provider) -> dict[str, Prefix]:
    """Preserve row identities and byte hashes without a cold-cache double pass."""
    result: dict[str, Prefix] = {}
    for name, frame in provider.tables.items():
        date_key = (
            "list_date"
            if name == "instruments"
            else "as_of_date"
            if name == "industry_membership"
            else "trade_date"
        )
        if date_key not in frame:
            continue
        columns = list(frame.columns)
        day_index = columns.index(date_key)
        key_indices = [columns.index(k) for k in KEYS[name]]
        economic_columns = [(i, c) for i, c in enumerate(columns) if c != "fetched_at"]
        records: Prefix = {}
        for row in frame.itertuples(index=False, name=None):
            day = row[day_index]
            if day is not None and day > provider.cutoff:
                continue
            key = "|".join(str(row[i]) for i in key_indices)
            economic = {c: str(row[i]) for i, c in economic_columns}
            records[key] = {
                "date": str(day) if day is not None else None,
                "hash": digest(json_bytes(economic)),
            }
        result[name] = records
    return result
