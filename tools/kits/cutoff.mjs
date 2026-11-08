#!/usr/bin/env node
// Hard cut-off check for a rendered track. A script listens for the broken-hearing-aid sound; nobody eyeballs it.
//
//   node tools/kits/cutoff.mjs [--drop-db 26] [--window-ms 12] [--floor-db -50] a.wav b.wav ...
//
// A "hard cut" is a sound that is still loud right up to a moment and then is gone almost at once.
// A note that rings out on its own (a one-shot plays its whole natural sound to the end) decays smoothly and never trips this.
// At each millisecond t we compare three peak levels:
//   before  = loudest sample in the window ending at t
//   near    = loudest sample in the last 2 ms before t
//   after   = loudest sample in the window starting at t
// t is a cut when before is above the floor, near is still at least a quarter of before (the sound had not died down yet),
// and after is more than `drop-db` below before. Cuts closer than 30 ms are one cut. Exit code 0 only when no file has a cut.
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import { decodeWav } from './measure.mjs';

// Loudest absolute sample in each 1 ms block, over all channels.
function blockPeaks(data, fs) {
  const block = Math.max(1, Math.round(fs / 1000));
  const n = data[0].length;
  const blocks = Math.ceil(n / block);
  const peaks = new Float32Array(blocks);
  for (const ch of data) {
    for (let b = 0; b < blocks; b++) {
      let m = peaks[b];
      const end = Math.min(n, (b + 1) * block);
      for (let i = b * block; i < end; i++) {
        const v = Math.abs(ch[i]);
        if (v > m) m = v;
      }
      peaks[b] = m;
    }
  }
  return peaks;
}

function maxOver(peaks, from, to) {
  let m = 0;
  for (let b = Math.max(0, from); b < Math.min(peaks.length, to); b++) if (peaks[b] > m) m = peaks[b];
  return m;
}

// Returns [{ timeSec, beforeDb, afterDb }] for every hard cut found.
export function hardCuts(data, fs, { dropDb = 26, windowMs = 12, floorDb = -50, nearMs = 2, mergeMs = 30 } = {}) {
  const peaks = blockPeaks(data, fs);
  const msPerBlock = (1000 * Math.max(1, Math.round(fs / 1000))) / fs;
  const w = Math.round(windowMs / msPerBlock);
  const near = Math.max(1, Math.round(nearMs / msPerBlock));
  const floor = 10 ** (floorDb / 20);
  const dropRatio = 10 ** (-dropDb / 20);
  const cuts = [];
  // Stop w blocks before the end: the file's own end is not a note cut.
  for (let b = w; b + w <= peaks.length; b++) {
    const before = maxOver(peaks, b - w, b);
    if (before < floor) continue;
    if (maxOver(peaks, b - near, b) < 0.25 * before) continue;
    const after = maxOver(peaks, b, b + w);
    if (after < before * dropRatio) {
      const timeSec = (b * msPerBlock) / 1000;
      const last = cuts[cuts.length - 1];
      if (last && (timeSec - last.timeSec) * 1000 < mergeMs) continue;
      cuts.push({ timeSec, beforeDb: 20 * Math.log10(before), afterDb: 20 * Math.log10(Math.max(after, 1e-9)) });
    }
  }
  return cuts;
}

export function checkFile(path, opts) {
  const { sampleRate, data } = decodeWav(readFileSync(path));
  const cuts = hardCuts(data, sampleRate, opts);
  return { file: path, cuts: cuts.length, first: cuts.slice(0, 10), ok: cuts.length === 0 };
}

function main(argv) {
  const opts = {};
  const files = [];
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--drop-db') opts.dropDb = Number(argv[++i]);
    else if (a === '--window-ms') opts.windowMs = Number(argv[++i]);
    else if (a === '--floor-db') opts.floorDb = Number(argv[++i]);
    else files.push(a);
  }
  if (!files.length) {
    console.error('usage: cutoff.mjs [--drop-db 26] [--window-ms 12] [--floor-db -50] a.wav ...');
    return 2;
  }
  const results = files.map((f) => checkFile(f, opts));
  console.log(JSON.stringify({ ok: results.every((r) => r.ok), results }, null, 2));
  return results.every((r) => r.ok) ? 0 : 1;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.exit(main(process.argv.slice(2)));
}
