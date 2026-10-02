import json
import unittest
from build_catalog import validate, build, ROOT

class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.q = dict(id='test_001', quote='Example fixture, not a podcast quotation.', speaker='GAVIN_FREE', show='RP', episode=1, episodeTitle='Test', youtubeVideoId='abcdefghijk', timestamp='01:02', timestampSeconds=62, listenUrl='https://www.youtube.com/watch?v=abcdefghijk&t=62s', weatherTags=['rain'])
        self.q['review'] = dict(status='verified', reviewer='Test fixture', checkedAt='2026-10-02', sourceUrl=self.q['listenUrl'], wordingChecked=True, speakersChecked=True, episodeChecked=True, timestampChecked=True, attributionPolicyChecked=True)
    def test_valid_fixture(self):
        validate(self.q, [])
    def test_unknown_speaker(self):
        self.q['speaker'] = 'UNKNOWN'
        with self.assertRaises(AssertionError): validate(self.q, [])
    def test_review_required(self):
        self.q['review']['speakersChecked'] = False
        with self.assertRaises(AssertionError): validate(self.q, [])
    def test_timestamp_mismatch(self):
        self.q['timestampSeconds'] = 90
        with self.assertRaises(AssertionError): validate(self.q, [])
    def test_retired_id(self):
        with self.assertRaises(AssertionError): validate(self.q, ['test_001'])
    def test_geoff_policy_includes_secondary_credit(self):
        self.q['secondarySpeaker'] = 'GEOFF_RAMSEY'
        self.q['quote'] = 'A cold beer.'
        with self.assertRaises(AssertionError): validate(self.q, [])
    def test_drafts_not_published(self):
        draft_ids = {json.loads(p.read_text())['id'] for p in (ROOT / 'drafts').glob('*.json')}
        self.assertTrue(draft_ids.isdisjoint(q['id'] for q in build()['quotes']))
