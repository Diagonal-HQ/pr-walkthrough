"""Free narration from the operating system, or explicit silent preview audio."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from common import duration


def make_line(project, line, provider, spoken, dry=False):
    if dry:
        return None
    out = Path(project) / 'audio' / 'vo'
    out.mkdir(parents=True, exist_ok=True)
    wav = out / (line['id'] + '.wav')
    signature = hashlib.sha256(json.dumps([spoken, provider, line.get('duration')]).encode()).hexdigest()
    meta = out / (line['id'] + '.local.json')
    if not (wav.exists() and meta.exists() and json.loads(meta.read_text()).get('signature') == signature):
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / 'speech.wav'
            if provider == 'silent':
                seconds = line.get('duration', max(2, len(spoken.split()) / 160 * 60))
                subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=mono', '-t', str(seconds), str(raw)], check=True)
            elif shutil.which('say'):
                text = Path(tmp) / 'text.txt'
                text.write_text(spoken)
                raw = Path(tmp) / 'speech.aiff'
                subprocess.run(['say', '-r', '160', '-f', str(text), '-o', str(raw)], check=True)
            elif shutil.which('espeak-ng') or shutil.which('espeak'):
                executable = shutil.which('espeak-ng') or shutil.which('espeak')
                subprocess.run([executable, '-s', '160', '-w', str(raw), '--stdin'], input=spoken, text=True, check=True)
            else:
                raise SystemExit('Local speech needs macOS say or Linux espeak-ng. Install it, or select --provider silent for a silent preview.')
            temporary = out / (line['id'] + '.part.wav')
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(raw), '-ar', '48000', '-ac', '1', str(temporary)], check=True)
            temporary.replace(wav)
            meta.write_text(json.dumps({'signature': signature}))
        (out / (line['id'] + '.alignment.json')).unlink(missing_ok=True)
    return {'text': line['text'], 'spoken': spoken, 'duration': round(duration(str(wav)), 3),
            'chars': len(spoken), 'rendered': False, 'provider': provider}
