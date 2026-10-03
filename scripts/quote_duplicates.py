"""Conservative wording deduplication across episodes and import sources."""
import json
import re
import unicodedata
from difflib import SequenceMatcher


def wording(text):
    text = unicodedata.normalize('NFKC', text).casefold()
    text = re.sub(r"['’‘]", '', text)
    return ' '.join(re.findall(r'\w+', text))


def is_repeat(text, known):
    key = wording(text)
    for previous in known:
        other = wording(previous)
        if key == other:
            return True
        # Only flag tiny wording changes in substantial sentences, not shared topics.
        if min(len(key.split()), len(other.split())) >= 8 and min(len(key),len(other))/max(len(key),len(other)) >= .9:
            if SequenceMatcher(None, key, other, autojunk=False).ratio() >= .94:
                return True
    return False


def existing_wording(root):
    return [json.loads(path.read_text())['quote']
            for folder in ('quotes', 'drafts', 'quarantine')
            for path in (root/folder).glob('*.json')]
