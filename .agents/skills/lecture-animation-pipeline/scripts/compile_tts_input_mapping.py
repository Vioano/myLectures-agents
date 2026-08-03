#!/usr/bin/env python3
"""Compile an exact, replayable TTS input from immutable formal narration."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from pipeline_v2_lib.episode_ops import _registry_occurrences


SCRIPT_ROOT = Path(__file__).resolve().parent
DEFAULT_REGISTRY = SCRIPT_ROOT.parent / "references/tts-pronunciation-registry.json"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise SystemExit(f"artifact is outside repo root: {path}") from exc


def parse_replacements(values: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise SystemExit(f"expected TOKEN=SPOKEN_FORM, received {value!r}")
        token, spoken_form = value.split("=", 1)
        token = token.strip().casefold()
        if not token or not spoken_form or token in result:
            raise SystemExit(f"invalid or duplicate replacement {value!r}")
        result[token] = spoken_form
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--scene-slug", required=True)
    parser.add_argument("--formal-script", required=True)
    parser.add_argument("--tts-input", required=True)
    parser.add_argument("--mapping", required=True)
    parser.add_argument("--route-id", required=True)
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--replace", action="append", default=[])
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    formal_path = Path(args.formal_script).resolve()
    tts_input_path = Path(args.tts_input).resolve()
    mapping_path = Path(args.mapping).resolve()
    registry_path = Path(args.registry).resolve()
    canonical_registry = (
        repo_root
        / ".agents/skills/lecture-animation-pipeline/references/tts-pronunciation-registry.json"
    ).resolve()
    if registry_path != canonical_registry:
        raise SystemExit("--registry must name the canonical Skill registry")
    for path in (formal_path, registry_path):
        if not path.is_file():
            raise SystemExit(f"required input does not exist: {path}")
    relative(formal_path, repo_root)
    relative(tts_input_path, repo_root)
    relative(mapping_path, repo_root)
    relative(registry_path, repo_root)

    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    if args.route_id not in dict(registry.get("routes", {})):
        raise SystemExit(f"unregistered route_id: {args.route_id}")
    route_candidates = dict(registry["routes"][args.route_id]).get(
        "candidate_forms", {}
    )
    replacements = parse_replacements(args.replace)
    unknown = sorted(set(replacements) - set(dict(registry.get("tokens", {}))))
    if unknown:
        raise SystemExit("unregistered replacement tokens: " + ", ".join(unknown))

    formal_text = formal_path.read_text(encoding="utf-8")
    occurrences = _registry_occurrences(formal_text, registry)
    observed_tokens = {row["token_key"] for row in occurrences}
    unused = sorted(set(replacements) - observed_tokens)
    if unused:
        raise SystemExit("replacement tokens have no formal occurrence: " + ", ".join(unused))

    rebuilt: list[str] = []
    previous_end = 0
    for row in occurrences:
        token_key = row["token_key"]
        spoken_form = replacements.get(token_key, row["formal_surface"])
        policy = registry["tokens"][token_key]
        allowed = {str(value) for value in dict(route_candidates).get(token_key, [])}
        forbidden = {
            str(value).strip().casefold()
            for value in policy.get("forbidden_forms", [])
        }
        if spoken_form != spoken_form.strip() or any(ord(char) < 32 for char in spoken_form):
            raise SystemExit(
                f"spoken form contains boundary whitespace or controls for {token_key}"
            )
        folded = spoken_form.casefold()
        if folded in forbidden:
            raise SystemExit(f"forbidden spoken form for {token_key}: {spoken_form!r}")
        if spoken_form not in allowed:
            raise SystemExit(f"unregistered spoken form for {token_key}: {spoken_form!r}")
        rebuilt.extend((formal_text[previous_end:row["formal_start"]], spoken_form))
        previous_end = row["formal_end"]
        row.update(
            {
                "spoken_form": spoken_form,
                "replacement_applied": spoken_form != row["formal_surface"],
                "context": formal_text[
                    max(0, row["formal_start"] - 18):min(
                        len(formal_text), row["formal_end"] + 18
                    )
                ].replace("\n", " "),
            }
        )
    rebuilt.append(formal_text[previous_end:])
    tts_text = "".join(rebuilt)

    tts_input_path.parent.mkdir(parents=True, exist_ok=True)
    mapping_path.parent.mkdir(parents=True, exist_ok=True)
    tts_input_path.write_text(tts_text, encoding="utf-8")
    mapping = {
        "schema": "lecture-animation-tts-input-mapping-v2",
        "scene_slug": args.scene_slug,
        "route_id": args.route_id,
        "formal_script_path": relative(formal_path, repo_root),
        "formal_script_sha256": sha256_bytes(formal_path.read_bytes()),
        "tts_input_path": relative(tts_input_path, repo_root),
        "tts_input_sha256": sha256_bytes(tts_text.encode("utf-8")),
        "policy": {
            "formal_script_immutable": True,
            "exact_ordered_span_replay_required": True,
            "unregistered_differences_blocked": True,
            "candidate_is_not_listening_pass": True,
        },
        "occurrences": occurrences,
        "status": "candidate_pending_exact_scene_ear_review",
    }
    mapping_path.write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "scene_slug": args.scene_slug,
                "route_id": args.route_id,
                "occurrence_count": len(occurrences),
                "replacement_count": sum(
                    bool(row["replacement_applied"]) for row in occurrences
                ),
                "tts_input_sha256": mapping["tts_input_sha256"],
                "mapping_path": relative(mapping_path, repo_root),
                "status": mapping["status"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
