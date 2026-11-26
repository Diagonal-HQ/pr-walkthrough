import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

export function projectDir(value = process.env.WALKTHROUGH_PROJECT) {
  if (!value) throw new Error('Set WALKTHROUGH_PROJECT or pass --project <directory>.');
  const requested = path.resolve(value);
  let parent = requested;
  while (!fs.existsSync(parent)) parent = path.dirname(parent);
  const project = path.join(fs.realpathSync(parent), path.relative(parent, requested));
  parent = fs.realpathSync(parent);
  const result = spawnSync('git', ['-C', parent, 'rev-parse', '--show-toplevel'], { encoding: 'utf8' });
  if (result.status === 0) {
    const root = result.stdout.trim();
    const ignored = spawnSync('git', ['-C', root, 'check-ignore', '-q', path.join(project, 'video.json')]).status === 0;
    const tracked = spawnSync('git', ['-C', root, 'ls-files', '--', project], { encoding: 'utf8' });
    if (!ignored || tracked.stdout.trim()) throw new Error(`Output must be git-ignored. Add .walkthrough/ to .gitignore and use it: ${project}`);
  }
  return project;
}

export function readConfig(project) {
  const file = path.join(project, 'walkthrough.json');
  return fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, 'utf8')) : {};
}
