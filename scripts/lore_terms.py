"""Match dictionary labels only; never use definitions as podcast quotations."""
import json
from functools import lru_cache
from pathlib import Path
import re

SOURCE = 'https://www.regulationlore.com.au/dictionary'
DATA = Path(__file__).resolve().parents[1] / 'inbox/lore_terms.json'

def normalize(text):
    return ' '.join(re.findall(r'[a-z0-9]+', text.casefold()))

@lru_cache(maxsize=1)
def terms():
    return [(term, ' ' + normalize(term) + ' ') for term in json.loads(DATA.read_text())['terms']]

def matches(text):
    needle = ' ' + normalize(text) + ' '
    return [term for term, normalized in terms() if normalized in needle]
