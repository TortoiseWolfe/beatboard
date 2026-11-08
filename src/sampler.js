/**
 * SAMPLER — plays a band member's sound pack (pack.json written by tools/sampler/build_pack.py).
 *
 * A pack holds recorded notes every few semitones. Any key is played from the nearest recorded note, repitched with
 * playbackRate. Each file already carries the instrument's own release (the note-off came at pack.hold_s), so a note
 * that is held at least that long just plays through. A shorter note starts a smooth fade at its end, over the pack's
 * release time, so sound always rings out and nothing is ever cut off. One-shots (drums) always play to the end.
 */

const FORMATS = ['ogg', 'mp3', 'wav'];
const MAX_FADE_S = 0.6;
const MIN_FADE_S = 0.12;

/** The recorded key nearest to `key` (the lower one on a tie, so a note is repitched up rather than down), with the repitch ratio. */
export function nearestNote(pack, key) {
  const keys = Object.keys(pack.notes).map(Number).sort((a, b) => a - b);
  if (!keys.length) throw new Error('pack has no notes');
  let best = keys[0];
  for (const k of keys) if (Math.abs(k - key) < Math.abs(best - key)) best = k;
  return { recorded: best, rate: Math.pow(2, (key - best) / 12), note: pack.notes[String(best)] };
}

/**
 * What to do for one note: which recorded note, the playback rate, and the gain envelope.
 * `lengthS` is how long the player holds the key. Returns { recorded, rate, fadeAtS, fadeS, endS } where
 * fadeAtS is null when the note plays straight through, and endS is when the sound is over (in context seconds after `when`).
 */
export function planNote(pack, key, lengthS) {
  const { recorded, rate, note } = nearestNote(pack, key);
  const fileLen = note.length_s / rate;
  if (pack.oneshot || lengthS == null || lengthS * rate >= note.hold_s) {
    return { recorded, rate, fadeAtS: null, fadeS: 0, endS: fileLen };
  }
  const fadeS = Math.min(MAX_FADE_S, Math.max(MIN_FADE_S, (note.release_s / rate) * 0.5));
  return { recorded, rate, fadeAtS: lengthS, fadeS, endS: Math.min(fileLen, lengthS + fadeS) };
}

export class PackPlayer {
  constructor(actx) {
    this.actx = actx;
    this.packs = new Map();     // member name -> { pack, buffers: Map<key, AudioBuffer> }
  }

  /** Fetch pack.json and every note file under `baseUrl` (the folder holding pack.json). Resolves the pack. */
  async load(name, baseUrl, fetchFn = fetch) {
    const root = baseUrl.replace(/\/$/, '');
    const pack = await (await fetchFn(root + '/pack.json')).json();
    const buffers = new Map();
    await Promise.all(Object.entries(pack.notes).map(async ([key, n]) => {
      const fmt = FORMATS.find(f => n.files[f] && this.canDecode(f));
      if (!fmt) throw new Error(`${name} ${key}: no playable format`);
      const bytes = await (await fetchFn(`${root}/${n.files[fmt]}`)).arrayBuffer();
      buffers.set(Number(key), await this.actx.decodeAudioData(bytes));
    }));
    this.packs.set(name, { pack, buffers });
    return pack;
  }

  canDecode(fmt) {
    if (typeof document === 'undefined') return true;
    const a = document.createElement('audio');
    const type = { ogg: 'audio/ogg; codecs="vorbis"', mp3: 'audio/mpeg', wav: 'audio/wav' }[fmt];
    return !!a.canPlayType && a.canPlayType(type) !== '';
  }

  has(name) { return this.packs.has(name); }

  /** Play `key` at context time `when`, held for `lengthS` seconds, into `dest`. Returns the plan used, or null when the pack is not loaded. */
  play(name, key, when, dest, lengthS, volume = 1) {
    const entry = this.packs.get(name);
    if (!entry) return null;
    const plan = planNote(entry.pack, key, lengthS);
    const buffer = entry.buffers.get(plan.recorded);
    const src = this.actx.createBufferSource();
    src.buffer = buffer;
    src.playbackRate.value = plan.rate;
    const g = this.actx.createGain();
    g.gain.setValueAtTime(volume, when);
    if (plan.fadeAtS != null) {
      g.gain.setValueAtTime(volume, when + plan.fadeAtS);
      g.gain.linearRampToValueAtTime(0, when + plan.fadeAtS + plan.fadeS);
    }
    src.connect(g);
    g.connect(dest);
    src.start(when);
    return plan;
  }
}
