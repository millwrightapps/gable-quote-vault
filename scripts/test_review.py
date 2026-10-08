import unittest
from unittest.mock import patch
from review_server import prepare, suggestion, publish, require_clean_quote_data
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
    @patch('review_server.subprocess.run')
    def test_code_changes_do_not_block_refresh(self, run):
        run.return_value.stdout=''
        require_clean_quote_data()
        self.assertIn('drafts', run.call_args.args[0])
        self.assertNotIn('scripts', run.call_args.args[0])
    @patch('review_server.subprocess.run')
    def test_unsaved_quote_data_still_blocks_refresh(self, run):
        run.return_value.stdout=' M drafts/reg_001.json\n'
        with self.assertRaisesRegex(ValueError, 'unsaved quote or queue edits'):
            require_clean_quote_data()
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

class RemoveTests(unittest.TestCase):
    @patch('review_server.subprocess.run')
    @patch('review_server.json_blob')
    @patch('review_server.gh')
    def test_remove_atomically_quarantines_without_changing_published_catalog(self, gh, blob, run):
        import json
        from review_server import remove_draft
        draft=dict(id='test_remove',quote='Synthetic test only.',review={'status':'draft'})
        blob.return_value=draft
        gh.side_effect=[{'object':{'sha':'head'}},{'tree':{'sha':'base'}},{'tree':[]},{'sha':'tree'},{'sha':'commit'},{}]
        remove_draft(draft)
        changes=gh.call_args_list[3].args[1]['tree']
        self.assertEqual({'drafts/test_remove.json','quarantine/test_remove.json'},{c['path'] for c in changes})
        self.assertIsNone(changes[1]['sha'])
        self.assertEqual('quarantined',json.loads(changes[0]['content'])['review']['status'])
        self.assertFalse(gh.call_args_list[-1].args[1]['force'])
    @patch('review_server.json_blob',return_value={'id':'changed'})
    @patch('review_server.gh')
    def test_changed_remote_draft_is_not_removed(self, gh, blob):
        from review_server import remove_draft
        gh.side_effect=[{'object':{'sha':'head'}},{'tree':{'sha':'base'}},{'tree':[]}]
        with self.assertRaises(ValueError): remove_draft({'id':'test_remove'})
        self.assertEqual(3,gh.call_count)

class ArchiveReviewTests(unittest.TestCase):
    draft = ReviewTests.draft
    edits = ReviewTests.edits
    def archive_edits(self):
        e=self.edits()
        e.update(show='FF',episode=1,playbackProvider='rtarchive',archiveVideoId='f-kface-2020-6-3')
        return e
    def test_archive_link_matches_review_and_omits_youtube(self):
        q=prepare(self.draft(),self.archive_edits(),'tester')
        self.assertEqual('https://rtarchive.org/watch/f-kface-2020-6-3?t=123',q['listenUrl'])
        self.assertNotIn('youtubeVideoId',q)
        self.assertEqual(q['listenUrl'],q['review']['sourceUrl'])
        validate(q,[])
    def test_archive_wrong_episode_or_show_rejected(self):
        for changes in ({'episode':2},{'show':'RP'},{'archiveVideoId':'unknown'}):
            e=self.archive_edits();e.update(changes)
            with self.assertRaises(ValueError): prepare(self.draft(),e,'tester')
    def test_archive_requires_confirmation_and_valid_time(self):
        for changes in ({'confirmed':False},{'timestampSeconds':-1},{'timestampSeconds':1.5}):
            e=self.archive_edits();e.update(changes)
            with self.assertRaises(ValueError): prepare(self.draft(),e,'tester')
    def test_archive_catalog_rejects_changed_recording(self):
        q=prepare(self.draft(),self.archive_edits(),'tester')
        q['episode']=2
        with self.assertRaises(AssertionError): validate(q,[])
    def test_archive_index_covers_early_episodes_without_claiming_transcripts(self):
        import json
        from build_catalog import ROOT
        records=json.loads((ROOT/'inbox/rtarchive_episodes.json').read_text())
        self.assertEqual(list(range(1,57)),sorted(r['episode'] for r in records))
        self.assertEqual(56,len({r['id'] for r in records}))
        self.assertTrue(all(not r['hasTranscript'] and r['url'].startswith('https://rtarchive.org/watch/') and r['mediaUrl'].startswith('https://archive.org/download/') for r in records))
