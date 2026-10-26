/**
 * KEYMAP — layers, learn mode, localStorage persistence
 * Uses event.code (physical keys) so layout-independent.
 * Ignored while a text field has focus.
 */
export const LAYERS = {
  PLAY: 'play',
  MIX: 'mix'
};

export const DEFAULT_KEYMAP = {
  play: {
    'KeyA': { action: 'hit', track: 4, pad: 'clap' },
    'KeyS': { action: 'hit', track: 3, pad: 'hatClosed' },
    'KeyD': { action: 'hit', track: 1, pad: 'kick' },
    'KeyF': { action: 'hit', track: 3, pad: 'hatOpen' },
    'KeyG': { action: 'hit', track: 5, pad: 'boom' },
    'KeyH': { action: 'hit', track: 3, pad: 'ride' },
    'KeyJ': { action: 'hit', track: 2, pad: 'snare' },
    'KeyK': { action: 'hit', track: 4, pad: 'tom' },
    'KeyL': { action: 'hit', track: 4, pad: 'tink' },
    'KeyQ': { action: 'hit', track: 6, pad: 'piano', note: 'C', sharp: false },
    'KeyW': { action: 'hit', track: 6, pad: 'piano', note: 'C', sharp: true },
    'KeyE': { action: 'hit', track: 6, pad: 'piano', note: 'D', sharp: false },
    'KeyR': { action: 'hit', track: 6, pad: 'piano', note: 'D', sharp: true },
    'KeyT': { action: 'hit', track: 6, pad: 'piano', note: 'E', sharp: false },
    'KeyY': { action: 'hit', track: 6, pad: 'piano', note: 'F', sharp: false },
    'KeyU': { action: 'hit', track: 6, pad: 'piano', note: 'F', sharp: true },
    'KeyI': { action: 'hit', track: 6, pad: 'piano', note: 'G', sharp: false },
    'KeyO': { action: 'hit', track: 6, pad: 'piano', note: 'G', sharp: true },
    'KeyP': { action: 'hit', track: 6, pad: 'piano', note: 'A', sharp: false },
    'BracketLeft': { action: 'hit', track: 6, pad: 'piano', note: 'A', sharp: true },
    'BracketRight': { action: 'hit', track: 6, pad: 'piano', note: 'B', sharp: false },
    'Backslash': { action: 'hit', track: 6, pad: 'piano', note: 'C', sharp: false, octave: 1 },
    'KeyZ': { action: 'launch', track: 8, kind: 'hook' },
    'KeyX': { action: 'launch', track: 8, kind: 'full' },
    'KeyC': { action: 'none' },
    'KeyV': { action: 'hit', track: 7, pad: 'quarterFlip' },
    'KeyB': { action: 'none' },
    'KeyN': { action: 'none' },
    'KeyM': { action: 'none' },
    'Digit1': { action: 'launch', track: 1 },
    'Digit2': { action: 'launch', track: 2 },
    'Digit3': { action: 'launch', track: 3 },
    'Digit4': { action: 'launch', track: 4 },
    'Digit5': { action: 'launch', track: 5 },
    'Digit6': { action: 'launch', track: 6 },
    'Digit7': { action: 'launch', track: 7 },
    'Digit8': { action: 'launch', track: 8 },
    'Enter': { action: 'transport' },
    'ArrowLeft': { action: 'tempo', delta: -1 },
    'ArrowRight': { action: 'tempo', delta: 1 },
    'ArrowUp': { action: 'masterLevel', delta: 0.05 },
    'ArrowDown': { action: 'masterLevel', delta: -0.05 },
    'BracketLeft': { action: 'preset', delta: -1 },
    'BracketRight': { action: 'preset', delta: 1 },
    'Backspace': { action: 'resetMixer' },
    'Escape': { action: 'stopAll' },
    'Backquote': { action: 'learnToggle' }
  },
  mix: {
    'KeyQ': { action: 'mute', track: 1 },
    'KeyW': { action: 'mute', track: 2 },
    'KeyE': { action: 'mute', track: 3 },
    'KeyR': { action: 'mute', track: 4 },
    'KeyT': { action: 'mute', track: 5 },
    'KeyY': { action: 'mute', track: 6 },
    'KeyU': { action: 'mute', track: 7 },
    'KeyI': { action: 'mute', track: 8 },
    'KeyA': { action: 'solo', track: 1 },
    'KeyS': { action: 'solo', track: 2 },
    'KeyD': { action: 'solo', track: 3 },
    'KeyF': { action: 'solo', track: 4 },
    'KeyG': { action: 'solo', track: 5 },
    'KeyH': { action: 'solo', track: 6 },
    'KeyJ': { action: 'solo', track: 7 },
    'KeyK': { action: 'solo', track: 8 },
    'KeyZ': { action: 'level', track: 1, delta: 0.05 },
    'KeyX': { action: 'level', track: 2, delta: 0.05 },
    'KeyC': { action: 'level', track: 3, delta: 0.05 },
    'KeyV': { action: 'level', track: 4, delta: 0.05 },
    'KeyB': { action: 'level', track: 5, delta: 0.05 },
    'KeyN': { action: 'level', track: 6, delta: 0.05 },
    'KeyM': { action: 'level', track: 7, delta: 0.05 },
    'Comma': { action: 'level', track: 8, delta: 0.05 }
  }
};

const STORAGE_KEY = 'beatboard.keymap.v1';
const LAYER_STORAGE_KEY = 'beatboard.layer.v1';

export function loadKeymap() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch (_) {}
  return JSON.parse(JSON.stringify(DEFAULT_KEYMAP));
}

export function saveKeymap(keymap) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(keymap));
}

export function exportKeymap() {
  return JSON.stringify(loadKeymap(), null, 2);
}

export function importKeymap(json) {
  try {
    const parsed = JSON.parse(json);
    saveKeymap(parsed);
    return true;
  } catch (_) {
    return false;
  }
}

export function loadLayer() {
  try {
    const raw = localStorage.getItem(LAYER_STORAGE_KEY);
    if (raw === 'mix') return LAYERS.MIX;
  } catch (_) {}
  return LAYERS.PLAY;
}

export function saveLayer(layer) {
  localStorage.setItem(LAYER_STORAGE_KEY, layer);
}

export function isTextInputFocused() {
  const el = document.activeElement;
  if (!el) return false;
  const tag = el.tagName.toLowerCase();
  if (tag === 'input' || tag === 'textarea') return true;
  if (el.isContentEditable) return true;
  return false;
}

export function createLearnMode(callback) {
  let pendingControl = null;
  let pendingTrack = null;
  let pendingPad = null;

  function enter(control, track, pad) {
    pendingControl = control;
    pendingTrack = track;
    pendingPad = pad;
  }

  function handleKey(code, shiftKey) {
    if (pendingControl === null) return false;
    const keymap = loadKeymap();
    const layer = LAYERS.PLAY;
    const binding = { action: pendingControl, track: pendingTrack, pad: pendingPad };
    if (shiftKey) binding.shift = true;
    keymap[layer][code] = binding;
    saveKeymap(keymap);
    pendingControl = pendingTrack = pendingPad = null;
    if (callback) callback(code, binding);
    return true;
  }

  function cancel() {
    pendingControl = pendingTrack = pendingPad = null;
  }

  function isActive() {
    return pendingControl !== null;
  }

  return { enter, handleKey, cancel, isActive };
}