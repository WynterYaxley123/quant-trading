"""Validate Docker's comma-delimited mount grammar before constructing argv."""

from __future__ import annotations

import re
from pathlib import Path


class MountInputError(ValueError):
    """A reference or path cannot be represented safely as a Docker mount."""


def reference_name(value: str) -> str:
    """Accept one bounded identifier, never a path or Docker grammar fragment."""
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9._-]{0,95}", value) or ".." in value:
        raise MountInputError("INVALID_MODEL_REFERENCE_NAME")
    return value


def bind_mount(source: Path, target: str, *, readonly: bool) -> list[str]:
    """Keep spaces in path values safe through argv; reject grammar delimiters."""
    values = (str(source), target)
    if any(not value or re.search(r"[,\"'\r\n\x00=]", value) for value in values):
        raise MountInputError("INVALID_DOCKER_MOUNT_PATH")
    return [
        "--mount",
        f"type=bind,source={source},target={target}" + (",readonly" if readonly else ""),
    ]
