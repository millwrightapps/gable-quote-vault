import unittest
from import_transcript import candidates
from quote_filters import is_ad, blocked_segments
from transcript_fixture import transcript

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
        segments=[(600,'Who knew you could give yourself the ick?'),
                  (620,'This episode is brought to you by Bumble.'),
                  (780,'Nobody expected the pencil argument to become an entire episode.')]
        self.assertEqual({0,1},blocked_segments(segments))
        quotes=[q['quote'] for q in candidates(transcript(*segments))]
        self.assertEqual(['Nobody expected the pencil argument to become an entire episode.'],quotes)
    def test_clock_stamps_still_supported(self):
        self.assertEqual({0,1},blocked_segments([('00:10:00','Who knew?'),('00:10:20','Brought to you by Bumble.'),('00:13:00','Later.')]))
    def test_opening_segment_not_collected(self):
        self.assertEqual([],candidates(transcript((30,'Nobody expected the pencil argument to become an entire episode.'))))
