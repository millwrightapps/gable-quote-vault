import unittest
from quote_duplicates import is_repeat
from transcript_fixture import transcript
from import_transcript import candidates

class DuplicateTests(unittest.TestCase):
    def test_case_punctuation_and_apostrophes(self):
        self.assertTrue(is_repeat("It's a very strange idea!", ['“It’s a very strange idea.”']))
    def test_tiny_wording_change(self):
        self.assertTrue(is_repeat('Nobody expected the pencil argument to become an entire episode.', ['Nobody expected the pencil argument to become an entire episode!']))
    def test_different_moments_not_collapsed(self):
        self.assertFalse(is_repeat('Nobody expected the pencil argument to become an entire episode.', ['Nobody expected the next discussion to last for three hours.']))
    def test_collector_looks_past_repeat(self):
        known='Nobody expected the pencil argument to become an entire episode.'
        quotes=[q['quote'] for q in candidates(transcript((300,known),(400,'I refuse to accept responsibility for the mysterious missing sandwich.')),[known])]
        self.assertEqual(['I refuse to accept responsibility for the mysterious missing sandwich.'],quotes)
    def test_import_deduplicates_within_transcript_and_against_catalog(self):
        line='Nobody expected the pencil argument to become an entire episode.'
        t=dict(youtubeVideoId='abcdefghijk',show='RP',episode=1,episodeTitle='Fixture',segments=[dict(start=200,text=line),dict(start=240,text=line)])
        self.assertEqual(1,len(candidates(t)))
        self.assertEqual([],candidates(t,[line]))
