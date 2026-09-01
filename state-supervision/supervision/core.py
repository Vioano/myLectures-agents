"""Dependency-free primitives shared by the supervision service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any


IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def object_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_hash(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def require_identifier(value: str, field: str) -> str:
    value = value.strip()
    if not IDENTIFIER_RE.fullmatch(value):
        raise DomainError(
            "invalid_identifier",
            f"{field} must match {IDENTIFIER_RE.pattern}",
            failed_invariant="stable_identifier",
            details={"field": field, "value": value},
        )
    return value


@dataclass(slots=True)
class DomainError(RuntimeError):
    """A stable, user-actionable domain denial rather than an internal crash."""

    code: str
    message: str
    failed_invariant: str
    allowed_next: tuple[str, ...] = ()
    recovery: str | None = None
    details: dict[str, Any] | None = None
    http_status: int = 409

    def __post_init__(self) -> None:
        RuntimeError.__init__(self, self.message)

    def as_result(self) -> dict[str, Any]:
        return {
            "ok": False,
            "status": "denied",
            "code": self.code,
            "message": self.message,
            "failed_invariant": self.failed_invariant,
            "allowed_next": list(self.allowed_next),
            "recovery": self.recovery,
            "details": self.details or {},
        }
