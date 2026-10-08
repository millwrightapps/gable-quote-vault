import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from collect_youtube import COOLDOWN_SECONDS, STATE_PATH, collect

EPISODE = [{"id": "abcdefghijk", "title": "Episode [2]"}]


class YouTubeCollectionTests(unittest.TestCase):
    def root(self, directory):
        root = Path(directory)
        for folder in ("drafts", "quotes", "inbox", "quarantine"):
            (root / folder).mkdir()
        return root

    def state(self, root):
        return json.loads((root / STATE_PATH).read_text())

    def test_writes_youtube_timed_drafts_without_speakers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.root(directory)
            video = {"id": "abcdefghijk", "title": "A strange episode [12]"}
            segments = [{"text": "I refuse to trust a thermometer that needs its own weather forecast.", "start": 162.8, "duration": 4.0}]
            result = collect(lambda _: segments, root, fetch_videos_fn=lambda: [video], delay_seconds=0)
            self.assertEqual({"added": 1, "checked": 1}, result)
            saved = json.loads(next((root / "drafts").glob("*.json")).read_text())
            self.assertEqual("RP", saved["show"])
            self.assertEqual(12, saved["episode"])
            self.assertIsNone(saved["speaker"])
            self.assertEqual(162, saved["timestampSeconds"])
            self.assertEqual("https://www.youtube.com/watch?v=abcdefghijk&t=162s", saved["listenUrl"])
            self.assertEqual(["abcdefghijk"], self.state(root)["processed"])

    def test_unavailable_video_is_skipped_and_marked_processed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.root(directory)
            def missing(_):
                raise RuntimeError("ERROR: [youtube] abcdefghijk: Video unavailable")
            result = collect(missing, root, fetch_videos_fn=lambda: EPISODE, delay_seconds=0)
            self.assertEqual({"added": 0, "checked": 1}, result)
            self.assertEqual(["abcdefghijk"], self.state(root)["processed"])

    def test_transient_failure_is_retried_later(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.root(directory)
            def flaky(_):
                raise RuntimeError("Connection reset")
            collect(flaky, root, fetch_videos_fn=lambda: EPISODE, delay_seconds=0)
            self.assertEqual([], self.state(root)["processed"])

    def test_bot_check_sets_cooldown_without_consuming_video(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.root(directory)
            def blocked(_):
                raise RuntimeError("Sign in to confirm you're not a bot")
            result = collect(blocked, root, fetch_videos_fn=lambda: EPISODE, delay_seconds=0, now_fn=lambda: 1000)
            self.assertEqual(COOLDOWN_SECONDS, result["retryAfter"])
            self.assertEqual([], self.state(root)["processed"])
            self.assertEqual(1000 + COOLDOWN_SECONDS, self.state(root)["cooldownUntil"])

    def test_playlist_rate_limit_sets_cooldown(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.root(directory)
            def limited():
                raise RuntimeError("YouTube playlist request failed with HTTP 429")
            result = collect(Mock(), root, fetch_videos_fn=limited, delay_seconds=0, now_fn=lambda: 1000)
            self.assertEqual({"added": 0, "checked": 0, "retryAfter": COOLDOWN_SECONDS}, result)
            self.assertEqual(1000 + COOLDOWN_SECONDS, self.state(root)["cooldownUntil"])

    def test_cooldown_avoids_repeat_requests(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.root(directory)
            (root / STATE_PATH).write_text(json.dumps({"processed": [], "cooldownUntil": 2000}))
            fetch = Mock()
            result = collect(Mock(), root, fetch_videos_fn=fetch, now_fn=lambda: 1000)
            fetch.assert_not_called()
            self.assertEqual(1001, result["retryAfter"])

    def test_videos_without_episode_numbers_are_not_guessed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.root(directory)
            result = collect(lambda _: self.fail("must not transcribe an ambiguous episode"), root,
                             fetch_videos_fn=lambda: [{"id": "abcdefghijk", "title": "Special episode"}], delay_seconds=0)
            self.assertEqual({"added": 0, "checked": 0}, result)
            self.assertEqual(["abcdefghijk"], self.state(root)["processed"])


if __name__ == "__main__":
    unittest.main()
