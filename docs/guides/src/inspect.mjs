// Usage: node inspect.mjs <browserExe> <html> [width] [height]
import { spawn } from 'node:child_process';
import { resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const [, , exe, html, W = '1440', H = '900'] = process.argv;
const port = 9700 + Math.floor(Math.random() * 200);
const prof = join(tmpdir(), `archify-insp-${Date.now()}`);
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
await send('Page.enable', {}, sessionId);
await send('Emulation.setDeviceMetricsOverride', { width: +W, height: +H, deviceScaleFactor: 1, mobile: false }, sessionId);
await send('Page.navigate', { url: 'file:///' + resolve(html).replace(/\\/g, '/') }, sessionId);
await wait(2200);
const { result } = await send('Runtime.evaluate', { expression: `
(() => {
  const walk = (el, depth, out) => {
    if (depth > 3) return;
    for (const c of el.children) {
      const r = c.getBoundingClientRect();
      if (r.height > 8) out.push('  '.repeat(depth) + c.tagName.toLowerCase() + (c.id ? '#'+c.id : '') + (c.className && typeof c.className === 'string' ? '.'+c.className.split(' ').slice(0,2).join('.') : '') + ' h=' + Math.round(r.height) + ' top=' + Math.round(r.top));
      walk(c, depth + 1, out);
    }
  };
  const out = [];
  walk(document.body, 0, out);
  return 'sw=' + document.documentElement.scrollWidth + ' sh=' + document.documentElement.scrollHeight + ' iw=' + innerWidth + ' ih=' + innerHeight + '\\n' + out.slice(0, 40).join('\\n');
})()`, returnByValue: true }, sessionId);
console.log(result.result.value);
ws.close(); browser.kill();
try { const { rmSync } = await import('node:fs'); rmSync(prof, { recursive: true, force: true }); } catch {}
process.exit(0);
