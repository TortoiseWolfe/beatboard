import { describe, it } from 'node:test';
import assert from 'node:assert';
import { Engine } from '../src/engine.js';

describe('game piano names to MIDI keys', () => {
  it('maps the game octave so c1 is middle C', () => {
    assert.strictEqual(Engine.noteNameToMidi('c1'), 60);
    assert.strictEqual(Engine.noteNameToMidi('c2'), 72);
    assert.strictEqual(Engine.noteNameToMidi('b1'), 71);
    assert.strictEqual(Engine.noteNameToMidi('a1'), 69);
  });

  it('reads the s suffix as a sharp', () => {
    assert.strictEqual(Engine.noteNameToMidi('c1s'), 61);
    assert.strictEqual(Engine.noteNameToMidi('a1s'), 70);
  });

  it('returns null for names that are not notes', () => {
    assert.strictEqual(Engine.noteNameToMidi('x'), null);
    assert.strictEqual(Engine.noteNameToMidi('f#3'), null);
  });
});

describe('engine with no pack loaded', () => {
  it('playPackNote returns null and loadPack without an audio context is false', async () => {
    const e = new Engine();
    assert.strictEqual(e.playPackNote('ivory', 60, 0, null), null);
    assert.strictEqual(await e.loadPack('ivory', 'assets/packs/ivory'), false);
  });
});
