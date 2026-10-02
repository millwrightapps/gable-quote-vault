#!/usr/bin/env python3
"""Extract short draft candidates from a supplied timed transcript, never infer speakers."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def is_intro(text):
    """Reject routine show greetings and introductions, not ordinary dialogue."""
    return bool(re.search(
        r"\bwelcome(?:\s+back)?\b.{0,100}\b(?:regulation|podcast|episode|f\W*ckface)\b"
        r"|\b(?:my name is|i(?:'|’)?m your host|your hosts? (?:are|is)|joining me today)\b",
        text, re.I,
    ))


def candidates(transcript):
    video = transcript['youtubeVideoId']
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}', video):
        raise ValueError('A specific YouTube recording is required')
    if transcript['show'] not in ('RP', 'FF') or type(transcript['episode']) is not int or transcript['episode'] <= 0:
        raise ValueError('Explicit show and episode required')
    results = {}
    for segment in transcript['segments']:
        text = segment['text'].strip()
        start = segment['start']
        if not isinstance(start, (int, float)) or not math.isfinite(start) or start < 0:
            raise ValueError('Invalid segment time')
        if not 30 <= len(text) <= 240 or is_intro(text):
            continue
        seconds = int(start)
        key = 'candidate_' + hashlib.sha256(f'{video}:{seconds}:{text}'.encode()).hexdigest()[:20]
        url = f'https://www.youtube.com/watch?v={video}&t={seconds}s'
        results[key] = dict(id=key, quote=text, speaker=None, show=transcript['show'],
            episode=transcript['episode'], episodeTitle=transcript['episodeTitle'],
            timestamp=f'{seconds // 60:02d}:{seconds % 60:02d}', timestampSeconds=seconds,
            youtubeVideoId=video, listenUrl=url, weatherTags=["random"], tags=[],
            review=dict(status='draft', reviewer='', sourceUrl=url, checkedAt='',
                        notes='Transcript candidate. Listen to identify every speaker and verify exact wording and timing.'))
        if len(results) >= 10:
            break
    return list(results.values())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('transcript', type=Path)
    args = parser.parse_args()
    target = ROOT / 'drafts'
    added = 0
    for quote in candidates(json.loads(args.transcript.read_text())):
        path = target / (quote['id'] + '.json')
        if not path.exists() and not (ROOT / 'quotes' / path.name).exists():
            path.write_text(json.dumps(quote, indent=2, ensure_ascii=False) + '\n')
            added += 1
    print(f'Added {added} unverified candidates; no speakers assigned and nothing published.')
