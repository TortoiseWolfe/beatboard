import { describe, it } from 'node:test';
import assert from 'node:assert';
import { nearestNote, planNote } from '../src/sampler.js';

const pack = {
  oneshot: false,
  notes: {
    48: { hold_s: 2.0, length_s: 4.0, release_s: 2.0 },
    51: { hold_s: 2.0, length_s: 4.0, release_s: 2.0 },
    54: { hold_s: 2.0, length_s: 4.0, release_s: 2.0 },
  },
};

describe('sampler: nearest recorded note', () => {
  it('a recorded key plays as recorded', () => {
    const r = nearestNote(pack, 51);
    assert.strictEqual(r.recorded, 51);
    assert.strictEqual(r.rate, 1);
  });

  it('an unrecorded key is repitched from the nearest one by the right number of semitones', () => {
    const up = nearestNote(pack, 52);
    assert.strictEqual(up.recorded, 51);
    assert.ok(Math.abs(up.rate - Math.pow(2, 1 / 12)) < 1e-9);
    const down = nearestNote(pack, 50);
    assert.strictEqual(down.recorded, 51);
    assert.ok(Math.abs(down.rate - Math.pow(2, -1 / 12)) < 1e-9);
  });

  it('a tie goes to the lower recorded note, so the sound is repitched up, never down', () => {
    // 49.5 is not a key; between 48 and 51 the middle is 49.5, so use a grid with an even gap
    const even = { notes: { 40: pack.notes[48], 44: pack.notes[48] } };
    assert.strictEqual(nearestNote(even, 42).recorded, 40);
  });

  it('keys beyond the ends repitch from the end note', () => {
    assert.strictEqual(nearestNote(pack, 60).recorded, 54);
    assert.strictEqual(nearestNote(pack, 40).recorded, 48);
  });

  it('an empty pack is refused', () => {
    assert.throws(() => nearestNote({ notes: {} }, 60));
  });
});

describe('sampler: how long a note sounds', () => {
  it('a note held as long as the recording plays straight through, with no fade', () => {
    const p = planNote(pack, 51, 2.0);
    assert.strictEqual(p.fadeAtS, null);
    assert.strictEqual(p.endS, 4.0);
  });

  it('a short note fades from its own end over the release, and still rings after it ends', () => {
    const p = planNote(pack, 51, 0.5);
    assert.strictEqual(p.fadeAtS, 0.5);
    assert.ok(p.fadeS >= 0.12 && p.fadeS <= 0.6);
    assert.ok(p.endS > 0.5, 'sound continues after the key is let go');
  });

  it('a repitched note scales the hold: a higher note has a shorter recording to hold', () => {
    // 54 played one octave up from 51 is not in range, so use 57 -> from 54 at rate 2^(3/12)
    const p = planNote(pack, 57, 1.6); // 1.6 * 1.189 = 1.9 < 2.0 -> still a short note
    assert.notStrictEqual(p.fadeAtS, null);
    const q = planNote(pack, 57, 1.8); // 1.8 * 1.189 = 2.14 >= 2.0 -> plays through
    assert.strictEqual(q.fadeAtS, null);
  });

  it('a one-shot always plays to the end, however short the key press', () => {
    const drums = { oneshot: true, notes: { 36: { hold_s: 0.1, length_s: 1.5, release_s: 0 } } };
    const p = planNote(drums, 36, 0.01);
    assert.strictEqual(p.fadeAtS, null);
    assert.strictEqual(p.endS, 1.5);
  });

  it('no length given means play through', () => {
    assert.strictEqual(planNote(pack, 51, undefined).fadeAtS, null);
  });
});
