import unittest
from collect_podscripts import TranscriptParser, candidate

class PodscriptsTests(unittest.TestCase):
    def page(self, title='Fixture [12]'):
        page = TranscriptParser()
        page.feed(f'<h1>{title}</h1><span class="pod_timestamp_indicator">Starting point is 00:03:20</span><span class="transcript-text">This weather is much colder than the synthetic test expected.</span>')
        return page
    def test_audio_time_is_not_youtube_time(self):
        q = candidate(self.page(), 'https://podscripts.co/podcasts/regulation-podcast/test')
        self.assertIsNone(q['speaker'])
        self.assertIsNone(q['timestamp'])
        self.assertIsNone(q['listenUrl'])
        self.assertEqual('00:03:20', q['source']['audioSegmentTimestamp'])
        self.assertLessEqual(len(q['quote'].split()), 25)
        self.assertEqual('draft', q['review']['status'])
    def test_supplemental_not_assigned_episode(self):
        self.assertIsNone(candidate(self.page('Special'), 'https://example.com'))
    def test_repeated_index_links_deduplicate(self):
        p = TranscriptParser()
        p.feed('<a href="/podcasts/regulation-podcast/test">x</a>' * 3)
        self.assertEqual(1, len(p.links))
