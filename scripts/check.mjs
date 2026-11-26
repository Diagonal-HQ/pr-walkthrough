import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
const files = [];
function walk(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    if (['node_modules', '.git', '.walkthrough', '__pycache__'].includes(entry.name)) continue;
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) walk(file); else files.push(file);
  }
}
walk('.');
for (const file of files) {
  if (file.endsWith('.mjs')) {
    const result = spawnSync(process.execPath, ['--check', file], { stdio: 'inherit' });
    if (result.status !== 0) process.exit(result.status || 1);
  }
  if (file.endsWith('.json')) JSON.parse(fs.readFileSync(file, 'utf8'));
  if (file.endsWith('.md')) {
    const text = fs.readFileSync(file, 'utf8');
    for (const match of text.matchAll(/\]\(([^)]+)\)/g)) {
      const link = match[1];
      if (/^(https?:|#|<)/.test(link) || link.includes('$')) continue;
      const target = link.split('#')[0];
      if (target && !fs.existsSync(path.resolve(path.dirname(file), target))) {
        throw new Error(`${file}: missing Markdown target ${link}`);
      }
    }
  }
}
const pythonFiles = files.filter((file) => file.endsWith('.py'));
const result = spawnSync(process.env.PYTHON || 'python3', ['-c', 'import ast,sys; [ast.parse(open(p).read(), filename=p) for p in sys.argv[1:]]', ...pythonFiles], { stdio: 'inherit' });
if (result.status !== 0) process.exit(result.status || 1);

const installed = JSON.parse(fs.readFileSync('skills/pr-walkthrough/package.json', 'utf8'));
const rootLock = JSON.parse(fs.readFileSync('package-lock.json', 'utf8'));
const skillLock = JSON.parse(fs.readFileSync('skills/pr-walkthrough/package-lock.json', 'utf8'));
for (const [name, version] of Object.entries(installed.dependencies)) {
  if (rootLock.packages['skills/pr-walkthrough'].dependencies[name] !== version || skillLock.packages[''].dependencies[name] !== version) {
    throw new Error(`Lockfile dependency mismatch: ${name}`);
  }
}

console.log(`Checked ${files.length} source and documentation files.`);
