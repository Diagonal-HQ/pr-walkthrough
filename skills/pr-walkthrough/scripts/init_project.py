"""Create editable project files. Existing projects are never overwritten."""
import argparse
import json
from pathlib import Path
import shutil
from common import project_dir

parser = argparse.ArgumentParser()
parser.add_argument('directory')
parser.add_argument('--preset', choices=['feature-clip', 'product-walkthrough', 'code-walkthrough'], default='feature-clip')
args = parser.parse_args()
project = Path(project_dir(args.directory))
if (project / 'video.json').exists():
    raise SystemExit(f'{project}/video.json already exists. Use it or select another output directory.')
skill = Path(__file__).resolve().parent.parent
for folder in ('footage', 'audio/vo', 'scenes', 'out', 'review'):
    (project / folder).mkdir(parents=True, exist_ok=True)
shutil.copyfile(skill / 'templates' / f'video.{args.preset}.json', project / 'video.json')
scene_name = 'scene.code.example.mjs' if args.preset == 'code-walkthrough' else 'scene.example.mjs'
scene = (skill / 'templates' / scene_name).read_text().replace('__SKILL_URL__', skill.as_uri())
if args.preset == 'product-walkthrough':
    video = json.loads((project / 'video.json').read_text())
    beats = '\n'.join(f"  await d.beat({line['id']!r});" for line in video['lines'] if line.get('on', 'capture') == 'capture')
    a = scene.index("  await d.beat('s1');"); b = scene.index('  console.log(', a)
    scene = scene[:a] + beats + '\n' + scene[b:]
(project / 'scenes/main.mjs').write_text(scene)
config = {'appUrl': 'http://localhost:3000', 'repo': str(Path.cwd())}
(project / 'walkthrough.json').write_text(json.dumps(config, indent=2) + '\n')
if args.preset == 'code-walkthrough':
    shutil.copyfile(skill / 'templates/code.example.json', project / 'code.json')
print(f'Project: {project}\nEdit video.json, walkthrough.json, and scenes/main.mjs.')
