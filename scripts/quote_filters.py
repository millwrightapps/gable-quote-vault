"""Conservative screening for automatic candidates; human review is still required."""
import re

AD = re.compile(
    r'\b(?:sponsor\w*|promo\w*|discount\w*|advertis\w*|savings|insurance)\b'
    r'|\b(?:brought to you by|paid partnership|cash back|terms apply|sign up|free trial|'
    r'limited.time offer|use (?:the |our )?code|enter (?:the |our )?code|'
    r'pre.sale tickets|exclusive dining|travel credit|groceries delivered|'
    r'only in (?:theaters|cinemas)|streaming (?:now|on)|download the app|'
    r'with me as always|i am your host)\b'
    r'|\b(?:american express|amex|pc express|no frills|activia|searchlight pictures|'
    r'go transit|betterhelp|squarespace|nordvpn|rocket money|disney plus|hulu original)\b'
    r'|(?:https?://|www\.|\.(?:com|ca|net)\b)', re.I)


def is_ad(text):
    return bool(AD.search(text))


def seconds(stamp):
    """Seconds from a number or an "HH:MM:SS" / "MM:SS" stamp."""
    if isinstance(stamp, (int, float)):
        return stamp
    return sum(int(value) * 60**i for i, value in enumerate(reversed(stamp.split(':'))))


def blocked_segments(segments):
    """Ad sentences can precede the brand reveal; screen neighboring blocks too."""
    marked = {i for i, (_, text) in enumerate(segments) if is_ad(text)}
    blocked = set(marked)
    for i in marked:
        for j in range(max(0,i-2), min(len(segments),i+3)):
            if abs(seconds(segments[j][0])-seconds(segments[i][0])) <= 90:
                blocked.add(j)
    return blocked
