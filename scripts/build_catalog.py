#!/usr/bin/env python3
"""Validate reviewed quotes and generate the public feed; standard library only."""
import argparse
import datetime
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SPEAKERS = {'ANDREW_PANTON', 'GAVIN_FREE', 'GEOFF_RAMSEY', 'ERIC_BAUDOUR', 'NICK_SCHWARTZ'}
ALCOHOL = re.compile(r'\b(beer|beers|wine|whiskey|whisky|vodka|alcohol|drunk|booze|cocktail|bourbon|tequila|drinking)\b', re.I)


def validate(q, retired):
    assert re.fullmatch(r'[a-z0-9_]+', q['id']), 'Invalid stable ID'
    assert q['id'] not in retired, 'Retired quote cannot be republished'
    assert q['speaker'] in SPEAKERS, 'Unknown speaker; never guess'
    if q.get('secondarySpeaker') is not None:
        assert q['secondarySpeaker'] in SPEAKERS, 'Unknown secondary speaker'
        assert q['speaker'] != q['secondarySpeaker'], 'Duplicate speaker'
    assert q['show'] in {'RP', 'FF'}, 'Unknown show'
    assert type(q['episode']) is int and q['episode'] > 0
    assert q['episodeTitle'].strip() and q['quote'].strip()
    assert re.fullmatch(r'\d+:[0-5]\d(?::[0-5]\d)?', q['timestamp']), 'Invalid timestamp'
    seconds = 0
    for part in q['timestamp'].split(':'):
        seconds = seconds * 60 + int(part)
    assert q['timestampSeconds'] == seconds, 'Timestamp fields disagree'
    if q.get('playbackProvider') == 'rtarchive':
        recordings = json.loads((ROOT / 'inbox/rtarchive_episodes.json').read_text())
        recording = next((r for r in recordings if r['id'] == q.get('archiveVideoId') and r['episode'] == q['episode']), None)
        assert q['show'] == 'FF' and recording, 'Archive recording must match the F**kFace episode'
        url = recording['url'] + f'?t={seconds}'
    else:
        assert re.fullmatch(r'[A-Za-z0-9_-]{11}', q['youtubeVideoId']), 'Direct recording required'
        url = f"https://www.youtube.com/watch?v={q['youtubeVideoId']}&t={seconds}s"
    assert q['listenUrl'] == url, 'Playback URL must match recording and timestamp'
    review = q['review']
    assert review['status'] == 'verified' and review['reviewer'].strip(), 'Human review required'
    datetime.date.fromisoformat(review['checkedAt'])
    assert review['sourceUrl'] == url, 'Review the actual linked recording'
    assert all(review.get(k) is True for k in ('wordingChecked', 'speakersChecked', 'episodeChecked', 'timestampChecked')), 'Complete all review checks'
    assert isinstance(q['weatherTags'], list) and q['weatherTags'] and all(isinstance(t, str) and t.strip() for t in q['weatherTags'])
    if 'GEOFF_RAMSEY' in (q['speaker'], q.get('secondarySpeaker')):
        assert not ALCOHOL.search(q['quote']), 'Geoff must not be associated with drinking alcohol'
    # Keyword checks are only a backstop; the reviewer must check context too.
    assert review.get('attributionPolicyChecked') is True, 'Review the Geoff attribution policy'


def build():
    manifest = json.loads((ROOT / 'catalog.json').read_text())
    assert manifest['schemaVersion'] == 1
    assert type(manifest['revision']) is int and manifest['revision'] > 0
    retired = manifest['retiredIds']
    quotes = []
    seen = set()
    for path in sorted((ROOT / 'quotes').glob('*.json')):
        q = json.loads(path.read_text())
        try:
            validate(q, retired)
            assert q['id'] not in seen, 'Duplicate quote ID'
        except (AssertionError, KeyError, ValueError, TypeError) as exc:
            raise ValueError(f'{path.name}: {exc}') from exc
        seen.add(q['id'])
        quotes.append(q)
    return {**manifest, 'quotes': quotes}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    output = json.dumps(build(), indent=2, ensure_ascii=False) + '\n'
    target = ROOT / 'published/catalog.json'
    if args.check:
        assert target.read_text() == output, 'Run python3 scripts/build_catalog.py and commit the generated catalog'
    else:
        target.write_text(output)
    print('Catalog valid; only reviewed entries are publishable.')
