from __future__ import annotations

from http.client import HTTPConnection
from pathlib import Path
import threading

from supervision.core import DomainError
from supervision.http_server import SupervisionHTTPServer

from .helpers import ServiceCase


class MediaReviewTests(ServiceCase):
    def setUp(self) -> None:
        super().setUp()
        self.media = self.repo / "review.mp4"
        self.media.write_bytes(b"0123456789abcdefghijklmnopqrstuvwxyz")
        self.add_task(
            "T-MEDIA",
            required_artifact_roles=["review_video"],
        )
        begun = self.service.begin(
            "EP", "T-MEDIA", actor="Ada", request_id="begin-media"
        )
        self.assertTrue(begun["ok"], begun)
        submitted = self.service.submit(
            "EP",
            "T-MEDIA",
            actor="Ada",
            artifacts=[{"role": "review_video", "path": "review.mp4"}],
            request_id="submit-media",
        )
        self.assertTrue(submitted["ok"], submitted)
        self.artifact_state = next(
            item
            for item in self.service.overview("EP")["artifacts"]
            if item["producer_task_id"] == "T-MEDIA"
        )

    def test_multiple_artifact_roles_produce_a_valid_default_work_key(self):
        added = self.add_task(
            "T-MULTI-OUTPUT",
            required_artifact_roles=["narration_audio", "review_video"],
        )
        self.assertEqual(
            added["task"]["work_key"],
            "work:T-MULTI-OUTPUT:narration_audio.review_video:production",
        )

    def test_media_annotation_binds_exact_time_position_and_batches_atomically(self):
        artifact_id = self.artifact_state["artifact_id"]
        first = self.service.annotate(
            "EP",
            actor="human-ui",
            target_id=artifact_id,
            body="Formula overlaps the curve.",
            severity="warning",
            location={
                "kind": "media",
                "artifact_id": artifact_id,
                "time_seconds": 12.3456,
                "timecode": "00:12.346",
                "position": {"x": 0.25, "y": 0.75},
            },
            request_id="annotate-media",
        )
        annotation = first["annotation"]
        self.assertEqual(annotation["target_kind"], "artifact")
        self.assertEqual(annotation["location"]["time_seconds"], 12.346)
        self.assertEqual(annotation["location"]["position"], {"x": 0.25, "y": 0.75})

        descriptors = [
            {
                "target_id": artifact_id,
                "body": "Audio click at the cut.",
                "severity": "note",
                "location": {
                    "artifact_id": artifact_id,
                    "time_seconds": 18,
                    "timecode": "00:18.000",
                },
            },
            {
                "target_id": artifact_id,
                "body": "Subtitle is late.",
                "severity": "blocker",
                "location": {
                    "artifact_id": artifact_id,
                    "time_seconds": 21.5,
                    "timecode": "00:21.500",
                },
            },
        ]
        batch = self.service.annotate_batch(
            "EP",
            actor="human-ui",
            annotations=descriptors,
            request_id="batch-media",
        )
        self.assertEqual(batch["created_count"], 2)
        replay = self.service.annotate_batch(
            "EP",
            actor="human-ui",
            annotations=descriptors,
            request_id="batch-media",
        )
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(len(self.service.overview("EP")["annotations"]), 3)

        before = len(self.service.overview("EP")["annotations"])
        rejected = self.service.annotate_batch(
            "EP",
            actor="human-ui",
            annotations=[
                descriptors[0],
                {
                    "target_id": "art_missing",
                    "body": "This target does not exist.",
                    "severity": "note",
                    "location": {
                        "artifact_id": "art_missing",
                        "time_seconds": 1,
                    },
                },
            ],
            request_id="batch-media-atomic-reject",
        )
        self.assertFalse(rejected["ok"])
        self.assertEqual(len(self.service.overview("EP")["annotations"]), before)

    def test_media_annotation_rejects_invalid_or_non_artifact_locations(self):
        artifact_id = self.artifact_state["artifact_id"]
        with self.assertRaises(DomainError):
            self.service.annotate(
                "EP",
                actor="human-ui",
                target_id=artifact_id,
                body="Outside the image.",
                location={
                    "artifact_id": artifact_id,
                    "time_seconds": 3,
                    "position": {"x": 1.2, "y": 0.4},
                },
            )
        wrong_target = self.service.annotate(
            "EP",
            actor="human-ui",
            target_id="T-MEDIA",
            body="This must bind to the artifact, not merely its task.",
            location={"artifact_id": "T-MEDIA", "time_seconds": 3},
        )
        self.assertFalse(wrong_target["ok"])
        self.assertEqual(wrong_target["code"], "invalid_annotation_location")

    def test_live_annotation_waits_for_heartbeat_attention_boundary(self):
        self.add_task("T-LIVE-NOTE")
        begun = self.service.begin(
            "EP", "T-LIVE-NOTE", actor="Ada", request_id="live-note-begin"
        )
        self.assertTrue(begun["ok"], begun)
        old_capsule_hash = begun["capsule"]["capsule_hash"]

        noted = self.service.annotate(
            "EP",
            actor="human-ui",
            target_id="T-LIVE-NOTE",
            body="Keep the equation visible for one more beat.",
            severity="warning",
            request_id="live-note-add",
        )
        self.assertTrue(noted["ok"], noted)
        self.assertEqual(noted["annotation"]["delivery_policy"], "attention_boundary")
        self.assertEqual(noted["annotation"]["delivery_state"], "pending_next_heartbeat")
        store = self.data_root.episode_store("EP")
        lease, _ = store.get("lease", "lease:T-LIVE-NOTE")
        task, _ = store.get("task", "T-LIVE-NOTE")
        self.assertEqual(lease["status"], "active")
        self.assertIn(
            noted["annotation"]["annotation_id"],
            task["pending_context_update"]["annotation_ids"],
        )
        scheduled = next(
            event
            for event in store.events_after()
            if event["event_type"] == "TaskAnnotationAttentionScheduled"
        )
        self.assertFalse(scheduled["payload"]["interrupt_active_lease"])

        heartbeat = self.service.heartbeat(
            "EP",
            "T-LIVE-NOTE",
            actor="Ada",
            request_id="live-note-heartbeat",
        )
        self.assertTrue(heartbeat["ok"], heartbeat)
        self.assertNotEqual(
            heartbeat["context_update"]["capsule_hash"], old_capsule_hash
        )
        payload = heartbeat["context_update"]["payload"]
        self.assertIn("Keep the equation visible", payload["assembled_prompt"])
        self.assertEqual(
            payload["why_now"]["human_annotation_delivery"]["boundary"],
            "heartbeat_attention_boundary",
        )
        self.assertEqual(payload["context_manifest"]["annotation_count"], 1)

    def test_http_media_endpoint_streams_byte_ranges_and_head(self):
        static_root = Path(__file__).resolve().parents[1] / "static"
        server = SupervisionHTTPServer(("127.0.0.1", 0), self.service, static_root)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address
        path = (
            f"/api/episodes/EP/artifacts/"
            f"{self.artifact_state['artifact_id']}/media"
        )
        try:
            connection = HTTPConnection(host, port, timeout=3)
            connection.request("GET", path, headers={"Range": "bytes=2-5"})
            ranged = connection.getresponse()
            self.assertEqual(ranged.status, 206)
            self.assertEqual(ranged.read(), b"2345")
            self.assertEqual(ranged.getheader("Content-Range"), "bytes 2-5/36")
            self.assertEqual(ranged.getheader("Accept-Ranges"), "bytes")
            self.assertEqual(ranged.getheader("Content-Type"), "video/mp4")

            connection.request("HEAD", path)
            head = connection.getresponse()
            self.assertEqual(head.status, 200)
            self.assertEqual(head.getheader("Content-Length"), "36")
            self.assertEqual(head.read(), b"")

            connection.request("GET", path, headers={"Range": "bytes=90-100"})
            invalid = connection.getresponse()
            self.assertEqual(invalid.status, 416)
            self.assertEqual(invalid.getheader("Content-Range"), "bytes */36")
            self.assertEqual(invalid.read(), b"")

            connection.request("GET", path)
            full = connection.getresponse()
            self.assertEqual(full.status, 200)
            self.assertEqual(full.read(), self.media.read_bytes())
            connection.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
