/**
 * KIT MEASURING SCRIPT TESTS (tools/kits/measure.mjs)
 * Synthetic audio only: every case has a known right answer.
 */
import { describe, it } from 'node:test';
import assert from 'node:assert';
import {
  decodeWav, encodeWav, expectedSamples, integratedLufs, offsetMs, gridPhase, seamClick,
  measureKit, normaliseStems, gridLockKit, shiftStem,
} from '../tools/kits/measure.mjs';

const FS = 48000;
const BPM = 120; // 500 ms beats keep the synthetic cases easy to read

function silent(sec) { return new Float32Array(Math.round(sec * FS)); }

// A short click-like note (decaying 1 kHz burst) every `everyMs`, the first one at `startMs`.
function notes(sec, everyMs, startMs, freq = 1000) {
  const ch = silent(sec);
  for (let t = startMs; t < sec * 1000; t += everyMs) {
    const s0 = Math.round((t * FS) / 1000);
    for (let i = 0; i < 2400 && s0 + i < ch.length; i++) {
      ch[s0 + i] += 0.8 * Math.exp(-i / 500) * Math.sin((2 * Math.PI * freq * i) / FS);
    }
  }
  return ch;
}

// Notes on an irregular pattern, so the stem has no beat of its own.
function irregular(sec, offsetMsShift) {
  const ch = silent(sec);
  let t = 137 + offsetMsShift;
  let k = 0;
  while (t < sec * 1000 - 100) {
    const s0 = Math.round((t * FS) / 1000);
    for (let i = 0; i < 1800; i++) ch[s0 + i] += 0.7 * Math.exp(-i / 400) * Math.sin((2 * Math.PI * 800 * i) / FS);
    t += 173 + ((k * 7919) % 11) * 43;
    k++;
  }
  return ch;
}

function sine(sec, freq, amp) {
  const ch = silent(sec);
  for (let i = 0; i < ch.length; i++) ch[i] = amp * Math.sin((2 * Math.PI * freq * i) / FS);
  return ch;
}

function stem(chs) { return { sampleRate: FS, frames: chs[0].length, data: chs }; }

describe('wav round trip', () => {
  it('encodes and decodes float samples exactly', () => {
    const a = sine(0.1, 440, 0.5);
    const back = decodeWav(encodeWav(stem([a, a])));
    assert.strictEqual(back.sampleRate, FS);
    assert.strictEqual(back.frames, a.length);
    assert.strictEqual(back.data[0][1234], a[1234]);
  });
});

describe('length', () => {
  it('16 bars at 112 BPM is 1645714 samples at 48 kHz', () => {
    assert.strictEqual(expectedSamples(16, 112, 48000), 1645714);
  });

  it('flags a stem that is one sample short', () => {
    const n = expectedSamples(1, BPM, FS);
    const ok = new Float32Array(n);
    const short = new Float32Array(n - 1);
    const r = measureKit([stem([ok]), stem([short])], { bpm: BPM, bars: 1 });
    assert.strictEqual(r.checks.length.ok, false);
  });
});

describe('loudness', () => {
  it('reads the EBU Tech 3341 reference tone (1 kHz sine, -23 dBFS peak, both channels) as -23.0 LUFS (+-0.1)', () => {
    const amp = 10 ** (-23 / 20);
    const lufs = integratedLufs([sine(20, 1000, amp), sine(20, 1000, amp)], FS);
    assert.ok(Math.abs(lufs - -23.0) < 0.1, `got ${lufs}`);
  });

  it('moves one-for-one with gain: doubling the amplitude adds 6.02 LU', () => {
    const a = integratedLufs([sine(6, 1000, 0.1), sine(6, 1000, 0.1)], FS);
    const b = integratedLufs([sine(6, 1000, 0.2), sine(6, 1000, 0.2)], FS);
    assert.ok(Math.abs(b - a - 6.0206) < 0.01, `step ${b - a}`);
  });

  it('flags a spread of more than 1 LU and clears it after normalising', () => {
    const loud = stem([sine(6, 1000, 0.5)]);
    const quiet = stem([sine(6, 1000, 0.1)]);
    const raw = measureKit([loud, quiet], { bpm: BPM });
    assert.strictEqual(raw.checks.loudness.ok, false);
    const fixed = measureKit(normaliseStems([loud, quiet], -20).map((g) => g.stem), { bpm: BPM });
    assert.strictEqual(fixed.checks.loudness.ok, true);
  });

  it('refuses a normalise that would clip', () => {
    const peaky = silent(6);
    peaky[24000] = 0.9; // one loud sample in an otherwise quiet stem
    const quietBody = sine(6, 200, 0.001);
    for (let i = 0; i < peaky.length; i++) peaky[i] += quietBody[i];
    const [n] = normaliseStems([stem([peaky])], -14);
    assert.strictEqual(n.ok, false);
  });
});

describe('alignment', () => {
  it('finds a 3 ms shifted copy', () => {
    const a = notes(8, 500, 20);
    const b = notes(8, 500, 23);
    const r = offsetMs([a], [b], FS);
    assert.strictEqual(r.ms, 3);
  });

  it('finds no offset between identical parts', () => {
    const a = irregular(10, 0);
    assert.strictEqual(offsetMs([a], [a], FS).ms, 0);
  });

  it('measures how far a stem sits from the beat grid, and locks it', () => {
    // The onset curve sees a note's attack a little after its first sample, so an on-grid reference
    // stem gives the zero point; what must hold is the 28 ms difference from it, and that lock removes it.
    const ref = gridPhase(notes(12, 500, 0), FS, BPM).ms;
    const drums = stem([notes(12, 500, 28)]); // 28 ms late against a 120 BPM grid
    const g = gridPhase(drums.data, FS, BPM);
    assert.ok(Math.abs(g.ms - ref - 28) <= 2.5, `phase ${g.ms} vs reference ${ref}`);
    const locked = gridLockKit([drums], BPM);
    assert.strictEqual(locked.locked, true);
    const after = gridPhase(locked.stems[0].data, FS, BPM);
    assert.ok(Math.abs(after.ms - ref) <= 2.5, `after lock ${after.ms} vs reference ${ref}`);
    assert.strictEqual(locked.stems[0].frames, drums.frames); // length untouched
  });

  it('moves every stem in a kit by the same amount, keeping their timing against each other', () => {
    const drums = stem([notes(12, 500, 28)]);
    const other = stem([notes(12, 250, 28, 600)]);
    const before = offsetMs(drums.data, other.data, FS).ms;
    const locked = gridLockKit([drums, other], BPM);
    const after = offsetMs(locked.stems[0].data, locked.stems[1].data, FS).ms;
    assert.strictEqual(after, before);
  });

  it('shifts by whole samples without changing length', () => {
    const s = stem([notes(2, 500, 100)]);
    const moved = shiftStem(s, 10);
    assert.strictEqual(moved.frames, s.frames);
    assert.strictEqual(moved.data[0].length, s.data[0].length);
  });

  it('leaves a stem with no beat alone', () => {
    // A pad: a steady tone swelling slowly, with no note attacks to lock to.
    const pad = sine(12, 220, 0.3);
    for (let i = 0; i < pad.length; i++) pad[i] *= 0.6 + 0.4 * Math.sin((2 * Math.PI * 0.13 * i) / FS);
    const r = gridLockKit([stem([pad])], BPM);
    assert.strictEqual(r.locked, false);
  });

  it('fails a kit whose beat-keeping stems are more than 5 ms off the grid, passes once locked', () => {
    const n = expectedSamples(8, BPM, FS);
    const cut = (ch) => ch.subarray(0, n);
    const late = stem([cut(notes(16, 500, 28))]);
    const onGrid = stem([cut(notes(16, 500, 0))]);
    assert.strictEqual(measureKit([late, onGrid], { bpm: BPM, bars: 8 }).checks.offset.ok, false);
    const fixed = [late, onGrid].map((s) => shiftStem(s, gridPhase(s.data, FS, BPM).ms));
    assert.strictEqual(measureKit(fixed, { bpm: BPM, bars: 8 }).checks.offset.ok, true);
  });
});

describe('loop seam', () => {
  it('flags a step across the seam', () => {
    const ch = sine(4, 220, 0.05);
    ch[0] = 0.9; // first sample far from the last one
    assert.strictEqual(seamClick([ch]).ok, false);
  });

  it('does not flag a continuous sine that ends where it starts', () => {
    const periods = 440; // whole number of cycles in 4 s, so the loop is seamless
    const ch = silent(4);
    for (let i = 0; i < ch.length; i++) ch[i] = 0.5 * Math.sin((2 * Math.PI * periods * i) / ch.length);
    assert.strictEqual(seamClick([ch]).ok, true);
  });
});
