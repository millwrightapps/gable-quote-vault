import unittest
from import_transcript import candidates
from quote_quality import assess
from transcript_fixture import transcript

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
    def test_best_candidate_ranks_first(self):
        result=candidates(transcript((300,'I refuse to accept responsibility for the mysterious missing sandwich.'),
                                     (600,'I would rather argue with a pencil because its silence is always more convincing.')))
        self.assertEqual(sorted((q['quality']['score'] for q in result), reverse=True), [q['quality']['score'] for q in result])
        self.assertTrue(all(q['quality']['accepted'] for q in result))
    def test_dictionary_mention_boosts_candidate_without_guessing_speaker(self):
        q=assess('The Gurple collection has finally arrived at my house.')
        self.assertTrue(q['accepted'])
        self.assertTrue(q['loreTerms'])
    def test_lore_does_not_rescue_fragment_or_match_inside_word(self):
        self.assertFalse(assess('Well, the Gurple collection arrived at my house today.')['accepted'])
        from lore_terms import matches
        self.assertEqual([], matches('megagurplewidget'))
    def test_multiple_distinct_moments_per_episode(self):
        result=candidates(transcript((300,'I refuse to surrender my mysterious invisible sandwich.'),
                                     (900,'Nobody expected the enormous cupboard to contain dragons.')))
        self.assertEqual(2,len({q['id'] for q in result}))
        self.assertTrue(all(q['speaker'] is None for q in result))
    def test_lore_ad_still_excluded(self):
        self.assertEqual([],candidates(transcript((300,'Our sponsor offers the best Gurple collection with a discount today.'))))
    def test_same_episode_duplicate_sentence_only_collected_once(self):
        line='I refuse to surrender my mysterious invisible sandwich.'
        self.assertEqual(1,len(candidates(transcript((300,line),(400,line)))))
