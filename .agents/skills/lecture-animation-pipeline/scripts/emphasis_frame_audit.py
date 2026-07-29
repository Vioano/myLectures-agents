#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image


def extract_frame(video: Path, timestamp: float, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-ss", f"{max(0.0, timestamp):.3f}", "-i", str(video),
            "-frames:v", "1", str(output),
        ],
        check=True,
    )


def coverage_map(path: Path) -> tuple[float, list[float]]:
    pixels = np.asarray(Image.open(path).convert("RGB"), dtype=np.int16)
    background = np.median(
        np.concatenate(
            [pixels[:8, :8], pixels[:8, -8:], pixels[-8:, :8], pixels[-8:, -8:]],
            axis=0,
        ).reshape(-1, 3),
        axis=0,
    )
    distance = np.max(np.abs(pixels - background), axis=2)
    mask = distance > 18
    rows = np.array_split(mask, 3, axis=0)
    tiles = [float(np.mean(tile)) for row in rows for tile in np.array_split(row, 4, axis=1)]
    return float(np.mean(mask)), tiles


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True)
    parser.add_argument("--telemetry", required=True)
    parser.add_argument("--frames-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    video = Path(args.video)
    telemetry = json.loads(Path(args.telemetry).read_text(encoding="utf-8"))
    frames_dir = Path(args.frames_dir)
    results = []
    issues = []
    for index, event in enumerate(telemetry.get("emphasis_events", []), start=1):
        if event.get("mode") != "scale_then_restore":
            continue
        cue_id = str(event.get("cue_id", f"cue_{index}"))
        start = float(event["start_time"])
        peak = float(event["peak_time"])
        hold = (float(event["peak_time"]) + float(event["hold_end_time"])) / 2
        recovered = float(event["end_time"]) + 0.06
        times = {
            "rest": max(0.0, start - 0.06),
            "peak": peak,
            "hold": hold,
            "recovered": recovered,
        }
        coverages = {}
        tile_coverages = {}
        frame_paths = {}
        for phase, timestamp in times.items():
            frame = frames_dir / f"{index:02d}_{cue_id}_{phase}_{timestamp:07.3f}.png"
            extract_frame(video, timestamp, frame)
            frame_paths[phase] = frame.as_posix()
            coverages[phase], tile_coverages[phase] = coverage_map(frame)
        baseline = max(coverages["rest"], 1e-6)
        ratios = {phase: value / baseline for phase, value in coverages.items()}
        cue_issues = []
        for phase in ("peak", "hold"):
            if ratios[phase] < 0.60:
                cue_issues.append(f"{phase} frame retains only {ratios[phase]:.2f} of rest-state visible coverage")
            for tile_index, rest_tile in enumerate(tile_coverages["rest"]):
                if rest_tile < 0.002:
                    continue
                tile_ratio = tile_coverages[phase][tile_index] / rest_tile
                if tile_ratio < 0.45:
                    cue_issues.append(
                        f"{phase} frame tile {tile_index} retains only {tile_ratio:.2f} of its rest-state visual content"
                    )
        if ratios["recovered"] < 0.78:
            cue_issues.append(f"recovered frame retains only {ratios['recovered']:.2f} of rest-state visible coverage")
        for message in cue_issues:
            issues.append({"cue_id": cue_id, "code": "EMPHASIS_FRAME_COLLAPSE", "message": message})
        results.append(
            {
                "cue_id": cue_id,
                "times": times,
                "frames": frame_paths,
                "visible_coverage": coverages,
                "tile_coverage": tile_coverages,
                "coverage_ratio_to_rest": ratios,
                "valid": not cue_issues,
            }
        )

    report = {
        "schema": "lecture-animation-emphasis-frame-audit-v2",
        "scene_slug": telemetry.get("scene_slug"),
        "video": video.as_posix(),
        "telemetry": Path(args.telemetry).as_posix(),
        "valid": not issues and bool(results),
        "events": results,
        "issues": issues,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": output.as_posix(), "valid": report["valid"], "issues": len(issues)}))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
