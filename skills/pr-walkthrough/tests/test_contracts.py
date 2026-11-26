"""Check output isolation, malformed scripts, stale renders, and code slides against real git refs."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parent.parent / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from common import load_video, project_dir, source_fingerprint


def git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True, text=True).stdout.strip()


class ProjectContractsTest(unittest.TestCase):
    def test_requires_ignored_output_in_a_consuming_repo(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            git(root, 'init')
            with self.assertRaises(SystemExit):
                project_dir(str(root / 'videos/new'))
            (root / '.gitignore').write_text('.walkthrough/\n')
            self.assertEqual(project_dir(str(root / '.walkthrough/new')), str((root / '.walkthrough/new').resolve()))

    def test_refuses_output_that_is_already_tracked_even_if_ignored(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            git(root, 'init')
            output = root / '.walkthrough'
            output.mkdir()
            (output / 'old.mp4').write_bytes(b'fixture')
            git(root, 'add', '.walkthrough/old.mp4')
            (root / '.gitignore').write_text('.walkthrough/\n')
            with self.assertRaises(SystemExit):
                project_dir(str(output))

    def test_rejects_duplicate_and_path_line_ids(self):
        for ids in (['same', 'same'], ['../outside'], ['a/b']):
            with self.subTest(ids=ids), tempfile.TemporaryDirectory() as root:
                Path(root, 'video.json').write_text(json.dumps({'lines': [{'id': lid, 'text': 'A line.'} for lid in ids]}))
                with self.assertRaises(SystemExit):
                    load_video(root)

    def test_rejects_empty_text_before_audio_generation(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root, 'video.json').write_text(json.dumps({'lines': [{'id': 'one', 'text': ' '}]}))
            with self.assertRaises(SystemExit):
                load_video(root)

    def test_script_changes_invalidate_timeline_before_render(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            (root / 'video.json').write_text(json.dumps({'lines': [{'id': 'one', 'text': 'Original.'}]}))
            fingerprint = source_fingerprint(str(root))
            (root / 'timeline.json').write_text(json.dumps({'source_fingerprint': fingerprint}))
            (root / 'video.json').write_text(json.dumps({'lines': [{'id': 'one', 'text': 'Changed.'}]}))
            result = subprocess.run([sys.executable, '-B', str(SCRIPTS / 'render.py'), '--project', str(root)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Timeline inputs changed', result.stderr)
            self.assertFalse((root / 'out').exists())

    def test_init_does_not_overwrite_existing_script(self):
        with tempfile.TemporaryDirectory() as root:
            project = Path(root) / 'new'
            command = [sys.executable, '-B', str(SCRIPTS / 'init_project.py'), str(project)]
            subprocess.run(command, check=True, capture_output=True)
            (project / 'video.json').write_text('preserve this script')
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((project / 'video.json').read_text(), 'preserve this script')

    def test_silent_narration_preserves_caption_text_and_duration(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            text = 'The open tasks remain visible.'
            (root / 'video.json').write_text(json.dumps({'lines': [{'id': 'one', 'text': text, 'duration': 2.5}]}))
            subprocess.run([sys.executable, '-B', str(SCRIPTS / 'narrate.py'), '--project', str(root), '--provider', 'silent'], check=True, capture_output=True)
            row = json.loads((root / 'audio/vo/manifest.json').read_text())['one']
            self.assertEqual(row['text'], text)
            self.assertEqual(row['provider'], 'silent')
            self.assertAlmostEqual(row['duration'], 2.5, places=2)

    def test_failed_paid_synthesis_reserves_budget_before_retry(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            project = root / 'video'
            project.mkdir()
            text = 'One test line.'
            (project / 'video.json').write_text(json.dumps({'lines': [{'id': 'one', 'text': text}]}))
            code = f"""
import runpy,sys
sys.path.insert(0, {str(SCRIPTS)!r})
import common
def fail(*args, **kwargs):
    print('ATTEMPTED_SYNTHESIS')
    raise SystemExit('simulated provider connection failure')
common.call = fail
sys.argv = ['narrate.py', '--project', {str(project)!r}]
runpy.run_path({str(SCRIPTS / 'narrate.py')!r}, run_name='__main__')
"""
            env = {**os.environ, 'WALKTHROUGH_CACHE': str(root / 'cache'), 'WALKTHROUGH_TTS_BUDGET': str(len(text))}
            first = subprocess.run([sys.executable, '-B', '-c', code], env=env, capture_output=True, text=True)
            second = subprocess.run([sys.executable, '-B', '-c', code], env=env, capture_output=True, text=True)
            self.assertNotEqual(first.returncode, 0)
            self.assertIn('ATTEMPTED_SYNTHESIS', first.stdout)
            self.assertIn('Budget stop', second.stderr)
            self.assertNotIn('ATTEMPTED_SYNTHESIS', second.stdout)
            rows = [json.loads(line) for line in (root / 'cache/ledger.jsonl').read_text().splitlines()]
            self.assertEqual(sum(row['chars'] for row in rows), len(text))

    def test_switching_from_silent_to_paid_and_back_restores_silent_duration(self):
        import base64
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            project = root / 'video'
            project.mkdir()
            (project / 'video.json').write_text(json.dumps({'lines': [{'id': 'one', 'text': 'One test line.', 'duration': 2.5}]}))
            env = {**os.environ, 'WALKTHROUGH_CACHE': str(root / 'cache')}
            silent = [sys.executable, '-B', str(SCRIPTS / 'narrate.py'), '--project', str(project), '--provider', 'silent']
            subprocess.run(silent, env=env, check=True, capture_output=True)
            sound = subprocess.run(['ffmpeg', '-loglevel', 'error', '-f', 'lavfi', '-i', 'sine=frequency=220:duration=1', '-f', 'mp3', '-'], check=True, capture_output=True).stdout
            encoded = base64.b64encode(sound).decode()
            code = f"""
import json,runpy,sys
sys.path.insert(0, {str(SCRIPTS)!r})
import common
common.call = lambda *args, **kwargs: (json.dumps({{'audio_base64': {encoded!r}, 'alignment': {{}}}}).encode(), {{}})
sys.argv = ['narrate.py', '--project', {str(project)!r}]
runpy.run_path({str(SCRIPTS / 'narrate.py')!r}, run_name='__main__')
"""
            subprocess.run([sys.executable, '-B', '-c', code], env=env, check=True, capture_output=True)
            subprocess.run(silent, env=env, check=True, capture_output=True)
            row = json.loads((project / 'audio/vo/manifest.json').read_text())['one']
            self.assertEqual(row['provider'], 'silent')
            self.assertAlmostEqual(row['duration'], 2.5, places=2)

    def test_code_slides_use_the_configured_repository_and_escape_html(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            repo, project = root / 'source', root / 'video'
            repo.mkdir(); project.mkdir()
            git(repo, 'init')
            git(repo, 'config', 'user.name', 'Fixture')
            git(repo, 'config', 'user.email', 'fixture@example.com')
            code = repo / 'validate.ts'
            code.write_text('export const valid = true;\n')
            git(repo, 'add', '.')
            git(repo, 'commit', '-m', 'Fixture base')
            base = git(repo, 'rev-parse', 'HEAD')
            code.write_text('export const valid = "<script>bad()</script>";\n')
            git(repo, 'add', '.')
            git(repo, 'commit', '-m', 'Fixture head')
            (project / 'walkthrough.json').write_text(json.dumps({'repo': str(repo)}))
            (project / 'code.json').write_text(json.dumps({'base': base, 'slides': [
                {'id': 'before', 'ref': 'base', 'file': 'validate.ts', 'lines': '1-1'},
                {'id': 'after', 'ref': 'head', 'file': 'validate.ts', 'lines': '1-1'}]}))
            result = subprocess.run(['node', str(SCRIPTS / 'code-pages.mjs')], env={**os.environ, 'WALKTHROUGH_PROJECT': str(project)}, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            page = (project / 'code/index.html').read_text()
            self.assertIn('hl del-line', page)
            self.assertIn('hl add-line', page)
            self.assertNotIn('<script>bad()</script>', page)


if __name__ == '__main__':
    unittest.main()
