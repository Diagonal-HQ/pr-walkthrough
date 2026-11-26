"""Optional upload through the AWS CLI. Credentials stay in the AWS credential chain."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import urllib.request
from urllib.parse import quote, urlparse
import uuid
from common import project_dir

parser = argparse.ArgumentParser()
parser.add_argument('--project')
parser.add_argument('--dry-run', action='store_true')
parser.add_argument('file', nargs='?')
args = parser.parse_args()
project = Path(project_dir(args.project))
config_file = project / 'walkthrough.json'
config = json.loads(config_file.read_text()).get('publish', {}) if config_file.exists() else {}
if not args.file:
    raise SystemExit('Pass the video path to upload. Nothing is uploaded automatically.')
video = Path(args.file).resolve()
if not video.is_file() or video.suffix.lower() != '.mp4':
    raise SystemExit('Choose an existing MP4 file.')
if video.stat().st_size > 50 * 1024 * 1024:
    raise SystemExit('Video exceeds 50 MB. Trim or re-encode it before upload.')
bucket, base = config.get('bucket'), config.get('publicBaseUrl')
if not bucket or not re.fullmatch(r'[a-z0-9][a-z0-9.-]+', bucket):
    raise SystemExit('Set publish.bucket in walkthrough.json.')
if not base or urlparse(base).scheme != 'https' or urlparse(base).query or urlparse(base).fragment:
    raise SystemExit('Set publish.publicBaseUrl to the HTTPS public bucket URL, without a query or fragment.')
prefix = config.get('prefix', 'walkthroughs').strip('/')
if not re.fullmatch(r'[a-zA-Z0-9/_-]+', prefix):
    raise SystemExit('publish.prefix uses letters, digits, slashes, underscores, or hyphens.')
key = f'{prefix}/{uuid.uuid4().hex}.mp4'
url = base.rstrip('/') + '/' + quote(key, safe='/')
command = ['aws']
if config.get('endpoint'):
    if urlparse(config['endpoint']).scheme != 'https':
        raise SystemExit('publish.endpoint must use HTTPS.')
    command += ['--endpoint-url', config['endpoint']]
command += ['s3', 'cp', str(video), f's3://{bucket}/{key}', '--content-type', 'video/mp4', '--only-show-errors']
if args.dry_run:
    print(f'Would upload {video.name} ({video.stat().st_size} bytes) to s3://{bucket}/{key}\nPublic URL: {url}\nNo request made.')
else:
    subprocess.run(command, check=True)
    request = urllib.request.Request(url, method='HEAD')
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise SystemExit('Upload completed, but the public URL is not readable. Check bucket routing before linking it.')
    print(url)
