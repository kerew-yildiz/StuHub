// Usage: node make-pdf.mjs <browserExe> <input.html> <output.pdf>
import { spawn } from 'node:child_process';
import { writeFileSync, rmSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { tmpdir } from 'node:os';

const [, , exe, input, output] = process.argv;
if (!exe || !input || !output) { console.error('usage: node make-pdf.mjs <exe> <input.html> <output.pdf>'); process.exit(2); }

const port = 9200 + Math.floor(Math.random() * 200);
const prof = join(tmpdir(), `archify-pdf-${Date.now()}`);
const browser = spawn(exe, ['--headless=new', '--disable-gpu', '--no-first-run', `--remote-debugging-port=${port}`, `--user-data-dir=${prof}`, 'about:blank'], { stdio: 'ignore' });
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
let wsUrl;
for (let i = 0; i < 40; i++) { try { const r = await fetch(`http://127.0.0.1:${port}/json/version`); if (r.ok) { wsUrl = (await r.json()).webSocketDebuggerUrl; break; } } catch {} await wait(250); }
if (!wsUrl) { console.error('CDP never came up'); process.exit(1); }
const ws = new WebSocket(wsUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
let id = 0; const pending = new Map();
ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const send = (method, params = {}, sessionId) => new Promise((res) => { const mid = ++id; pending.set(mid, res); ws.send(JSON.stringify({ id: mid, method, params, ...(sessionId ? { sessionId } : {}) })); });
const { result: { targetId } } = await send('Target.createTarget', { url: 'about:blank' });
const { result: { sessionId } } = await send('Target.attachToTarget', { targetId, flatten: true });
await send('Page.enable', {}, sessionId);
await send('Emulation.setDeviceMetricsOverride', { width: 1280, height: 1000, deviceScaleFactor: 1, mobile: false }, sessionId);
await send('Page.navigate', { url: 'file:///' + resolve(input).replace(/\\/g, '/') }, sessionId);
await wait(3000);
const { result: pr } = await send('Page.printToPDF', {
  printBackground: true, paperWidth: 8.27, paperHeight: 11.69, marginTop: 0.4, marginBottom: 0.4, marginLeft: 0, marginRight: 0, preferCSSPageSize: false,
}, sessionId);
if (!pr || !pr.data) { console.error('printToPDF failed', JSON.stringify(pr).slice(0, 300)); process.exit(1); }
writeFileSync(output, Buffer.from(pr.data, 'base64'));
console.log(`PDF written: ${output}`);
ws.close(); browser.kill();
try { rmSync(prof, { recursive: true, force: true }); } catch {}
process.exit(0);
