import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { Director } from '__SKILL_URL__/scripts/director.mjs';
const d = await Director.connect();
try {
  await d.goto(pathToFileURL(path.join(d.project, 'code/index.html')).href);
  const show = (id) => d.eval(`show(${JSON.stringify(id)})`);
  await show('files');
  await d.hide(`document.getElementById('__cur')`);
  await d.startCapture('main');
  await d.beat('files');
  await d.beat('before', () => show('before'));
  await d.beat('why');
  await d.beat('after', () => show('after'));
  await d.beat('test', () => show('test'));
  console.log(JSON.stringify(await d.stopCapture(), null, 2));
} finally {
  await d.close();
}
