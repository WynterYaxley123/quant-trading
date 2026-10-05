"""Terminal missed-session recovery; never reconstruct an intent or create a fill."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any


def abandon_missed_t1(ledger: dict[str, Any], *, day: date, now: datetime, epoch_key: str) -> bool:
    """Called under the account mutex and committed with the next legal generation.

    Preserve the original target and due date. Retire its epoch's fill authority,
    keeping holdings/cash/NAV intact for a new forward epoch. Duplicate wakes see
    the committed next generation, so cannot abandon twice or fill the old target.
    """
    pending = ledger.get("pending")
    if not pending or date.fromisoformat(pending["execution_date"]) >= day:
        return False
    if now.tzinfo is None or now.date() != day:
        raise ValueError("CURRENT_RECOVERY_TIME_REQUIRED")
    record = {
        "status": "ABANDONED_MISSED_T1",
        "recorded_at": now.isoformat(),
        "original_intent": dict(pending),
        "retroactive_fill_allowed": False,
        "fillable": False,
    }
    epoch = ledger.get(epoch_key)
    if epoch:
        ledger.setdefault("terminal_epochs", []).append(
            {
                **epoch,
                "status": "ABANDONED_MISSED_T1",
                "fillable": False,
                "ended_at": now.isoformat(),
            }
        )
    ledger.setdefault("recovery_events", []).append(record)
    for i, intent in enumerate(ledger.get("intents", [])):
        if intent == pending:
            ledger["intents"][i] = {**intent, "status": "ABANDONED_MISSED_T1", "fillable": False}
    ledger["pending"] = None
    ledger.pop(epoch_key, None)
    return True
