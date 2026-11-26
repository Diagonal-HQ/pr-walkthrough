"""Project validation, ElevenLabs HTTP calls, and media helpers. Standard library only."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import urllib.error
import urllib.request

API = 'https://api.elevenlabs.io'
SCRIPTS = os.path.dirname(os.path.abspath(__file__))


def project_dir(arg=None):
    raw = arg or os.environ.get('WALKTHROUGH_PROJECT')
    if not raw:
        raise SystemExit('Set WALKTHROUGH_PROJECT or pass --project <directory>.')
    path = Path(raw).expanduser().resolve()
    parent = path
    while not parent.exists() and parent != parent.parent:
        parent = parent.parent
    result = subprocess.run(['git', '-C', str(parent), 'rev-parse', '--show-toplevel'], capture_output=True, text=True)
    if result.returncode == 0:
        root = result.stdout.strip()
        probe = str(path / 'video.json')
        ignored = subprocess.run(['git', '-C', root, 'check-ignore', '-q', probe]).returncode == 0
        tracked = subprocess.check_output(['git', '-C', root, 'ls-files', '--', str(path)], text=True).strip()
        if tracked or not ignored:
            raise SystemExit(f'Output must be git-ignored. Add .walkthrough/ to the project .gitignore and use it: {path}')
    return str(path)


def api_key():
    key = os.environ.get('ELEVENLABS_API_KEY', '').strip()
    if not key:
        raise SystemExit('Export ELEVENLABS_API_KEY, or use --provider local. Credentials are never loaded from shell startup files.')
    return key, 'process environment'


def call(method, path, body=None, headers=None, timeout=180):
    key, _ = api_key()
    request_headers = {'xi-api-key': key, **(headers or {})}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        request_headers['Content-Type'] = 'application/json'
    request = urllib.request.Request(API + path, data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read(), dict(response.headers)
    except urllib.error.HTTPError as error:
        # Response bodies can contain request text. Report only the status.
        raise SystemExit(f'ElevenLabs request failed (HTTP {error.code}). Check the API key, permissions, and provider account.') from error


def duration(path):
    return float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path], text=True))


def narration_pauses(alignment, limit=0.6):
    characters = alignment.get('characters', [])
    starts = alignment.get('character_start_times_seconds', [])
    ends = alignment.get('character_end_times_seconds', [])
    pauses, previous = [], ''
    for index, (character, start, end) in enumerate(zip(characters, starts, ends)):
        seconds = round(end - start, 6)
        if character == ' ' and seconds >= limit and previous and previous not in '.,:;?!':
            pauses.append((seconds, ''.join(characters[max(0, index - 30):index])))
        if not character.isspace():
            previous = character
    return pauses


def load_video(project):
    file = Path(project) / 'video.json'
    if not file.exists():
        raise SystemExit(f'{file} is missing. Run init first.')
    video = json.loads(file.read_text())
    lines = video.get('lines')
    if not isinstance(lines, list) or not lines:
        raise SystemExit('video.json needs a non-empty lines array.')
    ids = set()
    for line in lines:
        lid = line.get('id')
        if not isinstance(lid, str) or not re.fullmatch(r'[a-zA-Z0-9_-]+', lid) or lid in ids:
            raise SystemExit('Line ids must be unique and use letters, digits, underscores, or hyphens.')
        ids.add(lid)
        if line.get('on', 'capture') not in ('capture', 'title', 'section', 'end'):
            raise SystemExit(f'{lid}: on must be capture, title, section, or end.')
        if 'text' in line and (not isinstance(line['text'], str) or not line['text'].strip()):
            raise SystemExit(f'{lid}: text must be non-empty, or omit text for a silent card.')
        if 'duration' in line and (not isinstance(line['duration'], (int, float)) or not math.isfinite(line['duration']) or line['duration'] <= 0):
            raise SystemExit(f'{lid}: duration must be a positive number.')
    return video


def args_with_project(argv):
    rest, project = [], None
    it = iter(argv)
    for arg in it:
        if arg == '--project':
            project = next(it, None)
            if not project:
                raise SystemExit('--project needs a directory.')
        else:
            rest.append(arg)
    return project_dir(project), rest


def source_fingerprint(project):
    """Detect changes to the inputs used by a built timeline."""
    root = Path(project)
    files = [root / 'video.json', root / 'audio/vo/manifest.json']
    files += sorted((root / 'footage').glob('*.json'))
    files += sorted((root / 'audio/vo').glob('*.alignment.json'))
    digest = hashlib.sha256()
    for file in files:
        digest.update(str(file.relative_to(root)).encode())
        digest.update(file.read_bytes() if file.exists() else b'MISSING')
    for file in sorted((root / 'footage').glob('*.mp4')) + sorted((root / 'audio/vo').glob('*.wav')):
        stat = file.stat()
        digest.update(f'{file.relative_to(root)}:{stat.st_size}:{stat.st_mtime_ns}'.encode())
    return digest.hexdigest()
