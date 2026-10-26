/**
 * PATTERNS TESTS — presets deep-copied on load
 */
import { describe, it } from 'node:test';
import assert from 'node:assert';
import { getPreset, getAllPresets, getDefaultPreset, presetNames } from '../src/patterns.js';

describe('patterns', () => {
  it('presetNames has 5 presets, Hip Hop first', () => {
    assert.equal(presetNames.length, 5);
    assert.equal(presetNames[0], 'Hip Hop');
  });

  it('getPreset returns deep copy (mutation does not affect source)', () => {
    const p1 = getPreset('Hip Hop');
    const p2 = getPreset('Hip Hop');
    p1[0].pattern[0] = 999;
    p1[0].muted = true;
    const p3 = getPreset('Hip Hop');
    assert.equal(p3[0].pattern[0], 1);
    assert.equal(p3[0].muted, false);
  });

  it('getPreset returns null for unknown name', () => {
    assert.equal(getPreset('Unknown'), null);
  });

  it('getAllPresets returns deep copies of all', () => {
    const all = getAllPresets();
    assert.equal(Object.keys(all).length, 5);
    all['Hip Hop'][0].pattern[0] = 999;
    const fresh = getPreset('Hip Hop');
    assert.equal(fresh[0].pattern[0], 1);
  });

  it('getDefaultPreset returns Hip Hop', () => {
    const def = getDefaultPreset();
    assert.equal(def[0].name, 'Kick');
    assert.equal(def.length, 8);
  });

  it('each preset has 8 tracks with pattern array of length 8', () => {
    for (const name of presetNames) {
      const p = getPreset(name);
      assert.equal(p.length, 8);
      for (const track of p) {
        assert.ok(Array.isArray(track.pattern));
        assert.equal(track.pattern.length, 8);
        assert.ok(typeof track.muted === 'boolean');
        assert.ok(typeof track.volume === 'number');
        assert.ok(typeof track.name === 'string');
      }
    }
  });

  it('Hip Hop preset has expected drum pattern', () => {
    const p = getPreset('Hip Hop');
    assert.deepEqual(p[0].pattern, [1, 0, 0, 0, 0, 0, 1, 0]); // Kick
    assert.deepEqual(p[1].pattern, [0, 0, 1, 0, 0, 0, 1, 0]); // Snare
    assert.deepEqual(p[2].pattern, [1, 0, 1, 0, 1, 0, 1, 0]); // Hats
    assert.deepEqual(p[3].pattern, [0, 1, 0, 1, 0, 1, 0, 1]); // Perc
  });

  it('Waltz preset has 3/4 feel (kick on 1 and 4)', () => {
    const p = getPreset('Waltz');
    assert.deepEqual(p[0].pattern, [1, 0, 0, 1, 0, 0, 0, 0]);
  });
});