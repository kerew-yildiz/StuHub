// CDP-based screenshot + containment evidence collector (no deps, Node 22+).
// Usage: node snap.mjs <browserExe> <outDir> <html1> [html2 ...]
// Captures each HTML at 1440x900, 1600x1000, 1920x1080 and records
// scrollWidth/scrollHeight containment + saves the 1600x1000 @2x image for print.

import { spawn } from 'node:child_process';
import { mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { basename, join, resolve } from 'node:path';
import { tmpdir } from 'node:os';

const [, , exe, outDir, ...htmls] = process.argv;
if (!exe || !outDir || htmls.length === 0) {
  console.error('usage: node snap.mjs <browserExe> <outDir> <html...>');
  process.exit(2);
}
mkdirSync(outDir, { recursive: true });

const port = 9900 + Math.floor(Math.random() * 500);
const prof = join(tmpdir(), `archify-snap-${Date.now()}`);

const browser = spawn(exe, [
  '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
  `--remote-debugging-port=${port}`, `--user-data-dir=${prof}`, 'about:blank',
], { stdio: 'ignore' });

const wait = (ms) => new Promise((r) => setTimeout(r, ms));

async function cdpUrl() {
  for (let i = 0; i < 40; i++) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/json/version`);
      if (res.ok) return (await res.json()).webSocketDebuggerUrl;
    } catch {}
    await wait(250);
  }
  throw new Error('browser did not expose CDP');
}

const wsUrl = await cdpUrl();
const ws = new WebSocket(wsUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });

let id = 0;
const pending = new Map();
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
};
function send(method, params = {}, sessionId) {
  return new Promise((res) => {
    const mid = ++id;
    pending.set(mid, res);
    ws.send(JSON.stringify({ id: mid, method, params, ...(sessionId ? { sessionId } : {}) }));
  });
}

const { result: { targetId } } = await send('Target.createTarget', { url: 'about:blank' });
const { result: { sessionId } } = await send('Target.attachToTarget', { targetId, flatten: true });
for (const m of ['Page.enable', 'Runtime.enable', 'Emulation.enable']) await send(m, {}, sessionId);

const report = [];
for (const html of htmls) {
  const file = resolve(html);
  const name = basename(file, '.html');
  const entry = { name, viewports: [], images: [] };
  for (const [w, h, scale, tag] of [[1440, 900, 1, '1440x900'], [1600, 1000, 2, '1600x1000@2x'], [1920, 1080, 1, '1920x1080']]) {
    await send('Emulation.setDeviceMetricsOverride', { width: w, height: h, deviceScaleFactor: scale, mobile: false }, sessionId);
    await send('Page.navigate', { url: 'file:///' + file.replace(/\\/g, '/') }, sessionId);
    await wait(2200);
    const { result } = await send('Runtime.evaluate', {
      expression: `JSON.stringify({sw:document.documentElement.scrollWidth,sh:document.documentElement.scrollHeight,iw:window.innerWidth,ih:window.innerHeight,title:document.title})`,
      returnByValue: true,
    }, sessionId);
    const m = JSON.parse(result.result.value);
    entry.viewports.push({ tag, ...m, contained: m.sw <= m.iw && m.sh <= m.ih });
    if (tag === '1600x1000@2x') {
      const { result: shot } = await send('Page.captureScreenshot', { format: 'png' }, sessionId);
      const img = join(outDir, `${name}.png`);
      writeFileSync(img, Buffer.from(shot.data, 'base64'));
      entry.images.push(img);
    }
  }
  report.push(entry);
  console.log(`${name}: ${entry.viewports.map(v => `${v.tag} contained=${v.contained}`).join('  ')}`);
}

writeFileSync(join(outDir, 'browser-evidence.json'), JSON.stringify(report, null, 2));
ws.close();
browser.kill();
try { rmSync(prof, { recursive: true, force: true }); } catch {}
process.exit(0);
