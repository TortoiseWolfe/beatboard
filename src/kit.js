/**
 * SYNTHESIZED DRUM KIT
 * Built from dsp.js primitives: NoiseBank, struckResonator, envelopes, filters.
 * No samples required — pure Web Audio synthesis.
 */
import { Rng } from './rng.js';
import {
  NoiseBank, biquad, gain, osc, hit, ad, sweep, series, shaper, saturationCurve,
  struckResonator, clamp, semis, lerp
} from './dsp.js';

export class Kit {
  constructor(actx, seed = 0xC0FFEE) {
    this.actx = actx;
    this.rng = new Rng(seed);
    this.bank = new NoiseBank(actx, this.rng.fork());
    this.masterGain = gain(actx, 1);
  }

  connect(dest) {
    this.masterGain.connect(dest);
  }

  /** Kick: deep sine + click + sub */
  kick(t0 = this.actx.currentTime, level = 1) {
    const out = gain(this.actx, 0);
    const rng = this.rng.fork();
    const jit = semis(rng.range(-1.5, 1.5));

    // Sub oscillator
    const sub = osc(this.actx, 'sine', 52 * jit);
    const subG = gain(this.actx, 0);
    series(sub, subG).connect(out);
    sweep(sub.frequency, t0, 68 * jit, 38 * jit, 0.18);
    ad(subG.gain, t0, 1.0 * level, 0.001, 0.18);
    sub.start(t0); sub.stop(t0 + 0.22);

    // Body
    const body = osc(this.actx, 'sine', 110 * jit);
    const bodyG = gain(this.actx, 0);
    const drv = shaper(this.actx, saturationCurve(3, 0.4), '2x');
    series(body, bodyG, drv).connect(out);
    sweep(body.frequency, t0, 140 * jit, 55 * jit, 0.08);
    ad(bodyG.gain, t0, 0.7 * level, 0.0015, 0.08);
    body.start(t0); body.stop(t0 + 0.16);

    // Click
    const click = this.bank.source('white', rng, rng.range(1.2, 1.8));
    const hp = biquad(this.actx, 'highpass', 2800, 0.7);
    const clickG = gain(this.actx, 0);
    series(click, hp, clickG).connect(out);
    hit(clickG.gain, t0, 0.45 * level, 0.004);
    click.start(t0, click._offset, 0.03);

    out.connect(this.masterGain);
    return { stop: () => out.disconnect() };
  }

  /** Snare: body + noise snap + ring */
  snare(t0 = this.actx.currentTime, level = 1) {
    const out = gain(this.actx, 0);
    const rng = this.rng.fork();
    const jit = semis(rng.range(-2, 2));

    // Body thump
    const body = osc(this.actx, 'triangle', 180 * jit);
    const bodyG = gain(this.actx, 0);
    const drv = shaper(this.actx, saturationCurve(2.5, 0.4), '2x');
    series(body, bodyG, drv).connect(out);
    sweep(body.frequency, t0, 220 * jit, 120 * jit, 0.06);
    ad(bodyG.gain, t0, 0.6 * level, 0.0015, 0.06);
    body.start(t0); body.stop(t0 + 0.12);

    // Noise snap
    const snap = this.bank.source('white', rng, rng.range(0.9, 1.3));
    const bp = biquad(this.actx, 'bandpass', 2200 * jit, 1.2);
    const snapG = gain(this.actx, 0);
    series(snap, bp, snapG).connect(out);
    sweep(bp.frequency, t0, 3200 * jit, 1400 * jit, 0.07);
    ad(snapG.gain, t0, 0.55 * level, 0.002, 0.07);
    snap.start(t0, snap._offset, 0.1);

    // Ring partials
    const ring = struckResonator(this.actx, this.bank, rng, t0, [
      { f: 1750 * semis(rng.range(-2, 2)), q: 28, g: 0.3 * level, decay: 0.15 },
      { f: 3100 * semis(rng.range(-2, 2)), q: 22, g: 0.18 * level, decay: 0.09 },
    ], 0.003);
    ring.connect(out);

    out.connect(this.masterGain);
    return { stop: () => out.disconnect() };
  }

  /** Closed hat: short noise burst */
  hatClosed(t0 = this.actx.currentTime, level = 1) {
    const out = gain(this.actx, 0);
    const rng = this.rng.fork();

    const src = this.bank.source('white', rng, rng.range(1.5, 2.2));
    const hp = biquad(this.actx, 'highpass', 8000, 0.8);
    const g = gain(this.actx, 0);
    series(src, hp, g).connect(out);
    hit(g.gain, t0, 0.35 * level, 0.018);
    src.start(t0, src._offset, 0.035);

    out.connect(this.masterGain);
    return { stop: () => out.disconnect() };
  }

  /** Open hat: longer noise with sweep */
  hatOpen(t0 = this.actx.currentTime, level = 1) {
    const out = gain(this.actx, 0);
    const rng = this.rng.fork();

    const src = this.bank.source('white', rng, rng.range(1.1, 1.5));
    const hp = biquad(this.actx, 'highpass', 6000, 0.7);
    const g = gain(this.actx, 0);
    series(src, hp, g).connect(out);
    sweep(hp.frequency, t0, 9000, 4000, 0.18);
    ad(g.gain, t0, 0.45 * level, 0.003, 0.18);
    src.start(t0, src._offset, 0.35);

    out.connect(this.masterGain);
    return { stop: () => out.disconnect() };
  }

  /** Ride: metallic ring */
  ride(t0 = this.actx.currentTime, level = 1) {
    const out = gain(this.actx, 0);
    const rng = this.rng.fork();

    const ring = struckResonator(this.actx, this.bank, rng, t0, [
      { f: 2200 * semis(rng.range(-1, 1)), q: 30, g: 0.4 * level, decay: 0.35 },
      { f: 3800 * semis(rng.range(-1, 1)), q: 24, g: 0.25 * level, decay: 0.22 },
      { f: 6200 * semis(rng.range(-1, 1)), q: 18, g: 0.15 * level, decay: 0.14 },
      { f: 9800 * semis(rng.range(-1, 1)), q: 14, g: 0.08 * level, decay: 0.08 },
    ], 0.0025);
    ring.connect(out);

    // Bell transient
    const click = this.bank.source('white', rng, 2.0);
    const hp = biquad(this.actx, 'highpass', 4000, 0.6);
    const cg = gain(this.actx, 0);
    series(click, hp, cg).connect(out);
    hit(cg.gain, t0, 0.2 * level, 0.003);
    click.start(t0, click._offset, 0.015);

    out.connect(this.masterGain);
    return { stop: () => out.disconnect() };
  }

  /** Clap: layered noise bursts */
  clap(t0 = this.actx.currentTime, level = 1) {
    const out = gain(this.actx, 0);
    const rng = this.rng.fork();

    for (let i = 0; i < 3; i++) {
      const ct = t0 + i * 0.012;
      const src = this.bank.source('white', rng, rng.range(0.9, 1.2));
      const bp = biquad(this.actx, 'bandpass', rng.range(1800, 2800), 0.9);
      const g = gain(this.actx, 0);
      series(src, bp, g).connect(out);
      ad(g.gain, ct, (i === 0 ? 0.5 : 0.25) * level, 0.002, 0.04);
      src.start(ct, src._offset, 0.06);
    }

    out.connect(this.masterGain);
    return { stop: () => out.disconnect() };
  }

  /** Tom: pitched sine with pitch drop */
  tom(t0 = this.actx.currentTime, level = 1, pitch = 1) {
    const out = gain(this.actx, 0);
    const rng = this.rng.fork();
    const baseFreq = 130 * pitch;

    const osc1 = osc(this.actx, 'sine', baseFreq);
    const g = gain(this.actx, 0);
    const drv = shaper(this.actx, saturationCurve(2, 0.3), '2x');
    series(osc1, g, drv).connect(out);
    sweep(osc1.frequency, t0, baseFreq * 1.3, baseFreq * 0.6, 0.12);
    ad(g.gain, t0, 0.6 * level, 0.002, 0.12);
    osc1.start(t0); osc1.stop(t0 + 0.18);

    out.connect(this.masterGain);
    return { stop: () => out.disconnect() };
  }

  /** Tink: bright metallic ping */
  tink(t0 = this.actx.currentTime, level = 1) {
    const out = gain(this.actx, 0);
    const rng = this.rng.fork();

    const ring = struckResonator(this.actx, this.bank, rng, t0, [
      { f: 4200 * semis(rng.range(-1, 1)), q: 40, g: 0.5 * level, decay: 0.18 },
      { f: 7800 * semis(rng.range(-1, 1)), q: 30, g: 0.3 * level, decay: 0.1 },
    ], 0.0015);
    ring.connect(out);

    out.connect(this.masterGain);
    return { stop: () => out.disconnect() };
  }

  /** Sub boom: very low sine */
  boom(t0 = this.actx.currentTime, level = 1) {
    const out = gain(this.actx, 0);
    const rng = this.rng.fork();

    const osc1 = osc(this.actx, 'sine', 42);
    const g = gain(this.actx, 0);
    series(osc1, g).connect(out);
    sweep(osc1.frequency, t0, 55, 32, 0.35);
    ad(g.gain, t0, 1.0 * level, 0.005, 0.35);
    osc1.start(t0); osc1.stop(t0 + 0.5);

    out.connect(this.masterGain);
    return { stop: () => out.disconnect() };
  }

  dispose() {
    this.bank.dispose();
    this.masterGain.disconnect();
  }
}