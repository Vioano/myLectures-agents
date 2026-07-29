from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from animation_preflight_gate import check_component_package, check_timeline_and_assignment


class TimelineSchemaCompatibilityTest(unittest.TestCase):
    def test_accepts_coarse_timeline_scene_groups(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            episode_dir = repo_root / "videos" / "0007-test"
            episode_dir.mkdir(parents=True)
            (episode_dir / "timeline.json").write_text(
                json.dumps(
                    {
                        "schema": "lecture-animation-coarse-timeline-v2",
                        "scene_groups": [
                            {
                                "id": "G012",
                                "scene_slug": "g012_conjugate_failure_synthesis",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            errors = check_timeline_and_assignment(
                repo_root,
                episode_dir,
                "g012_conjugate_failure_synthesis",
                {"source": {"timeline_segments": ["G012"]}},
                require_per_scene_review=False,
            )

            self.assertEqual(errors, [])

    def test_still_rejects_unknown_scene_group(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            episode_dir = repo_root / "videos" / "0007-test"
            episode_dir.mkdir(parents=True)
            (episode_dir / "timeline.json").write_text(
                json.dumps({"scene_groups": [{"id": "G011"}]}),
                encoding="utf-8",
            )

            errors = check_timeline_and_assignment(
                repo_root,
                episode_dir,
                "g012_conjugate_failure_synthesis",
                {"source": {"timeline_segments": ["G012"]}},
                require_per_scene_review=False,
            )

            self.assertEqual(errors, ["timeline segment not found: G012"])


class ComponentPackageOwnershipTest(unittest.TestCase):
    def test_rejects_scene_class_hidden_behind_thin_composer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            episode_dir = repo_root / "videos" / "0007-test"
            scene_dir = episode_dir / "src" / "scenes" / "g007_test"
            scene_dir.mkdir(parents=True)
            for name in [
                "contract.yaml",
                "drivers.py",
                "objects.py",
                "layout.py",
                "beats.py",
                "audit.py",
            ]:
                (scene_dir / name).write_text("", encoding="utf-8")
            (scene_dir / "composer.py").write_text(
                "from scene import HiddenScene\n"
                "class CanonicalScene(HiddenScene):\n"
                "    pass\n",
                encoding="utf-8",
            )
            (scene_dir / "scene.py").write_text(
                "from manim import Scene\n"
                "class HiddenScene(Scene):\n"
                "    pass\n",
                encoding="utf-8",
            )

            errors = check_component_package(
                repo_root,
                episode_dir,
                "g007_test",
                {"scene_class": "CanonicalScene"},
                require_component_package=True,
            )

            self.assertTrue(
                any("defines Manim Scene classes outside composer.py" in error for error in errors)
            )


if __name__ == "__main__":
    unittest.main()
