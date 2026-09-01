"""Version-pinned validator manifests and isolated subprocess execution."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any

from .core import DomainError, file_hash, object_hash
from .domain import display_path, resolve_repo_path


VALIDATOR_SCHEMA = "lecture-supervision-validator-v1"
GATE_RESULT_SCHEMA = "lecture-supervision-gate-result-v1"


def _asset_path(manifest_path: Path, repo_root: Path, raw_path: str) -> Path:
    expanded = raw_path.replace("{manifest_dir}", str(manifest_path.parent)).replace(
        "{repo_root}", str(repo_root)
    )
    candidate = Path(expanded)
    if not candidate.is_absolute():
        candidate = manifest_path.parent / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(repo_root)
    except ValueError as exc:
        raise DomainError(
            "validator_asset_outside_repo",
            f"validator asset escapes the repository: {raw_path}",
            failed_invariant="validator_assets_repo_scoped",
        ) from exc
    return resolved


def _validator_assets(
    manifest_path: Path, repo_root: Path, manifest: dict[str, Any]
) -> list[dict[str, Any]]:
    raw_assets = [str(item) for item in manifest.get("assets", [])]
    command = [str(item) for item in manifest["runner"]["command"]]
    raw_assets.extend(item for item in command[1:] if item.endswith(".py"))
    assets: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for raw_path in raw_assets:
        path = _asset_path(manifest_path, repo_root, raw_path)
        if path in seen:
            continue
        seen.add(path)
        if not path.is_file():
            raise DomainError(
                "validator_asset_missing",
                f"validator asset does not exist: {raw_path}",
                failed_invariant="validator_bundle_complete",
            )
        assets.append({"path": display_path(repo_root, path), "sha256": file_hash(path)})
    return sorted(assets, key=lambda item: item["path"])


def load_validator_manifest(path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DomainError(
            "validator_manifest_invalid",
            f"cannot read validator manifest {path}: {exc}",
            failed_invariant="validator_manifest_json",
        ) from exc
    if not isinstance(manifest, dict) or manifest.get("schema") != VALIDATOR_SCHEMA:
        raise DomainError(
            "validator_manifest_invalid",
            f"validator manifest must use schema {VALIDATOR_SCHEMA}",
            failed_invariant="validator_manifest_schema",
        )
    for field in ("validator_id", "version", "description", "runner"):
        if not manifest.get(field):
            raise DomainError(
                "validator_manifest_invalid",
                f"validator manifest is missing {field}",
                failed_invariant="validator_manifest_complete",
            )
    runner = manifest["runner"]
    if not isinstance(runner, dict) or not isinstance(runner.get("command"), list) or not runner["command"]:
        raise DomainError(
            "validator_manifest_invalid",
            "validator runner.command must be a non-empty argv array",
            failed_invariant="validator_runner_argv",
        )
    status = str(manifest.get("status", "draft"))
    if status not in {"draft", "canary", "active", "quarantined", "retired"}:
        raise DomainError(
            "validator_manifest_invalid",
            "validator status is invalid",
            failed_invariant="validator_lifecycle_state",
        )
    return manifest


def bind_validator(repo_root: Path, raw: dict[str, Any] | str) -> dict[str, Any]:
    descriptor = {"path": raw} if isinstance(raw, str) else dict(raw)
    raw_path = str(descriptor.get("path", "")).strip()
    if not raw_path:
        raise DomainError("invalid_validator", "validator manifest path is required", "validator_has_path")
    path = resolve_repo_path(repo_root, raw_path)
    if not path.is_file():
        raise DomainError(
            "validator_missing",
            f"validator manifest does not exist: {raw_path}",
            failed_invariant="validator_manifest_exists",
        )
    manifest = load_validator_manifest(path)
    requested_canary = bool(descriptor.get("allow_canary", False))
    if manifest.get("status") != "active" and not (requested_canary and manifest.get("status") == "canary"):
        raise DomainError(
            "validator_not_active",
            f"validator {manifest.get('validator_id')} is {manifest.get('status')}",
            failed_invariant="validator_activation_gate",
            recovery="Use an active manifest, or bind a canary only through explicit allow_canary planning.",
        )
    manifest_sha256 = file_hash(path)
    assets = _validator_assets(path, repo_root, manifest)
    bundle_sha256 = object_hash(
        {"manifest_sha256": manifest_sha256, "assets": assets}
    )
    return {
        "validator_id": str(manifest["validator_id"]),
        "version": str(manifest["version"]),
        "path": display_path(repo_root, path),
        "manifest_sha256": manifest_sha256,
        "assets": assets,
        "sha256": bundle_sha256,
        "required": bool(descriptor.get("required", True)),
        "canary": manifest.get("status") == "canary",
        "description": str(manifest["description"]),
    }


def verify_validator(repo_root: Path, descriptor: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    path = resolve_repo_path(repo_root, str(descriptor.get("path", "")))
    if not path.is_file():
        raise DomainError(
            "validator_missing",
            f"pinned validator manifest is missing: {descriptor.get('path')}",
            failed_invariant="validator_manifest_exists",
            allowed_next=("change", "gap"),
        )
    actual_manifest_hash = file_hash(path)
    expected_manifest_hash = descriptor.get("manifest_sha256")
    if actual_manifest_hash != expected_manifest_hash:
        raise DomainError(
            "validator_drift",
            f"validator changed after task planning: {descriptor.get('validator_id')}",
            failed_invariant="validator_version_pin",
            allowed_next=("change", "validator-rebind"),
            details={
                "expected_sha256": expected_manifest_hash,
                "actual_sha256": actual_manifest_hash,
            },
        )
    manifest = load_validator_manifest(path)
    if str(manifest.get("validator_id")) != descriptor.get("validator_id") or str(manifest.get("version")) != descriptor.get("version"):
        raise DomainError(
            "validator_identity_drift",
            "validator manifest identity differs from the task pin",
            failed_invariant="validator_identity_pin",
        )
    actual_assets = _validator_assets(path, repo_root, manifest)
    actual_bundle_hash = object_hash(
        {"manifest_sha256": actual_manifest_hash, "assets": actual_assets}
    )
    if actual_assets != descriptor.get("assets") or actual_bundle_hash != descriptor.get("sha256"):
        raise DomainError(
            "validator_drift",
            f"validator executable bundle changed after task planning: {descriptor.get('validator_id')}",
            failed_invariant="validator_bundle_pin",
            allowed_next=("change", "validator-rebind"),
            details={
                "expected_bundle_sha256": descriptor.get("sha256"),
                "actual_bundle_sha256": actual_bundle_hash,
            },
        )
    return path, manifest


def execute_validator(
    repo_root: Path,
    descriptor: dict[str, Any],
    input_payload: dict[str, Any],
) -> dict[str, Any]:
    manifest_path, manifest = verify_validator(repo_root, descriptor)
    runner = manifest["runner"]
    command = [str(item) for item in runner["command"]]
    if command[0] not in {"python3", "python", "uv"}:
        raise DomainError(
            "validator_runner_forbidden",
            "validator runner must use an allowlisted executable",
            failed_invariant="validator_runner_allowlist",
            details={"executable": command[0]},
        )
    resolved_command: list[str] = []
    for index, item in enumerate(command):
        replaced = item.replace("{manifest_dir}", str(manifest_path.parent)).replace("{repo_root}", str(repo_root))
        if index > 0 and not Path(replaced).is_absolute() and replaced.endswith(".py"):
            replaced = str((manifest_path.parent / replaced).resolve())
        resolved_command.append(replaced)
    timeout = max(1, min(int(runner.get("timeout_seconds", 60)), 600))
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "LC_ALL": os.environ.get("LC_ALL", "C.UTF-8"),
        "PYTHONIOENCODING": "utf-8",
        "LECTURE_VALIDATOR_ID": str(manifest["validator_id"]),
        "LECTURE_VALIDATOR_VERSION": str(manifest["version"]),
    }
    started = time.monotonic()
    try:
        completed = subprocess.run(
            resolved_command,
            input=json.dumps(input_payload, ensure_ascii=False),
            text=True,
            capture_output=True,
            cwd=repo_root,
            env=environment,
            timeout=timeout,
            check=False,
        )
        duration_ms = round((time.monotonic() - started) * 1000)
    except subprocess.TimeoutExpired as exc:
        return {
            "schema": GATE_RESULT_SCHEMA,
            "validator_id": descriptor["validator_id"],
            "validator_version": descriptor["version"],
            "status": "error",
            "summary": f"validator timed out after {timeout}s",
            "checks": [],
            "runner": {"timeout": True, "duration_ms": timeout * 1000, "stderr": str(exc)[:4000]},
        }
    stdout = completed.stdout[:1024 * 1024]
    stderr = completed.stderr[:64 * 1024]
    try:
        result = json.loads(stdout)
    except json.JSONDecodeError:
        result = {
            "schema": GATE_RESULT_SCHEMA,
            "validator_id": descriptor["validator_id"],
            "validator_version": descriptor["version"],
            "status": "error",
            "summary": "validator did not emit valid JSON",
            "checks": [],
        }
    if not isinstance(result, dict):
        result = {"status": "error", "summary": "validator output must be a JSON object", "checks": []}
    result = {
        **result,
        "schema": GATE_RESULT_SCHEMA,
        "validator_id": descriptor["validator_id"],
        "validator_version": descriptor["version"],
        "runner": {
            "exit_code": completed.returncode,
            "duration_ms": duration_ms,
            "stderr": stderr,
        },
    }
    if completed.returncode != 0 and result.get("status") == "pass":
        result["status"] = "error"
        result["summary"] = "validator claimed pass but exited non-zero"
    if result.get("status") not in {"pass", "fail", "error"}:
        result["status"] = "error"
        result["summary"] = "validator status must be pass, fail, or error"
    if not isinstance(result.get("checks"), list):
        result["checks"] = []
    return result
