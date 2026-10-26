/**
 * AUDIO OUTPUT TEST — measures real sound, not page errors.
 *
 * Headless Chromium loads the page, an init script wraps AudioNode.prototype.connect
 * so anything wired to ctx.destination also feeds an AnalyserNode, then the real keys
 * from keymap.default.json are pressed. Every kind of track must put non-silent signal
 * on the output. Set BASE_URL to run against the live site instead of a local server.
 *
 *   npm i && npx playwright install chromium && npm run test:audio
 */
import { describe, it, before, after } from 'node:test';
import assert from 'node:assert';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const MIN_PEAK = 0.01; // about -40 dBFS; a real hit is far above, silence is exactly 0
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json', '.css': 'text/css', '.mp3': 'audio/mpeg', '.png': 'image/png', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml' };

function serve() {
  const server = http.createServer((req, res) => {
    const rel = decodeURIComponent(new URL(req.url, 'http://x').pathname);
    const file = path.join(ROOT, rel.endsWith('/') ? rel + 'index.html' : rel);
    if (!file.startsWith(ROOT) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
      res.writeHead(404); res.end(); return;
    }
    res.writeHead(200, { 'content-type': TYPES[path.extname(file)] || 'application/octet-stream' });
    fs.createReadStream(file).pipe(res);
  });
  return new Promise(resolve => server.listen(0, '127.0.0.1', () => resolve(server)));
}

// Runs before any page script. Anything connected to a destination also feeds an analyser.
function tapOutput() {
  const tap = { peak: 0, an: null, buf: null, ctxs: [] };
  window.__tap = tap;
  const origConnect = AudioNode.prototype.connect;
  AudioNode.prototype.connect = function (dest, ...rest) {
    const r = origConnect.call(this, dest, ...rest);
    if (dest instanceof AudioDestinationNode && !tap.an) {
      const an = this.context.createAnalyser();
      an.fftSize = 2048;
      an.smoothingTimeConstant = 0;
      origConnect.call(this, an);
      tap.an = an;
      tap.buf = new Float32Array(an.fftSize);
      tap.ctxs.push(this.context);
    }
    return r;
  };
  setInterval(() => {
    if (!tap.an) return;
    tap.an.getFloatTimeDomainData(tap.buf);
    for (const v of tap.buf) tap.peak = Math.max(tap.peak, Math.abs(v));
  }, 4);
}

describe('audio output (headless Chromium, real keys)', () => {
  let server, browser, page, base;
  const problems = [];
  const peaks = {};

  before(async () => {
    if (process.env.BASE_URL) base = process.env.BASE_URL.replace(/\/$/, '');
    else { server = await serve(); base = `http://127.0.0.1:${server.address().port}`; }
    browser = await chromium.launch({ args: ['--autoplay-policy=document-user-activation-required'] });
    page = await browser.newPage();
    page.on('pageerror', e => problems.push('pageerror: ' + e.message));
    page.on('console', m => { if (m.type() === 'error') problems.push('console: ' + m.text()); });
    await page.addInitScript(tapOutput);
    await page.goto(base + '/', { waitUntil: 'networkidle' });
    await page.waitForFunction(() => document.querySelector('.mixer-track'), null, { timeout: 15000 });
  });

  after(async () => {
    console.log('peaks:', JSON.stringify(peaks));
    await browser?.close();
    server?.close();
  });

  async function press(code, ms) {
    await page.evaluate(() => { window.__tap.peak = 0; });
    await page.keyboard.press(code);
    await page.waitForTimeout(ms);
    return page.evaluate(() => window.__tap.peak);
  }

  async function reset() {
    await page.keyboard.press('Escape');
    await page.waitForTimeout(150);
  }

  const cases = [
    ['kick (drums)', 'KeyD', 800],
    ['snare (drums)', 'KeyJ', 800],
    ['hats', 'KeyS', 800],
    ['perc clap', 'KeyA', 800],
    ['bass boom', 'KeyG', 800],
    ['piano C', 'KeyQ', 1200],
    ['piano E', 'KeyE', 1200],
    ['fx quarter flip', 'KeyV', 1500],
    ['jingle hook', 'KeyZ', 2500],
    ['jingle full', 'KeyX', 2500],
  ];

  for (const [name, code, ms] of cases) {
    it(`${name} (${code}) is audible on the output`, async () => {
      const peak = await press(code, ms);
      peaks[name] = +peak.toFixed(4);
      await reset();
      assert.ok(peak > MIN_PEAK, `${name}: peak ${peak} on ctx.destination, expected > ${MIN_PEAK}`);
    });
  }

  it('bed loop (Digit7) is audible on the output', async () => {
    // launches quantized to the next bar (about 2.2 s at 110 BPM), so wait past it
    const peak = await press('Digit7', 5000);
    peaks['bed loop'] = +peak.toFixed(4);
    await reset();
    assert.ok(peak > MIN_PEAK, `bed loop: peak ${peak}, expected > ${MIN_PEAK}`);
  });

  it('sequencer (Enter) is audible on the output', async () => {
    const peak = await press('Enter', 2500);
    peaks['sequencer'] = +peak.toFixed(4);
    await reset();
    assert.ok(peak > MIN_PEAK, `sequencer: peak ${peak}, expected > ${MIN_PEAK}`);
  });

  it('the AudioContext is running after the first key press', async () => {
    const states = await page.evaluate(() => window.__tap.ctxs.map(c => c.state));
    assert.ok(states.length > 0, 'no AudioContext reached a destination');
    assert.ok(states.every(s => s === 'running'), `context states: ${states}`);
  });

  it('a single click on the page unlocks audio (no key needed)', async () => {
    const fresh = await browser.newPage();
    await fresh.addInitScript(tapOutput);
    await fresh.goto(base + '/', { waitUntil: 'networkidle' });
    await fresh.waitForFunction(() => document.querySelector('.mixer-track'), null, { timeout: 15000 });
    const before = await fresh.evaluate(() => window.__tap.ctxs.map(c => c.state));
    await fresh.mouse.click(5, 5);
    await fresh.waitForTimeout(400);
    const after = await fresh.evaluate(() => window.__tap.ctxs.map(c => c.state));
    await fresh.close();
    assert.deepStrictEqual(before, ['suspended'], 'context should start suspended under the autoplay policy');
    assert.deepStrictEqual(after, ['running'], 'a click should resume the context');
  });

  it('the page logged no errors', async () => {
    assert.deepStrictEqual(problems, [], 'page errors: ' + problems.join(' | '));
  });
});
