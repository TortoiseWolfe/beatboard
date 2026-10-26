/**
 * CLOCK MATH TESTS — next-bar quantize at several tempos
 */
import { describe, it } from 'node:test';
import assert from 'node:assert';

function quantizeToNextBar(currentTime, tempo, nextTickTime) {
  const barDuration = (60 / tempo) * 4;
  const elapsed = (currentTime - nextTickTime) % barDuration;
  return currentTime + (barDuration - elapsed) + 0.001;
}

describe('clock math', () => {
  it('quantizeToNextBar at 110 BPM', () => {
    const tempo = 110;
    const barDuration = (60 / tempo) * 4; // ~2.1818s
    const nextTickTime = 10.0;
    const currentTime = 10.5;
    const quantized = quantizeToNextBar(currentTime, tempo, nextTickTime);
    const expectedBar = Math.ceil((currentTime - nextTickTime) / barDuration) * barDuration + nextTickTime + 0.001;
    assert.ok(Math.abs(quantized - expectedBar) < 0.002);
  });

  it('quantizeToNextBar at 60 BPM (slow)', () => {
    const tempo = 60;
    const barDuration = (60 / tempo) * 4; // 4s
    const nextTickTime = 0;
    const currentTime = 1.5;
    const quantized = quantizeToNextBar(currentTime, tempo, nextTickTime);
    assert.ok(Math.abs(quantized - 4.001) < 0.002);
  });

  it('quantizeToNextBar at 200 BPM (fast)', () => {
    const tempo = 200;
    const barDuration = (60 / tempo) * 4; // 1.2s
    const nextTickTime = 0;
    const currentTime = 0.3;
    const quantized = quantizeToNextBar(currentTime, tempo, nextTickTime);
    assert.ok(Math.abs(quantized - 1.201) < 0.002);
  });

  it('quantizeToNextBar exactly on bar boundary', () => {
    const tempo = 120;
    const barDuration = (60 / tempo) * 4; // 2s
    const nextTickTime = 0;
    const currentTime = 4.0; // exactly 2 bars
    const quantized = quantizeToNextBar(currentTime, tempo, nextTickTime);
    assert.ok(Math.abs(quantized - 6.001) < 0.002);
  });

  it('stepDuration = beatDuration / 2', () => {
    const tempo = 110;
    const beatDuration = 60 / tempo;
    const stepDuration = beatDuration / 2;
    assert.ok(Math.abs(stepDuration - (60 / 110 / 2)) < 0.0001);
  });

  it('barDuration = beatDuration * 4', () => {
    const tempo = 110;
    const beatDuration = 60 / tempo;
    const barDuration = beatDuration * 4;
    assert.ok(Math.abs(barDuration - (60 / 110 * 4)) < 0.0001);
  });
});