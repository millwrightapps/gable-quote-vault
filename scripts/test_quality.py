import unittest
from quote_quality import assess
from collect_podscripts import TranscriptParser, candidate

class QualityTests(unittest.TestCase):
    def test_fragments_and_vague_lines_rejected(self):
        for text in ['Well, it is a hot plate so it would heat the powder.',
                     'That is exactly what I meant when I said it.',
                     'The temperature has been about the same every night.',
                     'I was going to get a jacket or something...']:
            self.assertFalse(assess(text)['accepted'], text)
    def test_clock_abbreviation_is_not_sentence_punctuation(self):
        self.assertFalse(assess('Months but I would wake up at 5:00 a.m.')['accepted'])
    def test_concrete_opinion_passes(self):
        self.assertTrue(assess('I refuse to trust a thermometer that needs its own weather forecast.')['accepted'])
    def test_uncertain_context_reduces_score(self):
        text='I refuse to accept responsibility for the mysterious missing sandwich.'
        self.assertGreater(assess(text)['score'],assess(text,'[inaudible]')['score'])
    def test_best_candidate_wins_instead_of_first(self):
        page=TranscriptParser();page.title='Fixture [10]';page.segments=[
            ('00:05:00','I refuse to accept responsibility for the mysterious missing sandwich.'),
            ('00:10:00','I would rather argue with a pencil because its silence is always more convincing.')]
        result=candidate(page,'https://podscripts.co/podcasts/regulation-podcast/test')
        self.assertIn('pencil',result['quote'])
        self.assertTrue(result['quality']['accepted'])

    def test_dictionary_mention_boosts_candidate_without_guessing_speaker(self):
        q=assess('The Gurple collection has finally arrived at my house.')
        self.assertTrue(q['accepted'])
        self.assertTrue(q['loreTerms'])
    def test_lore_does_not_rescue_fragment_or_match_inside_word(self):
        self.assertFalse(assess('Well, the Gurple collection arrived at my house today.')['accepted'])
        from lore_terms import matches
        self.assertEqual([], matches('megagurplewidget'))
    def test_multiple_distinct_moments_per_episode(self):
        from collect_podscripts import candidates
        p=TranscriptParser();p.title='Synthetic [12]';p.segments=[
            ('00:05:00','I refuse to surrender my mysterious invisible sandwich.'),
            ('00:15:00','Nobody expected the enormous cupboard to contain dragons.')]
        result=candidates(p,'https://podscripts.co/podcasts/regulation-podcast/test')
        self.assertEqual(2,len(result))
        self.assertEqual(2,len({q['id'] for q in result}))
        self.assertTrue(all(q['speaker'] is None for q in result))
        self.assertLessEqual(sum(len(q['quote'].split()) for q in result),25)
        self.assertEqual(1,len(candidates(p,'test',word_budget=10)))
        self.assertEqual([],candidates(p,'test',word_budget=0))
    def test_lore_ad_still_excluded(self):
        p=TranscriptParser();p.title='Synthetic [12]';p.segments=[
            ('00:05:00','Our sponsor offers the best Gurple collection with a discount today.')]
        self.assertIsNone(candidate(p,'https://podscripts.co/podcasts/regulation-podcast/test'))
    def test_same_episode_duplicate_sentence_only_collected_once(self):
        from collect_podscripts import candidates
        p=TranscriptParser();p.title='Synthetic [12]'
        p.segments=[('00:05:00','I refuse to surrender my mysterious invisible sandwich.')] * 2
        self.assertEqual(1,len(candidates(p,'test')))

    def test_source_budget_counts_reviewed_and_removed_excerpts(self):
        import tempfile,json
        from pathlib import Path
        from collect_podscripts import source_word_counts
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name in ('quotes','drafts','quarantine'):
                (root/name).mkdir()
                (root/name/'example.json').write_text(json.dumps({'quote':'Synthetic short fixture only','source':{'url':'https://example.com/episode'}}))
            self.assertEqual(12,source_word_counts(root)['https://example.com/episode'])
