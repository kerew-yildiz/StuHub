// Export clean SVG-crop PNGs of each delivered diagram for print use.
// Usage: node export-images.mjs <browserExe> <outDir> <html...>
import { spawn } from 'node:child_process';
import { mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { basename, join, resolve } from 'node:path';
import { tmpdir } from 'node:os';

const [, , exe, outDir, ...htmls] = process.argv;
if (!exe || !outDir || htmls.length === 0) { console.error('usage: node export-images.mjs <exe> <outDir> <html...>'); process.exit(2); }
mkdirSync(outDir, { recursive: true });

const port = 9400 + Math.floor(Math.random() * 300);
const prof = join(tmpdir(), `archify-img-${Date.now()}`);
const browser = spawn(exe, ['--headless=new', '--disable-gpu', '--no-first-run', `--remote-debugging-port=${port}`, `--user-data-dir=${prof}`, 'about:blank'], { stdio: 'ignore' });
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
let wsUrl;
for (let i = 0; i < 40; i++) { try { const r = await fetch(`http://127.0.0.1:${port}/json/version`); if (r.ok) { wsUrl = (await r.json()).webSocketDebuggerUrl; break; } } catch {} await wait(250); }
const ws = new WebSocket(wsUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
let id = 0; const pending = new Map();
ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const send = (method, params = {}, sessionId) => new Promise((res) => { const mid = ++id; pending.set(mid, res); ws.send(JSON.stringify({ id: mid, method, params, ...(sessionId ? { sessionId } : {}) })); });
const { result: { targetId } } = await send('Target.createTarget', { url: 'about:blank' });
const { result: { sessionId } } = await send('Target.attachToTarget', { targetId, flatten: true });
for (const m of ['Page.enable', 'Runtime.enable']) await send(m, {}, sessionId);
await send('Emulation.setDeviceMetricsOverride', { width: 1600, height: 1000, deviceScaleFactor: 2, mobile: false }, sessionId);

for (const html of htmls) {
  await send('Page.navigate', { url: 'file:///' + resolve(html).replace(/\\/g, '/') }, sessionId);
  await wait(2200);
  const { result } = await send('Runtime.evaluate', { expression: `JSON.stringify(document.querySelector('svg').getBoundingClientRect())`, returnByValue: true }, sessionId);
  const r = JSON.parse(result.result.value);
  const { result: shot } = await send('Page.captureScreenshot', { format: 'png', clip: { x: Math.max(0, r.x - 8), y: Math.max(0, r.y - 8), width: r.width + 16, height: r.height + 16, scale: 1 } }, sessionId);
  const out = join(outDir, basename(html, '.html') + '.png');
  writeFileSync(out, Buffer.from(shot.data, 'base64'));
  console.log(`${basename(out)}: ${Math.round(r.width)}x${Math.round(r.height)} css-px @2x`);
}
ws.close(); browser.kill();
try { rmSync(prof, { recursive: true, force: true }); } catch {}
process.exit(0);
