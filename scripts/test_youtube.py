import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from collect_youtube import COOLDOWN_SECONDS, collect, fetch_transcript


class IpBlocked(Exception):
    pass


class NoTranscriptFound(Exception):
    pass


class YouTubeCollectionTests(unittest.TestCase):
    def root(self, directory):
        root = Path(directory)
        for folder in ("drafts", "quotes", "inbox", "quarantine"):
            (root / folder).mkdir()
        return root

    def test_current_transcript_api_shape_is_converted_to_segments(self):
        class Fetched:
            def to_raw_data(self):
                return [{"text": "I refuse to trust a thermometer.", "start": 12.5, "duration": 2.0}]

        class Api:
            def fetch(self, video_id, languages):
                self.video_id = video_id
                self.languages = languages
                return Fetched()

        fake_module = types.SimpleNamespace(YouTubeTranscriptApi=Api)
        with patch.dict(sys.modules, {"youtube_transcript_api": fake_module}):
            segments = fetch_transcript("abcdefghijk")
        self.assertEqual([{"text": "I refuse to trust a thermometer.", "start": 12.5, "duration": 2.0}], segments)

    def test_refresh_writes_youtube_drafts_without_speakers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.root(directory)
            video = {"id": "abcdefghijk", "title": "A strange episode [12]"}
            segments = [{"text": "I refuse to trust a thermometer that needs its own weather forecast.", "start": 62.8, "duration": 4.0}]
            result = collect(root, fetch_videos_fn=lambda: [video], fetch_transcript_fn=lambda _: segments,
                             delay_seconds=0)
            self.assertEqual({"added": 1, "checked": 1}, result)
            saved = json.loads(next((root / "drafts").glob("*.json")).read_text())
            self.assertEqual("RP", saved["show"])
            self.assertEqual(12, saved["episode"])
            self.assertIsNone(saved["speaker"])
            self.assertEqual(62, saved["timestampSeconds"])
            self.assertEqual("https://www.youtube.com/watch?v=abcdefghijk&t=62s", saved["listenUrl"])
            self.assertEqual(["abcdefghijk"], json.loads((root / "inbox/youtube_processed.json").read_text())["processed"])

    def test_missing_captions_are_skipped_and_marked_processed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.root(directory)
            def missing(_):
                raise NoTranscriptFound()
            result = collect(root, fetch_videos_fn=lambda: [{"id": "abcdefghijk", "title": "Episode [2]"}],
                             fetch_transcript_fn=missing, delay_seconds=0)
            self.assertEqual({"added": 0, "checked": 1}, result)
            self.assertEqual(["abcdefghijk"], json.loads((root / "inbox/youtube_processed.json").read_text())["processed"])

    def test_ip_block_sets_cooldown_without_consuming_video(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.root(directory)
            def blocked(_):
                raise IpBlocked("YouTube blocked this IP")
            result = collect(root, fetch_videos_fn=lambda: [{"id": "abcdefghijk", "title": "Episode [2]"}],
                             fetch_transcript_fn=blocked, delay_seconds=0, now_fn=lambda: 1000)
            self.assertEqual(COOLDOWN_SECONDS, result["retryAfter"])
            state = json.loads((root / "inbox/youtube_processed.json").read_text())
            self.assertEqual([], state["processed"])
            self.assertEqual(1000 + COOLDOWN_SECONDS, state["cooldownUntil"])

    def test_playlist_rate_limit_sets_cooldown(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.root(directory)
            def limited():
                raise RuntimeError("YouTube playlist request failed with HTTP 429")
            result = collect(root, fetch_videos_fn=limited, delay_seconds=0, now_fn=lambda: 1000)
            self.assertEqual({"added": 0, "checked": 0, "retryAfter": COOLDOWN_SECONDS}, result)
            state = json.loads((root / "inbox/youtube_processed.json").read_text())
            self.assertEqual([], state["processed"])
            self.assertEqual(1000 + COOLDOWN_SECONDS, state["cooldownUntil"])

    def test_cooldown_avoids_repeat_requests(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.root(directory)
            (root / "inbox/youtube_processed.json").write_text(json.dumps({"processed": [], "cooldownUntil": 2000}))
            fetch = Mock()
            result = collect(root, fetch_videos_fn=fetch, now_fn=lambda: 1000)
            fetch.assert_not_called()
            self.assertEqual(1001, result["retryAfter"])

    def test_videos_without_episode_numbers_are_not_guessed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.root(directory)
            result = collect(root, fetch_videos_fn=lambda: [{"id": "abcdefghijk", "title": "Special episode"}],
                             fetch_transcript_fn=lambda _: self.fail("must not fetch ambiguous episode"),
                             delay_seconds=0)
            self.assertEqual({"added": 0, "checked": 0}, result)
            self.assertEqual(["abcdefghijk"], json.loads((root / "inbox/youtube_processed.json").read_text())["processed"])


if __name__ == "__main__":
    unittest.main()
