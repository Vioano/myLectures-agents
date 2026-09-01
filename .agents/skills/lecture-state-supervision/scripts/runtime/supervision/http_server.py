"""Small local HTTP/SSE service shared by the Human UI and Agent CLI backend."""

from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import time
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse

from .core import DomainError
from .domain import resolve_repo_path
from .service import SupervisionService
from .store import DataRoot


class SupervisionHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], service: SupervisionService, static_root: Path):
        super().__init__(address, SupervisionHandler)
        self.service = service
        self.data_root = service.data_root
        self.static_root = static_root.resolve()


class SupervisionHandler(BaseHTTPRequestHandler):
    server: SupervisionHTTPServer
    protocol_version = "HTTP/1.1"

    def handle(self) -> None:
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError):
            # Media elements routinely cancel obsolete Range requests while
            # seeking or replacing a preload. That is normal client control
            # flow, not a supervision or playback failure.
            return

    def log_message(self, format: str, *args: object) -> None:
        print(f"[web] {self.address_string()} {format % args}")

    def _json(self, value: Any, status: int = 200) -> None:
        payload = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _error(self, error: Exception) -> None:
        if isinstance(error, DomainError):
            self._json(error.as_result(), error.http_status)
            return
        self._json(
            {
                "ok": False,
                "status": "internal_error",
                "code": "internal_error",
                "message": str(error),
            },
            HTTPStatus.INTERNAL_SERVER_ERROR,
        )

    def _read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise DomainError("invalid_request", "invalid Content-Length", "http_request_shape", http_status=400) from exc
        if length <= 0 or length > 2 * 1024 * 1024:
            raise DomainError("invalid_request", "JSON body is required and capped at 2 MiB", "http_request_shape", http_status=400)
        try:
            value = json.loads(self.rfile.read(length))
        except json.JSONDecodeError as exc:
            raise DomainError("invalid_json", "request body is not valid JSON", "http_json", http_status=400) from exc
        if not isinstance(value, dict):
            raise DomainError("invalid_request", "request JSON must be an object", "http_request_shape", http_status=400)
        return value

    def do_GET(self) -> None:  # noqa: N802
        try:
            parsed = urlparse(self.path)
            path = unquote(parsed.path)
            query = parse_qs(parsed.query)
            if path == "/api/health":
                self._json({"ok": True, "service": "lecture-state-supervision", "version": 1})
                return
            if path == "/api/episodes":
                self._json({"ok": True, "episodes": self.server.data_root.list_episodes()})
                return
            if path.startswith("/api/episodes/"):
                parts = [part for part in path.split("/") if part]
                if len(parts) < 4:
                    raise DomainError("not_found", "API route not found", "http_route", http_status=404)
                episode_id = parts[2]
                action = parts[3]
                if action == "overview":
                    self._json({"ok": True, "overview": self.server.service.overview(episode_id)})
                    return
                if action == "next":
                    actor = query.get("actor", ["human-ui"])[0]
                    role = query.get("role", ["human"])[0]
                    self._json(self.server.service.next_action(episode_id, actor=actor, role=role))
                    return
                if action == "agents" and len(parts) == 5:
                    self._json(
                        self.server.service.agent_probe(episode_id, parts[4])
                    )
                    return
                if action == "artifacts" and len(parts) == 6 and parts[5] == "media":
                    self._media(episode_id, parts[4])
                    return
                if action == "events":
                    after = int(query.get("after", ["0"])[0])
                    limit = int(query.get("limit", ["500"])[0])
                    store = self.server.data_root.episode_store(episode_id)
                    events = store.events_after(after, limit)
                    self._json(
                        {
                            "ok": True,
                            "events": events,
                            "cursor": events[-1]["seq"] if events else store.cursor(),
                        }
                    )
                    return
                if action == "capsules" and len(parts) == 5:
                    store = self.server.data_root.episode_store(episode_id)
                    capsule = store.get_capsule(parts[4])
                    if capsule is None:
                        raise DomainError(
                            "capsule_not_found",
                            "context capsule was not found in this episode",
                            "capsule_episode_boundary",
                            allowed_next=("overview", "explain"),
                            http_status=404,
                        )
                    self._json({"ok": True, "status": "read_only", "capsule": capsule})
                    return
                if action == "context-preview" and len(parts) == 5:
                    actor = query.get("actor", ["human-ui"])[0]
                    self._json(
                        self.server.service.preview_context(
                            episode_id, parts[4], actor=actor
                        )
                    )
                    return
                if action == "explain" and len(parts) == 5:
                    actor = query.get("actor", ["human-ui"])[0]
                    self._json(
                        self.server.service.explain(
                            episode_id, parts[4], actor=actor
                        )
                    )
                    return
                if action == "scan":
                    deep = query.get("deep", ["false"])[0].lower() == "true"
                    self._json(self.server.service.scan(episode_id, deep=deep))
                    return
            if path == "/api/stream":
                self._stream(query)
                return
            self._static(path)
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as error:
            self._error(error)

    def do_POST(self) -> None:  # noqa: N802
        try:
            parsed = urlparse(self.path)
            if parsed.path != "/api/command":
                raise DomainError("not_found", "API route not found", "http_route", http_status=404)
            body = self._read_json()
            self._json(self._command(body))
        except Exception as error:
            self._error(error)

    def do_HEAD(self) -> None:  # noqa: N802
        try:
            parsed = urlparse(self.path)
            path = unquote(parsed.path)
            parts = [part for part in path.split("/") if part]
            if (
                len(parts) == 6
                and parts[:2] == ["api", "episodes"]
                and parts[3] == "artifacts"
                and parts[5] == "media"
            ):
                self._media(parts[2], parts[4], head_only=True)
                return
            raise DomainError(
                "not_found",
                "HEAD route not found",
                "http_route",
                http_status=404,
            )
        except Exception as error:
            self._error(error)

    def _command(self, body: dict[str, Any]) -> dict[str, Any]:
        command = str(body.get("command", "")).strip()
        episode_id = str(body.get("episode_id", "")).strip()
        actor = str(body.get("actor", "human-ui")).strip()
        request_id = body.get("request_id")
        arguments = body.get("arguments", {})
        if not isinstance(arguments, dict):
            raise DomainError("invalid_request", "arguments must be an object", "http_command_shape", http_status=400)
        common = {"actor": actor, "request_id": request_id}
        if command == "dispatch.reserve":
            assignments = arguments.get("assignments", [])
            if not isinstance(assignments, list):
                raise DomainError(
                    "invalid_request",
                    "assignments must be an array",
                    "http_command_shape",
                    http_status=400,
                )
            return self.server.service.reserve_dispatch_tasks(
                episode_id,
                reason=str(arguments.get("reason", "")),
                assignments=assignments,
                ttl_seconds=int(arguments.get("ttl_seconds", 15 * 60)),
                **common,
            )
        if command == "context.override":
            return self.server.service.add_context_override(
                episode_id,
                str(arguments.get("task_id", "")),
                instruction=str(arguments.get("instruction", "")),
                label=str(arguments.get("label", "临时要求")),
                scope=str(arguments.get("scope", "task")),
                assembly_mode=str(arguments.get("assembly_mode", "append")),
                context_slot=str(
                    arguments.get("context_slot", "temporary.instructions")
                ),
                delivery_policy=str(
                    arguments.get("delivery_policy", "attention_boundary")
                ),
                precedence=int(arguments.get("precedence", 700)),
                **common,
            )
        if command == "annotate":
            return self.server.service.annotate(
                episode_id,
                target_id=str(arguments.get("target_id", "")),
                body=str(arguments.get("body", "")),
                severity=str(arguments.get("severity", "note")),
                location=arguments.get("location"),
                **common,
            )
        if command == "annotate.batch":
            annotations = arguments.get("annotations", [])
            if not isinstance(annotations, list):
                raise DomainError(
                    "invalid_request",
                    "annotations must be an array",
                    "http_command_shape",
                    http_status=400,
                )
            return self.server.service.annotate_batch(
                episode_id,
                annotations=annotations,
                **common,
            )
        if command == "change":
            return self.server.service.change(
                episode_id,
                target_id=str(arguments.get("target_id", "")),
                reason=str(arguments.get("reason", "")),
                kind=str(arguments.get("kind", "scope_change")),
                **common,
            )
        if command == "route.switch":
            replacement_spec = arguments.get("replacement_spec", {})
            if not isinstance(replacement_spec, dict):
                raise DomainError(
                    "invalid_request",
                    "replacement_spec must be an object",
                    "http_command_shape",
                    http_status=400,
                )
            return self.server.service.switch_route(
                episode_id,
                str(arguments.get("replaced_task_id", "")),
                str(arguments.get("replacement_task_id", "")),
                strategy=str(arguments.get("strategy", "")),
                reason=str(arguments.get("reason", "")),
                replacement_spec=replacement_spec,
                **common,
            )
        if command == "gap":
            return self.server.service.gap(
                episode_id,
                str(arguments.get("task_id", "")),
                reason=str(arguments.get("reason", "")),
                kind=str(arguments.get("kind", "missing_input")),
                **common,
            )
        if command == "gap.resolve":
            return self.server.service.resolve_gap(
                episode_id,
                str(arguments.get("gap_id", "")),
                resolution=str(arguments.get("resolution", "")),
                **common,
            )
        if command == "human.decide":
            return self.server.service.human_decide(
                episode_id,
                str(arguments.get("task_id", "")),
                verdict=str(arguments.get("verdict", "")),
                note=str(arguments.get("note", "")),
                **common,
            )
        if command == "review":
            return self.server.service.review(
                episode_id,
                str(arguments.get("task_id", "")),
                verdict=str(arguments.get("verdict", "")),
                findings=arguments.get("findings", []),
                note=str(arguments.get("note", "")),
                review_context_hash=arguments.get("review_context_hash"),
                return_to=arguments.get("return_to"),
                **common,
            )
        if command == "return.route":
            return self.server.service.reroute_return(
                episode_id,
                str(arguments.get("return_ticket_id", "")),
                to_actor=str(arguments.get("to_actor", "")),
                reason=str(arguments.get("reason", "")),
                **common,
            )
        if command == "recover":
            return self.server.service.recover(
                episode_id,
                actor=actor,
                apply=bool(arguments.get("apply", False)),
                deep=bool(arguments.get("deep", False)),
                request_id=request_id,
            )
        raise DomainError(
            "unsupported_web_command",
            f"Web UI command {command!r} is not supported",
            failed_invariant="web_command_allowlist",
            allowed_next=("overview", "explain"),
            http_status=400,
        )

    def _media(self, episode_id: str, artifact_id: str, *, head_only: bool = False) -> None:
        store = self.server.data_root.episode_store(episode_id)
        artifact, _ = store.get("artifact", artifact_id)
        if artifact is None or artifact.get("episode_id") != episode_id:
            raise DomainError(
                "artifact_not_found",
                "media artifact was not found in this episode",
                "artifact_episode_boundary",
                http_status=404,
            )
        path = resolve_repo_path(
            self.server.service.repo_root,
            str(artifact.get("path", "")),
        )
        expected_size = int(artifact.get("size", -1))
        if not path.is_file() or path.stat().st_size != expected_size:
            raise DomainError(
                "artifact_drift",
                "media artifact is missing or its byte size no longer matches the registered candidate",
                "artifact_snapshot_current",
                allowed_next=("scan", "change"),
                details={"artifact_id": artifact_id, "path": artifact.get("path")},
                http_status=409,
            )
        size = path.stat().st_size
        byte_range = self._media_range(size)
        if byte_range is None:
            return
        start, end, partial = byte_range
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.PARTIAL_CONTENT if partial else HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Accept-Ranges", "bytes")
        content_length = 0 if size == 0 else end - start + 1
        self.send_header("Content-Length", str(content_length))
        self.send_header("Cache-Control", "private, no-cache")
        self.send_header("ETag", f'"{artifact.get("sha256", "")}"')
        self.send_header(
            "Content-Disposition",
            f"inline; filename*=UTF-8''{quote(path.name)}",
        )
        self.send_header("X-Content-Type-Options", "nosniff")
        if partial:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        if head_only or size == 0:
            return
        remaining = end - start + 1
        with path.open("rb") as handle:
            handle.seek(start)
            while remaining > 0:
                chunk = handle.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def _media_range(self, size: int) -> tuple[int, int, bool] | None:
        raw = self.headers.get("Range", "").strip()
        if not raw:
            return 0, max(0, size - 1), False
        try:
            if not raw.startswith("bytes=") or "," in raw or size <= 0:
                raise ValueError
            spec = raw.removeprefix("bytes=")
            start_text, end_text = spec.split("-", 1)
            if not start_text:
                suffix = int(end_text)
                if suffix <= 0:
                    raise ValueError
                start = max(0, size - suffix)
                end = size - 1
            else:
                start = int(start_text)
                end = int(end_text) if end_text else size - 1
                if start < 0 or start >= size or end < start:
                    raise ValueError
                end = min(end, size - 1)
            return start, end, True
        except (TypeError, ValueError):
            self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
            self.send_header("Content-Range", f"bytes */{size}")
            self.send_header("Content-Length", "0")
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            return None

    def _stream(self, query: dict[str, list[str]]) -> None:
        episode_id = query.get("episode", [""])[0]
        after = int(query.get("after", ["0"])[0])
        store = self.server.data_root.episode_store(episode_id)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        cursor = after
        started = time.monotonic()
        last_ping = 0.0
        while time.monotonic() - started < 55:
            events = store.events_after(cursor, 200)
            if events:
                cursor = events[-1]["seq"]
                payload = json.dumps({"cursor": cursor, "events": events}, ensure_ascii=False)
                self.wfile.write(f"id: {cursor}\nevent: delta\ndata: {payload}\n\n".encode("utf-8"))
                self.wfile.flush()
            elif time.monotonic() - last_ping > 10:
                self.wfile.write(f": keepalive {cursor}\n\n".encode("utf-8"))
                self.wfile.flush()
                last_ping = time.monotonic()
            time.sleep(0.5)

    def _static(self, request_path: str) -> None:
        relative = "index.html" if request_path in {"", "/"} else request_path.lstrip("/")
        candidate = (self.server.static_root / relative).resolve()
        try:
            candidate.relative_to(self.server.static_root)
        except ValueError as exc:
            raise DomainError("forbidden", "invalid static path", "static_path_boundary", http_status=403) from exc
        if not candidate.is_file():
            candidate = self.server.static_root / "index.html"
        content = candidate.read_bytes()
        content_type = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
            ".svg": "image/svg+xml",
        }.get(candidate.suffix, "application/octet-stream")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(content)


def serve(
    *,
    host: str,
    port: int,
    data_root: Path,
    repo_root: Path,
    static_root: Path,
) -> None:
    service = SupervisionService(DataRoot(data_root), repo_root)
    server = SupervisionHTTPServer((host, port), service, static_root)
    print(f"Lecture State Supervision listening on http://{host}:{port}/")
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
