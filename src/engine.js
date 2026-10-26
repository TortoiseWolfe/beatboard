/**
 * ENGINE — AudioContext, 8 track GainNodes, master gain, limiter, lookahead clock, quantized launch.
 * Samples decoded once into AudioBuffers; synthesized drums via Kit.
 * Lookahead: ~25ms timer, 100ms window, scheduled on AudioContext.currentTime.
 */
import { Kit } from './kit.js';
import { getPreset, getDefaultPreset, presetNames } from './patterns.js';
import { computeAudible, resetMixer, clearAllSolo } from './mixer.js';
import { loadKeymap, saveKeymap, loadLayer, saveLayer, isTextInputFocused, createLearnMode, LAYERS } from './keymap.js';

const TIMER_INTERVAL_MS = 25;
const SCHEDULE_WINDOW_MS = 100;

export class Engine {
  constructor() {
    this.actx = null;
    this.kit = null;
    this.masterGain = null;
    this.limiter = null;
    this.trackGains = [];
    this.tempo = 110;
    this.isPlaying = false;
    this.currentStep = 0;
    this.nextTickTime = 0;
    this.lookaheadTimerId = null;
    this.stepDuration = 0;
    this.beatDuration = 0;
    this.barDuration = 0;
    this.patterns = getDefaultPreset();
    this.jingleBuffers = new Map();
    this.pianoBuffers = new Map();
    this.bedBuffers = new Map();
    this.quarterFlipBuffer = null;
    this.keymap = loadKeymap();
    this.currentLayer = loadLayer();
    this.learnMode = createLearnMode((code, binding) => this.onLearnComplete(code, binding));
    this.masterLevel = 0.8;
    this.presetIndex = 0;
    this.presetNames = presetNames;
    this.selectedJingleFile = null;
    this.activeJingleSource = null;
    this.activeBedSource = null;
    this.lastHitPad = 'Ready';

    this.onTrackLaunchCallbacks = [];
    this.onTransportCallbacks = [];
    this.onTempoCallbacks = [];
    this.onStepCallbacks = [];
    this.onMasterLevelCallbacks = [];
    this.onPresetChangeCallbacks = [];
    this.onLearnCallbacks = [];
    this.onLayerChangeCallbacks = [];
    this.onLastPadCallbacks = [];

    this.jingleManifest = null;
    this.jingleLocalManifest = null;
    this.updateTiming();
  }

  async init() {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    this.actx = new AudioCtx();
    this.kit = new Kit(this.actx);

    this.masterGain = this.actx.createGain();
    this.masterGain.gain.value = this.masterLevel;

    this.limiter = this.actx.createWaveShaper();
    this.limiter.curve = this.makeLimiterCurve();
    this.limiter.oversample = '2x';

    this.masterGain.connect(this.limiter);
    this.limiter.connect(this.actx.destination);

    // One GainNode per track into master gain
    this.trackGains = [];
    for (let i = 0; i < 8; i++) {
      const g = this.actx.createGain();
      g.gain.value = (this.patterns[i]?.volume ?? 0.7);
      g.connect(this.masterGain);
      this.trackGains.push(g);
    }
    this.updateTrackGains();

    await this.loadSamples();
    this.updateTiming();
    this.startLookaheadClock();
  }

  ensureAudioContext() {
    if (!this.actx) return;
    if (this.actx.state === 'suspended') {
      this.actx.resume().catch(console.error);
    }
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

  updateTrackGains() {
    if (!this.actx || !this.trackGains.length) return;
    const audible = computeAudible(this.patterns);
    const now = this.actx.currentTime;
    this.patterns.forEach((track, i) => {
      const isAudible = audible[i];
      const level = track.level ?? track.volume ?? 0.7;
      const target = isAudible ? level : 0;
      this.trackGains[i].gain.setValueAtTime(target, now);
    });
  }

  async loadSamples() {
    const pianoNotes = [
      'a1', 'a1s', 'b1', 'c1', 'c1s', 'c2', 'd1', 'd1s', 'e1', 'f1', 'f1s', 'g1', 'g1s'
    ];

    for (const note of pianoNotes) {
      try {
        const resp = await fetch(`assets/piano/${note}.mp3`);
        if (resp.ok) {
          const arrayBuffer = await resp.arrayBuffer();
          const buffer = await this.actx.decodeAudioData(arrayBuffer);
          this.pianoBuffers.set(note, buffer);
        }
      } catch (_) {}
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
        if (resp.ok) {
          const arrayBuffer = await resp.arrayBuffer();
          const buffer = await this.actx.decodeAudioData(arrayBuffer);
          this.bedBuffers.set(f.id, buffer);
        }
      } catch (_) {}
    }

    try {
      const resp = await fetch('assets/fx/quarter-flip.mp3');
      if (resp.ok) {
        const arrayBuffer = await resp.arrayBuffer();
        this.quarterFlipBuffer = await this.actx.decodeAudioData(arrayBuffer);
      }
    } catch (_) {}

    await this.loadJingleManifests();
  }

  async loadJingleManifests() {
    try {
      const resp = await fetch('assets/jingle/manifest.json');
      if (resp.ok) this.jingleManifest = await resp.json();
    } catch (_) {
      this.jingleManifest = { takes: [] };
    }
    try {
      const resp = await fetch('assets/jingle-local/manifest.json');
      if (resp.ok) {
        this.jingleLocalManifest = await resp.json();
      }
    } catch (_) {
      this.jingleLocalManifest = null;
    }
  }

  getJingleTakes() {
    const takes = [];
    if (this.jingleLocalManifest?.takes?.length) {
      takes.push(...this.jingleLocalManifest.takes);
    } else if (this.jingleManifest?.takes?.length) {
      takes.push(...this.jingleManifest.takes);
    }
    return takes;
  }

  async loadJingleTake(file) {
    if (this.jingleBuffers.has(file)) {
      return this.jingleBuffers.get(file);
    }
    const base = this.jingleLocalManifest ? 'assets/jingle-local/' : 'assets/jingle/';
    try {
      const resp = await fetch(base + file);
      if (resp.ok) {
        const arrayBuffer = await resp.arrayBuffer();
        const buffer = await this.actx.decodeAudioData(arrayBuffer);
        this.jingleBuffers.set(file, buffer);
        return buffer;
      }
    } catch (_) {}
    return null;
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
    if (!this.isPlaying || !this.actx) return;
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

    for (let i = 0; i < 4; i++) {
      const track = this.patterns[i];
      if (!track || !track.pattern) continue;
      if (track.pattern[step] === 1 && audible[i]) {
        this.playSequencedDrum(i, playTime);
      }
    }

    this.onStepCallbacks.forEach(cb => cb(step, playTime));
  }

  playSequencedDrum(trackIndex, when) {
    if (!this.actx || !this.kit) return;
    const dest = this.trackGains[trackIndex];
    if (!dest) return;

    // Connect kit voice temporarily into track gain
    const originalMasterGain = this.kit.masterGain;
    this.kit.masterGain = dest;

    switch (trackIndex) {
      case 0: this.kit.kick(when, 1); break;
      case 1: this.kit.snare(when, 1); break;
      case 2: this.kit.hatClosed(when, 1); break;
      case 3: this.kit.clap(when, 1); break;
    }
    this.kit.masterGain = originalMasterGain;
  }

  async handleKeyDown(e) {
    this.ensureAudioContext();
    if (isTextInputFocused()) return;

    if (this.learnMode.isActive()) {
      this.learnMode.handleKey(e.code, e.shiftKey);
      e.preventDefault();
      return;
    }

    if (e.key === '?' || (e.shiftKey && e.code === 'Slash')) {
      e.preventDefault();
      const dialog = document.getElementById('bandDialog');
      if (dialog) dialog.showModal();
      return;
    }

    const binding = this.keymap[this.currentLayer]?.[e.code];
    if (!binding) return;

    switch (binding.action) {
      case 'hit':
        this.playHit(binding.track, binding.pad, binding, e.shiftKey);
        break;
      case 'launch':
        this.launchOrStopTrack(binding.track, binding.kind, e.shiftKey);
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
        if (e.shiftKey) {
          this.patterns = clearAllSolo(this.patterns);
          this.updateTrackGains();
          this.onPresetChangeCallbacks.forEach(cb => cb(this.presetNames[this.presetIndex], this.patterns));
        } else {
          this.toggleSolo(binding.track);
        }
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
    this.onLayerChangeCallbacks.forEach(cb => cb(layer));
  }

  toggleLearnMode() {
    this.setLayer(LAYERS.PLAY);
    this.learnMode.enter('learn', null, null);
    this.onLearnCallbacks.forEach(cb => cb(true));
  }

  onLearnComplete(code, binding) {
    this.onLearnCallbacks.forEach(cb => cb(false, code, binding));
  }

  setLastHitPad(name) {
    this.lastHitPad = name;
    this.onLastPadCallbacks.forEach(cb => cb(name));
  }

  playHit(trackNum, pad, binding = {}, shiftKey = false) {
    this.ensureAudioContext();
    if (!this.actx || !this.kit) return;
    const trackIndex = trackNum - 1;
    const dest = this.trackGains[trackIndex] || this.masterGain;
    const when = this.actx.currentTime;

    const originalMasterGain = this.kit.masterGain;
    this.kit.masterGain = dest;

    switch (trackNum) {
      case 1:
        this.kit.kick(when, 1);
        this.setLastHitPad('Kick');
        break;
      case 2:
        this.kit.snare(when, 1);
        this.setLastHitPad('Snare');
        break;
      case 3:
        if (pad === 'hatOpen') {
          this.kit.hatOpen(when, 1);
          this.setLastHitPad('Open Hat');
        } else if (pad === 'ride') {
          this.kit.ride(when, 1);
          this.setLastHitPad('Ride');
        } else {
          this.kit.hatClosed(when, 1);
          this.setLastHitPad('Closed Hat');
        }
        break;
      case 4:
        if (pad === 'tom') {
          this.kit.tom(when, 1);
          this.setLastHitPad('Tom');
        } else if (pad === 'tink') {
          this.kit.tink(when, 1);
          this.setLastHitPad('Tink');
        } else {
          this.kit.clap(when, 1);
          this.setLastHitPad('Clap');
        }
        break;
      case 5:
        if (pad === 'boom') {
          this.kit.boom(when, 1);
          this.setLastHitPad('Sub Boom');
        } else {
          this.playBassSample(pad, when, dest);
          this.setLastHitPad('Acid Bass');
        }
        break;
      case 6: {
        const note = (shiftKey || binding.sharp) ? (binding.sharpNote || `${binding.note}s`) : (binding.note || 'c1');
        this.playPianoNote(note, when, dest);
        this.setLastHitPad(`Piano ${note.toUpperCase()}`);
        break;
      }
      case 7:
        if (pad === 'quarterFlip' || !pad) {
          this.playQuarterFlip(when, dest);
          this.setLastHitPad('Quarter Flip');
        }
        break;
      case 8:
        if (binding.kind === 'hook') {
          this.playJingleTakeByKind('hook', dest);
          this.setLastHitPad('Jingle Hook');
        } else if (binding.kind === 'full') {
          this.playJingleTakeByKind('song', dest);
          this.setLastHitPad('Jingle Full');
        }
        break;
    }

    this.kit.masterGain = originalMasterGain;
  }

  playPianoNote(noteName, when, dest) {
    const key = noteName.toLowerCase();
    const buffer = this.pianoBuffers.get(key);
    if (!buffer) return;
    const src = this.actx.createBufferSource();
    src.buffer = buffer;
    src.connect(dest);
    src.start(when);
  }

  playQuarterFlip(when, dest) {
    if (!this.quarterFlipBuffer) return;
    const src = this.actx.createBufferSource();
    src.buffer = this.quarterFlipBuffer;
    src.connect(dest);
    src.start(when);
  }

  playBassSample(pad, when, dest) {
    const key = pad === 'acid2' ? 'acid2' : 'acid1';
    const buffer = this.bedBuffers.get(key);
    if (!buffer) return;
    const src = this.actx.createBufferSource();
    src.buffer = buffer;
    src.connect(dest);
    src.start(when);
  }

  playBedLoop(when, dest) {
    if (this.activeBedSource) {
      try { this.activeBedSource.stop(); } catch (_) {}
      this.activeBedSource = null;
    }
    const track = this.patterns[6];
    const buffer = track?.userBuffer || this.bedBuffers.get('bed1');
    if (!buffer) return;
    const src = this.actx.createBufferSource();
    src.buffer = buffer;
    src.loop = true;
    src.connect(dest);
    src.start(when);
    this.activeBedSource = src;
  }

  stopBedLoop() {
    if (this.activeBedSource) {
      try { this.activeBedSource.stop(); } catch (_) {}
      this.activeBedSource = null;
    }
  }

  async playJingleTakeByKind(kind, dest) {
    if (this.activeJingleSource) {
      try { this.activeJingleSource.stop(); } catch (_) {}
      this.activeJingleSource = null;
      return;
    }
    const takes = this.getJingleTakes();
    let take = takes.find(t => t.file === this.selectedJingleFile);
    if (!take) {
      take = takes.find(t => t.kind === kind) || takes[0];
    }
    if (!take) return;

    const buffer = await this.loadJingleTake(take.file);
    if (!buffer || !this.actx) return;
    const src = this.actx.createBufferSource();
    src.buffer = buffer;
    src.connect(dest);
    src.onended = () => {
      if (this.activeJingleSource === src) this.activeJingleSource = null;
    };
    src.start(this.actx.currentTime + 0.01);
    this.activeJingleSource = src;
  }

  launchOrStopTrack(trackNum, kind, immediate) {
    const track = this.patterns[trackNum - 1];
    if (!track) return;
    if (track.launched) {
      this.stopTrack(trackNum, immediate);
    } else {
      this.launchTrack(trackNum, kind, immediate);
    }
  }

  launchTrack(trackNum, kind, immediate) {
    const track = this.patterns[trackNum - 1];
    if (!track) return;
    const when = immediate ? (this.actx?.currentTime || 0) : this.quantizeToNextBar();

    track.launched = true;
    track.launchKind = kind;
    track.muted = false;
    this.updateTrackGains();

    if (trackNum === 7) {
      this.playBedLoop(when, this.trackGains[6]);
    } else if (trackNum === 8) {
      this.playJingleTakeByKind(kind || 'hook', this.trackGains[7]);
    }

    this.onTrackLaunchCallbacks.forEach(cb => cb(trackNum, when, true));
  }

  stopTrack(trackNum, immediate) {
    const track = this.patterns[trackNum - 1];
    if (!track) return;
    track.launched = false;
    track.muted = true;
    this.updateTrackGains();

    if (trackNum === 7) {
      this.stopBedLoop();
    } else if (trackNum === 8) {
      if (this.activeJingleSource) {
        try { this.activeJingleSource.stop(); } catch (_) {}
        this.activeJingleSource = null;
      }
    }

    this.onTrackLaunchCallbacks.forEach(cb => cb(trackNum, 0, false));
  }

  quantizeToNextBar(currentTime = (this.actx?.currentTime || 0)) {
    const elapsed = (currentTime - this.nextTickTime) % this.barDuration;
    return currentTime + (this.barDuration - elapsed) + 0.001;
  }

  toggleTransport() {
    this.ensureAudioContext();
    if (this.isPlaying) {
      this.stop();
    } else {
      this.start();
    }
  }

  start() {
    this.ensureAudioContext();
    this.isPlaying = true;
    this.nextTickTime = (this.actx?.currentTime || 0) + 0.01;
    this.currentStep = 0;
    this.onTransportCallbacks.forEach(cb => cb(true));
  }

  stop() {
    this.isPlaying = false;
    this.onTransportCallbacks.forEach(cb => cb(false));
  }

  stopAll() {
    this.stop();
    this.patterns.forEach((t, i) => {
      t.launched = false;
      t.muted = true;
    });
    this.stopBedLoop();
    if (this.activeJingleSource) {
      try { this.activeJingleSource.stop(); } catch (_) {}
      this.activeJingleSource = null;
    }
    this.updateTrackGains();
    this.currentStep = 0;
    this.onPresetChangeCallbacks.forEach(cb => cb(this.presetNames[this.presetIndex], this.patterns));
  }

  changeTempo(delta) {
    this.tempo = Math.max(60, Math.min(200, this.tempo + delta));
    this.updateTiming();
    this.onTempoCallbacks.forEach(cb => cb(this.tempo));
  }

  changeMasterLevel(delta) {
    this.masterLevel = Math.max(0, Math.min(1, Math.round((this.masterLevel + delta) * 100) / 100));
    if (this.masterGain && this.actx) {
      this.masterGain.gain.setValueAtTime(this.masterLevel, this.actx.currentTime);
    }
    this.onMasterLevelCallbacks.forEach(cb => cb(this.masterLevel));
  }

  changePreset(delta) {
    this.presetIndex = (this.presetIndex + delta + this.presetNames.length) % this.presetNames.length;
    const name = this.presetNames[this.presetIndex];
    this.patterns = getPreset(name);
    this.updateTrackGains();
    this.onPresetChangeCallbacks.forEach(cb => cb(name, this.patterns));
  }

  resetMixer() {
    this.patterns = resetMixer(this.patterns);
    this.updateTrackGains();
    this.onPresetChangeCallbacks.forEach(cb => cb(this.presetNames[this.presetIndex], this.patterns));
  }

  toggleMute(trackNum) {
    const track = this.patterns[trackNum - 1];
    if (!track) return;
    track.muted = !track.muted;
    if (track.muted) track.solo = false;
    this.updateTrackGains();
    this.onPresetChangeCallbacks.forEach(cb => cb(this.presetNames[this.presetIndex], this.patterns));
  }

  toggleSolo(trackNum) {
    const track = this.patterns[trackNum - 1];
    if (!track) return;
    track.solo = !track.solo;
    if (track.solo) track.muted = false;
    this.updateTrackGains();
    this.onPresetChangeCallbacks.forEach(cb => cb(this.presetNames[this.presetIndex], this.patterns));
  }

  adjustLevel(trackNum, delta) {
    const track = this.patterns[trackNum - 1];
    if (!track) return;
    const cur = track.level ?? track.volume ?? 0.7;
    track.level = Math.max(0, Math.min(1, Math.round((cur + delta) * 100) / 100));
    track.volume = track.level;
    this.updateTrackGains();
    this.onPresetChangeCallbacks.forEach(cb => cb(this.presetNames[this.presetIndex], this.patterns));
  }

  onTrackLaunch(cb) { this.onTrackLaunchCallbacks.push(cb); }
  onTransport(cb) { this.onTransportCallbacks.push(cb); }
  onTempo(cb) { this.onTempoCallbacks.push(cb); }
  onStep(cb) { this.onStepCallbacks.push(cb); }
  onMasterLevel(cb) { this.onMasterLevelCallbacks.push(cb); }
  onPresetChange(cb) { this.onPresetChangeCallbacks.push(cb); }
  onLearn(cb) { this.onLearnCallbacks.push(cb); }
  onLayerChange(cb) { this.onLayerChangeCallbacks.push(cb); }
  onLastPad(cb) { this.onLastPadCallbacks.push(cb); }

  dispose() {
    if (this.lookaheadTimerId) clearInterval(this.lookaheadTimerId);
    this.kit?.dispose();
    this.actx?.close();
  }
}
