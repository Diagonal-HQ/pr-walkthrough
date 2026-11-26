import { Director, byText, byLabel, hasText } from '__SKILL_URL__/scripts/director.mjs';
const d = await Director.connect();
try {
  await d.goto('__DEMO_URL__');
  await d.waitFor(hasText('5 tasks'));
  await d.moveTo(1200, 650, 10);
  await d.startCapture('main');
  await d.beat('orient');
  await d.beat('filter', async () => {
    await d.click(byText('button', 'Open only'));
    await d.waitFor(hasText('3 tasks'));
  });
  await d.beat('name', async () => {
    await d.click(byText('button', 'Save view'));
    await d.click(byLabel('View name'));
    await d.type('Open work', 65);
    await d.moveTo(1100, 600);
  });
  await d.beat('save', async () => {
    await d.click(byText('button', 'Save'));
    await d.waitFor(hasText('Open work'));
    await d.moveTo(1200, 650);
  });
  console.log(JSON.stringify(await d.stopCapture(), null, 2));
} finally {
  await d.close();
}
