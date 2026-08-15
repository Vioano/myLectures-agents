from __future__ import annotations

import hashlib
import math
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock
import wave

from pipeline_v2_lib.core import PipelineError, object_hash
from pipeline_v2_lib.final_media import (
    parse_publication_srt,
    validate_publication_srt,
    validate_upload_media_spec,
    validate_upload_package_receipt,
    verify_scene_voice_coverage,
)
from pipeline_v2_lib.storage import write_json


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_tone(path: Path, frequencies: list[float], seconds_each: float = 18.0) -> None:
    rate = 8000
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        for frequency in frequencies:
            for index in range(round(rate * seconds_each)):
                # Amplitude modulation avoids a degenerate constant-energy fixture.
                seconds = index / rate
                sample = 0.45 * math.sin(2 * math.pi * frequency * seconds)
                sample *= 0.55 + 0.45 * math.sin(2 * math.pi * 2.1 * seconds) ** 2
                handle.writeframesraw(struct.pack("<h", round(sample * 32767)))


class FinalMediaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.episode = self.root / "videos" / "0011-test"
        self.episode.mkdir(parents=True)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_publication_srt_is_reader_copy_not_spoken_signoff_dump(self) -> None:
        valid = self.root / "valid.srt"
        valid.write_text(
            "1\n00:00:00,000 --> 00:00:01,500\n柯西积分公式\n\n"
            "2\n00:00:02,000 --> 00:00:03,000\n边界决定内部\n",
            encoding="utf-8",
        )
        errors, cues = validate_publication_srt(valid, duration=4.0)
        self.assertEqual(errors, [])
        self.assertEqual(len(cues), 2)
        self.assertEqual(parse_publication_srt(valid)[0]["text"], "柯西积分公式")

        invalid = self.root / "invalid.srt"
        invalid.write_text(
            "1\n00:00:00,000 --> 00:00:01,500\n我是结束乐队的键盘手\n下个视频见\n第三行\n",
            encoding="utf-8",
        )
        errors, _ = validate_publication_srt(invalid, duration=4.0)
        self.assertTrue(any("two display lines" in row for row in errors))
        self.assertTrue(any("spoken series sign-off" in row for row in errors))

    def test_upload_media_spec_rejects_missing_audio_and_wrong_resolution(self) -> None:
        errors, _ = validate_upload_media_spec(
            {
                "streams": [
                    {
                        "codec_type": "video",
                        "codec_name": "h264",
                        "width": 1920,
                        "height": 1080,
                        "pix_fmt": "yuv420p",
                        "avg_frame_rate": "30/1",
                    }
                ],
                "format": {"duration": "10.0"},
            }
        )
        self.assertTrue(any("exactly one audio" in row for row in errors))
        self.assertTrue(any("width" in row for row in errors))

    def test_scene_voice_fingerprint_detects_one_scene_padded_with_silence(self) -> None:
        first = self.root / "g001.wav"
        second = self.root / "g002.wav"
        good = self.root / "good.wav"
        missing = self.root / "missing.wav"
        write_tone(first, [330.0])
        write_tone(second, [550.0])
        write_tone(good, [330.0, 550.0])
        write_tone(missing, [330.0, 0.0])
        scenes = [
            {
                "scene_slug": "G001",
                "global_start_seconds": 0.0,
                "slot_duration_seconds": 18.0,
                "voice_reference": {"path": str(first), "sha256": sha256(first)},
            },
            {
                "scene_slug": "G002",
                "global_start_seconds": 18.0,
                "slot_duration_seconds": 18.0,
                "voice_reference": {"path": str(second), "sha256": sha256(second)},
            },
        ]
        good_errors, good_evidence = verify_scene_voice_coverage(good, scenes, self.root)
        self.assertEqual(good_errors, [])
        self.assertTrue(all(row["pass"] for row in good_evidence))

        missing_errors, missing_evidence = verify_scene_voice_coverage(
            missing, scenes, self.root
        )
        self.assertTrue(any("G002 narration fingerprint missing" in row for row in missing_errors))
        self.assertFalse(missing_evidence[1]["pass"])

    def test_finalize_receipt_rejects_changed_final_bytes(self) -> None:
        artifacts: dict[str, Path] = {}
        for name in (
            "final_video",
            "final_audio",
            "publication_srt",
            "word_alignment",
            "finalization_manifest",
        ):
            path = self.root / name
            path.write_text(name, encoding="utf-8")
            artifacts[name] = path
        contract = self.root / "upload_contract.json"
        contract.write_text("{}\n", encoding="utf-8")
        receipt = {
            "schema": "lecture-animation-upload-package-receipt-v1",
            "compiler": "pipeline_v2.seal-upload-package",
            "episode": str(self.episode.relative_to(self.root)),
            "verdict": "pass",
            "contract": {"path": str(contract), "sha256": sha256(contract)},
            **{
                name: {"path": str(path), "sha256": sha256(path)}
                for name, path in artifacts.items()
            },
        }
        receipt["receipt_hash"] = object_hash(receipt)
        receipt_path = self.root / "receipt.json"
        write_json(receipt_path, receipt)
        canonical = dict(receipt)
        canonical.pop("receipt_hash")
        with mock.patch(
            "pipeline_v2_lib.final_media.validate_upload_package_contract",
            return_value=canonical,
        ):
            validate_upload_package_receipt(
                receipt_path,
                self.root,
                self.episode,
                final_video=artifacts["final_video"],
                final_audio=artifacts["final_audio"],
                final_srt=artifacts["publication_srt"],
                final_word_alignment=artifacts["word_alignment"],
                finalization_manifest=artifacts["finalization_manifest"],
            )
        artifacts["final_video"].write_text("changed", encoding="utf-8")
        with self.assertRaises(PipelineError):
            validate_upload_package_receipt(
                receipt_path,
                self.root,
                self.episode,
                final_video=artifacts["final_video"],
                final_audio=artifacts["final_audio"],
                final_srt=artifacts["publication_srt"],
                final_word_alignment=artifacts["word_alignment"],
                finalization_manifest=artifacts["finalization_manifest"],
            )

    def test_finalize_receipt_rejects_handwritten_minimal_self_hash(self) -> None:
        artifacts: dict[str, Path] = {}
        for name in (
            "final_video",
            "final_audio",
            "publication_srt",
            "word_alignment",
            "finalization_manifest",
        ):
            path = self.root / f"minimal-{name}"
            path.write_text(name, encoding="utf-8")
            artifacts[name] = path
        receipt = {
            "schema": "lecture-animation-upload-package-receipt-v1",
            "compiler": "pipeline_v2.seal-upload-package",
            "episode": str(self.episode.relative_to(self.root)),
            "verdict": "pass",
            **{
                name: {"path": str(path), "sha256": sha256(path)}
                for name, path in artifacts.items()
            },
        }
        receipt["receipt_hash"] = object_hash(receipt)
        receipt_path = self.root / "handwritten-minimal-receipt.json"
        write_json(receipt_path, receipt)
        with self.assertRaisesRegex(PipelineError, "sealed contract binding"):
            validate_upload_package_receipt(
                receipt_path,
                self.root,
                self.episode,
                final_video=artifacts["final_video"],
                final_audio=artifacts["final_audio"],
                final_srt=artifacts["publication_srt"],
                final_word_alignment=artifacts["word_alignment"],
                finalization_manifest=artifacts["finalization_manifest"],
            )


if __name__ == "__main__":
    unittest.main()
