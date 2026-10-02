import unittest
from unittest.mock import patch
from review_server import prepare, suggestion, publish
from build_catalog import validate

class ReviewTests(unittest.TestCase):
    def draft(self):
        return dict(id='test_review', quote='Synthetic weather example.', speaker='GAVIN_FREE', show='RP', episode=1, episodeTitle='Fixture')
    def edits(self):
        return {**self.draft(), 'youtubeVideoId':'abcdefghijk','timestampSeconds':123,'weatherTags':['rain'],'confirmed':True}
    def test_unverified_credit_not_used_as_suggestion(self):
        s = suggestion(self.draft(), [])
        self.assertIsNone(s['speaker'])
        self.assertIsNone(s['score'])
    def test_exact_match_requires_same_episode(self):
        approved = self.draft()
        self.assertEqual(100, suggestion(self.draft(), [approved])['score'])
        approved['episode'] = 2
        self.assertIsNone(suggestion(self.draft(), [approved])['score'])
    def test_disagreeing_verified_credits_do_not_suggest(self):
        a, b = self.draft(), self.draft()
        b['speaker']='ANDREW_PANTON'
        self.assertIsNone(suggestion(self.draft(), [a,b])['speaker'])
    def test_confirmation_required(self):
        e=self.edits(); e['confirmed']=False
        with self.assertRaises(ValueError): prepare(self.draft(), e, 'tester')
    def test_valid_review_generates_consistent_jump(self):
        q=prepare(self.draft(), self.edits(), 'tester')
        self.assertEqual('02:03', q['timestamp'])
        validate(q, [])
    def test_geoff_restriction_applies_to_approval(self):
        e=self.edits();e.update(speaker='GEOFF_RAMSEY',quote='A beer after the rain.')
        with self.assertRaises(AssertionError): validate(prepare(self.draft(), e, 'tester'), [])
    @patch('review_server.gh')
    def test_remote_changed_draft_blocks_before_writes(self, gh):
        gh.side_effect=[{'object':{'sha':'head'}},{'tree':{'sha':'tree'}},{'tree':[]}]
        with self.assertRaises(ValueError): publish(self.draft(), self.edits())
        self.assertTrue(all(call.kwargs.get('method','GET')=='GET' for call in gh.call_args_list))

class ManualDraftTests(unittest.TestCase):
    def test_manual_entry_is_unverified_and_deduplicated(self):
        from review_server import manual_draft
        body=dict(quote='A synthetic example.',show='RP',episode=1,episodeTitle='Test',sourceUrl='https://example.com')
        a=manual_draft(body)
        self.assertEqual(a['id'],manual_draft(body)['id'])
        self.assertIsNone(a['speaker'])
        self.assertEqual('draft',a['review']['status'])
    def test_bad_source_rejected(self):
        from review_server import manual_draft
        with self.assertRaises(ValueError):
            manual_draft(dict(quote='Example',show='RP',episode=1,episodeTitle='Test',sourceUrl='javascript:alert(1)'))
