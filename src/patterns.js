/**
 * PATTERN PRESETS
 * Five presets from wp-dev metronome-app, deep-copied on load so mutations
 * never leak back into the source objects. Hip Hop is first (index 0).
 * Each track: { name, pattern: 8-step array, muted, volume }
 */
const PRESET_DEFS = {
  'Hip Hop': [
    { name: 'Kick', pattern: [1, 0, 0, 0, 0, 0, 1, 0], muted: false, volume: 0.8 },
    { name: 'Snare', pattern: [0, 0, 1, 0, 0, 0, 1, 0], muted: false, volume: 0.8 },
    { name: 'Hats', pattern: [1, 0, 1, 0, 1, 0, 1, 0], muted: false, volume: 0.6 },
    { name: 'Perc', pattern: [0, 1, 0, 1, 0, 1, 0, 1], muted: false, volume: 0.5 },
    { name: 'Bass', pattern: [1, 0, 0, 0, 1, 0, 0, 0], muted: false, volume: 0.7 },
    { name: 'Keys', pattern: [0, 0, 0, 0, 0, 0, 0, 0], muted: false, volume: 0.6 },
    { name: 'Bed', pattern: [0, 0, 0, 0, 0, 0, 0, 0], muted: false, volume: 0.4 },
    { name: 'Jingle', pattern: [0, 0, 0, 0, 0, 0, 0, 0], muted: false, volume: 0.5 }
  ],
  'Basic Rock': [
    { name: 'Kick', pattern: [1, 0, 0, 0, 1, 0, 0, 0], muted: false, volume: 0.8 },
    { name: 'Snare', pattern: [0, 0, 1, 0, 0, 0, 1, 0], muted: false, volume: 0.8 },
    { name: 'Hats', pattern: [1, 1, 1, 1, 1, 1, 1, 1], muted: false, volume: 0.6 },
    { name: 'Perc', pattern: [0, 0, 0, 0, 0, 0, 0, 0], muted: true, volume: 0.5 },
    { name: 'Bass', pattern: [1, 0, 1, 0, 1, 0, 1, 0], muted: false, volume: 0.7 },
    { name: 'Keys', pattern: [0, 0, 0, 0, 0, 0, 0, 0], muted: false, volume: 0.6 },
    { name: 'Bed', pattern: [0, 0, 0, 0, 0, 0, 0, 0], muted: false, volume: 0.4 },
    { name: 'Jingle', pattern: [0, 0, 0, 0, 0, 0, 0, 0], muted: false, volume: 0.5 }
  ],
  'Disco': [
    { name: 'Kick', pattern: [1, 0, 0, 1, 1, 0, 0, 1], muted: false, volume: 0.8 },
    { name: 'Snare', pattern: [0, 0, 1, 0, 0, 0, 1, 0], muted: false, volume: 0.8 },
    { name: 'Hats', pattern: [1, 1, 1, 1, 1, 1, 1, 1], muted: false, volume: 0.6 },
    { name: 'Perc', pattern: [0, 1, 0, 1, 0, 1, 0, 1], muted: false, volume: 0.5 },
    { name: 'Bass', pattern: [1, 0, 1, 0, 0, 1, 0, 1], muted: false, volume: 0.7 },
    { name: 'Keys', pattern: [0, 1, 0, 1, 0, 1, 0, 1], muted: false, volume: 0.6 },
    { name: 'Bed', pattern: [0, 0, 0, 0, 0, 0, 0, 0], muted: false, volume: 0.4 },
    { name: 'Jingle', pattern: [0, 0, 0, 0, 0, 0, 0, 0], muted: false, volume: 0.5 }
  ],
  'Jazz': [
    { name: 'Kick', pattern: [1, 0, 0, 0, 0, 0, 0, 0], muted: false, volume: 0.8 },
    { name: 'Snare', pattern: [0, 0, 1, 0, 0, 0, 1, 0], muted: false, volume: 0.8 },
    { name: 'Hats', pattern: [0, 0, 0, 0, 0, 0, 0, 0], muted: true, volume: 0.6 },
    { name: 'Perc', pattern: [0, 0, 0, 0, 0, 0, 0, 0], muted: true, volume: 0.5 },
    { name: 'Bass', pattern: [1, 0, 1, 0, 1, 0, 1, 0], muted: false, volume: 0.7 },
    { name: 'Keys', pattern: [0, 1, 0, 1, 0, 1, 0, 1], muted: false, volume: 0.6 },
    { name: 'Bed', pattern: [0, 0, 0, 0, 0, 0, 0, 0], muted: false, volume: 0.4 },
    { name: 'Jingle', pattern: [0, 0, 0, 0, 0, 0, 0, 0], muted: false, volume: 0.5 }
  ],
  'Waltz': [
    { name: 'Kick', pattern: [1, 0, 0, 1, 0, 0, 0, 0], muted: false, volume: 0.8 },
    { name: 'Snare', pattern: [0, 0, 0, 0, 0, 1, 0, 0], muted: false, volume: 0.8 },
    { name: 'Hats', pattern: [1, 0, 1, 1, 0, 1, 0, 0], muted: false, volume: 0.6 },
    { name: 'Perc', pattern: [0, 0, 0, 0, 0, 0, 0, 0], muted: true, volume: 0.5 },
    { name: 'Bass', pattern: [1, 0, 0, 1, 0, 0, 1, 0], muted: false, volume: 0.7 },
    { name: 'Keys', pattern: [0, 0, 1, 0, 0, 0, 1, 0], muted: false, volume: 0.6 },
    { name: 'Bed', pattern: [0, 0, 0, 0, 0, 0, 0, 0], muted: false, volume: 0.4 },
    { name: 'Jingle', pattern: [0, 0, 0, 0, 0, 0, 0, 0], muted: false, volume: 0.5 }
  ]
};

export const presetNames = Object.keys(PRESET_DEFS);

export function getPreset(name) {
  const def = PRESET_DEFS[name];
  if (!def) return null;
  return JSON.parse(JSON.stringify(def));
}

export function getAllPresets() {
  const out = {};
  for (const [name, def] of Object.entries(PRESET_DEFS)) {
    out[name] = JSON.parse(JSON.stringify(def));
  }
  return out;
}

export function getDefaultPreset() {
  return getPreset('Hip Hop');
}