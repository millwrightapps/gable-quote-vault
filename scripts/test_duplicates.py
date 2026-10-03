import unittest
from quote_duplicates import is_repeat
from collect_podscripts import TranscriptParser, candidate
from import_transcript import candidates

class DuplicateTests(unittest.TestCase):
    def test_case_punctuation_and_apostrophes(self):
        self.assertTrue(is_repeat("It's a very strange idea!", ['“It’s a very strange idea.”']))
    def test_tiny_wording_change(self):
        self.assertTrue(is_repeat('Nobody expected the pencil argument to become an entire episode.', ['Nobody expected the pencil argument to become an entire episode!']))
    def test_different_moments_not_collapsed(self):
        self.assertFalse(is_repeat('Nobody expected the pencil argument to become an entire episode.', ['Nobody expected the next discussion to last for three hours.']))
    def test_collector_looks_past_repeat(self):
        p=TranscriptParser();p.title='Fixture [10]';p.segments=[('00:05:00','Nobody expected the pencil argument to become an entire episode. Another totally different conversation began about the mysterious missing sandwich.')]
        q=candidate(p,'https://podscripts.co/podcasts/regulation-podcast/test',['Nobody expected the pencil argument to become an entire episode.'])
        self.assertIn('sandwich',q['quote'])
    def test_import_deduplicates_within_transcript_and_against_catalog(self):
        line='Nobody expected the pencil argument to become an entire episode.'
        t=dict(youtubeVideoId='abcdefghijk',show='RP',episode=1,episodeTitle='Fixture',segments=[dict(start=200,text=line),dict(start=240,text=line)])
        self.assertEqual(1,len(candidates(t)))
        self.assertEqual([],candidates(t,[line]))
