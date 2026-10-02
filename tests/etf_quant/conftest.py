"""Isolated pure tests; no root/data/source fixture dependency."""

import sys
from decimal import ROUND_HALF_EVEN, Context, localcontext
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def isolated_decimal_assertion_context():
    """RQAlpha import changes global Decimal precision during full collection.

    Core uses its own fixed context; test-side reference arithmetic must use
    that same precision, without modifying framework globals or assertions.
    Individual low-precision regression tests still override this locally.
    """
    with localcontext(Context(prec=50, rounding=ROUND_HALF_EVEN)):
        yield
