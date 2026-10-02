#!/usr/bin/env python3
"""Discover public episodes without treating descriptions as spoken quotes."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
FEED_URL = 'https://feeds.megaphone.fm/fface'
LIMIT = 10 * 1024 * 1024


def parse_feed(payload):
    if len(payload) > LIMIT:
        raise ValueError('Feed too large')
    if b'<!DOCTYPE' in payload.upper() or b'<!ENTITY' in payload.upper():
        raise ValueError('XML entities are not supported')
    channel = ET.fromstring(payload).find('channel')
    if channel is None or channel.findtext('title') != 'Regulation Podcast':
        raise ValueError('Unexpected podcast feed')
    items = {}
    for item in channel.findall('item'):
        guid = item.findtext('guid')
        title = item.findtext('title')
        if not guid or not title:
            continue
        key = hashlib.sha256(guid.encode()).hexdigest()[:24]
        link = item.findtext('link') or ''
        items[key] = dict(id=key, guid=guid, title=title, published=item.findtext('pubDate'),
                          sourceFeed=FEED_URL, episodeUrl=link if link.startswith('https://') else None)
    return [items[k] for k in sorted(items)]


def discover(payload, output):
    episodes = parse_feed(payload)
    # Preserve discovery history if the upstream feed later trims old episodes.
    old = json.loads(output.read_text()) if output.exists() else []
    merged = {e['id']: e for e in old}
    merged.update({e['id']: e for e in episodes})
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps([merged[k] for k in sorted(merged)], indent=2, ensure_ascii=False) + '\n')
    return len(merged) - len(old)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--feed-file', type=Path)
    args = parser.parse_args()
    if args.feed_file:
        payload = args.feed_file.read_bytes()
    else:
        request = urllib.request.Request(FEED_URL, headers={'User-Agent': 'GableQuoteVault/1.0'})
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read(LIMIT + 1)
    print(f"Discovered {discover(payload, ROOT / 'inbox/episodes.json')} new episodes for source review.")
