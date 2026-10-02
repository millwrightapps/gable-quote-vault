#!/usr/bin/env python3
"""Collect one short, unattributed candidate per transcript; never auto-publish."""
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
import urllib.request
import urllib.error
from urllib.parse import urljoin, urlparse

ROOT = Path(__file__).resolve().parents[1]
INDEX = 'https://podscripts.co/podcasts/regulation-podcast/'


class TranscriptParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.title = ''
        self.time = None
        self.segments = []
        self.capture = None
        self.text = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        href = attrs.get('href', '')
        if tag == 'a' and href.startswith('/podcasts/regulation-podcast/'):
            url = urljoin(INDEX, href)
            if url.rstrip('/') != INDEX.rstrip('/') and url not in self.links:
                self.links.append(url)
        classes = attrs.get('class', '').split()
        if tag == 'h1':
            self.capture, self.text = 'title', []
        elif tag == 'span' and 'pod_timestamp_indicator' in classes:
            self.capture, self.text = 'time', []
        elif tag == 'span' and 'transcript-text' in classes:
            self.capture, self.text = 'segment', []
    def handle_data(self, data):
        if self.capture:
            self.text.append(data)
    def handle_endtag(self, tag):
        if (self.capture == 'title' and tag == 'h1') or (self.capture in ('time', 'segment') and tag == 'span'):
            text = ' '.join(''.join(self.text).split())
            if self.capture == 'title':
                self.title = text
            elif self.capture == 'time':
                match = re.search(r'(\d{2}:\d{2}:\d{2})', text)
                self.time = match.group(1) if match else None
            elif self.time:
                self.segments.append((self.time, text))
            self.capture = None


def candidate(page, url):
    episode = re.search(r'\[(\d+)\]', page.title)
    if not episode:
        return None  # Supplemental/ambiguous show numbering needs manual review.
    for stamp, block in page.segments:
        if re.search(r'(sponsor|promo|discount|advertis|savings|insurance|cash back|\.com|terms apply|sign up)', block, re.I):
            continue
        for sentence in re.split(r'(?<=[.!?])\s+', block):
            words = sentence.split()
            # One brief excerpt per source; omit ads and incomplete fragments.
            if not (8 <= len(words) <= 25):
                continue
            if re.search(r'\b(sponsor|promo|discount|advertis|offer|insurance|visit|\.com)\b', sentence, re.I):
                continue
            if sentence[-1:] not in '.!?':
                continue
            key = 'podscripts_' + hashlib.sha256(url.encode()).hexdigest()[:20]
            return dict(id=key, quote=sentence, speaker=None, show='RP', episode=int(episode.group(1)),
                episodeTitle=page.title, timestamp=None, timestampSeconds=None, youtubeVideoId=None,
                listenUrl=None, weatherTags=["random"], tags=[],
                source=dict(provider='Podscripts', url=url, audioSegmentTimestamp=stamp),
                review=dict(status='draft', reviewer='', sourceUrl=url, checkedAt='',
                    notes='Machine transcript candidate. Speaker unknown. Audio segment time is approximate and is NOT a YouTube jump time. Verify the recording and add playback metadata before approval.'))
    return None


def fetch(url):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.netloc != 'podscripts.co' or not (parsed.path == '/podcasts/regulation-podcast' or parsed.path.startswith('/podcasts/regulation-podcast/')):
        raise ValueError('Unexpected source URL')
    request = urllib.request.Request(url, headers={'User-Agent': 'GableQuoteVault/1.0 (+https://github.com/millwrightapps/gable-quote-vault)'})
    with urllib.request.urlopen(request, timeout=30) as response:
        if urlparse(response.url).netloc != 'podscripts.co':
            raise ValueError('Unexpected redirect')
        data = response.read(5 * 1024 * 1024 + 1)
    if len(data) > 5 * 1024 * 1024:
        raise ValueError('Source too large')
    page = TranscriptParser()
    page.feed(data.decode('utf-8'))
    return page


def collect(root=ROOT, target=10, max_episodes=20):
    state_path = root / 'inbox/podscripts_processed.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else []
    processed = set(state if isinstance(state, list) else state['processed'])
    page_number = 1 if isinstance(state, list) else state.get('nextPage', 1)
    cooldown = 0 if isinstance(state, list) else state.get('cooldownUntil', 0)
    if cooldown > time.time():
        return dict(added=0, checked=0, retryAfter=int(cooldown-time.time())+1)
    cooldown = 0
    def source_page(url):
        nonlocal cooldown
        try:
            return fetch(url)
        except urllib.error.HTTPError as error:
            if error.code != 429:
                raise
            retry = error.headers.get('Retry-After', '300') if error.headers else '300'
            try:
                delay = max(300, int(retry))
            except ValueError:
                from email.utils import parsedate_to_datetime
                try:
                    delay = max(300, int(parsedate_to_datetime(retry).timestamp()-time.time()))
                except (TypeError, ValueError):
                    delay = 300
            cooldown = time.time() + delay
            return None
    added = checked = index_pages = 0
    deadline = time.monotonic() + 120
    # Fill a batch across index pages, rather than stopping at the first two episodes.
    latest = source_page(INDEX)
    urls = latest.links if latest else []
    while not cooldown and time.monotonic() < deadline:
        for url in urls:
            if url in processed:
                continue
            if cooldown or added >= target or checked >= max_episodes or time.monotonic() >= deadline:
                break
            time.sleep(5)
            page = source_page(url)
            if page is None:
                break
            if not page.segments:
                raise ValueError('Transcript missing or markup changed; leaving source unprocessed')
            q = candidate(page, url)
            if q:
                target_path = root / 'drafts' / (q['id'] + '.json')
                approved = root / 'quotes' / target_path.name
                if not target_path.exists() and not approved.exists():
                    target_path.write_text(json.dumps(q, indent=2, ensure_ascii=False) + '\n')
                    added += 1
            processed.add(url)
            checked += 1
        if cooldown or added >= target or checked >= max_episodes or time.monotonic() >= deadline:
            break
        if index_pages >= 4:
            break
        # Revisit the saved page until exhausted, so partially read pages lose no episodes.
        page_number = max(2, page_number) if index_pages == 0 else page_number + 1
        older = source_page(INDEX.rstrip('/') + f'?page={page_number}')
        if older is None:
            break
        urls = older.links
        index_pages += 1
        if not urls:
            page_number = 1
            break
    state_path.write_text(json.dumps(dict(processed=sorted(processed), nextPage=page_number, cooldownUntil=cooldown), indent=2) + '\n')
    result = dict(added=added, checked=checked)
    if cooldown:
        result["retryAfter"] = max(1, int(cooldown-time.time())+1)
    return result


def main():
    result = collect()
    print(f"Added {result['added']} short Podscripts candidates for attribution review. Published none.")


if __name__ == '__main__':
    main()
