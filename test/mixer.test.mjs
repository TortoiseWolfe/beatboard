/**
 * MIXER TESTS — mute/solo/level truth table
 */
import { describe, it } from 'node:test';
import assert from 'node:assert';
import {
  computeAudible, applyMute, applySolo, applyLevel,
  resetMixer, toggleMute, toggleSolo, clearAllSolo,
  setTrackLevel, adjustTrackLevel
} from '../src/mixer.js';

const makeTracks = () => [
  { name: 'Kick', muted: false, solo: false, level: 0.8, defaultLevel: 0.8 },
  { name: 'Snare', muted: false, solo: false, level: 0.8, defaultLevel: 0.8 },
  { name: 'Hats', muted: false, solo: false, level: 0.6, defaultLevel: 0.6 },
  { name: 'Perc', muted: true, solo: false, level: 0.5, defaultLevel: 0.5 },
];

describe('mixer', () => {
  it('computeAudible: all audible when none muted/soloed', () => {
    const tracks = makeTracks();
    const audible = computeAudible(tracks);
    assert.deepEqual(audible, [true, true, true, false]); // Perc is muted
  });

  it('computeAudible: soloed track mutes others', () => {
    const tracks = makeTracks();
    tracks[1].solo = true; // Snare soloed
    const audible = computeAudible(tracks);
    assert.deepEqual(audible, [false, true, false, false]);
  });

  it('computeAudible: muted soloed track is silent', () => {
    const tracks = makeTracks();
    tracks[1].solo = true;
    tracks[1].muted = true;
    const audible = computeAudible(tracks);
    assert.deepEqual(audible, [false, false, false, false]);
  });

  it('applyMute: toggles mute on single track', () => {
    const tracks = makeTracks();
    const next = applyMute(tracks, 0, true);
    assert.equal(next[0].muted, true);
    assert.equal(next[1].muted, false);
  });

  it('applySolo: toggles solo on single track', () => {
    const tracks = makeTracks();
    const next = applySolo(tracks, 2, true);
    assert.equal(next[2].solo, true);
    assert.equal(next[0].solo, false);
  });

  it('applyLevel: clamps to 0..1', () => {
    const tracks = makeTracks();
    let next = applyLevel(tracks, 0, 1.5);
    assert.equal(next[0].level, 1);
    next = applyLevel(tracks, 0, -0.3);
    assert.equal(next[0].level, 0);
  });

  it('resetMixer: clears mute/solo, restores defaultLevel', () => {
    const tracks = makeTracks();
    tracks[0].muted = true;
    tracks[1].solo = true;
    tracks[2].level = 0.2;
    const next = resetMixer(tracks);
    assert.equal(next[0].muted, false);
    assert.equal(next[1].solo, false);
    assert.equal(next[2].level, 0.6);
  });

  it('toggleMute: flips mute, clears solo if muting', () => {
    const tracks = makeTracks();
    tracks[0].solo = true;
    let next = toggleMute(tracks, 0);
    assert.equal(next[0].muted, true);
    assert.equal(next[0].solo, false);
  });

  it('toggleSolo: flips solo, clears mute if soloing', () => {
    const tracks = makeTracks();
    tracks[0].muted = true;
    let next = toggleSolo(tracks, 0);
    assert.equal(next[0].solo, true);
    assert.equal(next[0].muted, false);
  });

  it('clearAllSolo: removes all solo flags', () => {
    const tracks = makeTracks();
    tracks[0].solo = true;
    tracks[2].solo = true;
    const next = clearAllSolo(tracks);
    assert.equal(next[0].solo, false);
    assert.equal(next[2].solo, false);
  });

  it('setTrackLevel: sets exact level', () => {
    const tracks = makeTracks();
    const next = setTrackLevel(tracks, 3, 0.75);
    assert.equal(next[3].level, 0.75);
  });

  it('adjustTrackLevel: adds delta relative to current', () => {
    const tracks = makeTracks();
    const next = adjustTrackLevel(tracks, 0, 0.1);
    assert.equal(next[0].level, 0.9);
  });
});