import unittest
from quote_filters import is_ad, blocked_segments
from collect_podscripts import TranscriptParser, candidate

class AdTests(unittest.TestCase):
    def test_promotions_are_recognized(self):
        for text in ["We've got access to pre-sale tickets so you don't miss it.",
                     'This episode is brought to you by Activia.',
                     'Get groceries delivered to your door from No Frills with PC Express.',
                     'You get access to exclusive dining experiences and an annual travel credit.',
                     'Searchlight Pictures presents a film, only in theaters tomorrow.']:
            self.assertTrue(is_ad(text), text)
    def test_normal_conversation_kept(self):
        self.assertFalse(is_ad('I bought a pencil yesterday and forgot where I put it.'))
    def test_brand_reveal_blocks_preceding_ad_sentence(self):
        segments=[('00:10:00','Who knew you could give yourself the ick?'),
                  ('00:10:20','This episode is brought to you by Bumble.'),
                  ('00:13:00','Nobody expected the pencil argument to become an entire episode.')]
        self.assertEqual({0,1},blocked_segments(segments))
        page=TranscriptParser();page.title='Fixture [10]';page.segments=segments
        self.assertIn('pencil',candidate(page,'https://podscripts.co/podcasts/regulation-podcast/test')['quote'])
    def test_opening_segment_not_collected(self):
        page=TranscriptParser();page.title='Fixture [10]';page.segments=[('00:00:00','A vague promotional sentence without any obvious brand or advertising keyword.')]
        self.assertIsNone(candidate(page,'https://podscripts.co/podcasts/regulation-podcast/test'))
