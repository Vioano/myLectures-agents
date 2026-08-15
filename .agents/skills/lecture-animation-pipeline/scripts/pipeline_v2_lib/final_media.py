"""Fail-closed verification for a viewer-facing upload package.

This module deliberately inspects the exact final media bytes.  State ledgers,
handwritten manifests, and whole-file loudness are not accepted as evidence
that every scene narration survived the final mix or that publication
subtitles were burned into the picture.
"""

from __future__ import annotations

from array import array
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import subprocess
from typing import Any

from .core import PipelineError, object_hash, utc_now
from .storage import load_json, write_json


UPLOAD_PACKAGE_SCHEMA = "lecture-animation-upload-package-v1"
UPLOAD_RECEIPT_SCHEMA = "lecture-animation-upload-package-receipt-v1"
SIGNOFF_TEXTS = ("我是结束乐队的键盘手", "下个视频见")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _resolve(path_value: str, repo_root: Path) -> Path:
    path = Path(path_value)
    return path.resolve() if path.is_absolute() else (repo_root / path).resolve()


def _relative_or_absolute(path: Path, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return str(path.resolve())


def _bound_file(
    binding: Any,
    repo_root: Path,
    label: str,
    errors: list[str],
) -> Path | None:
    if not isinstance(binding, dict):
        errors.append(f"{label} binding is missing")
        return None
    raw = str(binding.get("path", "") or "").strip()
    expected = str(binding.get("sha256", "") or "").strip()
    if not raw or not expected:
        errors.append(f"{label} must bind path and sha256")
        return None
    path = _resolve(raw, repo_root)
    if not path.is_file():
        errors.append(f"{label} does not exist: {path}")
        return None
    actual = _sha256(path)
    if actual != expected:
        errors.append(f"{label} sha256 is stale: expected {expected}, got {actual}")
        return None
    return path


def _run(command: list[str], *, binary: bool = False) -> bytes | str:
    completed = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace")
        raise PipelineError(
            f"command failed ({completed.returncode}): {' '.join(command)} | {stderr[-2000:]}"
        )
    return completed.stdout if binary else completed.stdout.decode("utf-8", errors="replace")


def probe_media(path: Path) -> dict[str, Any]:
    payload = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ]
    )
    assert isinstance(payload, str)
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise PipelineError(f"ffprobe returned invalid JSON for {path}: {exc}") from exc


def validate_upload_media_spec(probe: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    streams = probe.get("streams")
    if not isinstance(streams, list):
        return ["ffprobe stream list is missing"], {}
    videos = [row for row in streams if row.get("codec_type") == "video"]
    audios = [row for row in streams if row.get("codec_type") == "audio"]
    subtitles = [row for row in streams if row.get("codec_type") == "subtitle"]
    if len(videos) != 1:
        errors.append(f"upload must contain exactly one video stream, found {len(videos)}")
    if len(audios) != 1:
        errors.append(f"upload must contain exactly one audio stream, found {len(audios)}")
    if subtitles:
        errors.append("burned-subtitle upload must not contain a subtitle stream")
    video = videos[0] if len(videos) == 1 else {}
    audio = audios[0] if len(audios) == 1 else {}
    required_video = {
        "codec_name": "h264",
        "width": 3840,
        "height": 2160,
        "pix_fmt": "yuv420p",
        "avg_frame_rate": "30/1",
    }
    for key, expected in required_video.items():
        if video.get(key) != expected:
            errors.append(f"video {key} must be {expected!r}, got {video.get(key)!r}")
    if audio.get("codec_name") != "aac":
        errors.append(f"audio codec must be AAC, got {audio.get('codec_name')!r}")
    if str(audio.get("sample_rate", "")) != "48000":
        errors.append(f"audio sample rate must be 48000, got {audio.get('sample_rate')!r}")
    if int(audio.get("channels", 0) or 0) != 2:
        errors.append(f"audio must be stereo, got {audio.get('channels')!r} channels")
    try:
        duration = float((probe.get("format") or {}).get("duration"))
    except (TypeError, ValueError):
        duration = 0.0
        errors.append("container duration is missing")
    return errors, {
        "video": {
            key: video.get(key)
            for key in ("codec_name", "width", "height", "pix_fmt", "avg_frame_rate")
        },
        "audio": {
            key: audio.get(key)
            for key in ("codec_name", "sample_rate", "channels", "channel_layout")
        },
        "subtitle_stream_count": len(subtitles),
        "duration_seconds": duration,
    }


_SRT_TIME_RE = re.compile(
    r"^(?P<h>\d{2,}):(?P<m>\d{2}):(?P<s>\d{2}),(?P<ms>\d{3})$"
)


def _srt_seconds(value: str) -> float:
    match = _SRT_TIME_RE.fullmatch(value.strip())
    if match is None:
        raise ValueError(value)
    return (
        int(match.group("h")) * 3600
        + int(match.group("m")) * 60
        + int(match.group("s"))
        + int(match.group("ms")) / 1000
    )


def parse_publication_srt(path: Path) -> list[dict[str, Any]]:
    blocks = re.split(r"\r?\n\s*\r?\n", path.read_text(encoding="utf-8-sig").strip())
    cues: list[dict[str, Any]] = []
    for block in blocks:
        lines = [line.rstrip() for line in block.splitlines()]
        if not any(line.strip() for line in lines):
            continue
        if len(lines) < 3:
            raise PipelineError(f"malformed SRT block: {block[:120]!r}")
        try:
            index = int(lines[0].strip())
        except ValueError as exc:
            raise PipelineError(f"SRT index is not an integer: {lines[0]!r}") from exc
        timing = lines[1].split(" --> ")
        if len(timing) != 2:
            raise PipelineError(f"malformed SRT timing: {lines[1]!r}")
        try:
            start, end = map(_srt_seconds, timing)
        except ValueError as exc:
            raise PipelineError(f"malformed SRT timestamp: {lines[1]!r}") from exc
        cues.append(
            {
                "index": index,
                "start": start,
                "end": end,
                "lines": lines[2:],
                "text": "\n".join(lines[2:]).strip(),
            }
        )
    return cues


def validate_publication_srt(
    path: Path,
    *,
    duration: float,
) -> tuple[list[str], list[dict[str, Any]]]:
    errors: list[str] = []
    try:
        cues = parse_publication_srt(path)
    except PipelineError as exc:
        return [str(exc)], []
    if not cues:
        return ["publication SRT contains no cues"], []
    previous_end = -1.0
    for expected_index, cue in enumerate(cues, 1):
        if cue["index"] != expected_index:
            errors.append(
                f"SRT indices must be continuous: expected {expected_index}, got {cue['index']}"
            )
        if not cue["text"]:
            errors.append(f"SRT cue {expected_index} is empty")
        if cue["end"] <= cue["start"]:
            errors.append(f"SRT cue {expected_index} has nonpositive duration")
        if cue["start"] < previous_end - 0.001:
            errors.append(f"SRT cue {expected_index} overlaps the previous cue")
        if cue["end"] > duration + 0.04:
            errors.append(f"SRT cue {expected_index} exceeds final media duration")
        if len(cue["lines"]) > 2:
            errors.append(f"SRT cue {expected_index} exceeds two display lines")
        previous_end = cue["end"]
    joined = "".join(cue["text"] for cue in cues)
    for forbidden in SIGNOFF_TEXTS:
        if forbidden in joined:
            errors.append(f"publication SRT must omit spoken series sign-off: {forbidden}")
    for marker in ("```", "\\begin{", "\\end{", "pipeline", "review gate"):
        if marker in joined:
            errors.append(f"publication SRT contains production or source markup: {marker}")
    return errors, cues


def _decode_f32_mono(
    path: Path,
    *,
    start: float = 0.0,
    duration: float | None = None,
    sample_rate: int = 8000,
) -> array:
    command = ["ffmpeg", "-v", "error"]
    if start > 0:
        command.extend(["-ss", f"{start:.6f}"])
    command.extend(["-i", str(path)])
    if duration is not None:
        command.extend(["-t", f"{duration:.6f}"])
    command.extend(["-vn", "-ac", "1", "-ar", str(sample_rate), "-f", "f32le", "-"])
    payload = _run(command, binary=True)
    assert isinstance(payload, bytes)
    values = array("f")
    values.frombytes(payload)
    return values


def _rms(values: array, start: int, length: int) -> float:
    if length <= 0 or start < 0 or start + length > len(values):
        return 0.0
    return math.sqrt(sum(float(value) * float(value) for value in values[start : start + length]) / length)


def _pearson(left: array, right: array, offset: int = 0) -> float:
    left_start = max(0, -offset)
    right_start = max(0, offset)
    length = min(len(left) - left_start, len(right) - right_start)
    if length < 8000:
        return 0.0
    left_view = left[left_start : left_start + length]
    right_view = right[right_start : right_start + length]
    left_mean = sum(left_view) / length
    right_mean = sum(right_view) / length
    numerator = 0.0
    left_energy = 0.0
    right_energy = 0.0
    for x_value, y_value in zip(left_view, right_view):
        x_centered = float(x_value) - left_mean
        y_centered = float(y_value) - right_mean
        numerator += x_centered * y_centered
        left_energy += x_centered * x_centered
        right_energy += y_centered * y_centered
    denominator = math.sqrt(left_energy * right_energy)
    return numerator / denominator if denominator > 1e-12 else 0.0


def _time_shift(insertions: list[dict[str, Any]], reference_time: float) -> float:
    shift = 0.0
    for row in insertions:
        try:
            after = float(row["after_seconds"])
            duration = float(row["duration_seconds"])
        except (KeyError, TypeError, ValueError):
            continue
        if reference_time >= after:
            shift += duration
    return shift


def _window_crosses_insertion(
    insertions: list[dict[str, Any]],
    start: float,
    duration: float,
) -> bool:
    for row in insertions:
        try:
            after = float(row["after_seconds"])
        except (KeyError, TypeError, ValueError):
            continue
        if start - 0.25 <= after <= start + duration + 0.25:
            return True
    return False


def _select_voice_windows(
    reference: array,
    *,
    sample_rate: int,
    window_seconds: float,
    insertions: list[dict[str, Any]],
    count: int = 3,
) -> list[tuple[float, float]]:
    length = int(window_seconds * sample_rate)
    if len(reference) < length:
        return []
    candidates: list[tuple[float, float]] = []
    for start in range(0, len(reference) - length + 1, sample_rate):
        seconds = start / sample_rate
        if _window_crosses_insertion(insertions, seconds, window_seconds):
            continue
        candidates.append((_rms(reference, start, length), seconds))
    selected: list[tuple[float, float]] = []
    for energy, seconds in sorted(candidates, reverse=True):
        if energy < 0.002:
            continue
        if any(abs(seconds - prior_seconds) < window_seconds * 2 for _, prior_seconds in selected):
            continue
        selected.append((energy, seconds))
        if len(selected) >= count:
            break
    return selected


def verify_scene_voice_coverage(
    final_media: Path,
    scene_rows: list[dict[str, Any]],
    repo_root: Path,
    *,
    minimum_correlation: float = 0.30,
    sample_rate: int = 8000,
    window_seconds: float = 3.0,
) -> tuple[list[str], list[dict[str, Any]]]:
    errors: list[str] = []
    evidence: list[dict[str, Any]] = []
    for scene_index, row in enumerate(scene_rows, 1):
        scene_slug = str(row.get("scene_slug", "") or "").strip()
        if not scene_slug:
            errors.append(f"scene row {scene_index} lacks scene_slug")
            continue
        reference_binding = row.get("voice_reference")
        reference = _bound_file(
            reference_binding,
            repo_root,
            f"{scene_slug} voice_reference",
            errors,
        )
        try:
            global_start = float(row["global_start_seconds"])
            slot_duration = float(row["slot_duration_seconds"])
        except (KeyError, TypeError, ValueError):
            errors.append(f"{scene_slug} lacks numeric global_start_seconds/slot_duration_seconds")
            continue
        if reference is None:
            continue
        insertions = row.get("inserted_silences") or []
        if not isinstance(insertions, list):
            errors.append(f"{scene_slug} inserted_silences must be a list")
            insertions = []
        reference_pcm = _decode_f32_mono(reference, sample_rate=sample_rate)
        reference_duration = len(reference_pcm) / sample_rate
        expected_slot = reference_duration + sum(
            float(item.get("duration_seconds", 0.0) or 0.0)
            for item in insertions
            if isinstance(item, dict)
        )
        if abs(expected_slot - slot_duration) > 0.12:
            errors.append(
                f"{scene_slug} slot duration {slot_duration:.3f}s does not match "
                f"reference plus insertions {expected_slot:.3f}s"
            )
        selected = _select_voice_windows(
            reference_pcm,
            sample_rate=sample_rate,
            window_seconds=window_seconds,
            insertions=insertions,
        )
        if len(selected) < 2:
            errors.append(f"{scene_slug} has fewer than two usable high-energy voice windows")
            continue
        window_rows: list[dict[str, Any]] = []
        for energy, reference_start in selected:
            sample_start = int(reference_start * sample_rate)
            sample_length = int(window_seconds * sample_rate)
            source_window = reference_pcm[sample_start : sample_start + sample_length]
            final_start = global_start + reference_start + _time_shift(insertions, reference_start)
            search_padding = 0.12
            final_window = _decode_f32_mono(
                final_media,
                start=max(0.0, final_start - search_padding),
                duration=window_seconds + 2 * search_padding,
                sample_rate=sample_rate,
            )
            best_correlation = -1.0
            best_offset = 0
            max_shift = int(search_padding * sample_rate)
            for offset in range(0, 2 * max_shift + 1, max(1, int(0.01 * sample_rate))):
                candidate = final_window[offset : offset + sample_length]
                if len(candidate) < sample_length:
                    continue
                correlation = _pearson(source_window, candidate)
                if correlation > best_correlation:
                    best_correlation = correlation
                    best_offset = offset - max_shift
            passed = best_correlation >= minimum_correlation
            if not passed:
                errors.append(
                    f"{scene_slug} narration fingerprint missing at local "
                    f"{reference_start:.2f}s: correlation {best_correlation:.3f} "
                    f"< {minimum_correlation:.3f}"
                )
            window_rows.append(
                {
                    "reference_start_seconds": round(reference_start, 3),
                    "final_start_seconds": round(final_start, 3),
                    "reference_rms": round(energy, 6),
                    "best_correlation": round(best_correlation, 6),
                    "best_offset_seconds": round(best_offset / sample_rate, 4),
                    "pass": passed,
                }
            )
        evidence.append(
            {
                "scene_slug": scene_slug,
                "global_start_seconds": global_start,
                "slot_duration_seconds": slot_duration,
                "voice_reference": {
                    "path": _relative_or_absolute(reference, repo_root),
                    "sha256": _sha256(reference),
                },
                "windows": window_rows,
                "pass": all(item["pass"] for item in window_rows),
            }
        )
    return errors, evidence


def _frame_crop_difference(
    base_video: Path,
    final_video: Path,
    *,
    seconds: float,
) -> dict[str, float]:
    # Bottom 16 percent, downscaled for a deterministic and inexpensive pixel audit.
    filter_graph = (
        "[0:v]crop=iw:floor(ih*0.16):0:ih-floor(ih*0.16),scale=960:86:flags=area,format=gray[a];"
        "[1:v]crop=iw:floor(ih*0.16):0:ih-floor(ih*0.16),scale=960:86:flags=area,format=gray[b];"
        "[a][b]blend=all_mode=difference,format=gray[out]"
    )
    payload = _run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-ss",
            f"{seconds:.6f}",
            "-i",
            str(base_video),
            "-ss",
            f"{seconds:.6f}",
            "-i",
            str(final_video),
            "-filter_complex",
            filter_graph,
            "-map",
            "[out]",
            "-frames:v",
            "1",
            "-f",
            "rawvideo",
            "-",
        ],
        binary=True,
    )
    assert isinstance(payload, bytes)
    if not payload:
        raise PipelineError(f"could not decode subtitle comparison frame at {seconds:.3f}s")
    changed = sum(1 for value in payload if value >= 8)
    return {
        "changed_pixel_ratio": changed / len(payload),
        "mean_absolute_difference": sum(payload) / len(payload),
    }


def _distributed_cues(cues: list[dict[str, Any]], count: int = 12) -> list[dict[str, Any]]:
    if len(cues) <= count:
        return cues
    indices = sorted({round(index * (len(cues) - 1) / (count - 1)) for index in range(count)})
    return [cues[index] for index in indices]


def _noncue_times(cues: list[dict[str, Any]], duration: float, count: int = 8) -> list[float]:
    candidates: list[tuple[float, float]] = []
    previous = 0.0
    for cue in cues:
        gap = cue["start"] - previous
        if gap >= 0.8:
            candidates.append((gap, previous + gap / 2))
        previous = max(previous, cue["end"])
    if duration - previous >= 0.8:
        candidates.append((duration - previous, previous + (duration - previous) / 2))
    return [seconds for _, seconds in sorted(candidates, reverse=True)[:count]]


def verify_burned_subtitles(
    base_video: Path,
    final_video: Path,
    cues: list[dict[str, Any]],
    *,
    duration: float,
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    cue_rows: list[dict[str, Any]] = []
    for cue in _distributed_cues(cues):
        seconds = (cue["start"] + cue["end"]) / 2
        metrics = _frame_crop_difference(base_video, final_video, seconds=seconds)
        cue_rows.append({"cue_index": cue["index"], "seconds": round(seconds, 3), **metrics})
    noncue_rows = [
        {"seconds": round(seconds, 3), **_frame_crop_difference(base_video, final_video, seconds=seconds)}
        for seconds in _noncue_times(cues, duration)
    ]
    cue_ratios = [row["changed_pixel_ratio"] for row in cue_rows]
    noncue_ratios = [row["changed_pixel_ratio"] for row in noncue_rows]
    cue_median = statistics.median(cue_ratios) if cue_ratios else 0.0
    noncue_median = statistics.median(noncue_ratios) if noncue_ratios else 0.0
    # Re-encoding can introduce a small background delta.  Burn-in must add a
    # clear, repeated bottom-lane signal above that measured baseline.
    minimum = max(0.00005, noncue_median * 2.0 + 0.00002)
    if cue_median < minimum:
        errors.append(
            "publication subtitles are not proven in final pixels: "
            f"cue median {cue_median:.8f} < required {minimum:.8f}"
        )
    if sum(row["changed_pixel_ratio"] >= minimum for row in cue_rows) < max(1, len(cue_rows) - 1):
        errors.append("burned subtitle samples do not consistently differ from the subtitle-free base")
    return errors, {
        "base_video": str(base_video),
        "sampled_cues": cue_rows,
        "sampled_noncue_windows": noncue_rows,
        "cue_median_changed_pixel_ratio": cue_median,
        "noncue_median_changed_pixel_ratio": noncue_median,
        "required_changed_pixel_ratio": minimum,
        "pass": not errors,
    }


def _validate_proofread_audit(
    audit_path: Path,
    srt_path: Path,
    cue_count: int,
) -> list[str]:
    errors: list[str] = []
    audit = load_json(audit_path)
    if audit.get("schema") != "lecture-animation-publication-subtitle-audit-v1":
        errors.append("subtitle audit has unexpected schema")
    if audit.get("status") != "proofread_pass":
        errors.append("subtitle audit status must be proofread_pass")
    if audit.get("publication_srt_sha256") != _sha256(srt_path):
        errors.append("subtitle audit is not bound to the current publication SRT")
    if int(audit.get("cue_count", -1) or -1) != cue_count:
        errors.append("subtitle audit cue_count does not match publication SRT")
    reviewer = str(audit.get("proofreader", "") or "").strip()
    if not reviewer:
        errors.append("subtitle audit lacks a named proofreader")
    checks = audit.get("checks")
    required = {
        "timed_from_final_audio": True,
        "math_terms_proofread": True,
        "names_and_symbols_proofread": True,
        "reader_grouping_reviewed": True,
        "maximum_two_lines": True,
        "signoff_omitted": True,
    }
    if not isinstance(checks, dict):
        errors.append("subtitle audit checks are missing")
    else:
        for key, expected in required.items():
            if checks.get(key) is not expected:
                errors.append(f"subtitle audit check {key} must be true")
    return errors


def _validate_word_alignment(path: Path, duration: float) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    payload = load_json(path)
    tokens = payload.get("aligned_tokens") or payload.get("word_cues") or []
    if not isinstance(tokens, list) or not tokens:
        return ["final word alignment contains no tokens"], {}
    texts = "".join(str(row.get("text", "")) for row in tokens if isinstance(row, dict))
    for required in SIGNOFF_TEXTS:
        if required not in texts:
            errors.append(f"final word alignment lacks required spoken ending: {required}")
    ends: list[float] = []
    for row in tokens:
        if not isinstance(row, dict):
            continue
        try:
            ends.append(float(row.get("end")))
        except (TypeError, ValueError):
            continue
    if not ends or max(ends) > duration + 0.04:
        errors.append("final word alignment exceeds or does not bind final duration")
    return errors, {"token_count": len(tokens), "last_token_end": max(ends) if ends else None}


def _validate_scene_timeline(rows: list[dict[str, Any]], duration: float) -> list[str]:
    errors: list[str] = []
    if not rows:
        return ["upload package contains no scene voice rows"]
    expected_start = 0.0
    seen: set[str] = set()
    for index, row in enumerate(rows, 1):
        slug = str(row.get("scene_slug", "") or "")
        try:
            start = float(row["global_start_seconds"])
            slot = float(row["slot_duration_seconds"])
        except (KeyError, TypeError, ValueError):
            errors.append(f"scene row {index} has invalid timing")
            continue
        if slug in seen:
            errors.append(f"scene row {index} duplicates {slug}")
        seen.add(slug)
        if abs(start - expected_start) > 0.12:
            errors.append(
                f"scene {slug} starts at {start:.3f}s; contiguous timeline expects {expected_start:.3f}s"
            )
        if slot <= 0:
            errors.append(f"scene {slug} has nonpositive slot duration")
        expected_start = start + slot
    if abs(expected_start - duration) > 0.12:
        errors.append(
            f"scene timeline ends at {expected_start:.3f}s but final media ends at {duration:.3f}s"
        )
    return errors


def validate_upload_package_contract(
    contract_path: Path,
    repo_root: Path,
    episode: Path,
) -> dict[str, Any]:
    contract = load_json(contract_path)
    errors: list[str] = []
    if contract.get("schema") != UPLOAD_PACKAGE_SCHEMA:
        errors.append(f"contract schema must be {UPLOAD_PACKAGE_SCHEMA}")
    expected_episode = _relative_or_absolute(episode, repo_root)
    if contract.get("episode") != expected_episode:
        errors.append("upload package contract is bound to another episode")

    final_video = _bound_file(contract.get("final_video"), repo_root, "final_video", errors)
    final_audio = _bound_file(contract.get("final_audio"), repo_root, "final_audio", errors)
    final_srt = _bound_file(contract.get("publication_srt"), repo_root, "publication_srt", errors)
    base_video = _bound_file(
        contract.get("subtitle_free_video"), repo_root, "subtitle_free_video", errors
    )
    subtitle_audit = _bound_file(
        contract.get("subtitle_audit"), repo_root, "subtitle_audit", errors
    )
    word_alignment = _bound_file(
        contract.get("word_alignment"), repo_root, "word_alignment", errors
    )
    finalization_manifest = _bound_file(
        contract.get("finalization_manifest"), repo_root, "finalization_manifest", errors
    )
    bgm_source = _bound_file(contract.get("bgm_source"), repo_root, "bgm_source", errors)

    media_summary: dict[str, Any] = {}
    cues: list[dict[str, Any]] = []
    duration = 0.0
    if final_video is not None:
        probe = probe_media(final_video)
        spec_errors, media_summary = validate_upload_media_spec(probe)
        errors.extend(spec_errors)
        duration = float(media_summary.get("duration_seconds", 0.0) or 0.0)
        try:
            expected_duration = float(contract.get("expected_duration_seconds"))
        except (TypeError, ValueError):
            errors.append("expected_duration_seconds is missing or invalid")
            expected_duration = duration
        if abs(duration - expected_duration) > 0.12:
            errors.append(
                f"final duration {duration:.3f}s differs from sealed duration {expected_duration:.3f}s"
            )
    if final_audio is not None:
        audio_probe = probe_media(final_audio)
        try:
            audio_duration = float((audio_probe.get("format") or {}).get("duration"))
        except (TypeError, ValueError):
            audio_duration = 0.0
            errors.append("final audio duration is missing")
        if duration and abs(audio_duration - duration) > 0.12:
            errors.append(
                f"final audio duration {audio_duration:.3f}s differs from final video {duration:.3f}s"
            )
        media_summary["final_audio_duration_seconds"] = audio_duration

    if final_srt is not None and duration:
        srt_errors, cues = validate_publication_srt(final_srt, duration=duration)
        errors.extend(srt_errors)
    if subtitle_audit is not None and final_srt is not None:
        errors.extend(_validate_proofread_audit(subtitle_audit, final_srt, len(cues)))
    if word_alignment is not None and duration:
        alignment_errors, alignment_summary = _validate_word_alignment(word_alignment, duration)
        errors.extend(alignment_errors)
    else:
        alignment_summary = {}

    scene_rows = contract.get("scenes")
    if not isinstance(scene_rows, list):
        scene_rows = []
        errors.append("scenes must be a list")
    if duration:
        errors.extend(_validate_scene_timeline(scene_rows, duration))

    voice_evidence: list[dict[str, Any]] = []
    if final_video is not None and scene_rows:
        voice_errors, voice_evidence = verify_scene_voice_coverage(
            final_video,
            scene_rows,
            repo_root,
            minimum_correlation=float(contract.get("minimum_voice_correlation", 0.30)),
        )
        errors.extend(voice_errors)

    subtitle_burnin_summary: dict[str, Any] = {}
    if base_video is not None and final_video is not None and cues and duration:
        burn_errors, subtitle_burnin_summary = verify_burned_subtitles(
            base_video,
            final_video,
            cues,
            duration=duration,
        )
        errors.extend(burn_errors)

    bgm = contract.get("bgm")
    if not isinstance(bgm, dict):
        errors.append("bgm recipe binding is missing")
        bgm = {}
    required_recipe = {
        "base_volume": 4.8,
        "acompressor": "threshold=0.125:ratio=3:attack=20:release=400:makeup=2",
        "sidechaincompress": "threshold=0.025:ratio=8:attack=80:release=900",
        "loudnorm": "I=-17.0:TP=-1.5:LRA=11.0",
        "loop_when_short": True,
    }
    for key, expected in required_recipe.items():
        if bgm.get(key) != expected:
            errors.append(f"bgm recipe {key} must equal {expected!r}")
    if bgm_source is not None and bgm.get("source_sha256") != _sha256(bgm_source):
        errors.append("bgm recipe source_sha256 is stale")
    bgm_audit = _bound_file(contract.get("bgm_audit"), repo_root, "bgm_audit", errors)
    if bgm_audit is not None and final_video is not None:
        audit = load_json(bgm_audit)
        if audit.get("schema") != "lecture-animation-final-bgm-audit-v1":
            errors.append("BGM audit has unexpected schema")
        if audit.get("status") != "pass":
            errors.append("BGM audit status is not pass")
        if audit.get("final_video_sha256") != _sha256(final_video):
            errors.append("BGM audit is not bound to the current final video")
        if bgm_source is not None and audit.get("bgm_source_sha256") != _sha256(bgm_source):
            errors.append("BGM audit is not bound to the current BGM source")
        if int(audit.get("loop_count", 0) or 0) < 1:
            errors.append("BGM audit lacks a positive loop count")
        if duration > float(audit.get("single_loop_duration_seconds", 0.0) or 0.0) and int(
            audit.get("loop_count", 0) or 0
        ) < 2:
            errors.append("final duration exceeds one BGM play but audit does not prove looping")

    # Exact full-stream decode is intentionally repeated here.  A log from an
    # intermediate file is not accepted as evidence for the upload bytes.
    decode_summary: dict[str, Any] = {"video": False, "audio": False}
    if final_video is not None:
        try:
            _run(["ffmpeg", "-v", "error", "-i", str(final_video), "-map", "0:v:0", "-f", "null", "-"])
            decode_summary["video"] = True
        except PipelineError as exc:
            errors.append(f"full video decode failed: {exc}")
        try:
            _run(["ffmpeg", "-v", "error", "-i", str(final_video), "-map", "0:a:0", "-f", "null", "-"])
            decode_summary["audio"] = True
        except PipelineError as exc:
            errors.append(f"full audio decode failed: {exc}")

    delivery_root_raw = str(contract.get("delivery_root", "") or "").strip()
    review_root_raw = str(contract.get("review_root", "") or "").strip()
    for label, raw in (("delivery_root", delivery_root_raw), ("review_root", review_root_raw)):
        if not raw:
            errors.append(f"{label} is missing")
            continue
        root = _resolve(raw, repo_root)
        if not root.is_dir():
            errors.append(f"{label} does not exist: {root}")
            continue
        appledouble = [str(path) for path in root.rglob("._*")]
        if appledouble:
            errors.append(f"{label} contains AppleDouble files: {len(appledouble)}")

    if errors:
        raise PipelineError("upload package gate failed: " + " | ".join(errors))

    assert final_video is not None
    assert final_audio is not None
    assert final_srt is not None
    assert word_alignment is not None
    assert finalization_manifest is not None
    return {
        "schema": UPLOAD_RECEIPT_SCHEMA,
        "compiler": "pipeline_v2.seal-upload-package",
        "created_at": utc_now(),
        "episode": expected_episode,
        "contract": {
            "path": _relative_or_absolute(contract_path, repo_root),
            "sha256": _sha256(contract_path),
        },
        "final_video": {
            "path": _relative_or_absolute(final_video, repo_root),
            "sha256": _sha256(final_video),
        },
        "final_audio": {
            "path": _relative_or_absolute(final_audio, repo_root),
            "sha256": _sha256(final_audio),
        },
        "publication_srt": {
            "path": _relative_or_absolute(final_srt, repo_root),
            "sha256": _sha256(final_srt),
            "cue_count": len(cues),
        },
        "word_alignment": {
            "path": _relative_or_absolute(word_alignment, repo_root),
            "sha256": _sha256(word_alignment),
            **alignment_summary,
        },
        "finalization_manifest": {
            "path": _relative_or_absolute(finalization_manifest, repo_root),
            "sha256": _sha256(finalization_manifest),
        },
        "media_spec": media_summary,
        "scene_voice_coverage": voice_evidence,
        "subtitle_burn_in": subtitle_burnin_summary,
        "full_decode": decode_summary,
        "bgm_source_sha256": _sha256(bgm_source) if bgm_source is not None else None,
        "verdict": "pass",
    }


def command_seal_upload_package(args: Any) -> int:
    repo_root = Path(args.repo_root).resolve()
    episode = _resolve(str(args.episode), repo_root)
    contract_path = _resolve(str(args.contract), repo_root)
    receipt = validate_upload_package_contract(contract_path, repo_root, episode)
    receipt["receipt_hash"] = object_hash(receipt)
    output = _resolve(str(args.output), repo_root)
    write_json(output, receipt)
    print(
        json.dumps(
            {
                "upload_package_receipt": _relative_or_absolute(output, repo_root),
                "receipt_hash": receipt["receipt_hash"],
                "scene_count": len(receipt.get("scene_voice_coverage", [])),
                "subtitle_cue_count": receipt.get("publication_srt", {}).get("cue_count"),
                "verdict": "pass",
            },
            ensure_ascii=False,
        )
    )
    return 0


def validate_upload_package_receipt(
    receipt_path: Path,
    repo_root: Path,
    episode: Path,
    *,
    final_video: Path,
    final_audio: Path,
    final_srt: Path,
    final_word_alignment: Path,
    finalization_manifest: Path,
) -> dict[str, Any]:
    receipt = load_json(receipt_path)
    errors: list[str] = []
    if receipt.get("schema") != UPLOAD_RECEIPT_SCHEMA:
        errors.append("unexpected upload-package receipt schema")
    if receipt.get("compiler") != "pipeline_v2.seal-upload-package":
        errors.append("upload-package receipt was not produced by the canonical CLI")
    if receipt.get("verdict") != "pass":
        errors.append("upload-package receipt verdict is not pass")
    stored_hash = receipt.get("receipt_hash")
    unhashed = dict(receipt)
    unhashed.pop("receipt_hash", None)
    if stored_hash != object_hash(unhashed):
        errors.append("upload-package receipt hash is invalid")
    if receipt.get("episode") != _relative_or_absolute(episode, repo_root):
        errors.append("upload-package receipt is bound to another episode")
    contract_row = receipt.get("contract")
    contract_path: Path | None = None
    if not isinstance(contract_row, dict):
        errors.append("upload-package receipt lacks its sealed contract binding")
    else:
        contract_path = _resolve(str(contract_row.get("path", "")), repo_root)
        if not contract_path.is_file():
            errors.append("upload-package receipt contract path is stale")
        elif contract_row.get("sha256") != _sha256(contract_path):
            errors.append("upload-package receipt contract sha256 is stale")
    bindings = (
        ("final_video", final_video),
        ("final_audio", final_audio),
        ("publication_srt", final_srt),
        ("word_alignment", final_word_alignment),
        ("finalization_manifest", finalization_manifest),
    )
    for label, path in bindings:
        row = receipt.get(label)
        if not isinstance(row, dict):
            errors.append(f"upload-package receipt lacks {label}")
            continue
        if _resolve(str(row.get("path", "")), repo_root) != path.resolve():
            errors.append(f"upload-package receipt {label} path is stale")
        elif row.get("sha256") != _sha256(path):
            errors.append(f"upload-package receipt {label} sha256 is stale")
    if not errors and contract_path is not None:
        # A self-hash only detects accidental edits; it does not prove that the
        # canonical media gate actually ran. Re-run the bound contract against
        # the current bytes and require the receipt body to match that result.
        canonical = validate_upload_package_contract(contract_path, repo_root, episode)
        receipt_body = dict(receipt)
        receipt_body.pop("receipt_hash", None)
        receipt_body.pop("created_at", None)
        canonical_body = dict(canonical)
        canonical_body.pop("created_at", None)
        if receipt_body != canonical_body:
            errors.append(
                "upload-package receipt body does not match a fresh canonical seal"
            )
    if errors:
        raise PipelineError("upload-package receipt failed: " + " | ".join(errors))
    return receipt
