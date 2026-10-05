import json
from pathlib import Path
import tempfile
import unittest
from discover_episodes import discover, parse_feed
from import_transcript import candidates

FEED = b'<rss><channel><title>Regulation Podcast</title><item><guid>one</guid><title>Episode</title></item></channel></rss>'
class DiscoveryTests(unittest.TestCase):
    def test_idempotent_and_keeps_history(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'episodes.json'
            self.assertEqual(1, discover(FEED, path))
            self.assertEqual(0, discover(FEED, path))
            self.assertEqual(0, discover(FEED.replace(b'<item><guid>one</guid><title>Episode</title></item>', b''), path))
            self.assertEqual(1, len(json.loads(path.read_text())))
    def test_wrong_show_rejected(self):
        with self.assertRaises(ValueError): parse_feed(FEED.replace(b'Regulation Podcast', b'Other'))
    def test_no_speaker_guesses(self):
        transcript = dict(youtubeVideoId='abcdefghijk', show='RP', episode=1, episodeTitle='Fixture', segments=[dict(start=62.8, text='I refuse to trust a thermometer that needs its own weather forecast.')])
        result = candidates(transcript)
        self.assertEqual(1, len(result))
        self.assertIsNone(result[0]['speaker'])
        self.assertEqual('draft', result[0]['review']['status'])
        self.assertEqual(62, result[0]['timestampSeconds'])
        self.assertEqual(result, candidates(transcript))
    def test_general_transcript_moments_are_collected(self):
        result = candidates(dict(youtubeVideoId='abcdefghijk', show='RP', episode=1, episodeTitle='Fixture', segments=[dict(start=62, text='Nobody expected the pencil argument to become an entire episode.')]))
        self.assertEqual(1, len(result))
        self.assertEqual(['random'], result[0]['weatherTags'])
        self.assertIsNone(result[0]['speaker'])

    def test_caption_fragments_join_until_a_real_sentence_ending(self):
        transcript = dict(
            youtubeVideoId='abcdefghijk', show='RP', episode=1, episodeTitle='Fixture',
            segments=[
                dict(start=62, duration=2, text='I would set my alarm for 5:00 a.m.'),
                dict(start=64, duration=2, text='because the show started before sunrise.'),
            ],
        )
        result = candidates(transcript)
        self.assertEqual(1, len(result))
        self.assertEqual(
            'I would set my alarm for 5:00 a.m. because the show started before sunrise.',
            result[0]['quote'],
        )
        self.assertEqual(62, result[0]['timestampSeconds'])

    def test_time_abbreviations_do_not_turn_fragments_into_quotes(self):
        transcript = dict(
            youtubeVideoId='abcdefghijk', show='RP', episode=1, episodeTitle='Fixture',
            segments=[
                dict(start=62, duration=2, text='months but I would wake up at 5:00 a.m.'),
                dict(start=65, duration=2, text='always you guys 10: a.m. show up 8: a.m.'),
            ],
        )
        self.assertEqual([], candidates(transcript))

    def test_host_introductions_are_not_candidates(self):
        result = candidates(dict(youtubeVideoId='abcdefghijk', show='RP', episode=1, episodeTitle='Fixture', segments=[dict(start=0, text='Hello and welcome to another episode of the Regulation Podcast.')]))
        self.assertEqual([], result)

    def test_reject_negative_time(self):
        with self.assertRaises(ValueError):
            candidates(dict(youtubeVideoId='abcdefghijk', show='RP', episode=1, episodeTitle='Fixture', segments=[dict(start=-1, text='I refuse to trust a thermometer that needs its own weather forecast.')]))
