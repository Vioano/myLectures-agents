"""SQLite event store with per-episode isolation and rebuildable projections."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
from typing import Any

from .core import DomainError, canonical_json, object_hash, require_identifier, utc_now


SCHEMA_VERSION = 1


EPISODE_SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS schema_info (
  singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
  version INTEGER NOT NULL
);
INSERT OR IGNORE INTO schema_info(singleton, version) VALUES (1, 1);

CREATE TABLE IF NOT EXISTS events (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id TEXT NOT NULL UNIQUE,
  request_id TEXT NOT NULL,
  ordinal INTEGER NOT NULL,
  aggregate_type TEXT NOT NULL,
  aggregate_id TEXT NOT NULL,
  aggregate_version INTEGER NOT NULL,
  event_type TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  state_after_json TEXT NOT NULL,
  state_hash TEXT NOT NULL,
  actor TEXT NOT NULL,
  occurred_at TEXT NOT NULL,
  UNIQUE(request_id, ordinal),
  UNIQUE(aggregate_type, aggregate_id, aggregate_version)
);
CREATE INDEX IF NOT EXISTS events_aggregate_idx
  ON events(aggregate_type, aggregate_id, aggregate_version);
CREATE INDEX IF NOT EXISTS events_request_idx ON events(request_id);

CREATE TABLE IF NOT EXISTS aggregates (
  aggregate_type TEXT NOT NULL,
  aggregate_id TEXT NOT NULL,
  version INTEGER NOT NULL,
  state_json TEXT NOT NULL,
  state_hash TEXT NOT NULL,
  updated_seq INTEGER NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY(aggregate_type, aggregate_id),
  FOREIGN KEY(updated_seq) REFERENCES events(seq)
);

CREATE TABLE IF NOT EXISTS commands (
  request_id TEXT PRIMARY KEY,
  command_name TEXT NOT NULL,
  actor TEXT NOT NULL,
  payload_hash TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('completed', 'denied')),
  result_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS capsules (
  capsule_id TEXT PRIMARY KEY,
  capsule_hash TEXT NOT NULL UNIQUE,
  task_id TEXT NOT NULL,
  task_version INTEGER NOT NULL,
  payload_json TEXT NOT NULL,
  created_seq INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(created_seq) REFERENCES events(seq)
);

CREATE TABLE IF NOT EXISTS artifact_edges (
  upstream_artifact_id TEXT NOT NULL,
  downstream_artifact_id TEXT NOT NULL,
  relation TEXT NOT NULL,
  task_id TEXT NOT NULL,
  created_seq INTEGER NOT NULL,
  PRIMARY KEY(upstream_artifact_id, downstream_artifact_id, relation, task_id),
  FOREIGN KEY(created_seq) REFERENCES events(seq)
);
"""


CATALOG_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_info (
  singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
  version INTEGER NOT NULL
);
INSERT OR IGNORE INTO schema_info(singleton, version) VALUES (1, 1);
CREATE TABLE IF NOT EXISTS episodes (
  episode_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  db_path TEXT NOT NULL,
  status TEXT NOT NULL,
  health TEXT NOT NULL,
  last_seq INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
"""


class Transaction:
    """A single command transaction over one episode database."""

    def __init__(self, connection: sqlite3.Connection, request_id: str, actor: str, occurred_at: str):
        self.connection = connection
        self.request_id = request_id
        self.actor = actor
        self.occurred_at = occurred_at
        self.events: list[dict[str, Any]] = []
        self._ordinal = 0

    def get(self, aggregate_type: str, aggregate_id: str) -> tuple[dict[str, Any] | None, int]:
        row = self.connection.execute(
            "SELECT state_json, version FROM aggregates WHERE aggregate_type=? AND aggregate_id=?",
            (aggregate_type, aggregate_id),
        ).fetchone()
        if row is None:
            return None, 0
        return json.loads(row["state_json"]), int(row["version"])

    def require(self, aggregate_type: str, aggregate_id: str) -> tuple[dict[str, Any], int]:
        state, version = self.get(aggregate_type, aggregate_id)
        if state is None:
            raise DomainError(
                "not_found",
                f"{aggregate_type} {aggregate_id!r} does not exist",
                failed_invariant="aggregate_exists",
                allowed_next=("explain",),
                details={"aggregate_type": aggregate_type, "aggregate_id": aggregate_id},
                http_status=404,
            )
        return state, version

    def list(self, aggregate_type: str) -> list[tuple[dict[str, Any], int]]:
        rows = self.connection.execute(
            "SELECT state_json, version FROM aggregates WHERE aggregate_type=? ORDER BY aggregate_id",
            (aggregate_type,),
        ).fetchall()
        return [(json.loads(row["state_json"]), int(row["version"])) for row in rows]

    def transition(
        self,
        aggregate_type: str,
        aggregate_id: str,
        event_type: str,
        payload: dict[str, Any],
        state_after: dict[str, Any],
        *,
        expected_version: int | None = None,
    ) -> dict[str, Any]:
        require_identifier(aggregate_id, "aggregate_id")
        current, version = self.get(aggregate_type, aggregate_id)
        if expected_version is not None and version != expected_version:
            raise DomainError(
                "version_conflict",
                f"{aggregate_type} {aggregate_id!r} is at version {version}, not {expected_version}",
                failed_invariant="compare_and_swap",
                allowed_next=("explain",),
                recovery="Read the current aggregate and issue a new request id against its current version.",
                details={"expected_version": expected_version, "actual_version": version},
            )
        new_version = version + 1
        self._ordinal += 1
        event_id = "evt_" + object_hash({"request_id": self.request_id, "ordinal": self._ordinal})[:24]
        state_json = canonical_json(state_after)
        state_hash = object_hash(state_after)
        cursor = self.connection.execute(
            """
            INSERT INTO events(
              event_id, request_id, ordinal, aggregate_type, aggregate_id,
              aggregate_version, event_type, payload_json, state_after_json,
              state_hash, actor, occurred_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                self.request_id,
                self._ordinal,
                aggregate_type,
                aggregate_id,
                new_version,
                event_type,
                canonical_json(payload),
                state_json,
                state_hash,
                self.actor,
                self.occurred_at,
            ),
        )
        seq = int(cursor.lastrowid)
        self.connection.execute(
            """
            INSERT INTO aggregates(
              aggregate_type, aggregate_id, version, state_json, state_hash,
              updated_seq, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(aggregate_type, aggregate_id) DO UPDATE SET
              version=excluded.version,
              state_json=excluded.state_json,
              state_hash=excluded.state_hash,
              updated_seq=excluded.updated_seq,
              updated_at=excluded.updated_at
            """,
            (
                aggregate_type,
                aggregate_id,
                new_version,
                state_json,
                state_hash,
                seq,
                self.occurred_at,
            ),
        )
        summary = {
            "seq": seq,
            "event_id": event_id,
            "event_type": event_type,
            "aggregate_type": aggregate_type,
            "aggregate_id": aggregate_id,
            "aggregate_version": new_version,
            "state_hash": state_hash,
        }
        self.events.append(summary)
        return summary

    def save_capsule(self, task_id: str, task_version: int, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.events:
            raise RuntimeError("a capsule must be bound to a state transition in the same command")
        capsule_hash = object_hash(payload)
        capsule_id = "cap_" + capsule_hash[:24]
        self.connection.execute(
            """
            INSERT OR IGNORE INTO capsules(
              capsule_id, capsule_hash, task_id, task_version, payload_json,
              created_seq, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                capsule_id,
                capsule_hash,
                task_id,
                task_version,
                canonical_json(payload),
                self.events[-1]["seq"],
                self.occurred_at,
            ),
        )
        return {"capsule_id": capsule_id, "capsule_hash": capsule_hash, "payload": payload}


CommandHandler = Callable[[Transaction], dict[str, Any]]


def _command_subject(payload: dict[str, Any]) -> dict[str, Any]:
    for field in ("task_id", "target_id", "gap_id", "artifact_id", "scene_id", "wave_id", "episode_id"):
        if payload.get(field) not in (None, ""):
            return {"field": field, "id": payload[field]}
    return {}


class EpisodeStore:
    """Durable state for one episode; commands never span episode databases."""

    def __init__(self, path: Path):
        self.path = path.resolve()

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=30.0, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    def initialize(self) -> None:
        connection = self.connect()
        try:
            connection.executescript(EPISODE_SCHEMA)
            version = connection.execute(
                "SELECT version FROM schema_info WHERE singleton=1"
            ).fetchone()["version"]
            if int(version) != SCHEMA_VERSION:
                raise RuntimeError(f"unsupported episode schema version {version}")
        finally:
            connection.close()

    def execute(
        self,
        *,
        request_id: str,
        command_name: str,
        actor: str,
        payload: dict[str, Any],
        handler: CommandHandler,
        occurred_at: str | None = None,
    ) -> dict[str, Any]:
        request_id = require_identifier(request_id, "request_id")
        actor = require_identifier(actor, "actor")
        payload_hash = object_hash(payload)
        now = occurred_at or utc_now()
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            prior = connection.execute(
                "SELECT * FROM commands WHERE request_id=?", (request_id,)
            ).fetchone()
            if prior is not None:
                if (
                    prior["command_name"] != command_name
                    or prior["actor"] != actor
                    or prior["payload_hash"] != payload_hash
                ):
                    connection.rollback()
                    conflict = DomainError(
                        "idempotency_conflict",
                        "request id was already used for a different command payload",
                        failed_invariant="idempotency_key_reuse",
                        allowed_next=("explain",),
                        details={"request_id": request_id},
                    ).as_result()
                    return {
                        **conflict,
                        "command": command_name,
                        "request_id": request_id,
                        "cursor": self.latest_seq(connection),
                        "subject": _command_subject(payload),
                        "events": [],
                    }
                result = json.loads(prior["result_json"])
                connection.commit()
                result["idempotent_replay"] = True
                return result

            transaction = Transaction(connection, request_id, actor, now)
            result = handler(transaction)
            cursor = transaction.events[-1]["seq"] if transaction.events else self.latest_seq(connection)
            result = {
                "ok": True,
                "status": "completed",
                "command": command_name,
                "request_id": request_id,
                "cursor": cursor,
                "events": transaction.events,
                **result,
            }
            connection.execute(
                """
                INSERT INTO commands(
                  request_id, command_name, actor, payload_hash, status,
                  result_json, created_at, completed_at
                ) VALUES (?, ?, ?, ?, 'completed', ?, ?, ?)
                """,
                (request_id, command_name, actor, payload_hash, canonical_json(result), now, now),
            )
            connection.commit()
            return result
        except DomainError as error:
            connection.rollback()
            denied = {
                **error.as_result(),
                "command": command_name,
                "request_id": request_id,
                "cursor": self.latest_seq(connection),
                "subject": _command_subject(payload),
                "events": [],
            }
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT OR IGNORE INTO commands(
                  request_id, command_name, actor, payload_hash, status,
                  result_json, created_at, completed_at
                ) VALUES (?, ?, ?, ?, 'denied', ?, ?, ?)
                """,
                (request_id, command_name, actor, payload_hash, canonical_json(denied), now, utc_now()),
            )
            connection.commit()
            return denied
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def prior_command(
        self,
        *,
        request_id: str,
        command_name: str,
        actor: str,
        payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Return an exact prior result before an expensive external operation."""
        request_id = require_identifier(request_id, "request_id")
        actor = require_identifier(actor, "actor")
        payload_hash = object_hash(payload)
        with self.reader() as connection:
            row = connection.execute(
                "SELECT * FROM commands WHERE request_id=?", (request_id,)
            ).fetchone()
        if row is None:
            return None
        if (
            row["command_name"] != command_name
            or row["actor"] != actor
            or row["payload_hash"] != payload_hash
        ):
            raise DomainError(
                "idempotency_conflict",
                "request id was already used for a different command payload",
                failed_invariant="idempotency_key_reuse",
                allowed_next=("explain",),
                details={"request_id": request_id},
            )
        result = json.loads(row["result_json"])
        result["idempotent_replay"] = True
        return result

    @staticmethod
    def latest_seq(connection: sqlite3.Connection) -> int:
        return int(connection.execute("SELECT COALESCE(MAX(seq), 0) AS seq FROM events").fetchone()["seq"])

    @contextmanager
    def reader(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            yield connection
        finally:
            connection.close()

    def get(self, aggregate_type: str, aggregate_id: str) -> tuple[dict[str, Any] | None, int]:
        with self.reader() as connection:
            row = connection.execute(
                "SELECT state_json, version FROM aggregates WHERE aggregate_type=? AND aggregate_id=?",
                (aggregate_type, aggregate_id),
            ).fetchone()
            if row is None:
                return None, 0
            return json.loads(row["state_json"]), int(row["version"])

    def list(self, aggregate_type: str) -> list[tuple[dict[str, Any], int]]:
        with self.reader() as connection:
            rows = connection.execute(
                "SELECT state_json, version FROM aggregates WHERE aggregate_type=? ORDER BY aggregate_id",
                (aggregate_type,),
            ).fetchall()
            return [(json.loads(row["state_json"]), int(row["version"])) for row in rows]

    def events_after(self, after_seq: int = 0, limit: int = 500) -> list[dict[str, Any]]:
        with self.reader() as connection:
            rows = connection.execute(
                """
                SELECT seq, event_id, request_id, aggregate_type, aggregate_id,
                       aggregate_version, event_type, payload_json, state_hash,
                       actor, occurred_at
                FROM events WHERE seq>? ORDER BY seq LIMIT ?
                """,
                (max(0, after_seq), max(1, min(limit, 5000))),
            ).fetchall()
            return [
                {
                    **{key: row[key] for key in row.keys() if key != "payload_json"},
                    "payload": json.loads(row["payload_json"]),
                }
                for row in rows
            ]

    def cursor(self) -> int:
        with self.reader() as connection:
            return self.latest_seq(connection)

    def get_capsule(self, capsule_hash: str) -> dict[str, Any] | None:
        with self.reader() as connection:
            row = connection.execute(
                "SELECT * FROM capsules WHERE capsule_hash=?", (capsule_hash,)
            ).fetchone()
            if row is None:
                return None
            return {
                "capsule_id": row["capsule_id"],
                "capsule_hash": row["capsule_hash"],
                "task_id": row["task_id"],
                "task_version": row["task_version"],
                "payload": json.loads(row["payload_json"]),
                "created_seq": row["created_seq"],
                "created_at": row["created_at"],
            }

    def latest_capsule_for_task(self, task_id: str) -> dict[str, Any] | None:
        with self.reader() as connection:
            row = connection.execute(
                """
                SELECT * FROM capsules
                WHERE task_id=?
                ORDER BY created_seq DESC, capsule_id DESC
                LIMIT 1
                """,
                (task_id,),
            ).fetchone()
            if row is None:
                return None
            return {
                "capsule_id": row["capsule_id"],
                "capsule_hash": row["capsule_hash"],
                "task_id": row["task_id"],
                "task_version": row["task_version"],
                "payload": json.loads(row["payload_json"]),
                "created_seq": row["created_seq"],
                "created_at": row["created_at"],
            }

    def verify_integrity(self) -> dict[str, Any]:
        errors: list[dict[str, Any]] = []
        with self.reader() as connection:
            sqlite_check = connection.execute("PRAGMA integrity_check").fetchone()[0]
            if sqlite_check != "ok":
                errors.append({"kind": "sqlite_integrity", "detail": sqlite_check})
            last: dict[tuple[str, str], tuple[int, str, str, int]] = {}
            for row in connection.execute("SELECT * FROM events ORDER BY seq"):
                key = (row["aggregate_type"], row["aggregate_id"])
                expected_version = last.get(key, (0, "", "", 0))[0] + 1
                state = json.loads(row["state_after_json"])
                computed_hash = object_hash(state)
                if int(row["aggregate_version"]) != expected_version:
                    errors.append(
                        {
                            "kind": "event_version_gap",
                            "aggregate_type": key[0],
                            "aggregate_id": key[1],
                            "seq": row["seq"],
                            "expected": expected_version,
                            "actual": row["aggregate_version"],
                        }
                    )
                if row["state_hash"] != computed_hash:
                    errors.append(
                        {
                            "kind": "event_state_hash_mismatch",
                            "aggregate_type": key[0],
                            "aggregate_id": key[1],
                            "seq": row["seq"],
                        }
                    )
                last[key] = (int(row["aggregate_version"]), row["state_after_json"], computed_hash, int(row["seq"]))
            materialized = {
                (row["aggregate_type"], row["aggregate_id"]): row
                for row in connection.execute("SELECT * FROM aggregates")
            }
            for key, (version, state_json, state_hash, seq) in last.items():
                row = materialized.pop(key, None)
                if row is None:
                    errors.append({"kind": "missing_projection", "aggregate_type": key[0], "aggregate_id": key[1]})
                    continue
                if (
                    int(row["version"]) != version
                    or row["state_json"] != state_json
                    or row["state_hash"] != state_hash
                    or int(row["updated_seq"]) != seq
                ):
                    errors.append({"kind": "projection_drift", "aggregate_type": key[0], "aggregate_id": key[1]})
            for key in materialized:
                errors.append({"kind": "orphan_projection", "aggregate_type": key[0], "aggregate_id": key[1]})
            cursor = self.latest_seq(connection)
        return {"ok": not errors, "cursor": cursor, "errors": errors}

    def rebuild_projections(self, *, apply: bool = False, backup_dir: Path | None = None) -> dict[str, Any]:
        verification = self.verify_integrity()
        projection_errors = [
            error for error in verification["errors"]
            if error["kind"] in {"missing_projection", "projection_drift", "orphan_projection"}
        ]
        hard_errors = [error for error in verification["errors"] if error not in projection_errors]
        if hard_errors:
            raise DomainError(
                "event_log_corrupt",
                "projection rebuild is unsafe because the immutable event log failed verification",
                failed_invariant="event_log_integrity",
                allowed_next=("scan", "export"),
                details={"errors": hard_errors},
            )
        if not apply:
            return {"ok": not projection_errors, "would_rebuild": bool(projection_errors), "errors": projection_errors}
        if backup_dir is None:
            backup_dir = self.path.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / f"state-before-rebuild-{utc_now().replace(':', '-')}.db"
        source = self.connect()
        destination = sqlite3.connect(backup_path)
        try:
            source.backup(destination)
            destination.commit()
        finally:
            destination.close()
            source.close()
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DELETE FROM aggregates")
            rows = connection.execute(
                """
                SELECT e.* FROM events e
                JOIN (
                  SELECT aggregate_type, aggregate_id, MAX(aggregate_version) AS version
                  FROM events GROUP BY aggregate_type, aggregate_id
                ) latest
                ON e.aggregate_type=latest.aggregate_type
                AND e.aggregate_id=latest.aggregate_id
                AND e.aggregate_version=latest.version
                """
            ).fetchall()
            for row in rows:
                connection.execute(
                    """
                    INSERT INTO aggregates(
                      aggregate_type, aggregate_id, version, state_json, state_hash,
                      updated_seq, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["aggregate_type"], row["aggregate_id"], row["aggregate_version"],
                        row["state_after_json"], row["state_hash"], row["seq"], row["occurred_at"],
                    ),
                )
            connection.commit()
        finally:
            connection.close()
        after = self.verify_integrity()
        return {"ok": after["ok"], "backup_path": str(backup_path), "verification": after}


class DataRoot:
    """Episode registry plus isolated per-episode event stores."""

    def __init__(self, root: Path):
        self.root = root.expanduser().resolve()
        self.episodes_dir = self.root / "episodes"
        self.catalog_path = self.root / "catalog.sqlite3"

    def initialize(self) -> None:
        self.episodes_dir.mkdir(parents=True, exist_ok=True)
        with self._catalog() as connection:
            connection.executescript(CATALOG_SCHEMA)

    @contextmanager
    def _catalog(self) -> Iterator[sqlite3.Connection]:
        self.root.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.catalog_path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA busy_timeout=30000")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def episode_store(self, episode_id: str, *, must_exist: bool = True) -> EpisodeStore:
        episode_id = require_identifier(episode_id, "episode_id")
        path = self.episodes_dir / episode_id / "state.db"
        if must_exist and not path.exists():
            raise DomainError(
                "episode_not_found",
                f"episode {episode_id!r} is not registered",
                failed_invariant="episode_exists",
                allowed_next=("episode-create", "episodes"),
                http_status=404,
            )
        return EpisodeStore(path)

    def register_episode(
        self,
        episode_id: str,
        title: str,
        store: EpisodeStore,
        *,
        verified_health: str | None = None,
    ) -> None:
        episode, _ = store.get("episode", episode_id)
        if episode is None:
            raise RuntimeError("cannot register catalog entry before episode aggregate exists")
        cursor = store.cursor()
        now = utc_now()
        with self._catalog() as connection:
            previous = connection.execute(
                "SELECT health FROM episodes WHERE episode_id=?", (episode_id,)
            ).fetchone()
            health = verified_health or (str(previous["health"]) if previous is not None else "unknown")
            connection.execute(
                """
                INSERT INTO episodes(
                  episode_id, title, db_path, status, health, last_seq,
                  created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(episode_id) DO UPDATE SET
                  title=excluded.title,
                  db_path=excluded.db_path,
                  status=excluded.status,
                  health=excluded.health,
                  last_seq=excluded.last_seq,
                  updated_at=excluded.updated_at
                """,
                (
                    episode_id,
                    title,
                    str(store.path),
                    str(episode.get("status", "unknown")),
                    health,
                    cursor,
                    str(episode.get("created_at", now)),
                    now,
                ),
            )

    def sync_episode(self, episode_id: str) -> None:
        store = self.episode_store(episode_id)
        episode, _ = store.get("episode", episode_id)
        if episode is None:
            raise DomainError(
                "episode_projection_missing",
                "episode database exists but has no episode aggregate",
                failed_invariant="episode_projection_exists",
                allowed_next=("recover",),
            )
        self.register_episode(episode_id, str(episode.get("title", episode_id)), store)

    def list_episodes(self) -> list[dict[str, Any]]:
        self.initialize()
        with self._catalog() as connection:
            rows = connection.execute("SELECT * FROM episodes ORDER BY updated_at DESC, episode_id").fetchall()
            return [dict(row) for row in rows]

    def rebuild_catalog(self) -> dict[str, Any]:
        self.initialize()
        found: list[str] = []
        errors: list[dict[str, str]] = []
        for path in sorted(self.episodes_dir.glob("*/state.db")):
            episode_id = path.parent.name
            try:
                store = EpisodeStore(path)
                store.initialize()
                episode, _ = store.get("episode", episode_id)
                if episode is None:
                    raise RuntimeError("missing episode aggregate")
                self.register_episode(episode_id, str(episode.get("title", episode_id)), store)
                found.append(episode_id)
            except Exception as exc:
                errors.append({"episode_id": episode_id, "error": str(exc)})
        with self._catalog() as connection:
            if found:
                placeholders = ",".join("?" for _ in found)
                connection.execute(f"DELETE FROM episodes WHERE episode_id NOT IN ({placeholders})", found)
            else:
                connection.execute("DELETE FROM episodes")
        return {"ok": not errors, "episodes": found, "errors": errors}
