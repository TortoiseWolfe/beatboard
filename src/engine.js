/**
 * ENGINE — AudioContext, tracks, master, lookahead clock, quantized launch.
 * Samples decoded once into AudioBuffers; synthesized drums via Kit.
 * Lookahead: ~25ms timer, 100ms window, scheduled on AudioContext.currentTime.
 */
import { Kit } from './kit.js';
import { getDefaultPreset } from './patterns.js';
import { computeAudible, resetMixer } from './mixer.js';
import { loadKeymap, loadLayer, isTextInputFocused, createLearnMode } from './keymap.js';
import { getMusicianForTrack } from './band.js';

const LOOKAHEAD_MS = 25;
const SCHEDULE_WINDOW_MS = 100;
const TIMER_INTERVAL_MS = 25;

export class Engine {
  constructor() {
    this.actx = null;
    this.kit = null;
    this.masterGain = null;
    this.limiter = null;
    this.tracks = [];
    this.tempo = 110;
    this.isPlaying = false;
    this.currentStep = 0;
    this.nextTickTime = 0;
    this.timerId = null;
    this.lookaheadTimerId = null;
    this.stepDuration = 0;
    this.beatDuration = 0;
    this.barDuration = 0;
    this.patterns = getDefaultPreset();
    this.scheduledNotes = new Map();
    this.jingleBuffers = new Map();
    this.pianoBuffers = new Map();
    this.bedBuffers = new Map();
    this.quarterFlipBuffer = null;
    this.keymap = loadKeymap();
    this.currentLayer = loadLayer();
    this.learnMode = createLearnMode((code, binding) => this.onLearnComplete(code, binding));
    this.masterLevel = 0.8;
    this.presetIndex = 0;
    this.presetNames = ['Hip Hop', 'Basic Rock', 'Disco', 'Jazz', 'Waltz'];
    this.onTrackLaunchCallbacks = [];
    this.onTransportCallbacks = [];
    this.onTempoCallbacks = [];
    this.onStepCallbacks = [];
    this.onMasterLevelCallbacks = [];
    this.onPresetChangeCallbacks = [];
    this.onLearnCallbacks = [];
    this.jingleManifest = null;
    this.jingleLocalManifest = null;
  }

  async init() {
    this.actx = new (window.AudioContext || window.webkitAudioContext)();
    this.kit = new Kit(this.actx);
    this.masterGain = this.actx.createGain();
    this.masterGain.gain.value = this.masterLevel;

    this.limiter = this.actx.createWaveShaper();
    this.limiter.curve = this.makeLimiterCurve();
    this.limiter.oversample = '2x';

    this.masterGain.connect(this.limiter);
    this.limiter.connect(this.actx.destination);
    this.kit.connect(this.masterGain);

    await this.loadSamples();
    this.updateTiming();
    this.startLookaheadClock();
  }

  makeLimiterCurve() {
    const n = 4096;
    const curve = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      const x = (i / (n - 1)) * 2 - 1;
      const a = Math.abs(x);
      let y;
      if (a < 0.66) y = x;
      else y = Math.sign(x) * (0.66 + (1 - 0.66) * Math.tanh((a - 0.66) / (1 - 0.66)));
      curve[i] = y * 0.985;
    }
    return curve;
  }

  async loadSamples() {
    const pianoNotes = [
      'a1', 'a1s', 'b1', 'c1', 'c1s', 'c2', 'd1', 'd1s', 'e1', 'f1', 'f1s', 'g1', 'g1s'
    ];

    for (const note of pianoNotes) {
      try {
        const resp = await fetch(`assets/piano/${note}.mp3`);
        const arrayBuffer = await resp.arrayBuffer();
        const buffer = await this.actx.decodeAudioData(arrayBuffer);
        this.pianoBuffers.set(note, buffer);
      } catch (e) {
        console.warn(`Failed to load piano/${note}.mp3`, e);
      }
    }

    const bedFiles = [
      { id: 'bed1', url: 'assets/beds/404840_dark-hop-beet-f2.mp3' },
      { id: 'bed2', url: 'assets/beds/409940_webandbotmadeloop.mp3' },
      { id: 'bed3', url: 'assets/beds/435147_ambient-drone.mp3' },
      { id: 'bed4', url: 'assets/beds/441375_organ.mp3' },
      { id: 'acid1', url: 'assets/beds/214775_acid-bass.mp3' },
      { id: 'acid2', url: 'assets/beds/214958_acid-mod-bass.mp3' }
    ];

    for (const f of bedFiles) {
      try {
        const resp = await fetch(f.url);
        const arrayBuffer = await resp.arrayBuffer();
        const buffer = await this.actx.decodeAudioData(arrayBuffer);
        this.bedBuffers.set(f.id, buffer);
      } catch (e) {
        console.warn(`Failed to load ${f.url}`, e);
      }
    }

    try {
      const resp = await fetch('assets/fx/quarter-flip.mp3');
      const arrayBuffer = await resp.arrayBuffer();
      this.quarterFlipBuffer = await this.actx.decodeAudioData(arrayBuffer);
    } catch (e) {
      console.warn('Failed to load quarter-flip.mp3', e);
    }

    await this.loadJingleManifests();
  }

  async loadJingleManifests() {
    try {
      const resp = await fetch('assets/jingle/manifest.json');
      this.jingleManifest = await resp.json();
    } catch (_) {
      this.jingleManifest = { takes: [] };
    }
    try {
      const resp = await fetch('assets/jingle-local/manifest.json');
      this.jingleLocalManifest = await resp.json();
    } catch (_) {
      this.jingleLocalManifest = null;
    }
  }

  getJingleTakes() {
    const takes = [];
    if (this.jingleManifest?.takes) takes.push(...this.jingleManifest.takes);
    if (this.jingleLocalManifest?.takes) takes.push(...this.jingleLocalManifest.takes);
    return takes;
  }

  async loadJingleTake(file) {
    const base = this.jingleLocalManifest ? 'assets/jingle-local/' : 'assets/jingle/';
    try {
      const resp = await fetch(base + file);
      const arrayBuffer = await resp.arrayBuffer();
      return await this.actx.decodeAudioData(arrayBuffer);
    } catch (e) {
      console.warn(`Failed to load jingle ${file}`, e);
      return null;
    }
  }

  updateTiming() {
    this.beatDuration = 60 / this.tempo;
    this.stepDuration = this.beatDuration / 2;
    this.barDuration = this.beatDuration * 4;
  }

  startLookaheadClock() {
    if (this.lookaheadTimerId) clearInterval(this.lookaheadTimerId);
    this.lookaheadTimerId = setInterval(() => this.tick(), TIMER_INTERVAL_MS);
  }

  tick() {
    if (!this.isPlaying) return;
    const now = this.actx.currentTime;
    const windowEnd = now + SCHEDULE_WINDOW_MS / 1000;

    while (this.nextTickTime < windowEnd) {
      this.scheduleStep(this.nextTickTime);
      this.nextTickTime += this.stepDuration;
      this.currentStep = (this.currentStep + 1) % 8;
      if (this.currentStep === 0) {
        this.onTrackLaunchCallbacks.forEach(cb => cb());
      }
    }
  }

  scheduleStep(playTime) {
    const step = this.currentStep;
    const audible = computeAudible(this.patterns);

    this.patterns.forEach((track, i) => {
      if (!audible[i]) return;
      if (track.pattern[step] !== 1) return;
      this.playTrackSound(i, track, playTime, track.level);
    });

    this.onStepCallbacks.forEach(cb => cb(step, playTime));
  }

  playTrackSound(trackIndex, track, when, level) {
    const audible = computeAudible(this.patterns);
    if (!audible[trackIndex]) return;

    const gain = this.actx.createGain();
    gain.gain.value = level * (track.level ?? 1);
    gain.connect(this.kit.masterGain);

    switch (trackIndex) {
      case 0: this.kit.kick(when, level * (track.level ?? 1)); break;
      case 1: this.kit.snare(when, level * (track.level ?? 1)); break;
      case 2:
        if (track.pad === 'hatOpen') this.kit.hatOpen(when, level * (track.level ?? 1));
        else if (track.pad === 'ride') this.kit.ride(when, level * (track.level ?? 1));
        else this.kit.hatClosed(when, level * (track.level ?? 1));
        break;
      case 3:
        if (track.pad === 'tom') this.kit.tom(when, level * (track.level ?? 1));
        else if (track.pad === 'tink') this.kit.tink(when, level * (track.level ?? 1));
        else this.kit.clap(when, level * (track.level ?? 1));
        break;
      case 4:
        if (track.pad === 'boom') this.kit.boom(when, level * (track.level ?? 1));
        else this.playBassSample(track.pad, when, gain);
        break;
      case 5:
        this.playPianoNote(track.note, track.sharp, track.octave || 0, when, gain);
        break;
      case 6:
        this.playBedSample(track.pad, when, gain);
        break;
      case 7:
        this.playJingle(track.kind, when, gain);
        break;
    }
  }

  playBassSample(pad, when, gain) {
    const buffer = this.bedBuffers.get(pad === 'acid' ? 'acid1' : 'acid2');
    if (!buffer) return;
    const src = this.actx.createBufferSource();
    src.buffer = buffer;
    src.connect(gain);
    src.start(when);
  }

  playPianoNote(note, sharp, octave, when, gain) {
    const noteName = `${note}${sharp ? 's' : ''}${octave + 1}`;
    const buffer = this.pianoBuffers.get(noteName);
    if (!buffer) return;
    const src = this.actx.createBufferSource();
    src.buffer = buffer;
    src.connect(gain);
    src.start(when);
  }

  playBedSample(pad, when, gain) {
    const buffer = this.bedBuffers.get(pad);
    if (!buffer) return;
    const src = this.actx.createBufferSource();
    src.buffer = buffer;
    src.loop = true;
    src.connect(gain);
    src.start(when);
    return src;
  }

  playJingle(kind, when, gain) {
    const takes = this.getJingleTakes().filter(t => t.kind === kind);
    if (!takes.length) return;
    const take = takes[0];
    this.loadJingleTake(take.file).then(buffer => {
      if (!buffer) return;
      const src = this.actx.createBufferSource();
      src.buffer = buffer;
      src.connect(gain);
      src.start(this.actx.currentTime + 0.01);
    });
  }

  async handleKeyDown(e) {
    if (isTextInputFocused()) return;
    if (this.learnMode.isActive()) {
      this.learnMode.handleKey(e.code, e.shiftKey);
      e.preventDefault();
      return;
    }

    const binding = this.keymap[this.currentLayer][e.code];
    if (!binding) return;

    switch (binding.action) {
      case 'hit':
        this.playHit(binding.track, binding.pad, binding);
        break;
      case 'launch':
        this.launchTrack(binding.track, binding.kind, e.shiftKey);
        break;
      case 'transport':
        this.toggleTransport();
        break;
      case 'tempo':
        this.changeTempo(e.shiftKey ? binding.delta * 5 : binding.delta);
        break;
      case 'masterLevel':
        this.changeMasterLevel(binding.delta);
        break;
      case 'preset':
        this.changePreset(binding.delta);
        break;
      case 'resetMixer':
        this.resetMixer();
        break;
      case 'stopAll':
        this.stopAll();
        break;
      case 'learnToggle':
        this.toggleLearnMode();
        break;
      case 'mute':
        this.toggleMute(binding.track);
        break;
      case 'solo':
        this.toggleSolo(binding.track);
        break;
      case 'level':
        this.adjustLevel(binding.track, e.shiftKey ? -binding.delta : binding.delta);
        break;
    }
    e.preventDefault();
  }

  handleKeyUp(e) {
    if (this.currentLayer === LAYERS.MIX && e.code === 'Space') {
      this.setLayer(LAYERS.PLAY);
    }
  }

  setLayer(layer) {
    this.currentLayer = layer;
    saveLayer(layer);
    this.onLayerChangeCallbacks?.forEach(cb => cb(layer));
  }

  toggleLearnMode() {
    this.setLayer(LAYERS.PLAY);
    this.learnMode.enter('learn', null, null);
    this.onLearnCallbacks.forEach(cb => cb(true));
  }

  onLearnComplete(code, binding) {
    this.onLearnCallbacks.forEach(cb => cb(false, code, binding));
  }

  playHit(trackIndex, pad, binding) {
    const track = this.patterns[trackIndex - 1];
    if (!track) return;
    const when = this.actx.currentTime;
    const gain = this.actx.createGain();
    gain.gain.value = track.level ?? 0.7;
    gain.connect(this.kit.masterGain);

    switch (trackIndex) {
      case 1: this.kit.kick(when, gain.gain.value); break;
      case 2: this.kit.snare(when, gain.gain.value); break;
      case 3:
        if (pad === 'hatOpen') this.kit.hatOpen(when, gain.gain.value);
        else if (pad === 'ride') this.kit.ride(when, gain.gain.value);
        else this.kit.hatClosed(when, gain.gain.value);
        break;
      case 4:
        if (pad === 'tom') this.kit.tom(when, gain.gain.value);
        else if (pad === 'tink') this.kit.tink(when, gain.gain.value);
        else this.kit.clap(when, gain.gain.value);
        break;
      case 5:
        if (pad === 'boom') this.kit.boom(when, gain.gain.value);
        break;
      case 6:
        this.playPianoNote(binding.note, binding.sharp, binding.octave || 0, when, gain);
        break;
      case 7:
        if (pad === 'quarterFlip' && this.quarterFlipBuffer) {
          const src = this.actx.createBufferSource();
          src.buffer = this.quarterFlipBuffer;
          src.connect(gain);
          src.start(when);
        }
        break;
      case 8:
        break;
    }
  }

  launchTrack(trackNum, kind, immediate) {
    const track = this.patterns[trackNum - 1];
    if (!track) return;

    const when = immediate ? this.actx.currentTime : this.quantizeToNextBar();
    track.launched = true;
    track.launchKind = kind;
    track.launchTime = when;

    if (trackNum <= 4) {
      track.muted = false;
    } else if (trackNum === 7) {
      track.muted = false;
      if (kind === 'bed') {
        track.bedSource = this.playBedSample('bed1', when, this.kit.masterGain);
      }
    } else if (trackNum === 8) {
      track.muted = false;
      this.playJingle(kind || 'hook', when, this.kit.masterGain);
    }

    this.onTrackLaunchCallbacks.forEach(cb => cb(trackNum, when, immediate));
  }

  stopTrack(trackNum) {
    const track = this.patterns[trackNum - 1];
    if (!track) return;
    track.launched = false;
    track.muted = true;
    if (track.bedSource) {
      track.bedSource.stop();
      track.bedSource = null;
    }
    this.onTrackLaunchCallbacks.forEach(cb => cb(trackNum, 0, false));
  }

  quantizeToNextBar() {
    const now = this.actx.currentTime;
    const elapsed = (now - this.nextTickTime) % this.barDuration;
    return now + (this.barDuration - elapsed) + 0.001;
  }

  toggleTransport() {
    if (this.isPlaying) {
      this.stop();
    } else {
      this.start();
    }
  }

  start() {
    if (this.actx.state === 'suspended') this.actx.resume();
    this.isPlaying = true;
    this.nextTickTime = this.actx.currentTime + 0.01;
    this.currentStep = 0;
    this.onTransportCallbacks.forEach(cb => cb(true));
  }

  stop() {
    this.isPlaying = false;
    this.onTransportCallbacks.forEach(cb => cb(false));
  }

  stopAll() {
    this.stop();
    this.patterns.forEach(t => {
      t.launched = false;
      t.muted = true;
      if (t.bedSource) {
        t.bedSource.stop();
        t.bedSource = null;
      }
    });
    this.currentStep = 0;
  }

  changeTempo(delta) {
    this.tempo = Math.max(60, Math.min(200, this.tempo + delta));
    this.updateTiming();
    this.onTempoCallbacks.forEach(cb => cb(this.tempo));
  }

  changeMasterLevel(delta) {
    this.masterLevel = Math.max(0, Math.min(1, this.masterLevel + delta));
    if (this.masterGain) this.masterGain.gain.value = this.masterLevel;
    this.onMasterLevelCallbacks.forEach(cb => cb(this.masterLevel));
  }

  changePreset(delta) {
    this.presetIndex = (this.presetIndex + delta + this.presetNames.length) % this.presetNames.length;
    const name = this.presetNames[this.presetIndex];
    this.patterns = getPreset(name);
    this.onPresetChangeCallbacks.forEach(cb => cb(name, this.patterns));
  }

  resetMixer() {
    this.patterns = resetMixer(this.patterns);
    this.onPresetChangeCallbacks.forEach(cb => cb(this.presetNames[this.presetIndex], this.patterns));
  }

  toggleMute(trackNum) {
    const track = this.patterns[trackNum - 1];
    if (!track) return;
    track.muted = !track.muted;
    if (track.muted) track.solo = false;
    this.onPresetChangeCallbacks.forEach(cb => cb(this.presetNames[this.presetIndex], this.patterns));
  }

  toggleSolo(trackNum) {
    const track = this.patterns[trackNum - 1];
    if (!track) return;
    track.solo = !track.solo;
    if (track.solo) track.muted = false;
    this.onPresetChangeCallbacks.forEach(cb => cb(this.presetNames[this.presetIndex], this.patterns));
  }

  adjustLevel(trackNum, delta) {
    const track = this.patterns[trackNum - 1];
    if (!track) return;
    track.level = Math.max(0, Math.min(1, (track.level ?? 0.7) + delta));
    this.onPresetChangeCallbacks.forEach(cb => cb(this.presetNames[this.presetIndex], this.patterns));
  }

  onTrackLaunch(cb) { this.onTrackLaunchCallbacks.push(cb); }
  onTransport(cb) { this.onTransportCallbacks.push(cb); }
  onTempo(cb) { this.onTempoCallbacks.push(cb); }
  onStep(cb) { this.onStepCallbacks.push(cb); }
  onMasterLevel(cb) { this.onMasterLevelCallbacks.push(cb); }
  onPresetChange(cb) { this.onPresetChangeCallbacks.push(cb); }
  onLearn(cb) { this.onLearnCallbacks.push(cb); }
  onLayerChange(cb) { this.onLayerChangeCallbacks = this.onLayerChangeCallbacks || []; this.onLayerChangeCallbacks.push(cb); }

  getState() {
    return {
      tempo: this.tempo,
      isPlaying: this.isPlaying,
      currentStep: this.currentStep,
      patterns: this.patterns,
      masterLevel: this.masterLevel,
      currentPreset: this.presetNames[this.presetIndex],
      currentLayer: this.currentLayer
    };
  }

  dispose() {
    if (this.lookaheadTimerId) clearInterval(this.lookaheadTimerId);
    if (this.timerId) clearInterval(this.timerId);
    this.kit.dispose();
    this.actx?.close();
  }
}