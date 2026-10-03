import unittest
from collect_podscripts import TranscriptParser, candidate

class PodscriptsTests(unittest.TestCase):
    def page(self, title='Fixture [12]'):
        page = TranscriptParser()
        page.feed(f'<h1>{title}</h1><span class="pod_timestamp_indicator">Starting point is 00:03:20</span><span class="transcript-text">I refuse to trust a thermometer that needs its own weather forecast.</span>')
        return page
    def test_audio_time_is_not_youtube_time(self):
        q = candidate(self.page(), 'https://podscripts.co/podcasts/regulation-podcast/test')
        self.assertIsNone(q['speaker'])
        self.assertIsNone(q['timestamp'])
        self.assertIsNone(q['listenUrl'])
        self.assertEqual('00:03:20', q['source']['audioSegmentTimestamp'])
        self.assertLessEqual(len(q['quote'].split()), 25)
        self.assertEqual('draft', q['review']['status'])
    def test_general_lore_is_collected_without_weather_words(self):
        page = self.page()
        page.segments = [('00:10:00', 'Nobody expected the pencil argument to become an entire episode.')]
        q = candidate(page, 'https://podscripts.co/podcasts/regulation-podcast/test')
        self.assertIsNotNone(q)
        self.assertEqual(['random'], q['weatherTags'])
        self.assertIsNone(q['speaker'])

    def test_promotional_passages_still_excluded(self):
        page = self.page()
        page.segments = [('00:10:00', 'Our sponsor has an incredible offer for every listener today.')]
        self.assertIsNone(candidate(page, 'https://podscripts.co/podcasts/regulation-podcast/test'))

    def test_routine_show_introduction_is_skipped(self):
        page = self.page()
        page.segments = [('00:00:00', 'Hello and welcome to another episode of the Regulation Podcast.'),
                         ('00:02:00', 'Nobody expected the pencil argument to become an entire episode.')]
        q = candidate(page, 'https://podscripts.co/podcasts/regulation-podcast/test')
        self.assertIn('pencil argument', q['quote'])

    def test_supplemental_not_assigned_episode(self):
        self.assertIsNone(candidate(self.page('Special'), 'https://example.com'))
    def test_repeated_index_links_deduplicate(self):
        p = TranscriptParser()
        p.feed('<a href="/podcasts/regulation-podcast/test">x</a>' * 3)
        self.assertEqual(1, len(p.links))

class CollectionTests(unittest.TestCase):
    def test_refresh_continues_to_older_pages_without_duplicates(self):
        import tempfile
        import json
        from pathlib import Path
        from unittest.mock import patch
        from collect_podscripts import collect, INDEX
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ('drafts','quotes','inbox'): (root/name).mkdir()
            old = INDEX+'old'; new = INDEX+'older'
            (root/'inbox/podscripts_processed.json').write_text(json.dumps([old]))
            latest = TranscriptParser(); latest.links=[old]
            older = TranscriptParser(); older.links=[new]
            transcript = PodscriptsTests().page()
            with patch('collect_podscripts.fetch', side_effect=[latest,older,transcript]), patch('collect_podscripts.time.sleep'):
                result = collect(root, target=1)
            self.assertEqual({'added':1,'checked':1},result)
            state=json.loads((root/'inbox/podscripts_processed.json').read_text())
            self.assertEqual(2,state['nextPage'])
            self.assertEqual({old,new},set(state['processed']))
            self.assertEqual(1,len(list((root/'drafts').glob('*.json'))))

    def test_batch_keeps_looking_after_unsuitable_episode(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from collect_podscripts import collect, INDEX
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for folder in ('drafts', 'quotes', 'inbox'): (root/folder).mkdir()
            index = TranscriptParser(); index.links=[INDEX+str(i) for i in range(12)]
            unsuitable = PodscriptsTests().page('Supplemental')
            suitable = [PodscriptsTests().page() for _ in range(10)]
            for i, page in enumerate(suitable):
                page.segments = [('00:03:20', f'I refuse unique{i} alpha{i} beta{i} gamma{i} delta{i} epsilon{i} zeta{i} eta{i}.')]
            with patch('collect_podscripts.fetch', side_effect=[index, unsuitable]+suitable), patch('collect_podscripts.time.sleep'):
                result=collect(root)
            self.assertEqual({'added':10,'checked':11},result)
            self.assertEqual(10,len(list((root/'drafts').glob('*.json'))))

    def test_episode_cap_stops_batch_without_candidates(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from collect_podscripts import collect, INDEX
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for folder in ('drafts', 'quotes', 'inbox'): (root/folder).mkdir()
            index=TranscriptParser(); index.links=[INDEX+str(i) for i in range(30)]
            with patch('collect_podscripts.fetch', side_effect=[index]+[PodscriptsTests().page('Supplemental')]*20), patch('collect_podscripts.time.sleep'):
                self.assertEqual({'added':0,'checked':20},collect(root))

    def test_rate_limit_preserves_partial_batch_and_cooldown_blocks_network(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from urllib.error import HTTPError
        from collect_podscripts import collect, INDEX
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for folder in ('drafts','quotes','inbox'): (root/folder).mkdir()
            index=TranscriptParser();index.links=[INDEX+'a',INDEX+'b']
            with patch('collect_podscripts.fetch', side_effect=[index,PodscriptsTests().page(),HTTPError(INDEX,429,'Limited',{},None)]), patch('collect_podscripts.time.sleep'):
                result=collect(root)
            self.assertEqual(1,result['added'])
            self.assertGreater(result['retryAfter'],0)
            with patch('collect_podscripts.fetch') as fetch:
                result=collect(root)
                fetch.assert_not_called()
                self.assertGreater(result['retryAfter'],0)
