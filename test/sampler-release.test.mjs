/**
 * SAMPLER RELEASE TEST — real sound in headless Chromium.
 *
 * Builds a small pack on disk (a sine that holds, then rings out), loads it with PackPlayer, plays one note that is
 * let go early, renders it with an OfflineAudioContext, and measures the samples:
 *   - sound continues after the key is let go (the release rings out),
 *   - it fades smoothly to silence (no drop of more than 6 dB between neighbouring 10 ms windows),
 *   - a note stopped dead with source.stop() fails the same smoothness check, so the check can tell the two apart.
 */
import { describe, it, before, after } from 'node:test';
import assert from 'node:assert';
import http from 'node:http';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const RATE = 22050;
const HOLD = 0.5;
const LENGTH = 2.0;

function wav(samples) {
  const b = Buffer.alloc(44 + samples.length * 2);
  b.write('RIFF', 0); b.writeUInt32LE(36 + samples.length * 2, 4); b.write('WAVEfmt ', 8);
  b.writeUInt32LE(16, 16); b.writeUInt16LE(1, 20); b.writeUInt16LE(1, 22); b.writeUInt32LE(RATE, 24);
  b.writeUInt32LE(RATE * 2, 28); b.writeUInt16LE(2, 32); b.writeUInt16LE(16, 34); b.write('data', 36);
  b.writeUInt32LE(samples.length * 2, 40);
  samples.forEach((v, i) => b.writeInt16LE(Math.round(v * 32767), 44 + i * 2));
  return b;
}

function note(hz) {
  const n = Math.round(LENGTH * RATE);
  return Array.from({ length: n }, (_, i) => {
    const t = i / RATE;
    const env = t < HOLD ? 0.5 : 0.5 * Math.exp(-3 * (t - HOLD));  // held, then the instrument's own release
    return env * Math.sin(2 * Math.PI * hz * t);
  });
}

describe('sampler release (headless Chromium)', () => {
  let server, browser, page, base, dir;

  before(async () => {
    dir = fs.mkdtempSync(path.join(os.tmpdir(), 'pack-'));
    const notes = {};
    for (const [key, hz] of [[60, 261.63], [64, 329.63]]) {
      fs.writeFileSync(path.join(dir, `t-${key}.wav`), wav(note(hz)));
      notes[key] = { files: { wav: `t-${key}.wav` }, hold_s: HOLD, length_s: LENGTH, release_s: LENGTH - HOLD, gain_db: 0 };
    }
    fs.writeFileSync(path.join(dir, 'pack.json'), JSON.stringify({ member: 'Test', oneshot: false, notes }));
    server = http.createServer((req, res) => {
      const p = decodeURIComponent(new URL(req.url, 'http://x').pathname);
      if (p === '/__blank') { res.writeHead(200, { 'content-type': 'text/html' }); res.end('<!doctype html><title>t</title>'); return; }
      const file = p.startsWith('/__pack/') ? path.join(dir, p.slice(8)) : path.join(ROOT, p);
      const ok = (p.startsWith('/__pack/') ? file.startsWith(dir) : file.startsWith(ROOT)) && fs.existsSync(file) && fs.statSync(file).isFile();
      if (!ok) { res.writeHead(404); res.end(); return; }
      const type = file.endsWith('.js') ? 'text/javascript' : file.endsWith('.json') ? 'application/json' : file.endsWith('.wav') ? 'audio/wav' : 'application/octet-stream';
      res.writeHead(200, { 'content-type': type });
      fs.createReadStream(file).pipe(res);
    });
    await new Promise(r => server.listen(0, '127.0.0.1', r));
    base = `http://127.0.0.1:${server.address().port}`;
    browser = await chromium.launch();
    page = await browser.newPage();
    await page.goto(base + '/__blank');
  });

  after(async () => {
    await browser?.close();
    server?.close();
    fs.rmSync(dir, { recursive: true, force: true });
  });

  // Renders key 62 (repitched from 60), let go after 0.25 s, 2.5 s long. mode 'cut' stops the source dead instead of fading.
  async function render(mode) {
    return page.evaluate(async ({ base, mode }) => {
      const { PackPlayer } = await import(base + '/src/sampler.js');
      const sr = 44100;
      const ctx = new OfflineAudioContext(1, sr * 2.5, sr);
      const player = new PackPlayer(ctx);
      await player.load('test', base + '/__pack');
      if (mode === 'cut') {
        const { buffers } = player.packs.get('test');
        const src = ctx.createBufferSource();
        src.buffer = buffers.get(60);
        src.playbackRate.value = Math.pow(2, 2 / 12);
        src.connect(ctx.destination);
        src.start(0);
        src.stop(0.25);
      } else {
        player.play('test', 62, 0, ctx.destination, 0.25);
      }
      const out = await ctx.startRendering();
      return { sr, data: Array.from(out.getChannelData(0)) };
    }, { base, mode });
  }

  function windows(data, sr, ms = 10) {
    const n = Math.round((sr * ms) / 1000);
    const out = [];
    for (let i = 0; i + n <= data.length; i += n) {
      let s = 0;
      for (let k = 0; k < n; k++) s += data[i + k] ** 2;
      out.push(Math.sqrt(s / n));
    }
    return out;
  }

  function worstDropDb(w, floor = 0.01) {
    let worst = 0;
    for (let i = 1; i < w.length; i++) {
      if (w[i - 1] > floor) worst = Math.max(worst, 20 * Math.log10(w[i - 1] / Math.max(w[i], 1e-6)));
    }
    return worst;
  }

  it('the note is audible while held', async () => {
    const { sr, data } = await render('fade');
    const w = windows(data, sr);
    assert.ok(w[10] > 0.1, `rms at 0.1 s is ${w[10]}`);
  });

  it('sound continues after the key is let go, then dies away smoothly', async () => {
    const { sr, data } = await render('fade');
    const w = windows(data, sr);
    assert.ok(w[30] > 0.03, `0.05 s after release, rms ${w[30]}: the release must still be ringing`);
    assert.ok(w[40] > 0.01, `0.15 s after release, rms ${w[40]}`);
    assert.ok(w[w.length - 5] < 0.005, 'ends in silence');
    assert.ok(worstDropDb(w) < 6, `worst 10 ms drop ${worstDropDb(w).toFixed(1)} dB: that is a cut`);
  });

  it('the same check does catch a note stopped dead', async () => {
    const { sr, data } = await render('cut');
    assert.ok(worstDropDb(windows(data, sr)) > 20);
  });
});
