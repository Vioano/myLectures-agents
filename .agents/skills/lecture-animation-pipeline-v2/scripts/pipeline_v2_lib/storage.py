"""Process-safe durable storage for concurrent pipeline CLI invocations.

The CLI is intentionally synchronous. Parallel agents run separate CLI processes,
so correctness lives here: deterministic advisory locks, atomic JSON replacement,
and one-write JSONL appends.
"""

from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Callable, Iterator

from .core import PipelineError


LOCK_ROOT = Path(tempfile.gettempdir()) / "mylectures-pipeline-v2-locks"


def _lock_path(path: Path) -> Path:
    identity = hashlib.sha256(str(path.expanduser().resolve()).encode("utf-8")).hexdigest()
    return LOCK_ROOT / f"{identity}.lock"


@contextmanager
def locked_paths(paths: list[Path] | tuple[Path, ...]) -> Iterator[None]:
    """Hold exclusive locks for several state paths in deterministic order."""

    LOCK_ROOT.mkdir(parents=True, exist_ok=True)
    unique = sorted({path.expanduser().resolve() for path in paths}, key=str)
    handles = []
    try:
        for path in unique:
            lock_path = _lock_path(path)
            handle = lock_path.open("a+")
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            handles.append(handle)
        yield
    finally:
        for handle in reversed(handles):
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.close()


def load_json_unlocked(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PipelineError(f"cannot read JSON {path}: {exc}") from exc


def load_json(path: Path) -> Any:
    with locked_paths([path]):
        return load_json_unlocked(path)


def atomic_write_text_unlocked(path: Path, text: str) -> None:
    """Replace a file atomically after flushing its bytes to the same filesystem."""

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_write_json_unlocked(path: Path, value: Any) -> None:
    atomic_write_text_unlocked(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def write_json(path: Path, value: Any) -> None:
    with locked_paths([path]):
        atomic_write_json_unlocked(path, value)


def read_jsonl_unlocked(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="strict").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise PipelineError(f"invalid JSONL {path}:{line_number}: {exc}") from exc
        if not isinstance(value, dict):
            raise PipelineError(f"invalid JSONL {path}:{line_number}: row must be an object")
        rows.append(value)
    return rows


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with locked_paths([path]):
        return read_jsonl_unlocked(path)


def append_jsonl_unlocked(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    descriptor = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o644)
    try:
        written = 0
        while written < len(payload):
            written += os.write(descriptor, payload[written:])
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    with locked_paths([path]):
        append_jsonl_unlocked(path, value)


def append_unique_jsonl(
    path: Path,
    value: dict[str, Any],
    *,
    key_field: str,
) -> tuple[dict[str, Any], bool]:
    """Append exactly once under a process lock.

    Returns ``(stored_row, appended)``. The caller is responsible for making
    ``key_field`` a content-derived verification key.
    """

    key = value.get(key_field)
    if key in (None, ""):
        raise PipelineError(f"cannot append unique JSONL row without {key_field}")
    with locked_paths([path]):
        for row in read_jsonl_unlocked(path):
            if row.get(key_field) != key:
                continue
            return row, False
        append_jsonl_unlocked(path, value)
        return value, True


def update_json(
    path: Path,
    updater: Callable[[Any], Any],
    *,
    default: Any = None,
) -> Any:
    """Perform one locked read-modify-write transition."""

    with locked_paths([path]):
        current = load_json_unlocked(path) if path.exists() else default
        updated = updater(current)
        atomic_write_json_unlocked(path, updated)
        return updated
