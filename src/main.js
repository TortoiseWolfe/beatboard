/**
 * MAIN — entry point, wires engine to UI
 */
import { Engine } from './engine.js';
import { getMusicianForTrack, getPortraitPath, getLogoPath, getAllMusicians } from './band.js';

const engine = new Engine();
let activeLaunchButtons = new Set();
let mixLatched = false;

async function init() {
  await engine.init();
  buildMixer();
  bindUI();
  engine.onTransport(playing => updatePlayButton(playing));
  engine.onTempo(tempo => updateTempoDisplay(tempo));
  engine.onStep(step => highlightStep(step));
  engine.onMasterLevel(level => updateMasterFader(level));
  engine.onPresetChange((name, patterns) => {
    updatePresetDisplay(name);
    rebuildMixerPatterns(patterns);
  });
  engine.onLearn((active, code, binding) => updateLearnUI(active, code, binding));
  engine.onLayerChange(layer => updateLayerUI(layer));
  updatePlayButton(false);
  updateTempoDisplay(engine.tempo);
  updatePresetDisplay(engine.presetNames[engine.presetIndex]);
  renderBandList();
  loadPortraits();
}

function buildMixer() {
  const container = document.getElementById('mixerTracks');
  container.innerHTML = '';

  engine.patterns.forEach((track, i) => {
    const trackNum = i + 1;
    const casting = getMusicianForTrack(trackNum);
    const musician = casting?.musician;
    const guest = casting?.guest;
    const portraitUrl = musician ? getPortraitPath(musician.name) : '';

    const strip = document.createElement('div');
    strip.className = 'mixer-track';
    strip.dataset.track = trackNum;
    strip.innerHTML = `
      <div class="strip-launch" data-track="${trackNum}" aria-label="Launch track ${trackNum}">
        <span class="launch-light"></span>
      </div>
      <div class="strip-portrait" style="background-image: url('${portraitUrl}')" aria-label="${musician?.name || ''}"></div>
      <div class="strip-name">${musician?.name || `Track ${trackNum}`}</div>
      <div class="strip-role">${musician?.role || ''}${guest ? ` + ${guest.name}` : ''}</div>
      <div class="strip-controls">
        <button class="btn-mute" data-track="${trackNum}" aria-label="Mute (MIX: QWERTYUI)">${track.muted ? 'M' : 'M'}</button>
        <button class="btn-solo" data-track="${trackNum}" aria-label="Solo (MIX: ASDFGHJK)">${track.solo ? 'S' : 'S'}</button>
      </div>
      <div class="strip-fader">
        <input type="range" class="fader" data-track="${trackNum}" min="0" max="100" value="${Math.round((track.level || 0.7) * 100)}" aria-label="Track ${trackNum} level (MIX: ZXCVBNM,)">
      </div>
      <div class="strip-value">${Math.round((track.level || 0.7) * 100)}%</div>
    `;
    container.appendChild(strip);
  });

  container.querySelectorAll('.strip-launch').forEach(btn => {
    btn.addEventListener('click', () => {
      const track = parseInt(btn.dataset.track);
      engine.launchTrack(track, null, false);
    });
  });

  container.querySelectorAll('.btn-mute').forEach(btn => {
    btn.addEventListener('click', () => {
      const track = parseInt(btn.dataset.track);
      engine.toggleMute(track);
      updateMuteSoloButtons();
    });
  });

  container.querySelectorAll('.btn-solo').forEach(btn => {
    btn.addEventListener('click', () => {
      const track = parseInt(btn.dataset.track);
      engine.toggleSolo(track);
      updateMuteSoloButtons();
    });
  });

  container.querySelectorAll('.fader').forEach(fader => {
    fader.addEventListener('input', () => {
      const track = parseInt(fader.dataset.track);
      const level = parseInt(fader.value) / 100;
      engine.adjustLevel(track, level - (engine.patterns[track - 1]?.level || 0.7));
    });
  });

  updateMuteSoloButtons();
}

function rebuildMixerPatterns(patterns) {
  const container = document.getElementById('mixerTracks');
  patterns.forEach((track, i) => {
    const trackNum = i + 1;
    const fader = container.querySelector(`.fader[data-track="${trackNum}"]`);
    const value = container.querySelector(`.strip-value:nth-of-type(${i + 1})`);
    if (fader) fader.value = Math.round((track.level || 0.7) * 100);
    if (value) value.textContent = `${Math.round((track.level || 0.7) * 100)}%`;
  });
  updateMuteSoloButtons();
  updateLaunchLights();
}

function updateMuteSoloButtons() {
  document.querySelectorAll('.btn-mute').forEach(btn => {
    const track = parseInt(btn.dataset.track);
    const t = engine.patterns[track - 1];
    btn.textContent = t.muted ? 'M' : 'M';
    btn.classList.toggle('active', t.muted);
  });
  document.querySelectorAll('.btn-solo').forEach(btn => {
    const track = parseInt(btn.dataset.track);
    const t = engine.patterns[track - 1];
    btn.textContent = t.solo ? 'S' : 'S';
    btn.classList.toggle('active', t.solo);
  });
}

function updateLaunchLights() {
  document.querySelectorAll('.strip-launch').forEach(btn => {
    const track = parseInt(btn.dataset.track);
    const t = engine.patterns[track - 1];
    const light = btn.querySelector('.launch-light');
    light.classList.toggle('active', t.launched && !t.muted);
  });
}

function bindUI() {
  document.addEventListener('keydown', e => engine.handleKeyDown(e));
  document.addEventListener('keyup', e => engine.handleKeyUp(e));

  document.getElementById('btnPlay').addEventListener('click', () => engine.toggleTransport());
  document.getElementById('btnPresetPrev').addEventListener('click', () => engine.changePreset(-1));
  document.getElementById('btnPresetNext').addEventListener('click', () => engine.changePreset(1));
  document.getElementById('btnLearn').addEventListener('click', () => engine.toggleLearnMode());
  document.getElementById('btnBand').addEventListener('click', () => openBandDialog());

  document.getElementById('masterFader').addEventListener('input', e => {
    engine.changeMasterLevel((parseInt(e.target.value) / 100) - engine.masterLevel);
  });

  document.getElementById('closeBandDialog').addEventListener('click', () => closeBandDialog());
  document.getElementById('cancelLearn').addEventListener('click', () => {
    engine.learnMode.cancel();
    updateLearnUI(false);
  });

  document.getElementById('bandDialog').addEventListener('click', e => {
    if (e.target === e.currentTarget) closeBandDialog();
  });
  document.getElementById('learnDialog').addEventListener('click', e => {
    if (e.target === e.currentTarget) {
      engine.learnMode.cancel();
      updateLearnUI(false);
    }
  });

  document.querySelectorAll('.keycap').forEach(keycap => {
    keycap.addEventListener('click', () => handleKeycapClick(keycap));
    keycap.addEventListener('dragover', e => e.preventDefault());
    keycap.addEventListener('drop', e => handleDrop(e, keycap));
  });

  document.querySelectorAll('.mixer-track').forEach(strip => {
    strip.addEventListener('dragover', e => e.preventDefault());
    strip.addEventListener('drop', e => handleDrop(e, strip));
  });

  document.addEventListener('keydown', e => {
    if (e.code === 'Space' && !isTextInputFocused()) {
      e.preventDefault();
      if (!mixLatched) engine.setLayer('mix');
    }
    if (e.code === 'Tab' && !isTextInputFocused()) {
      e.preventDefault();
      mixLatched = !mixLatched;
      engine.setLayer(mixLatched ? 'mix' : 'play');
    }
  });
  document.addEventListener('keyup', e => {
    if (e.code === 'Space' && !mixLatched) {
      engine.setLayer('play');
    }
  });
}

function isTextInputFocused() {
  const el = document.activeElement;
  if (!el) return false;
  const tag = el.tagName.toLowerCase();
  return tag === 'input' || tag === 'textarea' || el.isContentEditable;
}

function handleKeycapClick(keycap) {
  if (engine.learnMode.isActive()) {
    const track = parseInt(keycap.dataset.track);
    const pad = keycap.dataset.pad;
    const action = keycap.dataset.action;
    if (action === 'hit' || action === 'launch') {
      engine.learnMode.enter(action, track, pad);
      updateLearnUI(true);
    }
    return;
  }

  const action = keycap.dataset.action;
  const track = parseInt(keycap.dataset.track);
  const pad = keycap.dataset.pad;
  const kind = keycap.dataset.kind;
  const shift = false;

  if (action === 'hit') {
    engine.playHit(track, pad, { track, pad, note: keycap.dataset.note, sharp: keycap.dataset.sharp === 'true', octave: parseInt(keycap.dataset.octave) || 0 });
    flashKeycap(keycap);
  } else if (action === 'launch') {
    engine.launchTrack(track, kind, shift);
    flashLaunchButton(track);
  }
}

function flashKeycap(keycap) {
  keycap.classList.add('playing');
  setTimeout(() => keycap.classList.remove('playing'), 100);
}

function flashLaunchButton(track) {
  const btn = document.querySelector(`.strip-launch[data-track="${track}"]`);
  if (btn) {
    btn.classList.add('launching');
    setTimeout(() => btn.classList.remove('launching'), 200);
  }
}

function highlightStep(step) {
  document.querySelectorAll('.keycap-row').forEach(row => {
    const track = parseInt(row.dataset.track);
    const pattern = engine.patterns[track - 1];
    if (pattern && pattern.pattern[step] === 1) {
      row.classList.add('step-active');
      setTimeout(() => row.classList.remove('step-active'), 50);
    }
  });
}

function updatePlayButton(playing) {
  const btn = document.getElementById('btnPlay');
  btn.textContent = playing ? '⏸' : '▶';
  btn.setAttribute('aria-label', playing ? 'Stop (Enter)' : 'Play (Enter)');
}

function updateTempoDisplay(tempo) {
  document.getElementById('tempoDisplay').textContent = `${tempo} BPM`;
}

function updatePresetDisplay(name) {
  document.getElementById('presetDisplay').textContent = name;
}

function updateMasterFader(level) {
  const fader = document.getElementById('masterFader');
  const value = document.getElementById('masterValue');
  fader.value = Math.round(level * 100);
  value.textContent = `${Math.round(level * 100)}%`;
}

function updateLearnUI(active, code, binding) {
  const dialog = document.getElementById('learnDialog');
  const prompt = document.getElementById('learnPrompt');
  if (active) {
    dialog.showModal();
    prompt.textContent = 'Click a pad or control, then press a key…';
  } else if (code && binding) {
    prompt.textContent = `Assigned <kbd>${code}</kbd> → ${binding.action} track ${binding.track}${binding.pad ? ` (${binding.pad})` : ''}`;
    setTimeout(() => dialog.close(), 1500);
  } else {
    dialog.close();
  }
}

function updateLayerUI(layer) {
  document.body.classList.toggle('mix-layer', layer === 'mix');
}

function openBandDialog() {
  document.getElementById('bandDialog').showModal();
}

function closeBandDialog() {
  document.getElementById('bandDialog').close();
}

function renderBandList() {
  const list = document.getElementById('bandList');
  const members = getAllMusicians();
  list.innerHTML = members.map(m => `
    <li>
      <img src="${getPortraitPath(m.name)}" alt="${m.look}" width="48" height="48">
      <strong>${m.name}</strong> — ${m.instrument} (${m.role})
      <span class="personality">${m.personality}</span>
    </li>
  `).join('');
}

async function loadPortraits() {
  const logoEl = document.getElementById('portraitMaster');
  logoEl.style.backgroundImage = `url(${getLogoPath()})`;
}

async function handleDrop(e, target) {
  e.preventDefault();
  const file = e.dataTransfer.files[0];
  if (!file || !file.type.startsWith('audio/')) return;

  let track = parseInt(target.dataset.track);
  if (isNaN(track)) {
    const strip = target.closest('.mixer-track');
    if (strip) track = parseInt(strip.dataset.track);
  }
  if (isNaN(track)) return;

  const arrayBuffer = await file.arrayBuffer();
  const buffer = await engine.actx.decodeAudioData(arrayBuffer);

  const trackObj = engine.patterns[track - 1];
  if (!trackObj) return;

  trackObj.userBuffer = buffer;
  trackObj.userBufferName = file.name;
  console.log(`Loaded user sample for track ${track}: ${file.name}`);
}

init().catch(console.error);