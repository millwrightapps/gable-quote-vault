import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from import_transcript import candidates
from quote_learning import MIN_EACH, Model, reviewed
from transcript_fixture import transcript

LIKED = ['I refuse to share my sandwich with a weather balloon number %d.' % i for i in range(MIN_EACH)]
SKIPPED = ['The spreadsheet column needs another formula for row %d.' % i for i in range(MIN_EACH)]


def vault(folder, approved=(), removed=(), reason=None):
    root = Path(folder)
    for name in ('quotes', 'quarantine', 'drafts', 'inbox'):
        (root / name).mkdir(exist_ok=True)
    for i, text in enumerate(approved):
        (root / 'quotes' / f'candidate_a{i}.json').write_text(json.dumps(dict(id=f'candidate_a{i}', quote=text)))
    for i, text in enumerate(removed):
        review = dict(quarantineReason='Removed by reviewer')
        if reason:
            review['removalReason'] = reason
        (root / 'quarantine' / f'candidate_r{i}.json').write_text(json.dumps(dict(id=f'candidate_r{i}', quote=text, review=review)))
    return root


class LearningTests(unittest.TestCase):
    def test_too_few_reviews_learns_nothing(self):
        model = Model(LIKED[:3], SKIPPED)
        self.assertFalse(model.ready)
        self.assertEqual(0, model.score('Anything at all.'))
        self.assertEqual(dict(liked=[], disliked=[]), model.explain('Anything at all.'))

    def test_ranks_lines_like_approvals_higher_and_says_why(self):
        model = Model(LIKED, SKIPPED)
        good = 'Nobody should share a sandwich with a balloon.'
        bad = 'Another spreadsheet formula would fix that column.'
        self.assertGreater(model.score(good), model.score(bad))
        self.assertTrue(any('sandwich' in f for f in model.explain(good)['liked']))
        self.assertEqual(['another', 'column', 'formula'], model.explain(bad)['disliked'])  # Ties: alphabetical.
        self.assertNotIn('a', model.explain(good)['liked'])

    def test_wrong_transcripts_and_automatic_removals_are_not_learned(self):
        with tempfile.TemporaryDirectory() as folder:
            root = vault(folder, LIKED, SKIPPED, reason='transcript')
            (root / 'quarantine' / 'candidate_ad.json').write_text(json.dumps(dict(
                id='candidate_ad', quote='Use code RP.', review=dict(quarantineReason='Promotional text or routine introduction'))))
            self.assertEqual([], reviewed(root)[1])
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(SKIPPED, reviewed(vault(folder, LIKED, SKIPPED, reason='flat'))[1])

    def test_each_episode_keeps_the_lines_most_like_approvals(self):
        filler = ['I refuse to fill the spreadsheet because the formula is absurd.',
                  'Nobody expected the spreadsheet column to turn purple overnight.',
                  'The accountant always hated the spreadsheet more than the printer.',
                  'Somehow the payroll spreadsheet ended up inside a birthday card.',
                  'I would rather fax the spreadsheet than email another column.',
                  'The best formula in the spreadsheet never worked on Tuesdays.',
                  'Apparently the spreadsheet had twelve tabs named after cheeses.',
                  'Imagine a spreadsheet that refuses to sort anything alphabetically.',
                  'The worst column in that spreadsheet was entirely question marks.',
                  'Instead of a calendar we used a spreadsheet full of dinosaurs.']
        lines = [(300 + i * 60, text) for i, text in enumerate(filler)]
        lines.append((1200, 'I refuse to share my sandwich with that absurd balloon.'))
        model = Model(LIKED, SKIPPED)
        kept = [q['quote'] for q in candidates(transcript(*lines), model=model)]
        self.assertEqual(10, len(kept))
        self.assertTrue(kept[0].startswith('I refuse to share my sandwich'))
        # Without enough reviews the rule-based score still decides.
        self.assertEqual(10, len(candidates(transcript(*lines), model=Model([], []))))

    def test_self_check_hides_each_line_from_its_own_ranking(self):
        check = Model(LIKED, SKIPPED).self_check(LIKED, SKIPPED)
        self.assertEqual(dict(reviews=20, approved=10, top=4, approvedInTop=4, byChance=2.0), check)


class RemoveReasonTests(unittest.TestCase):
    def draft(self):
        return dict(id='candidate_x', quote='A line.', review=dict(status='draft'))

    @patch('review_server.subprocess.run')
    @patch('review_server.gh')
    def test_removal_saves_the_reason(self, gh, run):
        import review_server
        draft = self.draft()
        written = {}
        def api(path, payload=None, method='GET'):
            if path == 'git/ref/heads/main': return {'object': {'sha': 'head'}}
            if path == 'git/commits/head': return {'tree': {'sha': 'tree'}}
            if path.startswith('git/trees/'): return {'tree': [{'path': 'drafts/candidate_x.json', 'sha': 'blob'}]}
            if path == 'git/trees':
                written.update(json.loads(payload['tree'][0]['content']))
                return {'sha': 'newtree'}
            if path == 'git/commits':
                written['message'] = payload['message']
                return {'sha': 'commit'}
            return {}
        gh.side_effect = api
        with patch('review_server.json_blob', return_value=draft):
            review_server.remove_draft(draft, 'context')
        self.assertEqual('Removed by reviewer', written['review']['quarantineReason'])
        self.assertEqual('context', written['review']['removalReason'])
        self.assertIn('Needs the conversation around it', written['message'])

    @patch('review_server.gh')
    def test_removal_without_a_known_reason_writes_nothing(self, gh):
        import review_server
        for reason in (None, 'bogus'):
            with self.assertRaisesRegex(ValueError, 'Choose why'):
                review_server.remove_draft(self.draft(), reason)
        gh.assert_not_called()


if __name__ == '__main__':
    unittest.main()
