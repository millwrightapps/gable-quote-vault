#!/usr/bin/env python3
"""Loopback-only review dashboard. GitHub credentials remain in the local gh CLI."""
import argparse
import datetime
import hashlib
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import secrets
import subprocess
import urllib.request
import xml.etree.ElementTree as ET
import sys
import time
import ipaddress
import tempfile
import shutil
import threading
from collect_youtube import STATE_PATH, collect, fetch_videos
from whisper_youtube import transcribe

REFRESH_LOCK = threading.Lock()
# The Whisper job the dashboard is running (one at a time), polled by the page.
JOB = dict(running=False, stop=False, total=0, done=0, added=0, addedIds=[], current='', message='')

from build_catalog import ROOT, SPEAKERS, validate

def repo_name():
    """owner/name of this vault on GitHub, from the folder's origin remote (works for any fork)."""
    url = subprocess.run(['git', 'remote', 'get-url', 'origin'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    match = re.search(r'github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$', url)
    if not match:
        raise SystemExit('This vault needs a GitHub remote named origin (git remote add origin https://github.com/you/your-vault.git).')
    return match.group(1)


REPO = repo_name()
TOKEN = secrets.token_urlsafe(32)
MEDIA = {}
PAIR_CODE = secrets.token_hex(6)
PAIR_ATTEMPTS = []
PAIR_LOCK = threading.Lock()


def normalize(text):
    return re.sub(r'[^a-z0-9]', '', text.lower().removeprefix('regulation podcast - '))


def suggestion(q, reviewed):
    matches = [r for r in reviewed if normalize(r['quote']) == normalize(q['quote']) and r['show'] == q['show'] and r['episode'] == q['episode']]
    credits = {(r['speaker'], r.get('secondarySpeaker')) for r in matches}
    if len(credits) == 1:
        speaker, secondary = next(iter(credits))
        return dict(speaker=speaker, secondarySpeaker=secondary, score=100, basis='Exact text and episode match to a human-reviewed quote. This is text agreement, not voice confidence.')
    return dict(speaker=None, secondarySpeaker=None, score=None, basis='No verified speaker evidence. The existing draft credit is unverified; listen before approving.')


def load_media():
    try:
        with urllib.request.urlopen('https://feeds.megaphone.fm/fface', timeout=20) as response:
            data = response.read(10 * 1024 * 1024 + 1)
        if len(data) > 10 * 1024 * 1024 or b'<!DOCTYPE' in data.upper():
            return
        for item in ET.fromstring(data).findall('channel/item'):
            enclosure = item.find('enclosure')
            if enclosure is not None and enclosure.get('url', '').startswith('https://'):
                MEDIA[normalize(item.findtext('title') or '')] = enclosure.get('url')
    except Exception:
        pass  # YouTube/source links remain available offline.


def gh(path, payload=None, method='GET'):
    cmd = ['gh', 'api', f'repos/{REPO}/{path}', '--method', method]
    if payload is not None:
        cmd += ['--input', '-']
    result = subprocess.run(cmd, input=json.dumps(payload) if payload is not None else None,
                            text=True, capture_output=True, timeout=45)
    if result.returncode:
        raise ValueError('GitHub could not complete the request. Check gh login and refresh the queue; nothing is marked approved locally.')
    return json.loads(result.stdout) if result.stdout else {}


def json_blob(tree, path):
    import base64
    entry = next((e for e in tree if e['path'] == path), None)
    if entry is None:
        raise ValueError('The draft changed or was removed. Refresh the queue.')
    obj = gh('git/blobs/' + entry['sha'])
    return json.loads(base64.b64decode(obj['content']))


def prepare(draft, edits, reviewer):
    q = dict(draft)
    for field in ('quote', 'speaker', 'secondarySpeaker', 'show', 'episode', 'episodeTitle', 'youtubeVideoId', 'weatherTags', 'playbackProvider', 'archiveVideoId'):
        q[field] = edits.get(field)
    if not q.get('secondarySpeaker'):
        q.pop('secondarySpeaker', None)
    seconds = edits.get('timestampSeconds')
    if type(seconds) is not int or not 0 <= seconds <= 86400:
        raise ValueError('Enter a valid recording start time in seconds.')
    q['timestampSeconds'] = seconds
    q['timestamp'] = f'{seconds // 60:02d}:{seconds % 60:02d}'
    if q.get('playbackProvider') == 'rtarchive':
        recordings = json.loads((ROOT/'inbox/rtarchive_episodes.json').read_text())
        recording = next((r for r in recordings if r['id'] == q.get('archiveVideoId') and r['episode'] == q['episode']), None)
        if q['show'] != 'FF' or recording is None:
            raise ValueError('Choose the matching F**kFace archive recording.')
        q.pop('youtubeVideoId', None)
        q['listenUrl'] = recording['url'] + f'?t={seconds}'
    else:
        q['listenUrl'] = f"https://www.youtube.com/watch?v={q['youtubeVideoId']}&t={seconds}s"
    if edits.get('confirmed') is not True:
        raise ValueError('Confirm that you checked the recording and all speaker credits.')
    q['review'] = dict(status='verified', reviewer=reviewer, checkedAt=datetime.date.today().isoformat(),
        sourceUrl=q['listenUrl'], wordingChecked=True, speakersChecked=True, episodeChecked=True,
        timestampChecked=True, attributionPolicyChecked=True)
    return q


def publish(draft, edits):
    # Read one immutable commit; one fast-forward-only update atomically publishes all four files.
    head = gh('git/ref/heads/main')['object']['sha']
    commit = gh('git/commits/' + head)
    tree = gh('git/trees/' + commit['tree']['sha'] + '?recursive=1')
    if tree.get('truncated'):
        raise ValueError('Vault is too large for this publisher; no change made.')
    entries = tree['tree']
    path = 'drafts/' + draft['id'] + '.json'
    if json_blob(entries, path) != draft:
        raise ValueError('This draft changed on GitHub. Refresh before reviewing again.')
    catalog = json_blob(entries, 'published/catalog.json')
    manifest = json_blob(entries, 'catalog.json')
    profile = subprocess.run(['gh', 'api', 'user', '--jq', '.login'], text=True, capture_output=True, timeout=20, check=True).stdout.strip()
    q = prepare(draft, edits, profile)
    evidence = suggestion(draft, catalog['quotes'])
    q['review']['speakerSuggestion'] = evidence
    q['review']['suggestionMatchedReview'] = (
        (evidence['speaker'], evidence['secondarySpeaker']) == (q['speaker'], q.get('secondarySpeaker'))
        if evidence['speaker'] is not None else None
    )
    validate(q, manifest['retiredIds'])
    if any(r['id'] == q['id'] for r in catalog['quotes']):
        raise ValueError('This quote is already published.')
    manifest['revision'] += 1
    catalog = {**manifest, 'quotes': sorted(catalog['quotes'] + [q], key=lambda r: r['id'])}
    for row in catalog['quotes']:
        validate(row, manifest['retiredIds'])
    changes = [dict(path=p, mode='100644', type='blob', content=json.dumps(obj, indent=2, ensure_ascii=False)+'\n')
        for p, obj in [('quotes/'+q['id']+'.json', q), ('catalog.json', manifest), ('published/catalog.json', catalog)]]
    changes.append(dict(path=path, mode='100644', type='blob', sha=None))
    new_tree = gh('git/trees', dict(base_tree=commit['tree']['sha'], tree=changes), 'POST')['sha']
    new_commit = gh('git/commits', dict(message='Approve reviewed quote '+q['id'], tree=new_tree, parents=[head]), 'POST')['sha']
    gh('git/refs/heads/main', dict(sha=new_commit, force=False), 'PATCH')
    subprocess.run(['git', 'pull', '--ff-only'], cwd=ROOT, capture_output=True, timeout=45)
    return dict(message='Approved and published. Gable will load the new revision on its next sync.', url=f'https://github.com/{REPO}/commit/{new_commit}')


def require_clean_quote_data():
    # Code, docs, and local settings do not risk being overwritten by queue collection.
    paths = ['drafts', 'quotes', 'inbox', 'quarantine', 'catalog.json', 'published/catalog.json']
    status = subprocess.run(['git', 'status', '--porcelain', '--', *paths],
                            cwd=ROOT, capture_output=True, text=True, check=True)
    if status.stdout.strip():
        raise ValueError('The vault has unsaved quote or queue edits. Save or commit those before collecting more quotes.')


def collect_one(videos):
    """Transcribe the next unprocessed numbered episode and commit its drafts and progress to GitHub."""
    # Use an isolated copy so a failure never leaves half-imported local drafts.
    require_clean_quote_data()
    subprocess.run(['git', 'pull', '--ff-only'], cwd=ROOT, capture_output=True, text=True, timeout=45, check=True)
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    base = gh('git/commits/' + head)['tree']['sha']
    titles = {v['id']: v['title'] for v in videos}

    def whisper(video_id):
        JOB['current'] = titles.get(video_id, video_id)
        return transcribe(video_id)

    with tempfile.TemporaryDirectory() as directory:
        temp = Path(directory)
        for folder in ('drafts', 'quotes', 'inbox', 'quarantine'):
            if (ROOT/folder).exists():
                shutil.copytree(ROOT / folder, temp / folder)
        result = collect(whisper, temp, target=10, max_videos=1, fetch_videos_fn=lambda: videos, delay_seconds=0)
        paths = [p for p in (temp/'drafts').glob('*.json') if not (ROOT/'drafts'/p.name).exists()]
        result['addedIds'] = [json.loads(p.read_text())['id'] for p in paths]
        paths.append(temp/STATE_PATH)
        changes = [dict(path=str(p.relative_to(temp)), mode='100644', type='blob', content=p.read_text())
                   for p in paths if not (ROOT/p.relative_to(temp)).exists() or p.read_bytes() != (ROOT/p.relative_to(temp)).read_bytes()]
        if changes:
            tree = gh('git/trees', dict(base_tree=base, tree=changes), 'POST')['sha']
            commit = gh('git/commits', dict(message='Add Whisper transcript candidates from review dashboard', tree=tree, parents=[head]), 'POST')['sha']
            gh('git/refs/heads/main', dict(sha=commit, force=False), 'PATCH')
            subprocess.run(['git', 'pull', '--ff-only'], cwd=ROOT, capture_output=True, timeout=45, check=True)
    return result


def run_whisper(count):
    """Background job: one episode at a time, each committed as it finishes, so Stop or a failure keeps earlier work."""
    try:
        videos = fetch_videos()
        while JOB['done'] < count and not JOB['stop']:
            result = collect_one(videos)
            if result.get('retryAfter'):
                JOB['message'] = f"YouTube is limiting downloads from this Mac. Paused for {(result['retryAfter'] + 59) // 60} minutes; try again later."
                break
            if not result['checked']:
                JOB['message'] = 'Every numbered episode in the playlist has been transcribed.'
                break
            JOB['done'] += 1
            JOB['added'] += result['added']
            JOB['addedIds'] += result['addedIds']
        else:
            JOB['message'] = 'Stopped.' if JOB['stop'] and JOB['done'] < count else ''
    except Exception as error:
        JOB['message'] = str(error) or 'Transcription failed. Your queue is unchanged; try again.'
    finally:
        JOB['message'] = JOB['message'] or f"Transcribed {JOB['done']} episode(s) and added {JOB['added']} candidate(s)."
        JOB.update(running=False, current='')
        REFRESH_LOCK.release()


def start_whisper(count):
    if type(count) is not int or not 1 <= count <= 50:
        raise ValueError('Choose between 1 and 50 episodes.')
    if not REFRESH_LOCK.acquire(blocking=False):
        raise ValueError('Transcription is already running.')
    JOB.update(running=True, stop=False, total=count, done=0, added=0, addedIds=[], current='Reading the playlist…', message='')
    threading.Thread(target=run_whisper, args=(count,), daemon=True).start()
    return dict(JOB)


def manual_draft(body):
    text = str(body.get('quote', '')).strip()
    title = str(body.get('episodeTitle', '')).strip()
    show, episode = body.get('show'), body.get('episode')
    if not 1 <= len(text) <= 2000 or not title or len(title) > 300:
        raise ValueError('Enter the quote and episode title.')
    if show not in ('RP', 'FF') or type(episode) is not int or episode < 1:
        raise ValueError('Choose the show and a valid episode number.')
    source = str(body.get('sourceUrl', '')).strip()
    if source and not source.startswith('https://'):
        raise ValueError('Source links must start with https://.')
    # Same text in the same episode receives the same ID, preventing double-click duplicates.
    key = hashlib.sha256(f'{show}:{episode}:{normalize(text)}'.encode()).hexdigest()[:20]
    return dict(id='manual_'+key, quote=text, speaker=None, show=show, episode=episode,
        episodeTitle=title, timestamp=None, timestampSeconds=None, youtubeVideoId=None,
        listenUrl=None, weatherTags=[], tags=[], source=dict(provider='Manual entry', url=source),
        review=dict(status='draft', reviewer='', sourceUrl=source, checkedAt='',
                    notes='Manually added. Verify recording, speaker credits, and timing before approval.'))


def add_draft(body):
    q = manual_draft(body)
    head = gh('git/ref/heads/main')['object']['sha']
    base = gh('git/commits/' + head)['tree']['sha']
    entries = gh('git/trees/' + base + '?recursive=1')
    if entries.get('truncated'):
        raise ValueError('Vault is too large for this operation.')
    if any(e['path'] in ('drafts/'+q['id']+'.json', 'quotes/'+q['id']+'.json') for e in entries['tree']):
        raise ValueError('This manual quote is already in the vault.')
    tree = gh('git/trees', dict(base_tree=base, tree=[dict(path='drafts/'+q['id']+'.json', mode='100644',
        type='blob', content=json.dumps(q, indent=2, ensure_ascii=False)+'\n')]), 'POST')['sha']
    commit = gh('git/commits', dict(message='Add manually entered quote for review', tree=tree, parents=[head]), 'POST')['sha']
    gh('git/refs/heads/main', dict(sha=commit, force=False), 'PATCH')
    subprocess.run(['git', 'pull', '--ff-only'], cwd=ROOT, capture_output=True, timeout=45, check=True)
    return dict(id=q['id'], message='Quote saved to drafts. No transcripts were pulled and nothing was published to the app.')


def remove_draft(draft):
    head = gh('git/ref/heads/main')['object']['sha']
    base = gh('git/commits/' + head)['tree']['sha']
    entries = gh('git/trees/' + base + '?recursive=1')
    if entries.get('truncated'):
        raise ValueError('Vault is too large for this operation.')
    path = 'drafts/' + draft['id'] + '.json'
    if json_blob(entries['tree'], path) != draft:
        raise ValueError('This draft changed on GitHub. Reload it before removing.')
    removed = {**draft, 'review': {**draft.get('review', {}), 'status':'quarantined',
        'quarantineReason':'Removed by reviewer', 'removedAt':datetime.datetime.now(datetime.timezone.utc).isoformat()}}
    changes = [dict(path='quarantine/'+draft['id']+'.json', mode='100644', type='blob',
                    content=json.dumps(removed, indent=2, ensure_ascii=False)+'\n'),
               dict(path=path, mode='100644', type='blob', sha=None)]
    tree = gh('git/trees', dict(base_tree=base, tree=changes), 'POST')['sha']
    commit = gh('git/commits', dict(message='Remove rejected quote from review queue', tree=tree, parents=[head]), 'POST')['sha']
    gh('git/refs/heads/main', dict(sha=commit, force=False), 'PATCH')
    subprocess.run(['git', 'pull', '--ff-only'], cwd=ROOT, capture_output=True, timeout=45, check=True)
    return dict(message='Quote removed. Its wording is blocked from automatic collection; a copy is kept in quarantine on GitHub.')


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(15)
    def reply(self, status, data, kind='application/json'):
        payload = json.dumps(data).encode() if kind == 'application/json' else data
        self.send_response(status)
        self.send_header('Content-Type', kind)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; frame-src https://www.youtube-nocookie.com; media-src https:; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(payload)
    def allowed(self):
        return self.headers.get('Host') in {f'{host}:{self.server.server_port}' for host in self.server.allowed_hosts}
    def authenticated(self):
        return self.client_address[0] == '127.0.0.1' or secrets.compare_digest(self.headers.get('X-Pair-Token', ''), TOKEN)
    def pair(self):
        with PAIR_LOCK:
            now = time.monotonic()
            PAIR_ATTEMPTS[:] = [stamp for stamp in PAIR_ATTEMPTS if now-stamp < 300]
            if len(PAIR_ATTEMPTS) >= 10:
                return self.reply(429, {'error':'Too many pairing attempts. Wait five minutes.'})
            PAIR_ATTEMPTS.append(now)
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size < 1024:
                raise ValueError()
            code = json.loads(self.rfile.read(size)).get('code','')
            if not isinstance(code, str) or not secrets.compare_digest(code.strip().lower(), PAIR_CODE):
                return self.reply(401, {'error':'Pairing code does not match. Check the code shown on your Mac.'})
            return self.reply(200, {'token':TOKEN})
        except (ValueError, TypeError):
            return self.reply(400, {'error':'Enter the pairing code shown on your Mac.'})
    def do_GET(self):
        if not self.allowed():
            return self.reply(403, {'error':'Use the local dashboard address.'})
        if self.path == '/api/whisper':
            if not self.authenticated():
                return self.reply(401, {'error':'Pair this phone with the code shown on your Mac.'})
            return self.reply(200, dict(JOB))
        if self.path == '/api/queue':
            if not self.authenticated():
                return self.reply(401, {'error':'Pair this phone with the code shown on your Mac.'})
            approved = [json.loads(p.read_text()) for p in (ROOT/'quotes').glob('*.json')]
            rows = []
            for p in sorted((ROOT/'drafts').glob('*.json')):
                q = json.loads(p.read_text())
                rows.append(dict(quote=q, fingerprint=hashlib.sha256(p.read_bytes()).hexdigest(),
                    suggestion=suggestion(q, approved), audioUrl=MEDIA.get(normalize(q['episodeTitle']))))
            return self.reply(200, dict(rows=rows, token=TOKEN, approved=len(approved), archiveEpisodes=json.loads((ROOT/'inbox/rtarchive_episodes.json').read_text())))
        files = {'/':'index.html', '/app.js':'app.js', '/style.css':'style.css'}
        if self.path not in files:
            return self.reply(404, {'error':'Not found'})
        name = files[self.path]
        return self.reply(200, (ROOT/'dashboard'/name).read_bytes(), {'html':'text/html; charset=utf-8','js':'text/javascript','css':'text/css'}[name.split('.')[-1]])
    def do_POST(self):
        origin = f"http://{self.headers.get('Host')}"
        if self.path == '/api/pair':
            if not self.allowed() or self.headers.get('Origin') != origin:
                return self.reply(403, {'error':'Use the dashboard address shown on your Mac.'})
            return self.pair()
        if not self.allowed() or not self.authenticated() or self.headers.get('Origin') != origin or not secrets.compare_digest(self.headers.get('X-Review-Token',''), TOKEN):
            return self.reply(403, {'error':'Refresh the local dashboard and try again.'})
        if self.path == '/api/whisper/stop':
            JOB['stop'] = True
            return self.reply(200, dict(JOB))
        if self.path not in ('/api/approve', '/api/drafts', '/api/remove', '/api/whisper'):
            return self.reply(404, {'error':'Not found'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size < 32768:
                raise ValueError('Invalid request size')
            body = json.loads(self.rfile.read(size))
            if self.path == '/api/whisper':
                return self.reply(200, start_whisper(body.get('count')))
            if self.path == '/api/drafts':
                return self.reply(200, add_draft(body))
            if not re.fullmatch('[a-z0-9_]+', body['id']):
                raise ValueError('Invalid quote')
            path = ROOT/'drafts'/(body['id']+'.json')
            if hashlib.sha256(path.read_bytes()).hexdigest() != body['fingerprint']:
                raise ValueError('Draft changed; refresh the queue.')
            draft = json.loads(path.read_text())
            if self.path == '/api/remove':
                return self.reply(200, remove_draft(draft))
            # Fail locally before any GitHub writes.
            validate(prepare(draft, body['edits'], 'pending'), json.loads((ROOT/'catalog.json').read_text())['retiredIds'])
            return self.reply(200, publish(draft, body['edits']))
        except Exception as error:
            return self.reply(400, {'error':str(error) or 'Review incomplete. Check the speaker, timestamp, source, and tags.'})
    def log_message(self, *_):
        pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--lan-ip', help='Private IPv4 address of this Mac for phone access')
    args = parser.parse_args()
    if args.lan_ip:
        address = ipaddress.ip_address(args.lan_ip)
        if address.version != 4 or not address.is_private or address.is_loopback:
            parser.error('--lan-ip must be your private LAN IPv4 address')
    load_media()
    # Another program (or a second dashboard) may already hold the port: use the next free one.
    for port in range(args.port, args.port + 20):
        try:
            server = ThreadingHTTPServer(('0.0.0.0' if args.lan_ip else '127.0.0.1', port), Handler)
            break
        except OSError:
            continue
    else:
        raise SystemExit(f'Ports {args.port}-{args.port + 19} are all in use. Close another dashboard and try again.')
    server.allowed_hosts = {'127.0.0.1'} | ({args.lan_ip} if args.lan_ip else set())
    if args.lan_ip:
        print(f'Phone: http://{args.lan_ip}:{port}  Pairing code: {PAIR_CODE}', flush=True)
    print(f'Review dashboard: http://127.0.0.1:{port}', flush=True)
    server.serve_forever()
