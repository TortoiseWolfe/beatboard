/**
 * HARD CUT-OFF CHECK TESTS (tools/kits/cutoff.mjs)
 * Synthetic audio only: every case has a known right answer.
 */
import { describe, it } from 'node:test';
import assert from 'node:assert';
import { hardCuts } from '../tools/kits/cutoff.mjs';

const FS = 48000;

// A decaying sine (time constant `tau` seconds) that starts at `startSec` and lasts `lenSec`, then stops dead.
function note(totalSec, startSec, lenSec, freq, tau) {
  const ch = new Float32Array(Math.round(totalSec * FS));
  const s0 = Math.round(startSec * FS);
  const n = Math.round(lenSec * FS);
  for (let i = 0; i < n; i++) ch[s0 + i] = 0.6 * Math.exp(-i / FS / tau) * Math.sin((2 * Math.PI * freq * i) / FS);
  return ch;
}

function mix(a, b) {
  for (let i = 0; i < a.length; i++) a[i] += b[i];
  return a;
}

describe('hardCuts', () => {
  it('a note that rings out to its natural end is not a cut', () => {
    // 2.5 s long with tau 0.4 s: the level at the end is under -50 dB, so it has died away by itself.
    const ch = note(3, 0.2, 2.5, 220, 0.4);
    assert.strictEqual(hardCuts([ch], FS).length, 0);
  });

  it('a note chopped off while still ringing is one cut, at the right time', () => {
    const ch = note(3, 0.2, 0.5, 220, 5); // slow decay, stops after 0.5 s: ends at 0.7 s
    const cuts = hardCuts([ch], FS);
    assert.strictEqual(cuts.length, 1);
    assert.ok(Math.abs(cuts[0].timeSec - 0.7) < 0.003, `cut at ${cuts[0].timeSec}`);
  });

  it('a low bass note chopped off is found too', () => {
    assert.strictEqual(hardCuts([note(3, 0.2, 0.6, 41, 5)], FS).length, 1);
  });

  it('a short tick with a fast natural decay is not a cut', () => {
    assert.strictEqual(hardCuts([note(2, 0.2, 0.3, 6000, 0.003)], FS).length, 0);
  });

  it('silence between notes and the file end are not cuts', () => {
    const a = mix(note(4, 0.1, 1.8, 330, 0.25), note(4, 2.0, 1.9, 330, 0.25));
    assert.strictEqual(hardCuts([a], FS).length, 0);
  });

  it('two chopped notes are two cuts', () => {
    const a = mix(note(4, 0.1, 0.4, 330, 5), note(4, 2.0, 0.4, 330, 5));
    assert.strictEqual(hardCuts([a], FS).length, 2);
  });
});
