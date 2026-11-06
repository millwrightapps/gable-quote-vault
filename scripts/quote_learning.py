#!/usr/bin/env python3
"""Learns which transcript lines this vault's reviewer tends to approve, from the vault's own history.

Approved quotes (quotes/) are the good examples; lines removed in the dashboard (quarantine/, "Removed by reviewer")
are the bad ones. A small naive Bayes model over words and word pairs ranks new candidates by how much they look like
past approvals. It only orders the queue and picks which lines an episode offers; it never approves, removes or credits
anything. Standard library only, and it retrains from the files every time, so each review counts straight away.

Run it directly to see how well it would have ranked your past reviews:
    python3 scripts/quote_learning.py
"""
import json
import math
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

# Why a line was removed, offered as one tap in the dashboard. Keys are saved in review.removalReason.
REASONS = {
    'context': 'Needs the conversation around it',
    'flat': 'Not funny or interesting enough',
    'unkind': 'Unkind or not OK out of context',
    'ad': 'Ad, intro or show housekeeping',
    'transcript': 'Transcript got the words wrong',
    'other': 'Something else',
}
# The line itself may be fine; Whisper misheard it. Learning from these would teach the model the wrong lesson.
NOT_ABOUT_THE_LINE = {'transcript'}
REMOVED_BY_REVIEWER = 'Removed by reviewer'
# Below this many approvals or removals the ranking is mostly noise, so the rule-based score is used instead.
MIN_EACH = 10
# Everyday words never offered as an explanation ("looks like lines you approved: the"), alone or in pairs.
QUIET = set("""a about all an and any are as at be been but by can can't could did do don't for from get go going got had
has have he her him his how i i'd i'll i'm i've if in into is it it's its just know like me more my no not now of oh
okay on one or our out over said say see she so some than that that's the their them then there they think this to too
up us very was we well were what when which who will with would yeah you you're your""".split())


def features(text):
    words = re.findall(r"[a-z0-9']+", text.casefold().replace('’', "'"))
    return set(words) | {a + ' ' + b for a, b in zip(words, words[1:])}


def reviewed(root=ROOT, transcript_only=False):
    """(approved texts, removed texts) from the vault's files. transcript_only keeps approvals that came from
    transcripts, leaving out quotes entered by hand or imported, which read differently from the queue."""
    root = Path(root)
    approved = [q['quote'] for q in (json.loads(p.read_text()) for p in sorted((root / 'quotes').glob('*.json')))
                if not transcript_only or q['id'].startswith('candidate_')]
    removed = []
    for path in sorted((root / 'quarantine').glob('*.json')):
        q = json.loads(path.read_text())
        review = q.get('review') or {}
        if review.get('quarantineReason') == REMOVED_BY_REVIEWER and review.get('removalReason') not in NOT_ABOUT_THE_LINE:
            removed.append(q['quote'])
    return approved, removed


class Model:
    def __init__(self, approved, removed):
        self.n = {1: 0, 0: 0}
        self.counts = {1: {}, 0: {}}
        for label, texts in ((1, approved), (0, removed)):
            for text in texts:
                self._add(features(text), label, 1)

    @classmethod
    def from_vault(cls, root=ROOT):
        return cls(*reviewed(root))

    def _add(self, feats, label, sign):
        self.n[label] += sign
        counts = self.counts[label]
        for f in feats:
            counts[f] = counts.get(f, 0) + sign

    @property
    def ready(self):
        return self.n[1] >= MIN_EACH and self.n[0] >= MIN_EACH

    @property
    def reviews(self):
        return self.n[1] + self.n[0]

    def _weight(self, f):
        """Log-likelihood ratio of seeing f in an approved vs a removed line (add-one smoothing)."""
        yes, no = self.counts[1].get(f, 0), self.counts[0].get(f, 0)
        if not yes and not no:
            return None  # Never seen in a review: says nothing either way.
        return math.log((yes + 1) / (self.n[1] + 2)) - math.log((no + 1) / (self.n[0] + 2))

    def score(self, text):
        """Higher means more like lines you approved. Only meaningful for ordering, not as a probability."""
        if not self.ready:
            return 0.0
        return sum(w for w in map(self._weight, features(text)) if w is not None)

    def explain(self, text, limit=3):
        """The words and pairs pushing this line up or down, seen in at least three reviews."""
        if not self.ready:
            return dict(liked=[], disliked=[])
        weights = []
        for f in features(text):
            if set(f.split()) <= QUIET or self.counts[1].get(f, 0) + self.counts[0].get(f, 0) < 3:
                continue
            weights.append((self._weight(f), f))
        weights.sort()
        return dict(liked=[f for w, f in reversed(weights[-limit:]) if w > 0.5],
                    disliked=[f for w, f in weights[:limit] if w < -0.5])

    def self_check(self, approved, removed):
        """Hide each given line in turn (all of them must be in this model), rank it with the rest, and count
        approvals in the top fifth."""
        scored = []
        for label, texts in ((1, approved), (0, removed)):
            for text in texts:
                feats = features(text)
                self._add(feats, label, -1)
                scored.append((self.score(text), label))
                self._add(feats, label, 1)
        scored.sort(key=lambda row: -row[0])
        top = len(scored) // 5
        return dict(reviews=len(scored), approved=len(approved), top=top,
                    approvedInTop=sum(label for _, label in scored[:top]),
                    byChance=round(top * len(approved) / max(1, len(scored)), 1))


if __name__ == '__main__':
    approved, removed = reviewed()
    model = Model(approved, removed)
    print(f'Learning from {len(approved)} approved and {len(removed)} removed lines.')
    if not model.ready:
        print(f'Needs at least {MIN_EACH} of each before it ranks anything; the rule-based score is used until then.')
    else:
        # Judge it on transcript lines only, like the queue it orders.
        check = model.self_check(reviewed(transcript_only=True)[0], removed)
        print(f"Ranking each past transcript line using only the other reviews, {check['approvedInTop']} of "
              f"{check['approved']} approved lines land in the top {check['top']} of {check['reviews']}, versus about "
              f"{check['byChance']} by chance.")
