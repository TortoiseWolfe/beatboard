#!/usr/bin/env node
// Alignment checks for a kit of per-robot stems. A script measures; nobody eyeballs a waveform.
//
//   node tools/kits/measure.mjs --bpm 112 [--bars 16] [--max-offset-ms 5] [--max-lu 1] [--grid-lock] [--normalise DIR [--target -20]] stem1.wav stem2.wav ...
//
// The four checks (band-wagon-toy-plan.md, "Verification"):
//   1. Every stem has the same length in samples (and, with --bars, the length the tempo implies).
//   2. Every pair of stems lines up to under 5 ms (cross-correlation of the note-onset curves).
//   3. Loudness (ITU-R BS.1770-4 / EBU R128 integrated, in LUFS) is within 1 LU across stems.
//   4. The loop seam (last sample into first sample) has no click.
// Exit code 0 only if all four pass. Reads WAV (16, 24, 32-bit integer or 32-bit float PCM).
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { basename, join } from 'node:path';
import { pathToFileURL } from 'node:url';

// ---------- WAV in and out ----------

export function decodeWav(buf) {
  if (buf.length < 12 || buf.toString('ascii', 0, 4) !== 'RIFF' || buf.toString('ascii', 8, 12) !== 'WAVE') {
    throw new Error('not a RIFF/WAVE file');
  }
  let fmt = null;
  let dataStart = -1;
  let dataLen = 0;
  for (let p = 12; p + 8 <= buf.length;) {
    const id = buf.toString('ascii', p, p + 4);
    let size = buf.readUInt32LE(p + 4);
    if (id === 'fmt ') {
      let tag = buf.readUInt16LE(p + 8);
      if (tag === 0xfffe && size >= 26) tag = buf.readUInt16LE(p + 8 + 24); // extensible: sub-format tag
      fmt = {
        tag,
        channels: buf.readUInt16LE(p + 10),
        sampleRate: buf.readUInt32LE(p + 12),
        bits: buf.readUInt16LE(p + 22),
      };
    } else if (id === 'data') {
      dataStart = p + 8;
      // Streamed files may carry 0 or 0xFFFFFFFF as the size: take what is there.
      if (size === 0 || size === 0xffffffff || dataStart + size > buf.length) size = buf.length - dataStart;
      dataLen = size;
      break;
    }
    p += 8 + size + (size & 1);
  }
  if (!fmt || dataStart < 0) throw new Error('WAV has no fmt or data chunk');
  const { tag, channels, sampleRate, bits } = fmt;
  const bytes = bits / 8;
  const frames = Math.floor(dataLen / (bytes * channels));
  const data = Array.from({ length: channels }, () => new Float32Array(frames));
  for (let i = 0; i < frames; i++) {
    for (let c = 0; c < channels; c++) {
      const o = dataStart + (i * channels + c) * bytes;
      let v;
      if (tag === 3 && bits === 32) v = buf.readFloatLE(o);
      else if (tag === 1 && bits === 16) v = buf.readInt16LE(o) / 32768;
      else if (tag === 1 && bits === 24) v = buf.readIntLE(o, 3) / 8388608;
      else if (tag === 1 && bits === 32) v = buf.readInt32LE(o) / 2147483648;
      else throw new Error(`unsupported WAV format: tag ${tag}, ${bits} bits`);
      data[c][i] = v;
    }
  }
  return { sampleRate, channels, frames, data };
}

// 32-bit float WAV, so tests and tools can write stems without losing anything.
export function encodeWav({ sampleRate, data }) {
  const channels = data.length;
  const frames = data[0].length;
  const out = Buffer.alloc(44 + frames * channels * 4);
  out.write('RIFF', 0, 'ascii');
  out.writeUInt32LE(36 + frames * channels * 4, 4);
  out.write('WAVEfmt ', 8, 'ascii');
  out.writeUInt32LE(16, 16);
  out.writeUInt16LE(3, 20);
  out.writeUInt16LE(channels, 22);
  out.writeUInt32LE(sampleRate, 24);
  out.writeUInt32LE(sampleRate * channels * 4, 28);
  out.writeUInt16LE(channels * 4, 32);
  out.writeUInt16LE(32, 34);
  out.write('data', 36, 'ascii');
  out.writeUInt32LE(frames * channels * 4, 40);
  for (let i = 0; i < frames; i++) {
    for (let c = 0; c < channels; c++) out.writeFloatLE(data[c][i], 44 + (i * channels + c) * 4);
  }
  return out;
}

// ---------- 1. length ----------

// A bar is 4 beats; at 112 BPM, 16 bars is 34.2857... s, which is rarely a whole number of samples.
export function expectedSamples(bars, bpm, sampleRate) {
  return Math.round((bars * 4 * 60 * sampleRate) / bpm);
}

// ---------- 3. loudness (BS.1770-4) ----------

function biquad(x, b0, b1, b2, a1, a2) {
  const y = new Float64Array(x.length);
  let x1 = 0, x2 = 0, y1 = 0, y2 = 0;
  for (let n = 0; n < x.length; n++) {
    const v = b0 * x[n] + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2;
    y[n] = v;
    x2 = x1; x1 = x[n]; y2 = y1; y1 = v;
  }
  return y;
}

// K-weighting: a high-shelf (head model) then a high-pass (RLB), designed for any sample rate.
export function kWeight(x, fs) {
  const f1 = 1681.974450955533, g1 = 3.999843853973347, q1 = 0.7071752369554196;
  let K = Math.tan((Math.PI * f1) / fs);
  const Vh = 10 ** (g1 / 20);
  const Vb = Vh ** 0.4996667741545416;
  let a0 = 1 + K / q1 + K * K;
  const s1 = biquad(
    x,
    (Vh + (Vb * K) / q1 + K * K) / a0,
    (2 * (K * K - Vh)) / a0,
    (Vh - (Vb * K) / q1 + K * K) / a0,
    (2 * (K * K - 1)) / a0,
    (1 - K / q1 + K * K) / a0,
  );
  const f2 = 38.13547087602444, q2 = 0.5003270373238773;
  K = Math.tan((Math.PI * f2) / fs);
  a0 = 1 + K / q2 + K * K;
  return biquad(s1, 1, -2, 1, (2 * (K * K - 1)) / a0, (1 - K / q2 + K * K) / a0);
}

// Integrated loudness in LUFS: 400 ms blocks, 75% overlap, absolute gate -70, relative gate -10 LU.
export function integratedLufs(data, fs) {
  const weighted = data.map((ch) => kWeight(ch, fs));
  const block = Math.round(0.4 * fs);
  const hop = Math.round(0.1 * fs);
  const frames = data[0].length;
  const energies = [];
  for (let s = 0; s + block <= frames; s += hop) {
    let z = 0;
    for (const w of weighted) {
      let sum = 0;
      for (let i = s; i < s + block; i++) sum += w[i] * w[i];
      z += sum / block; // channel weight 1.0 for left, right and centre
    }
    energies.push(z);
  }
  const lufs = (z) => -0.691 + 10 * Math.log10(z);
  const absGated = energies.filter((z) => z > 0 && lufs(z) > -70);
  if (absGated.length === 0) return -Infinity;
  const mean = (a) => a.reduce((s, v) => s + v, 0) / a.length;
  const relThreshold = lufs(mean(absGated)) - 10;
  const gated = absGated.filter((z) => lufs(z) > relThreshold);
  return lufs(mean(gated));
}

// ---------- 2. alignment ----------

// Different instruments share no waveform, so correlating raw samples would find nothing. What they
// share is when notes start. The onset curve is the rise of a 1 ms-resolution loudness envelope.
export function onsetCurve(data, fs) {
  const hop = Math.max(1, Math.round(fs / 1000));
  const n = Math.floor(data[0].length / hop);
  const env = new Float64Array(n);
  for (let k = 0; k < n; k++) {
    let sum = 0;
    for (const ch of data) for (let i = k * hop; i < (k + 1) * hop; i++) sum += Math.abs(ch[i]);
    env[k] = sum / (hop * data.length);
  }
  // Smooth over 5 ms so a note's attack becomes one rise, then keep only the rises.
  const w = 5;
  const smooth = new Float64Array(n);
  let acc = 0;
  for (let k = 0; k < n; k++) {
    acc += env[k];
    if (k >= w) acc -= env[k - w];
    smooth[k] = acc / w;
  }
  const out = new Float64Array(n);
  for (let k = 1; k < n; k++) out[k] = Math.max(0, smooth[k] - smooth[k - 1]);
  return out;
}

function removeMean(v) {
  let m = 0;
  for (let i = 0; i < v.length; i++) m += v[i];
  m /= v.length || 1;
  const o = new Float64Array(v.length);
  for (let i = 0; i < v.length; i++) o[i] = v[i] - m;
  return o;
}

// How many ms later `b` is than `a` (positive: b is late). Curves are mean-removed first, otherwise two
// unrelated parts correlate at ~0.2 everywhere. `strength` is the best correlation; `significance` is that
// peak divided by the median correlation over +-300 ms, so a pair with no shared onsets scores near 1-4
// and a pair that really plays together scores far higher.
export function offsetMs(a, b, fs, maxLagMs = 50, spanMs = 300) {
  const ca = removeMean(onsetCurve(a, fs));
  const cb = removeMean(onsetCurve(b, fs));
  const n = Math.min(ca.length, cb.length);
  const norm = (v) => {
    let s = 0;
    for (let i = 0; i < n; i++) s += v[i] * v[i];
    return Math.sqrt(s) || 1;
  };
  const na = norm(ca), nb = norm(cb);
  const at = (lag) => {
    let s = 0;
    for (let i = Math.max(0, -lag); i < Math.min(n, n - lag); i++) s += ca[i] * cb[i + lag];
    return s / (na * nb);
  };
  const all = [];
  let best = 0, bestLag = 0;
  for (let lag = -spanMs; lag <= spanMs; lag++) {
    const r = at(lag);
    all.push(Math.abs(r));
    if (r > best && Math.abs(lag) <= maxLagMs) { best = r; bestLag = lag; }
  }
  all.sort((x, y) => x - y);
  const median = all[Math.floor(all.length / 2)] || 1e-9;
  // The true peak may sit outside +-maxLag (a half-beat apart, say): then there is nothing to judge here.
  const widest = Math.max(...all);
  return { ms: bestLag, strength: best, significance: best / median, peakOutside: widest > best * 1.25 };
}

// Where the stem's note onsets sit inside the beat, in ms from the beat line of an ideal grid at `bpm`
// (-half a beat to +half). Fold the onset curve on the beat period, smooth 10 ms, take the strongest phase.
// `sharpness` is that phase's weight over the average phase: a flat pad scores ~1, a drum kit ~2.
export function gridPhase(data, fs, bpm) {
  const c = onsetCurve(data, fs);
  const period = 60000 / bpm;
  const B = Math.round(period * 10);
  const bins = new Float64Array(B);
  for (let i = 0; i < c.length; i++) bins[Math.min(B - 1, Math.floor((i % period) * 10))] += c[i];
  const mean = bins.reduce((x, y) => x + y, 0) / B;
  let best = 0, at = 0;
  for (let k = 0; k < B; k++) {
    let sum = 0;
    for (let d = -50; d <= 50; d++) sum += bins[(k + d + B) % B];
    if (sum / 101 > best) { best = sum / 101; at = k; }
  }
  // Refine: weighted centre of the raw bins within +-5 ms of the winner, so the answer is not stuck on the
  // smoothing window's edge.
  let wsum = 0, psum = 0;
  for (let d = -50; d <= 50; d++) {
    const w = bins[(at + d + B) % B];
    wsum += w;
    psum += w * d;
  }
  let ms = (at + (wsum ? psum / wsum : 0)) / 10;
  if (ms < 0) ms += period;
  if (ms > period / 2) ms -= period;
  return { ms, sharpness: mean ? best / mean : 0 };
}

// ---------- 4. loop seam ----------

// A click is a jump across the seam larger than anything the music does between neighbouring samples.
export function seamClick(data, { factor = 3, floor = 0.01 } = {}) {
  let worst = 0;
  let ratio = 0;
  for (const ch of data) {
    const n = ch.length;
    const deltas = new Float32Array(n - 1);
    for (let i = 0; i < n - 1; i++) deltas[i] = Math.abs(ch[i + 1] - ch[i]);
    const sorted = Float32Array.from(deltas).sort();
    const p999 = sorted[Math.floor(0.999 * (sorted.length - 1))];
    const jump = Math.abs(ch[0] - ch[n - 1]);
    const limit = Math.max(floor, factor * p999);
    worst = Math.max(worst, jump);
    ratio = Math.max(ratio, jump / limit);
  }
  return { jump: worst, ratio, ok: ratio <= 1 };
}

// ---------- the whole kit ----------

export function measureKit(stems, { bpm, bars, maxOffsetMs = 5, maxLu = 1, minSignificance = 8, minSharp = 1.7 } = {}) {
  const fs = stems[0].sampleRate;
  const report = { sampleRate: fs, stems: [], pairs: [], checks: {} };
  const lengths = stems.map((s) => s.frames);
  const expected = bars && bpm ? expectedSamples(bars, bpm, fs) : null;
  report.checks.length = {
    ok: lengths.every((l) => l === lengths[0]) && stems.every((s) => s.sampleRate === fs) && (expected === null || lengths[0] === expected),
    samples: lengths,
    expected,
  };
  stems.forEach((s, i) => {
    report.stems.push({
      index: i,
      frames: s.frames,
      lufs: integratedLufs(s.data, fs),
      seam: seamClick(s.data),
    });
  });
  const lufs = report.stems.map((s) => s.lufs).filter(Number.isFinite);
  const spread = lufs.length ? Math.max(...lufs) - Math.min(...lufs) : Infinity;
  report.checks.loudness = { ok: lufs.length === stems.length && spread <= maxLu, spreadLu: spread };
  for (let i = 0; i < stems.length; i++) {
    for (let j = i + 1; j < stems.length; j++) {
      report.pairs.push({ a: i, b: j, ...offsetMs(stems[i].data, stems[j].data, fs) });
    }
  }
  // Two checks, because parts that play different notes cannot all be compared with each other:
  //  - pairs that share onsets (significance >= minSignificance, peak inside the lag window) must sit under
  //    maxOffsetMs apart; the rest are counted as unjudged, never silently passed;
  //  - every stem with a clear beat (sharpness >= minSharp) must sit under maxOffsetMs from the bpm grid.
  report.stems.forEach((st, i) => { st.grid = gridPhase(stems[i].data, fs, bpm); });
  const judged = report.pairs.filter((p) => p.significance >= minSignificance && !p.peakOutside);
  const gridded = report.stems.filter((st) => st.grid.sharpness >= minSharp);
  report.checks.offset = {
    ok: judged.every((p) => Math.abs(p.ms) < maxOffsetMs) && gridded.every((st) => Math.abs(st.grid.ms) < maxOffsetMs),
    maxPairMs: judged.reduce((m, p) => Math.max(m, Math.abs(p.ms)), 0),
    judgedPairs: judged.length,
    unjudgedPairs: report.pairs.length - judged.length,
    maxGridMs: gridded.reduce((m, st) => Math.max(m, Math.abs(st.grid.ms)), 0),
    gridStems: gridded.length,
  };
  report.checks.seam = { ok: report.stems.every((s) => s.seam.ok) };
  report.ok = Object.values(report.checks).every((c) => c.ok);
  return report;
}

// ---------- loudness matching ----------

// Pure gain, so timing is untouched: scale each stem to `targetLufs`. Reports each stem's true sample
// peak after the gain and refuses (ok=false) when a stem would pass full scale, rather than clip it.
export function normaliseStems(stems, targetLufs = -20, ceiling = 0.99) {
  return stems.map((s) => {
    const lufs = integratedLufs(s.data, s.sampleRate);
    const gain = 10 ** ((targetLufs - lufs) / 20);
    let peak = 0;
    for (const ch of s.data) for (let i = 0; i < ch.length; i++) peak = Math.max(peak, Math.abs(ch[i]) * gain);
    const data = s.data.map((ch) => ch.map((v) => v * gain));
    return { stem: { sampleRate: s.sampleRate, frames: s.frames, data }, gainDb: 20 * Math.log10(gain), peak, ok: peak <= ceiling };
  });
}

// ---------- grid lock ----------

// Move a stem `lateMs` earlier (negative: later): the front is cut and silence fills the end, or the reverse,
// so the length stays exactly the same.
export function shiftStem(stem, lateMs) {
  const n = Math.round((lateMs * stem.sampleRate) / 1000); // samples to drop from the front (negative: pad)
  const data = stem.data.map((ch) => {
    const out = new Float32Array(ch.length);
    if (n >= 0) out.set(ch.subarray(n));
    else out.set(ch.subarray(0, ch.length + n), -n);
    // The cut leaves a step at the loop seam (music at the front, silence at the end): a short fade at
    // both ends turns the step into a ramp. The phase 2 slicer replaces this with a zero-crossing cut.
    const fade = Math.round(0.008 * stem.sampleRate);
    for (let i = 0; i < fade; i++) {
      const w = 0.5 - 0.5 * Math.cos((Math.PI * i) / fade);
      out[i] *= w;
      out[out.length - 1 - i] *= w;
    }
    return out;
  });
  return { sampleRate: stem.sampleRate, frames: stem.frames, data };
}

// Lock a whole kit to the grid with ONE shift for every stem. Layers rendered together share one timing
// (the cross-correlation shows them playing together to the millisecond), so moving them separately would
// break that. The shift is the median beat phase of the stems with a clear beat (sharpness >= minSharp);
// a pad has no beat to read. With no such stem the kit is returned as it came.
export function gridLockKit(stems, bpm, minSharp = 1.7) {
  const phases = stems.map((st) => gridPhase(st.data, st.sampleRate, bpm));
  const clear = phases.filter((g) => g.sharpness >= minSharp).map((g) => g.ms).sort((x, y) => x - y);
  if (!clear.length) return { stems, shiftMs: 0, locked: false, phases };
  const mid = clear.length >> 1;
  const shiftMs = clear.length % 2 ? clear[mid] : (clear[mid - 1] + clear[mid]) / 2;
  return { stems: stems.map((st) => shiftStem(st, shiftMs)), shiftMs: -shiftMs, locked: true, phases };
}

// ---------- command line ----------

function main(argv) {
  const opts = { bpm: null, bars: null, maxOffsetMs: 5, maxLu: 1 };
  let normDir = null;
  let lock = false;
  let target = -20;
  const files = [];
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--bpm') opts.bpm = Number(argv[++i]);
    else if (a === '--bars') opts.bars = Number(argv[++i]);
    else if (a === '--max-offset-ms') opts.maxOffsetMs = Number(argv[++i]);
    else if (a === '--max-lu') opts.maxLu = Number(argv[++i]);
    else if (a === '--grid-lock') lock = true;
    else if (a === '--normalise') normDir = argv[++i];
    else if (a === '--target') target = Number(argv[++i]);
    else files.push(a);
  }
  if (files.length < 2) {
    console.error('usage: measure.mjs --bpm N [--bars N] [--max-offset-ms 5] [--max-lu 1] [--grid-lock] [--normalise DIR [--target -20]] stem1.wav stem2.wav ...');
    return 2;
  }
  let stems = files.map((f) => decodeWav(readFileSync(f)));
  const shifts = [];
  if (lock) {
    if (!normDir) throw new Error('--grid-lock writes files: give --normalise DIR too');
    const r = gridLockKit(stems, opts.bpm);
    stems = r.stems;
    stems.forEach(() => shifts.push(r.shiftMs));
  }
  let gains = null;
  if (normDir) {
    mkdirSync(normDir, { recursive: true });
    gains = normaliseStems(stems, target);
    stems = gains.map((g) => g.stem);
    stems.forEach((st, i) => writeFileSync(join(normDir, basename(files[i])), encodeWav(st)));
  }
  const report = measureKit(stems, opts);
  report.stems.forEach((s, i) => { s.file = files[i]; if (gains) Object.assign(s, { gainDb: gains[i].gainDb, peak: gains[i].peak, gridShiftMs: shifts[i] }); });
  if (gains && !gains.every((g) => g.ok)) report.ok = false;
  console.log(JSON.stringify(report, null, 2));
  return report.ok ? 0 : 1;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.exit(main(process.argv.slice(2)));
}
