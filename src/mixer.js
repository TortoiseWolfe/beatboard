/**
 * MIXER LOGIC (pure, no Web Audio)
 * Mute / Solo / Level truth table.
 * A track is audible when: !muted && (no track soloed || soloed)
 */
export function computeAudible(tracks) {
  const anySolo = tracks.some(t => t.solo);
  return tracks.map(t => !t.muted && (!anySolo || t.solo));
}

export function applyMute(tracks, index, value) {
  const next = tracks.map((t, i) => i === index ? { ...t, muted: value } : t);
  return next;
}

export function applySolo(tracks, index, value) {
  const next = tracks.map((t, i) => i === index ? { ...t, solo: value } : t);
  return next;
}

export function applyLevel(tracks, index, level) {
  const clamped = Math.max(0, Math.min(1, level));
  const next = tracks.map((t, i) => i === index ? { ...t, level: clamped } : t);
  return next;
}

export function resetMixer(tracks) {
  return tracks.map(t => ({ ...t, muted: false, solo: false, level: t.defaultLevel ?? 0.7 }));
}

export function toggleMute(tracks, index) {
  const next = applyMute(tracks, index, !tracks[index].muted);
  if (next[index].muted) {
    next[index].solo = false;
  }
  return next;
}

export function toggleSolo(tracks, index) {
  const next = applySolo(tracks, index, !tracks[index].solo);
  if (next[index].solo) {
    next[index].muted = false;
  }
  return next;
}

export function clearAllSolo(tracks) {
  return tracks.map(t => ({ ...t, solo: false }));
}

export function setTrackLevel(tracks, index, level) {
  return applyLevel(tracks, index, level);
}

export function adjustTrackLevel(tracks, index, delta) {
  const current = tracks[index].level ?? 0.7;
  return applyLevel(tracks, index, current + delta);
}