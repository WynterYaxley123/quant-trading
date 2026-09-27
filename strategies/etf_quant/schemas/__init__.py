"""Pure JSON-compatible DTO projection, not a HTTP/API integration."""
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
import json
import math


def to_primitive(value):
    if isinstance(value, Enum): return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: to_primitive(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, (date, datetime)): return value.isoformat()
    if isinstance(value, Decimal):
        if not value.is_finite(): raise ValueError("nonfinite DTO money")
        return str(value)
    if isinstance(value, Mapping):
        if not all(isinstance(k, str) for k in value): raise ValueError("DTO object keys must be strings")
        return {k: to_primitive(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)): return [to_primitive(v) for v in value]
    if value is None or isinstance(value, (str, bool, int)): return value
    if isinstance(value, float) and math.isfinite(value): return value
    raise ValueError("unsupported/nonfinite DTO value")


def to_json(value) -> str:
    return json.dumps(to_primitive(value), ensure_ascii=False, allow_nan=False, sort_keys=True)
