/**
 * KEYMAP TESTS — layers, learn mode, export/import round-trip
 */
import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert';
import {
  LAYERS, DEFAULT_KEYMAP, loadKeymap, saveKeymap,
  exportKeymap, importKeymap, loadLayer, saveLayer,
  createLearnMode
} from '../src/keymap.js';

// Mock localStorage
const mockStorage = {};
global.localStorage = {
  getItem: (k) => mockStorage[k] ?? null,
  setItem: (k, v) => { mockStorage[k] = v; },
  removeItem: (k) => { delete mockStorage[k]; },
  clear: () => { Object.keys(mockStorage).forEach(k => delete mockStorage[k]); }
};

describe('keymap', () => {
  beforeEach(() => {
    global.localStorage.clear();
  });

  it('DEFAULT_KEYMAP has both layers', () => {
    assert.ok(DEFAULT_KEYMAP.play);
    assert.ok(DEFAULT_KEYMAP.mix);
  });

  it('loadKeymap returns default when storage empty', () => {
    const km = loadKeymap();
    assert.deepEqual(km, DEFAULT_KEYMAP);
  });

  it('saveKeymap / loadKeymap round-trip', () => {
    const custom = JSON.parse(JSON.stringify(DEFAULT_KEYMAP));
    custom.play.KeyZ = { action: 'hit', track: 1, pad: 'kick' };
    saveKeymap(custom);
    const loaded = loadKeymap();
    assert.deepEqual(loaded, custom);
  });

  it('exportKeymap produces valid JSON', () => {
    const json = exportKeymap();
    const parsed = JSON.parse(json);
    assert.deepEqual(parsed, DEFAULT_KEYMAP);
  });

  it('importKeymap accepts valid JSON', () => {
    const custom = JSON.parse(JSON.stringify(DEFAULT_KEYMAP));
    custom.play.KeyZ = { action: 'hit', track: 1, pad: 'kick' };
    const ok = importKeymap(JSON.stringify(custom));
    assert.equal(ok, true);
    const loaded = loadKeymap();
    assert.deepEqual(loaded, custom);
  });

  it('importKeymap rejects invalid JSON', () => {
    const ok = importKeymap('not json');
    assert.equal(ok, false);
  });

  it('loadLayer returns play by default', () => {
    assert.equal(loadLayer(), LAYERS.PLAY);
  });

  it('saveLayer / loadLayer round-trip', () => {
    saveLayer(LAYERS.MIX);
    assert.equal(loadLayer(), LAYERS.MIX);
  });

  it('createLearnMode: enter/handleKey/cancel flow', () => {
    let captured = null;
    const mode = createLearnMode((code, binding) => { captured = { code, binding }; });
    assert.equal(mode.isActive(), false);
    mode.enter('hit', 3, 'snare');
    assert.equal(mode.isActive(), true);
    const handled = mode.handleKey('KeyQ', false);
    assert.equal(handled, true);
    assert.ok(captured);
    assert.equal(captured.code, 'KeyQ');
    assert.equal(captured.binding.action, 'hit');
    assert.equal(captured.binding.track, 3);
    assert.equal(captured.binding.pad, 'snare');
    assert.equal(mode.isActive(), false);
  });

  it('createLearnMode: cancel clears pending', () => {
    const mode = createLearnMode(() => {});
    mode.enter('hit', 1, 'kick');
    assert.equal(mode.isActive(), true);
    mode.cancel();
    assert.equal(mode.isActive(), false);
  });

  it('createLearnMode: shift key captured in binding', () => {
    let captured = null;
    const mode = createLearnMode((code, binding) => { captured = binding; });
    mode.enter('launch', 5, 'boom');
    mode.handleKey('KeyG', true);
    assert.equal(captured.shift, true);
  });
});