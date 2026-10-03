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
