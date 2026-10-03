"""Explainable editorial heuristics, not a humor or attribution probability."""
import re
from lore_terms import matches, SOURCE

THRESHOLD = 70
VERSION = 2


def assess(text, context=''):
    words = re.findall(r"[\w’']+", text)
    lower = text.casefold().strip()
    reasons = []
    reject = None
    if not 8 <= len(words) <= 25:
        reject = 'Not a compact standalone sentence'
    elif not re.search(r'[.!?][”\"\']?$', text) or text.endswith('...'):
        reject = 'Incomplete thought'
    elif re.match(r'^(?:and|but|so|well|yeah|yes|no|okay|ok|wait|like|because|which|in a)\b', lower):
        reject = 'Conversational fragment or filler opening'
    elif re.search(r'\b(?:what (?:i|you|he|she) (?:said|meant)|you know what i mean|that thing|that guy|over there|do you remember|as i said|i don.t know)\b', lower):
        reject = 'Depends on missing conversation'
    if reject:
        return dict(score=0, reasons=[reject], version=VERSION, accepted=False)
    lore = matches(text)
    score = 50
    reasons.append('Compact complete sentence')
    if re.search(r'\b(?:refuse|never|always|impossible|ridiculous|absurd|unacceptable|worst|best|hate|love|begging|unbreakable)\b', lower):
        score += 20; reasons.append('Strong opinion or emphatic claim')
    if re.search(r'\b(?:nobody expected|somehow|apparently|instead|even though|except|but|yet|because|than|turned out|only to)\b', lower):
        score += 20; reasons.append('Surprise, contrast, or explanation')
    if re.search(r'\b(?:like (?:a|an)|as (?:a|an)|imagine|what if|would rather|could|should)\b', lower):
        score += 15; reasons.append('Comparison or unusual premise')
    if re.search(r'\d', text):
        score += 5; reasons.append('Specific detail')
    if lore:
        score += 20; reasons.append('Dictionary lore: ' + ', '.join(lore[:3]))
    # Context can lower confidence, but cannot turn a vague line into a good quote.
    if re.search(r'\b(?:inaudible|unintelligible|crosstalk)\b', context, re.I):
        score -= 20; reasons.append('Surrounding transcript is uncertain')
    if re.match(r'^(?:it|this|that|they|he|she|these|those)\b', lower):
        score -= 20; reasons.append('Unclear subject outside the conversation')
    score = max(0, min(100, score))
    return dict(score=score, reasons=reasons, version=VERSION, accepted=score >= THRESHOLD, loreTerms=lore, loreSource=SOURCE if lore else None)
