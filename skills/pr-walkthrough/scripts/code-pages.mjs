#!/usr/bin/env node
// Builds the page that a code walkthrough films: one slide for each entry of <project>/code.json.
// A code slide shows one region of one file at the base or the head ref. The changed lines are highlighted.
// A files slide lists the changed files with their added and removed line counts.
// usage: node code-pages.mjs            (WALKTHROUGH_PROJECT must be set)
// out:   <project>/code/index.html. A scene opens it with d.goto('file://...') and shows a slide with d.eval("show('<id>')").
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { codeToHtml } from 'shiki';
import { projectDir, readConfig } from './project.mjs';

const MAX_LINES = 22;     // more rows than this do not fit 1440x810 at a readable size
const MAX_COLUMNS = 116;  // a longer line wraps to a second row; a little under the 120 that fit, because wraps break at spaces
const LANGS = { php: 'php', ts: 'ts', tsx: 'tsx', js: 'js', mjs: 'js', jsx: 'jsx', json: 'json', md: 'md', yml: 'yaml', yaml: 'yaml', sql: 'sql', css: 'css', sh: 'bash', py: 'python', html: 'html' };

const project = projectDir(process.env.WALKTHROUGH_PROJECT);
if (!project) { console.error('usage: node code-pages.mjs   (set WALKTHROUGH_PROJECT)'); process.exit(2); }
const specPath = path.join(project, 'code.json');
if (!fs.existsSync(specPath)) { console.error(`${specPath} is missing. See references/code-walkthrough.md for its format.`); process.exit(2); }
const spec = JSON.parse(fs.readFileSync(specPath, 'utf8'));
const config = readConfig(project);
const repo = path.resolve(project, spec.repo || config.repo || process.cwd());
const git = (...args) => execFileSync('git', ['-C', repo, ...args], { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
const refs = { base: spec.base, head: spec.head || 'HEAD' };
if (!refs.base) { console.error('code.json: set "base", for example "origin/main".'); process.exit(2); }
for (const ref of Object.values(refs)) { if (typeof ref !== 'string' || ref.startsWith('-')) throw new Error('Refs must be git revision names, not options.'); }
const mergeBase = git('merge-base', refs.base, refs.head).trim();
const sha = { base: mergeBase, head: git('rev-parse', refs.head).trim() };

// The lines that the diff changes in a file, on each side, as 1-based line numbers.
function changedLines(file) {
  const out = git('diff', '-U0', '--no-color', sha.base, sha.head, '--', file);
  const lines = { base: new Set(), head: new Set() };
  for (const m of out.matchAll(/^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@/gm)) {
    const [a, b, c, d] = [+m[1], m[2] === undefined ? 1 : +m[2], +m[3], m[4] === undefined ? 1 : +m[4]];
    for (let i = 0; i < b; i++) lines.base.add(a + i);
    for (let i = 0; i < d; i++) lines.head.add(c + i);
  }
  return lines;
}

const parseRange = (text, label) => {
  const m = /^(\d+)-(\d+)$/.exec(String(text || ''));
  if (!m || +m[1] < 1 || +m[1] > +m[2]) throw new Error(`${label}: write a line range such as "40-58".`);
  return [+m[1], +m[2]];
};

const escape = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
const errors = [];
const warnings = [];
const slides = [];
const ids = new Set();

for (const [n, slide] of (spec.slides || []).entries()) {
  const label = `slides[${n}] ${slide.id || ''}`.trim();
  if (!slide.id || ids.has(slide.id)) { errors.push(`${label}: each slide needs a unique id.`); continue; }
  ids.add(slide.id);

  if (slide.kind === 'files') {
    const rows = git('diff', '--numstat', sha.base, sha.head).trim().split('\n').filter(Boolean)
      .map((row) => row.split('\t')).filter(([, , file]) => !(slide.exclude || []).some((p) => file.includes(p)));
    if (rows.length > MAX_LINES) warnings.push(`${label}: ${rows.length} files; the slide shows the first ${MAX_LINES}. Use "exclude" to drop generated or test files.`);
    const list = rows.slice(0, MAX_LINES).map(([add, del, file]) =>
      `<li><span class="add">+${escape(add)}</span><span class="del">−${escape(del)}</span><code>${escape(file)}</code></li>`).join('');
    slides.push(`<section id="${escape(slide.id)}"><header><h1>${escape(slide.title || 'What changed')}</h1></header><ul class="files">${list}</ul></section>`);
    continue;
  }

  const side = slide.ref === 'base' ? 'base' : slide.ref === 'head' ? 'head' : null;
  if (!side) { errors.push(`${label}: "ref" must be "base" or "head".`); continue; }
  if (!slide.file) { errors.push(`${label}: set "file".`); continue; }
  let range;
  try { range = parseRange(slide.lines, label); } catch (e) { errors.push(e.message); continue; }
  const [from, to] = range;

  let source;
  try { source = git('show', `${sha[side]}:${slide.file}`); } catch { errors.push(`${label}: ${slide.file} does not exist at ${side} (${sha[side].slice(0, 10)}).`); continue; }
  const all = source.split('\n');
  if (to > all.length) { errors.push(`${label}: ${slide.file} has ${all.length} lines at ${side}.`); continue; }
  const code = all.slice(from - 1, to).join('\n');
  const rows = all.slice(from - 1, to).reduce((sum, l) => sum + Math.max(1, Math.ceil(l.replace(/\t/g, '    ').length / MAX_COLUMNS)), 0);
  if (rows > MAX_LINES) { errors.push(`${label}: ${to - from + 1} lines fill ${rows} rows after long lines wrap. Show ${MAX_LINES} rows or fewer; pick the lines that the narration talks about.`); continue; }

  let marked;
  if (slide.highlight) {
    try { const [a, b] = parseRange(slide.highlight, `${label} highlight`); marked = new Set(Array.from({ length: b - a + 1 }, (_, i) => a + i)); } catch (e) { errors.push(e.message); continue; }
  } else {
    marked = changedLines(slide.file)[side];
  }
  const shown = [...marked].filter((l) => l >= from && l <= to).length;
  if (!shown && !slide.highlight) warnings.push(`${label}: no changed line is in ${slide.lines}. Check the range, or set "highlight".`);

  const lang = LANGS[path.extname(slide.file).slice(1)] || 'text';
  const html = await codeToHtml(code, {
    lang: slide.file.endsWith('.blade.php') ? 'blade' : lang,
    theme: 'github-light',
    transformers: [{ line(node, line) { if (marked.has(from + line - 1)) this.addClassToHast(node, side === 'base' ? 'hl del-line' : 'hl add-line'); } }],
  });
  const tag = side === 'base' ? '<span class="tag before">Before</span>' : '<span class="tag after">After</span>';
  slides.push(`<section id="${escape(slide.id)}"><header>${tag}<code class="path">${escape(slide.file)}</code>${slide.title ? `<h1>${escape(slide.title)}</h1>` : ''}</header><div class="code" style="counter-reset: line ${from - 1}">${html}</div></section>`);
}

warnings.forEach((w) => console.error('WARN  ' + w));
if (errors.length) { errors.forEach((e) => console.error('ERROR ' + e)); process.exit(1); }
if (!slides.length) { console.error('ERROR code.json has no slides.'); process.exit(1); }

const page = `<!doctype html><html><head><meta charset="utf-8"><title>${escape(spec.title || 'Code walkthrough')}</title><style>
html, body { margin: 0; height: 100%; background: #f6f7f9; font-family: Inter, ui-sans-serif, system-ui, sans-serif; color: #111827; overflow: hidden; }
section { display: none; box-sizing: border-box; height: 100vh; padding: 36px 56px; flex-direction: column; gap: 20px; }
section.on { display: flex; }
header { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
header h1 { flex-basis: 100%; margin: 4px 0 0; font-size: 26px; font-weight: 600; letter-spacing: -0.01em; }
.path { font: 500 18px ui-monospace, SFMono-Regular, Menlo, monospace; color: #374151; }
.tag { font-size: 15px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; padding: 5px 12px; border-radius: 999px; }
.tag.before { background: #fee2e2; color: #991b1b; }
.tag.after { background: #dcfce7; color: #166534; }
.code { flex: 1; min-height: 0; background: #fff; border: 1px solid #e5e7eb; border-radius: 14px; padding: 18px 0; overflow: hidden; }
.code pre { margin: 0; background: transparent !important; font: 17px/26px ui-monospace, SFMono-Regular, Menlo, monospace; }
.code code { display: flex; flex-direction: column; }
.code .line { padding: 0 24px 0 72px; text-indent: -72px; white-space: pre-wrap; overflow-wrap: anywhere; counter-increment: line; }
.code .line::before { content: counter(line); display: inline-block; width: 52px; margin-right: 20px; text-align: right; color: #9ca3af; }
.code .hl.del-line { background: #fef2f2; box-shadow: inset 4px 0 #ef4444; }
.code .hl.add-line { background: #f0fdf4; box-shadow: inset 4px 0 #22c55e; }
.files { list-style: none; margin: 0; padding: 18px 24px; background: #fff; border: 1px solid #e5e7eb; border-radius: 14px; font: 17px/26px ui-monospace, SFMono-Regular, Menlo, monospace; }
.files .add { display: inline-block; width: 64px; color: #15803d; }
.files .del { display: inline-block; width: 64px; color: #b91c1c; }
</style></head><body>
${slides.join('\n')}
<script>
window.show = (id) => { const next = document.getElementById(id); if (!next) return false; document.querySelectorAll('section.on').forEach((s) => s.classList.remove('on')); next.classList.add('on'); return true; };
const fromHash = () => show(location.hash.slice(1)) || show(document.querySelector('section').id);
addEventListener('hashchange', fromHash);
fromHash();
</script></body></html>`;

const outDir = path.join(project, 'code');
fs.mkdirSync(outDir, { recursive: true });
fs.writeFileSync(path.join(outDir, 'index.html'), page);
console.log(`code pages: ${slides.length} slide(s), base ${sha.base.slice(0, 10)}, head ${sha.head.slice(0, 10)}`);
console.log(`url: file://${path.join(outDir, 'index.html')}`);
